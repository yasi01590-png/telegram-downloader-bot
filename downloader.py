import os
import asyncio
import aiohttp
import aiofiles
import subprocess
from urllib.parse import urlparse, unquote
import time

class Downloader:
    def __init__(self, download_path="./downloads"):
        self.download_path = download_path
        os.makedirs(download_path, exist_ok=True)
    
    def get_filename_from_url(self, url):
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        filename = unquote(filename)
        if not filename or '.' not in filename:
            filename = f"file_{int(time.time())}"
        return filename
    
    def is_m3u8(self, url):
        return '.m3u8' in url.lower()
    
    async def get_file_size(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, allow_redirects=True) as response:
                    size = response.headers.get('Content-Length', 0)
                    return int(size)
        except:
            return 0
    
    async def download_direct(self, url, progress_callback=None):
        filename = self.get_filename_from_url(url)
        filepath = os.path.join(self.download_path, filename)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"خطا در دانلود: {response.status}")
                
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                
                async with aiofiles.open(filepath, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        await f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            await progress_callback(downloaded, total_size, progress)
        
        return filepath, filename
    
    async def download_m3u8(self, url, progress_callback=None):
        timestamp = int(time.time())
        output_filename = f"video_{timestamp}.mp4"
        output_path = os.path.join(self.download_path, output_filename)
        
        command = [
            'ffmpeg', '-i', url,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-movflags', '+faststart',
            '-y', output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            return await self.download_with_ytdlp(url)
        
        return output_path, output_filename
    
    async def download_with_ytdlp(self, url):
        timestamp = int(time.time())
        output_template = os.path.join(self.download_path, f"%(title)s_{timestamp}.%(ext)s")
        
        command = [
            'yt-dlp',
            '--no-warnings',
            '-f', 'best',
            '-o', output_template,
            '--print', 'after_move:filepath',
            url
        ]
        
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"خطا در دانلود: {stderr.decode()}")
        
        filepath = stdout.decode().strip()
        filename = os.path.basename(filepath)
        
        return filepath, filename
    
    async def download(self, url, progress_callback=None):
        try:
            if self.is_m3u8(url):
                return await self.download_m3u8(url, progress_callback)
            else:
                try:
                    return await self.download_direct(url, progress_callback)
                except:
                    return await self.download_with_ytdlp(url)
        except Exception as e:
            raise Exception(f"خطا در دانلود: {str(e)}")
    
    def cleanup(self, filepath):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass
