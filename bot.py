import os
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import telebot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== EDIT THESE VALUES =====
BOT_TOKEN = "7768542371:AAFVJ9PDPSnS63Cm9jWsGtOt4EMwYZJajAA"
ADMIN_BOT_TOKEN = "8224351252:AAGwZel-8rfURnT5zE8dQD9eEUYOBW1vUxU"
YOUR_TELEGRAM_ID = 1574602076
CHANNEL_ID = "@YourChannelUsername"  # ← ADD THIS: Your channel username (e.g., @MyVideoChannel)
# ===============================

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

# Database file for persistence
DB_FILE = 'video_database.json'
# Track sent videos for auto-deletion
SENT_VIDEOS_FILE = 'sent_videos_tracker.json'

# ===== DATABASE FUNCTIONS =====
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

# ===== SENT VIDEOS TRACKER =====
def load_sent_videos():
    """Load sent videos tracker"""
    global sent_videos
    try:
        if os.path.exists(SENT_VIDEOS_FILE):
            with open(SENT_VIDEOS_FILE, 'r') as f:
                sent_videos = json.load(f)
        else:
            sent_videos = {}
    except Exception as e:
        logger.error(f"Error loading sent videos: {e}")
        sent_videos = {}

def save_sent_videos():
    """Save sent videos tracker"""
    try:
        with open(SENT_VIDEOS_FILE, 'w') as f:
            json.dump(sent_videos, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving sent videos: {e}")

def add_sent_video(user_id, message_id, video_id, sent_time):
    """Add sent video to tracker"""
    key = f"{user_id}_{message_id}"
    sent_videos[key] = {
        'user_id': user_id,
        'message_id': message_id,
        'video_id': video_id,
        'sent_time': sent_time,
        'delete_at': (datetime.now() + timedelta(hours=1)).isoformat()
    }
    save_sent_videos()

# ===== AUTO DELETE THREAD =====
def auto_delete_worker():
    """Background thread to delete old videos"""
    while True:
        try:
            current_time = datetime.now()
            to_delete = []
            
            for key, data in sent_videos.items():
                if 'delete_at' in data:
                    delete_time = datetime.fromisoformat(data['delete_at'])
                    if current_time >= delete_time:
                        to_delete.append(key)
            
            for key in to_delete:
                data = sent_videos[key]
                try:
                    bot.delete_message(data['user_id'], data['message_id'])
                    logger.info(f"Auto-deleted video for user {data['user_id']}")
                except Exception as e:
                    logger.error(f"Failed to auto-delete: {e}")
                
                del sent_videos[key]
            
            if to_delete:
                save_sent_videos()
                
            time.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Error in auto_delete_worker: {e}")
            time.sleep(60)

# ===== CHANNEL POSTING FUNCTIONS =====
def post_to_channel(video_num):
    """Post to Telegram channel with Watch Now button"""
    try:
        website_url = f"https://pasindupramuditha23674-star.github.io/video-site?video={video_num}"
        
        # Create inline keyboard with Watch Now button
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                "🎬 Watch Now",
                url=website_url
            )
        )
        
        # Send message to channel
        post_msg = bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"🎥 Video {video_num} Now Available!\n\nClick the button below to watch 👇",
            reply_markup=keyboard
        )
        
        logger.info(f"Posted video {video_num} to channel {CHANNEL_ID}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to post to channel: {e}")
        return False

# Start auto-delete thread
auto_delete_thread = threading.Thread(target=auto_delete_worker, daemon=True)
auto_delete_thread.start()

# Load databases at startup
load_database()
load_sent_videos()

