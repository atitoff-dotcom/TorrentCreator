import re

RUTRACKER_CATEGORIES = {
    "foreign_hd": {"id": 313, "name": "Зарубежное кино (HD Video)"},
    "foreign_serial_hd": {"id": 2366, "name": "Зарубежные сериалы (HD Video)"},
    "russian_hd": {"id": 2200, "name": "Наше кино (HD Video)"},
    "russian_serial_hd": {"id": 2100, "name": "Русские сериалы (HD Video)"},
    "animation_hd": {"id": 539, "name": "Мультфильмы (HD Video)"}
}

def detect_rip_type(filename: str) -> str:
    f = filename.lower()
    if "web-dl" in f or "webdl" in f:
        return "WEB-DL"
    elif "webrip" in f:
        return "WEBRip"
    elif "bdrip" in f or "bluray" in f:
        return "BDRip"
    elif "hdtv" in f:
        return "HDTV"
    elif "dvdrip" in f:
        return "DVDRip"
    return "WEB-DL"

def format_audio_line(track: dict) -> str:
    raw_lang = track.get("language") or "rus"
    if len(raw_lang) <= 3:
        lang = raw_lang.upper()
    else:
        lang = raw_lang.capitalize()
    fmt = track.get("format") or "AC3"
    channels = f"{track.get('channels')} ch" if track.get("channels") else ""
    bitrate = track.get("bitrate") or ""
    desc = track.get("studio_or_desc") or track.get("title") or ""
    title = f"({desc})" if desc else ""
    parts = [lang, fmt, channels, bitrate, title]
    return ", ".join([p for p in parts if p]).strip()

def is_domestic_film(meta: dict) -> bool:
    """Определяет, является ли фильм отечественным (оригинальный язык съемок - русский).
       Если фильм снимался на русском языке - это отечественный фильм.
       Если фильм снимался на иностранном языке (даже в РФ, напр. 'Хардкор') - он зарубежный.
    """
    orig_lang = (meta.get("original_language") or "").lower()
    if orig_lang in ("ru", "rus"):
        return True
    if orig_lang and orig_lang not in ("ru", "rus", "und"):
        return False

    if meta.get("is_russian") is True:
        return True

    countries = (meta.get("countries") or meta.get("country") or "").lower()
    foreign_keywords = [
        "сша", "usa", "великобритани", "uk", "франци", "france", "германи", "germany",
        "япони", "japan", "коре", "korea", "италия", "italy", "испани", "spain",
        "китай", "china", "канада", "canada", "австрали", "australia", "индия", "india"
    ]
    domestic_keywords = ["россия", "ссср", "russia", "ussr", "беларусь", "belarus"]

    has_domestic = any(k in countries for k in domestic_keywords)
    has_foreign = any(k in countries for k in foreign_keywords)

    if has_domestic and not has_foreign:
        return True
    if has_foreign and not has_domestic:
        return False

    title_ru = (meta.get("title_ru") or "").strip().lower()
    title_orig = (meta.get("title_orig") or "").strip().lower()
    if title_ru and title_orig and title_ru == title_orig and re.search(r'[а-яёА-ЯЁ]', title_ru) and not re.search(r'[a-zA-Z]', title_ru):
        return True

    return False

def has_russian_full_subtitles(subtitles: list) -> bool:
    """Проверяет наличие включенных ПОЛНЫХ РУССКИХ субтитров для кода СТ в заголовке Кинозала.
    По правилам Кинозала код СТ означает 'полные русские субтитры'.
    Иностранные субтитры (английские и т.д.) и форсированные (только надписи) как СТ в названии не указываются.
    """
    if not subtitles:
        return False

    for s in subtitles:
        if isinstance(s, dict) and not s.get("enabled", True):
            continue

        # Проверка на forced / только надписи / комментарии
        if s.get("forced") is True:
            continue
        sub_type = (s.get("type") or "").lower()
        if sub_type in ("forced", "форсированные", "надписи", "комментарии", "commentary"):
            continue

        title = (s.get("title") or "").lower()
        if any(w in title for w in ("forced", "надпис", "форс", "табличк", "коммент")):
            continue

        # Проверка на русский язык
        lang = (s.get("language") or "").lower()
        is_russian = (
            "рус" in lang
            or "rus" in lang
            or lang in ("ru", "russian")
            or "рус" in title
        )

        if is_russian:
            return True

    return False

def build_rutracker_title(meta: dict, media: dict, release_opts: dict) -> str:
    title_ru = meta.get("title_ru") or media.get("filename")
    title_orig = meta.get("title_orig") or ""
    director = meta.get("directors") or ""
    first_director = director.split(",")[0].strip() if director else ""
    year = meta.get("year") or ""
    genres = meta.get("genres") or ""
    countries = meta.get("countries") or ""
    
    # Видео характеристики
    rip_type = detect_rip_type(media.get("filename", ""))
    resolution = media.get("resolution") or "1080p"
    if "1920x1080" in resolution:
        res_tag = "1080p"
    elif "3840x2160" in resolution or "2160" in resolution:
        res_tag = "2160p, 4K"
    elif "1280x720" in resolution:
        res_tag = "720p"
    else:
        res_tag = resolution

    video_tag = f"{rip_type} [{res_tag}]"

    # Озвучка
    audio_tracks = release_opts.get("audio_tracks", [])
    subtitles = release_opts.get("subtitle_tracks") if release_opts.get("subtitle_tracks") is not None else media.get("subtitles", [])
    has_subtitles = has_russian_full_subtitles(subtitles)
    is_domestic = is_domestic_film(meta)

    if is_domestic:
        voice_tag = ""
    elif audio_tracks:
        voice_tag = build_kinozal_translation_title(audio_tracks, False, has_subtitles, release_opts.get("translation_type_label", "ПМ"))
    else:
        trans_type = release_opts.get("translation_type_label", "Профессиональный (многоголосый)")
        studio = release_opts.get("studio", "").strip()
        voice_tag = f"{trans_type} ({studio})" if studio else trans_type

    # Сериальные метки
    is_series = meta.get("is_series", False)
    if is_series:
        season_num = release_opts.get("season", 1)
        episodes_str = release_opts.get("episodes", "Серии 1-X")
        serial_part = f" / Сезон: {season_num} / {episodes_str}"
    else:
        serial_part = ""

    director_part = f" ({first_director})" if first_director else ""
    orig_part = f" / {title_orig}" if (title_orig and not is_domestic and title_orig.lower() != title_ru.lower()) else ""
    voice_part = f" [{voice_tag}]" if voice_tag else ""

    # Строгий заголовок RuTracker:
    # Русское название / Оригинальное (Режиссер) [Год, Жанр, Качество] [Озвучка]
    return f"{title_ru}{orig_part}{serial_part}{director_part} [{year}, {genres}, {video_tag}]{voice_part}"

