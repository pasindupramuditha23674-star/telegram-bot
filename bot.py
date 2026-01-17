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
CHANNEL_ID = "@RedZoneLk"
WEBSITE_BASE_URL = "https://spontaneous-halva-72f63a.netlify.app"
# ===============================

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

# Track app start time for uptime monitoring
app_start_time = time.time()

# Global database variables
video_database = {}
sent_videos = {}  # Global variable for tracking sent videos

# ===== KEEP-ALIVE HEALTH CHECK ENDPOINT =====
@app.route('/health')
@app.route('/ping')
def health_check():
    """Health check endpoint for pinging services (UptimeRobot)"""
    try:
        # Quick status check
        mongo_status = "connected" if mongo_client is not None else "disconnected"
        
        response = {
            "status": "healthy",
            "service": "telegram-video-bot",
            "timestamp": datetime.now().isoformat(),
            "videos": len(video_database),
            "mongodb": mongo_status,
            "uptime_seconds": int(time.time() - app_start_time),
            "endpoints": {
                "health": "/health",
                "ping": "/ping",
                "home": "/",
                "setup": "/setup"
            }
        }
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({"status": "error", "message": str(e)[:100]}), 500

# ===== SELF-PING BACKUP SYSTEM =====
def self_ping_worker():
    """Self-ping to keep Render awake (backup system)"""
    # Lazy import to avoid dependency if not needed
    try:
        import requests
    except ImportError:
        logger.warning("⚠️ requests module not installed, self-ping disabled")
        return
    
    ping_count = 0
    while True:
        try:
            # Ping our own health endpoint
            response = requests.get('https://telegram-bot-7-dqqa.onrender.com/health', timeout=10)
            ping_count += 1
            
            # Log every 10th ping to avoid spam
            if ping_count % 10 == 0:
                logger.info(f"✅ Self-ping #{ping_count}: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            # Don't log normal timeouts/errors to avoid spam
            if ping_count % 20 == 0:
                logger.warning(f"Self-ping failed (attempt #{ping_count}): {e}")
        except Exception as e:
            if ping_count % 20 == 0:
                logger.error(f"Self-ping error: {e}")
        
        # Sleep for 8 minutes (Render needs <15 minute intervals)
        # This is a BACKUP in case UptimeRobot fails
        time.sleep(480)  # 8 minutes

# ===== MONGODB CONNECTION WITH SSL FIX =====
def connect_to_mongodb():
    """Connect to MongoDB Atlas with SSL fix"""
    try:
        mongodb_uri = os.getenv('MONGODB_URI')
        
        if not mongodb_uri:
            logger.warning("⚠️ MONGODB_URI not set in environment variables")
            return None
        
        if not MONGODB_AVAILABLE:
            logger.warning("⚠️ PyMongo not installed")
            return None
        
        logger.info(f"🔄 Attempting MongoDB connection...")
        
        # FIX: Added SSL/TLS parameters to fix connection issues
        client = MongoClient(
            mongodb_uri,
            serverSelectionTimeoutMS=15000,  # Increased timeout
            connectTimeoutMS=15000,
            socketTimeoutMS=15000,
            tls=True,                      # Enable TLS/SSL
            tlsAllowInvalidCertificates=True,  # Allow self-signed certs
            appname="video-bot"
        )
        
        # Test connection
        logger.info("🔄 Testing MongoDB connection...")
        client.admin.command('ping')
        
        # Get database and collections
        db = client.video_bot_database
        videos_collection = db.videos
        sent_videos_collection = db.sent_videos
        
        # Create indexes
        videos_collection.create_index('video_id', unique=True)
        sent_videos_collection.create_index('key', unique=True)
        
        logger.info("✅ Connected to MongoDB Atlas!")
        logger.info(f"📊 Database: {db.name}")
        logger.info(f"📁 Collections: videos, sent_videos")
        
        return {
            'client': client,
            'videos': videos_collection,
            'sent_videos': sent_videos_collection
        }
        
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {str(e)[:200]}")
        
        # Try alternative connection method if SRV fails
        if mongodb_uri and "mongodb+srv://" in mongodb_uri:
            try:
                logger.info("🔄 Trying alternative connection without SRV...")
                # Replace SRV with standard connection
                alt_uri = mongodb_uri.replace("mongodb+srv://", "mongodb://")
                alt_client = MongoClient(
                    alt_uri,
                    serverSelectionTimeoutMS=10000,
                    tlsAllowInvalidCertificates=True
                )
                alt_client.admin.command('ping')
                logger.info("✅ Alternative connection successful!")
                
                db = alt_client.video_bot_database
                return {
                    'client': alt_client,
                    'videos': db.videos,
                    'sent_videos': db.sent_videos
                }
            except Exception as alt_e:
                logger.error(f"❌ Alternative also failed: {str(alt_e)[:200]}")
        
        return None

# Initialize MongoDB
mongo_client = connect_to_mongodb()

# ===== DATABASE FUNCTIONS =====
def load_database():
    """Load database from MongoDB or local backup"""
    global video_database
    
    try:
        # Try MongoDB first - FIX: Check if mongo_client exists and has 'videos' key
        if mongo_client is not None and 'videos' in mongo_client:
            try:
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
            except Exception as mongo_error:
                logger.error(f"❌ MongoDB load failed, falling back to local: {mongo_error}")
                # Fall through to local backup
        
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
        # Save to MongoDB if available - FIX: Check mongo_client is not None
        mongo_success = False
        if mongo_client is not None and 'videos' in mongo_client:
            try:
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
                mongo_success = True
                logger.info(f"💾 Saved to MongoDB: {len(video_database)} videos")
            except Exception as mongo_error:
                logger.error(f"⚠️ MongoDB save failed (using local): {mongo_error}")
                mongo_success = False
        
        # ALWAYS save to local file (backup) - THIS IS CRITICAL
        with open('video_database.json', 'w') as f:
            json.dump(video_database, f, indent=2, ensure_ascii=False)
        
        # Create extra backup
        with open('video_database.backup.json', 'w') as f:
            json.dump(video_database, f, indent=2, ensure_ascii=False)
        
        status = f"✅ Database saved: {len(video_database)} videos"
        if mongo_client is not None:
            status += f" (MongoDB: {'✅' if mongo_success else '❌'})"
        
        logger.info(status)
        return True
        
    except Exception as e:
        logger.error(f"❌ Error saving database: {e}")
        return False

# ===== SENT VIDEOS TRACKER =====
def load_sent_videos():
    global sent_videos
    try:
        # Try MongoDB first - FIX: Check mongo_client, not collection object
        if mongo_client is not None and 'sent_videos' in mongo_client:
            try:
                # Load from MongoDB
                cursor = mongo_client['sent_videos'].find({})
                sent_videos = {}
                for doc in cursor:
                    key = doc.get('key')
                    if key:
                        doc.pop('_id', None)
                        doc.pop('key', None)
                        sent_videos[key] = doc
                logger.info(f"✅ Loaded {len(sent_videos)} sent videos from MongoDB")
                return
            except Exception as mongo_error:
                logger.error(f"MongoDB sent_videos load failed: {mongo_error}")
                # Fall through to local file
        
        # Local file
        if os.path.exists('sent_videos.json'):
            with open('sent_videos.json', 'r') as f:
                sent_videos = json.load(f)
                logger.info(f"✅ Loaded {len(sent_videos)} sent videos from local file")
        else:
            sent_videos = {}
            logger.info("📂 Starting fresh sent videos tracker")
    except Exception as e:
        logger.error(f"Error loading sent videos: {e}")
        sent_videos = {}

def save_sent_videos():
    global sent_videos
    try:
        # Save to MongoDB if available - FIX: Check mongo_client
        if mongo_client is not None and 'sent_videos' in mongo_client:
            try:
                # Clear old and save new
                mongo_client['sent_videos'].delete_many({})
                if sent_videos:
                    documents = []
                    for key, data in sent_videos.items():
                        doc = data.copy()
                        doc['key'] = key
                        documents.append(doc)
                    mongo_client['sent_videos'].insert_many(documents)
            except Exception as mongo_error:
                logger.error(f"MongoDB sent_videos save failed: {mongo_error}")
        
        # ALWAYS save local backup
        with open('sent_videos.json', 'w') as f:
            json.dump(sent_videos, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"Error saving sent videos: {e}")

def add_sent_video(user_id, message_id, video_id, sent_time):
    global sent_videos
    key = f"{user_id}_{message_id}"
    sent_videos[key] = {
        'user_id': user_id,
        'message_id': message_id,
        'video_id': video_id,
        'sent_time': sent_time,
        'delete_at': (datetime.now() + timedelta(hours=1)).isoformat()
    }
    save_sent_videos()
    logger.info(f"✅ Added sent video: {video_id} for user {user_id}")

# ===== AUTO DELETE THREAD =====
def auto_delete_worker():
    global sent_videos
    
    while True:
        try:
            current_time = datetime.now()
            to_delete = []
            
            # Check if sent_videos exists
            if sent_videos is None:
                logger.warning("sent_videos is None, initializing empty dict")
                sent_videos = {}
                time.sleep(60)
                continue
            
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

# ===== BOT WARMUP FUNCTION =====
def warmup_bot():
    """Pre-load everything to reduce cold start time"""
    logger.info("🔥 Warming up bot for faster response...")
    
    # Pre-load database if empty
    if len(video_database) == 0:
        load_database()
    
    # Pre-connect to MongoDB if not connected
    if mongo_client is None:
        connect_to_mongodb()
    
    # Test Telegram API connection
    try:
        bot.get_me()
        logger.info("✅ Bot warmed up successfully")
    except Exception as e:
        logger.warning(f"Bot warmup warning: {e}")
    
    return True

# Warm up the bot on startup
warmup_bot()

# ===== DIAGNOSTIC COMMANDS =====
@bot.message_handler(commands=['mongotest'])
def test_mongodb(message):
    """Test MongoDB connection"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        # Get connection string (hide password)
        mongodb_uri = os.getenv('MONGODB_URI', 'Not set')
        if mongodb_uri and '@' in mongodb_uri:
            # Hide password
            parts = mongodb_uri.split('@')
            user_pass = parts[0]
            if ':' in user_pass:
                user = user_pass.split(':')[0]
                mongodb_uri_display = f"{user}:***@{parts[1].split('/')[0]}"
            else:
                mongodb_uri_display = "***@***"
        else:
            mongodb_uri_display = mongodb_uri
        
        # Test connection
        test_status = "Not tested"
        if mongodb_uri and mongodb_uri != 'Not set':
            try:
                test_client = MongoClient(
                    mongodb_uri,
                    serverSelectionTimeoutMS=5000,
                    tlsAllowInvalidCertificates=True
                )
                test_client.admin.command('ping')
                test_status = "✅ CONNECTED"
                test_client.close()
            except Exception as e:
                test_status = f"❌ FAILED: {str(e)[:150]}"
        else:
            test_status = "❌ URI NOT SET"
        
        response = (
            f"🔧 MongoDB Diagnostic Test:\n\n"
            f"URI: {mongodb_uri_display}\n"
            f"Status: {test_status}\n"
            f"Current client: {'✅ Ready' if mongo_client is not None else '❌ Not ready'}\n"
            f"MongoDB collections: {'✅ Loaded' if mongo_client and 'videos' in mongo_client else '❌ Not loaded'}\n"
            f"Local videos: {len(video_database)}\n\n"
        )
        
        # Add MongoDB document count if connected
        if mongo_client is not None and 'videos' in mongo_client:
            try:
                mongo_count = mongo_client['videos'].count_documents({})
                response += f"MongoDB documents: {mongo_count}\n"
                response += f"Sync status: {'✅' if len(video_database) == mongo_count else '⚠️ Not synced'}"
            except:
                response += "⚠️ Could not count MongoDB documents"
        
        bot.reply_to(message, response)
        
    except Exception as e:
        bot.reply_to(message, f"Test error: {str(e)[:100]}")

@bot.message_handler(commands=['synctomongo'])
def sync_to_mongo(message):
    """Sync local videos to MongoDB"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        if mongo_client is None:
            bot.reply_to(message, "❌ MongoDB not connected. Fix connection first.")
            return
        
        count = len(video_database)
        if count == 0:
            bot.reply_to(message, "❌ No videos in local database")
            return
        
        # Save to MongoDB (this will sync)
        success = save_database()
        
        if success:
            # Verify sync
            mongo_count = mongo_client['videos'].count_documents({})
            
            response = (
                f"✅ Sync Complete!\n\n"
                f"Local videos: {count}\n"
                f"MongoDB videos: {mongo_count}\n\n"
                f"Status: {'✅ Synced' if count == mongo_count else '⚠️ Count mismatch'}\n"
                f"Now MongoDB will auto-backup new videos."
            )
        else:
            response = "❌ Sync failed. Check logs."
        
        bot.reply_to(message, response)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Sync error: {str(e)[:200]}")

@bot.message_handler(commands=['mongoinfo'])
def mongo_info(message):
    """Detailed MongoDB information"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        if mongo_client is None:
            bot.reply_to(message, "❌ MongoDB client is None")
            return
        
        info = "📊 MongoDB Status:\n\n"
        info += f"Client type: {type(mongo_client)}\n"
        
        if isinstance(mongo_client, dict):
            info += f"Keys in mongo_client: {list(mongo_client.keys())}\n"
            
            if 'videos' in mongo_client:
                try:
                    count = mongo_client['videos'].count_documents({})
                    info += f"Videos collection: {count} documents\n"
                except:
                    info += "Videos collection: Error counting\n"
            
            if 'sent_videos' in mongo_client:
                try:
                    count = mongo_client['sent_videos'].count_documents({})
                    info += f"Sent videos: {count} documents\n"
                except:
                    info += "Sent videos: Error counting\n"
        else:
            info += "⚠️ mongo_client is not a dictionary\n"
        
        bot.reply_to(message, info)
        
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)[:200]}")

@bot.message_handler(commands=['simple'])
def simple_status(message):
    """Simple status check that always works"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        # Basic counts
        total = len(video_database)
        with_files = sum(1 for v in video_database.values() if v.get('file_id'))
        pending = len(sent_videos)
        
        response = (
            f"📊 Simple Status:\n"
            f"Videos: {total}\n"
            f"Ready: {with_files}\n"
            f"Auto-delete queue: {pending}\n"
            f"Bot: ✅ Working\n"
            f"MongoDB: {'✅' if mongo_client is not None else '❌'}\n"
            f"Uptime: {int(time.time() - app_start_time)}s"
        )
        
        bot.reply_to(message, response)
        
    except Exception as e:
        bot.reply_to(message, f"✅ Bot is running (status error: {str(e)[:50]})")

@bot.message_handler(commands=['status'])
def bot_status_command(message):
    """Check bot and database status"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        # MongoDB status
        mongo_status = "✅ Connected" if mongo_client is not None else "❌ Not connected (using local files)"
        
        # Count videos
        total_videos = len(video_database)
        videos_with_file = sum(1 for v in video_database.values() if v.get('file_id'))
        
        # Uptime calculation
        uptime_seconds = int(time.time() - app_start_time)
        uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m"
        
        response = (
            f"🤖 BOT STATUS REPORT\n\n"
            f"📊 Database Status:\n"
            f"• MongoDB: {mongo_status}\n"
            f"• Total videos: {total_videos}\n"
            f"• Videos with file_id: {videos_with_file}\n"
            f"• Pending deletions: {len(sent_videos)}\n"
            f"• Uptime: {uptime_str}\n\n"
            
            f"🔧 System Info:\n"
            f"• Channel: {CHANNEL_ID}\n"
            f"• Website: {WEBSITE_BASE_URL}\n"
            f"• Admin ID: {YOUR_TELEGRAM_ID}\n"
            f"• Health check: /health\n\n"
            
            f"✅ Bot is working normally!\n"
            f"Test MongoDB: /mongotest\n"
            f"Sync to MongoDB: /synctomongo"
        )
        
        bot.reply_to(message, response)
        
    except Exception as e:
        bot.reply_to(message, f"✅ Bot is running (status details unavailable)")

@bot.message_handler(commands=['keepalive'])
def keepalive_status(message):
    """Check keep-alive system status"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        # Test health endpoint
        import requests
        health_url = "https://telegram-bot-7-dqqa.onrender.com/health"
        
        try:
            response = requests.get(health_url, timeout=10)
            health_status = f"✅ Responding ({response.status_code})"
            health_data = response.json()
        except Exception as e:
            health_status = f"❌ Error: {str(e)[:100]}"
            health_data = {}
        
        response = (
            f"🔧 KEEP-ALIVE SYSTEM STATUS\n\n"
            f"Health endpoint: {health_status}\n"
            f"URL: {health_url}\n"
            f"Self-ping: {'✅ Active' if 'self_ping_thread' in globals() else '❌ Inactive'}\n"
            f"Bot uptime: {int(time.time() - app_start_time)} seconds\n\n"
            f"📝 Setup UptimeRobot:\n"
            f"1. Go to UptimeRobot.com\n"
            f"2. Add monitor: {health_url}\n"
            f"3. Set interval: 5 minutes\n"
            f"4. Bot stays awake 24/7\n\n"
            f"Current status: {health_data.get('status', 'Unknown')}"
        )
        
        bot.reply_to(message, response)
        
    except ImportError:
        bot.reply_to(message, "❌ requests module not installed for health check")
    except Exception as e:
        bot.reply_to(message, f"Keep-alive check error: {str(e)[:100]}")

@bot.message_handler(commands=['emergencybackup'])
def emergency_backup(message):
    """Create emergency backup you can download"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        # Save to multiple locations
        locations = [
            'video_database_emergency.json',
            '/tmp/video_backup.json',  # Render /tmp might survive longer
            'backup_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.json'
        ]
        
        success_count = 0
        for loc in locations:
            try:
                with open(loc, 'w') as f:
                    json.dump(video_database, f, indent=2)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to save to {loc}: {e}")
        
        count = len(video_database)
        bot.reply_to(message, f"✅ Emergency backup created!\n\nSaved {count} videos to {success_count} locations")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Backup failed: {str(e)[:200]}")

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
            f"✅ **SAVED WITH BACKUPS**\n"
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
        "mongodb": "Connected" if mongo_client is not None else "Not connected",
        "videos_in_db": len(video_database)
    })

@app.route('/')
def home():
    mongo_status = "✅ Connected" if mongo_client is not None else "⚠️ Local only"
    uptime = int(time.time() - app_start_time)
    uptime_str = f"{uptime // 3600}h {(uptime % 3600) // 60}m"
    return f"✅ Video Bot running! MongoDB: {mongo_status} | Uptime: {uptime_str} | Health: /health"

# ===== START SELF-PING THREAD (BACKUP) =====
try:
    self_ping_thread = threading.Thread(target=self_ping_worker, daemon=True)
    self_ping_thread.start()
    logger.info("✅ Self-ping backup thread started")
except Exception as e:
    logger.warning(f"⚠️ Could not start self-ping thread: {e}")

if __name__ == '__main__':
    logger.info(f"🤖 Bot started with MongoDB support")
    logger.info(f"📊 Videos in database: {len(video_database)}")
    logger.info(f"🔗 MongoDB: {'Connected' if mongo_client is not None else 'Not connected'}")
    logger.info(f"📢 Channel: {CHANNEL_ID}")
    logger.info(f"🏥 Health endpoint: /health")
    logger.info(f"⏱️ Bot will stay awake with UptimeRobot pings")
    app.run(host='0.0.0.0', port=5000)
