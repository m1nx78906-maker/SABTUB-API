from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="SabTube Ultimate Video Extractor")

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

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            title = info.get('title', 'SabTube Video')
            raw_description = info.get('description') or 'No description available.'
            description = raw_description[:500] + ('...' if len(raw_description) > 500 else '')
            thumbnail = info.get('thumbnail')
            duration = info.get('duration', 0)
            formats_raw = info.get('formats', [])

            audio_data = None
            video_options = {}

            # ১. সেরা অডিও বের করা
            for f in formats_raw:
                acodec = str(f.get('acodec')).lower()
                vcodec = str(f.get('vcodec')).lower()
                if vcodec == 'none' and acodec != 'none':
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

            # ২. ভিডিও বের করা
            for f in formats_raw:
                vcodec = str(f.get('vcodec')).lower()
                acodec = str(f.get('acodec')).lower()
                
                has_video = vcodec != 'none'
                has_audio = acodec != 'none'

                if has_video:
                    res = max(f.get('height') or 0, f.get('width') or 0)
                    if res > 0 and res < 144:
                        continue
                        
                    res_key = f"{res}p" if res > 0 else "Normal"
                    category = "FHD" if res >= 1080 else ("HD" if res >= 720 else "SD")

                    # যদি সাউন্ড থাকে, তবেই লিস্টে তুলবে
                    if res_key not in video_options or (has_audio and not video_options[res_key]['has_audio']):
                        video_options[res_key] = {
                            "quality": res_key,
                            "category": category,
                            "url": f.get('url'),
                            "ext": f.get('ext', 'mp4'),
                            "size": format_size(f.get('filesize') or f.get('filesize_approx')),
                            "has_audio": has_audio
                        }

            # মিউট ভিডিও বাদ দেওয়া
            final_videos = [v for v in video_options.values() if v['has_audio']]

            # ৩. 🟢 দ্য আল্টিমেট ফেলব্যাক (যে কারণে আপনার লিস্ট ফাঁকা এসেছিল) 🟢
            # যদি ফিল্টার করার পর লিস্ট ফাঁকা হয়ে যায়, তবে মাস্টার ভিডিওটি দিয়ে দেবে!
            if not final_videos:
                fallback_url = info.get('url')
                if fallback_url:
                    final_videos.append({
                        "quality": "Best Quality",
                        "category": "HD/SD",
                        "url": fallback_url,
                        "ext": info.get('ext', 'mp4'),
                        "size": "Unknown",
                        "has_audio": True # মাস্টার ফাইলে সাউন্ড ১০০% থাকবে
                    })

            # সাইজ অনুযায়ী সাজানো
            def sort_key(v):
                q = v['quality'].replace('p', '')
                return int(q) if q.isdigit() else 0
                
            sorted_videos = sorted(final_videos, key=sort_key)

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
        raise HTTPException(status_code=400, detail=f"ভিডিও প্রসেস করা সম্ভব হয়নি। Error: {str(e)}")
