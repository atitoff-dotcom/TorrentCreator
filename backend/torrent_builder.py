import os
from pathlib import Path
import torf
from backend.config_manager import load_config

def calculate_piece_size(total_bytes: int) -> int:
    """Вычисляет оптимальный размер куска (piece size) по стандартам трекеров"""
    # 2^18 = 256 KB, 2^19 = 512 KB, 2^20 = 1 MB, 2^21 = 2 MB, 2^22 = 4 MB, 2^23 = 8 MB, 2^24 = 16 MB
    if total_bytes < 500 * 1024 * 1024:         # < 500 MB
        return 2 ** 18  # 256 KB
    elif total_bytes < 2 * 1024 * 1024 * 1024:   # < 2 GB
        return 2 ** 20  # 1 MB
    elif total_bytes < 8 * 1024 * 1024 * 1024:   # < 8 GB
        return 2 ** 21  # 2 MB
    elif total_bytes < 20 * 1024 * 1024 * 1024:  # < 20 GB
        return 2 ** 22  # 4 MB
    elif total_bytes < 50 * 1024 * 1024 * 1024:  # < 50 GB
        return 2 ** 23  # 8 MB
    else:                                        # >= 50 GB
        return 2 ** 24  # 16 MB

def build_torrent(source_path: str, tracker_type: str = "rutracker", custom_save_dir: str = None) -> dict:
    """Создает .torrent файл для отдельного файла или папки"""
    p = Path(source_path)
    if not p.exists():
        return {"error": f"Путь не найден: {source_path}"}

    cfg = load_config()

    # Определение папки сохранения
    if custom_save_dir and Path(custom_save_dir).exists():
        save_dir = Path(custom_save_dir)
    elif cfg.get("torrent_save_path") and Path(cfg.get("torrent_save_path")).exists():
        save_dir = Path(cfg.get("torrent_save_path"))
    else:
        # По умолчанию рядом с исходным файлом/папкой
        save_dir = p.parent

    # Вычисление общего размера
    if p.is_file():
        total_size = p.stat().st_size
    else:
        total_size = sum(f.stat().st_size for f in p.glob('**/*') if f.is_file())

    piece_size = calculate_piece_size(total_size)

    # Инициализация Torf
    try:
        t = torf.Torrent(path=str(p), piece_size=piece_size)

        # Для Кинозала прописываем персональный announce URL, если задан passkey
        if tracker_type.lower() == "kinozal":
            passkey = cfg.get("kinozal_passkey", "").strip()
            if passkey:
                t.trackers = [f"http://tr.kinozal.tv/announce.php?uk={passkey}"]
            out_filename = f"{p.stem}_kinozal.torrent"
        else:
            # Для Рутрекера создаем чистый торрент
            out_filename = f"{p.stem}_rutracker.torrent"

        t.generate()
        out_path = save_dir / out_filename
        t.write(str(out_path), overwrite=True)

        return {
            "success": True,
            "torrent_path": str(out_path),
            "torrent_name": out_filename,
            "piece_size": piece_size,
            "info_hash": t.infohash
        }
    except Exception as e:
        return {"error": f"Ошибка создания торрент-файла: {e}"}
