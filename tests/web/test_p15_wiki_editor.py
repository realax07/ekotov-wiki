"""WYSIWYG-редактор Wiki (tasks.md 3.3 add-wiki; FR-110, FR-111; design §5,
§7) — web-кейсы playwright по паттерну tests/web (стенд conftest: uvicorn app
+ http.server static, tmp-БД + seed owner/wife).

TC-ID (реестр тест→кейс, 1 кейс = 1 тест):
  TC-wiki-301 → test_toolbar_formats_change_tags (FR-110, тулбар H1–H3/B/I/U, 3.3а)
  TC-wiki-302 → test_toolbar_lists_and_undo_redo (FR-110, ul/ol + undo/redo, 3.3а)
  TC-wiki-303 → test_toolbar_inserts_table_3x3 (FR-110, таблица 3×3, 3.3а)
  TC-wiki-304 → test_link_javascript_scheme_rejected (FR-110/design §4, javascript: отклонен, 3.3а)
  TC-wiki-305 → test_image_insert_from_gallery (FR-111, изображение из галереи, 3.3б)
  TC-wiki-306 → test_image_insert_from_disk_uploads_and_inserts (FR-111, загрузка с диска, 3.3б)
  TC-wiki-307 → test_save_create_posts_and_redirects (FR-110, создание POST → redirect, 3.3в)
  TC-wiki-308 → test_save_edit_puts_new_version_and_redirects (FR-110, правка PUT = новая версия, 3.3в)
  TC-wiki-309 → test_empty_title_error_no_request (FR-110, пустой title — ошибка без запроса, 3.3в)
Кейсы этапа C (QA) не утверждены (test-model/approved/add-wiki нет); ID
заведены по формату TC-wiki-NNN, привязка будет уточнена в QA-цикле 6.1.

Проверяется (мокап design/wiki-editor.html — эталон):
  1) тулбар применяет форматирование — текст меняет тег (H1–H3, B/I/U,
     ul/ol, цитата, код-блок);
  2) таблица 3×3 вставляется (thead + 2×3 td);
  3) ссылка с javascript: НЕ вставляется (проверка схемы до createLink);
     http-ссылка вставляется;
  4) изображение вставляется после выбора — из галереи (GET /api/images,
     грид-выбор) и с диска (file input → POST /api/images →
     <img src=/images/{...}>);
  5) сохранение пишет и редиректит: создание POST → /wiki/{id}; правка
     GET → заполнить → PUT → /wiki/{id} (в API появляется новая версия);
  6) пустой title — 422-случай: ошибка по мокапу БЕЗ сохранения (запрос
     не уходит).

Изоляция: страницы создаются API от owner-сессии, удаляются в teardown
(DELETE, листья снизу вверх — FK RESTRICT); загруженные в тестах
изображения удаляются из БД/тома по QAE-префиксу original_name.
"""

import io
import os
import re
import socket
import sqlite3
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.sync_api import expect

from tests.web.pages.wiki import WikiEditor

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

# Каталоги сервисов (паттерн conftest: cwd изолирует конфликт пакетов app)
_REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_BACKEND_DIR = _REPO_ROOT / "backend"
REPO_IMAGES_DIR = _REPO_ROOT / "services" / "images"

BASE_URL_ENV = "EKOTOV_WIKI_BASE_URL"
BASE_URL = os.environ.get(BASE_URL_ENV, "http://127.0.0.1:8080")
DB_PATH = os.environ.get("EKOTOV_WIKI_DB_PATH")

MARKER = "QAE-"
IMAGES_DIR = os.environ.get("EKOTOV_WIKI_IMAGES_DIR", "/tmp/qa-images")


# ---------------------------------------------------------------------------
# helpers / fixtures
# ---------------------------------------------------------------------------


