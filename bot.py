import os
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import telebot

try:
    from pymongo import MongoClient
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "7768542371:AAFVJ9PDPSnS63Cm9jWsGtOt4EMwYZJajAA"
ADMIN_BOT_TOKEN = "8224351252:AAGwZel-8rfURnT5zE8dQD9eEUYOBW1vUxU"
YOUR_TELEGRAM_ID = 1574602076

# ===== UPDATED CHANNEL INFORMATION =====
CHANNEL_INVITE_LINK = "https://t.me/+NEW_LINK_HERE"  # Replace with your new private channel link

# ===== YOUR NEW CHANNEL ID =====
# Your channel ID: 1003030466566
# Add -100 prefix to make it: -1003030466566
CHANNEL_ID = -1003030466566  # Correct format for private channels

WEBSITE_BASE_URL = "https://spontaneous-halva-72f63a.netlify.app"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

app_start_time = time.time()
video_database = {}
sent_videos = {}
detected_channel_id = CHANNEL_ID  # Start with your known channel ID

def detect_channel_id():
    global detected_channel_id
    try:
        logger.info("🔄 Detecting channel ID...")
        
        # First try the manually set channel ID
        if CHANNEL_ID:
            try:
                chat = bot.get_chat(CHANNEL_ID)
                detected_channel_id = chat.id
                logger.info(f"✅ Using manually set channel ID: {detected_channel_id}")
                logger.info(f"✅ Channel title: {chat.title}")
                return detected_channel_id
            except Exception as e:
                logger.warning(f"❌ Manual channel ID failed: {e}")
        
        # Try alternative methods if manual ID fails
        try:
            # Try getting the channel by invite link
            if CHANNEL_INVITE_LINK:
                chat = bot.get_chat(CHANNEL_INVITE_LINK)
                detected_channel_id = chat.id
                logger.info(f"✅ Detected channel ID via invite link: {detected_channel_id}")
                logger.info(f"✅ Channel title: {chat.title}")
                return detected_channel_id
        except:
            pass
        
        logger.error("❌ Could not detect channel ID. Bot needs to be added to channel first.")
        return None
        
    except Exception as e:
        logger.error(f"❌ Channel detection error: {e}")
        return None

def get_channel_info():
    global detected_channel_id
    try:
        if not detected_channel_id:
            detected_channel_id = detect_channel_id()
            if not detected_channel_id:
                return {'success': False, 'error': 'Channel not detected'}
        
        chat = bot.get_chat(detected_channel_id)
        return {
            'success': True,
            'title': chat.title,
            'type': chat.type,
            'id': chat.id,
            'username': getattr(chat, 'username', 'N/A'),
            'invite_link': CHANNEL_INVITE_LINK
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.route('/health')
@app.route('/ping')
def health_check():
    try:
        mongo_status = "connected" if mongo_client is not None else "disconnected"
        channel_info = get_channel_info()
        
        response = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "videos": len(video_database),
            "channel_detected": bool(detected_channel_id),
            "channel_info": channel_info if channel_info['success'] else None,
            "channel_error": channel_info.get('error') if not channel_info['success'] else None,
            "uptime_seconds": int(time.time() - app_start_time)
        }
        return jsonify(response), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)[:100]}), 500

def connect_to_mongodb():
    try:
        mongodb_uri = os.getenv('MONGODB_URI')
        if not mongodb_uri or not MONGODB_AVAILABLE:
            return None
        
        client = MongoClient(
            mongodb_uri,
            serverSelectionTimeoutMS=15000,
            connectTimeoutMS=15000,
            socketTimeoutMS=15000,
            tls=True,
            tlsAllowInvalidCertificates=True
        )
        
        client.admin.command('ping')
        db = client.video_bot_database
        videos_collection = db.videos
        sent_videos_collection = db.sent_videos
        
        videos_collection.create_index('video_id', unique=True)
        sent_videos_collection.create_index('key', unique=True)
        
        return {
            'client': client,
            'videos': videos_collection,
            'sent_videos': sent_videos_collection
        }
    except Exception as e:
        return None

mongo_client = connect_to_mongodb()

