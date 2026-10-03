import json
import sys
from pathlib import Path

DEFAULT_KP_KEY = "6834c208-9ed1-451f-8d5d-6fcaa5f2a0f0"
DEFAULT_TMDB_KEY = "782af07368e06c3b1bc48bf2a1d06631"

def get_config_path() -> Path:
    # 1. Executable directory (portable mode)
    if getattr(sys, 'frozen', False) or 'pyapp' in sys.executable.lower():
        exe_dir_cfg = Path(sys.executable).parent / "config.json"
        if exe_dir_cfg.exists():
            return exe_dir_cfg
    # 2. Local directory (portable / dev mode)
    cwd_cfg = Path.cwd() / "config.json"
    if cwd_cfg.exists():
        return cwd_cfg
    # 3. Package directory parent
    pkg_parent_cfg = Path(__file__).resolve().parent.parent / "config.json"
    if pkg_parent_cfg.exists():
        return pkg_parent_cfg
    # 4. User home app directory (~/.torrentcreator/config.json)
    user_cfg_dir = Path.home() / ".torrentcreator"
    user_cfg_dir.mkdir(parents=True, exist_ok=True)
    return user_cfg_dir / "config.json"

CONFIG_PATH = get_config_path()

DEFAULT_CONFIG = {
    "theme": "dark",
    "kinopoisk_api_key": DEFAULT_KP_KEY,
    "tmdb_api_key": DEFAULT_TMDB_KEY,
    "screenshots_count": 12,
    "screenshots_release_count": 4,
    "image_host": "fastpic",
    "fastpic_jpeg_quality": 95,
    "preview_size": 350,
    "default_tracker": "kinozal",
    "ffmpeg_path": ""
}

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            # Если ключи в файле пустые — используем рабочие ключи по умолчанию
            if not merged.get("kinopoisk_api_key"):
                merged["kinopoisk_api_key"] = DEFAULT_KP_KEY
            if not merged.get("tmdb_api_key"):
                merged["tmdb_api_key"] = DEFAULT_TMDB_KEY
            return merged
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(cfg: dict) -> bool:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
