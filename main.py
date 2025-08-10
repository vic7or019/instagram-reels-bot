import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
from datetime import datetime
import yt_dlp
from config import BOT_TOKEN, PROXY_URL, CHANNEL_ID

# Path configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'bot.log')
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads')
COOKIES_FILE = os.path.join(BASE_DIR, 'cookies.txt')

# Create directories
for directory in [LOG_DIR, DOWNLOADS_DIR]:
    os.makedirs(directory, exist_ok=True)

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

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверка подписки пользователя на канал"""
    try:
        user_id = update.effective_user.id
        chat_member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        
        if chat_member.status in ['member', 'administrator', 'creator']:
            return True
            
        await update.message.reply_text(
            "Для того чтобы скачивать видео подпишитесь на канал @zabugor_pay"
        )
        return False
        
    except Exception as e:
        logger.error(f"Error checking subscription: {str(e)}")
        await update.message.reply_text(
            "Для того чтобы скачивать видео подпишитесь на канал @zabugor_pay"
        )
        return False

def download_video(url, output_path, is_youtube=False):
    """Download video using yt-dlp"""
    ydl_opts = {
        'format': 'best' if is_youtube else None,
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
        'proxy': PROXY_URL,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_color': True,
    }
    
    if not is_youtube:
        ydl_opts['cookiefile'] = COOKIES_FILE
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.download([url])
            
            # Find downloaded video file
            video_file = None
            for file in os.listdir(output_path):
                if file.endswith(('.mp4', '.mkv')):
                    video_file = os.path.join(output_path, file)
                    break
                    
            return video_file
            
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    if not await check_subscription(update, context):
        return
        
    await update.message.reply_text(
        "👋 Привет! Я могу скачивать видео из:\n"
        "• Instagram Reels\n"
        "• YouTube\n\n"
        "Просто отправь мне ссылку на видео!"
    )
    logger.info(f"Start command used by user {update.effective_user.id}")

async def process_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ссылок на видео"""
    if not await check_subscription(update, context):
        return
        
    user_id = update.effective_user.id
    message = update.message.text
    
    logger.info(f"Received request from user {user_id}: {message}")
    
    # Check URL type
    is_youtube = "youtube.com" in message or "youtu.be" in message
    is_instagram = "instagram.com/reel" in message
    
    if not (is_youtube or is_instagram):
        await update.message.reply_text(
            "❌ Пожалуйста, отправьте корректную ссылку на видео из YouTube или Instagram Reels."
        )
        return

    try:
        await update.message.reply_text("⏳ Начинаю загрузку видео...")
        
        temp_dir = os.path.join(DOWNLOADS_DIR, f"temp_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(temp_dir, exist_ok=True)
        
        logger.info(f"Created temp directory: {temp_dir}")
        
        video_path = download_video(message, temp_dir, is_youtube)
        
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

def main():
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_video))

        logger.info("Bot started")
        print("🤖 Бот запущен и готов к работе!")
        application.run_polling()

    except Exception as e:
        logger.critical(f"Critical error: {str(e)}")
        raise

if __name__ == '__main__':
    main()