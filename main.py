import logging
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

# Настройка путей
BASE_DIR = '/var/log/insta-bot'
LOG_FILE = os.path.join(BASE_DIR, 'bot.log')
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация Instagram клиента
cl = Client()
cl.set_proxy(PROXY_URL)
cl.set_device_settings('samsung_galaxy_s10')

def initialize_instagram():
    try:
        logger.info(f"Attempting to login to Instagram as {INSTAGRAM_USERNAME}...")
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        
        # Проверяем логин
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
        
        # Извлекаем media_pk из URL
        media_pk = cl.media_pk_from_url(message)
        
        # Создаем временную директорию
        temp_dir = os.path.join(DOWNLOADS_DIR, f"temp_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(temp_dir, mode=0o755, exist_ok=True)
        
        logger.info(f"Created temp directory: {temp_dir}")
        
        # Случайная задержка перед запросом
        time.sleep(random.uniform(1, 2))
        
        # Скачиваем видео
        video_path = cl.clip_download(media_pk, folder=temp_dir)
        logger.info("Video download completed")
        
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
        # Очистка
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
        # Создаем необходимые директории
        os.makedirs(DOWNLOADS_DIR, mode=0o755, exist_ok=True)
        
        # Инициализируем Instagram
        if not initialize_instagram():
            logger.error("Failed to initialize Instagram")
            return
            
        # Инициализируем бота
        application = Application.builder().token(BOT_TOKEN).build()

        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_reels))
        application.add_error_handler(error_handler)

        # Запускаем бота
        logger.info("Bot started with Instagram API")
        print("🤖 Бот запущен и готов к работе!")
        application.run_polling()

    except Exception as e:
        logger.critical(f"Critical error: {str(e)}")
        raise

if __name__ == '__main__':
    main()