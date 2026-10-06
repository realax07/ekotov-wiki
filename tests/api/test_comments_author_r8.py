"""Юнит-тесты r8 2.3 (FR-91): author_name в ответе GET списка комментариев.

По конвенции сервисных юнитов (services/search/tests, services/images/tests):
TestClient над app.main, БД — временная sqlite в фикстуре
(EKOTOV_WIKI_DB_PATH на время теста); для запросов с валидной сессией в ту
же БД пишется строка sessions.

Запуск (из корня репозитория):
  python3 -m pytest tests/api/test_comments_author_r8.py -v
(без стенда: TestClient инпроцесс; конфиг-заглушка DB_PATH/SECRET_KEY —
conftest-фикстура ставит env до импорта app.main — см. env_app ниже).

Трассировка: сценарий дельты specs/tasks «Шапка комментария — автор и
человечески читаемая дата» + «Контракт записи комментария не изменился»
(P12 п.3, FR-91, design §5). Нумерация TC-r8c-1… (1 сценарий = 1 тест).

Проверяется ТОЛЬКО контракт API (клиентский рендер шапки — web-сьют):
- author_name присутствует в ответе GET (display_name и fallback login);
- обратная совместимость: прежние поля на месте, POST-контракт не изменился.
"""

import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

# Плагин pytest-base-url (транзитивная зависимость pytest-playwright) несет
# autouse session-фикстуру _verify_url → тянет conftest-овский base_url
# (поллинг живого стенда) — TestClient-юнитам стенд не нужен. Перекрываем
# no-op'ом в этом модуле (модульная фикстура бьет conftest/plugin); conftest
# tests/api не трогаем — он нужен живым api-тестам.
@pytest.fixture(scope="session", autouse=True)
def _verify_url():
    yield


# Конфиг приложения читает env на импорте (app.config.settings) — env
# обязателен ДО import app.main (низ модуля). tmp-путь уникален на прогон.
os.environ.setdefault("DB_PATH", f"/tmp/r8c-{uuid.uuid4().hex}.db")
os.environ.setdefault("SECRET_KEY", "r8-unit-test-key")

# backend/app в sys.path (из корня репозитория — тесты api живут там).
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.middleware import SESSION_COOKIE_NAME  # noqa: E402

# Схема — только нужные яру comments таблицы (users/sessions/tasks/comments),
# дословно app/db.py SCHEMA_SQL (остальные объекты схеме ответов не нужны).
SCHEMA_SQL = """
CREATE TABLE users (
  id            INTEGER PRIMARY KEY,
  login         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name  TEXT,
  role          TEXT,
  bio           TEXT,
  avatar_path   TEXT,
  avatar_updated_at TEXT
);
CREATE TABLE sessions (
  token       TEXT PRIMARY KEY,
  user_id     INTEGER NOT NULL REFERENCES users(id),
  created_at  TEXT NOT NULL,
  expires_at  TEXT NOT NULL
);
CREATE TABLE tasks (
  id          INTEGER PRIMARY KEY,
  title       TEXT NOT NULL,
  description TEXT,
  priority    TEXT CHECK(priority IN ('low','medium','high') OR priority IS NULL),
  category    TEXT,
  due_date    TEXT,
  is_fast     INTEGER NOT NULL DEFAULT 0,
  status      TEXT NOT NULL DEFAULT 'todo'
    CHECK(status IN ('todo','in_progress','done')),
  done_at     TEXT,
  archived_at TEXT,
  creator_id  INTEGER REFERENCES users(id),
  assigned_to_id INTEGER REFERENCES users(id),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
CREATE TABLE comments (
  id         INTEGER PRIMARY KEY,
  task_id    INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  author_id  INTEGER NOT NULL REFERENCES users(id),
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Временная sqlite: 2 пользователя (с display_name и без) + задача.

    display_name владельца задан («Анна Смирнова»), у wife — NULL
    (fallback login — отдельный тест-кейс). Сессия owner — валидная.
    """
    path = str(tmp_path / "wiki.db")
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO users (id, login, password_hash, display_name)"
            " VALUES (1, 'owner', 'x', 'Анна Смирнова')"
        )
        conn.execute(
            "INSERT INTO users (id, login, password_hash, display_name)"
            " VALUES (2, 'wife', 'x', NULL)"
        )
        conn.execute(
            "INSERT INTO tasks (id, title, is_fast, status, created_at,"
            " updated_at) VALUES (1, 'QAT-r8c', 0, 'todo', ?, ?)",
            ("2026-10-05T10:00:00+00:00", "2026-10-05T10:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at)"
            " VALUES ('r8-token-1', 1, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    # Ядро (backend/app/config.py) читает DB_PATH на импорте в объект
    # settings; на время теста переключаем сам объект (env переменной
    # settings уже не читает) — паттерн «EKOTOV_WIKI_DB_PATH на время
    # теста» сервисных юнитов здесь неприменим: у ядра путь из settings.
    monkeypatch.setattr("app.config.settings.db_path", path)
    monkeypatch.setenv("EKOTOV_WIKI_DB_PATH", path)
    return path


@pytest.fixture()
def anon_client(db_path):
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def client(db_path):
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, "r8-token-1")
        yield client


def _add_comment(client, task_id, body):
    return client.post(f"/api/tasks/{task_id}/comments", json={"body": body})


# --------------------------------------------------------------------------
# FR-91: author_name в ответе GET списка (display_name и fallback login)
# --------------------------------------------------------------------------


def test_comments_list_contains_author_name_display_name(client):
    """TC-r8c-001: author_name = display_name автора, когда он задан."""
    resp_add = _add_comment(client, 1, "Первый комментарий")
    assert resp_add.status_code == 201

    resp = client.get("/api/tasks/1/comments")
    assert resp.status_code == 200
    comments = resp.json()["comments"]
    assert len(comments) == 1
    assert comments[0]["author_id"] == 1
    assert comments[0]["author_name"] == "Анна Смирнова"


def test_comments_list_author_name_falls_back_to_login(client):
    """TC-r8c-002: display_name NULL → author_name = login (fallback)."""
    # Комментарий от wife вставляется напрямую в БД (сессия в фикстуре
    # одна — owner; контракт POST «автор из сессии» не задействуем).
    import sqlite3

    db = os.environ["EKOTOV_WIKI_DB_PATH"]
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO comments (task_id, author_id, body, created_at)"
            " VALUES (1, 2, 'Ответ wife', '2026-10-05T11:00:00+00:00')"
        )
        conn.commit()
    finally:
        conn.close()

    resp = client.get("/api/tasks/1/comments")
    assert resp.status_code == 200
    comments = resp.json()["comments"]
    assert len(comments) == 1
    assert comments[0]["author_id"] == 2
    assert comments[0]["author_name"] == "wife"


