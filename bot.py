import os
import logging
from flask import Flask, request, jsonify
import telebot

# ------------------ CONFIG ------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")

# Webhook URL (update with your Render app URL)
WEBHOOK_URL = "https://YOUR-APP-NAME.onrender.com/webhook"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# ------------------ VIDEO DATABASE ------------------
video_database = {
    'video1': {
        'file_id': 'AAMCBQADGQECkBz3aUjXEzUStPLev12oYAwVjrCfTUwAAsUaAAJrmklWBsTui-qiTgEBAAdtAAM2BA',
        'title': 'Amazing Video 1',
        'description': 'This is the first amazing video'
    },
    'video2': {
        'file_id': 'AAMCBQADGQECYDuHaPT0KZILOjJlvHRedB8xTXiM1ucAAuQdAAJVSahXrQZIKoihduEBAAdtAAM2BA',
        'title': 'Awesome Video 2',
        'description': 'This is the second awesome video'
    }
}

# ------------------ BOT HANDLERS ------------------
@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        text = message.text.strip()
        parts = text.split(maxsplit=1)

        logger.info(f"/start from {user_id}: {text}")

        # ❌ Started without website parameter
        if len(parts) < 2:
            bot.reply_to(
                message,
                "❌ Please get the video using the button on our website.\n\n"
                "👉 Go back, wait 5 seconds, and click **Get Video**."
            )
            return

        video_key = parts[1]

        # ❌ Invalid or fake parameter
        if video_key not in video_database:
            bot.reply_to(
                message,
                "❌ Invalid or expired link.\n\n"
                "Please return to the website and try again."
            )
            return

        video_data = video_database[video_key]

        bot.reply_to(message, f"🎬 Sending: *{video_data['title']}*", parse_mode="Markdown")
        send_specific_video(message.chat.id, video_data)

    except Exception as e:
        logger.exception("Start command error")
        bot.reply_to(message, "⚠️ Something went wrong. Please try again.")

def send_specific_video(chat_id, video_data):
    try:
        bot.send_video(
            chat_id=chat_id,
            video=video_data['file_id'],
            caption=(
                f"🎥 *{video_data['title']}*\n\n"
                f"{video_data['description']}\n\n"
                "Enjoy! 😊"
            ),
            parse_mode="Markdown"
        )
        logger.info(f"Video sent: {video_data['title']}")
    except Exception:
        logger.exception("Video send error")
        bot.send_message(chat_id, "❌ Failed to send video. Please try again later.")

@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.reply_to(
        message,
        "📹 This bot sends videos **only via our website**.\n\n"
        "Steps:\n"
        "1️⃣ Open the website link\n"
        "2️⃣ Wait 5 seconds\n"
        "3️⃣ Click **Get Video**\n"
        "4️⃣ Video will arrive here automatically"
    )

# ------------------ FLASK WEBHOOK ------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.data.decode("utf-8"))
        bot.process_new_updates([update])
        return "OK"
    except Exception:
        logger.exception("Webhook error")
        return "ERROR", 400

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set: {WEBHOOK_URL}")
        return jsonify({"success": True, "webhook": WEBHOOK_URL})
    except Exception as e:
        logger.exception("Set webhook error")
        return jsonify({"success": False, "error": str(e)})

@app.route('/')
def index():
    return "✅ Bot is running and ready to deliver videos!"

# ------------------ RUN FLASK ------------------
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=PORT)

