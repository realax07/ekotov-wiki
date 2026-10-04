"""Юнит-тесты search-сервиса (задача 1.1, add-microservices-full).

Без живого стенда: TestClient (fastapi/starlette) над app.main — сервис
проверяется в том же in-process режиме, что и заморозка контракта.
БД — временная sqlite в фикстуре (EKOTOV_WIKI_DB_PATH на время теста);
для запросов с валидной сессией в ту же БД пишется строка sessions.

Трассировка: TC-openapi-203…TC-openapi-210 (продолжение нумерации
TC-openapi-201/202 из tests/api/test_openapi_search_service.py).
Контракт: contracts/openapi-search.json (заморожен, задача 0.1).
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware import SESSION_COOKIE_NAME

AUTH = {"error": "unauthorized"}


# --------------------------------------------------------------------------
# Фикстуры: временная БД с фиксированными данными + клиент с/без сессии
# --------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  login TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name TEXT,
  role TEXT,
  bio TEXT,
  avatar_path TEXT,
  avatar_updated_at TEXT
);
CREATE TABLE sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  priority TEXT CHECK(priority IN ('low','medium','high') OR priority IS NULL),
  category TEXT,
  due_date TEXT,
  is_fast INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'todo'
    CHECK(status IN ('todo','in_progress','done')),
  done_at TEXT,
  archived_at TEXT,
  creator_id INTEGER REFERENCES users(id),
  assigned_to_id INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE task_tags (
  task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tags(id),
  PRIMARY KEY (task_id, tag_id)
);
"""


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Временная sqlite с фиксированным содержимым; env сервиса на нее переключен."""
    path = str(tmp_path / "wiki.db")
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO users (id, login, password_hash) VALUES (1, 'owner', 'x')"
        )
        conn.execute(
            "INSERT INTO users (id, login, password_hash) VALUES (2, 'wife', 'x')"
        )
        # Задачи: 1 активная high/home (owner→wife, тег home), 2 архивная low/wife,
        # 3 без исполнителя, срок 2026-10-10.
        conn.executemany(
            "INSERT INTO tasks (id, title, priority, category, due_date, is_fast,"
            " status, done_at, archived_at, creator_id, assigned_to_id,"
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (1, "QAT-svc-1", "high", "home", "2026-10-10", 0,
                 "todo", None, None, 1, 2, "2026-10-01T00:00:00+03:00",
                 "2026-10-01T00:00:00+03:00"),
                (2, "QAT-svc-2", "low", "dacha", None, 0,
                 "done", "2026-09-20T00:00:00+03:00",
                 "2026-09-21T00:00:00+03:00", 2, 2, "2026-09-19T00:00:00+03:00",
                 "2026-09-21T00:00:00+03:00"),
                (3, "QAT-svc-3", None, None, "2026-10-10", 0,
                 "todo", None, None, 1, None, "2026-10-02T00:00:00+03:00",
                 "2026-10-02T00:00:00+03:00"),
            ],
        )
        conn.execute("INSERT INTO tags (id, name) VALUES (1, 'home')")
        conn.execute("INSERT INTO tags (id, name) VALUES (2, 'car')")
        conn.executemany(
            "INSERT INTO task_tags (task_id, tag_id) VALUES (?, ?)",
            [(1, 1), (2, 2)],  # тег car осиротел после… нет: задача 2 существует
        )
        # Валидная сессия для сервис-клиента (скользящий TTL middleware).
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at)"
            " VALUES ('test-token-1', 1, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("EKOTOV_WIKI_DB_PATH", path)
    return path


@pytest.fixture()
def anon_client(db_path):
    """Клиент без сессии (401 на защищенных путях)."""
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def client(db_path):
    """Клиент с валидной сессией (кука test-token-1 из фикстуры БД)."""
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, "test-token-1")
        yield client


# --------------------------------------------------------------------------
# TC-openapi-203+: health / авторизация / search / suggestions
# --------------------------------------------------------------------------

def test_health_no_session(anon_client):
    """TC-openapi-203: GET /api/health без сессии → 200 {"status":"ok"} (exempt)."""
    resp = anon_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_search_requires_session(anon_client):
    """TC-openapi-204: GET /api/search без сессии → 401 {"error":"unauthorized"}."""
    resp = anon_client.get("/api/search")
    assert resp.status_code == 401
    assert resp.json() == AUTH


def test_openapi_schema_requires_session(anon_client, client):
    """TC-openapi-205: /openapi.json без сессии → 401; с сессией → 200."""
    assert anon_client.get("/openapi.json").status_code == 401
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert set(schema["paths"].keys()) == {
        "/api/search",
        "/api/search/advanced",
        "/api/suggestions",
        "/api/suggestions/users",
        "/api/health",
    }


def test_search_all_and_filters(client):
    """TC-openapi-206: GET /api/search — пустой фильтр = все (вкл. архив);
    priority/category/tag/archived фильтруют по фиксированной БД."""
    # Пустой набор = все задачи, включая архивные.
    body = client.get("/api/search").json()
    assert [t["id"] for t in body["results"]] == [1, 2, 3]

    # priority=high → только задача 1; с логинами creator/assigned.
    body = client.get("/api/search", params={"priority": "high"}).json()
    assert [t["id"] for t in body["results"]] == [1]
    task = body["results"][0]
    assert task["creator"] == "owner"
    assert task["assigned"] == "wife"
    assert task["tags"] == ["home"]
    assert set(task.keys()) == {
        "id", "title", "description", "priority", "category", "due_date",
        "tags", "is_fast", "status", "done_at", "archived_at",
        "creator", "assigned",
    }

    # archived=false → без архивных (задача 2 исключена).
    body = client.get("/api/search", params={"archived": "false"}).json()
    assert [t["id"] for t in body["results"]] == [1, 3]

    # Повторяемый tag: ИЛИ внутри признака (IN) — tag=home&tag=car → 1 и 2.
    body = client.get("/api/search", params=[("tag", "home"), ("tag", "car")]).json()
    assert sorted(t["id"] for t in body["results"]) == [1, 2]


def test_search_invalid_params_422(client):
    """TC-openapi-207: GET /api/search — невалидный priority/archived → 422
    в форме sdd §3 ({"error": "validation error", "details": ...})."""
    for params in ({"priority": "urgent"}, {"archived": "maybe"},
                   {"due_before": "10-10-2026"}):
        resp = client.get("/api/search", params=params)
        assert resp.status_code == 422, params
        assert resp.json()["error"] == "validation error"


def test_search_unknown_user_422(client):
    """TC-openapi-208: GET /api/search — несуществующий assigned/creator → 422."""
    resp = client.get("/api/search", params={"assigned": "ghost"})
    assert resp.status_code == 422
    assert resp.json() == {
        "error": "validation error", "details": {"assigned": "unknown user"}
    }
    # assigned=none — легально: только задача 3 без исполнителя.
    resp = client.get("/api/search", params={"assigned": "none"})
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()["results"]] == [3]


def test_search_advanced(client):
    """TC-openapi-209: POST /api/search/advanced — 200 + normalized_query;
    синтаксическая ошибка → 400 без выполнения запроса."""
    resp = client.post(
        "/api/search/advanced", json={"query": 'priority = "high"'}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [t["id"] for t in body["results"]] == [1]
    assert body["normalized_query"] == 'priority = "high"'

    # assigned IS NULL (ОВ-24) → задача 3.
    resp = client.post("/api/search/advanced", json={"query": "assigned IS NULL"})
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()["results"]] == [3]

    # Пустой текст = все задачи.
    resp = client.post("/api/search/advanced", json={"query": ""})
    assert [t["id"] for t in resp.json()["results"]] == [1, 2, 3]

    # OR не поддерживается → 400 с позицией; тело — {"error": "filter syntax: ..."}.
    resp = client.post(
        "/api/search/advanced", json={"query": 'priority = "high" OR x'}
    )
    assert resp.status_code == 400
    assert resp.json()["error"].startswith("filter syntax: position ")


def test_suggestions_and_users(client):
    """TC-openapi-210: GET /api/suggestions (UNION теги ∪ категории, sorted,
    kind=tags/categories) и /api/suggestions/users (логины из данных)."""
    # БЕЗ kind — UNION: car, dacha, home (тег home ∩ категория home — один раз).
    resp = client.get("/api/suggestions")
    assert resp.status_code == 200
    assert resp.json() == {"suggestions": ["car", "dacha", "home"]}

    resp = client.get("/api/suggestions", params={"kind": "tags"})
    assert resp.json() == {"suggestions": ["car", "home"]}
    resp = client.get("/api/suggestions", params={"kind": "categories"})
    assert resp.json() == {"suggestions": ["dacha", "home"]}
    # Иной kind → 422.
    assert client.get("/api/suggestions", params={"kind": "bogus"}).status_code == 422

    # Логины из данных: owner (creator 1,3) ∪ wife (assigned 1,2 / creator 2).
    resp = client.get("/api/suggestions/users")
    assert resp.status_code == 200
    assert resp.json() == {"users": ["owner", "wife"]}


def test_suggestions_requires_session(anon_client):
    """TC-openapi-211: /api/suggestions* без сессии → 401 (middleware)."""
    assert anon_client.get("/api/suggestions").status_code == 401
    assert anon_client.get("/api/suggestions/users").status_code == 401
