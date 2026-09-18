"""Фикстуры API-тестов add-kanban-core (скилл test-automation).

- ``base_url`` — из env ``EKOTOV_WIKI_BASE_URL`` (дефолт локального прогона);
- ``http`` — requests.Session с включенной cookie-банкой (сессия авторизации
  переносится между запросами теста, как curl -c/-b cookies.txt);
- ``owner_session`` / ``wife_session`` — отдельные сессии с выполненным входом
  (логины seed: owner/wife; пароли — из env, тестовые значения без секретности);
- ``api`` — helper: имена методов, создание/чтение/удаление тестовых задач.

Изоляция: каждый тест создает свои данные (уникальный префикс ``QAT-``) и
удаляет их в teardown (fixture-финализаторы + ``cleanup_task``). Детерминизм:
никаких sleep — готовность сервера проверяется poll-циклом с таймаутом.
"""

import os
import uuid

import pytest
import requests

BASE_URL_ENV = "EKOTOV_WIKI_BASE_URL"
DEFAULT_BASE_URL = "http://127.0.0.1:8080"

# Тестовые учетные данные seed-пользователей (значения только тестовые,
# заведены seed-скриптом; в артефакты продукта не попадают — NFR-7).
OWNER_LOGIN = "owner"
OWNER_PASSWORD = os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!")
WIFE_LOGIN = "wife"
WIFE_PASSWORD = os.environ.get("EKOTOV_WIKI_WIFE_PASSWORD", "QaWife_Pass_2!")

TITLE_PREFIX = "QAT-"  # префикс автотестов: безопасная очистка своих данных


def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        action="store",
        default=None,
        help="Базовый URL приложения (иначе env EKOTOV_WIKI_BASE_URL / локальный дефолт)",
    )


def _resolve_base_url(config) -> str:
    return (
        config.getoption("--base-url")
        or os.environ.get(BASE_URL_ENV)
        or DEFAULT_BASE_URL
    )


@pytest.fixture(scope="session")
def base_url(request) -> str:
    """Корень развернутого приложения (без завершающего слеша)."""
    url = _resolve_base_url(request.config).rstrip("/")
    # Детерминированное ожидание готовности (без sleep: poll-цикл с таймаутом)
    deadline = 60.0
    import time

    started = time.monotonic()
    last_error = None
    while time.monotonic() - started < deadline:
        try:
            resp = requests.get(f"{url}/api/health", timeout=2)
            if resp.status_code == 200 and resp.json() == {"status": "ok"}:
                return url
        except requests.RequestException as exc:  # сервер еще не поднялся
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(
        f"Приложение {url} не готово за {deadline}s (health): {last_error}"
    )


@pytest.fixture
def http() -> requests.Session:
    """HTTP-сессия с cookie-банкой (аналог curl -c/-b cookies.txt).

    Продукт ставит куку session с флагом Secure (sdd §3.1) — по https-развертыванию
    requests отправляет ее штатно. Для локального прогона по http куки Secure
    requests'ом НЕ отправляются; браузеры же (Chrome/Firefox) считают localhost
    trustworthy-источником и Secure-куки по http://localhost отправляют
    (RFC 6265bis, trustworthy origin). Локальная сессия повторяет это
    браузерное поведение: снимает флаг secure у кук http-ответов localhost.
    """
    session = LocalhostSession()
    yield session
    session.close()


class LocalhostSession(requests.Session):
    """requests.Session, отправляющая Secure-куки по http на localhost/127.0.0.1
    (браузерное поведение trustworthy origin — см. docstring фикстуры http)."""

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


def login_session(base_url: str, login: str, password: str) -> requests.Session:
    """Новая сессия с выполненным входом (200 + кука session)."""
    session = LocalhostSession()
    resp = session.post(
        f"{base_url}/api/auth/login",
        json={"login": login, "password": password},
    )
    assert resp.status_code == 200, f"seed-вход {login} не удался: {resp.status_code} {resp.text}"
    return session


@pytest.fixture
def owner_session(base_url) -> requests.Session:
    """Сессия owner — на каждый тест (function-scope): тесты expire/logout
    инвалидируют сессию, общая сессия ломала бы изоляцию последующих тестов."""
    session = login_session(base_url, OWNER_LOGIN, OWNER_PASSWORD)
    yield session
    session.close()


@pytest.fixture
def wife_session(base_url) -> requests.Session:
    """Сессия wife; создается на тест и закрывается после него."""
    session = login_session(base_url, WIFE_LOGIN, WIFE_PASSWORD)
    yield session
    session.close()


