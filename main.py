import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
import re
from datetime import datetime
import time
import random
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from config import BOT_TOKEN, PROXY_URL

# Path configuration
BASE_DIR = '/var/log/insta-bot'
LOG_FILE = os.path.join(BASE_DIR, 'bot.log')
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads')

# Create directories with proper permissions
for directory in [BASE_DIR, DOWNLOADS_DIR]:
    try:
        os.makedirs(directory, mode=0o755, exist_ok=True)
        os.chmod(directory, 0o755)
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

# Headers for Instagram requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.instagram.com",
    "Connection": "keep-alive"
}

def get_video_url(url):
    """Extract video URL from Instagram Reel page"""
    try:
        proxies = {
            'http': PROXY_URL,
            'https': PROXY_URL
        }
        
        response = requests.get(url, headers=HEADERS, proxies=proxies)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for video URL in meta tags
        video_url = None
        for meta in soup.find_all('meta', {'property': 'og:video'}):
            video_url = meta.get('content')
            if video_url:
                break
                
        if not video_url:
            raise Exception("Video URL not found")
            
        return video_url
        
    except Exception as e:
        logger.error(f"Error extracting video URL: {str(e)}")
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
        
        video_url = get_video_url(message)
        
        proxies = {
            'http': PROXY_URL,
            'https': PROXY_URL
        }
        
        response = requests.get(video_url, headers=HEADERS, proxies=proxies)
        video_path = os.path.join(temp_dir, "reel.mp4")
        
        with open(video_path, 'wb') as f:
            f.write(response.content)
        
        if os.path.exists(video_path):
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