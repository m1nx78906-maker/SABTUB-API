from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="SabTube Ultimate Video Extractor")

# সব ধরনের ওয়েবসাইট ও অ্যাপ থেকে রিকোয়েস্ট অ্যালাউ করা
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
    """বাইট সাইজকে MB-তে কনভার্ট করার ফাংশন"""
    if not bytes_size:
        return "Unknown"
    return f"{round(bytes_size / (1024 * 1024), 2)} MB"

@app.get("/")
def home():
    return {"status": "online", "message": "SabTube Backend is Running Perfectly!"}

@app.post("/api/extract")
def extract_video_info(request: VideoRequest):
    url = request.url.strip()

    if not url:
        raise HTTPException(status_code=400, detail="দয়া করে একটি সঠিক URL দিন।")

    # yt-dlp এর স্মার্ট কনফিগারেশন (IP Block / Bot Detection এড়ানোর জন্য)
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Fetch-Mode': 'navigate',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # মেটাডাটা এক্সট্র্যাক্ট করা
            info = ydl.extract_info(url, download=False)

            # মূল ইনফরমেশন (টাইটেল, ডেসক্রিপশন, থাম্বনেইল)
            title = info.get('title', 'SabTube Video')
            # ডেসক্রিপশন অনেক বড় হলে প্রথম ৫০০ অক্ষর নেবে
            raw_description = info.get('description') or 'No description available.'
            description = raw_description[:500] + ('...' if len(raw_description) > 500 else '')
            thumbnail = info.get('thumbnail')
            duration = info.get('duration', 0)
            formats_raw = info.get('formats', [])

            audio_data = None
            video_options = {}

            # ১. সেরা কোয়ালিটির অডিও এক্সট্র্যাক্ট করা
            for f in formats_raw:
                if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                    # যদি আগের থেকে ভালো বিটরেট পাওয়া যায়, তবে আপডেট করবে
                    current_bitrate = f.get('abr') or 0
                    saved_bitrate = int(audio_data['bitrate'].replace('kbps', '')) if audio_data else 0
                    
                    if not audio_data or current_bitrate > saved_bitrate:
                        audio_data = {
                            "category": "Audio / Music",
                            "url": f.get('url'),
                            "ext": f.get('ext', 'm4a'),
                            "bitrate": f"{int(current_bitrate)}kbps" if current_bitrate else "Auto",
                            "size": format_size(f.get('filesize') or f.get('filesize_approx'))
                        }

            # ২. ভিডিও এক্সট্র্যাক্ট করা (Reels, TikTok, YouTube সব সাপোর্ট করবে)
            for f in formats_raw:
                if f.get('vcodec') != 'none':
                    # ভার্টিক্যাল (রিলস) এবং হরাইজোন্টাল ভিডিওর সাইজ বোঝার লজিক
                    height = f.get('height') or 0
                    width = f.get('width') or 0
                    res_value = max(height, width) # যেটা বড় সেটাই রেজ্যুলেশন হিসেবে ধরবে

                    if res_value >= 144: # খুব বাজে কোয়ালিটি বাদ দেওয়া হলো
                        # SD, HD, FHD ক্যাটাগরি তৈরি
                        if res_value >= 1080:
                            category = "FHD"
                        elif res_value >= 720:
                            category = "HD"
                        else:
                            category = "SD"
                        
                        res_key = f"{res_value}p"

                        # একই রেজ্যুলেশনের ভিডিও আগে না থাকলে বা নতুনটাতে অডিও থাকলে সেটা নেবে
                        if res_key not in video_options or (f.get('acodec') != 'none' and not video_options[res_key]['has_audio']):
                            video_options[res_key] = {
                                "quality": res_key,
                                "category": category,
                                "url": f.get('url'),
                                "ext": f.get('ext', 'mp4'),
                                "size": format_size(f.get('filesize') or f.get('filesize_approx')),
                                "has_audio": f.get('acodec') != 'none'
                            }

            # ভিডিওগুলোকে রেজ্যুলেশন অনুযায়ী ছোট থেকে বড়তে সাজানো
            sorted_videos = [video_options[k] for k in sorted(video_options.keys(), key=lambda x: int(x.replace('p', '')))]

            return {
                "success": True,
                "title": title,
                "description": description,
                "thumbnail": thumbnail,
                "duration_seconds": duration,
                "audio": audio_data,
                "videos": sorted_videos
            }

    except Exception as e:
        error_msg = str(e)
        # যদি ইউটিউব বা ফেসবুক ব্লক করে, তবে সেই মেসেজটি সুন্দর করে পাঠাবে
        raise HTTPException(status_code=400, detail=f"ভিডিও প্রসেস করা সম্ভব হয়নি। লিংকটি সঠিক কিনা চেক করুন। Error: {error_msg}")
