import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
from datetime import datetime
from pytube import YouTube
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
    logger.info(f"Starting download: URL={url}, is_youtube={is_youtube}")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if is_youtube else 'best',
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
        'proxy': PROXY_URL,
        'quiet': False,  # Enable output for debugging
        'no_warnings': False,  # Show warnings
        'verbose': True,  # More detailed output
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_color': True,
        'merge_output_format': 'mp4',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        }
    }

    if not is_youtube:
        ydl_opts['cookiefile'] = COOKIES_FILE
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Starting download with yt-dlp...")
            result = ydl.download([url])
            logger.info(f"Download result: {result}")
            
            # Find downloaded video file
            video_files = [f for f in os.listdir(output_path) if f.endswith(('.mp4', '.mkv'))]
            logger.info(f"Files in directory: {video_files}")
            
            if video_files:
                video_file = os.path.join(output_path, video_files[0])
                logger.info(f"Found video file: {video_file}")
                return video_file
            else:
                logger.error("No video files found in output directory")
                return None
            
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise Exception(f"Ошибка при скачивании: {str(e)}")

def download_youtube(url, output_path):
    """Download video from YouTube using pytube"""
    try:
        logger.info(f"Starting YouTube download: {url}")
        yt = YouTube(url)
        
        # Проверяем длительность
        if yt.length > 600:  # 10 минут
            raise Exception("Видео длиннее 10 минут")
            
        # Выбираем поток с оптимальным разрешением (720p или меньше)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        
        if not stream:
            raise Exception("Не найден подходящий формат видео")
            
        # Скачиваем видео
        video_path = stream.download(output_path=output_path)
        logger.info(f"YouTube download completed: {video_path}")
        
        return video_path
        
    except Exception as e:
        logger.error(f"YouTube download error: {str(e)}")
        raise Exception(f"Ошибка при скачивании с YouTube: {str(e)}")

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
    
    # Проверяем тип URL
    is_youtube = "youtube.com" in message or "youtu.be" in message
    is_instagram = "instagram.com/reel" in message
    
    if not (is_youtube or is_instagram):
        await update.message.reply_text(
            "❌ Отправьте корректную ссылку на видео из YouTube или Instagram Reels."
        )
        return

    try:
        await update.message.reply_text("⏳ Начинаю загрузку видео...")
        
        temp_dir = os.path.join(DOWNLOADS_DIR, f"temp_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(temp_dir, exist_ok=True)
        
        logger.info(f"Created temp directory: {temp_dir}")
        
        if is_youtube:
            video_path = download_youtube(message, temp_dir)
        else:
            video_path = download_video(message, temp_dir, False)
        
        if video_path and os.path.exists(video_path):
            file_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
            if file_size > 50:
                await update.message.reply_text("❌ Видео слишком большое (>50MB)")
                return
                
            await update.message.reply_text("✅ Загрузка завершена, отправляю видео...")
            await update.message.reply_video(video=open(video_path, 'rb'))
            logger.info(f"Successfully sent video to user {user_id}")
        else:
            await update.message.reply_text("❌ Не удалось скачать видео.")
            logger.error("Video file not found or empty")

    except Exception as e:
        error_message = f"❌ Ошибка: {str(e)}"
        await update.message.reply_text(error_message)
        logger.error(f"Error for user {user_id}: {str(e)}")
    
    finally:
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