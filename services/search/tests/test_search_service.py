"""Юнит-тесты search-сервиса (задача 1.1, add-microservices-full).

Без живого стенда: TestClient (fastapi/starlette) над app.main — сервис
проверяется в том же in-process режиме, что и заморозка контракта.
БД — временная sqlite в фикстуре (EKOTOV_WIKI_DB_PATH на время теста);
для запросов с валидной сессией в ту же БД пишется строка sessions.

Трассировка: TC-openapi-203…TC-openapi-210 (продолжение нумерации
TC-openapi-201/202 из tests/api/test_openapi_search_service.py).
Контракт: contracts/openapi-search.json (заморожен, задача 0.1).
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    """Временная sqlite с фиксированным содержимым; env сервиса на нее переключен.

    БД создается в WAL-режиме (PRAGMA journal_mode=WAL) — как у писателя
    (app) на стенде: заголовок БД несет write/read_version=2 (WAL) и ПОСЛЕ
    закрытия писателя. Это необходимо для дискриминационной силы TC-212:
    probe mode=ro на такой БД без -wal/-shm на ro-каталоге падает
    («attempt to write a readonly database») → срабатывает fallback
    immutable=1. БД в delete-journal-режиме (заголовок 1/1) probe mode=ro
    проходит успешно и fallback мертв — тест перестает проверять ветку.
    """
    path = str(tmp_path / "wiki.db")
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
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
    # Писатель закрыт: sqlite чекпоинтил wal и удаляет -wal/-shm сам; стираем
    # остатки явно (гарантия состояния «wal физически отсутствует» — инвариант
    # TC-212/TC-214, fallback immutable=1 легален только при живом писателе
    # с -wal/-shm, см. TC-213).
    for suffix in ("-wal", "-shm"):
        try:
            os.remove(path + suffix)
        except FileNotFoundError:
            pass
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


# --------------------------------------------------------------------------
# Ревью задачи 1.2 (TC-openapi-212+): read-only открытие БД
# --------------------------------------------------------------------------

def test_readonly_dir_without_wal(db_path, client):
    """TC-openapi-212: ro-каталог БД при отсутствии -wal/-shm (app в простое).

    Регресс ревью задачи 1.2: get_connection с PRAGMA journal_mode=WAL на
    ro-маунте падал «unable to open database file» → 500 на /api/search.
    Гибрид mode=ro → immutable=1: сервис отвечает 200 (снапшот main-db).
    """
    ro_dir = os.path.dirname(db_path)
    mode = os.stat(ro_dir).st_mode
    os.chmod(ro_dir, 0o500)  # каталог только для чтения (эмуляция ro-маунта)
    try:
        resp = client.get("/api/search")
        assert resp.status_code == 200
        assert [t["id"] for t in resp.json()["results"]] == [1, 2, 3]
    finally:
        os.chmod(ro_dir, mode)


def test_readonly_dir_with_live_writer(db_path, client):
    """TC-openapi-213: ro-маунт при живом писателе (app) — свежие данные видны.

    mode=ro читает wal: задача, вставленная ПОСЛЕ seed другим соединением,
    видна сервису без перезапуска (fallback immutable здесь НЕ срабатывает —
    он для случая «wal отсутствует» и свежесть НЕ гарантирует).
    """
    # Писатель остается ОТКРЫТЫМ на время запроса: -wal/-shm существуют, и
    # probe mode=ro обязан пройти (ветка fallback не задействована —
    # иначе незачекпоинченная вставка не была бы видна и тест краснел).
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO tasks (id, title, priority, category, creator_id,"
            " assigned_to_id, created_at, updated_at) VALUES"
            " (99, 'QAT-svc-fresh', 'low', 'x', 1, NULL, ?, ?)",
            ("2026-10-03T00:00:00+03:00", "2026-10-03T00:00:00+03:00"),
        )
        conn.commit()

        resp = client.get("/api/search")
        assert resp.status_code == 200
        assert 99 in [t["id"] for t in resp.json()["results"]]
    finally:
        conn.close()


def test_expired_session_select_only(db_path, anon_client):
    """TC-openapi-214: истекшая сессия → 401 БЕЗ попытки записи (SELECT-only).

    Регресс ревью задачи 1.2: middleware копировал ядро (DELETE истекшей
    записи + sliding-TTL UPDATE) — на ro-маунте это 500 вместо 401.

    Дискриминационная сила: каталог БД переводится в ro (как TC-212), БД —
    с WAL-заголовком. Дефектный middleware (DELETE+commit через ro-conn)
    падает «attempt to write a readonly database» → 500 и тест краснеет;
    SELECT-only вариант проходит. На записываемой БД оба варианта дают 401 —
    поэтому ro-условие обязательно (ревью 1.1, находка 1.1-b).
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE sessions SET expires_at = ? WHERE token = 'test-token-1'",
            ((datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),),
        )
        conn.commit()
    finally:
        conn.close()

    ro_dir = os.path.dirname(db_path)
    mode = os.stat(ro_dir).st_mode
    os.chmod(ro_dir, 0o500)  # каталог только для чтения (эмуляция ro-маунта)
    try:
        resp = anon_client.get("/api/search")
        assert resp.status_code == 401
        assert resp.json() == {"error": "unauthorized"}
    finally:
        os.chmod(ro_dir, mode)


