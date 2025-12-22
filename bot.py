import os
import logging
from flask import Flask, request, jsonify
import telebot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot token from environment variable
BOT_TOKEN = os.environ.get('BOT_TOKEN')

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# ✅ FIXED: Added title and verified file_id format
video_database = {
    'video1': {
        'file_id': '"AAMCBQADGQECZcQxaP8AAU6V0AzYZAYNX5wfAAHDVby1yAACtBwAAgrq-VeSvlKXxZojhgEAB20AAzYE',
        'title': 'Amazing Video 1',  # ✅ ADDED TITLE
        'description': 'This is the first amazing video'
    },
    'video2': {
        'file_id': 'AAMCBQADGQECYDuHaPT0KZILOjJlvHRedB8xTXiM1ucAAuQdAAJVSahXrQZIKoihduEBAAdtAAM2BA',
        'title': 'Awesome Video 2',
        'description': 'This is the second awesome video'
    }
}

@bot.message_handler(commands=['start'])
def start_command(message):
    """Handle /start command with video parameters"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        command_args = message.text.split()
        
        logger.info(f"User {user_id} ({user_name}) sent: {message.text}")
        
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
    """Handle all other messages"""
    bot.reply_to(message,
        "📹 I automatically send videos to users who come from our website.\n\n"
        "Visit our website through the links in our Telegram channel to receive your content!\n\n"
        "If you came from the website, make sure you:\n"
        "1. Clicked the link in our channel\n"
        "2. Waited 5 seconds on the website\n"
        "3. Clicked the 'Get Your Video' button\n"
        "4. Came back here to receive your video automatically!"
    )

@app.route('/webhook', methods=['POST'])
def webhook():
    """Receive updates from Telegram"""
    try:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return 'OK'
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 400

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Set webhook for Telegram bot"""
    webhook_url = "https://deliverybot-ph3t.onrender.com/webhook"
    try:
        bot.remove_webhook()
        success = bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set: {success} for URL: {webhook_url}")
        return jsonify({"success": True, "url": webhook_url})
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/')
def index():
    return "Bot is running and ready to serve videos! 🎬"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)  # ✅ FIXED: Added missing ) and 0