def build_rutracker_bbcode(meta: dict, media: dict, release_opts: dict, uploaded_screens: list) -> str:
    poster_url = meta.get("poster_url") or ""
    poster_bb = f"[align=center][img=right]{poster_url}[/img][/align]\n" if poster_url else ""

    # Скриншоты
    screens_bb = ""
    if uploaded_screens:
        # Группируем по 3-4 в ряд
        bb_list = [s.get("bb_code", "") for s in uploaded_screens if s.get("bb_code")]
        screens_bb = " ".join(bb_list)
    else:
        screens_bb = "[i]Скриншоты добавляются...[/i]"

    # Список аудиодорожек
    audio_lines = []
    audio_tracks_list = release_opts.get("audio_tracks") or media.get("audio_tracks", [])
    for idx, track in enumerate(audio_tracks_list):
        audio_lines.append(f"[b]Аудио {idx+1}:[/b] {format_audio_line(track)}")
    audio_block = "\n".join(audio_lines) if audio_lines else "[b]Аудио:[/b] - "

    # Субтитры
    subtitles = release_opts.get("subtitle_tracks") if release_opts.get("subtitle_tracks") is not None else media.get("subtitles", [])
    enabled_subs = [s for s in subtitles if s.get("enabled", True)]
    sub_text = format_subtitles_text(enabled_subs) or "нет"

    # Сборка монолитного BB-кода
    bb = f"""{poster_bb}[b]Год выпуска:[/b] {meta.get('year', '')}
[b]Страна:[/b] {meta.get('countries', '')}
[b]Жанр:[/b] {meta.get('genres', '')}
[b]Продолжительность:[/b] {media.get('duration', '')}

[b]Режиссер:[/b] {meta.get('directors', '')}
[b]В ролях:[/b] {meta.get('actors', '')}

[b]Описание:[/b]
{meta.get('plot', '')}

[hr]
[b]Качество видео:[/b] {detect_rip_type(media.get('filename', ''))}
[b]Формат видео:[/b] MKV
[b]Видео:[/b] {media.get('resolution', '')} at {media.get('fps', '')} fps, {media.get('video_codec', '')}, ~{media.get('video_bitrate', '')}
{audio_block}
[b]Субтитры:[/b] {sub_text}

[hr]
[b]Скриншоты:[/b]
[align=center]
{screens_bb}
[/align]

[spoiler="MediaInfo"]
{media.get('raw_mediainfo', '') or 'MediaInfo: ' + media.get('filename', '')}
[/spoiler]
"""
    return bb.strip()

# Словари языков для Кинозала
LANG_RU_MAP = {
    "ru": "Русский", "rus": "Русский", "russian": "Русский",
    "en": "Английский", "eng": "Английский", "english": "Английский",
    "ja": "Японский", "jpn": "Японский", "japanese": "Японский",
    "ko": "Корейский", "kor": "Корейский", "korean": "Корейский",
    "fr": "Французский", "fra": "Французский", "fre": "Французский",
    "de": "Немецкий", "deu": "Немецкий", "ger": "Немецкий",
    "it": "Итальянский", "ita": "Итальянский",
    "es": "Испанский", "spa": "Испанский",
    "zh": "Китайский", "zho": "Китайский", "chi": "Китайский",
    "uk": "Украинский", "ukr": "Украинский",
    "pl": "Польский", "pol": "Польский",
    "pt": "Португальский", "por": "Португальский",
}

SUB_RU_MAP = {
    "ru": "Русские", "rus": "Русские", "russian": "Русские", "русский": "Русские",
    "en": "английские", "eng": "английские", "english": "английские", "английский": "английские",
    "uk": "украинские", "ukr": "украинские", "ukrainian": "украинские", "украинский": "украинские",
    "ja": "японские", "jpn": "японские", "japanese": "японские", "японский": "японские",
    "ko": "корейские", "kor": "корейские", "korean": "корейские", "корейский": "корейские",
    "fr": "французские", "fra": "французские", "fre": "французские", "french": "французские", "французский": "французские",
    "de": "немецкие", "deu": "немецкие", "ger": "немецкие", "german": "немецкие", "немецкий": "немецкие",
    "it": "итальянские", "ita": "итальянские", "italian": "итальянские", "итальянский": "итальянские",
    "es": "испанские", "spa": "испанские", "spanish": "испанские", "испанский": "испанские",
    "zh": "китайские", "zho": "китайские", "chi": "китайские", "chinese": "китайские", "китайский": "китайские",
    "pl": "польские", "pol": "польские", "polish": "польские", "польский": "польские",
    "pt": "португальские", "por": "португальские", "portuguese": "португальские", "португальский": "португальские",
}

IGNORED_STUDIO_WORDS = {
    "dub", "дуб", "дубляж", "дублированный",
    "mvo", "пм", "многоголосый", "профессиональный", "проф.", "проф",
    "dvo", "пд", "двухголосый",
    "pvo", "по", "одноголосый",
    "avo", "ап", "авторский",
    "lvo", "ло", "любительский",
    "lmvo", "лм", "ldvo", "лд",
    "original", "оригинал", "бп", "ст",
    "rus", "рус", "русский", "eng", "англ", "английский",
    "2ch", "6ch", "ac3", "dts", "aac", "eac3", "flac"
}

def format_subtitles_text(subtitles: list) -> str:
    """Форматирует строку субтитров по правилам Кинозала:
       Русские (форсированные, полные), английские
       Первое слово с большой буквы, остальные с маленькой через запятую.
    """
    if not subtitles:
        return ""

    lang_map = {}
    for s in subtitles:
        if isinstance(s, dict) and not s.get("enabled", True):
            continue
        raw_lang = (s.get("language") or "Русский").strip().lower()
        if raw_lang in SUB_RU_MAP:
            adj = SUB_RU_MAP[raw_lang]
        elif raw_lang[:3] in SUB_RU_MAP:
            adj = SUB_RU_MAP[raw_lang[:3]]
        elif raw_lang in ("und", "none", ""):
            adj = "Русские"
        else:
            adj = f"{raw_lang.capitalize()} субтитры"

        type_key = (s.get("type") or "full").lower()
        is_forced = s.get("forced", False) or type_key == "forced"
        type_note = ""
        if is_forced:
            type_note = "форсированные"
        elif type_key == "sdh":
            type_note = "SDH"
        elif type_key == "commentary":
            type_note = "комментарии"

        author = (s.get("title") or s.get("author") or "").strip()
        if author and author.lower() not in (
            "forced", "full", "sdh", "utf-8", "srt", "ass", "pgs", "vobsub",
            "subtitles", "субтитры", "русский", "английский", "rus", "eng", "und"
        ):
            type_note = f"{type_note} - {author}" if type_note else author

        # Группируем по приведенному к нижнему регистру названию
        norm_key = adj.lower()
        if norm_key not in lang_map:
            lang_map[norm_key] = {"display": adj, "notes": []}
        if type_note and type_note not in lang_map[norm_key]["notes"]:
            lang_map[norm_key]["notes"].append(type_note)

    if not lang_map:
        return ""

    result_items = []
    for info in lang_map.values():
        name = info["display"].lower()
        notes = info["notes"]
        if notes:
            result_items.append(f"{name} ({', '.join(notes)})")
        else:
            result_items.append(name)

    if not result_items:
        return ""

    # Первое слово с большой буквы
    first = result_items[0]
    first_cap = first[0].upper() + first[1:] if len(first) > 1 else first.upper()
    return ", ".join([first_cap] + result_items[1:])

