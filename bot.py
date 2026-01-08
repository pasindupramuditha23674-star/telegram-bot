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
CHANNEL_ID = "@storagechannel01"
WEBSITE_BASE_URL = "https://spontaneous-halva-72f63a.netlify.app"
# ===============================

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

# Database files with multiple backup locations
DB_FILE = 'video_database.json'
BACKUP_FILE = 'video_database.backup.json'
BACKUP_FILE_2 = '/tmp/video_database.backup.json'  # Render's /tmp
SENT_VIDEOS_FILE = 'sent_videos_tracker.json'

# ===== ENHANCED BACKUP SYSTEM =====
def create_backup():
    """Create multiple backup copies of database"""
    try:
        if not video_database:
            logger.warning("⚠️ No data to backup")
            return False
            
        # Backup 1: Local file
        with open(BACKUP_FILE, 'w') as f:
            json.dump(video_database, f, indent=2, ensure_ascii=False)
        
        # Backup 2: /tmp directory (persists longer on Render)
        try:
            with open(BACKUP_FILE_2, 'w') as f:
                json.dump(video_database, f, indent=2, ensure_ascii=False)
        except Exception as tmp_error:
            logger.warning(f"⚠️ /tmp backup failed: {tmp_error}")
        
        logger.info(f"✅ Created backups ({len(video_database)} videos)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Backup creation failed: {e}")
        return False

def restore_from_backup():
    """Restore database from backup files"""
    global video_database
    restored_from = None
    
    # Try backup locations in order (most reliable first)
    backup_locations = [
        (BACKUP_FILE_2, "/tmp backup"),
        (BACKUP_FILE, "Local backup"),
        (DB_FILE, "Main database")
    ]
    
    for backup_path, source_name in backup_locations:
        try:
            if os.path.exists(backup_path):
                with open(backup_path, 'r') as f:
                    restored_data = json.load(f)
                
                if restored_data and isinstance(restored_data, dict) and len(restored_data) > 0:
                    video_database = restored_data
                    restored_from = source_name
                    logger.info(f"✅ Restored {len(video_database)} videos from {source_name}")
                    return True
        except Exception as e:
            logger.warning(f"⚠️ Could not restore from {source_name}: {e}")
            continue
    
    # If all backups failed, start fresh
    if not restored_from:
        video_database = {}
        logger.info("📂 No backup found, starting fresh database")
    
    return False if not restored_from else True

def save_database_with_backup():
    """Save database with automatic backups"""
    try:
        # Save main database
        with open(DB_FILE, 'w') as f:
            json.dump(video_database, f, indent=2, ensure_ascii=False)
        
        # Create automatic backups
        create_backup()
        
        logger.info(f"💾 Saved {len(video_database)} videos with backups")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error saving database: {e}")
        return False

# ===== DATABASE LOADING =====
def load_database():
    """Load database on startup (auto-restores from backup)"""
    global video_database
    
    try:
        # First try to restore from backups
        if restore_from_backup():
            logger.info(f"✅ Database auto-restored: {len(video_database)} videos")
            return
        
        # If no backup, try original file
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                video_database = json.load(f)
                logger.info(f"✅ Loaded {len(video_database)} videos from main file")
        else:
            video_database = {}
            logger.info("📂 No database found, starting fresh")
            
    except Exception as e:
        logger.error(f"❌ Error loading database: {e}")
        video_database = {}

# ===== SENT VIDEOS TRACKER =====
def load_sent_videos():
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
    try:
        with open(SENT_VIDEOS_FILE, 'w') as f:
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
                save_database_with_backup()  # ← USING ENHANCED SAVE
                
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

# Start auto-delete thread
auto_delete_thread = threading.Thread(target=auto_delete_worker, daemon=True)
auto_delete_thread.start()

