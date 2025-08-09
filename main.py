import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import instaloader
import os
import re
from datetime import datetime
import time
import random
from config import BOT_TOKEN, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
from instaloader.exceptions import TwoFactorAuthRequiredException, ConnectionException, BadCredentialsException

# Настройка путей
LOG_DIR = '/var/log/insta-bot'
LOG_FILE = os.path.join(LOG_DIR, 'bot.log')
DOWNLOADS_DIR = os.path.join(LOG_DIR, 'downloads')

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

# Инициализация Instagram loader с настройками
L = instaloader.Instaloader(
    download_videos=True,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    compress_json=False,
    post_metadata_txt_pattern='',
    user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 12_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 105.0.0.11.118 (iPhone11,8; iOS 12_3_1; en_US; en-US; scale=2.00; 828x1792; 165586599)'
)
is_logged_in = False

# Создание необходимых директорий
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def instagram_login():
    global is_logged_in
    if is_logged_in:
        return True
        
    try:
        logger.info(f"Attempting to login as {INSTAGRAM_USERNAME}")
        L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        is_logged_in = True
        logger.info("Successfully logged in to Instagram")
        
        # Проверка статуса логина
        if L.context.is_logged_in:
            logger.info("Login verification successful")
        else:
            logger.error("Login seems successful but verification failed")
            is_logged_in = False
            
        return is_logged_in
    except TwoFactorAuthRequiredException:
        logger.error("2FA is enabled. Please disable it for bot account")
        return False
    except BadCredentialsException:
        logger.error("Invalid Instagram credentials")
        return False
    except Exception as e:
        logger.error(f"Login failed with detailed error: {str(e)}")
        is_logged_in = False
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
    global is_logged_in
    user_id = update.effective_user.id
    message = update.message.text
    
    logger.info(f"Received request from user {user_id}: {message}")
    
    if "instagram.com/reel" not in message:
        await update.message.reply_text("❌ Пожалуйста, отправьте корректную ссылку на Instagram Reels.")
        return

    try:
        # Проверяем авторизацию только если не авторизованы
        if not is_logged_in and not instagram_login():
            await update.message.reply_text("❌ Ошибка авторизации в Instagram. Попробуйте позже.")
            return

        await update.message.reply_text("⏳ Начинаю загрузку Reels...")
        
        # Извлекаем ID видео из URL
        shortcode = re.search(r"/reel/([^/]+)/", message).group(1)
        
        # Создаем временную директорию для этой загрузки
        temp_dir = os.path.join(DOWNLOADS_DIR, f"temp_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(temp_dir, exist_ok=True)
        
        logger.info(f"Created temp directory: {temp_dir}")
        
        # Добавляем случайную задержку перед запросом
        time.sleep(random.uniform(2, 4))
        
        # Получаем пост
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        logger.info(f"Successfully retrieved post information for shortcode: {shortcode}")
        
        # Скачиваем видео
        L.download_post(post, target=temp_dir)
        logger.info("Post download completed")
        
        # Находим видео файл
        video_file = None
        for file in os.listdir(temp_dir):
            if file.endswith('.mp4'):
                video_file = os.path.join(temp_dir, file)
                break
        
        if video_file:
            # Отправляем видео
            await update.message.reply_text("✅ Загрузка завершена, отправляю видео...")
            await update.message.reply_video(video=open(video_file, 'rb'))
            logger.info(f"Successfully sent video to user {user_id}")
        else:
            await update.message.reply_text("❌ Не удалось найти видео.")
            logger.error(f"Video file not found for user {user_id}")

    except ConnectionException as ce:
        is_logged_in = False
        logger.error(f"Connection error: {str(ce)}")
        await update.message.reply_text("❌ Ошибка подключения к Instagram. Попробуйте позже.")
    except Exception as e:
        error_message = f"❌ Произошла ошибка: {str(e)}"
        await update.message.reply_text(error_message)
        logger.error(f"Error for user {user_id}: {str(e)}")
    
    finally:
        # Очищаем временные файлы
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
        # Проверяем первичную авторизацию
        if not instagram_login():
            logger.error("Initial Instagram login failed")
            return

        # Инициализируем бота
        application = Application.builder().token(BOT_TOKEN).build()

        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_reels))
        application.add_error_handler(error_handler)

        # Запускаем бота
        logger.info("Bot started")
        print("🤖 Бот запущен и готов к работе!")
        application.run_polling()

    except Exception as e:
        logger.critical(f"Critical error: {str(e)}")
        raise

if __name__ == '__main__':
    main()