# ==================== PERMANENT FILE ID SYSTEM ====================
@bot.message_handler(content_types=['video'])
def handle_video_upload(message):
    """Get permanent file ID when video is sent directly to main bot"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        bot.reply_to(message, "⛔ This feature is for admin only.")
        return
    
    file_id = message.video.file_id
    file_size = message.video.file_size or 0
    duration = message.video.duration or 0
    
    response = (
        f"✅ PERMANENT FILE ID READY!\n\n"
        f"File ID:\n{file_id}\n\n"
        f"Video Details:\n"
        f"• Duration: {duration}s\n"
        f"• Size: {file_size:,} bytes\n\n"
        f"TO SAVE PERMANENTLY:\n"
        f"Reply to this video with:\n"
        f"/savevideo 1  (for video1)\n\n"
        f"SECURITY FEATURES:\n"
        f"• Auto-delete after 1 hour\n"
        f"• No saving to gallery\n"
        f"• No forwarding allowed"
    )
    
    bot.reply_to(message, response)

@bot.message_handler(commands=['savevideo'])
def save_video_command(message):
    """Save video by replying to a video message"""
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
        
        # Add to database
        video_database[video_id] = {
            'file_id': file_id,
            'title': f'Video {video_num}',
            'added_date': datetime.now().isoformat(),
            'permanent': True
        }
        
        save_database()
        
        # Post to channel
        channel_posted = post_to_channel(video_num)
        
        # Response
        response = (
            f"✅ Video {video_num} saved!\n\n"
            f"Security features enabled:\n"
            f"• Auto-delete after 1 hour\n"
            f"• No saving/forwarding allowed\n\n"
            f"Website link:\n"
            f"https://pasindupramuditha23674-star.github.io/video-site?video={video_num}\n\n"
        )
        
        if channel_posted:
            response += f"✅ Posted to channel: {CHANNEL_ID}"
        else:
            response += f"⚠ Could not post to channel (check CHANNEL_ID)"
        
        response += f"\n\nTest with:\n/start {video_id}"
        
        bot.reply_to(message, response)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:200]}")
        logger.error(f"Error in save_video_command: {e}")

# ==================== VIDEO DELIVERY WITH SECURITY ====================
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
    """Send video with security features"""
    try:
        video_data = video_database[video_id]
        
        # Send video with protected content settings
        sent_msg = bot.send_video(
            chat_id=message.chat.id,
            video=video_data['file_id'],
            caption="",  # Empty caption
            protect_content=True,  # Prevents saving and forwarding
            has_spoiler=False,
            parse_mode=None
        )
        
        # Add to auto-delete tracker
        add_sent_video(
            user_id=message.chat.id,
            message_id=sent_msg.message_id,
            video_id=video_id,
            sent_time=datetime.now().isoformat()
        )
        
        logger.info(f"Protected video {video_id} sent to {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        bot.reply_to(message, "❌ Failed to send video.")

def show_video_menu(message):
    """Show available videos"""
    if video_database:
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        for vid_id in sorted(video_database.keys()):
            num = vid_id.replace('video', '')
            keyboard.add(telebot.types.InlineKeyboardButton(
                f"Video {num}", 
                callback_data=f"send_{vid_id}"
            ))
            
        bot.reply_to(message, "Select a video:", reply_markup=keyboard)
    else:
        bot.reply_to(message, "No videos available yet.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Handle button clicks"""
    if call.data.startswith('send_'):
        video_id = call.data.replace('send_', '')
        if video_id in video_database:
            try:
                video_data = video_database[video_id]
                
                # Send protected video
                sent_msg = bot.send_video(
                    chat_id=call.from_user.id,
                    video=video_data['file_id'],
                    caption="",  # Empty caption
                    protect_content=True,
                    has_spoiler=False,
                    parse_mode=None
                )
                
                # Add to auto-delete tracker
                add_sent_video(
                    user_id=call.from_user.id,
                    message_id=sent_msg.message_id,
                    video_id=video_id,
                    sent_time=datetime.now().isoformat()
                )
                
                bot.answer_callback_query(call.id, "✅ Video sent! (Auto-deletes in 1 hour)")
                
            except Exception as e:
                logger.error(f"Error sending video via callback: {e}")
                bot.answer_callback_query(call.id, "❌ Failed to send video")

# ==================== ADMIN COMMANDS ====================
@bot.message_handler(commands=['testvideo'])
def test_video_command(message):
    """Test if a video file_id still works"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "Usage: /testvideo [video_number]")
            return
        
        video_num = parts[1]
        video_id = f"video{video_num}"
        
        if video_id not in video_database:
            bot.reply_to(message, f"❌ {video_id} not found")
            return
        
        file_id = video_database[video_id]['file_id']
        
        # Test with protected content
        sent_msg = bot.send_video(
            chat_id=YOUR_TELEGRAM_ID,
            video=file_id,
            caption="Test video",
            protect_content=True
        )
        
        # Add to auto-delete for admin too
        add_sent_video(
            user_id=YOUR_TELEGRAM_ID,
            message_id=sent_msg.message_id,
            video_id=video_id,
            sent_time=datetime.now().isoformat()
        )
        
        bot.reply_to(message, f"✅ Test successful! Video will auto-delete in 1 hour")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['listvideos'])
def list_all_videos(message):
    """List all videos in database"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        bot.reply_to(message, "⛔ Admin only.")
        return
    
    if not video_database:
        bot.reply_to(message, "No videos in database")
        return
    
    response = "📹 ALL VIDEOS:\n\n"
    for vid_id in sorted(video_database.keys()):
        num = vid_id.replace('video', '')
        data = video_database[vid_id]
        if data.get('permanent', False):
            status = "✅ PERMANENT"
        else:
            status = "⚠ TEMPORARY"
        response += f"• Video {num} ({status})\n"
        response += f"  Added: {data.get('added_date', 'Unknown')}\n"
        response += f"  URL: https://pasindupramuditha23674-star.github.io/video-site?video={num}\n\n"
    
    response += f"Total: {len(video_database)} videos"
    bot.reply_to(message, response)

