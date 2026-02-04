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
CHANNEL_ID = "-1002264208544"
WEBSITE_BASE_URL = "https://spontaneous-halva-72f63a.netlify.app"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

app_start_time = time.time()
video_database = {}
sent_videos = {}

def get_channel_info():
    try:
        chat = bot.get_chat(CHANNEL_ID)
        return {
            'success': True,
            'title': chat.title,
            'type': chat.type,
            'id': chat.id
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.route('/health')
@app.route('/ping')
def health_check():
    try:
        mongo_status = "connected" if mongo_client is not None else "disconnected"
        channel_info = get_channel_info()
        channel_status = "✅ Connected" if channel_info['success'] else "❌ Error"
        
        response = {
            "status": "healthy",
            "service": "telegram-video-bot",
            "timestamp": datetime.now().isoformat(),
            "videos": len(video_database),
            "mongodb": mongo_status,
            "channel": channel_status,
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

@bot.message_handler(commands=['channelinfo'])
def channel_info_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        info = get_channel_info()
        if info['success']:
            response = f"✅ Channel: {info['title']}\nID: {info['id']}"
        else:
            response = f"❌ Error: {info.get('error')}"
        bot.reply_to(message, response)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:200]}")

@bot.message_handler(commands=['testchannel'])
def test_channel_post(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(telebot.types.InlineKeyboardButton("🎬 Test", url=WEBSITE_BASE_URL))
        
        test_msg = bot.send_message(
            CHANNEL_ID,
            "✅ Bot test message with button",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        bot.reply_to(message, "✅ Channel test successful! Check your channel.")
    except Exception as e:
        bot.reply_to(message, f"❌ Channel error: {str(e)[:200]}")

@bot.message_handler(commands=['mongotest'])
def test_mongodb(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        mongodb_uri = os.getenv('MONGODB_URI', 'Not set')
        test_status = "Not tested"
        if mongodb_uri and mongodb_uri != 'Not set':
            try:
                test_client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
                test_client.admin.command('ping')
                test_status = "✅ CONNECTED"
                test_client.close()
            except Exception as e:
                test_status = f"❌ FAILED: {str(e)[:150]}"
        else:
            test_status = "❌ URI NOT SET"
        
        response = f"MongoDB: {test_status}"
        bot.reply_to(message, response)
    except Exception as e:
        bot.reply_to(message, f"Test error: {str(e)[:100]}")

@bot.message_handler(commands=['status'])
def bot_status_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        return
    
    try:
        total_videos = len(video_database)
        videos_with_file = sum(1 for v in video_database.values() if v.get('file_id'))
        uptime_seconds = int(time.time() - app_start_time)
        uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m"
        
        response = f"Videos: {total_videos}\nReady: {videos_with_file}\nUptime: {uptime_str}"
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
    try:
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
        
        try:
            if video_id in video_database and 'thumbnail_id' in video_database[video_id]:
                bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=video_database[video_id]['thumbnail_id'],
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                return True
        except Exception as e:
            logger.warning(f"Photo post failed: {e}")
        
        try:
            if video_message and video_message.video:
                bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=video_message.video.file_id,
                    caption=caption_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown',
                    supports_streaming=True
                )
                return True
        except Exception as e:
            logger.warning(f"Video post failed: {e}")
        
        try:
            bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            return True
        except Exception as e:
            logger.error(f"Text post also failed: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Post to channel error: {e}")
        return False

@bot.message_handler(content_types=['video'])
def handle_video_upload(message):
    if message.from_user.id != YOUR_TELEGRAM_ID:
        bot.reply_to(message, "⛔ Admin only.")
        return
    
    file_id = message.video.file_id
    response = (
        f"✅ Video ready!\n\n"
        f"Optional:\n"
        f"1. Set thumbnail: /thumb [number]\n"
        f"2. Set caption: /caption [number] [text]\n\n"
        f"Then reply to this video with:\n"
        f"/savevideo [number]"
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
        
        channel_posted = post_to_channel(video_num, message.reply_to_message)
        
        has_thumbnail = 'thumbnail_id' in video_database[video_id]
        has_caption = 'custom_caption' in video_database[video_id]
        
        response = f"✅ Video {video_num} saved!\n"
        if has_thumbnail:
            response += "✅ Custom thumbnail\n"
        if has_caption:
            response += f"✅ Custom caption\n"
        
        response += f"Channel post: {'✅ Successful' if channel_posted else '❌ Failed'}\n\n"
        response += f"Link: {WEBSITE_BASE_URL}/?video={video_num}"
        
        if not channel_posted:
            response += f"\n\n❌ Channel post failed. Check:\n"
            response += f"1. Bot is admin in channel\n"
            response += f"2. Test with /testchannel"
        
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
        "videos_in_db": len(video_database)
    })

@app.route('/')
def home():
    uptime = int(time.time() - app_start_time)
    uptime_str = f"{uptime // 3600}h {(uptime % 3600) // 60}m"
    return f"✅ Video Bot running! | Uptime: {uptime_str}"

if __name__ == '__main__':
    logger.info(f"🤖 Bot started for channel: {CHANNEL_ID}")
    logger.info(f"📊 Videos: {len(video_database)}")
    app.run(host='0.0.0.0', port=5000)
