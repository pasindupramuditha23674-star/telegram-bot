import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import telebot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== EDIT THESE VALUES =====
BOT_TOKEN = "7768542371:AAFVJ9PDPSnS63Cm9jWsGtOt4EMwYZJajAA"  # From STEP 1
ADMIN_BOT_TOKEN = "8224351252:AAGwZel-8rfURnT5zE8dQD9eEUYOBW1vUxU"  # From STEP 2
YOUR_TELEGRAM_ID = 1574602076  # Get from @userinfobot
# ===============================

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

# Database file for persistence
DB_FILE = 'video_database.json'

# ===== DATABASE PERSISTENCE FUNCTIONS =====
def load_database():
    """Load database from JSON file"""
    global video_database
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                video_database = json.load(f)
                logger.info(f"✅ Loaded {len(video_database)} videos from {DB_FILE}")
        else:
            video_database = {}
            logger.info("📂 No existing database, starting fresh")
            
            # Optional: Initialize with some default videos
            video_database.update({
                'video1': {
                    'file_id': 'BAACAgUAAxkBAAEC-DVpSV4-9MJUUM9K4PMX3GnEa_XHugACkx8AAhsKSFbxcawF4hIbRDYE',
                    'title': 'Video 1',
                    'description': 'Enjoy this video!',
                    'added_date': datetime.now().isoformat(),
                    'permanent': False
                },
                'video2': {
                    'file_id': 'BAACAgUAAxkBAAEC-JZpSj7hnbLtxISynqEZcbJHdIv13wACthwAAs3CUVbfKSm2EcblizYE',
                    'title': 'video 2',
                    'description': 'carry mahansi yko meka hadala',
                    'added_date': datetime.now().isoformat(),
                    'permanent': False
                },
                'video3': {
                    'file_id': 'BAACAgUAAxkBAAEC_1xpU2-94qt6O8iraCBHcpwEE-XR5QACzhsAAt76mFbVOIO3Uf6DNjgE',
                    'title': 'video 3',
                    'description': 'carry mahansi yko meka hadala',
                    'added_date': datetime.now().isoformat(),
                    'permanent': False
                },
                'video4': {
                    'file_id': 'BAACAgUAAxkBAAEC_15pU2_srj0d_vapM95_gKc6X0aPzAAC0BsAAt76mFaiYuZBhhd9LjgE',
                    'title': 'video 4',
                    'description': 'carry mahansi yko meka hadala',
                    'added_date': datetime.now().isoformat(),
                    'permanent': False
                }
            })
            save_database()  # Save the initial database
            
    except Exception as e:
        logger.error(f"❌ Error loading database: {e}")
        video_database = {}

def save_database():
    """Save database to JSON file"""
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(video_database, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Saved {len(video_database)} videos to {DB_FILE}")
    except Exception as e:
        logger.error(f"❌ Error saving database: {e}")

# Load database at startup
load_database()

# ==================== PERMANENT FILE ID SYSTEM ====================
@bot.message_handler(content_types=['video'])
def handle_video_upload(message):
    """Get permanent file ID when video is sent directly to main bot"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        bot.reply_to(message, "⛔ This feature is for admin only.")
        return
    
    # Get file information
    file_id = message.video.file_id
    file_unique_id = message.video.file_unique_id
    file_size = message.video.file_size or 0
    duration = message.video.duration or 0
    width = message.video.width or 0
    height = message.video.height or 0
    
    # Send information to user
    bot.reply_to(message,
        f"✅ **Permanent File ID Ready!**\n\n"
        f"**File ID:**\n`{file_id}`\n\n"
        f"**Video Details:**\n"
        f"• Duration: {duration}s\n"
        f"• Resolution: {width}x{height}\n"
        f"• Size: {file_size:,} bytes\n"
        f"• Unique ID: `{file_unique_id}`\n\n"
        f"**To save permanently, reply to this video with:**\n"
        f"`/savevideo 1` (for video1)\n"
        f"`/savevideo 2` (for video2)\n\n"
        f"Or copy the file_id and use:\n"
        f"`/addperm 1 {file_id}`",
        parse_mode='Markdown'
    )
    
    logger.info(f"Video received from admin: {file_unique_id}, size: {file_size}")

@bot.message_handler(commands=['savevideo'])
def save_video_command(message):
    """Save video by replying to a video message (PERMANENT METHOD)"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        bot.reply_to(message, "⛔ Admin only.")
        return
    
    if not message.reply_to_message or not message.reply_to_message.video:
        bot.reply_to(message, "❌ Please reply to a video message with /savevideo [number]")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "Usage: /savevideo [video_number]\nExample: /savevideo 1")
            return
        
        video_num = parts[1]
        video_id = f"video{video_num}"
        file_id = message.reply_to_message.video.file_id
        file_unique_id = message.reply_to_message.video.file_unique_id
        
        # Test the file_id first
        try:
            test_msg = bot.send_video(
                YOUR_TELEGRAM_ID,
                file_id,
                caption=f"✅ TEST: Video {video_num}"
            )
            test_passed = True
        except Exception as test_error:
            test_passed = False
            error_msg = str(test_error)
        
        # Add to database
        video_database[video_id] = {
            'file_id': file_id,
            'file_unique_id': file_unique_id,
            'title': f'Video {video_num}',
            'description': 'Added via permanent method',
            'added_date': datetime.now().isoformat(),
            'permanent': True,
            'size': message.reply_to_message.video.file_size,
            'duration': message.reply_to_message.video.duration
        }
        
        # Save to persistent storage
        save_database()
        
        if test_passed:
            bot.reply_to(message,
                f"✅ **PERMANENT Video Saved!**\n\n"
                f"**Video ID:** {video_id}\n"
                f"**File ID:** `{file_id[:50]}...`\n"
                f"**Test:** ✅ Working perfectly!\n\n"
                f"**Use it now:**\n"
                f"• In bot: /start {video_id}\n"
                f"• Website: https://pasindupramuditha23674-star.github.io/video-site?video={video_num}\n\n"
                f"✅ This file_id should not expire!",
                parse_mode='Markdown'
            )
        else:
            bot.reply_to(message,
                f"⚠ **Video Saved but Test Failed**\n\n"
                f"**Video ID:** {video_id}\n"
                f"**Error:** {error_msg}\n\n"
                f"The file_id may be invalid. Try sending the video again.",
                parse_mode='Markdown'
            )
        
        logger.info(f"Saved {video_id} with permanent file_id")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")
        logger.error(f"Error in save_video_command: {e}")