KZ_CODE_MAP = {
    "dub": "ДБ",
    "mvo": "ПМ",
    "dvo": "ПД",
    "pvo": "ПО",
    "avo": "АП",
    "lvo": "ЛО",
    "ldvo": "ЛД",
    "lmvo": "ЛМ",
    "ru": "РУ",
    "original": "БП",
    "sub": "СТ",
    "nk": "НК",
    "tk": "ТК",
    "dub_ts": "ДБ (TS)",
    "funny": "(Смешной перевод)",
    "ai_dub": "ДБ (AI)",
    "ai_mvo": "ЛМ (AI)",
    "ai_ldvo": "ЛД (AI)",
    "ai_lvo": "ЛО (AI)",
}

KZ_TRANSLATION_NAME_MAP = {
    "dub": "Дублированный",
    "mvo": "Профессиональный многоголосый",
    "dvo": "Профессиональный двухголосый",
    "pvo": "Профессиональный одноголосый",
    "avo": "Авторский",
    "lvo": "Любительский одноголосый",
    "ldvo": "Любительский двухголосый",
    "lmvo": "Любительский многоголосый",
    "ru": "Русский",
    "original": "Отсутствует",
    "sub": "Полные субтитры",
    "nk": "Не требуется",
    "tk": "Тифлокомментарии",
    "dub_ts": "Дублированный (TS)",
    "funny": "Пародийный перевод",
    "ai_dub": "Дублированный (AI)",
    "ai_mvo": "Любительский многоголосый (AI)",
    "ai_ldvo": "Любительский двухголосый (AI)",
    "ai_lvo": "Любительский одноголосый (AI)",
}

def format_kinozal_size(bytes_val: int) -> str:
    """Форматирует размер по правилам Кинозала: только МБ и ГБ заглавными русскими, десятичные через точку"""
    if not bytes_val:
        return "0 МБ"
    gb = bytes_val / (1024 ** 3)
    if gb >= 1.0:
        return f"{gb:.2f} ГБ"
    mb = bytes_val / (1024 ** 2)
    if mb >= 10:
        return f"{int(round(mb))} МБ"
    return f"{mb:.2f} МБ"

def detect_kinozal_quality(media: dict) -> str:
    """Определяет качество раздачи строго латиницей по правилам Кинозала"""
    filename = (media.get("filename") or "").lower()
    width = media.get("width", 0) or 0
    height = media.get("height", 0) or 0
    scan = media.get("scan_type", "Progressive")
    vcodec = (media.get("video_codec") or "").upper()

    res = ""
    if width > 0 and height > 0:
        if height >= 4000 or width >= 7000:
            res = "4320p"
        elif height >= 2100 or width >= 3800:
            res = "2160p"
        elif height >= 1400 or width >= 2500:
            res = "1440p"
        elif height >= 900 or width >= 1800:
            res = "1080i" if scan == "Interlaced" else "1080p"
        elif height >= 650 or width >= 1200:
            res = "720p"
        elif height >= 500 or width >= 900:
            res = "576p"
        elif height >= 400 or width >= 700:
            res = "480p"
    else:
        if "4320" in filename or "8k" in filename:
            res = "4320p"
        elif "2160" in filename or "4k" in filename:
            res = "2160p"
        elif "1440" in filename or "2k" in filename:
            res = "1440p"
        elif "1080" in filename:
            res = "1080i" if "1080i" in filename or scan == "Interlaced" else "1080p"
        elif "720" in filename:
            res = "720p"
        elif "576" in filename:
            res = "576p"
        elif "480" in filename:
            res = "480p"

    if "remux" in filename:
        return f"Blu-Ray Remux ({res})" if res else "Blu-Ray Remux (1080p)"
    elif "blu-ray" in filename or "bluray" in filename or "bdmv" in filename:
        return f"Blu-Ray ({res})" if res else "Blu-Ray (1080p)"
    elif "bdrip" in filename:
        if res:
            return f"BDRip ({res})"
        if "avc" in filename or "AVC" in vcodec or "H.264" in vcodec:
            return "BDRip (AVC)"
        elif "av1" in filename or "AV1" in vcodec:
            return "BDRip (AV1)"
        elif "hevc" in filename or "HEVC" in vcodec:
            return "BDRip (HEVC)"
        return "BDRip"
    elif "web-dlrip" in filename or "webdlrip" in filename:
        if res:
            return f"WEB-DLRip ({res})"
        return "WEB-DLRip (AVC)" if ("avc" in filename or "AVC" in vcodec) else "WEB-DLRip"
    elif "web-dl" in filename or "webdl" in filename:
        return f"WEB-DL ({res})" if res else "WEB-DL (1080p)"
    elif "webrip" in filename:
        return f"WEBRip ({res})" if res else "WEBRip (1080p)"
    elif "hdtvrip" in filename:
        if res:
            return f"HDTVRip ({res})"
        return "HDTVRip (AVC)" if ("avc" in filename or "AVC" in vcodec) else "HDTVRip"
    elif "hdtv" in filename:
        return f"HDTV ({res})" if res else "HDTV (1080i)"
    elif "dvd-9" in filename or "dvd9" in filename:
        return "DVD-9"
    elif "dvd-5" in filename or "dvd5" in filename:
        return "DVD-5"
    elif "dvdrip" in filename:
        return "DVDRip (AVC)" if ("avc" in filename or "AVC" in vcodec) else "DVDRip"

    if res in ("2160p", "4320p", "1440p"):
        return f"WEB-DL ({res})"
    elif res in ("1080p", "1080i"):
        return f"BDRip ({res})"
    elif res == "720p":
        return "BDRip (720p)"
    return "WEB-DL"

