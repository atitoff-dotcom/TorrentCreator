import os
import sys
import re
import shutil
import zipfile
import tarfile
import subprocess
from pathlib import Path
from typing import Optional, Callable
import requests

from backend.config_manager import load_config, save_config

def get_target_bin_dir() -> Path:
    """Определяет подходящую директорию для хранения бинарника ffmpeg"""
    # 1. Проверяем текущую рабочую директорию (портативный режим рядом с приложением)
    cwd = Path.cwd()
    try:
        test_file = cwd / ".write_test"
        test_file.touch()
        test_file.unlink()
        return cwd
    except Exception:
        pass
    
    # 2. Резервный вариант: домашняя директория пользователя ~/.torrentcreator/bin
    user_bin = Path.home() / ".torrentcreator" / "bin"
    user_bin.mkdir(parents=True, exist_ok=True)
    return user_bin

def get_ffmpeg_binary_name() -> str:
    return "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

def get_ffmpeg_path() -> Optional[str]:
    """Ищет путь к ffmpeg: из настроек -> рядом с приложением -> в ~/.torrentcreator/bin -> в системном PATH"""
    cfg = load_config()
    cfg_path = cfg.get("ffmpeg_path", "").strip()
    if cfg_path and os.path.isfile(cfg_path):
        return cfg_path

    bin_name = get_ffmpeg_binary_name()

    # Проверка в текущей папке
    local_path = Path.cwd() / bin_name
    if local_path.is_file():
        return str(local_path.resolve())

    # Проверка в ~/.torrentcreator/bin/
    user_path = Path.home() / ".torrentcreator" / "bin" / bin_name
    if user_path.is_file():
        return str(user_path.resolve())

    # Проверка в системном PATH
    which_path = shutil.which("ffmpeg")
    if which_path and os.path.isfile(which_path):
        return which_path

    return None

def check_ffmpeg_version(ffmpeg_path: Optional[str] = None) -> dict:
    """Проверяет работоспособность и версию FFmpeg без всплывающих окон"""
    if not ffmpeg_path:
        ffmpeg_path = get_ffmpeg_path()

    if not ffmpeg_path:
        return {
            "found": False,
            "path": "",
            "version": "",
            "major": 0,
            "is_outdated": True,
            "error": "FFmpeg не обнаружен"
        }

    extra_flags = {}
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        extra_flags["startupinfo"] = startupinfo
        extra_flags["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        res = subprocess.run(
            [ffmpeg_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
            **extra_flags
        )
        if res.returncode == 0:
            first_line = res.stdout.splitlines()[0] if res.stdout else ""
            ver_match = re.search(r"ffmpeg version\s+([^\s]+)", first_line)
            ver_str = ver_match.group(1) if ver_match else first_line

            num_match = re.search(r"(\d+)\.(\d+)", ver_str)
            major = int(num_match.group(1)) if num_match else (7 if "git" in ver_str.lower() else 5)
            is_outdated = major < 5

            return {
                "found": True,
                "path": str(Path(ffmpeg_path).resolve()),
                "version": ver_str,
                "major": major,
                "is_outdated": is_outdated,
                "error": None
            }
        else:
            return {
                "found": False,
                "path": ffmpeg_path,
                "version": "",
                "major": 0,
                "is_outdated": True,
                "error": f"Ошибка вызова: код {res.returncode}"
            }
    except Exception as e:
        return {
            "found": False,
            "path": ffmpeg_path,
            "version": "",
            "major": 0,
            "is_outdated": True,
            "error": str(e)
        }

def get_download_url_for_os() -> dict:
    """Возвращает проверенные ссылки на официальные статические сборки"""
    if sys.platform == "win32":
        return {
            "os": "windows",
            "url": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
            "format": "zip",
            "bin_name": "ffmpeg.exe"
        }
    elif sys.platform == "darwin":
        return {
            "os": "macos",
            "url": "https://evermeet.cx/ffmpeg/getrelease/zip",
            "format": "zip",
            "bin_name": "ffmpeg"
        }
    else:
        return {
            "os": "linux",
            "url": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
            "format": "tar.xz",
            "bin_name": "ffmpeg"
        }

def download_and_extract_ffmpeg(progress_callback: Optional[Callable[[int, str], None]] = None) -> dict:
    """Скачивает и извлекает статический бинарник FFmpeg с отчетом о прогрессе"""
    info = get_download_url_for_os()
    url = info["url"]
    target_dir = get_target_bin_dir()
    bin_name = info["bin_name"]
    final_bin_path = target_dir / bin_name
    temp_archive = target_dir / f"ffmpeg_download.{'zip' if info['format'] == 'zip' else 'tar.xz'}"

    try:
        if progress_callback:
            progress_callback(2, f"Подключение к серверу загрузки...")

        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        total_size = int(resp.headers.get("content-length", 0))

        downloaded = 0
        with open(temp_archive, "wb") as f:
            for chunk in resp.iter_content(chunk_size=128 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and progress_callback:
                        pct = int((downloaded / total_size) * 85)
                        mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        progress_callback(pct, f"Загрузка FFmpeg: {mb:.1f} из {total_mb:.1f} МБ ({pct}%)")

        if progress_callback:
            progress_callback(88, "Распаковка бинарного файла...")

        # Извлечение только нужного бинарника ffmpeg / ffmpeg.exe
        if info["format"] == "zip":
            with zipfile.ZipFile(temp_archive, "r") as z:
                for member in z.namelist():
                    if member.endswith(bin_name) and not member.startswith("__MACOSX"):
                        with z.open(member) as source, open(final_bin_path, "wb") as target:
                            shutil.copyfileobj(source, target)
                        break
        else: # tar.xz
            with tarfile.open(temp_archive, "r:xz") as t:
                for member in t.getmembers():
                    if member.name.endswith(f"/{bin_name}") or member.name == bin_name:
                        source = t.extractfile(member)
                        if source:
                            with open(final_bin_path, "wb") as target:
                                shutil.copyfileobj(source, target)
                        break

        # Удаляем временный архив
        if temp_archive.exists():
            temp_archive.unlink()

        if not final_bin_path.exists():
            return {"success": False, "error": "Не удалось извлечь бинарный файл из архива"}

        # Устанавливаем права на исполнение на Linux / macOS
        if sys.platform != "win32":
            os.chmod(final_bin_path, 0o755)

        # Сохраняем путь в config.json
        cfg = load_config()
        cfg["ffmpeg_path"] = str(final_bin_path.resolve())
        save_config(cfg)

        if progress_callback:
            progress_callback(100, "FFmpeg успешно установлен и проверен!")

        # Проверяем версию установленного бинарника
        ver_info = check_ffmpeg_version(str(final_bin_path.resolve()))
        return {
            "success": True,
            "path": str(final_bin_path.resolve()),
            "version": ver_info.get("version", "актуальная"),
            "major": ver_info.get("major", 7)
        }

    except Exception as e:
        if temp_archive.exists():
            try: temp_archive.unlink()
            except: pass
        return {"success": False, "error": str(e)}
