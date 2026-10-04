"""
Модуль эталонных правил оформления раздач Кинозала (Kinozal.tv/me).
Является ЕДИНЫМ ИСТОЧНИКОМ ПРАВДЫ (Single Source of Truth) для:
1. Валидатора раздач (проверка ручного и автоматического ввода).
2. Автоисправления типичных ошибок.
3. Интерактивного Справочника правил (Help) в интерфейсе программы.
4. Экспорта официального регламента правил для Администрации Кинозала.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, List, Dict, Any
import re


@dataclass
class KinozalRule:
    id: str                                  # Уникальный код: "TITLE_MAX_LEN"
    category: str                            # Категория: "Заголовок раздачи", "Озвучка и переводы", etc.
    title: str                               # Короткое название: "Ограничение длины названия"
    description: str                         # Официальный текст правила для Хелпа
    severity: str = "error"                  # "error" (критично) или "warning" (предупреждение)
    example_good: str = ""                   # Эталонный пример для человека
    example_bad: str = ""                    # Частая ошибка для человека
    check_fn: Optional[Callable[[Dict[str, Any]], tuple[bool, str]]] = None
    fix_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "example_good": self.example_good,
            "example_bad": self.example_bad
        }


# =========================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ВАЛИДАЦИИ И ИСПРАВЛЕНИЯ
# =========================================================================

KZ_ALLOWED_QUALITY = [
    "BDRip", "BDRip (1080p)", "BDRip (720p)", "BDRip (AVC)",
    "WEB-DL", "WEB-DL (1080p)", "WEB-DL (720p)", "WEB-DL (2160p)",
    "WEB-DLRip", "WEB-DLRip (1080p)", "WEB-DLRip (720p)", "WEB-DLRip (AVC)",
    "WEBRip", "WEBRip (1080p)", "WEBRip (720p)", "WEBRip (2160p)", "WEBRip (1440p)", "WEBRip (4320p)",
    "Blu-Ray", "Blu-Ray (1080p)", "Blu-Ray (2160p)", "Blu-Ray (1080i)",
    "Blu-Ray Remux", "Blu-Ray Remux (1080p)", "Blu-Ray Remux (2160p)",
    "HDTV", "HDTV (1080i)", "HDTV (1080p)", "HDTV (720p)",
    "HDTVRip", "HDTVRip (1080i)", "HDTVRip (720p)", "HDTVRip (AVC)",
    "DVDRip", "DVDRip (AVC)", "DVD-5", "DVD-9", "HDDVDRip", "HDRip"
]

KZ_VALID_CODES = {
    "ДБ", "ДБ (TS)", "ПМ", "ПД", "ПО",
    "ЛМ", "ЛД", "ЛО",
    "АП",
    "(Смешной перевод)",
    "ДБ (AI)", "ЛМ (AI)", "ЛД (AI)", "ЛО (AI)",
    "РУ", "НК", "БП", "СТ", "ТК"
}


def _check_title_len(fields: dict) -> tuple[bool, str]:
    title = (fields.get("title_full") or fields.get("title") or "").strip()
    length = len(title)
    if length == 0:
        return False, "Название раздачи не заполнено."
    if length > 150:
        return False, f"Длина названия {length} символов (максимально допустимо 150 знаков по базе Кинозала)."
    return True, ""


def _check_title_slashes(fields: dict) -> tuple[bool, str]:
    title = (fields.get("title_full") or fields.get("title") or "").strip()
    if not title:
        return True, ""
    # Проверка на слитные слэши или слэши без пробелов
    if "//" in title:
        return False, "Обнаружен двойной слэш '//'. Позиции разделяются одиночным ' / '."
    parts = title.split(" / ")
    if len(parts) < 3:
        # Проверяем, может пользователь забыл пробелы вокруг слэша
        if "/" in title and len(parts) == 1:
            return False, "В названии пропущены пробелы вокруг слэшей. Требуется строгий формат: ' / '."
        return False, "В названии меньше 3 основных позиций шаблона."
    return True, ""


def _check_audio_tech_in_title(fields: dict) -> tuple[bool, str]:
    title = (fields.get("title_full") or fields.get("title") or "").strip()
    tech_patterns = [
        r"\b\d+\s*kbps\b", r"\b\d+\.\d+\b", r"\b\d+\s*ch\b", r"\b\d+\s*k?hz\b",
        r"\bdts(-hd)?\b", r"\bac3\b", r"\bac-3\b", r"\btruehd\b", r"\bflac\b", r"\baac\b",
        r"\bстерео\b", r"\bдвухголос\w*", r"\bодноголос\w*", r"\bмногоголос\w*", r"\bдублирован\w*"
    ]
    for p in tech_patterns:
        m = re.search(p, title, re.IGNORECASE)
        if m:
            return False, f"В заголовок попали технические данные аудио: '{m.group(0)}'. Звуковые параметры пишутся только в описании раздачи!"
    return True, ""


def _check_movie_audio_studios(fields: dict) -> tuple[bool, str]:
    is_series = bool(fields.get("is_series", False))
    if is_series:
        return True, ""  # Для сериалов студии разрешены
    title = (fields.get("title_full") or fields.get("title") or "").strip()
    # Проверяем наличие студии в скобках у закадровых переводов фильмов
    pattern = r"\b(ПД|ПО|ПМ|ЛД|ЛО|ЛМ|ДБ)\s*\([^)]+\)"
    m = re.search(pattern, title)
    if m:
        return False, (
            f"В названии фильма указана студия/автор в скобках: '{m.group(0)}'. "
            "Для фильмов по правилам Кинозала используются только краткие коды перевода без скобок (например, просто 'ПД' или 'ПМ'), "
            "иначе длина названия превысит лимит."
        )
    return True, ""


def _check_quality_at_end(fields: dict) -> tuple[bool, str]:
    title = (fields.get("title_full") or fields.get("title") or "").strip()
    if not title:
        return True, ""
    parts = [p.strip() for p in title.split(" / ")]
    last_part = parts[-1] if parts else ""
    # Проверяем, содержит ли последняя позиция признак качества
    has_quality = any(q.lower() in last_part.lower() for q in [
        "bdrip", "web-dl", "webrip", "blu-ray", "remux", "hdtv", "dvdrip", "dvd-", "hdrip"
    ])
    if not has_quality:
        return False, f"В конце названия отсутствует формат качества видеоряда (найдено: '{last_part}'). Шаблон должен оканчиваться качеством, например '/ BDRip (1080p)'."
    return True, ""


def _check_released_string(fields: dict) -> tuple[bool, str]:
    pre_desc = fields.get("pre_description") or ""
    # Ищем строку [b]Выпущено:[/b]
    m = re.search(r"\[b\]Выпущено:\[/b\]\s*(.+)", pre_desc)
    if not m:
        country = fields.get("country") or fields.get("countries") or ""
        studio = fields.get("studio") or fields.get("production_companies") or ""
        if not country:
            return False, "В блоке 'Выпущено' не указана страна производства."
        if not studio:
            return False, "В блоке 'Выпущено' не указана кинокомпания / студия (требуется по правилам Кинозала)."
        return True, ""
    val = m.group(1).strip()
    if "," not in val:
        return False, (
            f"В строке 'Выпущено: {val}' не найден разделитель-запятая. "
            "По правилам Кинозала указывается: 'Страна, Кинокомпания' (например, 'США, Paramount Pictures')."
        )
    return True, ""


def _check_genres_count(fields: dict) -> tuple[bool, str]:
    genre_str = fields.get("genre") or fields.get("genres") or ""
    if not genre_str:
        return False, "Поле 'Жанр' не заполнено."
    genres = [g.strip() for g in genre_str.split(",") if g.strip()]
    if len(genres) < 2:
        return False, f"Указан только {len(genres)} жанр. Правила Кинозала требуют указывать от 2 до 6 определений через запятую."
    if len(genres) > 6:
        return False, f"Указано {len(genres)} жанров. Правила Кинозала рекомендуют не более 6 определений жанра."
    return True, ""


def _check_apostrophes(fields: dict) -> tuple[bool, str]:
    # Проверяем поля на одинарные кавычки '
    targets = [
        ("Режиссер", fields.get("director") or fields.get("directors") or ""),
        ("В ролях", fields.get("cast") or fields.get("actors") or ""),
        ("Заголовок", fields.get("title_full") or fields.get("title") or "")
    ]
    for label, val in targets:
        if "'" in val:
            return False, f"В поле '{label}' обнаружен прямой апостроф ('). По правилам Кинозала (п. 249) апостроф заменяется на знак грависа (`)."
    return True, ""


def _check_actors_count(fields: dict) -> tuple[bool, str]:
    cast_str = fields.get("cast") or fields.get("actors") or ""
    if not cast_str:
        return True, ""
    actors = [a.strip() for a in cast_str.split(",") if a.strip()]
    if len(actors) > 15:
        return False, f"В ролях указано {len(actors)} актеров. По правилам Кинозала список ограничивается 15 персонами."
    return True, ""


def _check_plot_header(fields: dict) -> tuple[bool, str]:
    plot = (fields.get("plot") or "").strip()
    if not plot:
        return False, "Описание сюжета ('О фильме') не заполнено."
    if "[b]О фильме:[/b]" not in plot and "[b]О сериале:[/b]" not in plot and "[b]О передаче:[/b]" not in plot:
        return False, "Описание сюжета должно начинаться со строгого маркера '[b]О фильме:[/b]' (или '[b]О сериале:[/b]')."
    return True, ""


def _check_screenshots(fields: dict) -> tuple[bool, str]:
    screens = fields.get("uploaded_screens") or fields.get("screens_list") or []
    if not screens or len(screens) < 2:
        return False, f"Отобрано {len(screens)} скриншотов. Для раздачи требуется минимум 2–3 залитых скриншота."
    return True, ""


# --- Функции автоисправления ---

def _fix_slashes_and_apostrophes(fields: dict) -> dict:
    f = dict(fields)
    # 1. Замена апострофов на гравис
    for k in ["director", "directors", "cast", "actors", "title_full", "title_ru", "title_orig"]:
        if k in f and isinstance(f[k], str) and "'" in f[k]:
            f[k] = f[k].replace("'", "`")

    # 2. Исправление слэшей в заголовке
    if "title_full" in f and f["title_full"]:
        t = f["title_full"]
        t = re.sub(r"\s*/+\s*", " / ", t)
        f["title_full"] = t

    # 3. Обрезание списка актеров до 15
    for k in ["cast", "actors"]:
        if k in f and f[k]:
            parts = [a.strip() for a in f[k].split(",") if a.strip()]
            if len(parts) > 15:
                f[k] = ", ".join(parts[:15])

    return f


# =========================================================================
# РЕЕСТР ПРАВИЛ КИНОЗАЛА
# =========================================================================

KINOZAL_RULES: List[KinozalRule] = [
    # 1. ЗАГОЛОВОК ТЕМЫ
    KinozalRule(
        id="TITLE_MAX_LEN",
        category="1. Заголовок раздачи",
        title="Ограничение длины названия (150 символов)",
        description=(
            "Основное название раздачи не должно превышать 150 символов с учётом пробелов. "
            "При превышении лимита движок Кинозала физически обрезает заголовок, теряя качество видеоряда."
        ),
        severity="error",
        example_good="Старикам тут не место / No Country for Old Men / 2007 / ДБ, ПД, ПО / BDRip (1080p)",
        example_bad="Фильм... / ДБ, ПД (DTS 5.1, 1536 kbps Гланц и Королёва)... [более 150 знаков]",
        check_fn=_check_title_len
    ),

    KinozalRule(
        id="TITLE_SLASH_SPACES",
        category="1. Заголовок раздачи",
        title="Пробелы вокруг слэшей ( ' / ' )",
        description="Разделитель позиций шаблона — косая черта со строгими пробелами до и после: ' / '. Слитные слэши или '//' запрещены.",
        severity="error",
        example_good="Фильм / Movie / 2024 / ДБ / BDRip",
        example_bad="Фильм/Movie/2024 / ДБ//BDRip",
        check_fn=_check_title_slashes,
        fix_fn=_fix_slashes_and_apostrophes
    ),

    KinozalRule(
        id="TITLE_QUALITY_END",
        category="1. Заголовок раздачи",
        title="Формат качества в конце названия",
        description="Шаблон названия обязательно должен завершаться указанием качества видеоматериала латиницей (BDRip, WEB-DL, Blu-Ray Remux...).",
        severity="error",
        example_good="... / 2007 / ДБ, ПД / BDRip (1080p)",
        example_bad="... / 2007 / ДБ, ПД (качество забыто или обрезано)",
        check_fn=_check_quality_at_end
    ),

    # 2. ОЗВУЧКА И ПЕРЕВОДЫ
    KinozalRule(
        id="AUDIO_NO_TECH_IN_TITLE",
        category="2. Озвучка и переводы",
        title="Запрет технических параметров звука в названии",
        description=(
            "В названии раздачи строго запрещено указывать кодеки (DTS, AC3), каналы (5.1), "
            "битрейты (1536 kbps) и слова 'двухголосый', 'одноголосый'. Все эти данные "
            "указываются исключительно в теле раздачи (в блоке релиза)."
        ),
        severity="error",
        example_good="... / 2007 / ДБ, ПД, ПО / BDRip (1080p)",
        example_bad="... / 2007 / ДБ, ПД (DTS 5.1, 1536 kbps (двухголосый, П.Гланц)), ПО... /",
        check_fn=_check_audio_tech_in_title
    ),

    KinozalRule(
        id="AUDIO_MOVIE_NO_STUDIOS",
        category="2. Озвучка и переводы",
        title="Запрет студий и авторов в скобках для фильмов",
        description=(
            "Для фильмов закадровые переводы указываются только двухбуквенными кодами (ПД, ПО, ПМ, ЛД). "
            "Студии в скобках разрешены только для сериалов (например, 'ПМ (LostFilm)'). "
            "Для авторского перевода фильма указывается только краткая фамилия: 'АП (Гланц)'."
        ),
        severity="warning",
        example_good="Старикам тут не место / No Country for Old Men / 2007 / ДБ, ПД, ПО / BDRip (1080p)",
        example_bad="... / 2007 / ДБ, ПД (Гланц и Королёва), ПО (Немахов) / ...",
        check_fn=_check_movie_audio_studios
    ),

    # 3. МЕТАДАННЫЕ И ОПИСАНИЕ
    KinozalRule(
        id="META_RELEASED_FORMAT",
        category="3. Метаданные и описание",
        title="Формат строки «Выпущено:»",
        description=(
            "В строке «Выпущено:» сначала через запятую перечисляются страны производства, "
            "а затем через запятую — кинокомпании (студии), выпустившие фильм."
        ),
        severity="warning",
        example_good="[b]Выпущено:[/b] США, Paramount Vantage, Miramax Films, Scott Rudin Productions",
        example_bad="[b]Выпущено:[/b] США (без студий) или [b]Выпущено:[/b] Paramount (без страны)",
        check_fn=_check_released_string
    ),

    KinozalRule(
        id="META_GENRES_COUNT",
        category="3. Метаданные и описание",
        title="Количество жанров (от 2 до 6)",
        description="По правилам Кинозала указывается от 2-3 до 5-6 определений жанра через запятую с пробелом с заглавной буквы.",
        severity="warning",
        example_good="[b]Жанр:[/b] Триллер, драма, криминал",
        example_bad="[b]Жанр:[/b] Драма (всего один) или список из 9 жанров",
        check_fn=_check_genres_count
    ),

    KinozalRule(
        id="META_NO_APOSTROPHES",
        category="3. Метаданные и описание",
        title="Замена апострофа на гравис ( ` )",
        description="В именах и названиях одинарная кавычка (') ломает экранирование и заменяется на знак грависа (`).",
        severity="warning",
        example_good="Д`Артаньян, О`Коннор, О`Нил",
        example_bad="Д'Артаньян, О'Коннор",
        check_fn=_check_apostrophes,
        fix_fn=_fix_slashes_and_apostrophes
    ),

    KinozalRule(
        id="META_ACTORS_LIMIT",
        category="3. Метаданные и описание",
        title="Ограничение списка актёров (до 15)",
        description="В графе 'В ролях' указывается не более 15 основных актёров через запятую с пробелом.",
        severity="warning",
        example_good="Томми Ли Джонс, Хавьер Бардем, Джош Бролин (до 15 персон)",
        example_bad="Список из 25 человек, скопированный целиком из титров",
        check_fn=_check_actors_count,
        fix_fn=_fix_slashes_and_apostrophes
    ),

    KinozalRule(
        id="META_PLOT_HEADER",
        category="3. Метаданные и описание",
        title="Маркер [b]О фильме:[/b]",
        description="Описание сюжета должно быть одним связным абзацем и начинаться со знака [b]О фильме:[/b] (или [b]О сериале:[/b]).",
        severity="error",
        example_good="[b]О фильме:[/b] Обычный рабочий находит в пустыне...",
        example_bad="Просто текст сюжета без тега [b]О фильме:[/b]",
        check_fn=_check_plot_header
    ),

    # 4. СКРИНШОТЫ
    KinozalRule(
        id="SCREENS_COUNT",
        category="4. Скриншоты раздачи",
        title="Количество скриншотов (от 2 до 6)",
        description="Для оформления раздачи требуется от 2 до 6 скриншотов, залитых на поддерживаемый фотохостинг.",
        severity="warning",
        example_good="3-4 качественных кадра с превью 300-350px",
        example_bad="0 скриншотов или ссылки на локальный диск",
        check_fn=_check_screenshots
    )
]


# =========================================================================
# ВНЕШНИЙ ИНТЕРФЕЙС ВАЛИДАЦИИ И ЭКСПОРТА
# =========================================================================

def validate_kinozal_release(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Прогоняет поля релиза по всем правилам Кинозала и возвращает детальный отчет"""
    errors = []
    warnings = []

    for rule in KINOZAL_RULES:
        if rule.check_fn:
            try:
                ok, msg = rule.check_fn(fields)
                if not ok:
                    item = {
                        "rule_id": rule.id,
                        "category": rule.category,
                        "title": rule.title,
                        "message": msg,
                        "example_good": rule.example_good,
                        "has_fix": rule.fix_fn is not None
                    }
                    if rule.severity == "error":
                        errors.append(item)
                    else:
                        warnings.append(item)
            except Exception as e:
                print(f"Error executing rule {rule.id}: {e}")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "total_issues": len(errors) + len(warnings)
    }


