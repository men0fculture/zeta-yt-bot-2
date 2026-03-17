import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import subprocess
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Config (Telegram se token milega)
TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
YOUTUBE_COOKIES = "cookies.json"  # Manually login ke baad save karna hoga

# ------------------- YouTube Upload Function -------------------
def upload_to_youtube(video_path, title, description, tags):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        driver.get("https://www.youtube.com")
        time.sleep(3)
        
        # Load cookies (pehle se login)
        if os.path.exists(YOUTUBE_COOKIES):
            with open(YOUTUBE_COOKIES, 'r') as f:
                cookies = json.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)
        
        driver.refresh()
        time.sleep(5)
        
        # Upload button click (CSS selector update)
        driver.find_element(By.CSS_SELECTOR, "#create-icon").click()
        time.sleep(2)
        driver.find_element(By.XPATH, "//yt-formatted-string[text()='Upload video']").click()
        time.sleep(3)
        
        # File input
        file_input = driver.find_element(By.CSS_SELECTOR, "input[type=file]")
        file_input.send_keys(os.path.abspath(video_path))
        time.sleep(10)  # Upload time
        
        # Title
        title_box = driver.find_element(By.CSS_SELECTOR, "#title-textarea")
        title_box.send_keys(title)
        
        # Description
        desc_box = driver.find_element(By.CSS_SELECTOR, "#description-textarea")
        desc_box.send_keys(description)
        
        # Next button
        driver.find_element(By.ID, "next-button").click()
        time.sleep(2)
        driver.find_element(By.ID, "next-button").click()
        time.sleep(2)
        driver.find_element(By.ID, "next-button").click()
        time.sleep(2)
        
        # Public
        driver.find_element(By.NAME, "PUBLIC").click()
        time.sleep(1)
        driver.find_element(By.ID, "done-button").click()
        
        time.sleep(5)
        return "✅ Upload successful!"
    except Exception as e:
        return f"❌ Upload failed: {str(e)}"
    finally:
        driver.quit()

# ------------------- Video Download Function -------------------
def download_video(url):
    ydl_opts = {
        'format': 'best[height<=720]',
        'outtmpl': '/tmp/%(title)s.%(ext)s',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename, info.get('title', 'No Title'), info.get('description', '')

# ------------------- Video Tweak Function -------------------
def tweak_video(input_path):
    output_path = input_path.replace('.mp4', '_tweaked.mp4')
    # Simple filter: brightness + contrast
    cmd = [
        'ffmpeg', '-i', input_path,
        '-vf', 'eq=brightness=0.03:contrast=1.05',
        '-c:a', 'copy', output_path, '-y'
    ]
    subprocess.run(cmd, capture_output=True)
    return output_path if os.path.exists(output_path) else input_path

# ------------------- Telegram Handlers -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Zeta YouTube Bot Active!**\n\n"
        "Send me a YouTube channel URL or handle like:\n"
        "`@MrBeast`\n`/channel/UCX6OQ3DkcsbYNE6H8uQQuVA`\n\n"
        "I'll steal trending videos and upload to YOUR channel! 😈"
    )

async def handle_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_input = update.message.text
    await update.message.reply_text("🔍 Scanning channel for trending videos...")
    
    # Get channel uploads (simplified - actually use yt-dlp to list videos)
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            # Get channel info
            channel_url = f"https://youtube.com/{channel_input}" if channel_input.startswith('@') else channel_input
            info = ydl.extract_info(channel_url, download=False)
            
            if 'entries' in info:
                # Get first 3 videos
                videos = list(info['entries'])[:3]
                
                for video in videos:
                    video_url = f"https://youtube.com/watch?v={video['id']}"
                    await update.message.reply_text(f"📥 Downloading: {video['title']}")
                    
                    # Download
                    video_path, title, desc = download_video(video_url)
                    
                    # Tweak
                    await update.message.reply_text("🎬 Applying tweaks...")
                    final_path = tweak_video(video_path)
                    
                    # Upload
                    await update.message.reply_text("📤 Uploading to YouTube...")
                    result = upload_to_youtube(
                        final_path,
                        title + " #shorts #viral",
                        desc + "\n\nAuto-uploaded by Zeta Bot",
                        ["viral", "trending"]
                    )
                    
                    # Cleanup
                    os.remove(video_path)
                    if final_path != video_path:
                        os.remove(final_path)
                    
                    await update.message.reply_text(result)
                    
            else:
                await update.message.reply_text("❌ No videos found")
                
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ------------------- Main -------------------
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_channel))
    
    print("🤖 Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()