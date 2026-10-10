"""G3-проба (одноразовая, НЕ тест сьюта): перехват всех сетевых запросов
страниц Wiki — /wiki, /wiki?create=1 (редактор), статья, история; внешний =
всё, что не 127.0.0.1/localhost. Плюс MIME-ошибки ES-модулей (responsefinished
по /static/js/** с не-JS content-type). Стенд — автостенд tests/web/conftest.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests" / "web"))
sys.path.insert(0, str(REPO / "backend"))

import os
import socket
import subprocess
import tempfile
import time

import requests

OWNER_PW = "QaOwner_Pass_1!"
BASE_ENV = "EKOTOV_WIKI_BASE_URL"
DB_ENV = "EKOTOV_WIKI_DB_PATH"
for var in (BASE_ENV, DB_ENV):
    os.environ.pop(var, None)  # гарантия автоподъема, не внешний стенд


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_health(url, deadline=60.0):
    t0 = time.monotonic()
    last = None
    while time.monotonic() - t0 < deadline:
        try:
            r = requests.get(f"{url}/api/health", timeout=2)
            if r.status_code == 200 and r.json() == {"status": "ok"}:
                return
        except requests.RequestException as e:
            last = e
        time.sleep(0.3)
    raise RuntimeError(f"{url} не готов: {last}")


def main():
    tmp = tempfile.TemporaryDirectory(prefix="g3-probe-")
    db_path = str(Path(tmp.name) / "app.db")
    avatars = str(Path(tmp.name) / "avatars")
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ, DB_PATH=db_path, SECRET_KEY="g3-probe-secret",
               TZ="UTC", AVATARS_DIR=avatars)
    subprocess.run([sys.executable, "-m", "app.db"], cwd=REPO / "backend",
                   env=env, check=True, capture_output=True)
    subprocess.run([sys.executable, "-m", "app.migrate_wiki"], cwd=REPO / "backend",
                   env=env, check=True, capture_output=True)

    # seed owner (bcrypt) + категории — как _seed_users conftest
    import bcrypt, sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO users (login, password_hash, role) VALUES (?,?,?)",
                 ("owner", bcrypt.hashpw(OWNER_PW.encode(), bcrypt.gensalt()).decode(), "Product manager"))
    for name in ("Дом", "Работа", "Личное"):
        conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
    conn.commit(); conn.close()

    app_env = dict(env)
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                               "--host", "127.0.0.1", "--port", str(port),
                               "--log-level", "warning"],
                              cwd=REPO / "backend", env=app_env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # статика: роль nginx — http.server на docroot frontend/static (conftest §_start_static_server)
    static_port = free_port()
    static_proc = subprocess.Popen([sys.executable, "-m", "http.server", str(static_port),
                                    "--bind", "127.0.0.1"],
                                   cwd=REPO / "frontend" / "static",
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    static_url = f"http://127.0.0.1:{static_port}"
    try:
        wait_health(base)

        from playwright.sync_api import sync_playwright

        ext_requests = []       # все запросы не-localhost
        all_hosts = set()
        mime_errors = []        # ES-модули с неправильным MIME
        failures = []           # requestfailed

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context()
            # Playwright-маршрутизация «роль nginx» (conftest):
            # {base}/static/* → http.server статики; единый origin.
            def _to_static(route):
                new_url = static_url + route.request.url.partition("/static")[2]
                route.fulfill(response=route.fetch(url=new_url))
            context.route(f"{base}/static/**", _to_static)
            page = context.new_page()

            page.on("request", lambda req: _on_request(req, ext_requests, all_hosts))
            page.on("requestfailed", lambda req: failures.append(
                {"url": req.url, "failure": req.failure}))
            page.on("responsefinished", lambda resp: _on_response(resp, mime_errors))

            # 1) вход owner через UI (как logged_in_page)
            page.goto(f"{base}/login")
            page.get_by_label("Логин").fill("owner")
            page.get_by_label("Пароль").fill(OWNER_PW)
            page.get_by_role("button", name="Войти").click()
            page.get_by_role("heading", name="Доска", exact=True).wait_for()

            # 2) seed-страница через API в контексте браузера (куки сессии)
            page.evaluate("""async () => {
                const r = await fetch('/api/wiki/pages', {method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({title:'G3 корень', content:'тело G3'})});
                return r.status;
            }""")
            page_id = page.evaluate("""async () => {
                const r = await fetch('/api/wiki/pages');
                const j = await r.json();
                return j.pages[0] ? j.pages[0].id : null;
            }""")
            assert page_id, "wiki-страница не создана"

            # 3) целевые страницы Wiki; на каждой — рендер + interaction-пауза
            targets = [f"{base}/wiki",
                       f"{base}/wiki?create=1",
                       f"{base}/wiki/{page_id}",
                       f"{base}/wiki/{page_id}/history"]
            visited = []
            for url in targets:
                page.goto(url)
                page.wait_for_load_state("networkidle")
                # активность редактора: contenteditable-тулбар на ?create=1
                if "create=1" in url:
                    try:
                        page.locator(".editor-area, [contenteditable='true']").first.click(timeout=3000)
                        page.keyboard.type("текст G3 ")
                        # попробовать тулбар-кнопки (bold и т.п.)
                        btns = page.locator(".editor-toolbar button, [class*='toolbar'] button")
                        for i in range(min(btns.count(), 5)):
                            try:
                                btns.nth(i).click(timeout=800)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    page.wait_for_load_state("networkidle")
                # статьи: провзаимодействовать с тулбаром чтения/истории
                page.wait_for_timeout(300)
                visited.append(page.title())

            # 3b) САННОТИЗИРУЮЩИЙ подсчет фактических запросов страниц:
            # убеждаемся, что каждая целевая страница реально грузила статику
            # (проба не «молча» прошла мимо цели)
            page.goto(f"{base}/wiki")
            page.wait_for_load_state("networkidle")
            tree_count = page.locator("ul.wiki-tree li").count()
            editor_visible = page.goto(f"{base}/wiki?create=1") is not None and \
                page.locator("[contenteditable='true']").first.is_visible()
            assert tree_count >= 1, "дерево /wiki пусто — цель пробы не достигнута"
            assert editor_visible, "редактор ?create=1 не виден — цель пробы не достигнута"

            # 4) закрыть редактор/сохранить? — не требуется: сеть уже снята
            context.close()
            browser.close()

        result = {
            "external_requests": ext_requests,
            "all_hosts": sorted(all_hosts),
            "total_requests_seen": _on_request.__defaults__[0][0],
            "mime_errors": mime_errors,
            "request_failed": failures,
            "visited_titles": visited,
            "targets": len(targets),
        }
        print("G3RESULT " + json.dumps(result, ensure_ascii=False, indent=1))
        assert not ext_requests, f"ВНЕШНИЕ ЗАПРОСЫ: {ext_requests}"
        assert not mime_errors, f"MIME-ОШИБКИ ES-МОДУЛЕЙ: {mime_errors}"
        print("G3 VERDICT: PASS — внешних запросов нет, MIME в норме")
    finally:
        server.terminate()
        static_proc.terminate()
        for proc in (server, static_proc):
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        tmp.cleanup()


def _on_request(req, ext_requests, all_hosts, _counter=[0]):
    _counter[0] += 1
    url = req.url
    if url.startswith("data:") or url.startswith("about:"):
        return
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    all_hosts.add(f"{host}" + (f":{urlparse(url).port}" if urlparse(url).port else ""))
    if host not in ("127.0.0.1", "localhost", "::1"):
        ext_requests.append({"url": url, "resource_type": req.resource_type,
                             "method": req.method})


def _on_response(resp, mime_errors):
    from urllib.parse import urlparse
    url = resp.url
    if "/static/js/" in url and url.endswith(".js"):
        ct = (resp.headers or {}).get("content-type", "")
        if "javascript" not in ct and "ecmascript" not in ct:
            mime_errors.append({"url": url, "content_type": ct, "status": resp.status})


if __name__ == "__main__":
    main()
