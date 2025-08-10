import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from instagrapi import Client
import os
import re
from datetime import datetime
import time
import random
from pathlib import Path
from config import BOT_TOKEN, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, PROXY_URL

# Path configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'bot.log')
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads')

# Create necessary directories
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Add startup log message
logger.info("Bot starting up...")

# Initialize Instagram client
cl = Client()
cl.set_proxy(PROXY_URL)
cl.set_device_settings('samsung_galaxy_s10')

def initialize_instagram():
    try:
        logger.info(f"Attempting to login to Instagram as {INSTAGRAM_USERNAME}...")
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        
        try:
            user_id = cl.user_id_from_username("instagram")
            logger.info("Instagram login successful")
            return True
        except Exception as e:
            logger.error(f"Login verification failed: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "👋 Привет! Отправь мне ссылку на Reels из Instagram, и я скачаю его для тебя."
        )
        logger.info(f"Start command used by user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}")

async def download_reels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message.text
    
    logger.info(f"Received request from user {user_id}: {message}")
    
    if "instagram.com/reel" not in message:
        await update.message.reply_text("❌ Пожалуйста, отправьте корректную ссылку на Instagram Reels.")
        return

    try:
        await update.message.reply_text("⏳ Начинаю загрузку Reels...")
        
        # Extract media_pk from URL
        media_pk = cl.media_pk_from_url(message)
        
        # Create temp directory
        temp_dir = os.path.join(DOWNLOADS_DIR, f"temp_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(temp_dir, mode=0o755, exist_ok=True)
        
        logger.info(f"Created temp directory: {temp_dir}")
        
        # Random delay
        time.sleep(random.uniform(1, 2))
        
        # Download video
        video_path = cl.clip_download(media_pk, folder=temp_dir)
        logger.info(f"Video download completed: {video_path}")
        
        if video_path and os.path.exists(video_path):
            await update.message.reply_text("✅ Загрузка завершена, отправляю видео...")
            await update.message.reply_video(video=open(video_path, 'rb'))
            logger.info(f"Successfully sent video to user {user_id}")
        else:
            await update.message.reply_text("❌ Не удалось найти видео.")
            logger.error(f"Video file not found")

    except Exception as e:
        error_message = f"❌ Произошла ошибка: {str(e)}"
        await update.message.reply_text(error_message)
        logger.error(f"Error for user {user_id}: {str(e)}")
    
    finally:
        # Cleanup
        try:
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                for file in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, file))
                os.rmdir(temp_dir)
                logger.info(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

def main():
    try:
        # Initialize Instagram
        if not initialize_instagram():
            logger.error("Failed to initialize Instagram")
            return
            
        # Initialize bot
        application = Application.builder().token(BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_reels))
        application.add_error_handler(error_handler)

        # Start bot
        logger.info("Bot started with Instagram API")
        print("🤖 Бот запущен и готов к работе!")
        application.run_polling()

    except Exception as e:
        logger.critical(f"Critical error: {str(e)}")
        raise

if __name__ == '__main__':
    main()