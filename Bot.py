import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import subprocess
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json

# ------------------- Config -------------------
TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
YOUTUBE_API_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = "client_secrets.json"  # Google Cloud se download karna hoga

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------- YouTube Auth -------------------
def get_authenticated_service():
    credentials = None
    token_file = "token.json"
    
    if os.path.exists(token_file):
        credentials = Credentials.from_authorized_user_file(token_file, YOUTUBE_API_SCOPES)
    
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, YOUTUBE_API_SCOPES)
            credentials = flow.run_local_server(port=0)
        
        with open(token_file, 'w') as token:
            token.write(credentials.to_json())
    
    return build("youtube", "v3", credentials=credentials)

# ------------------- YouTube Upload Function -------------------
def upload_to_youtube(video_path, title, description, tags, privacy_status="public"):
    try:
        youtube = get_authenticated_service()
        
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "22"  # 22 = People & Blogs
            },
            "status": {
                "privacyStatus": privacy_status
            }
        }
        
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        response = request.execute()
        return f"✅ Uploaded: https://youtu.be/{response['id']}"
    
    except Exception as e:
        return f"❌ Upload failed: {str(e)}"

# ------------------- Video Download Function -------------------
def download_video(url):
    ydl_opts = {
        'format': 'best[height<=720]',
        'outtmpl': '/tmp/%(title)s.%(ext)s',
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename, info.get('title', 'No Title'), info.get('description', '')

# ------------------- Video Tweak Function (Optional) -------------------
def tweak_video(input_path):
    output_path = input_path.replace('.mp4', '_tweaked.mp4')
    # Simple brightness adjustment
    cmd = [
        'ffmpeg', '-i', input_path,
        '-vf', 'eq=brightness=0.03',
        '-c:a', 'copy', output_path, '-y'
    ]
    subprocess.run(cmd, capture_output=True)
    return output_path if os.path.exists(output_path) else input_path

# ------------------- Telegram Handlers -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Zeta YouTube Bot Active!**\n\n"
        "Send me:\n"
        "• A YouTube **video link** to upload it to your channel\n"
        "• A **channel URL/handle** (like @MrBeast) to steal videos\n\n"
        "Powered by YouTube API"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text("⏳ Processing...")
    
    # Check if it's a channel or video
    if "channel" in text or "@" in text or "/c/" in text:
        await handle_channel(update, text)
    else:
        await handle_video(update, text)

async def handle_video(update: Update, url: str):
    try:
        await update.message.reply_text("📥 Downloading video...")
        video_path, title, desc = download_video(url)
        
        await update.message.reply_text("🎬 Applying tweaks...")
        final_path = tweak_video(video_path)
        
        await update.message.reply_text("📤 Uploading to YouTube...")
        result = upload_to_youtube(
            final_path,
            title,
            desc + "\n\nAuto-uploaded by Zeta Bot",
            ["viral", "trending", "shorts"]
        )
        
        # Cleanup
        os.remove(video_path)
        if final_path != video_path:
            os.remove(final_path)
        
        await update.message.reply_text(result)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def handle_channel(update: Update, channel_input: str):
    await update.message.reply_text("🔍 Fetching latest videos from channel...")
    
    try:
        # Get channel uploads
        if not channel_input.startswith("http"):
            channel_input = f"https://youtube.com/{channel_input}"
        
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(channel_input, download=False)
            
            if 'entries' in info:
                videos = list(info['entries'])[:3]  # Get first 3 videos
                
                for video in videos:
                    video_url = f"https://youtube.com/watch?v={video['id']}"
                    await update.message.reply_text(f"➡️ Processing: {video['title']}")
                    await handle_video(update, video_url)
                    await asyncio.sleep(2)  # Avoid quota issues
            else:
                await update.message.reply_text("❌ No videos found")
                
    except Exception as e:
        await update.message.reply_text(f"❌ Channel error: {str(e)}")

# ------------------- Main -------------------
def main():
    if TOKEN == "YOUR_TOKEN_HERE":
        print("❌ TELEGRAM_TOKEN not set!")
        return
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot started successfully!")
    app.run_polling()

if __name__ == "__main__":
    main()