def detect_video_features(media: dict, release_opts: dict = None) -> list:
    """Определяет особенности видеоряда строго по правилам Кинозала (docs/new_kinozal.md):
       Формат 3D, 8K/4K/2K, HEVC/AV1/VP9, SDR/HDR/HDR10+/HLG, Dolby Vision (DV), Open Matte, Transfer.
    """
    opts = release_opts or {}
    features = []
    width = media.get("width", 0) or 0
    height = media.get("height", 0) or 0
    codec = (media.get("video_codec") or "").upper()
    comm_name = (media.get("video_commercial_name") or "").upper()
    hdr = (media.get("hdr_format") or "").upper()
    hdr_prof = (media.get("hdr_format_profile") or "").upper()
    transfer = (media.get("transfer_characteristics") or "").upper()
    filename = (media.get("filename") or "").lower()

    # 1. Формат 3D (указывается в начале особенностей видеоряда)
    if "3d" in filename or opts.get("is_3d"):
        if "2d" in filename and "3d" in filename:
            if "анаглиф" in filename or "anaglyph" in filename:
                features.append("2D, 3D (Анаглиф)")
            else:
                features.append("2D, 3D")
        elif "hsbs" in filename:
            features.append("3D (HSBS)")
        elif "hou" in filename:
            features.append("3D (HOU)")
        elif "sbs" in filename:
            features.append("3D (SBS)")
        elif "ou" in filename:
            features.append("3D (OU)")
        elif "анаглиф" in filename or "anaglyph" in filename:
            features.append("3D (Анаглиф)")
        else:
            features.append("3D")

    # 2. Разрешение (только 8K, 4K, 2K - 1080p/720p здесь не указываются)
    if width > 0 and height > 0:
        is_8k = width >= 7600 or height >= 4200
        is_4k = (width >= 3800 or height >= 2100) and not is_8k
        is_2k = (width >= 2500 or height >= 1400) and not is_4k and not is_8k
    else:
        is_8k = "4320" in filename or "8k" in filename
        is_4k = ("2160" in filename or "4k" in filename) and not is_8k
        is_2k = ("1440" in filename or "2k" in filename) and not is_4k and not is_8k

    if is_8k:
        features.append("8K")
    elif is_4k:
        features.append("4K")
    elif is_2k:
        features.append("2K")

    # 3. Кодек (HEVC, AV1, VP9)
    if "AV1" in codec or "av1" in filename:
        features.append("AV1")
    elif "HEVC" in codec or "H.265" in codec or "HEVC" in comm_name or "hevc" in filename or "x265" in filename:
        features.append("HEVC")
    elif "VP9" in codec or "vp9" in filename:
        features.append("VP9")

    # 4. Диапазон яркости и Dolby Vision
    is_dovi = (
        "DOLBY VISION" in hdr
        or "DV" in hdr
        or "dovi" in filename
        or "dolby vision" in filename
        or "dv" in filename.split(".")
    )

    if is_dovi:
        # Базовый слой HDR / HDR10+
        if "HDR10+" in hdr or "hdr10+" in filename:
            features.append("HDR10+")
        elif (
            "HDR" in hdr
            or "SMPTE ST 2086" in hdr
            or "SMPTE ST 2084" in transfer
            or "PQ" in transfer
            or "remux" in filename
            or "web" in filename
            or "hdr" in filename
        ):
            features.append("HDR")

        # Определение профиля Dolby Vision
        # Rule: Для раздач Dolby Vision указание профиля обязательно за исключением раздач Blu-Ray и Blu-Ray Remux в папке BDMV
        is_remux_or_bdmv = ("remux" in filename or "blu-ray" in filename or "bluray" in filename or "bdmv" in filename)
        is_p8 = bool(re.search(r'(profile\s*8|\bp8\b|08\.|dvhe\.08|dvh1\.08|dovi\.08)', (hdr_prof + " " + hdr + " " + filename).lower()))
        is_p7 = bool(re.search(r'(profile\s*7|\bp7\b|07\.|dvhe\.07|dvh1\.07|dovi\.07)', (hdr_prof + " " + hdr + " " + filename).lower()))
        is_tv = "tv" in hdr_prof.lower() or "dv tv" in filename or "dolby vision tv" in filename

        if is_tv:
            features.append("Dolby Vision TV")
        elif is_p8:
            features.append("Dolby Vision P8")
        elif is_p7 and not is_remux_or_bdmv:
            features.append("Dolby Vision P7")
        else:
            features.append("Dolby Vision")
    elif "HDR10+" in hdr or "SMPTE ST 2094" in hdr or "hdr10+" in filename:
        features.append("HDR10+")
    elif "HLG" in hdr or "ARIB STD-B67" in transfer or "hlg" in filename:
        features.append("HLG")
    elif "HDR" in hdr or "PQ" in transfer or "SMPTE ST 2084" in transfer or "hdr10" in filename or "hdr" in filename:
        features.append("HDR")
    elif is_4k or is_2k or is_8k:
        # SDR указывается только для 2K, 4K, 8K раздач с диапазоном яркости SDR
        features.append("SDR")

    # 5. Open Matte
    if "open matte" in filename or "open.matte" in filename or opts.get("open_matte"):
        features.append("Open Matte")

    # 6. Transfer (RUS Transfer, GER Transfer и т.д.)
    transfer_country = opts.get("transfer_country")
    if not transfer_country:
        m_trans = re.search(r'\b(rus|ger|fra|ita|usa|uk|jpn)\s*transfer\b', filename, re.IGNORECASE)
        if m_trans:
            transfer_country = m_trans.group(1).upper()
    if transfer_country:
        features.append(f"{transfer_country} Transfer")

    return features

def clean_audio_codec_name(raw_format: str, comm_name: str = "") -> str:
    """Приводит название аудиокодека к стандартам Кинозала"""
    f = (raw_format or "").upper()
    c = (comm_name or "").upper()
    if "E-AC-3 JOC" in f or "ATMOS" in c:
        return "E-AC3+Atmos"
    elif "E-AC-3" in f or "EAC3" in f:
        return "E-AC3"
    elif "AC-3" in f or "AC3" in f:
        return "AC3"
    elif "TRUEHD" in f:
        return "TrueHD+Atmos" if "ATMOS" in c else "TrueHD"
    elif "DTS-HD MA" in c or "MASTER AUDIO" in c:
        return "DTS-HD MA"
    elif "DTS" in f:
        return "DTS"
    elif "FLAC" in f:
        return "FLAC"
    elif "AAC" in f:
        return "AAC"
    elif "OPUS" in f:
        return "Opus"
    elif "MPEG" in f or "MP3" in f:
        return "MP3"
    elif "VORBIS" in f or "OGG" in f:
        return "Vorbis"
    return raw_format or "AC3"

def format_kinozal_audio_track(track: dict, is_first: bool = False) -> str:
    """Форматирует одну аудиодорожку: Язык (аудио-кодек, количество каналов аудио ch, аудио-битрейт Кбит/с)"""
    lang_code = (track.get("language") or "und").lower()
    lang_name = LANG_RU_MAP.get(lang_code, lang_code.capitalize())
    if not is_first:
        lang_name = lang_name.lower()

    codec = clean_audio_codec_name(track.get("format", ""), track.get("commercial_name", ""))
    channels = track.get("channels", 2)
    ch_str = f"{channels} ch"

    bitrate_str = ""
    raw_bitrate = track.get("bitrate", "")
    if raw_bitrate:
        nums = re.findall(r"\d+", str(raw_bitrate))
        if nums:
            bitrate_str = f"{nums[0]} Кбит/с"

    inner_parts = [codec, ch_str]
    if bitrate_str:
        inner_parts.append(bitrate_str)

    return f"{lang_name} ({', '.join(inner_parts)})"

