import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
import re
from datetime import datetime
import time
import random
import yt_dlp
from pathlib import Path
from config import BOT_TOKEN, PROXY_URL

# Path configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'bot.log')
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads')
COOKIES_FILE = os.path.join(BASE_DIR, 'cookies.txt')

# Create directories
for directory in [LOG_DIR, DOWNLOADS_DIR]:
    try:
        os.makedirs(directory, exist_ok=True)
        os.chmod(directory, 0o755)  # Set permissions
    except Exception as e:
        print(f"Error creating directory {directory}: {str(e)}")

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

def download_reel(url, output_path):
    """Download Instagram Reel using yt-dlp"""
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
        'proxy': PROXY_URL,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_color': True,
        'cookiefile': COOKIES_FILE,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.download([url])
            
            # Find downloaded video file
            video_file = None
            for file in os.listdir(output_path):
                if file.endswith('.mp4'):
                    video_file = os.path.join(output_path, file)
                    break
                    
            return video_file
            
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise

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
        
        temp_dir = os.path.join(DOWNLOADS_DIR, f"temp_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(temp_dir, mode=0o755, exist_ok=True)
        
        logger.info(f"Created temp directory: {temp_dir}")
        
        video_path = download_reel(message, temp_dir)
        
        if video_path and os.path.exists(video_path):
            await update.message.reply_text("✅ Загрузка завершена, отправляю видео...")
            await update.message.reply_video(video=open(video_path, 'rb'))
            logger.info(f"Successfully sent video to user {user_id}")
        else:
            await update.message.reply_text("❌ Не удалось скачать видео.")
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
        # Verify cookies file exists and is readable
        if not os.path.exists(COOKIES_FILE):
            logger.error(f"Cookies file not found: {COOKIES_FILE}")
            raise FileNotFoundError("Cookies file is required for Instagram downloads")
            
        if not os.access(COOKIES_FILE, os.R_OK):
            logger.error(f"Cannot read cookies file: {COOKIES_FILE}")
            raise PermissionError("Cannot read cookies file")

        application = Application.builder().token(BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_reels))
        application.add_error_handler(error_handler)

        logger.info("Bot started")
        print("🤖 Бот запущен и готов к работе!")
        application.run_polling()

    except Exception as e:
        logger.critical(f"Critical error: {str(e)}")
        raise

if __name__ == '__main__':
    main()