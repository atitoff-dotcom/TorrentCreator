import re
import urllib.parse
import requests
from backend.config_manager import load_config

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_IMAGE_ORIGINAL = "https://image.tmdb.org/t/p/original"

KP_UNOFFICIAL_BASE_URL = "https://kinopoiskapiunofficial.tech/api"

def clean_title_from_filename(filename: str) -> dict:
    """Очищает имя файла от служебных тегов рипов, извлекая вероятное название, год и сезон"""
    name = re.sub(r'\.(mkv|mp4|avi|ts)$', '', filename, flags=re.IGNORECASE)
    name = name.replace('.', ' ').replace('_', ' ')

    # Поиск сезона и серии (например, S01E05 или s01)
    season_match = re.search(r'\b[sS](\d{1,2})(?:[eE](\d{1,3}))?\b', name)
    season = None
    episode = None
    if season_match:
        season = int(season_match.group(1))
        if season_match.group(2):
            episode = int(season_match.group(2))
        name = name[:season_match.start()]

    # Поиск года (19xx или 20xx)
    year_match = re.search(r'\b(19\d\d|20\d\d)\b', name)
    year = None
    if year_match:
        year = year_match.group(1)
        name = name[:year_match.start()]

    # Удаление типичных тегов релизов
    rip_tags = r'\b(1080p|720p|2160p|4k|uhd|web-dl|webrip|bdrip|bluray|dvdrip|hdtv|x264|x265|hevc|avc|ddp5\.1|dd5\.1|ac3|aac|dts)\b'
    name = re.sub(rip_tags, '', name, flags=re.IGNORECASE)
    clean_name = re.sub(r'\s+', ' ', name).strip()

    return {
        "query": clean_name or filename,
        "year": year,
        "season": season,
        "episode": episode,
        "is_series": season is not None
    }