# --------------------------------------------------------------------------
# ОВ-7 (design add-p20-contracts §2; возврат Д-1 code-review-001):
# Error-схема и $ref на 401/400/422 в замороженном контракте
# --------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = REPO_ROOT / "contracts" / "openapi-search.json"
_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _error_schema_of(body: dict) -> dict:
    """Минимальная валидация тела по контрактной Error-схеме (сценарий ОВ-7):
    required «error» присутствует и является строкой; details не запрещены
    (без additionalProperties:false — ОВ-1б)."""
    assert isinstance(body, dict)
    assert isinstance(body.get("error"), str)
    return body


def test_contract_error_schema_and_refs():
    """TC-openapi-215: ОВ-7 — components.schemas.Error в контракте; все
    401/400/422-ответы ссылаются на нее $ref-ом; FastAPI-заготовка
    HTTPValidationError в файле отсутствует (фактическая форма 422 —
    {"error", "details"} validation-handler, не {\"detail\": [...]})."""
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    error = contract["components"]["schemas"]["Error"]
    assert error["type"] == "object"
    assert error["required"] == ["error"]
    assert "additionalProperties" not in error  # ОВ-1б

    error_refs, validation_refs = 0, 0
    for path, item in contract["paths"].items():
        for method, op in item.items():
            if method not in _HTTP_METHODS:
                continue
            for status, response in op.get("responses", {}).items():
                schema = response["content"]["application/json"]["schema"]
                if status in {"400", "401", "422"}:
                    assert schema == {"$ref": "#/components/schemas/Error"}, (
                        f"{method.upper()} {path} {status}: {schema}"
                    )
                    error_refs += 1
                if "HTTPValidationError" in json.dumps(schema):
                    validation_refs += 1
    # 401 на всех защищенных операциях (4) + 422 search/suggestions/advanced
    # + 400 advanced = 8 аннотированных error-ответов.
    assert error_refs == 8
    assert validation_refs == 0
    assert "HTTPValidationError" not in contract["components"]["schemas"]


def test_error_responses_match_contract_schema(client, anon_client):
    """TC-openapi-216: ОВ-7 сценарий — фактические тела 401 (middleware),
    422 (validation-handler и семантический unknown user) и 400 (advanced)
    валидируются по контрактной Error-схеме (required «error»)."""
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["components"]["schemas"]["Error"]["required"] == ["error"]

    _error_schema_of(anon_client.get("/api/search").json())          # 401
    _error_schema_of(client.get("/api/search", params={"priority": "urgent"}).json())  # 422
    _error_schema_of(client.get("/api/search", params={"assigned": "ghost"}).json())   # 422 semantic
    _error_schema_of(client.get("/api/suggestions", params={"kind": "bogus"}).json())  # 422
    _error_schema_of(
        client.post("/api/search/advanced", json={"query": 'x = "a" OR y'}).json()
    )  # 400 filter syntax
    _error_schema_of(
        client.post("/api/search/advanced", json={"query": 123}).json()
    )  # 422 query not a string


