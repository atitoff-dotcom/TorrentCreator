import re
import webview
from pathlib import Path
from backend.config_manager import load_config, save_config
from backend.mediainfo_reader import analyze_media
from backend.meta_fetcher import MetaFetcher, clean_title_from_filename

class AppAPI:
    def __init__(self, window=None):
        self._window = window
        self.current_media_data = None
        self.meta_fetcher = MetaFetcher()

    def set_window(self, window):
        self._window = window

    def select_file_dialog(self):
        """Открывает нативный диалог выбора MKV файла"""
        if not self._window:
            return None
        file_types = ('Video Files (*.mkv;*.mp4;*.avi)', 'All files (*.*)')
        try:
            dialog_type = webview.FileDialog.OPEN
        except AttributeError:
            dialog_type = webview.OPEN_DIALOG
        result = self._window.create_file_dialog(
            dialog_type,
            allow_multiple=False,
            file_types=file_types
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def select_folder_dialog(self):
        """Открывает нативный диалог выбора папки"""
        if not self._window:
            return None
        try:
            dialog_type = webview.FileDialog.FOLDER
        except AttributeError:
            dialog_type = webview.FOLDER_DIALOG
        result = self._window.create_file_dialog(
            dialog_type,
            allow_multiple=False
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def process_media_file(self, file_path: str):
        """Анализирует медиафайл и возвращает структурированный словарь"""
        try:
            data = analyze_media(file_path)
            clean_info = clean_title_from_filename(data.get("filename", ""))
            data["clean_query"] = clean_info.get("query")
            data["year_guess"] = clean_info.get("year")
            self.current_media_data = data
            return data
        except Exception as e:
            return {"error": str(e)}

    def get_config(self):
        """Возвращает настройки приложения"""
        return load_config()

    def save_config(self, cfg: dict):
        """Сохраняет настройки приложения"""
        res = save_config(cfg)
        self.meta_fetcher.reload_config()
        return res

    def search_metadata(self, query: str, year: str = None):
        """Поиск фильма/сериала в Кинопоиске и TMDb (Кинопоиск в приоритете)"""
        try:
            results = []
            clean_q = (query or "").strip()
            if not clean_q:
                return []

            # Если строка состоит только из цифр (номер файла/диска вроде 00034, 01) - не ищем онлайн
            if clean_q.isdigit() and len(clean_q) <= 5:
                return []

            # 1. Проверяем, не ссылка ли это на Кинопоиск (например, kinopoisk.ru/film/161023/)
            kp_url_match = re.search(r'kinopoisk\.ru/(?:film|series)/(\d+)', clean_q)
            if kp_url_match:
                film_id = int(kp_url_match.group(1))
                det = self.meta_fetcher.get_kinopoisk_details(film_id)
                if det:
                    return [{
                        "source": "kinopoisk",
                        "id": film_id,
                        "kinopoisk_id": film_id,
                        "title_ru": det.get("title_ru"),
                        "title_orig": det.get("title_orig"),
                        "year": det.get("year"),
                        "poster_url": det.get("poster_url"),
                        "rating_kinopoisk": det.get("kinopoisk_rating"),
                        "overview": det.get("plot", "")[:120]
                    }]

            # 2. Если есть ключ Кинопоиска — ищем в первую очередь на Кинопоиске!
            kp_results = self.meta_fetcher.search_kinopoisk(clean_q)
            results.extend(kp_results)

            # 3. Затем дополняем результатами TMDb
            tmdb_results = self.meta_fetcher.search_tmdb(clean_q, year)
            results.extend(tmdb_results)

            return results
        except Exception as e:
            print(f"Error searching metadata: {e}")
            return []

    def get_metadata_details(self, source: str, item_id: int, is_series: bool = False):
        """Получает полные детали фильма/сериала"""
        try:
            if source == "tmdb":
                return self.meta_fetcher.get_tmdb_details(item_id, is_series)
            elif source == "kinopoisk":
                return self.meta_fetcher.get_kinopoisk_details(item_id)
            return {}
        except Exception as e:
            print(f"Error getting metadata details: {e}")
            return {}

    def make_screenshots(self, file_path: str, count: int = 12):
        """Снимает набор скриншотов из видеофайла"""
        try:
            from backend.screenshot_maker import generate_screenshots
            return generate_screenshots(file_path, count)
        except Exception as e:
            return {"error": str(e)}

    def upload_single_screenshot(self, image_path: str, preview_size: int = 350):
        """Загружает один скриншот на фотохостинг Fastpic"""
        try:
            from backend.screenshot_maker import upload_to_fastpic
            return upload_to_fastpic(image_path, preview_size)
        except Exception as e:
            return {"error": str(e)}

    def upload_screenshots(self, image_paths: list, preview_size: int = 350):
        """Загружает список изображений на фотохостинг"""
        try:
            from backend.screenshot_maker import upload_to_fastpic
            uploaded = []
            for path in image_paths:
                res = upload_to_fastpic(path, preview_size)
                if res.get("success"):
                    uploaded.append(res)
            return uploaded
        except Exception as e:
            return {"error": str(e)}

    def create_torrent(self, tracker_type: str = "rutracker"):
        """Создает .torrent файл для текущего медиафайла"""
        if not self.current_media_data or not self.current_media_data.get("file_path"):
            return {"error": "Медиафайл не выбран"}
        try:
            from backend.torrent_builder import build_torrent
            return build_torrent(self.current_media_data["file_path"], tracker_type)
        except Exception as e:
            return {"error": str(e)}

    def upload_mediainfo_paste(self):
        """Загружает текстовый отчёт MediaInfo текущего файла на Rentry и возвращает URL"""
        if not self.current_media_data or not self.current_media_data.get("raw_mediainfo"):
            return {"error": "Медиафайл не проанализирован"}
        
        cached_url = self.current_media_data.get("info_file_url")
        if cached_url:
            return {"success": True, "url": cached_url}

        from backend.mediainfo_reader import upload_mediainfo_paste
        url = upload_mediainfo_paste(self.current_media_data["raw_mediainfo"])
        if url:
            self.current_media_data["info_file_url"] = url
            return {"success": True, "url": url}
        return {"error": "Не удалось загрузить инфо-файл на сервис"}

    def generate_release_data(self, release_opts: dict, uploaded_screens: list = None):
        """Формирует заголовки, BB-код RuTracker и поля Kinozal"""
        try:
            from backend.templates import build_rutracker_title, build_rutracker_bbcode, build_kinozal_fields
            meta = release_opts.get("meta") or {}
            media = self.current_media_data or {}
            screens = uploaded_screens or []

            # Автоматическая загрузка инфо-файла MediaInfo на Rentry, если ссылка еще не была указана
            info_url = release_opts.get("info_file_url") or media.get("info_file_url")
            if not info_url and media.get("raw_mediainfo"):
                from backend.mediainfo_reader import upload_mediainfo_paste
                info_url = upload_mediainfo_paste(media["raw_mediainfo"])
                if info_url:
                    media["info_file_url"] = info_url
                    release_opts["info_file_url"] = info_url

            ru_title = build_rutracker_title(meta, media, release_opts)
            ru_bbcode = build_rutracker_bbcode(meta, media, release_opts, screens)
            kz_fields = build_kinozal_fields(meta, media, release_opts, screens)

            payload = {
                "rutracker_title": ru_title,
                "rutracker_bbcode": ru_bbcode,
                "kinozal_fields": kz_fields,
                "info_file_url": info_url or ""
            }
            return payload
        except Exception as e:
            return {"error": str(e)}

    def open_browser_url(self, url: str):
        """Открывает URL в браузере по умолчанию"""
        import webbrowser
        webbrowser.open(url)
        return True

    def set_theme(self, theme_name: str):
        """Обновляет тему оформления в конфиге"""
        cfg = load_config()
        cfg["theme"] = theme_name
        save_config(cfg)
        return True

    def publish_kinozal(self, release_opts: dict, uploaded_screens: list = None):
        """Открывает Кинозал в браузере и автоматически заполняет все поля раздачи"""
        try:
            payload = self.generate_release_data(release_opts, uploaded_screens)
            if "error" in payload:
                return payload
            from backend.browser_autofill import autofill_kinozal
            kz_fields = payload.get("kinozal_fields") or {}
            res = autofill_kinozal(kz_fields)
            if isinstance(res, dict) and payload.get("info_file_url"):
                res["info_file_url"] = payload["info_file_url"]
            return res
        except Exception as e:
            return {"error": str(e)}

    def publish_rutracker(self, release_opts: dict, uploaded_screens: list = None, forum_id: int = 313):
        """Открывает RuTracker в браузере и автоматически заполняет тему и BB-код"""
        try:
            payload = self.generate_release_data(release_opts, uploaded_screens)
            if "error" in payload:
                return payload
            from backend.browser_autofill import autofill_rutracker
            ru_title = payload.get("rutracker_title") or ""
            ru_bbcode = payload.get("rutracker_bbcode") or ""
            res = autofill_rutracker(ru_title, ru_bbcode, forum_id)
            if isinstance(res, dict) and payload.get("info_file_url"):
                res["info_file_url"] = payload["info_file_url"]
            return res
        except Exception as e:
            return {"error": str(e)}

    def get_config(self):
        """Возвращает текущую конфигурацию приложения"""
        return load_config()

    def save_config(self, cfg: dict):
        """Сохраняет конфигурацию приложения"""
        current = load_config()
        current.update(cfg)
        return save_config(current)

    def check_ffmpeg_status(self):
        """Проверяет наличие и версию FFmpeg в системе"""
        from backend.ffmpeg_manager import check_ffmpeg_version
        return check_ffmpeg_version()

    def select_ffmpeg_file(self):
        """Открывает диалог выбора исполняемого файла ffmpeg"""
        if not self._window:
            return {"found": False, "error": "Окно не инициализировано"}
        import sys
        if sys.platform == "win32":
            file_types = ('FFmpeg Executable (ffmpeg.exe)', 'All files (*.*)')
        else:
            file_types = ('FFmpeg Executable (ffmpeg)', 'All files (*.*)')

        try:
            dialog_type = webview.FileDialog.OPEN
        except AttributeError:
            dialog_type = webview.OPEN_DIALOG

        result = self._window.create_file_dialog(
            dialog_type,
            allow_multiple=False,
            file_types=file_types
        )
        if result and len(result) > 0:
            selected_path = result[0]
            from backend.ffmpeg_manager import check_ffmpeg_version
            status = check_ffmpeg_version(selected_path)
            if status.get("found"):
                cfg = load_config()
                cfg["ffmpeg_path"] = status["path"]
                save_config(cfg)
            return status
        return {"found": False, "cancelled": True}

    def download_ffmpeg(self):
        """Автоматически скачивает и настраивает статический бинарник FFmpeg"""
        from backend.ffmpeg_manager import download_and_extract_ffmpeg
        return download_and_extract_ffmpeg()


