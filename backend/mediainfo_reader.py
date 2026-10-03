import os
import re
import subprocess
from pathlib import Path
from pymediainfo import MediaInfo

def format_size(bytes_val: int) -> str:
    if not bytes_val:
        return "0 Б"
    for unit in ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} ПБ"

def format_duration(ms: int) -> str:
    if not ms:
        return "00:00:00"
    seconds = int(ms) // 1000
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def detect_subtitle_language(file_path: Path, sub_stream_index: int, sub_format: str) -> str:
    """Определяет язык текстовых субтитров через ffmpeg и анализ текста, если он не указан в MKV"""
    fmt_upper = (sub_format or "").upper()
    if any(non_text in fmt_upper for non_text in ("PGS", "VOBSUB", "SUP", "HDMV")):
        return "und"

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    for seek in ("0", "120", "300"):
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", seek,
            "-i", str(file_path),
            "-map", f"0:s:{sub_stream_index}",
            "-t", "180",
            "-f", "srt",
            "-"
        ]
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                timeout=4
            )
            raw = res.stdout.decode('utf-8', errors='ignore')
            clean = re.sub(r'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}', ' ', raw)
            clean = re.sub(r'\{[^}]+\}|<[^>]+>|\d+', ' ', clean)
            words = re.findall(r'[a-zA-Zа-яА-ЯёЁіІїЇєЄґҐ]+', clean)
            if len(words) >= 3:
                cyr = len(re.findall(r'[а-яА-ЯёЁіІїЇєЄґҐ]', clean))
                lat = len(re.findall(r'[a-zA-Z]', clean))
                if cyr > lat:
                    if re.search(r'[іІїЇєЄґҐ]', clean):
                        return 'ukr'
                    return 'rus'
                elif lat > cyr:
                    lower_words = set(w.lower() for w in words)
                    if lower_words & {'the', 'and', 'you', 'that', 'what', 'is', 'it', 'for', 'are', 'not', 'have'}:
                        return 'eng'
                    if lower_words & {'que', 'el', 'la', 'los', 'las', 'por', 'con', 'para'}:
                        return 'spa'
                    if lower_words & {'les', 'des', 'est', 'pour', 'dans', 'une', 'qui'}:
                        return 'fra'
                    if lower_words & {'und', 'der', 'die', 'das', 'ist', 'nicht', 'ein'}:
                        return 'deu'
                    return 'eng'
        except Exception:
            pass

    return "und"

def analyze_media(file_path: str) -> dict:
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    # Попытка парсинга через pymediainfo
    media_info = MediaInfo.parse(str(p))
    
    general_track = None
    video_track = None
    audio_tracks = []
    subtitle_tracks = []

    for track in media_info.tracks:
        if track.track_type == 'General':
            general_track = track
        elif track.track_type == 'Video' and not video_track:
            video_track = track
        elif track.track_type == 'Audio':
            audio_tracks.append({
                "id": track.track_id,
                "title": track.title or "",
                "language": track.language or "und",
                "format": track.format or "",
                "commercial_name": track.commercial_name or track.format or "",
                "channels": track.channel_s or 2,
                "bitrate": f"{int(track.bit_rate)//1000} kbps" if track.bit_rate else "",
                "sampling_rate": track.sampling_rate or ""
            })
        elif track.track_type == 'Text':
            lang = track.language or "und"
            sub_fmt = track.format or ""
            sub_idx = len(subtitle_tracks)
            if lang in ("und", "None", ""):
                detected = detect_subtitle_language(p, sub_idx, sub_fmt)
                if detected != "und":
                    lang = detected

            subtitle_tracks.append({
                "id": track.track_id,
                "title": track.title or "",
                "language": lang,
                "format": sub_fmt,
                "forced": getattr(track, "forced", "No") == "Yes"
            })

    # Сборка данных о видео
    width = getattr(video_track, "width", 0) or 0
    height = getattr(video_track, "height", 0) or 0
    fps = getattr(video_track, "frame_rate", "") or ""
    video_format = getattr(video_track, "format", "") or ""
    commercial_name = getattr(video_track, "commercial_name", "") or ""
    format_profile = getattr(video_track, "format_profile", "") or ""
    bit_depth = getattr(video_track, "bit_depth", None)
    scan_type = getattr(video_track, "scan_type", "Progressive") or "Progressive"
    
    # HDR / Dolby Vision / HLG detection
    hdr_format = getattr(video_track, "hdr_format", "") or getattr(video_track, "hdr_format_commercial", "") or ""
    hdr_format_profile = getattr(video_track, "hdr_format_profile", "") or ""
    transfer_chars = getattr(video_track, "transfer_characteristics", "") or ""
    
    video_bitrate_val = getattr(video_track, "bit_rate", None)
    video_bitrate = f"{int(video_bitrate_val)//1000} kbps" if video_bitrate_val else ""
    video_bitrate_kbps = int(video_bitrate_val)//1000 if video_bitrate_val else None

    # Полный сырой текст для спойлера трекеров
    try:
        raw_text = MediaInfo.parse(str(p), output="")
    except Exception:
        try:
            raw_text = str(media_info.to_data())
        except Exception:
            raw_text = f"MediaInfo: {p.name}"

    duration_ms = getattr(general_track, "duration", 0) or 0

    return {
        "file_path": str(p),
        "filename": p.name,
        "file_size": format_size(p.stat().st_size),
        "file_size_bytes": p.stat().st_size,
        "duration": format_duration(duration_ms),
        "duration_ms": duration_ms,
        "resolution": f"{width}x{height}",
        "width": width,
        "height": height,
        "fps": fps,
        "scan_type": scan_type,
        "bit_depth": bit_depth,
        "hdr_format": hdr_format,
        "hdr_format_profile": hdr_format_profile,
        "transfer_characteristics": transfer_chars,
        "video_codec": video_format,
        "video_format_profile": format_profile,
        "video_commercial_name": commercial_name,
        "video_bitrate": video_bitrate,
        "video_bitrate_kbps": video_bitrate_kbps,
        "audio_tracks": audio_tracks,
        "subtitles": subtitle_tracks,
        "raw_mediainfo": raw_text
    }

def upload_mediainfo_paste(raw_mediainfo: str) -> str:
    """Загружает текстовый отчёт MediaInfo на Rentry и возвращает публичную ссылку на инфо-файл"""
    if not raw_mediainfo or len(raw_mediainfo.strip()) < 10:
        return ""
    
    formatted_text = f"```\n{raw_mediainfo.strip()}\n```"
    try:
        import requests
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        resp = s.get("https://rentry.co", timeout=6)
        token = s.cookies.get("csrftoken")
        if not token:
            return ""

        post_data = {
            "csrfmiddlewaretoken": token,
            "text": formatted_text
        }
        res = s.post("https://rentry.co/api/new", data=post_data, headers={"Referer": "https://rentry.co"}, timeout=8)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "200" and data.get("url"):
                return data["url"]
    except Exception as e:
        print(f"Error uploading MediaInfo paste: {e}")
    return ""

