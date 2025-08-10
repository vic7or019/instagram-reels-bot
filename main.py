import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
import re
from datetime import datetime
import time
import random
import json
import requests
from pathlib import Path
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
    "User-Agent": "Instagram 219.0.0.12.117 Android",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.instagram.com",
    "Connection": "keep-alive",
    "Referer": "https://www.instagram.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "X-IG-App-ID": "936619743392459",
    "X-IG-WWW-Claim": "0",
    "X-Requested-With": "XMLHttpRequest"
}

def get_video_url(url):
    """Extract video URL from Instagram Reel using multiple methods"""
    try:
        # Extract shortcode from URL
        shortcode = re.search(r'/reel/([^/?]+)', url).group(1)
        logger.info(f"Extracted shortcode: {shortcode}")
        
        proxies = {
            'http': PROXY_URL,
            'https': PROXY_URL
        }
        
        # Try different methods to get video URL
        methods = [
            {
                'url': f"https://www.instagram.com/graphql/query/?query_hash=b3055c01b4b222b8a47dc12b090e4e64&variables={{\"shortcode\":\"{shortcode}\"}}",
                'path': ['data', 'shortcode_media', 'video_url']
            },
            {
                'url': f"https://www.instagram.com/reel/{shortcode}/?__a=1&__d=dis",
                'path': ['items', 0, 'video_versions', 0, 'url']
            },
            {
                'url': f"https://www.instagram.com/api/v1/media/{shortcode}/info/",
                'path': ['items', 0, 'video_versions', 0, 'url']
            }
        ]
        
        for method in methods:
            try:
                response = requests.get(
                    method['url'], 
                    headers=HEADERS, 
                    proxies=proxies,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Navigate through JSON path
                    result = data
                    for key in method['path']:
                        result = result[key] if isinstance(key, str) else result[key]
                    if result and isinstance(result, str):
                        logger.info(f"Successfully found video URL using method: {method['url']}")
                        return result
            except Exception as e:
                logger.warning(f"Method failed {method['url']}: {str(e)}")
                continue
        
        raise Exception("Не удалось получить URL видео ни одним из методов")
            
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
        
        # Get video URL with retries
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                video_url = get_video_url(message)
                break
            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    raise
                time.sleep(random.uniform(1, 3))
        
        proxies = {
            'http': PROXY_URL,
            'https': PROXY_URL
        }
        
        # Download video with timeout and chunk size
        response = requests.get(
            video_url, 
            headers=HEADERS, 
            proxies=proxies, 
            stream=True,
            timeout=30
        )
        
        video_path = os.path.join(temp_dir, "reel.mp4")
        
        with open(video_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
            await update.message.reply_text("✅ Загрузка завершена, отправляю видео...")
            await update.message.reply_video(video=open(video_path, 'rb'))
            logger.info(f"Successfully sent video to user {user_id}")
        else:
            await update.message.reply_text("❌ Не удалось скачать видео.")
            logger.error(f"Video file is empty or not found")

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