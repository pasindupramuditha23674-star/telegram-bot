import os
import json
import logging
import threading
import time
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
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

# ===== VIDEO CHANNEL =====
CHANNEL_INVITE_LINK = "https://t.me/+NEW_LINK_HERE"
CHANNEL_ID = -1003030466566

# ===== LINK CHANNEL =====
LINK_GROUP_ID = -1003302471500

WEBSITE_BASE_URL = "https://spontaneous-halva-72f63a.netlify.app"

app = Flask(__name__)
CORS(app)
bot = telebot.TeleBot(BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

app_start_time = time.time()
video_database = {}
sent_videos = {}
detected_channel_id = CHANNEL_ID
link_database = {}

# ---------- MongoDB / JSON setup ----------
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
        links_collection = db.links
        videos_collection.create_index('video_id', unique=True)
        sent_videos_collection.create_index('key', unique=True)
        links_collection.create_index('link_id', unique=True)
        return {
            'client': client,
            'videos': videos_collection,
            'sent_videos': sent_videos_collection,
            'links': links_collection
        }
    except Exception:
        return None

mongo_client = connect_to_mongodb()

# ----- Video database -----
def load_database():
    global video_database
    try:
        if mongo_client and 'videos' in mongo_client:
            videos_cursor = mongo_client['videos'].find({})
            video_database = {}
            for doc in videos_cursor:
                video_id = doc['video_id']
                doc.pop('_id', None)
                video_database[video_id] = doc
            return
        if os.path.exists('video_database.json'):
            with open('video_database.json', 'r') as f:
                video_database = json.load(f)
        else:
            video_database = {}
    except Exception:
        video_database = {}

def save_database():
    try:
        if mongo_client and 'videos' in mongo_client:
            for video_id, data in video_database.items():
                data_to_save = data.copy()
                data_to_save['video_id'] = video_id
                data_to_save['last_updated'] = datetime.now().isoformat()
                mongo_client['videos'].update_one(
                    {'video_id': video_id},
                    {'$set': data_to_save},
                    upsert=True
                )
        with open('video_database.json', 'w') as f:
            json.dump(video_database, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# ----- Link database -----
def load_links():
    global link_database
    try:
        if mongo_client and 'links' in mongo_client:
            cursor = mongo_client['links'].find({})
            link_database = {}
            for doc in cursor:
                link_id = doc['link_id']
                doc.pop('_id', None)
                link_database[link_id] = doc
            return
        if os.path.exists('link_database.json'):
            with open('link_database.json', 'r') as f:
                link_database = json.load(f)
        else:
            link_database = {}
    except Exception:
        link_database = {}

def save_links():
    try:
        if mongo_client and 'links' in mongo_client:
            for link_id, data in link_database.items():
                data_to_save = data.copy()
                data_to_save['link_id'] = link_id
                data_to_save['last_updated'] = datetime.now().isoformat()
                mongo_client['links'].update_one(
                    {'link_id': link_id},
                    {'$set': data_to_save},
                    upsert=True
                )
        with open('link_database.json', 'w') as f:
            json.dump(link_database, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# ----- Sent videos -----
def load_sent_videos():
    global sent_videos
    try:
        if mongo_client and 'sent_videos' in mongo_client:
            cursor = mongo_client['sent_videos'].find({})
            sent_videos = {}
            for doc in cursor:
                key = doc.get('key')
                if key:
                    doc.pop('_id', None)
                    doc.pop('key', None)
                    sent_videos[key] = doc
            return
        if os.path.exists('sent_videos.json'):
            with open('sent_videos.json', 'r') as f:
                sent_videos = json.load(f)
        else:
            sent_videos = {}
    except Exception:
        sent_videos = {}

def save_sent_videos():
    global sent_videos
    try:
        if mongo_client and 'sent_videos' in mongo_client:
            mongo_client['sent_videos'].delete_many({})
            if sent_videos:
                documents = []
                for key, data in sent_videos.items():
                    doc = data.copy()
                    doc['key'] = key
                    documents.append(doc)
                mongo_client['sent_videos'].insert_many(documents)
        with open('sent_videos.json', 'w') as f:
            json.dump(sent_videos, f, indent=2, ensure_ascii=False)
    except Exception:
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
        except Exception:
            time.sleep(60)

threading.Thread(target=auto_delete_worker, daemon=True).start()

load_database()
load_links()
load_sent_videos()

# ========== KEEP ALIVE FUNCTION ==========
def keep_alive():
    url = "https://telegram-bot-7-dqqa.onrender.com/"
    while True:
        time.sleep(600)
        try:
            response = requests.get(url, timeout=10)
            logger.info(f"Self-ping keep-alive: status {response.status_code}")
        except Exception as e:
            logger.error(f"Self-ping failed: {e}")

threading.Thread(target=keep_alive, daemon=True).start()

# ========== ORIGINAL VIDEO COMMANDS ==========
def detect_channel_id():
    global detected_channel_id
    try:
        if CHANNEL_ID:
            chat = bot.get_chat(CHANNEL_ID)
            detected_channel_id = chat.id
            return detected_channel_id
        if CHANNEL_INVITE_LINK:
            chat = bot.get_chat(CHANNEL_INVITE_LINK)
            detected_channel_id = chat.id
            return detected_channel_id
        return None
    except Exception:
        return None

def get_channel_info():
    global detected_channel_id
    try:
        if not detected_channel_id:
            detected_channel_id = detect_channel_id()
        chat = bot.get_chat(detected_channel_id)
        return {'success': True, 'title': chat.title, 'id': chat.id}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@bot.message_handler(commands=['thumbname'])
def set_thumbnail_name_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "Usage: /thumbname [num] [name]")
        return
    video_id = f"video{parts[1]}"
    if video_id not in video_database:
        bot.reply_to(message, "Video not found")
        return
    video_database[video_id]['thumbnail_name'] = parts[2]
    save_database()
    bot.reply_to(message, f"✅ Set name: {parts[2]}")

@bot.message_handler(commands=['listthumbnames'])
def list_thumbnail_names_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    if not video_database:
        bot.reply_to(message, "No videos")
        return
    text = "📋 Custom names:\n"
    for vid, data in video_database.items():
        num = vid.replace('video','')
        name = data.get('thumbnail_name', 'No name')
        text += f"Video {num}: {name}\n"
    bot.reply_to(message, text[:4000])

@bot.message_handler(commands=['removethumbname'])
def remove_thumbnail_name_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /removethumbname [num]")
        return
    video_id = f"video{parts[1]}"
    if video_id in video_database and 'thumbnail_name' in video_database[video_id]:
        del video_database[video_id]['thumbnail_name']
        save_database()
        bot.reply_to(message, "✅ Removed")
    else:
        bot.reply_to(message, "No custom name")

@bot.message_handler(commands=['findchannel'])
def find_channel_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    cid = detect_channel_id()
    bot.reply_to(message, f"Channel ID: {cid}" if cid else "Not found")

@bot.message_handler(commands=['testchannel'])
def test_channel_post(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    if not detected_channel_id: detect_channel_id()
    if not detected_channel_id:
        bot.reply_to(message, "No channel")
        return
    try:
        bot.send_message(detected_channel_id, "Test OK")
        bot.reply_to(message, "Sent")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['setchannel'])
def set_channel_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /setchannel [id]")
        return
    try:
        new_id = int(parts[1])
        chat = bot.get_chat(new_id)
        global detected_channel_id
        detected_channel_id = chat.id
        bot.reply_to(message, f"✅ Channel set to {chat.title}")
    except Exception as e:
        bot.reply_to(message, f"Invalid: {e}")

@bot.message_handler(commands=['status'])
def bot_status_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    uptime = int(time.time() - app_start_time)
    uptime_str = f"{uptime//3600}h {(uptime%3600)//60}m"
    bot.reply_to(message, f"Videos: {len(video_database)} | Links: {len(link_database)} | Uptime: {uptime_str}")

@bot.message_handler(content_types=['photo'])
def handle_photo_upload(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    if message.caption and message.caption.startswith('/thumb'):
        parts = message.caption.split()
        if len(parts) >= 2:
            video_id = f"video{parts[1]}"
            if video_id not in video_database:
                video_database[video_id] = {}
            video_database[video_id]['thumbnail_id'] = message.photo[-1].file_id
            save_database()
            bot.reply_to(message, f"✅ Thumbnail set for {video_id}")

@bot.message_handler(commands=['caption'])
def set_caption_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "Usage: /caption [num] [text]")
        return
    video_id = f"video{parts[1]}"
    if video_id not in video_database:
        video_database[video_id] = {}
    video_database[video_id]['custom_caption'] = parts[2]
    save_database()
    bot.reply_to(message, "✅ Caption set")

def post_to_channel(video_num, video_message=None):
    try:
        if not detected_channel_id: detect_channel_id()
        website_url = f"{WEBSITE_BASE_URL}/?video={video_num}"
        video_id = f"video{video_num}"
        display_name = video_database[video_id].get('thumbnail_name', f'Video {video_num}')
        caption = video_database[video_id].get('custom_caption', f"🎥 {display_name}") + "\n\nClick button 👇"
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(telebot.types.InlineKeyboardButton("🎬 Watch Now", url=website_url))
        if 'thumbnail_id' in video_database[video_id]:
            bot.send_photo(detected_channel_id, video_database[video_id]['thumbnail_id'], caption=caption, reply_markup=keyboard)
        else:
            bot.send_message(detected_channel_id, caption, reply_markup=keyboard)
        return True
    except Exception as e:
        logger.error(f"Post error: {e}")
        return False

@bot.message_handler(content_types=['video'])
def handle_video_upload(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    bot.reply_to(message, "Video received. Reply with /savevideo [number]")

@bot.message_handler(commands=['savevideo'])
def save_video_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    if not message.reply_to_message or not message.reply_to_message.video:
        bot.reply_to(message, "Reply to a video with /savevideo [number]")
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /savevideo [number]")
        return
    video_num = parts[1]
    video_id = f"video{video_num}"
    file_id = message.reply_to_message.video.file_id
    if video_id not in video_database:
        video_database[video_id] = {}
    video_database[video_id]['file_id'] = file_id
    video_database[video_id]['title'] = f'Video {video_num}'
    video_database[video_id]['added_date'] = datetime.now().isoformat()
    save_database()
    posted = post_to_channel(video_num, message.reply_to_message)
    bot.reply_to(message, f"✅ Video {video_num} saved. Channel post: {'OK' if posted else 'Failed'}")

def show_video_menu(message):
    if not video_database:
        bot.reply_to(message, "No videos yet.")
        return
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    for vid in sorted(video_database.keys(), key=lambda x: int(x.replace('video','') or 0)):
        num = vid.replace('video','')
        name = video_database[vid].get('thumbnail_name', f'Video {num}')
        keyboard.add(telebot.types.InlineKeyboardButton(f"🎬 {name}", callback_data=f"send_{vid}"))
    bot.reply_to(message, "Select a video:", reply_markup=keyboard)

@bot.message_handler(commands=['start'])
def handle_start(message):
    parts = message.text.split()
    if len(parts) > 1 and parts[1] in video_database:
        send_video_to_user(message, parts[1])
    else:
        show_video_menu(message)

def send_video_to_user(message, video_id):
    try:
        video_data = video_database[video_id]
        sent = bot.send_video(message.chat.id, video_data['file_id'], protect_content=True)
        add_sent_video(message.chat.id, sent.message_id, video_id, datetime.now().isoformat())
    except Exception as e:
        bot.reply_to(message, "Failed to send video.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data.startswith('send_'):
        video_id = call.data.replace('send_', '')
        if video_id in video_database:
            try:
                sent = bot.send_video(call.from_user.id, video_database[video_id]['file_id'], protect_content=True)
                add_sent_video(call.from_user.id, sent.message_id, video_id, datetime.now().isoformat())
                bot.answer_callback_query(call.id, "✅ Video sent!")
            except Exception:
                bot.answer_callback_query(call.id, "❌ Failed")
    elif call.data == "list_names" and call.from_user.id == YOUR_TELEGRAM_ID:
        list_thumbnail_names_command(call.message)
        bot.answer_callback_query(call.id)

# ========== NEW LINK MANAGEMENT COMMANDS ==========
@bot.message_handler(commands=['addlink'])
def add_link_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        bot.reply_to(message, "Usage: /addlink [number] [url] [display_name]\nExample: /addlink 1 https://t.me/telegram 'News'")
        return
    link_num = parts[1]
    url = parts[2]
    name = parts[3]
    link_id = f"link{link_num}"
    if not url.startswith(('http://','https://')):
        url = 'https://' + url
    link_database[link_id] = {
        "url": url,
        "name": name,
        "added_date": datetime.now().isoformat()
    }
    save_links()
    post_link_to_group(link_num)
    bot.reply_to(message, f"✅ Link {link_num} saved and posted to channel.\nName: {name}\nURL: {url}")

@bot.message_handler(commands=['setlinkdesc'])
def set_link_description(message):
    """Set a custom description for a link post.
    Usage: /setlinkdesc 1 This is my channel description"""
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "Usage: /setlinkdesc [link_number] [description]\nExample: /setlinkdesc 1 This channel posts daily news.")
        return
    link_num = parts[1]
    description = parts[2]
    link_id = f"link{link_num}"
    if link_id not in link_database:
        bot.reply_to(message, f"❌ Link {link_num} not found. Use /addlink first.")
        return
    link_database[link_id]['description'] = description
    save_links()
    bot.reply_to(message, f"✅ Description set for Link {link_num}:\n\n{description}")

@bot.message_handler(commands=['listlinks'])
def list_links_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    if not link_database:
        bot.reply_to(message, "No links yet.")
        return
    text = "📌 Saved links:\n"
    for lid, data in link_database.items():
        text += f"• {lid}: {data['name']}\n  → {data['url']}\n"
        if 'description' in data:
            text += f"  📝 {data['description'][:50]}...\n"
        text += "\n"
    bot.reply_to(message, text[:4000], parse_mode='Markdown')

@bot.message_handler(commands=['deletelink'])
def delete_link_command(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /deletelink link1")
        return
    if parts[1] in link_database:
        del link_database[parts[1]]
        save_links()
        bot.reply_to(message, f"✅ {parts[1]} deleted.")
    else:
        bot.reply_to(message, "❌ Not found.")

@bot.message_handler(commands=['postlink'])
def post_link_manually(message):
    if message.from_user.id != YOUR_TELEGRAM_ID: return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /postlink 1")
        return
    if post_link_to_group(parts[1]):
        bot.reply_to(message, f"✅ Link {parts[1]} reposted.")
    else:
        bot.reply_to(message, "❌ Failed.")

@bot.message_handler(commands=['getlink'])
def get_link_direct_command(message):
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /getlink [number]")
        return
    link_id = f"link{parts[1]}"
    if link_id not in link_database:
        bot.reply_to(message, f"❌ Link {parts[1]} not found.")
        return
    url = link_database[link_id]['url']
    name = link_database[link_id]['name']
    bot.reply_to(message, f"🔗 **{name}**\n\n{url}", parse_mode='Markdown', disable_web_page_preview=False)

def post_link_to_group(link_num):
    try:
        if LINK_GROUP_ID is None:
            logger.error("LINK_GROUP_ID not set")
            return False
        link_id = f"link{link_num}"
        if link_id not in link_database:
            return False
        data = link_database[link_id]
        target_url = f"{WEBSITE_BASE_URL}/?link={link_num}"
        
        # Build the message: bold channel name, optional description, then button
        channel_name = data['name']
        description = data.get('description', '')
        
        caption = f"✨ **{channel_name}**"
        if description:
            caption += f"\n{description}"
        
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(telebot.types.InlineKeyboardButton("🔗 Get Link", url=target_url))
        
        bot.send_message(LINK_GROUP_ID, caption, reply_markup=keyboard, parse_mode='Markdown')
        logger.info(f"Posted link {link_num} to channel {LINK_GROUP_ID}")
        return True
    except Exception as e:
        logger.error(f"Failed to post link: {e}")
        return False

# ========== API endpoint for website ==========
@app.route('/api/links')
def get_links_api():
    return jsonify(link_database)

# ========== FLASK WEBHOOKS ==========
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
    return jsonify({"message": "Webhooks configured", "videos": len(video_database), "links": len(link_database)})

@app.route('/')
def home():
    uptime = int(time.time() - app_start_time)
    uptime_str = f"{uptime // 3600}h {(uptime % 3600) // 60}m"
    return f"✅ Bot running | Videos: {len(video_database)} | Links: {len(link_database)} | Uptime: {uptime_str}"

if __name__ == '__main__':
    logger.info("Starting bot...")
    detect_channel_id()
    app.run(host='0.0.0.0', port=5000)
