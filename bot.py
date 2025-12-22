#!/usr/bin/env python3
# bot.py - Telegram Bot for sending videos using pyTelegramBotAPI

import os
import logging
import telebot
from telebot import types
from flask import Flask, request

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== EDIT THESE VALUES =====
# Your bot token from BotFather
BOT_TOKEN = "7333444202:AAEogLn_hq-DKQOs6qYoq40dHbLiBHGuzoo"

# Your video file ID (get this by sending video to bot)
VIDEO_FILE_ID = "BAACAgUAAxkBAAEC-DVpSV4-9MJUUM9K4PMX3GnEa_XHugACkx8AAhsKSFbxcawF4hIbRDYE"

# Your Telegram user ID (for admin commands)
ADMIN_USER_ID = 1574602076
# =============================

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Initialize Flask app for webhook (optional)
app = Flask(__name__)

# Store user states
user_requests = {}

# Start command handler
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Send welcome message when /start is issued."""
    user = message.from_user
    
    # Create keyboard
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("🎬 Get Video", callback_data='get_video')
    )
    keyboard.row(
        types.InlineKeyboardButton("📢 Join Channel", url="https://t.me/YOUR_CHANNEL")
    )
    keyboard.row(
        types.InlineKeyboardButton("ℹ️ Help", callback_data='help')
    )
    
    # Send welcome message
    bot.reply_to(
        message,
        f"👋 Hello {user.first_name}!\n\n"
        "Welcome to the Video Sender Bot!\n\n"
        "Click the button below to receive your video:",
        reply_markup=keyboard
    )
    
    # Log the user
    user_requests[user.id] = user_requests.get(user.id, 0) + 1
    logger.info(f"User {user.id} started the bot")

# Callback query handler
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    """Handle button callbacks."""
    if call.data == 'get_video':
        send_video_callback(call)
    elif call.data == 'help':
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🤖 **Bot Help**\n\n"
                 "1. Click 'Get Video' to receive your video\n"
                 "2. Make sure you've clicked the link from our channel\n"
                 "3. If video doesn't send, contact admin\n\n"
                 "📢 Join our channel for more content!",
            parse_mode='Markdown'
        )

# Send video function (for callback)
def send_video_callback(call):
    """Send video to user from callback."""
    try:
        # Edit message to show sending status
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📤 Sending video..."
        )
        
        # Send the video
        bot.send_video(
            call.from_user.id,
            VIDEO_FILE_ID,
            caption="🎬 Here's your video!\n\n"
                   "Enjoy! Don't forget to join our channel for more content!",
            parse_mode='Markdown'
        )
        
        # Update status
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✅ Video sent successfully! Check above. 👆"
        )
        
        logger.info(f"Video sent to user {call.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ Failed to send video. Please try again or contact admin."
        )

# Handle regular messages
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Handle regular text messages."""
    text = message.text.lower()
    
    if any(word in text for word in ['video', 'get', 'send']):
        # Create simple keyboard for video
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("🎬 Get Video", callback_data='get_video')
        )
        bot.reply_to(
            message,
            "Click the button below to get your video:",
            reply_markup=keyboard
        )
    else:
        bot.reply_to(
            message,
            "I don't understand. Try /start to begin."
        )

# Admin command to get file ID
@bot.message_handler(commands=['getfileid'])
def get_file_id(message):
    """Get file ID of sent video (admin only)."""
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "⛔ Admin only command.")
        return
    
    if message.reply_to_message and message.reply_to_message.video:
        video = message.reply_to_message.video
        file_id = video.file_id
        bot.reply_to(
            message,
            f"📹 Video File ID:\n`{file_id}`\n\n"
            "Copy this to your bot.py file",
            parse_mode='Markdown'
        )
    else:
        bot.reply_to(
            message,
            "Reply to a video message with /getfileid to get its file ID."
        )

# Stats command (admin)
@bot.message_handler(commands=['stats'])
def show_stats(message):
    """Show bot statistics (admin only)."""
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "⛔ Admin only command.")
        return
    
    total_users = len(user_requests)
    total_requests = sum(user_requests.values())
    
    bot.reply_to(
        message,
        f"📊 **Bot Statistics**\n\n"
        f"👥 Total Users: {total_users}\n"
        f"📨 Total Requests: {total_requests}\n"
        f"📹 Video File ID: {VIDEO_FILE_ID[:20]}...",
        parse_mode='Markdown'
    )

# Main execution
if __name__ == '__main__':
    print("🤖 Bot is starting...")
    print(f"📹 Video File ID: {VIDEO_FILE_ID}")
    print("✅ Bot is running. Press Ctrl+C to stop.")
    
    # Start polling
    bot.infinity_polling()