def format_kinozal_release_audio(track: dict, idx: int, fallback_trans_name: str = "", fallback_studio: str = "") -> str:
    """Форматирует строку звуковой дорожки для вкладки [pagesd=Релиз] по правилам Кинозала:
       Аудио 01: Русский / 48.0 KHz, AAC, 2 ch, ~128 Kbps / Многоголосый - СТС
    """
    raw_lang = (track.get("language") or "und").lower()
    if raw_lang in LANG_RU_MAP:
        lang = LANG_RU_MAP[raw_lang]
    elif track.get("language") and track.get("language") not in ("und", "None"):
        lang = str(track.get("language")).strip().capitalize()
    else:
        lang = "Русский"

    # Частота дискретизации (например, 48.0 KHz)
    sr = track.get("sampling_rate")
    sr_str = ""
    if sr:
        try:
            sr_num = float(re.findall(r"[\d.]+", str(sr))[0])
            if sr_num > 1000:
                sr_num = sr_num / 1000.0
            sr_str = f"{sr_num:.1f} KHz"
        except Exception:
            sr_str = str(sr)

    # Кодек
    fmt = clean_audio_codec_name(track.get("format", ""), track.get("commercial_name", ""))

    # Количество каналов (2 ch, 6 ch)
    ch = track.get("channels", 2)
    ch_str = f"{ch} ch" if ch else ""

    # Битрейт (~128 Kbps)
    br_str = ""
    raw_br = track.get("bitrate", "")
    if raw_br:
        nums = re.findall(r"\d+", str(raw_br))
        if nums:
            br_str = f"~{nums[0]} Kbps"

    specs = [s for s in [sr_str, fmt, ch_str, br_str] if s]
    spec_str = ", ".join(specs)

    # Описание перевода / студии / оригинала
    type_key = track.get("translation_type_key", "")
    user_desc = (track.get("studio_or_desc") or track.get("title") or fallback_studio or "").strip()
    trans_name = KZ_TRANSLATION_NAME_MAP.get(type_key, fallback_trans_name or "Многоголосый")

    if type_key == "original" or (lang not in ("Русский", "rus") and not user_desc):
        desc = user_desc or "Original"
    elif type_key == "avo":
        if "автор" not in user_desc.lower():
            desc = f"Авторский - {user_desc}" if user_desc else "Авторский"
        else:
            desc = user_desc
    elif type_key == "mvo":
        if "многоголос" not in user_desc.lower() and "профессиональн" not in user_desc.lower():
            desc = f"Многоголосый - {user_desc}" if user_desc else "Многоголосый"
        else:
            desc = user_desc
    elif type_key == "dvo":
        if "двухголос" not in user_desc.lower():
            desc = f"Двухголосый - {user_desc}" if user_desc else "Двухголосый"
        else:
            desc = user_desc
    elif type_key == "pvo":
        if "одноголос" not in user_desc.lower():
            desc = f"Одноголосый - {user_desc}" if user_desc else "Одноголосый"
        else:
            desc = user_desc
    elif type_key == "dub":
        if "дубл" not in user_desc.lower():
            desc = f"Дублированный - {user_desc}" if user_desc else "Дублированный"
        else:
            desc = user_desc
    elif type_key == "lmvo":
        desc = f"Любительский многоголосый - {user_desc}" if user_desc else "Любительский многоголосый"
    elif type_key == "ldvo":
        desc = f"Любительский двухголосый - {user_desc}" if user_desc else "Любительский двухголосый"
    elif type_key == "lvo":
        desc = f"Любительский одноголосый - {user_desc}" if user_desc else "Любительский одноголосый"
    elif type_key == "ru":
        if user_desc and user_desc.lower() not in ("оригинал", "original"):
            desc = f"Оригинал ({user_desc})"
        else:
            desc = "Оригинал"
    else:
        desc = f"{trans_name} - {user_desc}" if user_desc else trans_name

    num_str = f"{idx:02d}"
    if spec_str:
        return f"Аудио {num_str}: {lang} / {spec_str} / {desc}"
    else:
        return f"Аудио {num_str}: {lang} / {desc}"

def has_kinozal_tk(audio_tracks: list, subtitles: list = None, release_opts: dict = None) -> bool:
    """Проверяет наличие тифлокомментариев (ТК).
    По правилам Кинозала код ТК выносится в отдельную позицию через слэш:
    Шаблон: Название / Оригинальное название / Год / Код перевода / ТК / Качество
    """
    opts = release_opts or {}
    if opts.get("has_tk") or opts.get("tk"):
        return True

    tk_keywords = ["тифло", "тифлокомментар", "audio description", "visual description", "descriptive audio"]

    for t in (audio_tracks or []):
        if not isinstance(t, dict):
            continue
        if t.get("translation_type_key") == "tk":
            return True
        title = (t.get("title") or t.get("studio_or_desc") or "").lower()
        if any(k in title for k in tk_keywords):
            return True

    for s in (subtitles or []):
        if not isinstance(s, dict):
            continue
        title = (s.get("title") or "").lower()
        if any(k in title for k in tk_keywords):
            return True

    return False

def build_kinozal_translation_title(audio_tracks: list, is_domestic: bool, has_subtitles: bool, fallback_code: str = "ПМ") -> str:
    """Группирует коды перевода для названия раздачи по правилам Кинозала (docs/new_kinozal.md):
       например: 'ДБ, 2 х ПД, 3 х АП (Гаврилов, Живов, Володарский)'
       или: 'ПМ (Культура, R5), СТ'
       или: 'РУ'
    """
    if is_domestic:
        return "РУ"
    if not audio_tracks:
        code = fallback_code
        if has_subtitles and "СТ" not in code:
            code = f"{code}, СТ"
        return code

    code_counts = {}
    code_studios = {}
    author_names = []
    has_russian = False

    for t in audio_tracks:
        lang = (t.get("language") or "").lower()
        type_key = t.get("translation_type_key", "mvo")
        desc = (t.get("studio_or_desc") or "").strip()

        # Тифлокомментарии выносятся в отдельную позицию / ТК /, не дублируем их внутри кодов
        if type_key == "tk":
            continue

        if "рус" in lang or type_key in (
            "dub", "mvo", "dvo", "pvo", "avo", "lmvo", "ldvo", "lvo", "ru",
            "ai_dub", "ai_mvo", "ai_ldvo", "ai_lvo", "dub_ts", "funny"
        ):
            has_russian = True

        if type_key == "avo":
            if desc:
                parts = desc.split()
                last_name = parts[-1] if parts else desc
                if last_name not in author_names:
                    author_names.append(last_name)
            code_counts["АП"] = code_counts.get("АП", 0) + 1
        elif type_key in KZ_CODE_MAP:
            c = KZ_CODE_MAP[type_key]
            if c not in ("БП", "СТ", "ТК"):
                code_counts[c] = code_counts.get(c, 0) + 1
                if desc and desc.lower() not in IGNORED_STUDIO_WORDS:
                    code_studios.setdefault(c, []).append(desc)

    if not has_russian:
        return "БП, СТ" if has_subtitles else "БП"

    order = [
        "ДБ", "ДБ (TS)", "ПМ", "ПД", "ПО",
        "ЛМ", "ЛД", "ЛО",
        "АП",
        "(Смешной перевод)",
        "ДБ (AI)", "ЛМ (AI)", "ЛД (AI)", "ЛО (AI)",
        "РУ", "НК"
    ]
    result_parts = []

    for c in order:
        cnt = code_counts.get(c, 0)
        if cnt == 0:
            continue
        if c == "АП":
            if author_names:
                names_str = ", ".join(author_names)
                if cnt > 1:
                    result_parts.append(f"{cnt} х АП ({names_str})")
                else:
                    result_parts.append(f"АП ({names_str})")
            else:
                result_parts.append(f"{cnt} х АП" if cnt > 1 else "АП")
        elif c == "(Смешной перевод)":
            result_parts.append(c)
        else:
            studios = code_studios.get(c, [])
            studios_clean = []
            for s in studios:
                if s not in studios_clean:
                    studios_clean.append(s)
            studios_str = ", ".join(studios_clean)
            if studios_str:
                if cnt > 1:
                    result_parts.append(f"{cnt} х {c} ({studios_str})")
                else:
                    result_parts.append(f"{c} ({studios_str})")
            else:
                if cnt > 1:
                    result_parts.append(f"{cnt} х {c}")
                else:
                    result_parts.append(c)

    if not result_parts:
        result_parts.append(fallback_code)

    if has_subtitles and "СТ" not in result_parts:
        result_parts.append("СТ")

    return ", ".join(result_parts)

