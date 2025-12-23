import os
import logging
from flask import Flask, request, jsonify
import telebot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== EDIT THESE 3 VALUES =====
BOT_TOKEN = "7768542371:AAFVJ9PDPSnS63Cm9jWsGtOt4EMwYZJajAA"  # From STEP 1
ADMIN_BOT_TOKEN = "8224351252:AAGwZel-8rfURnT5zE8dQD9eEUYOBW1vUxU"  # From STEP 2
YOUR_TELEGRAM_ID = 1574602076  # Get from @userinfobot
# ===============================

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

# Start with empty database - add videos using admin bot
video_database = {
    'video1': {
        'file_id': 'BAACAgUAAxkBAAEC-DVpSV4-9MJUUM9K4PMX3GnEa_XHugACkx8AAhsKSFbxcawF4hIbRDYE',  # ← Get from admin bot
        'title': 'Video 1',
        'description': 'Enjoy this video!'
    }
}

# ==================== MAIN BOT ====================
@bot.message_handler(commands=['start'])
def handle_start(message):
    """Handle /start command with video parameters"""
    try:
        parts = message.text.split()
        
        if len(parts) > 1 and parts[1] in video_database:
            video_id = parts[1]
            send_video_to_user(message, video_id)
        else:
            show_video_menu(message)
            
    except Exception as e:
        logger.error(f"Error: {e}")
        bot.reply_to(message, "❌ Error. Please try again.")

def send_video_to_user(message, video_id):
    """Send specific video to user"""
    try:
        video_data = video_database[video_id]
        bot.send_video(
            message.chat.id,
            video_data['file_id'],
            caption=f"🎬 {video_data['title']}\n\n{video_data['description']}\n\nEnjoy! 😊"
        )
        logger.info(f"Video {video_id} sent to {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        bot.reply_to(message, "❌ Failed to send video. Please try again.")

def show_video_menu(message):
    """Show available videos"""
    if video_database:
        keyboard = telebot.types.InlineKeyboardMarkup()
        for vid_id in video_database.keys():
            num = vid_id.replace('video', '')
            keyboard.add(telebot.types.InlineKeyboardButton(
                f"🎬 Video {num}", 
                callback_data=f"send_{vid_id}"
            ))
        bot.reply_to(message, "📹 Select a video:", reply_markup=keyboard)
    else:
        bot.reply_to(message, "📭 No videos available yet. Check back soon!")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Handle button clicks"""
    if call.data.startswith('send_'):
        video_id = call.data.replace('send_', '')
        if video_id in video_database:
            try:
                video_data = video_database[video_id]
                bot.send_video(
                    call.from_user.id,
                    video_data['file_id'],
                    caption=f"🎬 {video_data['title']}"
                )
                bot.answer_callback_query(call.id, "✅ Video sent!")
            except:
                bot.answer_callback_query(call.id, "❌ Failed to send")

# ==================== ADMIN BOT ====================
@admin_bot.message_handler(commands=['start'])
def admin_start(message):
    """Admin bot help"""
    admin_bot.reply_to(message,
        "🤖 **Admin Bot**\n\n"
        "Send me videos to get File IDs for your main bot.\n\n"
        "Commands:\n"
        "/addvideo [number] - Add video to database\n"
        "/listvideos - Show all videos\n"
        "/deletevideo [number] - Remove video"
    )

@admin_bot.message_handler(content_types=['video'])
def handle_video(message):
    """Get File ID from video"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        admin_bot.reply_to(message, "⛔ Admin only.")
        return
    
    file_id = message.video.file_id
    admin_bot.reply_to(message,
        f"📹 **File ID:**\n`{file_id}`\n\n"
        "To add to database, reply with:\n"
        "`/addvideo 1` (for video1)\n"
        "`/addvideo 2` (for video2)",
        parse_mode='Markdown'
    )

@admin_bot.message_handler(commands=['addvideo'])
def add_video_command(message):
    """Add video to database"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        admin_bot.reply_to(message, "⛔ Admin only.")
        return
    
    if message.reply_to_message and message.reply_to_message.video:
        try:
            parts = message.text.split()
            if len(parts) != 2:
                admin_bot.reply_to(message, "Usage: /addvideo [number]\nExample: /addvideo 1")
                return
            
            video_num = parts[1]
            video_id = f"video{video_num}"
            file_id = message.reply_to_message.video.file_id
            
            video_database[video_id] = {
                'file_id': file_id,
                'title': f'Video {video_num}',
                'description': 'Watch and enjoy!'
            }
            
            admin_bot.reply_to(message,
                f"✅ Added {video_id}\n"
                f"File ID: `{file_id[:30]}...`\n\n"
                f"Test with: /start {video_id} in main bot",
                parse_mode='Markdown'
            )
            logger.info(f"Added {video_id} to database")
            
        except Exception as e:
            admin_bot.reply_to(message, f"❌ Error: {e}")
    else:
        admin_bot.reply_to(message, "❌ Reply to a video with /addvideo [number]")

@admin_bot.message_handler(commands=['listvideos'])
def list_videos_command(message):
    """List all videos in database"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        admin_bot.reply_to(message, "⛔ Admin only.")
        return
    
    if not video_database:
        admin_bot.reply_to(message, "📭 No videos in database")
        return
    
    response = "📹 **Video Database:**\n\n"
    for vid_id, data in video_database.items():
        num = vid_id.replace('video', '')
        response += f"• **Video {num}:** `{vid_id}`\n"
        response += f"  File ID: `{data['file_id'][:30]}...`\n"
        response += f"  Website link: `https://pasindupramuditha23674-star.github.io/video-site?video={num}`\n\n"
    
    response += f"**Total:** {len(video_database)} videos"
    admin_bot.reply_to(message, response, parse_mode='Markdown')

# ==================== WEBHOOK ROUTES ====================
@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK'

@app.route('/admin_webhook', methods=['POST'])
def admin_webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    admin_bot.process_new_updates([update])
    return 'OK'

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    webhook_url = "https://telegram-bot-7-dqqa.onrender.com/webhook"
    bot.remove_webhook()
    success = bot.set_webhook(url=webhook_url)
    return jsonify({"success": bool(success), "url": webhook_url})

@app.route('/set_admin_webhook', methods=['GET'])
def set_admin_webhook():
    webhook_url = "https://telegram-bot-7-dqqa.onrender.com/admin_webhook"
    admin_bot.remove_webhook()
    success = admin_bot.set_webhook(url=webhook_url)
    return jsonify({"success": bool(success), "url": webhook_url})

@app.route('/setup', methods=['GET'])
def setup_webhooks():
    set_webhook()
    set_admin_webhook()
    return jsonify({
        "message": "Webhooks configured!",
        "main_bot": "Ready at /webhook",
        "admin_bot": "Ready at /admin_webhook"
    })

@app.route('/')
def home():
    return "✅ Video Delivery Bot is running! Visit /setup to configure webhooks."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)