# --------------------------------------------------------------------------
# Волна 5 (add-p20-contracts, FR-138/ОВ-1б, NFR-46): схемная валидация
# ответов по замороженному контракту — helper tests/contract_helpers.py
# (копия одного файла, design §3). Существующие ассерты не правятся
# (NFR-45) — только ДОБАВЛЕНИЕ проверок.
# --------------------------------------------------------------------------

from tests.contract_helpers import validate_response  # noqa: E402


def test_contract_helper_unit_positive_and_negative():
    """TC-openapi-217 (волна 5, задача 5.2): юнит helper'а — позитивный
    payload валиден (в т.ч. с details — ОВ-1б, без additionalProperties:false);
    негативный (error не строка) падает с маршрутом и несовпавшим полем;
    неизвестные маршрут/статус — AssertionError (ловушка дрейфа)."""
    # Позитив: Error-схема — required «error» строка, details не запрещены.
    validate_response("/api/search", "GET", 401,
                      {"error": "unauthorized", "details": {"x": 1}})
    # Позитив: 200-схема маршрута — `{}` (любой payload валиден).
    validate_response("/api/suggestions", "GET", 200, {"suggestions": []})
    # Негатив: поле «error» не строка — сообщение содержит маршрут и поле.
    with pytest.raises(AssertionError) as ei:
        validate_response("/api/search", "GET", 401, {"error": 123})
    msg = str(ei.value)
    assert "GET /api/search" in msg and "[401]" in msg and "$.error" in msg
    # Ловушки дрейфа: неизвестные маршрут и статус.
    with pytest.raises(AssertionError, match="маршрут отсутствует"):
        validate_response("/api/ghost", "GET", 200, {})
    with pytest.raises(AssertionError, match="статус 503 не описан"):
        validate_response("/api/search", "GET", 503, {})


def test_search_happy_paths_match_contract(client):
    """TC-openapi-218 (волна 5, задача 5.3): happy-path 200 КАЖДОГО маршрута
    search-сервиса валидируется по схеме из contracts/openapi-search.json."""
    validate_response("/api/search", "GET", 200,
                      client.get("/api/search").json())
    validate_response("/api/search", "GET", 200,
                      client.get("/api/search", params={"priority": "high"}).json())
    validate_response("/api/search/advanced", "POST", 200,
                      client.post("/api/search/advanced",
                                  json={"query": 'priority = "high"'}).json())
    validate_response("/api/suggestions", "GET", 200,
                      client.get("/api/suggestions").json())
    validate_response("/api/suggestions/users", "GET", 200,
                      client.get("/api/suggestions/users").json())
    validate_response("/api/health", "GET", 200,
                      client.get("/api/health").json())


def test_search_error_payloads_match_contract(client, anon_client):
    """TC-openapi-219 (волна 5, задача 5.3): типовые ошибки — 401 без сессии
    и ОБЕ формы 422 (validation-handler и семантическая unknown user) плюс
    400 filter syntax — валидируются по Error-схеме контракта."""
    validate_response("/api/search", "GET", 401,
                      anon_client.get("/api/search").json())
    # Форма 1: validation-handler — {"error": "validation error", "details": …}.
    resp = client.get("/api/search", params={"priority": "urgent"})
    assert resp.status_code == 422
    validate_response("/api/search", "GET", 422, resp.json())
    # Форма 2: семантическая — {"error": "validation error",
    # "details": {"assigned": "unknown user"}}.
    resp = client.get("/api/search", params={"assigned": "ghost"})
    assert resp.status_code == 422
    validate_response("/api/search", "GET", 422, resp.json())
    # 400 advanced (filter syntax) — тоже Error-схема.
    resp = client.post("/api/search/advanced", json={"query": 'x = "a" OR y'})
    assert resp.status_code == 400
    validate_response("/api/search/advanced", "POST", 400, resp.json())