def detect_kinozal_category(meta: dict, is_series: bool, is_domestic: bool) -> str:
    """Определяет ID раздела Кинозала (<select id='type1'>) на основе метаданных"""
    genres_raw = (meta.get("genre") or meta.get("genres") or "").lower()
    country_raw = (meta.get("country") or meta.get("countries") or "").lower()

    # 1. Мультфильмы и Аниме
    if "аниме" in genres_raw or "anime" in genres_raw:
        return "20"  # Мульт - Аниме
    if "мульт" in genres_raw or "анимац" in genres_raw or "cartoon" in genres_raw or "animation" in genres_raw:
        return "22" if is_domestic else "21"  # Мульт - Русский / Буржуйский

    # 2. Сериалы
    if is_series:
        return "45" if is_domestic else "46"  # Сериал - Русский / Буржуйский

    # 3. Документальные, Спорт, Концерты, ТВ-шоу
    if "документ" in genres_raw or "documentary" in genres_raw:
        return "18"  # Кино - Документальный
    if "спорт" in genres_raw or "sport" in genres_raw:
        return "37"  # Кино - Спорт
    if "концерт" in genres_raw or "музык" in genres_raw:
        return "48"  # Кино - Концерт
    if "клип" in genres_raw or "видеоклип" in genres_raw:
        return "1"   # Другое - Видеоклипы
    if "передач" in genres_raw or "шоу" in genres_raw or "ток-шоу" in genres_raw:
        return "49" if is_domestic else "50"  # Передачи / ТВ-шоу / ТВ-шоу Мир
    if "театр" in genres_raw or "опера" in genres_raw or "балет" in genres_raw:
        return "38"  # Кино - Театр, Опера, Балет
    if "эротик" in genres_raw or "erotic" in genres_raw:
        return "16"  # Кино - Эротика

    # 4. По географии (Индийское, Азиатское, Наше Кино)
    if "индия" in country_raw or "india" in country_raw or "индийск" in genres_raw:
        return "39"  # Кино - Индийское

    asian_keys = ["япония", "корея", "китай", "гонконг", "тайвань", "таиланд", "вьетнам", "japan", "korea", "china", "hong kong"]
    if any(k in country_raw for k in asian_keys):
        return "47"  # Кино - Азиатский

    # Отечественные фильмы (СССР, Россия)
    if is_domestic:
        return "10"  # Кино - Наше Кино

    # 5. Зарубежные фильмы по жанрам
    if "комед" in genres_raw or "comedy" in genres_raw:
        return "8"   # Кино - Комедия
    if "боевик" in genres_raw or "action" in genres_raw or "военн" in genres_raw or "war" in genres_raw:
        return "6"   # Кино - Боевик / Военный
    if "триллер" in genres_raw or "thriller" in genres_raw or "детектив" in genres_raw or "криминал" in genres_raw or "crime" in genres_raw:
        return "15"  # Кино - Триллер / Детектив
    if "фантастик" in genres_raw or "sci-fi" in genres_raw or "science fiction" in genres_raw:
        return "13"  # Кино - Фантастика
    if "фэнтези" in genres_raw or "fantasy" in genres_raw:
        return "14"  # Кино - Фэнтези
    if "ужас" in genres_raw or "horror" in genres_raw or "мистик" in genres_raw:
        return "24"  # Кино - Ужас / Мистика
    if "приключен" in genres_raw or "adventure" in genres_raw:
        return "11"  # Кино - Приключения
    if "истор" in genres_raw or "history" in genres_raw:
        return "9"   # Кино - Исторический
    if "мелодрам" in genres_raw or "romance" in genres_raw:
        return "35"  # Кино - Мелодрама
    if "детск" in genres_raw or "семейн" in genres_raw or "family" in genres_raw:
        return "12"  # Кино - Детский / Семейный
    if "драма" in genres_raw or "drama" in genres_raw:
        return "17"  # Кино - Драма

    return "0"