def load_database():
    global video_database
    try:
        if mongo_client is not None and 'videos' in mongo_client:
            try:
                videos_cursor = mongo_client['videos'].find({})
                video_database = {}
                for doc in videos_cursor:
                    video_id = doc['video_id']
                    doc.pop('_id', None)
                    video_database[video_id] = doc
                return
            except Exception:
                pass
        
        if os.path.exists('video_database.json'):
            with open('video_database.json', 'r') as f:
                video_database = json.load(f)
        else:
            video_database = {}
    except Exception as e:
        video_database = {}

def save_database():
    try:
        mongo_success = False
        if mongo_client is not None and 'videos' in mongo_client:
            try:
                for video_id, data in video_database.items():
                    data_to_save = data.copy()
                    data_to_save['video_id'] = video_id
                    data_to_save['last_updated'] = datetime.now().isoformat()
                    mongo_client['videos'].update_one(
                        {'video_id': video_id},
                        {'$set': data_to_save},
                        upsert=True
                    )
                mongo_success = True
            except Exception:
                pass
        
        with open('video_database.json', 'w') as f:
            json.dump(video_database, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        return False

def load_sent_videos():
    global sent_videos
    try:
        if mongo_client is not None and 'sent_videos' in mongo_client:
            try:
                cursor = mongo_client['sent_videos'].find({})
                sent_videos = {}
                for doc in cursor:
                    key = doc.get('key')
                    if key:
                        doc.pop('_id', None)
                        doc.pop('key', None)
                        sent_videos[key] = doc
                return
            except Exception:
                pass
        
        if os.path.exists('sent_videos.json'):
            with open('sent_videos.json', 'r') as f:
                sent_videos = json.load(f)
        else:
            sent_videos = {}
    except Exception as e:
        sent_videos = {}

def save_sent_videos():
    global sent_videos
    try:
        if mongo_client is not None and 'sent_videos' in mongo_client:
            try:
                mongo_client['sent_videos'].delete_many({})
                if sent_videos:
                    documents = []
                    for key, data in sent_videos.items():
                        doc = data.copy()
                        doc['key'] = key
                        documents.append(doc)
                    mongo_client['sent_videos'].insert_many(documents)
            except Exception:
                pass
        
        with open('sent_videos.json', 'w') as f:
            json.dump(sent_videos, f, indent=2, ensure_ascii=False)
    except Exception as e:
        pass

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

def auto_delete_worker():
    global sent_videos
    while True:
        try:
            current_time = datetime.now()
            to_delete = []
            
            if sent_videos is None:
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
                except Exception:
                    pass
                del sent_videos[key]
            
            if to_delete:
                save_sent_videos()
            time.sleep(60)
        except Exception as e:
            time.sleep(60)

auto_delete_thread = threading.Thread(target=auto_delete_worker, daemon=True)
auto_delete_thread.start()

load_database()
load_sent_videos()

@bot.message_handler(commands=['findchannel'])
def find_channel_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        detected_channel_id = detect_channel_id()
        if detected_channel_id:
            info = get_channel_info()
            if info['success']:
                response = (
                    f"✅ Channel Found!\n\n"
                    f"Title: {info['title']}\n"
                    f"ID: {info['id']}\n"
                    f"Type: {info['type']}\n"
                    f"Username: {info['username']}\n\n"
                    f"Invite link: {info['invite_link']}\n\n"
                    f"Now test with: /testchannel"
                )
            else:
                response = f"✅ Channel ID detected: {detected_channel_id}\nBut error: {info.get('error')}"
        else:
            response = (
                f"❌ Channel not found!\n\n"
                f"Current channel ID: {CHANNEL_ID}\n\n"
                f"Steps to fix:\n"
                f"1. Add @{bot.get_me().username} to your private channel as ADMIN\n"
                f"2. Make sure bot has permission to:\n"
                f"   • Send Messages\n"
                f"   • Send Media\n"
                f"   • Add Web Previews\n"
                f"3. Use /testchannel to verify"
            )
        
        bot.reply_to(message, response)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:200]}")

