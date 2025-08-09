import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import instaloader
import os
import re
from datetime import datetime
from config import BOT_TOKEN, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
from instaloader.exceptions import TwoFactorAuthRequiredException, ConnectionException, BadCredentialsException

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
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
    post_metadata_txt_pattern=''
)
is_logged_in = False

# Создание временной директории
TEMP_DIR = 'downloads'
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

def instagram_login():
    global is_logged_in
    if is_logged_in:
        return True
        
    try:
        L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        is_logged_in = True
        logger.info("Successfully logged in to Instagram")
        return True
    except TwoFactorAuthRequiredException:
        logger.error("2FA is enabled. Please disable it for bot account")
        return False
    except BadCredentialsException:
        logger.error("Invalid Instagram credentials")
        return False
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
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
        temp_dir = f"{TEMP_DIR}/temp_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(temp_dir, exist_ok=True)
        
        logger.info(f"Created temp directory: {temp_dir}")
        
        # Получаем пост
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Скачиваем видео
        L.download_post(post, target=temp_dir)
        
        # Находим видео файл
        video_file = None
        for file in os.listdir(temp_dir):
            if file.endswith('.mp4'):
                video_file = f"{temp_dir}/{file}"
                break
        
        if video_file:
            # Отправляем видео
            await update.message.reply_text("✅ Загрузка завершена, отправляю видео...")
            await update.message.reply_video(video=open(video_file, 'rb'))
            logger.info(f"Successfully sent video to user {user_id}")
        else:
            await update.message.reply_text("❌ Не удалось найти видео.")
            logger.error(f"Video file not found for user {user_id}")

    except ConnectionException:
        is_logged_in = False
        await update.message.reply_text("❌ Ошибка подключения к Instagram. Попробуйте позже.")
        logger.error("Instagram connection error")
    except Exception as e:
        error_message = f"❌ Произошла ошибка: {str(e)}"
        await update.message.reply_text(error_message)
        logger.error(f"Error for user {user_id}: {str(e)}")
    
    finally:
        # Очищаем временные файлы
        try:
            if 'temp_dir' in locals():
                for file in os.listdir(temp_dir):
                    os.remove(f"{temp_dir}/{file}")
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