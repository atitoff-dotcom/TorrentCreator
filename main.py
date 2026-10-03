import os
import sys
from pathlib import Path
import webview
from backend.app_api import AppAPI
from backend.config_manager import load_config

def main():
    base_dir = Path(__file__).resolve().parent
    frontend_dir = base_dir / "frontend"
    html_path = frontend_dir / "index.html"

    # Загружаем настройки
    config = load_config()

    # Инициализируем API
    api = AppAPI()

    # Создаем главное окно
    window = webview.create_window(
        title="TorrentCreator",
        url=str(html_path.resolve()),
        js_api=api,
        width=1100,
        height=750,
        min_size=(900, 600),
        background_color="#12141a" if config.get("theme") == "dark" else "#f4f6fa"
    )

    api.set_window(window)

    icon_path = base_dir / "assets" / "icon.ico"

    # Запуск окна WebView2 с иконкой
    webview.start(debug=False, icon=str(icon_path.resolve()) if icon_path.exists() else None)

if __name__ == "__main__":
    main()