@bot.message_handler(commands=['clearvideos'])
def clear_old_sent_videos(message):
    """Manually clear old sent videos"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        current_time = datetime.now()
        deleted_count = 0
        
        for key, data in list(sent_videos.items()):
            if 'delete_at' in data:
                delete_time = datetime.fromisoformat(data['delete_at'])
                if current_time >= delete_time:
                    try:
                        bot.delete_message(data['user_id'], data['message_id'])
                        deleted_count += 1
                    except:
                        pass
                    del sent_videos[key]
        
        save_sent_videos()
        bot.reply_to(message, f"✅ Cleared {deleted_count} old videos")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ===== NEW CHANNEL COMMANDS =====
@bot.message_handler(commands=['posttochannel'])
def manual_post_to_channel(message):
    """Manually post existing video to channel"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "Usage: /posttochannel [video_number]\nExample: /posttochannel 1")
            return
        
        video_num = parts[1]
        video_id = f"video{video_num}"
        
        if video_id not in video_database:
            bot.reply_to(message, f"❌ Video {video_num} not found")
            return
        
        # Post to channel
        if post_to_channel(video_num):
            bot.reply_to(message, f"✅ Video {video_num} posted to channel!")
        else:
            bot.reply_to(message, f"❌ Failed to post to channel. Check CHANNEL_ID.")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['setchannel'])
def set_channel_command(message):
    """Set channel ID dynamically"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            bot.reply_to(message, "Usage: /setchannel @YourChannelUsername\nOr: /setchannel -1234567890")
            return
        
        global CHANNEL_ID
        CHANNEL_ID = parts[1]
        
        # Test the channel
        try:
            test_msg = bot.send_message(CHANNEL_ID, "✅ Channel connected successfully!")
            bot.delete_message(CHANNEL_ID, test_msg.message_id)
            bot.reply_to(message, f"✅ Channel set to: {CHANNEL_ID}")
        except:
            bot.reply_to(message, f"⚠ Channel set to {CHANNEL_ID}\nBut could not send test message")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ==================== ADMIN BOT ====================
@admin_bot.message_handler(commands=['start'])
def admin_start(message):
    """Admin bot help"""
    admin_bot.reply_to(message,
        "🤖 ADMIN BOT\n\n"
        "For videos with security features:\n"
        "1. Send videos to MAIN bot directly\n"
        "2. Use /savevideo command\n\n"
        "Features enabled:\n"
        "• Auto-delete after 1 hour\n"
        "• No saving to gallery\n"
        "• No forwarding allowed\n\n"
        f"Channel: {CHANNEL_ID}"
    )

@admin_bot.message_handler(commands=['stats'])
def stats_command(message):
    """Show bot statistics"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    response = (
        f"📊 BOT STATISTICS\n\n"
        f"• Videos in database: {len(video_database)}\n"
        f"• Videos pending deletion: {len(sent_videos)}\n"
        f"• Permanent videos: {sum(1 for v in video_database.values() if v.get('permanent', False))}\n"
        f"• Channel: {CHANNEL_ID}\n\n"
        f"Security features:\n"
        f"✅ Auto-delete enabled\n"
        f"✅ Protect content enabled\n"
        f"✅ No forwarding allowed"
    )
    
    admin_bot.reply_to(message, response)

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
        "security_features": {
            "auto_delete": "1 hour",
            "protect_content": True,
            "no_saving": True,
            "no_forwarding": True
        },
        "channel": CHANNEL_ID,
        "database": f"Loaded {len(video_database)} videos"
    })

@app.route('/stats', methods=['GET'])
def web_stats():
    """Web statistics endpoint"""
    return jsonify({
        "video_count": len(video_database),
        "pending_deletions": len(sent_videos),
        "security_enabled": True,
        "auto_delete_hours": 1,
        "channel": CHANNEL_ID
    })

@app.route('/')
def home():
    return "✅ Secure Video Delivery Bot is running! Visit /setup to configure."

if __name__ == '__main__':
    logger.info(f"Secure Bot started with {len(video_database)} videos")
    logger.info(f"Channel: {CHANNEL_ID}")
    logger.info("Security features: Auto-delete 1h, Protect content enabled")
    app.run(host='0.0.0.0', port=5000)