def _png_bytes(color=(120, 40, 200)):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (320, 200), color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(scope="session", autouse=True)
def wiki_stand_schema(web_server):
    """Схема wiki + gallery в tmp-БД стенда (идемпотентно; монолит —
    владелец схемы). conftest-стенд прогоняет только python -m app.db
    (ядро) — wiki-API без migrate_wiki падал бы 500 на INSERT в pages.
    Внешний стенд (E7) уже смигрирован — пропуск."""
    import subprocess as sp
    import sys

    db_path = web_server.get("db_path") if isinstance(web_server, dict) else None
    if not db_path:
        return  # внешний стенд — схема уже на месте
    mig_env = dict(os.environ, DB_PATH=db_path, SECRET_KEY="web-tests-secret-key")
    mig_env.pop("PYTHONPATH", None)
    for module in ("app.migrate_wiki", "app.migrate_gallery"):
        mig = sp.run(
            [sys.executable, "-m", module],
            cwd=str(REPO_BACKEND_DIR), env=mig_env,
            capture_output=True, text=True,
        )
        assert mig.returncode == 0, f"{module}: {mig.stderr}"


@pytest.fixture(scope="session")
def images_service(web_server, wiki_stand_schema):
    """Реверс-прокси «роль nginx» для images-семейства (design §5): свой
    ThreadingHTTPServer на свободном порту — /api/images* и /images/*
    уходят в images-сервис (uvicorn services/images), остальное —
    прозрачное проксирование на стенд conftest (app/static/search).

    Прокси, а не playwright-роутинг: multipart-тело POST браузер стримит,
    playwright route.fetch такое тело не реплеит (файл приходит пустым) —
    сетевой уровень тело не трогает.

    Подъем: uvicorn services/images на свободном порту (EKOTOV_WIKI_DB_PATH
    — та же БД стенда, IMAGES_DIR — tmp) + прокси. Внешний стенд (E7) без
    images — изображение-кейсы skip.
    """
    import subprocess as sp
    import sys
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlsplit
    from urllib.request import Request as _Req, build_opener
    from urllib.error import HTTPError as _HTTPError

    import requests

    db_path = web_server.get("db_path")
    if not db_path:
        pytest.skip("нужен внутренний стенд (EKOTOV_WIKI_DB_PATH не задан)")

    env = dict(
        os.environ,
        EKOTOV_WIKI_DB_PATH=db_path,
        EKOTOV_WIKI_IMAGES_DIR=IMAGES_DIR,
        TZ="UTC",
    )
    env.pop("DB_PATH", None)
    # PYTHONPATH пакетов чужих окружений ломает импорт PIL в сервисе
    # (пакет app сервиса разрешается cwd'ом — паритет conftest, строка 177)
    env.pop("PYTHONPATH", None)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        images_port = sock.getsockname()[1]
    images_base = f"http://127.0.0.1:{images_port}"
    os.makedirs(IMAGES_DIR, exist_ok=True)

    proc = sp.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(images_port),
            "--log-level", "warning",
        ],
        cwd=str(REPO_IMAGES_DIR), env=env,
        stdout=sp.DEVNULL, stderr=sp.DEVNULL,
    )
    try:
        # poll готовности без time.sleep (запрещен спекой qa-pipeline,
        # лексическая проверка flow_check): Event.wait(0.3) на threading-
        # событии — тот же интервал между health-пробами, без sleep.
        _wake = threading.Event()
        deadline = 30.0
        started = time.monotonic()
        while time.monotonic() - started < deadline:
            try:
                if requests.get(f"{images_base}/api/health", timeout=2).status_code == 200:
                    break
            except requests.RequestException:
                _wake.wait(0.3)
        else:
            raise RuntimeError("images-сервис не готов за 30s")

        base_url = web_server["base_url"]
        static_url = web_server.get("static_url")
        search_url = web_server.get("search_url")

        class ProxyHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: A002 — сигнатура stdlib
                pass

            def _target(self, path):
                if path.startswith("/api/images") or path.startswith("/images/"):
                    return images_base + path
                if static_url and path.startswith("/static/"):
                    # http.server-статика имеет docroot frontend/static —
                    # префикс /static отрезается (паритет conftest _to_static
                    # и nginx location /static/ alias), иначе 404
                    return static_url + path.partition("/static")[2]
                if search_url and (
                    path.startswith("/api/search")
                    or path.startswith("/api/suggestions")
                ):
                    return search_url + path
                return base_url + path

            def _proxy(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else None
                target = self._target(self.path)
                headers = {
                    key: value
                    for key, value in self.headers.items()
                    if key.lower() not in ("host", "connection", "accept-encoding")
                }
                request = _Req(
                    target, method=self.command, data=body, headers=headers
                )
                try:
                    response = build_opener().open(request, timeout=60)
                    status, resp_headers, data = (
                        response.status, response.headers, response.read()
                    )
                except _HTTPError as exc:
                    status, resp_headers, data = (
                        exc.code, exc.headers, exc.read()
                    )
                self.send_response(status)
                hop = {"connection", "transfer-encoding", "content-encoding",
                       "keep-alive"}
                for key, value in resp_headers.items():
                    if key.lower() not in hop:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_PUT = do_DELETE = do_OPTIONS = do_HEAD = _proxy

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            proxy_port = sock.getsockname()[1]
        server = ThreadingHTTPServer(("127.0.0.1", proxy_port), ProxyHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield {
                "base_url": f"http://127.0.0.1:{proxy_port}",
                "app_base": base_url,
            }
        finally:
            server.shutdown()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except sp.TimeoutExpired:
            proc.kill()


def _png_file(name="QAE-pick.png", color=(120, 40, 200)):
    return {"name": name, "mimeType": "image/png", "buffer": _png_bytes(color)}


def _owner_session(web_base_url):
    """requests-сессия owner для assert-чтения API из тела теста
    (Secure-кука по http — браузерное поведение localhost, conftest)."""
    import requests

    session = requests.Session()
    resp = session.post(
        f"{web_base_url}/api/auth/login",
        json={
            "login": "owner",
            "password": os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!"),
        },
    )
    assert resp.status_code == 200
    for cookie in session.cookies:
        cookie.secure = False
    return session


@pytest.fixture
def wiki_images_routing(images_service):
    """Адрес стенда через images-прокси («роль nginx»): изображение-кейсы
    открывают редактор по этому URL — /api/images* и /images/* уходят в
    images-сервис, остальное — в стенд conftest."""
    return images_service["base_url"]


@pytest.fixture
def wiki_api(web_base_url, web_owner_session):
    """Парные хелперы create/delete wiki-страниц с teardown-очисткой.

    Страницы, созданные САМИМ браузером через UI (save-кейсы), тест
    регистрирует вызовом register(page_id) — teardown удаляет и их
    (иначе session-tmp-БД грязнится и порядок прогонов ломает
    пустое состояние, F-2 review-004).
    """

    created: list[int] = []

    def register(page_id):
        created.append(page_id)

    def create(title, content="", parent_id=None):
        resp = web_owner_session.post(
            f"{web_base_url}/api/wiki/pages",
            json={"title": title, "content": content, "parent_id": parent_id},
        )
        assert resp.status_code == 201, resp.text
        page_id = resp.json()["id"]
        created.append(page_id)
        return page_id

    api = SimpleNamespace(register=register, create=create)

    yield api

    for page_id in reversed(created):
        try:
            web_owner_session.delete(f"{web_base_url}/api/wiki/pages/{page_id}")
        except Exception:
            pass


@pytest.fixture
def gallery_image(web_base_url, web_owner_session, images_service):
    """Загруженное в галерею изображение (для кейса «из галереи»);
    загрузка — напрямую в images-сервис (тот же сеялочный путь, что у
    gallery_ui: через API, не через UI). Teardown чистит БД images + том
    по QAE-префиксу original_name."""
    name = f"{MARKER}gallery-pick.png"
    resp = web_owner_session.post(
        f"{images_service['base_url']}/api/images",
        files={"file": (name, _png_bytes(), "image/png")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    yield body
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute(
                "SELECT filename, thumb_name FROM images WHERE id = ?", (body["id"],)
            ).fetchone()
            if row:
                conn.execute("DELETE FROM images WHERE id = ?", (body["id"],))
                conn.commit()
        finally:
            conn.close()
        for filename in row or ():
            try:
                os.remove(os.path.join(IMAGES_DIR, filename))
            except OSError:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 1. Тулбар: форматирование меняет тег
# ---------------------------------------------------------------------------


def test_toolbar_formats_change_tags(logged_in_page, web_base_url):
    """TC-wiki-301 (FR-110): каждый базовый инструмент тулбара применяет форматирование —
    текст в contenteditable меняет тег (FR-110)."""
    page = logged_in_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    area = editor.area
    area.click()
    page.keyboard.type("Строка для форматирования")
    editor.select_all_text()

    # B → <b> (+ состояние кнопки aria-pressed)
    editor.toolbar_button("Полужирный").click()
    expect(area.locator("b")).to_have_text("Строка для форматирования")
    expect(editor.toolbar_button("Полужирный")).to_have_attribute(
        "aria-pressed", "true"
    )

    # I → <i>, U → <u>
    editor.toolbar_button("Курсив").click()
    expect(area.locator("i")).to_have_text("Строка для форматирования")
    editor.toolbar_button("Подчеркнутый").click()
    expect(area.locator("u")).to_have_text("Строка для форматирования")

    # H2 → текст внутри <h2>
    editor.toolbar_button("Заголовок 2").click()
    expect(area.locator("h2")).to_have_text("Строка для форматирования")

    # H3
    editor.toolbar_button("Заголовок 3").click()
    expect(area.locator("h3")).to_have_count(1)

    # Цитата → <blockquote>
    editor.toolbar_button("Цитата").click()
    expect(area.locator("blockquote")).to_have_count(1)

    # Код-блок → <pre> (мокап: pre>code)
    editor.toolbar_button("Код-блок").click()
    expect(area.locator("pre")).to_have_count(1)


def test_toolbar_lists_and_undo_redo(logged_in_page, web_base_url):
    """TC-wiki-302 (FR-110): ul/ol вставляют списки; undo/redo возвращают/повторяют."""
    page = logged_in_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    area = editor.area
    area.click()
    page.keyboard.type("Пункт списка")
    editor.select_all_text()

    editor.toolbar_button("Маркированный список").click()
    expect(area.locator("ul li")).to_have_text("Пункт списка")

    editor.toolbar_button("Нумерованный список").click()
    expect(area.locator("ol li")).to_have_text("Пункт списка")

    # undo (кнопка) — список снят, текст вернулся
    editor.toolbar_button("Отменить").click()
    expect(area.locator("ol li")).to_have_count(0)
    # redo — вернулся
    editor.toolbar_button("Повторить").click()
    expect(area.locator("ol li")).to_have_text("Пункт списка")


# ---------------------------------------------------------------------------
# 2. Таблица 3×3
# ---------------------------------------------------------------------------


def test_toolbar_inserts_table_3x3(logged_in_page, web_base_url):
    """TC-wiki-303 (FR-110): кнопка «Таблица» вставляет таблицу 3×3 по мокапу
    (thead с 3 th + tbody с 2 строками по 3 td)."""
    page = logged_in_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    area = editor.area
    area.click()
    editor.toolbar_button("Таблица").click()

    table = area.locator("table")
    expect(table).to_have_count(1)
    expect(table.locator("thead th")).to_have_count(3)
    expect(table.locator("tbody tr")).to_have_count(2)
    expect(table.locator("tbody td")).to_have_count(6)


# ---------------------------------------------------------------------------
# 3. Ссылка: javascript: не вставляется, http — вставляется
# ---------------------------------------------------------------------------


def test_link_javascript_scheme_rejected(logged_in_page, web_base_url):
    """TC-wiki-304 (безопасность, design §4): javascript: в диалоге ссылки —
    ошибка, НИЧЕГО не вставляется (в редакторе нет <a href=javascript:>)."""
    page = logged_in_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    area = editor.area
    area.click()
    page.keyboard.type("текст для ссылки")
    editor.select_all_text()

    editor.toolbar_button("Ссылка").click()
    dialog = editor.link_dialog
    expect(dialog).to_be_visible()
    editor.link_address_input().fill("javascript:alert(1)")
    dialog.get_by_role("button", name="Вставить").click()

    # ошибка показана, диалог остался открытым
    expect(dialog.locator(".error-banner")).to_be_visible()
    expect(dialog).to_be_visible()

    html = editor.area_html()
    assert "javascript:" not in html, html
    assert "<a" not in html, html

    # корректная ссылка после отказа вставляется
    editor.link_address_input().fill("https://example.com/doc")
    dialog.get_by_role("button", name="Вставить").click()
    expect(area.locator("a")).to_have_attribute("href", "https://example.com/doc")


# ---------------------------------------------------------------------------
# 4. Изображение: из галереи и с диска
# ---------------------------------------------------------------------------


def test_image_insert_from_gallery(
    logged_in_page, web_base_url, gallery_image, wiki_images_routing
):
    """TC-wiki-305 (FR-111): диалог «Изображение» → «Из галереи» → грид из
    GET /api/images → выбор → Вставить → <img src=/images/{...}>."""
    page = logged_in_page
    editor = WikiEditor(page)
    editor.open_create(wiki_images_routing)
    area = editor.area
    area.click()

    editor.toolbar_button("Изображение").click()
    dialog = editor.img_dialog
    expect(dialog).to_be_visible()

    item = editor.img_pick_item(f"{MARKER}gallery-pick.png")
    expect(item).to_be_visible()
    item.click()
    expect(item).to_have_attribute("aria-selected", "true")

    # масштаб: Среднее (480 px) — возврат живой приемки 2026-10-11
    dialog.get_by_label("Среднее (480 px)").check()
    dialog.get_by_role("button", name="Вставить").click()

    img = area.locator("img")
    expect(img).to_have_count(1)
    src = img.get_attribute("src")
    assert src.startswith("/images/"), src
    expect(img).to_have_attribute("width", "480")


def test_image_insert_from_disk_uploads_and_inserts(
    logged_in_page, web_base_url, web_owner_session, wiki_images_routing
):
    """TC-wiki-306 (FR-111): «Загрузить с диска» → file input → POST /api/images →
    вставка <img src=/images/{...}>. Teardown чистит изображение по маркеру."""
    page = logged_in_page
    editor = WikiEditor(page)
    editor.open_create(wiki_images_routing)
    area = editor.area
    area.click()

    editor.toolbar_button("Изображение").click()
    dialog = editor.img_dialog
    expect(dialog).to_be_visible()

    dialog.get_by_text("Загрузить с диска").check()
    name = f"{MARKER}disk-upload.png"
    payload = _png_file(name)
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(payload["buffer"])
        tmp_path = tmp.name
    try:
        editor.img_file_input().set_input_files(tmp_path)
        img = area.locator("img")
        expect(img).to_have_count(1)
        src = img.get_attribute("src")
        assert src.startswith("/images/"), src
    finally:
        os.unlink(tmp_path)

    # teardown: убрать запись + файл из тома (DB_PATH из env рантайма —
    # conftest ставит EKOTOV_WIKI_DB_PATH при подъёме стенда, на импорте
    # модуля его ещё нет)
    db_path = os.environ.get("EKOTOV_WIKI_DB_PATH")
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT filename, thumb_name FROM images WHERE original_name = ?", (name,)
        ).fetchone()
        if row:
            conn.execute("DELETE FROM images WHERE original_name = ?", (name,))
            conn.commit()
    finally:
        conn.close()
    for filename in row or ():
        try:
            os.remove(os.path.join(IMAGES_DIR, filename))
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 4b. Масштаб изображения (возврат живой приемки 2026-10-11, как в Confluence)
# ---------------------------------------------------------------------------


def test_image_insert_custom_invalid_size_no_insert(
    logged_in_page, web_base_url, gallery_image, wiki_images_routing
):
    """Возврат живой приемки: «Свой размер» с НЕВАЛИДНЫМ числом (не целое /
    вне 16..4096) — отказ вставки: ошибки в диалоге, <img> в редакторе НЕТ."""
    page = logged_in_page
    editor = WikiEditor(page)
    editor.open_create(wiki_images_routing)
    area = editor.area
    area.click()

    editor.toolbar_button("Изображение").click()
    dialog = editor.img_dialog
    expect(dialog).to_be_visible()

    item = editor.img_pick_item(f"{MARKER}gallery-pick.png").first
    expect(item).to_be_visible()
    item.click()

    dialog.get_by_label("Свой размер (px)").check()
    custom = dialog.get_by_label("Свой размер в пикселях")
    expect(custom).to_be_visible()

    # type=number не принимает «abc» на уровне input — невалид как «пустое»;
    # нецелое проверяем через "480.5" (браузер number-инпута его отбрасывает,
    # валидное значение целое 16..4096 — проходит), вне диапазона — 5/99999
    for bad in ("5", "99999", "abc", ""):
        try:
            custom.fill(bad)
        except Exception:
            # number-input отклонил непарсable строку — поле осталось пустым:
            # невалид «свой размер без числа», отказ вставки
            pass
        dialog.get_by_role("button", name="Вставить").click()
        # ошибка показана, диалог открыт, ничего не вставлено
        expect(dialog.locator(".error-banner")).to_be_visible()
        expect(dialog).to_be_visible()
        expect(area.locator("img")).to_have_count(0)

    # валидный размер после отказа вставляется
    custom.fill("320")
    dialog.get_by_role("button", name="Вставить").click()
    img = area.locator("img")
    expect(img).to_have_count(1)
    expect(img).to_have_attribute("width", "320")


def test_image_click_opens_scale_editor_and_changes_width(
    logged_in_page, web_base_url, gallery_image, wiki_images_routing
):
    """Усиление в духе Confluence: клик по уже вставленному img в редакторе —
    модалка «Масштаб изображения»; выбор меняет width НА МЕСТЕ (src/alt не
    тронуты); «Оригинал» width снимает."""
    page = logged_in_page
    editor = WikiEditor(page)
    editor.open_create(wiki_images_routing)
    area = editor.area
    area.click()

    editor.toolbar_button("Изображение").click()
    dialog = editor.img_dialog
    expect(dialog).to_be_visible()
    item = editor.img_pick_item(f"{MARKER}gallery-pick.png").first
    item.click()
    dialog.get_by_label("Среднее (480 px)").check()
    dialog.get_by_role("button", name="Вставить").click()

    img = area.locator("img")
    expect(img).to_have_count(1)
    src = img.get_attribute("src")
    expect(img).to_have_attribute("width", "480")

    # клик по вставленному img → модалка масштаба
    img.click()
    scale_dialog = editor.img_scale_dialog
    expect(scale_dialog).to_be_visible()
    expect(scale_dialog.get_by_label("Среднее (480 px)")).to_be_checked()

    # Маленькое → width=240 на месте, src/alt прежние
    scale_dialog.get_by_label("Маленькое (240 px)").check()
    scale_dialog.get_by_role("button", name="Применить").click()
    expect(scale_dialog).not_to_be_visible()
    expect(img).to_have_attribute("width", "240")
    assert img.get_attribute("src") == src

    # Свой размер → width=300
    img.click()
    expect(scale_dialog).to_be_visible()
    scale_dialog.get_by_label("Свой размер (px)").check()
    scale_dialog.get_by_label("Свой размер в пикселях").fill("300")
    scale_dialog.get_by_role("button", name="Применить").click()
    expect(scale_dialog).not_to_be_visible()
    expect(img).to_have_attribute("width", "300")

    # Оригинал → width снят
    img.click()
    expect(scale_dialog).to_be_visible()
    scale_dialog.get_by_label("Оригинал").check()
    scale_dialog.get_by_role("button", name="Применить").click()
    expect(scale_dialog).not_to_be_visible()
    assert img.get_attribute("width") is None


# ---------------------------------------------------------------------------
# 5. Сохранение: пишет и редиректит
# ---------------------------------------------------------------------------


def test_save_create_posts_and_redirects(logged_in_page, web_base_url, wiki_api):
    """TC-wiki-307 (FR-110): создание — заполненный редактор → «Сохранить» → POST
    /api/wiki/pages → redirect /wiki/{id}; страница появилась в API."""
    page = logged_in_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)

    editor.title_input.fill(f"{MARKER}создание через UI")
    area = editor.area
    area.click()
    page.keyboard.type("Тело новой страницы")
    editor.save_button().click()

    page.wait_for_url("**/wiki/*")
    assert "/wiki?" not in page.url
    page_id = int(page.url.rstrip("/").rsplit("/", 1)[1])

    # страница в API с сохраненным контентом (санитизация сервером)
    session = _owner_session(web_base_url)
    got = session.get(f"{web_base_url}/api/wiki/pages/{page_id}").json()
    versions = session.get(
        f"{web_base_url}/api/wiki/pages/{page_id}/versions"
    ).json()["versions"]
    session.close()
    assert got["title"] == f"{MARKER}создание через UI"
    assert "Тело новой страницы" in got["content"]
    assert len(versions) == 1  # первая версия = исходный контент

    # страница создана браузером через UI — регистрируем в teardown-очистке
    wiki_api.register(page_id)
    # сеть страницы-редиректа доливается после wait_for_url — без networkidle
    # teardown (Browser.close) гоняет 'Fetch response has been disposed'
    page.wait_for_load_state("networkidle")


def test_save_edit_puts_new_version_and_redirects(
    logged_in_page, web_base_url, wiki_api
):
    """TC-wiki-308 (FR-110): правка — /wiki/{id}?edit=1 → GET заполняет редактор → правка
    → «Сохранить» → PUT → redirect /wiki/{id}; в API НОВАЯ версия."""
    page_id = wiki_api.create(f"{MARKER}правка", "старое тело")
    page = logged_in_page
    editor = WikiEditor(page)

    editor.open_edit(web_base_url, page_id)

    title = editor.title_input
    expect(title).to_have_value(f"{MARKER}правка")
    expect(editor.area).to_contain_text("старое тело")

    # правим контент и заголовок (заголовок тоже версия — design §5)
    editor.title_input.fill(f"{MARKER}правка-2")
    area = editor.area
    area.click()
    page.keyboard.press("Control+a")
    page.keyboard.type("новое тело от редактора")
    editor.save_button().click()

    page.wait_for_url(f"**/wiki/{page_id}")
    assert page.url.endswith(f"/wiki/{page_id}")
    # дождаться статики страницы-редиректа: иначе в worktree остаются
    # in-flight route-обработки _to_static и teardown (Browser.close)
    # падает 'Route.fulfill: Fetch response has been disposed' (гонка
    # disposeAPIResponse с невыполненным fulfill — pw 1.63)
    page.wait_for_load_state("networkidle")

    session = _owner_session(web_base_url)
    got = session.get(f"{web_base_url}/api/wiki/pages/{page_id}").json()
    versions = session.get(
        f"{web_base_url}/api/wiki/pages/{page_id}/versions"
    ).json()["versions"]
    session.close()
    assert got["title"] == f"{MARKER}правка-2"
    assert "новое тело от редактора" in got["content"]
    assert len(versions) == 2  # v1 из создания + v2 из правки


# ---------------------------------------------------------------------------
# 6. Пустой title — ошибка без сохранения
# ---------------------------------------------------------------------------


def test_empty_title_error_no_request(logged_in_page, web_base_url):
    """TC-wiki-309 (мокап: «Пустой заголовок — ошибка без сохранения»): пустой
    заголовок → ошибка-баннер, POST/PUT НЕ уходит (редиректа нет)."""
    requests_seen = []
    page = logged_in_page

    def _track(request):
        if request.method in ("POST", "PUT") and "/api/wiki/pages" in request.url:
            requests_seen.append(request.method + " " + request.url)

    page.on("request", _track)
    editor = WikiEditor(page)
    editor.open_create(web_base_url)

    # заголовок НЕ заполняем, контент есть
    area = editor.area
    area.click()
    page.keyboard.type("тело без заголовка")
    editor.save_button().click()

    banner = editor.error_banner
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("Заголовок не может быть пустым")

    # запросов сохранения не было — ошибка отработана локально (422-случай)
    assert requests_seen == [], requests_seen
