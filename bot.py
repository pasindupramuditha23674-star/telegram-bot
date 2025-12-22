#!/usr/bin/env python3
# bot.py - Telegram Bot for sending videos

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== EDIT THESE VALUES =====
# Your bot token from BotFather
BOT_TOKEN = "7333444202:AAEogLn_hq-DKQOs6qYoq40dHbLiBHGuzoo"

# Your video file ID (get this by sending /getfileid to your bot after uploading)
VIDEO_FILE_ID = "YOUR_VIDEO_FILE_ID_HERE"

# Your Telegram user ID (for admin commands)
ADMIN_USER_ID = YOUR_USER_ID_HERE
# =============================

# Store user states (optional for tracking)
user_requests = {}

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("🎬 Get Video", callback_data='get_video')],
        [InlineKeyboardButton("📢 Join Channel", url="https://t.me/storagechannel01")],
        [InlineKeyboardButton("ℹ️ Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f"👋 Hello {user.mention_html()}!\n\n"
        "Welcome to the Video Sender Bot!\n\n"
        "Click the button below to receive your video:",
        reply_markup=reply_markup
    )
    
    # Log the user
    user_requests[user.id] = user_requests.get(user.id, 0) + 1
    logger.info(f"User {user.id} started the bot")

# Handle button callbacks
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'get_video':
        await send_video(update, context)
    elif query.data == 'help':
        await query.edit_message_text(
            text="🤖 **Bot Help**\n\n"
                 "1. Click 'Get Video' to receive your video\n"
                 "2. Make sure you've clicked the link from our channel\n"
                 "3. If video doesn't send, contact admin\n\n"
                 "📢 Join our channel for more content!",
            parse_mode='Markdown'
        )

# Send video function
async def send_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send video to user."""
    try:
        # Check if it's callback query or message
        if update.callback_query:
            user = update.callback_query.from_user
            message = update.callback_query.message
        else:
            user = update.effective_user
            message = update.message
        
        # Send "sending" status
        if update.callback_query:
            await update.callback_query.edit_message_text("📤 Sending video...")
        else:
            await message.reply_text("📤 Sending video...")
        
        # Send the video
        await context.bot.send_video(
            chat_id=user.id,
            video=VIDEO_FILE_ID,
            caption="🎬 Here's your video!\n\n"
                   "Enjoy! Don't forget to join our channel for more content!",
            parse_mode='Markdown'
        )
        
        # Update status
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "✅ Video sent successfully! Check above. 👆"
            )
        
        logger.info(f"Video sent to user {user.id}")
        
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        error_msg = "❌ Failed to send video. Please try again or contact admin."
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.effective_message.reply_text(error_msg)

# Admin command to get file ID
async def getfileid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get file ID of sent video (admin only)."""
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return
    
    if update.message.reply_to_message and update.message.reply_to_message.video:
        video = update.message.reply_to_message.video
        file_id = video.file_id
        await update.message.reply_text(
            f"📹 Video File ID:\n`{file_id}`\n\n"
            "Copy this to your bot.py file",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "Reply to a video message with /getfileid to get its file ID."
        )

# Stats command (admin)
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics (admin only)."""
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return
    
    total_users = len(user_requests)
    total_requests = sum(user_requests.values())
    
    await update.message.reply_text(
        f"📊 **Bot Statistics**\n\n"
        f"👥 Total Users: {total_users}\n"
        f"📨 Total Requests: {total_requests}\n"
        f"📹 Video File ID: {VIDEO_FILE_ID[:20]}...",
        parse_mode='Markdown'
    )

# Broadcast command (admin)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users (admin only)."""
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast Your message here")
        return
    
    message = ' '.join(context.args)
    sent = 0
    failed = 0
    
    for user_id in list(user_requests.keys()):
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 **Broadcast**\n\n{message}",
                parse_mode='Markdown'
            )
            sent += 1
        except:
            failed += 1
    
    await update.message.reply_text(
        f"📢 Broadcast completed!\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message."""
    await update.message.reply_text(
        "🤖 **How to use this bot:**\n\n"
        "1. Click 'Get Video' button\n"
        "2. Wait for the video to be sent\n"
        "3. Join our channel for more content\n\n"
        "👨‍💻 Admin commands:\n"
        "/stats - View bot statistics\n"
        "/broadcast - Send message to all users\n"
        "/getfileid - Get video file ID\n\n"
        "Need help? Contact @your_username",
        parse_mode='Markdown'
    )

# Handle regular messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages."""
    text = update.message.text.lower()
    
    if any(word in text for word in ['video', 'get', 'send']):
        await send_video(update, context)
    else:
        await update.message.reply_text(
            "Click the button below to get your video:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎬 Get Video", callback_data='get_video')
            ]])
        )

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

# Main function
def main():
    """Start the bot."""
    # Create Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("getfileid", getfileid))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    print("🤖 Bot is starting...")
    print(f"📹 Video File ID: {VIDEO_FILE_ID}")
    print("✅ Bot is running. Press Ctrl+C to stop.")
    
    # Run bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