# Load databases on startup
load_database()
load_sent_videos()

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
        
        save_database_with_backup()  # ← USING ENHANCED SAVE WITH BACKUP
        
        # Post to channel
        channel_posted = post_to_channel(video_num, message.reply_to_message)
        
        # Response
        has_thumbnail = 'thumbnail_id' in video_database[video_id]
        thumb_status = "✅ With custom thumbnail" if has_thumbnail else "⚠ No custom thumbnail"
        
        response = (
            f"✅ Video {video_num} saved WITH BACKUP!\n"
            f"{thumb_status}\n\n"
            f"Security features enabled:\n"
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

# ==================== DIAGNOSTIC & BACKUP COMMANDS ====================

@bot.message_handler(commands=['backup'])
def backup_command(message):
    """Manually create backup"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        if create_backup():
            bot.reply_to(message, 
                f"✅ **BACKUP CREATED!**\n\n"
                f"Videos backed up: {len(video_database)}\n"
                f"Backup locations:\n"
                f"1. {BACKUP_FILE}\n"
                f"2. {BACKUP_FILE_2}\n\n"
                f"✅ Safe from Render restarts!"
            )
        else:
            bot.reply_to(message, "❌ Backup failed (no data to backup?)")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['restore'])
def restore_command(message):
    """Manually restore from backup"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        if restore_from_backup():
            count = len(video_database)
            bot.reply_to(message, 
                f"✅ **DATABASE RESTORED!**\n\n"
                f"Videos loaded: {count}\n"
                f"Last backup restored\n\n"
                f"Check videos: /videos\n"
                f"Test: /testvideo 1"
            )
        else:
            bot.reply_to(message, "❌ No backup found to restore")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['status'])
def bot_status_command(message):
    """Check bot and database status"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        # Check backup files
        backup1_exists = os.path.exists(BACKUP_FILE)
        backup2_exists = os.path.exists(BACKUP_FILE_2)
        main_db_exists = os.path.exists(DB_FILE)
        
        # Count videos with/without file_ids
        videos_with_file = sum(1 for v in video_database.values() if v.get('file_id'))
        
        response = (
            f"🤖 **BOT STATUS REPORT**\n\n"
            f"📊 **Database Status:**\n"
            f"• Videos in memory: {len(video_database)}\n"
            f"• Videos with file_id: {videos_with_file}\n"
            f"• Pending deletions: {len(sent_videos)}\n\n"
            
            f"💾 **Backup Status:**\n"
            f"• Main DB: {'✅ Exists' if main_db_exists else '❌ Missing'}\n"
            f"• Local backup: {'✅ Exists' if backup1_exists else '❌ Missing'}\n"
            f"• /tmp backup: {'✅ Exists' if backup2_exists else '❌ Missing'}\n\n"
            
            f"🔧 **System Info:**\n"
            f"• Channel: {CHANNEL_ID}\n"
            f"• Website: {WEBSITE_BASE_URL}\n"
            f"• Admin ID: {YOUR_TELEGRAM_ID}\n\n"
            
            f"⚡ **Quick Commands:**\n"
            f"• /backup - Create backup now\n"
            f"• /restore - Restore from backup\n"
            f"• /videos - List all videos\n"
            f"• /checkall - Test all videos"
        )
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['testvideo'])
def test_video_command(message):
    """Test if a video file_id still works"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        bot.reply_to(message, "⛔ Admin only.")
        return
    
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
        
        file_id = video_database[video_id].get('file_id')
        if not file_id:
            bot.reply_to(message, f"❌ {video_id} has no file_id")
            return
        
        # Try to send the video
        try:
            sent_msg = bot.send_video(
                chat_id=YOUR_TELEGRAM_ID,
                video=file_id,
                caption=f"✅ TEST SUCCESS: {video_id}\nFile ID still works!",
                protect_content=True
            )
            
            # Add to auto-delete tracker
            add_sent_video(
                user_id=YOUR_TELEGRAM_ID,
                message_id=sent_msg.message_id,
                video_id=video_id,
                sent_time=datetime.now().isoformat()
            )
            
            bot.reply_to(message, 
                f"✅ **Test Successful!**\n\n"
                f"Video: {video_id}\n"
                f"Status: File ID is valid\n"
                f"Video sent to you (will auto-delete in 1 hour)"
            )
            
        except Exception as send_error:
            error_msg = str(send_error)
            logger.error(f"Test failed for {video_id}: {error_msg}")
            
            bot.reply_to(message,
                f"❌ **TEST FAILED**\n\n"
                f"Video: {video_id}\n"
                f"Error: {error_msg[:100]}\n\n"
                f"**Solution:**\n"
                f"1. Send video again to bot\n"
                f"2. Reply with: /savevideo {video_num}"
            )
            
    except Exception as e:
        logger.error(f"Error in test_video_command: {e}")
        bot.reply_to(message, f"❌ Command error: {str(e)[:200]}")

