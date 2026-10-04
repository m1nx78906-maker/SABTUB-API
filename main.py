from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os

app = FastAPI(title="Universal Video Downloader API")

# অ্যান্ড্রয়েড অ্যাপ এবং যেকোনো ক্লায়েন্ট থেকে রিকোয়েস্ট অ্যাক্সেস করার অনুমতি
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    url: str

def format_size(bytes_size):
    """বাইট সাইজকে MB-তে কনভার্ট করার হেল্পার ফাংশন"""
    if not bytes_size:
        return "Unknown"
    return f"{round(bytes_size / (1024 * 1024), 2)} MB"

# ১. রেন্ডারকে ঘুম থেকে জাগিয়ে রাখার হোম রাউট (Keep-Alive Ping Endpoint)
@app.get("/")
def home():
    return {
        "status": "online",
        "message": "API is running successfully!"
    }

# ২. মূল ভিডিও অ্যানালাইসিস রাউট
@app.post("/api/extract")
def extract_video_info(request: VideoRequest):
    url = request.url.strip()

    if not url:
        raise HTTPException(status_code=400, detail="দয়া করে একটি সঠিক URL দিন।")

    # yt-dlp কনফিগারেশন (বট ট্র্যাকিং এড়ানোর জন্য সাধারণ ব্রাউজার হেডার সহ)
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            title = info.get('title', 'Video')
            thumbnail = info.get('thumbnail')
            duration = info.get('duration', 0)
            formats_raw = info.get('formats', [])

            # ক. সেরা অডিও স্ট্রিম বের করা (MP3 তৈরির জন্য)
            audio_stream = None
            for f in formats_raw:
                if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                    if not audio_stream or (f.get('abr') or 0) > (audio_stream.get('abr') or 0):
                        audio_stream = {
                            "url": f.get('url'),
                            "ext": f.get('ext', 'm4a'),
                            "bitrate": f"{int(f.get('abr', 128))}kbps",
                            "size": format_size(f.get('filesize') or f.get('filesize_approx'))
                        }

            # খ. ভিডিও ফরম্যাটগুলো ফিল্টার ও গ্রুপিং করা
            video_options = {}
            target_resolutions = [360, 480, 720, 1080, 1440, 2160]

            for f in formats_raw:
                height = f.get('height')
                # শুধু নির্দিষ্ট রেজ্যুলেশনের ভিডিও ফিল্টার করা
                if height in target_resolutions and f.get('vcodec') != 'none':
                    res_key = f"{height}p"

                    if res_key not in video_options:
                        has_audio = f.get('acodec') != 'none'
                        video_options[res_key] = {
                            "quality": res_key,
                            "url": f.get('url'),
                            "ext": f.get('ext', 'mp4'),
                            "size": format_size(f.get('filesize') or f.get('filesize_approx')),
                            "has_audio": has_audio
                        }

            # রেজ্যুলেশন ক্রমানুসারে সাজানো
            sorted_videos = [video_options[k] for k in sorted(video_options.keys(), key=lambda x: int(x.replace('p', '')))]

            return {
                "success": True,
                "title": title,
                "thumbnail": thumbnail,
                "duration_seconds": duration,
                "audio": audio_stream,
                "videos": sorted_videos
            }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ভিডিও প্রসেস করা সম্ভব হয়নি: {str(e)}")
