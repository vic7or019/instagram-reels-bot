from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import instaloader
import os
import re
from datetime import datetime

# Инициализация Instagram loader
L = instaloader.Instaloader()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Отправь мне ссылку на Reels из Instagram, и я скачаю его для тебя."
    )

async def download_reels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    
    if "instagram.com/reel" not in message:
        await update.message.reply_text("❌ Пожалуйста, отправьте корректную ссылку на Instagram Reels.")
        return

    try:
        await update.message.reply_text("⏳ Начинаю загрузку Reels...")
        
        # Извлекаем ID видео из URL
        shortcode = re.search(r"/reel/([^/]+)/", message).group(1)
        
        # Создаем временную директорию с текущим timestamp
        temp_dir = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(temp_dir, exist_ok=True)
        
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
        else:
            await update.message.reply_text("❌ Не удалось найти видео.")

    except Exception as e:
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
    
    finally:
        # Очищаем временные файлы
        if 'temp_dir' in locals():
            for file in os.listdir(temp_dir):
                os.remove(f"{temp_dir}/{file}")
            os.rmdir(temp_dir)

def main():
    # Инициализируем бота
    application = Application.builder().token('7881925612:AAE1-Ld6IcfloGYvkEXt5lgWTutlEqW_-UU').build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_reels))

    # Запускаем бота
    print("🤖 Бот запущен и готов к работе!")
    application.run_polling()

if __name__ == '__main__':
    main()