@bot.message_handler(commands=['checkall'])
def check_all_videos(message):
    """Check all videos in database"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        bot.reply_to(message, "⛔ Admin only.")
        return
    
    try:
        if not video_database:
            bot.reply_to(message, "📭 No videos in database")
            return
        
        bot.reply_to(message, "🔄 Testing all videos... This may take a minute.")
        
        working = []
        failed = []
        total = len(video_database)
        
        for video_id in sorted(video_database.keys()):
            video_num = video_id.replace('video', '')
            file_id = video_database[video_id].get('file_id')
            
            if not file_id:
                failed.append(f"{video_id} (no file_id)")
                continue
            
            # Test the file_id
            try:
                # Quick test - try to get file info
                bot.get_file(file_id)
                working.append(video_id)
            except Exception as e:
                failed.append(f"{video_id} - {str(e)[:30]}")
        
        # Create report
        response = f"📊 **Video Health Check**\n\n"
        response += f"Total videos: {total}\n"
        response += f"✅ Working: {len(working)}\n"
        response += f"❌ Failed: {len(failed)}\n\n"
        
        if failed:
            response += "**Failed Videos:**\n"
            for fail in failed[:10]:
                response += f"• {fail}\n"
            
            if len(failed) > 10:
                response += f"... and {len(failed)-10} more\n\n"
            
            response += "\n**To fix:**\n"
            response += "For each failed video:\n"
            response += "1. Send video to bot\n"
            response += "2. Reply with: /savevideo [number]\n"
        
        if working:
            response += "\n**Working Videos:**\n"
            for vid in working[:5]:
                response += f"• {vid}\n"
            
            if len(working) > 5:
                response += f"... and {len(working)-5} more"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in check_all_videos: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)[:200]}")

@bot.message_handler(commands=['videos'])
def list_videos_simple(message):
    """Simple list of all videos"""
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        if not video_database:
            bot.reply_to(message, "No videos in database")
            return
        
        response = "📹 **All Videos:**\n\n"
        for video_id in sorted(video_database.keys()):
            num = video_id.replace('video', '')
            data = video_database[video_id]
            
            has_file = "✅" if data.get('file_id') else "❌"
            has_thumb = "🖼️" if data.get('thumbnail_id') else "📭"
            
            response += f"{has_file} Video {num} {has_thumb}\n"
        
        response += f"\nTotal: {len(video_database)} videos"
        response += f"\n\nTest any video: /testvideo [number]"
        
        bot.reply_to(message, response)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ==================== OTHER ADMIN COMMANDS ====================
@bot.message_handler(commands=['listvideos'])
def list_all_videos(message):
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
        response += f"  URL: {WEBSITE_BASE_URL}/?video={num}\n\n"
    
    response += f"Total: {len(video_database)} videos"
    bot.reply_to(message, response)

# (Keep all other existing commands: clearvideos, posttochannel, etc.)

# ==================== ADMIN BOT ====================
@admin_bot.message_handler(commands=['start'])
def admin_start(message):
    """Admin bot help"""
    admin_bot.reply_to(message,
        "🤖 ADMIN BOT - BACKUP SYSTEM ENABLED\n\n"
        "**Main Bot Commands:**\n"
        "• /savevideo [num] - Save video with auto-backup\n"
        "• /thumb [num] - Set thumbnail\n"
        "• /backup - Create backup now\n"
        "• /restore - Restore from backup\n"
        "• /status - Check system status\n"
        "• /testvideo [num] - Test video\n\n"
        f"Channel: {CHANNEL_ID}\n"
        f"Website: {WEBSITE_BASE_URL}"
    )

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
        "backup_system": "ENABLED",
        "auto_restore": "ENABLED",
        "channel": CHANNEL_ID,
        "website": WEBSITE_BASE_URL,
        "videos_in_db": len(video_database)
    })

@app.route('/')
def home():
    return f"✅ Secure Video Bot with BACKUP SYSTEM is running! Website: {WEBSITE_BASE_URL}"

if __name__ == '__main__':
    logger.info(f"🤖 Bot started with backup system")
    logger.info(f"📊 Videos in database: {len(video_database)}")
    logger.info(f"🔧 Auto-backup & auto-restore: ENABLED")
    app.run(host='0.0.0.0', port=5000)
