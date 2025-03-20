from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask, request, jsonify, send_file
import requests
import re
import threading
import os
import json
import importlib
from pymongo import MongoClient
from config import *
from auth import AUTH_TOKEN

# Function to reload configuration
def reload_config():
    global AUTH_TOKEN, MONGODB_ENABLED, MONGODB_URI, JSON_CACHE_ENABLED, START_IMAGE_URL, HEADERS
    importlib.reload(importlib.import_module('config'))
    importlib.reload(importlib.import_module('auth'))
    from config import MONGODB_ENABLED, MONGODB_URI, JSON_CACHE_ENABLED, START_IMAGE_URL
    from auth import AUTH_TOKEN
    # Update headers with new token
    HEADERS['authorization'] = f'Bearer {AUTH_TOKEN}'
    return 'Configuration reloaded successfully'

# Admin commands for configuration management
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        if update.callback_query:
            await update.callback_query.answer("Unauthorized access", show_alert=True)
        else:
            await update.message.reply_text(f"{BOT_THEME['symbols']['error']} This command is only available to the bot owner.")
        return
    
    keyboard = [
        [InlineKeyboardButton('🔧 View Settings', callback_data='view_settings')],
        [InlineKeyboardButton('🔄 Update AUTH_TOKEN', callback_data='update_auth')],
        [InlineKeyboardButton('📡 MongoDB Settings', callback_data='mongodb_settings')],
        [InlineKeyboardButton('💾 JSON Cache Settings', callback_data='json_settings')],
        [InlineKeyboardButton('🖼 Update Start Image', callback_data='update_image')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        '🎛 *ᴀᴅᴍɪɴ ᴄᴏɴᴛʀᴏʟ ᴘᴀɴᴇʟ*\n'
        'Select an option to view or modify settings:'
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=message,
            parse_mode='MarkdownV2',
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text=message,
            parse_mode='MarkdownV2',
            reply_markup=reply_markup
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != OWNER_ID:
        await query.answer("Unauthorized access", show_alert=True)
        return
    
    if query.data == 'view_settings':
        settings = (
            f'*Current Settings*\n\n'
            f'🔐 *MongoDB*\n'
            f'Enabled: {MONGODB_ENABLED}\n'
            f'URI: `{MONGODB_URI}`\n\n'
            f'💾 *JSON Cache*\n'
            f'Enabled: {JSON_CACHE_ENABLED}\n'
            f'File: `{JSON_CACHE_FILE}`\n\n'
            f'🖼 *Start Image*\n'
            f'URL: `{START_IMAGE_URL}`'
        )
        keyboard = [[InlineKeyboardButton('« Back', callback_data='back_to_main')]]
        await query.edit_message_text(
            text=settings,
            parse_mode='MarkdownV2',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == 'update_auth':
        keyboard = [[InlineKeyboardButton('« Back', callback_data='back_to_main')]]
        await query.edit_message_text(
            text='Send the new AUTH_TOKEN in this format:\n/set_auth_token YOUR_NEW_TOKEN',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == 'mongodb_settings':
        keyboard = [
            [InlineKeyboardButton('Toggle MongoDB', callback_data='toggle_mongodb')],
            [InlineKeyboardButton('Update URI', callback_data='update_mongodb_uri')],
            [InlineKeyboardButton('« Back', callback_data='back_to_main')]
        ]
        await query.edit_message_text(
            text=f'*MongoDB Settings*\n\n'
                 f'Current status: {"Enabled" if MONGODB_ENABLED else "Disabled"}\n'
                 f'URI: `{MONGODB_URI}`',
            parse_mode='MarkdownV2',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == 'json_settings':
        keyboard = [
            [InlineKeyboardButton('Toggle JSON Cache', callback_data='toggle_json')],
            [InlineKeyboardButton('« Back', callback_data='back_to_main')]
        ]
        await query.edit_message_text(
            text=f'*JSON Cache Settings*\n\n'
                 f'Current status: {"Enabled" if JSON_CACHE_ENABLED else "Disabled"}',
            parse_mode='MarkdownV2',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == 'update_image':
        keyboard = [[InlineKeyboardButton('« Back', callback_data='back_to_main')]]
        await query.edit_message_text(
            text='Send the new image URL in this format:\n/set_image_url YOUR_IMAGE_URL',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == 'back_to_main':
        await admin_panel(update, context)
    
    elif query.data in ['toggle_mongodb', 'toggle_json']:
        setting_type = 'MONGODB_ENABLED' if query.data == 'toggle_mongodb' else 'JSON_CACHE_ENABLED'
        current_value = MONGODB_ENABLED if query.data == 'toggle_mongodb' else JSON_CACHE_ENABLED
        
        try:
            with open('config.py', 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            new_content = config_content.replace(
                f'{setting_type} = {str(current_value)}',
                f'{setting_type} = {str(not current_value)}'
            )
            
            with open('config.py', 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            reload_config()
            keyboard = [[InlineKeyboardButton('« Back', callback_data='back_to_main')]]
            await query.edit_message_text(
                text=f'✅ {setting_type} has been toggled to {not current_value}',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            keyboard = [[InlineKeyboardButton('« Back', callback_data='back_to_main')]]
            await query.edit_message_text(
                text=f'❌ Error: {str(e)}',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

async def update_auth_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text(f"{BOT_THEME['symbols']['error']} Unauthorized access")
        return
    
    try:
        new_token = context.args[0]
        with open('auth.py', 'w', encoding='utf-8') as f:
            f.write(f'# Authorization token for Rooter.io API\nAUTH_TOKEN = "{new_token}"\n')
        reload_config()
        await update.message.reply_text(f"{BOT_THEME['symbols']['success']} AUTH_TOKEN updated successfully")
    except Exception as e:
        await update.message.reply_text(f"{BOT_THEME['symbols']['error']} Error: {str(e)}")

async def update_mongodb_uri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text(f"{BOT_THEME['symbols']['error']} Unauthorized access")
        return
    
    try:
        new_uri = ' '.join(context.args)
        with open('config.py', 'r', encoding='utf-8') as f:
            config_content = f.read()
        
        new_content = re.sub(
            r'MONGODB_URI = ".*"',
            f'MONGODB_URI = "{new_uri}"',
            config_content
        )
        
        with open('config.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        reload_config()
        await update.message.reply_text(f"{BOT_THEME['symbols']['success']} MongoDB URI updated successfully")
    except Exception as e:
        await update.message.reply_text(f"{BOT_THEME['symbols']['error']} Error: {str(e)}")

async def update_image_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text(f"{BOT_THEME['symbols']['error']} Unauthorized access")
        return
    
    try:
        new_url = context.args[0]
        with open('config.py', 'r', encoding='utf-8') as f:
            config_content = f.read()
        
        new_content = re.sub(
            r'START_IMAGE_URL = ".*"',
            f'START_IMAGE_URL = "{new_url}"',
            config_content
        )
        
        with open('config.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        reload_config()
        await update.message.reply_text(f"{BOT_THEME['symbols']['success']} Start image URL updated successfully")
    except Exception as e:
        await update.message.reply_text(f"{BOT_THEME['symbols']['error']} Error: {str(e)}")

app = Flask(__name__)

# Initialize MongoDB client if enabled
mongo_client = None
mongo_collection = None
if MONGODB_ENABLED:
    try:
        mongo_client = MongoClient(MONGODB_URI)
        mongo_db = mongo_client[MONGODB_DB]
        mongo_collection = mongo_db[MONGODB_COLLECTION]
        print("MongoDB connection established successfully")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")

def save_to_cache(user_id, username):
    """Save username to both MongoDB and JSON cache if enabled"""
    if MONGODB_ENABLED and mongo_collection is not None:
        try:
            mongo_collection.update_one(
                {"user_id": user_id},
                {"$set": {"username": username}},
                upsert=True
            )
        except Exception as e:
            print(f"MongoDB save error: {e}")
    
    if JSON_CACHE_ENABLED:
        try:
            cache_data = {}
            if os.path.exists(JSON_CACHE_FILE):
                with open(JSON_CACHE_FILE, 'r') as f:
                    cache_data = json.load(f)
            cache_data[user_id] = username
            with open(JSON_CACHE_FILE, 'w') as f:
                json.dump(cache_data, f, indent=4)
        except Exception as e:
            print(f"JSON cache save error: {e}")

def get_from_cache(user_id):
    """Try to get username from cache (MongoDB or JSON)"""
    if MONGODB_ENABLED and mongo_collection is not None:
        try:
            result = mongo_collection.find_one({"user_id": user_id})
            if result:
                return result["username"]
        except Exception as e:
            print(f"MongoDB lookup error: {e}")
    
    if JSON_CACHE_ENABLED and os.path.exists(JSON_CACHE_FILE):
        try:
            with open(JSON_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                return cache_data.get(user_id)
        except Exception as e:
            print(f"JSON cache lookup error: {e}")
    
    return None
API_URL = "https://bazaar.rooter.io/order/getUnipinUsername?gameCode=BGMI_IN&id={}"  # API URL
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "app-version": "1.0.0",
    "authorization": f"Bearer {AUTH_TOKEN}",
    "device-id": "02b11c30-047d-11f0-8b2d-dbab3e96ae19",
    "device-type": "web",
    "origin": "https://shop.rooter.gg",
    "priority": "u=1, i",
    "referer": "https://shop.rooter.gg/",
    "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": "Android",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Mobile Safari/537.36"
}

def get_html_content():
    try:
        html_path = os.path.join('bgmi.html')
        if os.path.exists(html_path):
            return send_file(html_path)
        else:
            return jsonify({'error': 'HTML file not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def format_response(data, user_id=None):
    try:
        if data.get('transaction') == 'SUCCESS' and data.get('unipinRes', {}).get('username'):
            username = data['unipinRes']['username']
            if user_id:
                save_to_cache(user_id, username)
            return username, 200
        elif data.get('transaction') == 'FAILED':
            return 'Incorrect Player Id', 404
        elif data.get('success') is False and data.get('statusCode') == 403:
            return {'error': data.get('message', 'Authentication failed')}, 403
        else:
            # For any other response format, return the complete message
            return {'error': data.get('message', str(data))}, 500
    except Exception as e:
        return {'error': str(e)}, 500

# Flask routes
@app.route('/bgmi', methods=['GET'])
def get_username():
    user_id = request.args.get('id')
    if not user_id:
        return get_html_content()
    
    # Try to get from cache first
    cached_username = get_from_cache(user_id)
    if cached_username:
        return cached_username, 200
        
    try:
        url = API_URL.format(user_id)
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code == 200:
            data = response.json()
            formatted_response, status_code = format_response(data, user_id)
            return jsonify(formatted_response), status_code
        else:
            data = response.json()
            return jsonify({'error': data.get('message', 'Cookies Expired. Please update your cookies.')}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/', methods=['POST'])
def post_username():
    user_id = request.json.get('id')
    if not user_id:
        return jsonify({'error': 'ID parameter is required in JSON body'}), 400
    
    # Try to get from cache first
    cached_username = get_from_cache(user_id)
    if cached_username:
        return jsonify({'username': cached_username}), 200
    
    try:
        url = API_URL.format(user_id)
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code == 200:
            data = response.json()
            formatted_response, status_code = format_response(data, user_id)
            return jsonify(formatted_response), status_code
        else:
            data = response.json()
            return jsonify({'error': data.get('message', 'Cookies Expired. Please update your cookies.')}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Telegram bot functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = context.bot.username
    bot_name = context.bot.first_name
    # Escape special characters for MarkdownV2
    bot_name_escaped = re.escape(bot_name)
    # Properly escape underscores in username
    bot_username_escaped = bot_username.replace('_', '\\_')

    message = (
        f"✦ ʜᴇʟʟᴏ ᴅᴇᴀʀ, ɪ'ᴍ [{bot_name_escaped}](https://t\\.me/{bot_username_escaped}) 🤖\n"
        "⚘ ᴀ ᴘᴏᴡᴇʀғᴜʟ ᴀɴᴅ ʀᴇʟɪᴀʙʟᴇ ɢᴀᴍᴇ ᴜsᴇʀɴᴀᴍᴇ ᴄʜᴇᴄᴋᴇʀ ʙᴏᴛ\\. 🔍\n\n"
        "❖ ᴡʜʏ ᴜɴɪᴘɪɴ ᴄʜᴇᴄᴋᴇʀ ɪs ᴜsᴇғᴜʟ?\n"
        "┏━━━━━━━━━━━━━━━━━━⧫\n"
        "┠● ɪɴsᴛᴀɴᴛ ɢᴀᴍᴇ ᴜsᴇʀɴᴀᴍᴇ ʟᴏᴏᴋᴜᴘ 🎮\n"
        "┠● ғᴇᴛᴄʜ ᴜsᴇʀ ɪɴғᴏʀᴍᴀᴛɪᴏɴ ᴜsɪɴɢ ɪᴅ 📊\n"
        "┠● ᴜsᴇ ᴄᴏᴍᴍᴀɴᴅs /get, GET, /check ᴛᴏ ғᴇᴛᴄʜ ᴅᴀᴛᴀ 🚀\n"
        "┠● ʟɪɢʜᴛᴡᴇɪɢʜᴛ, ʟᴀɢ\\-ғʀᴇᴇ ᴇxᴘᴇʀɪᴇɴᴄᴇ ⚡\n"
        "┗━━━━━━━━━━━━━━━━━━⧫\n"
        f"⦿ ʙᴏᴛ: @{bot_username_escaped} ✅\n"
        "⦿ ᴛʀʏ ɪᴛ ɴᴏᴡ ᴀɴᴅ sᴛᴀʏ ᴜᴘᴅᴀᴛᴇᴅ\\! 🛠"
    )
    
    try:
        # Send the start image if configured
        if START_IMAGE_URL:
            await update.message.reply_photo(
                photo=START_IMAGE_URL,
                caption=message,
                parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(message, parse_mode="MarkdownV2")
    except Exception as e:
        # Fallback to text-only message if image fails
        print(f"Error sending start image: {e}")
        await update.message.reply_text(message, parse_mode="MarkdownV2")

async def get_cached_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ɪs ᴏɴʟʏ ᴀᴠᴀɪʟᴀʙʟᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ\\.")
        return
    
    mongodb_data = []
    json_data = []
    
    # Get MongoDB data
    if MONGODB_ENABLED and mongo_collection is not None:
        try:
            cursor = mongo_collection.find({}, {"_id": 0})
            mongodb_data = [f"ɪᴅ: {doc['user_id']} \\- ᴜsᴇʀɴᴀᴍᴇ: {doc['username']}" for doc in cursor]
        except Exception as e:
            mongodb_data = [f"ᴇʀʀᴏʀ ғᴇᴛᴄʜɪɴɢ ᴍᴏɴɢᴏᴅʙ ᴅᴀᴛᴀ: {str(e)}"]
    
    # Get JSON data
    if JSON_CACHE_ENABLED and os.path.exists(JSON_CACHE_FILE):
        try:
            with open(JSON_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                json_data = [f"ɪᴅ: {user_id} \\- ᴜsᴇʀɴᴀᴍᴇ: {username}" for user_id, username in cache_data.items()]
        except Exception as e:
            json_data = [f"ᴇʀʀᴏʀ ғᴇᴛᴄʜɪɴɢ ᴊsᴏɴ ᴅᴀᴛᴀ: {str(e)}"]
    
    # Create content for text file
    content = "=== ᴍᴏɴɢᴏᴅʙ ᴄᴀᴄʜᴇ ===\n"
    content += "\n".join(mongodb_data) if mongodb_data else "ɴᴏ ᴅᴀᴛᴀ ᴏʀ ᴍᴏɴɢᴏᴅʙ ᴅɪsᴀʙʟᴇᴅ\n"
    content += "\n\n=== ᴊsᴏɴ ᴄᴀᴄʜᴇ ===\n"
    content += "\n".join(json_data) if json_data else "ɴᴏ ᴅᴀᴛᴀ ᴏʀ ᴊsᴏɴ ᴄᴀᴄʜᴇ ᴅɪsᴀʙʟᴇᴅ\n"
    
    # Save to temporary file and send
    try:
        with open('cache_data.txt', 'w', encoding='utf-8') as f:
            f.write(content)
        with open('cache_data.txt', 'rb') as f:
            await update.message.reply_document(f, filename='cache_data.txt')
        os.remove('cache_data.txt')  # Clean up
    except Exception as e:
        await update.message.reply_text(f"❌ ᴇʀʀᴏʀ ᴄʀᴇᴀᴛɪɴɢ ᴄᴀᴄʜᴇ ғɪʟᴇ: {str(e)}")

async def fetch_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    match = re.search(r"(?:/get|GET|/check)\s(\d+)", text)
    
    if match:
        user_id = match.group(1)
        
        # Send loader message
        loader_message = await update.message.reply_text("⏳ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ, ғᴇᴛᴄʜɪɴɢ ᴘʟᴀʏᴇʀ ᴜsᴇʀɴᴀᴍᴇ...")
        
        # Try to get from cache first
        cached_username = get_from_cache(user_id)
        if cached_username:
            await loader_message.delete()
            await update.message.reply_text(f"🔹 ᴜsᴇʀɴᴀᴍᴇ: {cached_username}")
            return
        
        url = API_URL.format(user_id)
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('transaction') == 'SUCCESS' and data.get('unipinRes', {}).get('username'):
                username = data['unipinRes']['username']
                save_to_cache(user_id, username)
                await loader_message.delete()
                await update.message.reply_text(f"🔹 ᴜsᴇʀɴᴀᴍᴇ: {username}")
            elif data.get('transaction') == 'FAILED':
                await loader_message.delete()
                await update.message.reply_text("❌ ɪɴᴄᴏʀʀᴇᴄᴛ ᴘʟᴀʏᴇʀ ɪᴅ")
            elif data.get('success') is False and data.get('statusCode') == 403:
                await loader_message.delete()
                error_msg = data.get('message', 'ᴀᴜᴛʜᴇɴᴛɪᴄᴀᴛɪᴏɴ ғᴀɪʟᴇᴅ')
                await update.message.reply_text(f"❌ {error_msg}")
            else:
                await loader_message.delete()
                error_msg = data.get('message', str(data))
                await update.message.reply_text(f"❌ {error_msg}")
        else:
            data = response.json()
            await loader_message.delete()
            error_msg = data.get('message', 'ᴄᴏᴏᴋɪᴇs ᴇxᴘɪʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴜᴘᴅᴀᴛᴇ ʏᴏᴜʀ ᴄᴏᴏᴋɪᴇs.')
            await update.message.reply_text(f"❌ {error_msg}")
    else:
        await update.message.reply_text("⚠ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɪᴅ ᴀғᴛᴇʀ /get, GET, ᴏʀ /check.")

def run_flask():
    app.run(host='0.0.0.0', port=5000)

def run_telegram_bot():
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(MessageHandler(filters.Regex(r"(?:/get|GET|/check)\s\d+"), fetch_id))
    print("Rooter.io Unipin Checker Bot is running...")
    app_bot.run_polling()

if __name__ == "__main__":
    # Initialize and start the Telegram bot
    application = Application.builder().token(TOKEN).build()
    
    # Basic command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler(["get", "check", "GET", "id", "fetch"], fetch_id))
    application.add_handler(CommandHandler("getcache", get_cached_data))
    
    # Admin command handlers
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("set_auth_token", update_auth_token))
    application.add_handler(CommandHandler("set_mongodb_uri", update_mongodb_uri))
    application.add_handler(CommandHandler("set_image_url", update_image_url))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("Robin@Urr_wissh Bgmi Name Checker Bot is running...")
    
    # Run Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True  # Make thread daemon so it exits when main program exits
    flask_thread.start()
    
    # Run the bot in the main thread
    application.run_polling()
