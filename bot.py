import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("7407256981:AAEFnoMfwBK0kXtxKOkEIAnaAC4MSpSzusA")  # token from Render

VIDEO_MAP = {
    "video1": "https://t.me/storagechannel01/2",
    "video2": "https://t.me/storagechannel01/3",
    "video3": "https://t.me/storagechannel01/4"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Welcome! Use the links from the website to get a video.")
        return
    key = args[0]
    video_link = VIDEO_MAP.get(key)
    if video_link:
        await update.message.reply_text(f"Here is your video 🎥:\n{video_link}")
    else:
        await update.message.reply_text("Sorry, I couldn't find that video.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == "__main__":
    main()
