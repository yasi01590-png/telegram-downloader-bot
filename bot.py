import os
import asyncio
import time
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import Message
from config import Config
from downloader import Downloader

# --- Web Server for Health Check ---
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.environ.get('PORT', 8000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

# Start health server
Thread(target=run_health_server, daemon=True).start()

# --- Telegram Bot ---
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
    await message.reply_text(
        "🎉 **به ربات دانلودر خوش آمدید!**\n\n"
        "📥 این ربات می‌تواند:\n"
        "• لینک‌های مستقیم را دانلود کند\n"
        "• فایل‌های m3u8 را به mp4 تبدیل کند\n\n"
        "📌 **لینک خود را بفرستید!**\n\n"
        "⚠️ حداکثر حجم: 2GB"
    )

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    await message.reply_text(
        "📚 **راهنما**\n\n"
        "1️⃣ لینک مستقیم بفرستید\n"
        "2️⃣ لینک m3u8 بفرستید\n\n"
        "ربات فایل را دانلود و ارسال می‌کند ✅"
    )

@app.on_message(filters.text & filters.private & ~filters.command(["start", "help"]))
async def handle_url(client: Client, message: Message):
    url = message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await message.reply_text("❌ لینک معتبر نیست!")
        return
    
    user_id = message.from_user.id
    if user_id in active_downloads:
        await message.reply_text("⏳ صبر کنید...")
        return
    
    active_downloads[user_id] = True
    status_msg = await message.reply_text("🔍 در حال بررسی...")
    
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
        
        progress_bar = create_progress_bar(progress)
        
        try:
            await status_msg.edit_text(
                f"📥 **دانلود...**\n\n"
                f"{progress_bar} {progress:.1f}%\n\n"
                f"📦 {format_size(downloaded)} / {format_size(total)}\n"
                f"⚡ {format_size(speed)}/s"
            )
        except:
            pass
    
    try:
        await status_msg.edit_text("📥 در حال دانلود...")
        filepath, filename = await downloader.download(url, progress_callback)
        
        file_size = os.path.getsize(filepath)
        
        if file_size > Config.MAX_FILE_SIZE:
            await status_msg.edit_text(f"❌ حجم بیشتر از 2GB است!")
            downloader.cleanup(filepath)
            del active_downloads[user_id]
            return
        
        await status_msg.edit_text("📤 در حال ارسال...")
        
        ext = os.path.splitext(filename)[1].lower()
        
        if ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']:
            await client.send_video(
                message.chat.id,
                filepath,
                caption=f"📹 {filename}\n📦 {format_size(file_size)}",
                supports_streaming=True
            )
        elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
            await client.send_audio(
                message.chat.id,
                filepath,
                caption=f"🎵 {filename}\n📦 {format_size(file_size)}"
            )
        else:
            await client.send_document(
                message.chat.id,
                filepath,
                caption=f"📁 {filename}\n📦 {format_size(file_size)}"
            )
        
        total_time = time.time() - start_time
        await status_msg.edit_text(
            f"✅ **کامل شد!**\n\n"
            f"📁 {filename}\n"
            f"📦 {format_size(file_size)}\n"
            f"⏱ {format_time(total_time)}"
        )
        
    except Exception as e:
        await status_msg.edit_text(f"❌ خطا:\n{str(e)}")
    
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