class MetaFetcher:
    def __init__(self):
        self.config = load_config()

    def reload_config(self):
        self.config = load_config()

    # --- TMDb Интеграция ---
    def search_tmdb(self, query: str, year: str = None) -> list:
        api_key = (self.config.get("tmdb_api_key") or "").strip()
        if not api_key or not query or (query.isdigit() and len(query) <= 5):
            return []

        params = {
            "api_key": api_key,
            "query": query,
            "language": "ru-RU",
            "include_adult": "false"
        }
        if year:
            params["year"] = year

        try:
            resp = requests.get(f"{TMDB_BASE_URL}/search/multi", params=params, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("results", []):
                    media_type = item.get("media_type")
                    if media_type not in ["movie", "tv"]:
                        continue

                    is_tv = media_type == "tv"
                    title = item.get("name" if is_tv else "title")
                    orig_title = item.get("original_name" if is_tv else "original_title")
                    release_date = item.get("first_air_date" if is_tv else "release_date", "")
                    item_year = release_date.split("-")[0] if release_date else ""
                    poster_path = item.get("poster_path")

                    results.append({
                        "source": "tmdb",
                        "id": item.get("id"),
                        "is_series": is_tv,
                        "title_ru": title,
                        "title_orig": orig_title,
                        "year": item_year,
                        "poster_url": f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None,
                        "overview": item.get("overview", "")
                    })
                return results
        except Exception as e:
            print(f"Error searching TMDb: {e}")
        return []

    def get_tmdb_details(self, tmdb_id: int, is_series: bool = False) -> dict:
        api_key = (self.config.get("tmdb_api_key") or "").strip()
        if not api_key:
            return {}

        endpoint = f"tv/{tmdb_id}" if is_series else f"movie/{tmdb_id}"
        params = {
            "api_key": api_key,
            "language": "ru-RU",
            "append_to_response": "credits,external_ids,images"
        }

        try:
            resp = requests.get(f"{TMDB_BASE_URL}/{endpoint}", params=params, timeout=8)
            if resp.status_code != 200:
                return {}

            data = resp.json()
            is_tv = is_series
            title_ru = data.get("name" if is_tv else "title")
            title_orig = data.get("original_name" if is_tv else "original_title")
            release_date = data.get("first_air_date" if is_tv else "release_date", "")
            year = release_date.split("-")[0] if release_date else ""

            # Страны, жанры и кинокомпании
            countries = [c.get("name") for c in data.get("production_countries", [])]
            genres = [g.get("name") for g in data.get("genres", [])]
            companies = [c.get("name") for c in data.get("production_companies", []) if c.get("name")]
            studio_str = ", ".join(companies[:4])

            # Режиссеры и актеры
            credits = data.get("credits", {})
            directors = []
            if is_tv:
                directors = [c.get("name") for c in data.get("created_by", [])]
            else:
                directors = [m.get("name") for m in credits.get("crew", []) if m.get("job") == "Director"]

            actors = [a.get("name") for a in credits.get("cast", [])[:10]]

            # Внешние ID (IMDb)
            ext_ids = data.get("external_ids", {})
            imdb_id = ext_ids.get("imdb_id")

            # Постеры
            poster_path = data.get("poster_path")
            poster_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None
            posters = []
            images = data.get("images", {})
            for img in images.get("posters", [])[:6]:
                p_path = img.get("file_path")
                if p_path:
                    posters.append(f"{TMDB_IMAGE_BASE}{p_path}")

            vote_avg = data.get("vote_average")
            imdb_rating_val = f"{round(vote_avg, 1)}" if vote_avg else None

            # Проверяем, есть ли фильм на Кинопоиске по IMDb ID для получения kinopoisk_id
            kp_match = self.find_kinopoisk_by_imdb(imdb_id) if imdb_id else {}
            kp_id = kp_match.get("kinopoisk_id")
            kp_rating = kp_match.get("kinopoisk_rating")

            orig_lang = (data.get("original_language") or "").lower()
            is_russian = (orig_lang == "ru")

            return {
                "source": "tmdb",
                "id": tmdb_id,
                "is_series": is_tv,
                "title_ru": title_ru,
                "title_orig": title_orig,
                "original_language": orig_lang,
                "is_russian": is_russian,
                "year": year,
                "countries": ", ".join(countries),
                "studio": studio_str,
                "production_companies": studio_str,
                "genres": ", ".join(genres),
                "directors": ", ".join(directors),
                "actors": ", ".join(actors),
                "plot": data.get("overview", ""),
                "poster_url": poster_url,
                "posters": posters or ([poster_url] if poster_url else []),
                "imdb_id": imdb_id,
                "imdb_rating": imdb_rating_val,
                "imdb_url": f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else "",
                "tmdb_url": f"https://www.themoviedb.org/{'tv' if is_tv else 'movie'}/{tmdb_id}",
                "kinopoisk_id": kp_id,
                "kinopoisk_rating": kp_rating,
                "rating_kinopoisk": kp_rating
            }
        except Exception as e:
            print(f"Error getting TMDb details: {e}")
            return {}

    def find_kinopoisk_by_imdb(self, imdb_id: str) -> dict:
        """Ищет фильм в Кинопоиске по IMDb ID для связки ID"""
        api_key = (self.config.get("kinopoisk_api_key") or "").strip()
        if not api_key or not imdb_id:
            return {}

        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        try:
            resp = requests.get(f"{KP_UNOFFICIAL_BASE_URL}/v2.2/films?imdbId={imdb_id}", headers=headers, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    it = items[0]
                    film_id = it.get("kinopoiskId") or it.get("filmId")
                    raw_kp_r = it.get("ratingKinopoisk")
                    return {
                        "kinopoisk_id": film_id,
                        "kinopoisk_rating": str(raw_kp_r) if raw_kp_r else None
                    }
        except Exception as e:
            print(f"Error finding Kinopoisk by IMDb: {e}")
        return {}

    # --- Кинопоиск Unofficial API Интеграция ---
    def search_kinopoisk(self, query: str) -> list:
        api_key = (self.config.get("kinopoisk_api_key") or "").strip()
        if not api_key or not query or (query.isdigit() and len(query) <= 5):
            return []

        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }

        # 1. Сначала пробуем v2.2/films?keyword=...
        try:
            params = {"keyword": query, "page": 1}
            resp = requests.get(f"{KP_UNOFFICIAL_BASE_URL}/v2.2/films", headers=headers, params=params, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("items", []):
                    film_id = item.get("kinopoiskId") or item.get("filmId")
                    if not film_id:
                        continue
                    name_ru = item.get("nameRu") or item.get("nameEn") or item.get("nameOriginal")
                    name_orig = item.get("nameOriginal") or item.get("nameEn")
                    kp_r = item.get("ratingKinopoisk")
                    results.append({
                        "source": "kinopoisk",
                        "id": film_id,
                        "kinopoisk_id": film_id,
                        "title_ru": name_ru,
                        "title_orig": name_orig,
                        "year": str(item.get("year", "")),
                        "poster_url": item.get("posterUrlPreview") or item.get("posterUrl"),
                        "rating_kinopoisk": str(kp_r) if kp_r else None,
                        "overview": f"Рейтинг КП: {kp_r}" if kp_r else ""
                    })
                if results:
                    return results
        except Exception as e:
            print(f"Kinopoisk v2.2 search warning: {e}")

        # 2. Fallback на v2.1/films/search-by-keyword
        try:
            params = {"keyword": query, "page": 1}
            resp = requests.get(f"{KP_UNOFFICIAL_BASE_URL}/v2.1/films/search-by-keyword", headers=headers, params=params, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("films", []):
                    film_id = item.get("filmId")
                    results.append({
                        "source": "kinopoisk",
                        "id": film_id,
                        "kinopoisk_id": film_id,
                        "title_ru": item.get("nameRu"),
                        "title_orig": item.get("nameEn") or item.get("nameOriginal"),
                        "year": str(item.get("year", "")),
                        "poster_url": item.get("posterUrlPreview") or item.get("posterUrl"),
                        "overview": item.get("description", "")
                    })
                return results
        except Exception as e:
            print(f"Error searching Kinopoisk: {e}")
        return []

    def get_kinopoisk_details(self, film_id: int) -> dict:
        api_key = (self.config.get("kinopoisk_api_key") or "").strip()
        if not api_key:
            return {}

        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }

        try:
            # Основные данные о фильме
            resp = requests.get(f"{KP_UNOFFICIAL_BASE_URL}/v2.2/films/{film_id}", headers=headers, timeout=12)
            if resp.status_code != 200:
                return {}
            data = resp.json()

            # Создатели (режиссеры, актеры)
            staff_resp = requests.get(f"{KP_UNOFFICIAL_BASE_URL}/v1/staff?filmId={film_id}", headers=headers, timeout=12)
            directors = []
            actors = []
            if staff_resp.status_code == 200:
                for person in staff_resp.json():
                    role = person.get("professionKey")
                    name = person.get("nameRu") or person.get("nameEn")
                    if role == "DIRECTOR" and len(directors) < 3:
                        directors.append(name)
                    elif role == "ACTOR" and len(actors) < 10:
                        actors.append(name)

            countries = [c.get("country") for c in data.get("countries", [])]
            genres = [g.get("genre") for g in data.get("genres", [])]
            poster_url = data.get("posterUrl") or data.get("posterUrlPreview")

            kp_rating_raw = data.get("ratingKinopoisk")
            kp_rating_str = f"{kp_rating_raw}" if kp_rating_raw else None
            imdb_id = data.get("imdbId")
            imdb_rating_raw = data.get("ratingImdb")
            imdb_rating_str = f"{imdb_rating_raw}" if imdb_rating_raw else None

            # Обогащаем данными о кинокомпаниях из TMDb по IMDb ID
            studio_str = ""
            if imdb_id:
                studio_str = self.get_tmdb_companies_by_imdb(imdb_id)

            # Определение отечественного фильма на Кинопоиске
            countries_list = [c.get("country", "") for c in data.get("countries", []) if c.get("country")]
            primary_country = countries_list[0].lower() if countries_list else ""
            name_orig = (data.get("nameOriginal") or data.get("nameEn") or "").strip()
            name_ru = (data.get("nameRu") or "").strip()
            is_domestic_country = any(k in primary_country for k in ["россия", "ссср", "russia", "ussr", "беларусь"])
            has_foreign_title = bool(name_orig and re.search(r'[a-zA-Z]', name_orig) and name_orig.lower() != name_ru.lower())
            is_russian = is_domestic_country and not has_foreign_title
            orig_lang = "ru" if is_russian else "en"

            return {
                "source": "kinopoisk",
                "id": film_id,
                "kinopoisk_id": film_id,
                "kinopoisk_rating": kp_rating_str,
                "rating_kinopoisk": kp_rating_str,
                "is_series": data.get("type") in ["TV_SERIES", "MINI_SERIES"],
                "title_ru": data.get("nameRu"),
                "title_orig": data.get("nameOriginal") or data.get("nameEn"),
                "original_language": orig_lang,
                "is_russian": is_russian,
                "year": str(data.get("year", "")),
                "countries": ", ".join(countries),
                "studio": studio_str,
                "production_companies": studio_str,
                "genres": ", ".join(genres),
                "directors": ", ".join(directors),
                "actors": ", ".join(actors),
                "plot": data.get("description", ""),
                "poster_url": poster_url,
                "posters": [poster_url] if poster_url else [],
                "imdb_id": imdb_id,
                "imdb_rating": imdb_rating_str,
                "rating_imdb": imdb_rating_str,
                "imdb_url": f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else "",
                "kinopoisk_url": data.get("webUrl") or f"https://www.kinopoisk.ru/film/{film_id}/"
            }
        except Exception as e:
            print(f"Error getting Kinopoisk details: {e}")
            return {}

    def get_tmdb_companies_by_imdb(self, imdb_id: str) -> str:
        """Получает названия кинокомпаний из TMDb по IMDb ID"""
        tmdb_key = (self.config.get("tmdb_api_key") or "").strip()
        if not tmdb_key or not imdb_id:
            return ""
        try:
            resp = requests.get(
                f"{TMDB_BASE_URL}/find/{imdb_id}",
                params={"api_key": tmdb_key, "external_source": "imdb_id"},
                timeout=4
            )
            if resp.status_code != 200:
                return ""
            data = resp.json()
            movie_res = data.get("movie_results", [])
            tv_res = data.get("tv_results", [])
            if movie_res:
                tmdb_id = movie_res[0].get("id")
                det_resp = requests.get(
                    f"{TMDB_BASE_URL}/movie/{tmdb_id}",
                    params={"api_key": tmdb_key},
                    timeout=4
                )
                if det_resp.status_code == 200:
                    companies = [c.get("name") for c in det_resp.json().get("production_companies", []) if c.get("name")]
                    return ", ".join(companies[:4])
            elif tv_res:
                tv_id = tv_res[0].get("id")
                det_resp = requests.get(
                    f"{TMDB_BASE_URL}/tv/{tv_id}",
                    params={"api_key": tmdb_key},
                    timeout=4
                )
                if det_resp.status_code == 200:
                    networks = [n.get("name") for n in det_resp.json().get("networks", []) if n.get("name")]
                    companies = [c.get("name") for c in det_resp.json().get("production_companies", []) if c.get("name")]
                    all_c = networks + [c for c in companies if c not in networks]
                    return ", ".join(all_c[:4])
        except Exception as e:
            print(f"Error fetching TMDb companies for IMDb {imdb_id}: {e}")
        return ""
