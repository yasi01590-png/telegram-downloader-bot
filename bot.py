import os
import asyncio
import time
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from config import Config
from downloader import Downloader

app = Client(
    "downloader_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

downloader = Downloader(Config.DOWNLOAD_PATH)
active_downloads = {}

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

def format_time(seconds):
    if seconds < 60:
        return f"{int(seconds)} ثانیه"
    elif seconds < 3600:
        return f"{int(seconds // 60)} دقیقه"
    else:
        return f"{int(seconds // 3600)} ساعت"

def create_progress_bar(progress, length=20):
    filled = int(length * progress / 100)
    bar = '█' * filled + '░' * (length - filled)
    return bar

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    welcome_text = """
🎉 **به ربات دانلودر خوش آمدید!**

📥 این ربات می‌تواند:
• لینک‌های مستقیم را دانلود کند
• فایل‌های m3u8 را به mp4 تبدیل کند
• ویدیوها را از سایت‌های مختلف دانلود کند

📌 **نحوه استفاده:**
فقط لینک را برای من بفرستید!

🔧 **دستورات:**
/start - شروع
/help - راهنما
"""
    await message.reply_text(welcome_text)

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    help_text = """
📚 **راهنمای استفاده**

1️⃣ **دانلود فایل مستقیم:**
   لینک مستقیم فایل را بفرستید

2️⃣ **دانلود m3u8:**
   لینک m3u8 را بفرستید، ربات آن را به mp4 تبدیل می‌کند

⚠️ **نکات:**
• صبور باشید
• حداکثر حجم: 2 گیگابایت
"""
    await message.reply_text(help_text)

@app.on_message(filters.text & filters.private & ~filters.command(["start", "help"]))
async def handle_url(client: Client, message: Message):
    url = message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await message.reply_text("❌ لطفاً یک لینک معتبر ارسال کنید!")
        return
    
    user_id = message.from_user.id
    if user_id in active_downloads:
        await message.reply_text("⏳ شما یک دانلود فعال دارید. لطفاً صبر کنید...")
        return
    
    active_downloads[user_id] = True
    status_msg = await message.reply_text("🔍 در حال بررسی لینک...")
    
    start_time = time.time()
    last_update = 0
    filepath = None
    
    async def progress_callback(downloaded, total, progress):
        nonlocal last_update
        current_time = time.time()
        
        if current_time - last_update < 3:
            return
        last_update = current_time
        
        elapsed = current_time - start_time
        speed = downloaded / elapsed if elapsed > 0 else 0
        eta = (total - downloaded) / speed if speed > 0 else 0
        
        progress_bar = create_progress_bar(progress)
        
        progress_text = f"""
📥 **در حال دانلود...**

{progress_bar} {progress:.1f}%

📦 حجم: {format_size(downloaded)} / {format_size(total)}
⚡ سرعت: {format_size(speed)}/s
⏱ باقی‌مانده: {format_time(eta)}
"""
        try:
            await status_msg.edit_text(progress_text)
        except:
            pass
    
    try:
        await status_msg.edit_text("📥 در حال دانلود...")
        filepath, filename = await downloader.download(url, progress_callback)
        
        file_size = os.path.getsize(filepath)
        
        if file_size > Config.MAX_FILE_SIZE:
            await status_msg.edit_text(f"❌ حجم فایل ({format_size(file_size)}) بیشتر از 2GB است!")
            downloader.cleanup(filepath)
            del active_downloads[user_id]
            return
        
        await status_msg.edit_text("📤 در حال آپلود به تلگرام...")
        
        ext = os.path.splitext(filename)[1].lower()
        
        if ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']:
            await client.send_video(
                message.chat.id,
                filepath,
                caption=f"📹 {filename}\n📦 حجم: {format_size(file_size)}",
                supports_streaming=True
            )
        elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
            await client.send_audio(
                message.chat.id,
                filepath,
                caption=f"🎵 {filename}\n📦 حجم: {format_size(file_size)}"
            )
        else:
            await client.send_document(
                message.chat.id,
                filepath,
                caption=f"📁 {filename}\n📦 حجم: {format_size(file_size)}"
            )
        
        total_time = time.time() - start_time
        await status_msg.edit_text(
            f"✅ **دانلود و ارسال کامل شد!**\n\n"
            f"📁 نام: {filename}\n"
            f"📦 حجم: {format_size(file_size)}\n"
            f"⏱ زمان: {format_time(total_time)}"
        )
        
    except Exception as e:
        await status_msg.edit_text(f"❌ **خطا:**\n`{str(e)}`")
    
    finally:
        try:
            if filepath:
                downloader.cleanup(filepath)
        except:
            pass
        
        if user_id in active_downloads:
            del active_downloads[user_id]

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
