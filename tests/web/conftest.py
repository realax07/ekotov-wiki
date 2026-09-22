"""Тестовый стенд web-сьюта: uvicorn (app) + python -m http.server (static).

Продуктовая архитектура (sdd.md §1/§3.6, design §8): nginx раздает статику
frontend/static/ и проксирует остальное на uvicorn; в app.static НЕ смонтирована
(review 2.3, замечание 2 — «монтирование в app противоречило бы design»).
Локальный стенд повторяет прод-топологию двумя процессами:
- uvicorn app.main:app на свободном порту (API + Jinja2-страницы);
- http.server на соседнем свободном порту с docroot frontend/ (файлы /static/*).
Playwright-маршрутизация: запросы {base}/static/* перебрасываются на
static_url, остальные идут в app — единый origin для браузера, куки работают.

Временная пустая SQLite-БД + seed owner/wife (тестовые пароли кейсов, NFR-7).
EKOTOV_WIKI_DB_PATH выставляется на сессию — DB-крюки TC-UI-017/018 работают
из коробки. Заданный снаружи EKOTOV_WIKI_BASE_URL отключает автоподъем стенда
(внешний стенд; статика должна раздаваться им самим — как на VPS).
"""

import functools
import http.server
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"

BASE_URL_ENV = "EKOTOV_WIKI_BASE_URL"
DB_PATH_ENV = "EKOTOV_WIKI_DB_PATH"

# Тестовые учетные данные seed-пользователей (значения кейсов ui-01.md,
# без секретности — NFR-7; env-переопределение как в tests/api/conftest.py).
OWNER_LOGIN = "owner"
OWNER_PASSWORD = os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!")
WIFE_LOGIN = "wife"
WIFE_PASSWORD = os.environ.get("EKOTOV_WIKI_WIFE_PASSWORD", "QaWife_Pass_2!")

pytest_plugins = ["pytest_playwright"]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# Seed справочника категорий (CHK-139 / TC-env-001, add-r2-categories-settings):
# «Дом», «Работа», «Личное» — заведение session-scope ДО любого прогона
# (жесткая валидация FR-21: задача с непустой категорией вне справочника — 422).
SEED_CATEGORIES = ("Дом", "Работа", "Личное")


def _seed_users(db_path: str, owner_password: str, wife_password: str) -> None:
    """Заведение owner/wife с тестовыми паролями прямо в БД (bcrypt,
    как app.seed_users.seed_user, но без интерактивного getpass)."""
    import bcrypt
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        for login, password in (("owner", owner_password), ("wife", wife_password)):
            conn.execute(
                "INSERT INTO users (login, password_hash) VALUES (?, ?)",
                (login, bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()),
            )
        # Seed справочника (CHK-139/TC-env-001): INSERT OR IGNORE — идемпотентно.
        for name in SEED_CATEGORIES:
            conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
        conn.commit()
    finally:
        conn.close()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 — сигнатура stdlib
        pass  # шум http.server в pytest-вывод не нужен


def _start_static_server() -> tuple[subprocess.Popen, int]:
    """http.server с docroot frontend/static — роль nginx'а по статике
    (design §8): URL /static/css/app.css → файл static/css/app.css."""
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=FRONTEND_DIR / "static",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc, port


@pytest.fixture(scope="session")
def web_server(request):
    """Тест-стенд сессии: uvicorn + static + временная БД + seed."""
    external_base_url = os.environ.get(BASE_URL_ENV)
    if external_base_url:
        yield {"base_url": external_base_url.rstrip("/"), "db_path": os.environ.get(DB_PATH_ENV), "static_url": None}
        return

    tmp = tempfile.TemporaryDirectory(prefix="ekotov-web-tests-")
    db_path = str(Path(tmp.name) / "app.db")
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    # Схема + seed в отдельном процессе (модуль app из backend/).
    env = dict(os.environ, DB_PATH=db_path, SECRET_KEY="web-tests-secret-key", TZ="UTC")
    subprocess.run(
        [sys.executable, "-m", "app.db"],
        cwd=BACKEND_DIR, env=env, check=True, capture_output=True,
    )
    _seed_users(db_path, OWNER_PASSWORD, WIFE_PASSWORD)

    server = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
        ],
        cwd=BACKEND_DIR, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    static_proc, static_port = _start_static_server()
    try:
        deadline = 60.0
        started = time.monotonic()
        last_error = None
        while time.monotonic() - started < deadline:
            try:
                resp = requests.get(f"{base_url}/api/health", timeout=2)
                if resp.status_code == 200 and resp.json() == {"status": "ok"}:
                    break
            except requests.RequestException as exc:
                last_error = exc
            time.sleep(0.3)
        else:
            raise RuntimeError(f"Тест-стенд {base_url} не готов за {deadline}s: {last_error}")

        # DB-крюки кейсов (TC-UI-017/018) — env на время сессии.
        os.environ[BASE_URL_ENV] = base_url
        os.environ[DB_PATH_ENV] = db_path
        yield {
            "base_url": base_url,
            "db_path": db_path,
            "static_url": f"http://127.0.0.1:{static_port}",
        }
    finally:
        server.terminate()
        static_proc.terminate()
        for proc in (server, static_proc):
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        os.environ.pop(BASE_URL_ENV, None)
        os.environ.pop(DB_PATH_ENV, None)
        tmp.cleanup()


@pytest.fixture(scope="session")
def web_base_url(web_server) -> str:
    """Корень тест-стенда для страниц и API (кейс: {BASE_URL})."""
    return web_server["base_url"]


