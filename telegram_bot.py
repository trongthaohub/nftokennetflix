import os
import telebot
import requests
import tempfile
import time
from datetime import datetime
from dotenv import load_dotenv
from checker import (
    extract_cookies, check_netflix_cookie, generate_token, 
    extract_zip_and_get_files, format_account_details, OWNER_CREDIT
)

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not BOT_TOKEN:
    print("Warning: TELEGRAM_BOT_TOKEN not found in environment or .env file.")

bot = telebot.TeleBot(BOT_TOKEN)

# Helper function to process content
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
        "🎬 *Netflix NFToken Checker Bot*\n\n"
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
    bot.reply_to(message, "📤 Please upload a `.txt` or `.zip` file containing Netflix cookies to start batch checking.", parse_mode='Markdown')

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    file_info = bot.get_file(message.document.file_id)
    filename = message.document.file_name.lower()
    
    if not (filename.endswith('.txt') or filename.endswith('.zip')):
        bot.reply_to(message, "❌ Please upload a `.txt` or `.zip` file.")
        return
    
    status_msg = bot.reply_to(message, f"⏳ Processing `{message.document.file_name}`...")
    
    # Download file
    downloaded_file = bot.download_file(file_info.file_path)
    
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, message.document.file_name)
    
    with open(file_path, 'wb') as f:
        f.write(downloaded_file)
    
    results = []
    
    if filename.endswith('.zip'):
        txt_files = extract_zip_and_get_files(file_path, temp_dir)
        for txt_file in txt_files:
            try:
                with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                result, error = process_cookie_content(content)
                if result:
                    results.append({"filename": os.path.basename(txt_file), **result})
            except:
                pass
    else:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            result, error = process_cookie_content(content)
            if result:
                results.append({"filename": message.document.file_name, **result})
            else:
                bot.edit_message_text(f"❌ Error in `{message.document.file_name}`: {error}", 
                                      chat_id=status_msg.chat.id, message_id=status_msg.message_id)
                return
        except Exception as e:
            bot.edit_message_text(f"❌ Error reading file: {str(e)}", 
                                  chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            return

    if not results:
        bot.edit_message_text("❌ No valid accounts found in the file.", 
                             chat_id=status_msg.chat.id, message_id=status_msg.message_id)
    else:
        valid_count = len(results)
        bot.edit_message_text(f"✅ Found {valid_count} valid accounts. Sending details...", 
                             chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        
        for res in results:
            acc = res['account_info']
            token = res['token_result']
            
            summary = (
                f"✅ *HIT:* `{res['filename']}`\n"
                f"🌍 *Country:* `{acc['country']}` | *Plan:* `{acc['plan']}`\n"
                f"🔑 *URL:* `{token['direct_login_url']}`"
            )
            bot.send_message(message.chat.id, summary, parse_mode='Markdown', disable_web_page_preview=True)
            
            # Send full details as file for each hit
            full_details = format_account_details({**acc, 'token_result': token})
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(full_details)
                temp_path = f.name
            
            with open(temp_path, 'rb') as f:
                bot.send_document(message.chat.id, f, caption=f"📄 Details for `{res['filename']}`")
            os.unlink(temp_path)

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is required. Please set it in .env file.")
    else:
        print("Bot is starting...")
        bot.infinity_polling()