def auto_fix_kinozal_release(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Применяет автоматические исправления к полям релиза"""
    fixed = dict(fields)
    for rule in KINOZAL_RULES:
        if rule.fix_fn:
            try:
                fixed = rule.fix_fn(fixed)
            except Exception as e:
                print(f"Error applying fix for {rule.id}: {e}")
    return fixed


def get_kinozal_rules_catalog() -> List[Dict[str, Any]]:
    """Возвращает структурированный каталог всех правил для отображения в Help (UI)"""
    return [rule.to_dict() for rule in KINOZAL_RULES]


def export_rules_to_markdown() -> str:
    """Генерирует официальный эталонный Регламент правил Кинозала в Markdown"""
    lines = [
        "# Официальный стандарт оформления раздач Кинозал.ТВ",
        "",
        "> Автоматизированный стандарт правил оформления тем и раздач видеоматериалов.",
        "",
    ]

    current_cat = ""
    for r in KINOZAL_RULES:
        if r.category != current_cat:
            current_cat = r.category
            lines.append(f"## {current_cat}\n")

        lines.append(f"### {r.title} (`{r.id}`)")
        lines.append(f"- **Требование:** {r.description}")
        lines.append(f"- **Строгость:** {'Критическая ошибка' if r.severity == 'error' else 'Предупреждение'}")
        if r.example_good:
            lines.append(f"- **Правильно:** `{r.example_good}`")
        if r.example_bad:
            lines.append(f"- **Ошибка:** `{r.example_bad}`")
        lines.append("")

    return "\n".join(lines)