@pytest.fixture
def web_db_path(web_server) -> str:
    """Путь SQLite-БД стенда (DB-крюк: UPDATE tasks SET done_at ...)."""
    db_path = web_server["db_path"]
    if not db_path:
        pytest.skip(f"нужен {DB_PATH_ENV} (путь SQLite-БД тест-стенда)")
    return db_path


@pytest.fixture
def page(page, web_server):
    """Обертка playwright-page: статика /static/* — с http.server-стенда
    (роль nginx, design §8), остальное — напрямую в app."""
    static_url = web_server["static_url"]
    if static_url:
        def _to_static(route):
            new_url = static_url + route.request.url.partition("/static")[2]
            route.fulfill(response=route.fetch(url=new_url))

        page.route(f"{web_server['base_url']}/static/**", _to_static)
    yield page


class LocalhostSession(requests.Session):
    """requests.Session, отправляющая Secure-куки по http на localhost/127.0.0.1.

    Продукт ставит куку session с флагом Secure (sdd §3.1) — requests по http
    ее НЕ отправляет, браузеры же (Playwright/Chrome) считают localhost
    trustworthy origin и отправляют (RFC 6265bis). Чтобы teardown-хелпер
    (DELETE /api/tasks/{id}) работал по http-стенду так же, как браузер,
    повторяем браузерное поведение — как в tests/api/conftest.py.
    """

    _LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")

    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)
        is_http_local = response.url.startswith("http://") and any(
            f"//{host}:" in response.url for host in self._LOCAL_HOSTS
        )
        if is_http_local:
            for cookie in self.cookies:
                if cookie.secure:
                    cookie.secure = False
        return response


@pytest.fixture
def http():
    """requests-сессия с cookie-банкой (teardown-хелпер, как tests/api)."""
    session = LocalhostSession()
    yield session
    session.close()


@pytest.fixture
def web_owner_session(web_base_url, http):
    """API-сессия owner для setup/teardown теста (не для ассертов кейса)."""
    resp = http.post(
        f"{web_base_url}/api/auth/login",
        json={"login": OWNER_LOGIN, "password": OWNER_PASSWORD},
    )
    assert resp.status_code == 200, f"seed-вход owner не удался: {resp.status_code} {resp.text}"
    return http


@pytest.fixture
def web_cleanup_created(web_base_url, web_owner_session):
    """Фабрика трекинга задач с гарантированным удалением в teardown.

    Удаляет физически (DELETE /api/tasks/{id}), включая архивированные —
    автоархивация не оставляет хвостов после упавшего/пройденного теста.
    """
    created: list[int] = []

    def _track(task_id: int) -> None:
        created.append(task_id)

    yield _track

    for task_id in created:
        try:
            web_owner_session.delete(f"{web_base_url}/api/tasks/{task_id}")
        except requests.RequestException:
            pass


@pytest.fixture
def logged_in_page(page, web_base_url):
    """Страница с выполненным входом owner (предусловие большинства кейсов).

    Вход — как в TC-UI-002: /login → fill Логин/Пароль → «Войти» → доска.
    """
    page.goto(f"{web_base_url}/login")
    page.get_by_label("Логин").fill(OWNER_LOGIN)
    page.get_by_label("Пароль").fill(OWNER_PASSWORD)
    page.get_by_role("button", name="Войти").click()
    page.get_by_role("heading", name="Доска", exact=True).wait_for()
    return page


@pytest.fixture
def board_page(logged_in_page):
    """Доска загружена: data-loaded=true (предусловие кейсов создания)."""
    expect_board_loaded(logged_in_page)
    return logged_in_page


def expect_board_loaded(page) -> None:
    """Автожидание готовности доски (без sleep): #board data-loaded=true."""
    from playwright.sync_api import expect

    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")


def create_task_via_ui(
    page,
    title: str,
    *,
    description: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    due_date: str | None = None,
    tags: str | None = None,
    is_fast: bool = False,
) -> None:
    """Создание задачи через UI-форму (шаги кейсов TC-UI-007/009/010).

    Категория — select из справочника (3.1, FR-19/FR-30): выбор только
    select_option (кейс CHK-146: ни одного .fill() на поле категории);
    значения берутся из seed справочника (CHK-139: «Дом», «Работа»,
    «Личное») или созданного самим тестом."""
    page.get_by_role("button", name="Создать задачу").click()
    page.get_by_label("Название").fill(title)
    if description is not None:
        page.get_by_label("Описание").fill(description)
    if priority is not None:
        page.get_by_label("Приоритет").select_option(priority)
    if category is not None:
        page.get_by_label("Категория").select_option(category)
    if due_date is not None:
        page.get_by_label("Срок").fill(due_date)
    if tags is not None:
        page.get_by_label("Теги (через запятую)").fill(tags)
    if is_fast:
        page.get_by_label("fast line").check()
    page.get_by_role("button", name="Создать", exact=True).click()
    expect_form_hidden(page)


def expect_form_hidden(page) -> None:
    from playwright.sync_api import expect

    expect(page.locator("#task-form-overlay")).to_be_hidden()


def move_via_card_select(page, title: str, status: str) -> None:
    """Перемещение задачи через селект «Столбец» в ее карточке
    (механика кейсов TC-UI-012/017/018).

    Автожидание факта перемещения: карточка появилась в целевом столбце
    (это гарантирует и завершение POST /move на сервере, и рефреш доски —
    важно для DB-крюков TC-UI-017/018, идущих сразу после перемещения:
    wait по заголовку столбца гонку с POST не закрывает)."""
    from playwright.sync_api import expect

    card = page.get_by_role("article").filter(has_text=title)
    card.click()
    page.get_by_label("Столбец").select_option(status)
    column = page.locator(f'[data-status="{status}"]')
    expect(column.get_by_role("article").filter(has_text=title)).to_be_visible()