class Api:
    """Хелпер API-операций над задачами: создание/чтение/удаление/поиск."""

    def __init__(self, base_url: str, session: requests.Session):
        self.base_url = base_url
        self.session = session

    # --- низкоуровневые -------------------------------------------------
    def create(self, **payload):
        return self.session.post(f"{self.base_url}/api/tasks", json=payload)

    def get_task(self, task_id):
        return self.session.get(f"{self.base_url}/api/tasks/{task_id}")

    def patch(self, task_id, **payload):
        return self.session.patch(f"{self.base_url}/api/tasks/{task_id}", json=payload)

    def delete(self, task_id):
        return self.session.delete(f"{self.base_url}/api/tasks/{task_id}")

    def move(self, task_id, status: str):
        return self.session.post(
            f"{self.base_url}/api/tasks/{task_id}/move", json={"status": status}
        )

    def board(self):
        return self.session.get(f"{self.base_url}/api/board")

    def search(self, **params):
        return self.session.get(f"{self.base_url}/api/search", params=params)

    def advanced(self, query: str):
        return self.session.post(
            f"{self.base_url}/api/search/advanced", json={"query": query}
        )

    def comments(self, task_id):
        return self.session.get(f"{self.base_url}/api/tasks/{task_id}/comments")

    def add_comment(self, task_id, body: str):
        return self.session.post(
            f"{self.base_url}/api/tasks/{task_id}/comments", json={"body": body}
        )

    # --- высокоуровневые -------------------------------------------------
    def create_ok(self, title: str, **payload) -> dict:
        """Создать задачу, вернуть Task-объект (падение = дефект окружения)."""
        resp = self.create(title=title, **payload)
        assert resp.status_code == 201, f"setup: создание {title!r}: {resp.status_code} {resp.text}"
        return resp.json()

    def cleanup_all(self) -> None:
        """Удалить все задачи с префиксом автотестов (изоляция прогонов)."""
        resp = self.search(archived="all")
        if resp.status_code != 200:
            return
        for task in resp.json().get("results", []):
            if str(task.get("title", "")).startswith(TITLE_PREFIX):
                self.delete(task["id"])


@pytest.fixture
def api(base_url, owner_session) -> Api:
    """API-хелпер от имени owner + очистка своих тестовых данных в teardown."""
    helper = Api(base_url, owner_session)
    helper.cleanup_all()  # убрать хвосты прошлого упавшего прогона
    yield helper
    helper.cleanup_all()


@pytest.fixture
def unique_title() -> str:
    """Уникальное название тестовой задачи (изоляция от параллельных прогонов)."""
    return f"{TITLE_PREFIX}{uuid.uuid4().hex[:8]}"


@pytest.fixture
def cleanup_task(api):
    """Фабрика задач с гарантированным удалением в teardown (даже без префикса)."""
    created: list[int] = []

    def _make(title: str, **payload) -> dict:
        task = api.create_ok(title, **payload)
        created.append(task["id"])
        return task

    yield _make

    for task_id in created:
        try:
            api.delete(task_id)
        except requests.RequestException:
            pass


@pytest.fixture
def fast_occupied(cleanup_task):
    """Активная fast-задача (fast line занята); удаляется в teardown."""
    return cleanup_task(f"{TITLE_PREFIX}fast-первая", is_fast=True)


# ==========================================================================
# DB-хелперы: прямая правка SQLite для кейсов «смещение done_at»
# (TC-board-005, TC-arch-002/003/007, TC-tasks-016) и «просроченная сессия»
# (TC-auth-002). Путь БД — из env EKOTOV_WIKI_DB_PATH (кейс: «из конфига
# развертывания»); без переменной такие тесты пропускаются (skip), т.к.
# прямая правка БД вне процесса приложения невозможна.
# ==========================================================================

DB_PATH_ENV = "EKOTOV_WIKI_DB_PATH"


def _db_path() -> str | None:
    return os.environ.get(DB_PATH_ENV)


def db_update(db_path: str, sql: str, params: tuple = ()) -> None:
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def db_select_one(db_path: str, sql: str, params: tuple = ()):
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


@pytest.fixture
def shift_done_at_yesterday(api):
    """Смещает done_at задачи на вчерашний МСК-день 15:00+03:00 (SQL UPDATE).

    Требует EKOTOV_WIKI_DB_PATH; без него — pytest.skip (кейс требует прямого
    доступа к БД; помечено в README как ограничение окружения).
    """
    db_path = _db_path()
    if not db_path:
        pytest.skip(f"нужен env {DB_PATH_ENV} (путь SQLite-БД приложения)")
    from datetime import datetime, timedelta, timezone

    MSK = timezone(timedelta(hours=3))
    yesterday = (datetime.now(MSK) - timedelta(days=1)).date().isoformat()

    def _shift(task_id: int, time_hhmm: str = "15:00") -> str:
        done_at = f"{yesterday}T{time_hhmm}:00+03:00"
        db_update(
            db_path,
            "UPDATE tasks SET done_at = ? WHERE id = ?",
            (done_at, task_id),
        )
        return done_at

    return _shift


@pytest.fixture
def expire_session(base_url):
    """Истекает сессию (UPDATE sessions.expires_at в прошлое).

    Требует EKOTOV_WIKI_DB_PATH; без него — pytest.skip.
    Возвращает функцию: expire_session(session) -> None.
    """
    db_path = _db_path()
    if not db_path:
        pytest.skip(f"нужен env {DB_PATH_ENV} (путь SQLite-БД приложения)")

    def _expire(session: requests.Session) -> str:
        token = session.cookies.get("session")
        assert token, "в сессии нет куки session"
        db_update(
            db_path,
            "UPDATE sessions SET expires_at = '2020-01-01T00:00:00+00:00' WHERE token = ?",
            (token,),
        )
        return token

    return _expire


@pytest.fixture
def msk_dates():
    """Текущая и вчерашняя МСК-даты (строки YYYY-MM-DD)."""
    from datetime import datetime, timedelta, timezone

    MSK = timezone(timedelta(hours=3))
    now_msk = datetime.now(MSK)
    return now_msk.date().isoformat(), (now_msk - timedelta(days=1)).date().isoformat()
