import os
import re
import subprocess
import shutil
import base64
from pathlib import Path
from PIL import Image, ImageStat
import requests

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "screenshots"

def get_video_duration_seconds(file_path: str) -> float:
    """Получает точную длительность видео в секундах через ffprobe/ffmpeg"""
    cmd = [
        "ffmpeg", "-i", file_path
    ]
    try:
        proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, errors="ignore")
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", proc.stderr)
        if match:
            h, m, s = match.groups()
            return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception as e:
        print(f"Error getting duration: {e}")
    return 0.0

def is_frame_too_dark(image_path: Path, threshold: float = 18.0) -> bool:
    """Проверяет, не является ли кадр слишком темным (черный экран/смена сцены)"""
    try:
        with Image.open(image_path) as img:
            gray = img.convert('L')
            stat = ImageStat.Stat(gray)
            return stat.mean[0] < threshold
    except Exception:
        return False

def format_timestamp(seconds: float) -> str:
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"

def extract_single_frame(file_path: str, timestamp_sec: float, output_path: Path) -> bool:
    """Извлекает одиночный кадр по таймкоду (быстрый seek)"""
    cmd = [
        "ffmpeg",
        "-ss", str(timestamp_sec),
        "-i", file_path,
        "-frames:v", "1",
        "-q:v", "2",
        str(output_path),
        "-y"
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return res.returncode == 0 and output_path.exists()
    except Exception as e:
        print(f"Error extracting frame at {timestamp_sec}: {e}")
        return False

def generate_screenshots(file_path: str, count: int = 12, start_offset_ratio: float = 0.05, end_offset_ratio: float = 0.07) -> list:
    """Генерирует набор скриншотов с равномерным распределением и пропуском темных сцен"""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    # Создаем папку для скриншотов текущего релиза
    release_cache = CACHE_DIR / re.sub(r'[^\w\-_\.]', '_', p.stem)
    if release_cache.exists():
        shutil.rmtree(release_cache, ignore_errors=True)
    release_cache.mkdir(parents=True, exist_ok=True)

    duration = get_video_duration_seconds(file_path)
    if duration <= 10:
        duration = 3600  # Fallback если не удалось определить

    start_sec = duration * start_offset_ratio
    end_sec = duration * (1.0 - end_offset_ratio)
    available_range = max(10, end_sec - start_sec)

    step = available_range / (count + 1)
    results = []

    for i in range(count):
        target_time = start_sec + (i + 1) * step
        out_name = f"screen_{i+1:02d}.png"
        out_file = release_cache / out_name

        # Пробуем снять кадр, если слишком темный — сдвигаем на 4 секунды вперед
        success = extract_single_frame(file_path, target_time, out_file)
        if success and is_frame_too_dark(out_file) and (target_time + 4 < end_sec):
            extract_single_frame(file_path, target_time + 4, out_file)

        if out_file.exists():
            # Кодируем превью в base64 для мгновенного отображения в WebView без проблем с CORS
            try:
                with open(out_file, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                results.append({
                    "id": i + 1,
                    "file_path": str(out_file),
                    "timestamp": format_timestamp(target_time),
                    "data_url": f"data:image/png;base64,{b64}"
                })
            except Exception as e:
                print(f"Error encoding preview: {e}")

    return results

# --- Модуль загрузки на Fastpic ---
def upload_to_fastpic(image_path: str, preview_size: int = 350) -> dict:
    """Загружает изображение на Fastpic.org через публичный API"""
    p = Path(image_path)
    if not p.exists():
        return {"error": "Файл не найден"}

    url = "https://fastpic.org/upload?api=1"
    try:
        with open(p, "rb") as img_f:
            files = {"file1": (p.name, img_f, "image/png")}
            data = {
                "method": "upload",
                "check_thumb": "size",
                "size": str(preview_size),
                "uploading": "1"
            }
            resp = requests.post(url, files=files, data=data, timeout=30)
            if resp.status_code == 200:
                text = resp.text
                img_match = re.search(r"<imagepath>(.*?)</imagepath>", text)
                thumb_match = re.search(r"<thumbpath>(.*?)</thumbpath>", text)
                if img_match and thumb_match:
                    full_url = img_match.group(1).strip()
                    thumb_url = thumb_match.group(1).strip()
                    bb_code = f"[url={full_url}][img]{thumb_url}[/img][/url]"
                    return {
                        "success": True,
                        "full_url": full_url,
                        "thumb_url": thumb_url,
                        "bb_code": bb_code
                    }
        return {"error": "Не удалось распарсить ответ Fastpic"}
    except Exception as e:
        return {"error": f"Ошибка сети при загрузке на Fastpic: {e}"}