@bot.message_handler(commands=['addperm'])
def add_permanent_video(message):
    """Add permanent video using file_id directly"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) != 3:
            bot.reply_to(message,
                "Usage: /addperm [video_number] [file_id]\n\n"
                "Example: /addperm 1 BAACAgUAAxkBAAEC-DVpSV4...\n\n"
                "Get file_id by:\n"
                "1. Send video to this bot\n"
                "2. Copy file_id from response\n"
                "3. Use this command"
            )
            return
        
        video_num = parts[1]
        file_id = parts[2]
        video_id = f"video{video_num}"
        
        # Test the file_id
        try:
            test_msg = bot.send_video(YOUR_TELEGRAM_ID, file_id, caption="Testing...")
            test_passed = True
        except Exception as test_error:
            test_passed = False
            error_msg = str(test_error)
        
        # Add to database
        video_database[video_id] = {
            'file_id': file_id,
            'title': f'Video {video_num}',
            'description': 'Added via permanent file_id',
            'added_date': datetime.now().isoformat(),
            'permanent': True
        }
        
        save_database()  # Save to persistent storage
        
        if test_passed:
            bot.reply_to(message, f"✅ Added {video_id} - Test successful!")
        else:
            bot.reply_to(message, f"⚠ Added {video_id} but test failed: {error_msg}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['testvideo'])
def test_video_command(message):
    """Test if a video file_id still works"""
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "Usage: /testvideo [video_number]\nExample: /testvideo 1")
            return
        
        video_num = parts[1]
        video_id = f"video{video_num}"
        
        if video_id not in video_database:
            bot.reply_to(message, f"❌ {video_id} not found in database")
            return
        
        file_id = video_database[video_id]['file_id']
        is_permanent = video_database[video_id].get('permanent', False)
        
        try:
            test_msg = bot.send_video(
                YOUR_TELEGRAM_ID,
                file_id,
                caption=f"✅ Test: {video_id}\nPermanent: {is_permanent}"
            )
            
            status = "✅ PERMANENT - Should not expire" if is_permanent else "✅ TEMPORARY - May expire soon"
            bot.reply_to(message,
                f"**Test Results for {video_id}:**\n\n"
                f"{status}\n"
                f"File ID: `{file_id[:50]}...`\n"
                f"Added: {video_database[video_id].get('added_date', 'Unknown')}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            bot.reply_to(message,
                f"❌ **FILE ID EXPIRED**\n\n"
                f"Video: {video_id}\n"
                f"Error: {str(e)}\n\n"
                f"**Solution:**\n"
                f"1. Send video again to bot\n"
                f"2. Use /savevideo {video_num} to get new permanent ID"
            )
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['listvideos'])
def list_all_videos(message):
    """List all videos in database"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        bot.reply_to(message, "⛔ Admin only.")
        return
    
    if not video_database:
        bot.reply_to(message, "📭 No videos in database")
        return
    
    response = "📹 **All Videos in Database:**\n\n"
    for vid_id, data in video_database.items():
        num = vid_id.replace('video', '')
        status = "✅ PERMANENT" if data.get('permanent', False) else "⚠ TEMPORARY"
        response += f"• **Video {num}** ({status})\n"
        response += f"  Title: {data['title']}\n"
        response += f"  Added: {data.get('added_date', 'Unknown')}\n"
        response += f"  File ID: `{data['file_id'][:30]}...`\n"
        response += f"  Website: https://pasindupramuditha23674-star.github.io/video-site?video={num}\n\n"
    
    response += f"**Total:** {len(video_database)} videos"
    bot.reply_to(message, response, parse_mode='Markdown')