def build_kinozal_fields(meta: dict, media: dict, release_opts: dict, uploaded_screens: list) -> dict:
    """Формирует структурированный словарь полей строго по правилам Кинозала (docs/kinozal.md)"""
    title_ru = (meta.get("title_ru") or media.get("filename", "")).strip()
    title_orig = (meta.get("title_orig") or "").strip()
    year = str(meta.get("year", "")).strip()
    countries = (meta.get("countries") or "").strip()

    # Определение отечественного фильма
    is_domestic = is_domestic_film(meta)

    # 1. Определение кодов перевода и аудиодорожек
    audio_tracks = release_opts.get("audio_tracks") or media.get("audio_tracks", [])
    trans_key = release_opts.get("translation_type_key", "mvo")
    studio = release_opts.get("studio", "").strip()

    if is_domestic:
        voice_code = "РУ"
        trans_name = "Русский"
    else:
        voice_code = KZ_CODE_MAP.get(trans_key, "ПМ")
        trans_name = KZ_TRANSLATION_NAME_MAP.get(trans_key, release_opts.get("translation_type_label", "Профессиональный многоголосый"))

    subtitles = release_opts.get("subtitle_tracks") if release_opts.get("subtitle_tracks") is not None else media.get("subtitles", [])
    enabled_subs = [s for s in subtitles if s.get("enabled", True)]
    has_russian_subs = has_russian_full_subtitles(enabled_subs)
    voice_code_full = build_kinozal_translation_title(audio_tracks, is_domestic, has_russian_subs, voice_code)

    # Особенности видеоряда
    video_features = detect_video_features(media, release_opts)
    features_str = ", ".join(video_features) if video_features else ""

    # Качество
    quality = detect_kinozal_quality(media)

    # Проверка на тифлокомментарии (ТК)
    has_tk = has_kinozal_tk(audio_tracks, enabled_subs, release_opts)

    # Сериальные метки
    is_series = meta.get("is_series", False)
    season_num = release_opts.get("season", 1)
    episodes_str = str(release_opts.get("episodes") or release_opts.get("episodes_str") or meta.get("episodes") or "").strip()
    episodes_count = release_opts.get("episodes_count", 0) or meta.get("episodes_count", 0)

    title_main_part = title_ru
    if is_series:
        if episodes_str:
            if "сезон" in episodes_str.lower() or "сери" in episodes_str.lower():
                title_main_part = f"{title_ru} ({episodes_str})"
            elif season_num and int(season_num) > 1:
                title_main_part = f"{title_ru} ({season_num} сезон: {episodes_str})"
            else:
                title_main_part = f"{title_ru} ({episodes_str})"
        elif episodes_count:
            if season_num and int(season_num) > 1:
                title_main_part = f"{title_ru} ({season_num} сезон: 1-{episodes_count} серии из {episodes_count})"
            else:
                title_main_part = f"{title_ru} ({episodes_count} серии из {episodes_count})" if episodes_count > 1 else f"{title_ru} (1 серия)"
        else:
            title_main_part = f"{title_ru} ({season_num} сезон)" if (season_num and int(season_num) > 1) else title_ru

    # Сборка основного заголовка (до 150 символов)
    # Правило: Если русское и оригинальное совпадают (отечественные), оставляем только оригинальное
    title_components = []
    if is_domestic:
        title_components.append(title_main_part or title_orig)
    else:
        title_components.append(title_main_part)
        if title_orig and title_orig.lower() != title_ru.lower():
            title_components.append(title_orig)

    if year:
        title_components.append(str(year))

    title_components.append(voice_code_full)

    # Тифлокомментарии (ТК) выносятся отдельной позицией через косую черту по правилам Кинозала
    if has_tk:
        title_components.append("ТК")

    if features_str:
        title_components.append(features_str)

    title_components.append(quality)

    title_full = " / ".join(title_components)
    # Контроль длины заголовка (лимит Кинозала 150 знаков)
    if len(title_full) > 150 and studio and f" ({studio})" in title_full:
        title_full = title_full.replace(f" ({studio})", "")
    if len(title_full) > 150:
        title_full = title_full[:147] + "..."

    # 2. Поле "Предварительное описание" (BB-код, расширенный режим)
    # Жанры: от 2-3 до 5-6 определений, через запятую с пробелом
    raw_genres = meta.get("genres", "")
    genres_list = [g.strip().capitalize() for g in raw_genres.split(",") if g.strip()]
    if len(genres_list) > 6:
        genres_list = genres_list[:6]
    genres_formatted = ", ".join(genres_list) if genres_list else "Драма"

    # Выпущено: Страна, киностудия
    country_part = countries or "США"
    studio_meta = meta.get("studio") or meta.get("production_companies") or ""
    released_str = f"{country_part}, {studio_meta}".strip(", ") if studio_meta else country_part

    # Режиссер и В ролях (апострофы меняем на ` согласно правилу п.249)
    director = (meta.get("directors") or "").replace("'", "`").strip()
    raw_actors = (meta.get("actors") or "").replace("'", "`")
    actors_list = [a.strip() for a in raw_actors.split(",") if a.strip()]
    if len(actors_list) > 15:
        actors_list = actors_list[:15]
    cast_formatted = ", ".join(actors_list)

    # Роль (Исполнитель, Ведущий, Комментатор, В ролях)
    role_label = "В ролях"
    genres_lower = raw_genres.lower()
    if "музык" in genres_lower or "концерт" in genres_lower:
        role_label = "Исполнитель"
    elif "спорт" in genres_lower:
        role_label = "Комментатор"
    elif "ток-шоу" in genres_lower or "передача" in genres_lower or "телешоу" in genres_lower:
        role_label = "Ведущий"

    pre_desc_lines = []
    if not is_domestic and title_ru and title_orig and title_ru.lower() != title_orig.lower():
        pre_desc_lines.append(f"[b]Название:[/b] {title_ru}")
        pre_desc_lines.append(f"[b]Оригинальное название:[/b] {title_orig}")
    else:
        pre_desc_lines.append(f"[b]Оригинальное название:[/b] {title_orig or title_ru}")

    if year:
        pre_desc_lines.append(f"[b]Год выпуска:[/b] {year}")
    pre_desc_lines.append(f"[b]Жанр:[/b] {genres_formatted}")
    pre_desc_lines.append(f"[b]Выпущено:[/b] {released_str}")
    if director:
        pre_desc_lines.append(f"[b]Режиссер:[/b] {director}")
    if cast_formatted:
        pre_desc_lines.append(f"[b]{role_label}:[/b] {cast_formatted}")

    pre_description_bb = "\n".join(pre_desc_lines)

    # 3. Поле "Описание"
    # Строго один абзац, начиная со знака [b]О фильме:[/b]
    raw_plot = (meta.get("plot") or "").strip()
    clean_plot = " ".join(raw_plot.split()) if raw_plot else "Описание сюжета отсутствует."
    plot_bb = f"[b]О фильме:[/b] {clean_plot}"

    # 4. Поле "Технические данные" (вкладка Техданные)
    # Кодек видео
    v_codec = media.get("video_codec", "")
    if "HEVC" in v_codec.upper() or "H.265" in v_codec.upper():
        clean_vcodec = "HEVC"
    elif "AVC" in v_codec.upper() or "H.264" in v_codec.upper():
        clean_vcodec = "H.264"
    elif "AV1" in v_codec.upper():
        clean_vcodec = "AV1"
    elif "VP9" in v_codec.upper():
        clean_vcodec = "VP9"
    elif "MPEG" in v_codec.upper():
        clean_vcodec = "MPEG-2"
    else:
        clean_vcodec = v_codec or "H.264"

    v_bitrate_kbps = media.get("video_bitrate_kbps")
    if not v_bitrate_kbps and media.get("video_bitrate"):
        b_nums = re.findall(r"\d+", str(media.get("video_bitrate")))
        if b_nums:
            v_bitrate_kbps = int(b_nums[0])
    v_bitrate_str = f"{v_bitrate_kbps} Кбит/с" if v_bitrate_kbps else ""

    resolution = media.get("resolution") or "1920x1080"
    bit_depth = media.get("bit_depth")

    video_line_parts = [clean_vcodec]
    if v_bitrate_str:
        video_line_parts.append(v_bitrate_str)
    video_line_parts.append(resolution)
    if clean_vcodec == "HEVC":
        video_line_parts.append(f"{bit_depth or 10} бит")

    video_field_val = ", ".join(video_line_parts)

    # Аудиодорожки
    audio_tracks = release_opts.get("audio_tracks") or media.get("audio_tracks", [])
    if audio_tracks:
        audio_lines = [format_kinozal_audio_track(t, is_first=(i == 0)) for i, t in enumerate(audio_tracks)]
        audio_field_val = ", ".join(audio_lines)
    else:
        audio_field_val = "Русский (AC3, 2 ch, 192 Кбит/с)"

    # Размер
    file_size_bytes = media.get("file_size_bytes") or 0
    kinozal_size = format_kinozal_size(file_size_bytes)

    # Продолжительность
    duration_str = media.get("duration") or "01:30:00"
    if is_series and episodes_count and episodes_count > 1:
        duration_field_val = f"{episodes_count} x ~ {duration_str}"
    else:
        duration_field_val = duration_str

    # Перевод / Язык
    has_russian_track = is_domestic or any("рус" in (t.get("language") or "").lower() or t.get("translation_type_key") in ("dub", "mvo", "dvo", "pvo", "avo", "lmvo", "ldvo", "lvo", "ru") for t in audio_tracks)

    if is_domestic:
        trans_label_tag = "Язык"
        trans_value = "Русский"
    elif not has_russian_track and audio_tracks:
        trans_label_tag = "Перевод"
        trans_value = "Отсутствует"
    else:
        type_names = []
        for t in audio_tracks:
            tk = t.get("translation_type_key", "mvo")
            name = KZ_TRANSLATION_NAME_MAP.get(tk, "")
            if name and name not in ("Отсутствует", "Не требуется") and name not in type_names:
                type_names.append(name)
        if not type_names:
            type_names.append(trans_name)

        formatted_names = [type_names[0]] + [n.lower() for n in type_names[1:]]
        trans_label_tag = "Перевод"
        trans_value = ", ".join(formatted_names)

    # Субтитры
    sub_text = format_subtitles_text(enabled_subs)

    techdata_lines = [
        f"[b]Качество:[/b] {quality}",
        f"[b]Видео:[/b] {video_field_val}",
        f"[b]Аудио:[/b] {audio_field_val}",
        f"[b]Размер:[/b] {kinozal_size}",
        f"[b]Продолжительность:[/b] {duration_field_val}",
        f"[b]{trans_label_tag}:[/b] {trans_value}"
    ]
    if sub_text:
        techdata_lines.append(f"[b]Субтитры:[/b] {sub_text}")

    techdata_bb = "\n".join(techdata_lines)

    # 5. Пятое поле: "Оформление, вкладки, примечания, скриншоты"
    field5_blocks = []

    # 1. Поиск раздач
    search_title = title_orig or title_ru
    if search_title:
        search_query = f"{search_title} / {year}" if year else search_title
        field5_blocks.append(f"[searchm=Подобные раздачи]{search_query}[/searchm]")

    # 2. Рейтинги IMDb и Кинопоиск
    imdb_id = meta.get("imdb_id")
    imdb_rating = meta.get("imdb_rating") or meta.get("rating_imdb") or (meta.get("rating") if meta.get("source") == "tmdb" else None)
    if imdb_id and imdb_rating:
        field5_blocks.append(f"[imdb={imdb_id}]{imdb_rating}[/imdb]")

    kp_id = meta.get("kinopoisk_id") or (meta.get("id") if meta.get("source") == "kinopoisk" else None)
    kp_rating = meta.get("kinopoisk_rating") or meta.get("rating_kinopoisk") or (meta.get("rating") if meta.get("source") == "kinopoisk" else None)
    if kp_id and kp_rating:
        field5_blocks.append(f"[kinopoisk={kp_id}]{kp_rating}[/kinopoisk]")

    # 3. Трейлер и Инфо-файл
    trailer_url = meta.get("trailer_url") or meta.get("trailer")
    if trailer_url:
        field5_blocks.append(f"[linkm=Трейлер]{trailer_url}[/linkm]")

    info_file_url = release_opts.get("info_file_url")
    if info_file_url:
        field5_blocks.append(f"[linkm=Инфо-файл]{info_file_url}[/linkm]")

    # 4. Вкладка [pagesd=Релиз]
    release_lines = []
    if audio_tracks:
        for i, t in enumerate(audio_tracks, 1):
            release_lines.append(format_kinozal_release_audio(t, i, trans_name, studio))
    elif studio:
        release_lines.append(f"Релиз-группа / Автор озвучивания: {studio}")

    if release_lines:
        field5_blocks.append("[pagesd=Релиз]\n" + "\n".join(release_lines) + "\n[/pagesd]")

    # Вкладка [pagesd=Награды] если указана
    awards = meta.get("awards") or release_opts.get("awards")
    if awards:
        field5_blocks.append(f"[pagesd=Награды]{awards}[/pagesd]")

    # 5. Скриншоты: вкладка [pagesd=Скриншоты] (по 2 в ряд через пробел, от 2 до 6 штук)
    screens_list = [s.get("full_url", "") for s in (uploaded_screens or []) if s.get("full_url")]
    screens_links = "\n".join(screens_list)

    if uploaded_screens:
        screen_rows = []
        row = []
        for s in (uploaded_screens or [])[:6]:
            full = s.get("full_url", "")
            thumb = s.get("thumb_url") or full
            if full:
                row.append(f"[url={full}][img]{thumb}[/img][/url]")
                if len(row) == 2:
                    screen_rows.append(" ".join(row))
                    row = []
        if row:
            screen_rows.append(" ".join(row))

        if screen_rows:
            field5_blocks.append("[pagesd=Скриншоты]\n" + "\n".join(screen_rows) + "\n[/pagesd]")

    field5_bb = "\n\n".join(field5_blocks).strip()
    poster_url = meta.get("poster_url", "")

    # Полный монолитный BB-код релиза для удобного копирования
    full_bb_parts = [pre_description_bb, plot_bb, techdata_bb]
    if field5_bb:
        full_bb_parts.append(field5_bb)
    full_bb = "\n\n".join(full_bb_parts).strip()

    category_id = detect_kinozal_category(meta, is_series, is_domestic)

    return {
        "category_id": category_id,
        "title_full": title_full,
        "title_ru": title_ru,
        "title_orig": title_orig,
        "year": str(year),
        "country": country_part,
        "genre": genres_formatted,
        "director": director,
        "cast": cast_formatted,
        "pre_description": pre_description_bb,
        "plot": plot_bb,
        "raw_plot": clean_plot,
        "video": video_field_val,
        "audio": audio_field_val,
        "size": kinozal_size,
        "duration": duration_field_val,
        "translation": trans_value,
        "translation_label": trans_label_tag,
        "subtitles": sub_text,
        "techdata": techdata_bb,
        "field5": field5_bb,
        "quality": quality,
        "poster_url": poster_url,
        "screens_list": screens_list,
        "screens_links": screens_links,
        "full_bbcode": full_bb,
        "mediainfo": media.get("raw_mediainfo", "")
    }
