import os
import logging
from flask import Flask, request, jsonify
import telebot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot tokens from environment variables
BOT_TOKEN = "7768542371:AAFVJ9PDPSnS63Cm9jWsGtOt4EMwYZJajAA"
ADMIN_BOT_TOKEN = "8446738472:AAHYgjb8CUYbTYiHSwRkCHSR7VzNMoKk_OA"  # Your admin bot token

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

# Video database - update these file_ids with ones from your admin bot
video_database = {
    'video1': {
        'file_id': 'BQACAgUAAxkBAAMKaQAB0oRIgoQzg0I3KCUBJ1YI8PjuAALxGwACrrkIVLjRgoazN5igNgQ',
        'title': 'Amazing Video 1',
        'description': 'This is the first amazing video'
    },
    'video2': {
        'file_id': 'AAMCBQADGQECYDuHaPT0KZILOjJlvHRedB8xTXiM1ucAAuQdAAJVSahXrQZIKoihduEBAAdtAAM2BA',
        'title': 'Awesome Video 2',
        'description': 'This is the second awesome video'
    }
}

# ==================== MAIN BOT HANDLERS ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    """Handle /start command with video parameters"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        command_args = message.text.split()
        
        logger.info(f"Main Bot - User {user_id} ({user_name}) sent: {message.text}")
        
        if len(command_args) > 1 and command_args[1] in video_database:
            video_id = command_args[1]
            video_data = video_database[video_id]
            
            bot.reply_to(message, f"🎬 Sending your video: {video_data['title']}...")
            send_specific_video(message, video_data)
        else:
            bot.reply_to(message,
                "Welcome! 👋\n\n"
                "This bot delivers videos from our website. "
                "Visit our website through the links in our Telegram channel to receive your videos!"
            )
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        bot.reply_to(message, "Sorry, there was an error processing your request.")

def send_specific_video(message, video_data):
    """Send specific video based on video data"""
    try:
        bot.send_video(
            chat_id=message.chat.id,
            video=video_data['file_id'],
            caption=f"🎥 {video_data['title']}\n\n{video_data['description']}\n\nEnjoy! 😊"
        )
        logger.info(f"Video sent successfully: {video_data['title']}")
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        bot.reply_to(message, "Sorry, there was an error sending the video. Please try again.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Handle all other messages for main bot"""
    bot.reply_to(message,
        "📹 I automatically send videos to users who come from our website.\n\n"
        "Visit our website through the links in our Telegram channel to receive your content!\n\n"
        "If you came from the website, make sure you:\n"
        "1. Clicked the link in our channel\n"
        "2. Waited 5 seconds on the website\n"
        "3. Clicked the 'Get Your Video' button\n"
        "4. Came back here to receive your video automatically!"
    )

# ==================== ADMIN BOT HANDLERS ====================

@admin_bot.message_handler(commands=['start'])
def admin_start_command(message):
    """Start command for admin bot"""
    admin_bot.reply_to(message,
        "🤖 **Admin File ID Bot**\n\n"
        "Send or forward any video/file to get its File ID.\n\n"
        "Use this File ID in your main bot's video_database."
    )

@admin_bot.message_handler(content_types=['document', 'video'])
def handle_admin_upload(message):
    """Get file_id from any video/document for admin"""
    
    response_text = "📁 **File Information:**\n\n"
    
    if message.video:
        file_id = message.video.file_id
        response_text += f"🎬 **VIDEO File ID:**\n`{file_id}`\n\n"
        response_text += f"📊 Duration: {message.video.duration}s\n"
        response_text += f"📏 Size: {message.video.file_size} bytes\n"
        response_text += f"🖼️ Resolution: {message.video.width}x{message.video.height}"
        
    elif message.document:
        file_id = message.document.file_id
        response_text += f"📄 **DOCUMENT File ID:**\n`{file_id}`\n\n"
        response_text += f"📝 File Name: {message.document.file_name}\n"
        response_text += f"📦 Size: {message.document.file_size} bytes\n"
        response_text += f"🎞️ MIME Type: {message.document.mime_type}"
    
    logger.info(f"Admin Bot - File ID extracted: {file_id}")
    admin_bot.reply_to(message, response_text, parse_mode='Markdown')

@admin_bot.message_handler(func=lambda message: True)
def handle_admin_message(message):
    """Handle other messages for admin bot"""
    admin_bot.reply_to(message, "📁 Send me a video or file to get its File ID!")

# ==================== FLASK ROUTES ====================

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook for main bot"""
    try:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return 'OK'
    except Exception as e:
        logger.error(f"Main webhook error: {e}")
        return 'Error', 400

@app.route('/admin_webhook', methods=['POST'])
def admin_webhook():
    """Webhook for admin bot"""
    try:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        admin_bot.process_new_updates([update])
        return 'OK'
    except Exception as e:
        logger.error(f"Admin webhook error: {e}")
        return 'Error', 400

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Set webhook for main bot"""
    webhook_url = "https://deliverybot-ph3t.onrender.com/webhook"
    try:
        bot.remove_webhook()
        success = bot.set_webhook(url=webhook_url)
        logger.info(f"Main webhook set: {success} for URL: {webhook_url}")
        return jsonify({"success": True, "url": webhook_url})
    except Exception as e:
        logger.error(f"Error setting main webhook: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/set_admin_webhook', methods=['GET'])
def set_admin_webhook():
    """Set webhook for admin bot"""
    webhook_url = "https://deliverybot-ph3t.onrender.com/admin_webhook"
    try:
        admin_bot.remove_webhook()
        success = admin_bot.set_webhook(url=webhook_url)
        logger.info(f"Admin webhook set: {success} for URL: {webhook_url}")
        return jsonify({"success": True, "url": webhook_url})
    except Exception as e:
        logger.error(f"Error setting admin webhook: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/')
def index():
    return "Both bots are running and ready! 🤖🎬"

@app.route('/setup', methods=['GET'])
def setup_webhooks():
    """Setup both webhooks at once"""
    main_result = set_webhook()
    admin_result = set_admin_webhook()
    return jsonify({
        "main_bot": "Webhook set - visit /set_webhook for details",
        "admin_bot": "Webhook set - visit /set_admin_webhook for details",
        "message": "Both webhooks configured successfully!"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
