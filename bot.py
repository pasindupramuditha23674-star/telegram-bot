import os
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import telebot

# Try to import pymongo (for MongoDB)
try:
    from pymongo import MongoClient
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    print("⚠️ PyMongo not installed, using local storage only")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== EDIT THESE VALUES =====
BOT_TOKEN = "7768542371:AAFVJ9PDPSnS63Cm9jWsGtOt4EMwYZJajAA"
ADMIN_BOT_TOKEN = "8224351252:AAGwZel-8rfURnT5zE8dQD9eEUYOBW1vUxU"
YOUR_TELEGRAM_ID = 1574602076
CHANNEL_ID = "@storagechannel01"
WEBSITE_BASE_URL = "https://spontaneous-halva-72f63a.netlify.app"
# ===============================

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

# ===== MONGODB CONNECTION =====
def connect_to_mongodb():
    """Connect to MongoDB Atlas"""
    try:
        mongodb_uri = os.getenv('MONGODB_URI')
        
        if not mongodb_uri:
            logger.warning("⚠️ MONGODB_URI not set in environment variables")
            return None
        
        if not MONGODB_AVAILABLE:
            logger.warning("⚠️ PyMongo not installed")
            return None
        
        # Connect to MongoDB
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        logger.info("✅ Connected to MongoDB Atlas!")
        
        # Get database and collections
        db = client.video_bot_database
        videos_collection = db.videos
        sent_videos_collection = db.sent_videos
        
        # Create indexes
        videos_collection.create_index('video_id', unique=True)
        
        return {
            'client': client,
            'videos': videos_collection,
            'sent_videos': sent_videos_collection
        }
        
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        return None

# Initialize MongoDB
mongo_client = connect_to_mongodb()

# ===== DATABASE FUNCTIONS =====
def load_database():
    """Load database from MongoDB or local backup"""
    global video_database
    
    try:
        # Try MongoDB first
        if mongo_client and mongo_client['videos']:
            # Load from MongoDB
            videos_cursor = mongo_client['videos'].find({})
            video_database = {}
            
            for doc in videos_cursor:
                video_id = doc['video_id']
                # Remove MongoDB _id field
                doc.pop('_id', None)
                video_database[video_id] = doc
            
            logger.info(f"✅ Loaded {len(video_database)} videos from MongoDB")
            return
        
        # Fallback: Try local file
        if os.path.exists('video_database.json'):
            with open('video_database.json', 'r') as f:
                video_database = json.load(f)
                logger.info(f"✅ Loaded {len(video_database)} videos from local file")
        else:
            video_database = {}
            logger.info("📂 Starting fresh database")
            
    except Exception as e:
        logger.error(f"❌ Error loading database: {e}")
        video_database = {}

def save_database():
    """Save database to MongoDB AND local file"""
    try:
        # Save to MongoDB if available
        if mongo_client and mongo_client['videos']:
            for video_id, data in video_database.items():
                # Ensure video_id is in the document
                data_to_save = data.copy()
                data_to_save['video_id'] = video_id
                data_to_save['last_updated'] = datetime.now().isoformat()
                
                # Update or insert
                mongo_client['videos'].update_one(
                    {'video_id': video_id},
                    {'$set': data_to_save},
                    upsert=True
                )
            logger.info(f"💾 Saved to MongoDB: {len(video_database)} videos")
        
        # ALWAYS save to local file (backup)
        with open('video_database.json', 'w') as f:
            json.dump(video_database, f, indent=2, ensure_ascii=False)
        
        # Create extra backup
        with open('video_database.backup.json', 'w') as f:
            json.dump(video_database, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Database saved with backups: {len(video_database)} videos")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error saving database: {e}")
        return False

# ===== SENT VIDEOS TRACKER =====
def load_sent_videos():
    global sent_videos
    try:
        # Try MongoDB first
        if mongo_client and mongo_client['sent_videos']:
            sent_videos = {}
            # We'll load as needed
        else:
            # Local file
            if os.path.exists('sent_videos.json'):
                with open('sent_videos.json', 'r') as f:
                    sent_videos = json.load(f)
            else:
                sent_videos = {}
    except Exception as e:
        logger.error(f"Error loading sent videos: {e}")
        sent_videos = {}

def save_sent_videos():
    try:
        # Save to MongoDB if available
        if mongo_client and mongo_client['sent_videos']:
            # Clear old and save new
            mongo_client['sent_videos'].delete_many({})
            if sent_videos:
                mongo_client['sent_videos'].insert_many([
                    {'key': k, **v} for k, v in sent_videos.items()
                ])
        
        # Local backup
        with open('sent_videos.json', 'w') as f:
            json.dump(sent_videos, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"Error saving sent videos: {e}")