@bot.message_handler(commands=['testchannel'])
def test_channel_post(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        if not detected_channel_id:
            detect_channel_id()
        
        if not detected_channel_id:
            bot.reply_to(message, "❌ Channel not detected. Use /findchannel first")
            return
        
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(telebot.types.InlineKeyboardButton("🎬 Test Button", url=WEBSITE_BASE_URL))
        
        test_msg = bot.send_message(
            detected_channel_id,
            "✅ **Bot Test Successful!**\n\nThis is a test message from your video bot.\n\nChannel ID: `{}`".format(detected_channel_id),
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # Also test sending a photo
        try:
            photo_msg = bot.send_photo(
                detected_channel_id,
                "https://via.placeholder.com/400x300/0088cc/ffffff?text=Test+Thumbnail",
                caption="✅ **Photo Test**\n\nIf you see this, thumbnails will work!",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as photo_error:
            logger.warning(f"Photo test failed: {photo_error}")
        
        info = get_channel_info()
        channel_name = info.get('title', 'Unknown') if info['success'] else 'Unknown'
        
        bot.reply_to(message, f"✅ Test messages sent to: {channel_name}\n\nNow you can upload videos!")
    except Exception as e:
        error_msg = str(e)
        if "chat not found" in error_msg.lower():
            response = (
                f"❌ **CHANNEL NOT FOUND**\n\n"
                f"Current channel ID: {detected_channel_id}\n"
                f"Expected format: -1003030466566\n\n"
                f"**To fix:**\n"
                f"1. Make sure bot is added to channel\n"
                f"2. Bot must be ADMIN with posting rights\n"
                f"3. Channel must be private but bot can access\n"
                f"4. Use /setchannel to update ID if needed"
            )
        elif "not enough rights" in error_msg.lower():
            response = (
                f"❌ **BOT NEEDS ADMIN RIGHTS**\n\n"
                f"Add @{bot.get_me().username} as ADMIN to your private channel.\n\n"
                f"Required permissions:\n"
                f"• Post Messages ✓\n"
                f"• Edit Messages ✓\n"
                f"• Delete Messages ✓\n"
                f"• Send Media ✓\n"
                f"• Add Web Previews ✓"
            )
        else:
            response = f"❌ Error: {error_msg[:200]}"
        
        bot.reply_to(message, response)

@bot.message_handler(commands=['setchannel'])
def set_channel_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "Usage: /setchannel [channel_id]\nExample: /setchannel -1003030466566")
            return
        
        new_channel_id = parts[1]
        
        try:
            # Convert to int if it's numeric
            if new_channel_id.startswith('-100'):
                new_channel_id = int(new_channel_id)
            elif new_channel_id.isdigit():
                # If user enters 1003030466566, convert to -1003030466566
                if new_channel_id.startswith('100'):
                    new_channel_id = int('-100' + new_channel_id[3:])
                else:
                    new_channel_id = int(new_channel_id)
            
            # Test the channel
            chat = bot.get_chat(new_channel_id)
            
            global detected_channel_id
            detected_channel_id = chat.id
            
            response = (
                f"✅ Channel set successfully!\n\n"
                f"Title: {chat.title}\n"
                f"ID: {chat.id}\n"
                f"Type: {chat.type}\n"
                f"Username: {getattr(chat, 'username', 'Private channel')}\n\n"
                f"Test with: /testchannel"
            )
            
            bot.reply_to(message, response)
        except ValueError:
            bot.reply_to(message, "❌ Invalid channel ID format. Use numeric ID like -1003030466566")
        except Exception as e:
            bot.reply_to(message, f"❌ Invalid channel ID: {str(e)[:100]}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:200]}")

@bot.message_handler(commands=['status'])
def bot_status_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        total_videos = len(video_database)
        videos_with_file = sum(1 for v in video_database.values() if v.get('file_id'))
        videos_with_thumb = sum(1 for v in video_database.values() if v.get('thumbnail_id'))
        uptime_seconds = int(time.time() - app_start_time)
        uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m"
        
        channel_info = get_channel_info()
        if channel_info['success']:
            channel_status = f"✅ {channel_info['title']}"
        else:
            channel_status = f"❌ {channel_info.get('error', 'Not detected')}"
        
        response = (
            f"🤖 Bot Status\n\n"
            f"📊 Database:\n"
            f"Total Videos: {total_videos}\n"
            f"With Files: {videos_with_file}\n"
            f"With Thumbs: {videos_with_thumb}\n\n"
            f"📢 Channel:\n"
            f"{channel_status}\n"
            f"ID: {detected_channel_id or 'Not set'}\n\n"
            f"⏱️ Uptime: {uptime_str}\n\n"
            f"🔧 Commands:\n"
            f"/findchannel - Detect channel\n"
            f"/testchannel - Test posting\n"
            f"/setchannel - Manual set ID"
        )
        
        bot.reply_to(message, response)
    except Exception as e:
        bot.reply_to(message, "✅ Bot is running")

@bot.message_handler(content_types=['photo'])
def handle_photo_upload(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    if message.caption and message.caption.startswith('/thumb'):
        try:
            parts = message.caption.split()
            if len(parts) >= 2:
                video_num = parts[1]
                video_id = f"video{video_num}"
                photo_id = message.photo[-1].file_id
                
                if video_id not in video_database:
                    video_database[video_id] = {
                        'file_id': None,
                        'title': f'Video {video_num}',
                        'added_date': datetime.now().isoformat(),
                        'permanent': False
                    }
                
                video_database[video_id]['thumbnail_id'] = photo_id
                save_database()
                
                bot.reply_to(message, f"✅ Thumbnail set for Video {video_num}!")
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['caption'])
def set_caption_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "Usage: /caption [video_number] [your custom caption]")
            return
        
        video_num = parts[1]
        custom_caption = parts[2]
        video_id = f"video{video_num}"
        
        if video_id not in video_database:
            video_database[video_id] = {
                'file_id': None,
                'title': f'Video {video_num}',
                'added_date': datetime.now().isoformat(),
                'permanent': False
            }
        
        video_database[video_id]['custom_caption'] = custom_caption
        save_database()
        
        bot.reply_to(message, f"✅ Custom caption set for Video {video_num}!\n\n{custom_caption}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:200]}")

def post_to_channel(video_num, video_message=None):
    global detected_channel_id
    try:
        if not detected_channel_id:
            detect_channel_id()
            if not detected_channel_id:
                logger.error("No channel ID detected for posting")
                return False
        
        website_url = f"{WEBSITE_BASE_URL}/?video={video_num}"
        video_id = f"video{video_num}"
        
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(telebot.types.InlineKeyboardButton("🎬 Watch Now", url=website_url))
        
        caption_text = ""
        if video_id in video_database and 'custom_caption' in video_database[video_id]:
            caption_text = video_database[video_id]['custom_caption']
        else:
            caption_text = f"🎥 Video {video_num}"
        
        caption_text += f"\n\nClick the button below to watch 👇"
        
        # First try to send photo with thumbnail
        try:
            if video_id in video_database and 'thumbnail_id' in video_database[video_id]:
                photo_msg = bot.send_photo(
                    chat_id=detected_channel_id,
                    photo=video_database[video_id]['thumbnail_id'],
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                logger.info(f"✅ Posted thumbnail to channel: Video {video_num}")
                return True
            else:
                logger.info(f"⚠️ No thumbnail found for Video {video_num}")
        except Exception as e:
            logger.error(f"❌ Photo post failed for Video {video_num}: {e}")
        
        # If photo fails, try video
        try:
            if video_message and video_message.video:
                video_msg = bot.send_video(
                    chat_id=detected_channel_id,
                    video=video_message.video.file_id,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown',
                    supports_streaming=True
                )
                logger.info(f"✅ Posted video to channel: Video {video_num}")
                return True
        except Exception as e:
            logger.error(f"❌ Video post failed for Video {video_num}: {e}")
        
        # Last resort: text message
        try:
            text_msg = bot.send_message(
                chat_id=detected_channel_id,
                text=caption_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Posted text to channel: Video {video_num}")
            return True
        except Exception as e:
            logger.error(f"❌ Text post failed for Video {video_num}: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Post to channel error for Video {video_num}: {e}")
        return False

@bot.message_handler(content_types=['video'])
def handle_video_upload(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        bot.reply_to(message, "⛔ Admin only.")
        return
    
    file_id = message.video.file_id
    response = (
        f"✅ Video received!\n\n"
        f"File ID: {file_id[:20]}...\n\n"
        f"To save:\n"
        f"1. (Optional) Set thumbnail: Send photo with caption '/thumb [number]'\n"
        f"2. (Optional) Set caption: /caption [number] [text]\n"
        f"3. Reply to this video: /savevideo [number]\n\n"
        f"Example:\n"
        f"/caption 1 Amazing video!\n"
        f"Then reply to video: /savevideo 1"
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
        
        if video_id not in video_database:
            video_database[video_id] = {}
        
        video_database[video_id].update({
            'file_id': file_id,
            'title': f'Video {video_num}',
            'added_date': datetime.now().isoformat(),
            'permanent': True
        })
        
        save_database()
        
        # Try to post to channel
        channel_posted = post_to_channel(video_num, message.reply_to_message)
        
        # Generate response
        has_thumbnail = 'thumbnail_id' in video_database[video_id]
        has_caption = 'custom_caption' in video_database[video_id]
        
        response = f"✅ Video {video_num} saved!\n"
        if has_thumbnail:
            response += "✅ Custom thumbnail set\n"
        if has_caption:
            response += f"✅ Custom caption set\n"
        
        response += f"Channel post: {'✅ Successful' if channel_posted else '❌ Failed'}\n\n"
        response += f"Link: {WEBSITE_BASE_URL}/?video={video_num}"
        
        if not channel_posted:
            response += f"\n\n❌ Channel post failed!\n"
            response += f"Common issues:\n"
            response += f"1. Bot not admin in channel\n"
            response += f"2. Channel ID incorrect\n"
            response += f"3. Bot doesn't have posting rights\n\n"
            response += f"Fix with:\n"
            response += f"/findchannel - Check channel status\n"
            response += f"/testchannel - Test posting ability"
        
        bot.reply_to(message, response)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:200]}")

@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        parts = message.text.split()
        if len(parts) > 1 and parts[1] in video_database:
            send_video_to_user(message, parts[1])
        else:
            show_video_menu(message)
    except Exception as e:
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
    except Exception as e:
        bot.reply_to(message, "❌ Failed to send video.")

def show_video_menu(message):
    if video_database:
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        for vid_id in sorted(video_database.keys()):
            num = vid_id.replace('video', '')
            keyboard.add(telebot.types.InlineKeyboardButton(f"Video {num}", callback_data=f"send_{vid_id}"))
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
                bot.answer_callback_query(call.id, "❌ Failed to send video")

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
        "videos_in_db": len(video_database),
        "channel_detected": bool(detected_channel_id),
        "channel_id": detected_channel_id
    })

@app.route('/')
def home():
    uptime = int(time.time() - app_start_time)
    uptime_str = f"{uptime // 3600}h {(uptime % 3600) // 60}m"
    channel_info = get_channel_info()
    channel_status = "✅" if channel_info['success'] else "❌"
    return f"✅ Video Bot | Channel: {channel_status} | ID: {detected_channel_id} | Uptime: {uptime_str}"

if __name__ == '__main__':
    logger.info(f"🤖 Bot starting...")
    logger.info(f"📢 Channel ID: {CHANNEL_ID}")
    logger.info(f"📢 Channel invite: {CHANNEL_INVITE_LINK}")
    
    detect_channel_id()
    
    if detected_channel_id:
        info = get_channel_info()
        if info['success']:
            logger.info(f"✅ Channel detected: {info['title']} (ID: {detected_channel_id})")
        else:
            logger.warning(f"⚠️ Channel ID found but error: {info.get('error')}")
    else:
        logger.warning("⚠️ Channel not detected. Bot will try to detect when needed.")
    
    logger.info(f"📊 Videos in database: {len(video_database)}")
    
    app.run(host='0.0.0.0', port=5000)
