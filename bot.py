import logging
from flask import Flask, request
import telebot
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "7768542371:AAFVJ9PDPSnS63Cm9jWsGtOt4EMwYZJajAA"
YOUR_TELEGRAM_ID = 1574602076

app = Flask(__name__)
CORS(app)
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['status'])
def status_command(message):
    bot.reply_to(message, "✅ Bot is alive and well")

@bot.message_handler(commands=['addlink'])
def addlink_command(message):
    logger.info(f"ADD LINK CALLED by user {message.from_user.id}")
    if message.from_user.id != YOUR_TELEGRAM_ID:
        bot.reply_to(message, "Unauthorized")
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        bot.reply_to(message, "Usage: /addlink [num] [url] [name]")
        return
    bot.reply_to(message, f"Received: number={parts[1]}, url={parts[2]}, name={parts[3]}")

@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK'

if __name__ == '__main__':
    bot.remove_webhook()
    app.run(host='0.0.0.0', port=5000)