# ==================== MAIN BOT (EXISTING FUNCTIONS) ====================
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
        is_permanent = video_data.get('permanent', False)
        
        caption = f"🎬 {video_data['title']}\n\n{video_data['description']}\n\n"
        if is_permanent:
            caption += "✅ Permanent video - Enjoy! 😊"
        else:
            caption += "⚠ Temporary video - Enjoy! 😊"
        
        bot.send_video(
            message.chat.id,
            video_data['file_id'],
            caption=caption
        )
        logger.info(f"Video {video_id} sent to {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        bot.reply_to(message, "❌ Failed to send video. The file may have expired. Please contact admin.")

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
        
        # Add admin button if user is admin
        if message.from_user.id == YOUR_TELEGRAM_ID:
            keyboard.add(telebot.types.InlineKeyboardButton(
                "🔧 Admin Panel", 
                callback_data="admin_panel"
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
                bot.answer_callback_query(call.id, "❌ Failed to send video")
    
    elif call.data == 'admin_panel' and call.from_user.id == YOUR_TELEGRAM_ID:
        bot.answer_callback_query(call.id, "Opening admin panel...")
        bot.send_message(
            call.from_user.id,
            "🔧 **Admin Panel**\n\n"
            "Commands:\n"
            "/listvideos - Show all videos\n"
            "/testvideo [num] - Test video\n"
            "/savevideo [num] - Save video (reply to video)\n"
            "/addperm [num] [file_id] - Add permanent video"
        )

# ==================== ADMIN BOT (EXISTING FUNCTIONS) ====================
@admin_bot.message_handler(commands=['start'])
def admin_start(message):
    """Admin bot help"""
    admin_bot.reply_to(message,
        "🤖 **Admin Bot**\n\n"
        "Send me videos to get File IDs for your main bot.\n\n"
        "Commands:\n"
        "/addvideo [number] - Add video to database (OLD METHOD)\n"
        "/listvideos - Show all videos\n"
        "/deletevideo [number] - Remove video\n\n"
        "**For PERMANENT file IDs:**\n"
        "Send videos directly to main bot and use /savevideo"
    )

@admin_bot.message_handler(content_types=['video'])
def handle_video(message):
    """Get File ID from video (OLD METHOD)"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        admin_bot.reply_to(message, "⛔ Admin only.")
        return
    
    file_id = message.video.file_id
    file_unique_id = message.video.file_unique_id
    
    admin_bot.reply_to(message,
        f"📹 **File ID (OLD METHOD):**\n`{file_id}`\n\n"
        f"**Unique ID:** `{file_unique_id}`\n\n"
        "⚠ **This method may give temporary file IDs**\n\n"
        "For permanent IDs:\n"
        "1. Send video to main bot directly\n"
        "2. Use /savevideo command\n\n"
        "To add anyway (reply to video):\n"
        "`/addvideo 1`",
        parse_mode='Markdown'
    )

@admin_bot.message_handler(commands=['addvideo'])
def add_video_command(message):
    """Add video to database (OLD METHOD)"""
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
                'description': 'Watch and enjoy!',
                'added_date': datetime.now().isoformat(),
                'permanent': False  # Mark as temporary
            }
            
            save_database()  # Save to persistent storage
            
            admin_bot.reply_to(message,
                f"✅ Added {video_id} (Temporary)\n"
                f"File ID: `{file_id[:30]}...`\n\n"
                f"⚠ **May expire soon**\n"
                f"For permanent: Send to main bot & use /savevideo\n\n"
                f"Test with: /start {video_id} in main bot",
                parse_mode='Markdown'
            )
            logger.info(f"Added {video_id} to database (temporary)")
            
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
        status = "✅ PERMANENT" if data.get('permanent', False) else "⚠ TEMPORARY"
        response += f"• **Video {num}** ({status})\n"
        response += f"  File ID: `{data['file_id'][:30]}...`\n"
        response += f"  Added: {data.get('added_date', 'Unknown')}\n"
        response += f"  Website: https://pasindupramuditha23674-star.github.io/video-site?video={num}\n\n"
    
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
        "admin_bot": "Ready at /admin_webhook",
        "database": f"Loaded {len(video_database)} videos"
    })

@app.route('/reset_database', methods=['GET'])
def reset_database():
    """Reset database to empty (for testing)"""
    if request.args.get('secret') == 'your_secret_key':  # Add a secret key
        global video_database
        video_database = {}
        save_database()
        return jsonify({"message": "Database reset", "count": 0})
    return jsonify({"error": "Unauthorized"}), 403

@app.route('/database_status', methods=['GET'])
def database_status():
    """Check database status"""
    return jsonify({
        "video_count": len(video_database),
        "database_file": DB_FILE,
        "file_exists": os.path.exists(DB_FILE),
        "videos": list(video_database.keys())
    })

@app.route('/')
def home():
    return "✅ Video Delivery Bot is running! Visit /setup to configure webhooks."

if __name__ == '__main__':
    # Initialize database
    load_database()
    
    # Log startup info
    logger.info(f"Bot started with {len(video_database)} videos in database")
    logger.info(f"Admin ID: {YOUR_TELEGRAM_ID}")
    
    app.run(host='0.0.0.0', port=5000)
