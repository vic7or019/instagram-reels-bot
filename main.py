import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import instaloader
import os
import re
from datetime import datetime
import time
import random
import socks
import socket
from pathlib import Path
import shutil
from config import BOT_TOKEN, PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS

# Path configuration
BASE_DIR = '/var/log/insta-bot'
LOG_FILE = os.path.join(BASE_DIR, 'bot.log')
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads')
SESSION_FILE = '/home/ubuntu/instagram-reels-bot/session-kluyev_s'

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure proxy
socks.setdefaultproxy(
    proxy_type=socks.PROXY_TYPE_SOCKS5,
    addr=PROXY_HOST,
    port=PROXY_PORT,
    username=PROXY_USER,
    password=PROXY_PASS
)
socket.socket = socks.socksocket

# Initialize Instagram loader
L = instaloader.Instaloader(
    download_videos=True,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    compress_json=False,
    post_metadata_txt_pattern='',
    user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 12_3_1 like Mac OS X) AppleWebKit/605.1.15'
)

def load_session():
    try:
        logger.info("Attempting to load Instagram session...")
        session_file = Path(SESSION_FILE)
        
        if not session_file.exists():
            logger.error(f"Session file not found at: {session_file}")
            return False
            
        # Create temp session directory
        temp_session_dir = Path('/tmp/.instaloader-ubuntu')
        temp_session_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy session file to temp directory
        temp_session_file = temp_session_dir / 'session-kluyev_s'
        shutil.copy2(session_file, temp_session_file)
        
        # Load session
        L.load_session('kluyev_s')
        
        # Verify session
        try:
            test_profile = instaloader.Profile.from_username(L.context, "instagram")
            logger.info("Session loaded and verified successfully")
            return True
        except Exception as e:
            logger.error(f"Session verification failed: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to load session: {str(e)}")
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
        
        # Extract video ID from URL
        shortcode = re.search(r"/reel/([^/]+)/", message).group(1)
        
        # Create temp directory
        temp_dir = os.path.join(DOWNLOADS_DIR, f"temp_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(temp_dir, mode=0o755, exist_ok=True)
        
        logger.info(f"Created temp directory: {temp_dir}")
        
        # Random delay before request
        time.sleep(random.uniform(1, 2))
        
        # Get post through proxy
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        logger.info(f"Successfully retrieved post information for shortcode: {shortcode}")
        
        # Download video
        L.download_post(post, target=temp_dir)
        logger.info("Post download completed")
        
        # Find video file
        video_file = None
        for file in os.listdir(temp_dir):
            if file.endswith('.mp4'):
                video_file = os.path.join(temp_dir, file)
                break
        
        if video_file:
            await update.message.reply_text("✅ Загрузка завершена, отправляю видео...")
            await update.message.reply_video(video=open(video_file, 'rb'))
            logger.info(f"Successfully sent video to user {user_id}")
        else:
            await update.message.reply_text("❌ Не удалось найти видео.")
            logger.error(f"Video file not found for user {user_id}")

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
        # Create required directories
        os.makedirs(DOWNLOADS_DIR, mode=0o755, exist_ok=True)
        
        # Load Instagram session
        if not load_session():
            logger.error("Failed to load Instagram session")
            return
            
        # Initialize bot
        application = Application.builder().token(BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_reels))
        application.add_error_handler(error_handler)

        # Start bot
        logger.info("Bot started with proxy configuration")
        print("🤖 Бот запущен и готов к работе!")
        application.run_polling()

    except Exception as e:
        logger.critical(f"Critical error: {str(e)}")
        raise

if __name__ == '__main__':
    main()