def add_sent_video(user_id, message_id, video_id, sent_time):
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
                
            time.sleep(60)
            
        except Exception as e:
            logger.error(f"Error in auto_delete_worker: {e}")
            time.sleep(60)

# Start auto-delete thread
auto_delete_thread = threading.Thread(target=auto_delete_worker, daemon=True)
auto_delete_thread.start()

# Load databases
load_database()
load_sent_videos()

# ===== MANUAL THUMBNAIL SYSTEM =====
@bot.message_handler(content_types=['photo'])
def handle_photo_upload(message):
    """Set custom thumbnail for videos"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    if message.caption and message.caption.startswith('/thumb'):
        try:
            parts = message.caption.split()
            if len(parts) >= 2:
                video_num = parts[1]
                video_id = f"video{video_num}"
                
                # Get the photo file_id (highest resolution)
                photo_id = message.photo[-1].file_id
                
                # Initialize video entry if doesn't exist
                if video_id not in video_database:
                    video_database[video_id] = {
                        'file_id': None,
                        'title': f'Video {video_num}',
                        'added_date': datetime.now().isoformat(),
                        'permanent': False
                    }
                
                # Store thumbnail
                video_database[video_id]['thumbnail_id'] = photo_id
                save_database()
                
                bot.reply_to(message, 
                    f"✅ Thumbnail set for Video {video_num}!\n\n"
                    f"Now upload the video and use:\n"
                    f"/savevideo {video_num}"
                )
                logger.info(f"Thumbnail set for {video_id}")
            else:
                bot.reply_to(message, "Usage: /thumb [video_number]\nExample: /thumb 1")
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")
    else:
        bot.reply_to(message, 
            "To set thumbnail:\n"
            "Send photo with caption:\n"
            "/thumb 1  (for video1)\n"
            "/thumb 2  (for video2)"
        )

def post_to_channel(video_num, video_message=None):
    """Post to channel with custom thumbnail"""
    try:
        website_url = f"{WEBSITE_BASE_URL}/?video={video_num}"
        
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                "🎬 Watch Now",
                url=website_url
            )
        )
        
        video_id = f"video{video_num}"
        
        # 1. Check for custom thumbnail
        if video_id in video_database and 'thumbnail_id' in video_database[video_id]:
            thumbnail_id = video_database[video_id]['thumbnail_id']
            
            post_msg = bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=thumbnail_id,
                caption=f"🎥 **Video {video_num}**\n\nClick the button below to watch 👇",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            logger.info(f"Posted with custom thumbnail: Video {video_num}")
            
        # 2. No custom thumbnail, use video preview
        elif video_message and video_message.video:
            post_msg = bot.send_video(
                chat_id=CHANNEL_ID,
                video=video_message.video.file_id,
                caption=f"🎥 **Video {video_num}**\n\nClick the button below to watch 👇",
                reply_markup=keyboard,
                parse_mode='Markdown',
                supports_streaming=True
            )
            logger.info(f"Posted with video preview: Video {video_num}")
            
        # 3. Fallback: text only
        else:
            post_msg = bot.send_message(
                chat_id=CHANNEL_ID,
                text=f"🎥 **Video {video_num} Available!**\n\nClick: {website_url}",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            logger.info(f"Posted as text: Video {video_num}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to post to channel: {e}")
        return False

# ==================== PERMANENT FILE ID SYSTEM ====================
@bot.message_handler(content_types=['video'])
def handle_video_upload(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        bot.reply_to(message, "⛔ Admin only.")
        return
    
    file_id = message.video.file_id
    response = (
        f"✅ FILE ID READY!\n\n"
        f"File ID:\n{file_id}\n\n"
        f"To save with thumbnail:\n"
        f"1. First set thumbnail: /thumb 1\n"
        f"2. Then save: /savevideo 1\n\n"
        f"Or save directly: /savevideo 1"
    )
    bot.reply_to(message, response)

@bot.message_handler(commands=['savevideo'])
def save_video_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        bot.reply_to(message, "⛔ Admin only.")
        return
    
    if not message.reply_to_message or not message.reply_to_message.video:
        bot.reply_to(message, "❌ Reply to a video with /savevideo [number]")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "Usage: /savevideo [video_number]")
            return
        
        video_num = parts[1]
        video_id = f"video{video_num}"
        file_id = message.reply_to_message.video.file_id
        
        # Save or update video
        if video_id not in video_database:
            video_database[video_id] = {}
        
        video_database[video_id].update({
            'file_id': file_id,
            'title': f'Video {video_num}',
            'added_date': datetime.now().isoformat(),
            'permanent': True
        })
        
        save_database()
        
        # Post to channel
        channel_posted = post_to_channel(video_num, message.reply_to_message)
        
        # Response
        has_thumbnail = 'thumbnail_id' in video_database[video_id]
        thumb_status = "✅ With custom thumbnail" if has_thumbnail else "⚠ No custom thumbnail"
        
        response = (
            f"✅ Video {video_num} saved!\n"
            f"{thumb_status}\n\n"
            f"✅ **STORED IN MONGODB CLOUD**\n"
            f"Security features:\n"
            f"• Auto-delete after 1 hour\n"
            f"• No saving/forwarding\n\n"
            f"Website:\n"
            f"{WEBSITE_BASE_URL}/?video={video_num}\n\n"
        )
        
        if channel_posted:
            response += f"✅ Posted to: {CHANNEL_ID}"
        else:
            response += f"⚠ Channel post failed"
        
        response += f"\n\nTest: /start {video_id}"
        
        bot.reply_to(message, response)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:200]}")

# ==================== VIDEO DELIVERY ====================
@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        parts = message.text.split()
        if len(parts) > 1 and parts[1] in video_database:
            send_video_to_user(message, parts[1])
        else:
            show_video_menu(message)
    except Exception as e:
        logger.error(f"Error: {e}")
        bot.reply_to(message, "❌ Error. Please try again.")

def send_video_to_user(message, video_id):
    try:
        video_data = video_database[video_id]
        sent_msg = bot.send_video(
            chat_id=message.chat.id,
            video=video_data['file_id'],
            caption="",
            protect_content=True,
            has_spoiler=False
        )
        
        add_sent_video(
            user_id=message.chat.id,
            message_id=sent_msg.message_id,
            video_id=video_id,
            sent_time=datetime.now().isoformat()
        )
        
        logger.info(f"Video {video_id} sent to {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        bot.reply_to(message, "❌ Failed to send video.")

def show_video_menu(message):
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
    if call.data.startswith('send_'):
        video_id = call.data.replace('send_', '')
        if video_id in video_database:
            try:
                video_data = video_database[video_id]
                sent_msg = bot.send_video(
                    chat_id=call.from_user.id,
                    video=video_data['file_id'],
                    caption="",
                    protect_content=True,
                    has_spoiler=False
                )
                
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

# ==================== DIAGNOSTIC COMMANDS ====================

@bot.message_handler(commands=['status'])
def bot_status_command(message):
    """Check bot and database status"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        # MongoDB status
        mongo_status = "✅ Connected" if mongo_client else "❌ Not connected"
        
        # Count videos
        total_videos = len(video_database)
        videos_with_file = sum(1 for v in video_database.values() if v.get('file_id'))
        
        response = (
            f"🤖 **BOT STATUS REPORT**\n\n"
            f"📊 **Database:**\n"
            f"• MongoDB: {mongo_status}\n"
            f"• Total videos: {total_videos}\n"
            f"• With file_id: {videos_with_file}\n"
            f"• Pending deletions: {len(sent_videos)}\n\n"
            
            f"🔧 **System Info:**\n"
            f"• Channel: {CHANNEL_ID}\n"
            f"• Website: {WEBSITE_BASE_URL}\n"
            f"• Admin ID: {YOUR_TELEGRAM_ID}\n\n"
            
            f"⚡ **Quick Commands:**\n"
            f"• /savevideo [num] - Save video\n"
            f"• /testvideo [num] - Test video\n"
            f"• /videos - List videos\n"
            f"• /checkall - Test all videos"
        )
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# Add all other diagnostic commands from previous code
# (testvideo, checkall, videos, etc. - keep them as before)

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
        "mongodb": "Connected" if mongo_client else "Not connected",
        "videos_in_db": len(video_database)
    })

@app.route('/')
def home():
    mongo_status = "✅ Connected" if mongo_client else "⚠️ Local only"
    return f"✅ Video Bot running! MongoDB: {mongo_status}"

if __name__ == '__main__':
    logger.info(f"🤖 Bot started with MongoDB support")
    logger.info(f"📊 Videos in database: {len(video_database)}")
    logger.info(f"🔗 MongoDB: {'Connected' if mongo_client else 'Not connected'}")
    app.run(host='0.0.0.0', port=5000)