# --------------------------------------------------------------------------
# Обратная совместимость ответа
# --------------------------------------------------------------------------


def test_comments_list_backward_compatible_shape(client):
    """TC-r8c-003: прежние поля на месте и с прежними значениями; список
    в прежней обертке {"comments": [...]}; порядок created_at ASC."""
    _add_comment(client, 1, "Комментарий А")
    import sqlite3

    db = os.environ["EKOTOV_WIKI_DB_PATH"]
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO comments (task_id, author_id, body, created_at)"
            " VALUES (1, 1, 'Комментарий Б', '2026-10-04T09:00:00+00:00')"
        )
        conn.commit()
    finally:
        conn.close()

    resp = client.get("/api/tasks/1/comments")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"comments"}
    comments = body["comments"]
    # Порядок: created_at ASC (Б раньше А).
    assert [c["body"] for c in comments] == ["Комментарий Б", "Комментарий А"]
    for comment in comments:
        # Прежний контракт Comment (sdd §4) + новое поле.
        assert set(comment.keys()) == {
            "id",
            "task_id",
            "author_id",
            "body",
            "created_at",
            "author_name",
        }
        assert comment["task_id"] == 1
        assert comment["created_at"]


def test_comments_post_contract_unchanged(client):
    """TC-r8c-004: POST-контракт не изменился — 201, ответ ровно Comment
    (sdd §4) БЕЗ author_name, author_id = пользователь сессии."""
    resp = _add_comment(client, 1, "Контракт записи")
    assert resp.status_code == 201
    comment = resp.json()
    assert set(comment.keys()) == {
        "id",
        "task_id",
        "author_id",
        "body",
        "created_at",
    }
    assert comment["author_id"] == 1
    assert comment["body"] == "Контракт записи"

    # Пустой текст по-прежнему 422 (валидация не задета).
    resp_empty = _add_comment(client, 1, "   ")
    assert resp_empty.status_code == 422


def test_comments_list_404_and_empty_preserved(client, anon_client):
    """TC-r8c-005: 404 для несуществующей задачи; пустой список —
    {"comments": []}; без сессии — 401 (middleware не задет правками)."""
    assert client.get("/api/tasks/999/comments").status_code == 404
    assert client.get("/api/tasks/1/comments").json() == {"comments": []}
    assert anon_client.get("/api/tasks/1/comments").status_code == 401
