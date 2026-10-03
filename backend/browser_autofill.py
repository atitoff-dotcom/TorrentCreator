"""
Модуль прямой автоматизации браузера через nodriver (чистый Python + CDP, без Node.js).
Использует выделенный рабочий поток с отдельным asyncio event loop и asyncio.run_coroutine_threadsafe.
Вызовы из любых потоков pywebview выполняются безопасно и без блокировки GUI.
При закрытии браузера пользователем следующий вызов автоматически перезапускает его с сохранением сессии.
"""

import asyncio
import json
import threading
from pathlib import Path

import nodriver as uc
from nodriver import cdp

# Профиль браузера для сохранения сессий (куки, авторизация на трекерах)
PROFILE_DIR = Path.home() / ".torrent_creator_browser_profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)


class _AutomationWorker:
    def __init__(self):
        self._loop = None
        self._browser = None
        self._ready_event = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._ready_event.wait(timeout=5.0)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready_event.set()
        self._loop.run_forever()

    async def _ensure_browser(self):
        """Гарантирует запуск браузера с профилем пользователя"""
        if self._browser is not None:
            if not self._browser.stopped:
                return self._browser
            print("[nodriver] Окно браузера было закрыто, перезапускаем...", flush=True)
            try:
                self._browser.stop()
            except Exception:
                pass
            self._browser = None

        print(f"[nodriver] Запуск браузера с профилем: {PROFILE_DIR}...", flush=True)
        self._browser = await uc.start(
            user_data_dir=PROFILE_DIR,
            headless=False,
            browser_args=["--start-maximized", "--no-default-browser-check"]
        )
        return self._browser

    async def _eval_json(self, page, js_expr: str):
        """Выполняет JS и возвращает чистый Python объект через JSON.stringify"""
        try:
            raw = await page.evaluate(f"JSON.stringify((() => {{ {js_expr} }})())")
            if raw and isinstance(raw, str):
                return json.loads(raw)
            return raw
        except Exception:
            return None

    async def _get_page(self, browser, target_url: str):
        """Открывает страницу в существующей или новой вкладке"""
        tabs = [t for t in browser.tabs if t.target.type_ == "page"]
        if len(tabs) <= 1:
            page = await browser.get(target_url)
        else:
            page = await browser.get(target_url, new_tab=True)
        return page

    async def _wait_for_condition(self, page, target_url: str, form_check_js: str, max_seconds: int = 40):
        """Ожидает готовности формы с обработкой Cloudflare и страницы авторизации"""
        for i in range(max_seconds):
            try:
                status = await self._eval_json(page, f"""
                    const title = (document.title || '').toLowerCase();
                    const url = window.location.href || '';
                    const is_cf = title.includes('проверк') || title.includes('just a moment') || title.includes('cloudflare');
                    const is_login = !!document.querySelector('input[type="password"]');
                    const is_ready = Boolean({form_check_js});
                    return {{
                        is_ready: is_ready,
                        is_cf: is_cf,
                        is_login: is_login,
                        title: document.title,
                        url: url
                    }};
                """)

                if not status:
                    await asyncio.sleep(1.0)
                    continue

                if status.get("is_ready"):
                    return True

                if status.get("is_cf"):
                    print(f"[nodriver] Проверка безопасности (Cloudflare)... ожидание ({i+1}/{max_seconds})", flush=True)
                elif status.get("is_login"):
                    print(f"[nodriver] Требуется авторизация на трекере. Ожидание входа... ({i+1}/{max_seconds})", flush=True)
                else:
                    url = status.get("url", "")
                    if "upload.php" not in url and "posting.php" not in url and "login.php" not in url:
                        await page.evaluate(f"window.location.href = '{target_url}';")

            except Exception as e:
                print(f"[nodriver] Ошибка проверки страницы ({i+1}): {e}", flush=True)

            await asyncio.sleep(1.0)
        return False

    async def _do_kinozal(self, kz_fields: dict, target_url: str = "https://kinozal.me/upload.php"):
        browser = await self._ensure_browser()
        print(f"[nodriver] Переход на Кинозал: {target_url}...", flush=True)
        page = await self._get_page(browser, target_url)

        try:
            await page.send(cdp.page.bring_to_front())
        except Exception:
            pass

        # Ждем появления формы
        form_ready = await self._wait_for_condition(
            page,
            target_url,
            "document.querySelector('input[name=\"name\"]') !== null"
        )

        if not form_ready:
            return {
                "success": False,
                "error": "Форма Кинозала не открылась вовремя. Возможно, требуется войти в аккаунт."
            }

        # 1. Переключение в расширенный режим
        try:
            await page.evaluate("""(() => {
                if (typeof Upl !== 'undefined' && typeof Upl.changeMode === 'function') {
                    Upl.changeMode(1);
                    return true;
                }
                const m1 = document.getElementById('m1');
                if (m1) {
                    m1.click();
                    return true;
                }
                return false;
            })()""")
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"[nodriver] Ошибка переключения режима формы: {e}", flush=True)

        # 2. Пакетное заполнение полей через JS
        payload_json = json.dumps(kz_fields, ensure_ascii=False)
        fill_res = await self._eval_json(page, f"""
            const data = {payload_json};
            let count = 0;

            function setVal(sel, val) {{
                if (!val) return false;
                const el = document.querySelector(sel);
                if (el) {{
                    el.scrollIntoView({{ block: 'nearest' }});
                    el.value = val;
                    el.style.border = '2px solid #10b981';
                    el.style.boxShadow = '0 0 8px rgba(16, 185, 129, 0.4)';
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    count++;
                    return true;
                }}
                return false;
            }}

            setVal('input[name="name"]', data.title_full);
            setVal('input[name="poster"]', data.poster_url);

            setVal('#d1, textarea[name="desc1"]', data.pre_description);
            setVal('#d2, textarea[name="desc2"]', data.plot);
            setVal('#d3, textarea[name="desc3"]', data.techdata);

            const f5 = data.field5 || data.screens_links;
            if (f5) {{
                setVal('#d4, textarea[name="desc4"]', f5);
            }} else {{
                const d4 = document.getElementById('d4') || document.querySelector('textarea[name="desc4"]');
                if (d4 && d4.value && (d4.value.includes('tt00000') || d4.value.includes('searchm='))) {{
                    d4.value = '';
                    d4.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            }}

            const catId = data.category_id;
            if (catId && String(catId) !== '0') {{
                const sel = document.getElementById('type1') || document.querySelector('select[name="type1"]');
                if (sel) {{
                    sel.value = String(catId);
                    sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    count++;
                }}
            }}

            return count;
        """)

        count = fill_res if isinstance(fill_res, int) else 0

        try:
            await page.send(cdp.page.bring_to_front())
        except Exception:
            pass

        print(f"[nodriver] Успешно заполнено {count} полей на Кинозале!", flush=True)
        return {
            "success": True,
            "filled_count": count,
            "message": f"Кинозал успешно открыт и заполнен ({count} полей)!"
        }

    async def _do_rutracker(self, ru_title: str, ru_bbcode: str, forum_id: int):
        browser = await self._ensure_browser()
        target_url = f"https://rutracker.org/forum/posting.php?mode=newtopic&f={forum_id}"
        print(f"[nodriver] Переход на RuTracker: {target_url}...", flush=True)
        page = await self._get_page(browser, target_url)

        try:
            await page.send(cdp.page.bring_to_front())
        except Exception:
            pass

        form_ready = await self._wait_for_condition(
            page,
            target_url,
            "document.querySelector('textarea[name=\"message\"]') !== null"
        )

        if not form_ready:
            return {
                "success": False,
                "error": "Форма создания темы RuTracker не открылась вовремя. Возможно, требуется войти в аккаунт."
            }

        title_json = json.dumps(ru_title, ensure_ascii=False)
        bbcode_json = json.dumps(ru_bbcode, ensure_ascii=False)

        fill_res = await self._eval_json(page, f"""
            let count = 0;
            const titleEl = document.querySelector('input[name="subject"]');
            if (titleEl) {{
                titleEl.value = {title_json};
                titleEl.style.border = '2px solid #10b981';
                titleEl.style.boxShadow = '0 0 8px rgba(16, 185, 129, 0.4)';
                titleEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                titleEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
                count++;
            }}

            const msgEl = document.querySelector('textarea[name="message"]');
            if (msgEl) {{
                msgEl.value = {bbcode_json};
                msgEl.style.border = '2px solid #10b981';
                msgEl.style.boxShadow = '0 0 8px rgba(16, 185, 129, 0.4)';
                msgEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                msgEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
                count++;
            }}

            return count;
        """)

        count = fill_res if isinstance(fill_res, int) else 0

        try:
            await page.send(cdp.page.bring_to_front())
        except Exception:
            pass

        print(f"[nodriver] RuTracker: заполнено {count} полей", flush=True)
        return {
            "success": count > 0,
            "message": "RuTracker успешно открыт и заполнен!" if count > 0 else "Не удалось заполнить поля RuTracker"
        }

    def execute(self, coro_func, *args, timeout: float = 120.0):
        fut = asyncio.run_coroutine_threadsafe(coro_func(*args), self._loop)
        return fut.result(timeout=timeout)


_worker = _AutomationWorker()


def autofill_kinozal(kz_fields: dict, target_url: str = "https://kinozal.me/upload.php"):
    return _worker.execute(_worker._do_kinozal, kz_fields, target_url)


def autofill_rutracker(ru_title: str, ru_bbcode: str, forum_id: int = 313):
    return _worker.execute(_worker._do_rutracker, ru_title, ru_bbcode, forum_id)
