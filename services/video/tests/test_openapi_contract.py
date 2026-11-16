"""Контрактный тест путей video-сервиса (add-p20-contracts, волна 2, 2.3).

Замороженная спека contracts/openapi-video.json = живому /openapi.json
сервиса под сессией, 1:1: множества path-items И множества методов на
каждом пути (14 операций). Дрейф поверхности (новый/удаленный маршрут
или метод) краснит тест еще до включения гейта IR-08 (волна 7).

Схемная валидация payloads — волна 5 (design §3); здесь только
поверхность + присутствие error-схем ОВ-7 (Error/$ref).

Трассировка: TC-vid-110/111 (продолжение нумерации services/video/tests).
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware import SESSION_COOKIE_NAME

# Замороженный контракт — из корня репозитория
# (services/video/tests/x.py → parents[3] = корень).
CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "openapi-video.json"

EXPECTED_PATHS = {
    "/api/videos",
    "/api/videos/{video_id}",
    "/api/videos/{video_id}/file",
    "/api/videos/{video_id}/preview",
    "/api/videos/{video_id}/comments",
    "/api/videos/{video_id}/comments/{comment_id}",
    "/api/videos/{video_id}/reaction",
    "/api/videos/categories",
    "/api/videos/authcheck",
    "/api/health",
}
EXPECTED_OPERATIONS = 14  # videos.py 7 + social.py 6 + /api/health


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient с валидной сессией (минимум для middleware — sessions)."""
    import sqlite3
    from datetime import datetime, timedelta, timezone

    db_path = str(tmp_path / "wiki.db")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
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
            """
        )
        conn.execute(
            "INSERT INTO users (id, login, password_hash) VALUES (1, 'owner', 'x')"
        )
        now = datetime.now(timezone.utc)
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at)"
            " VALUES (?, 1, ?, ?)",
            ("contract-token", now.isoformat(), (now + timedelta(days=1)).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("EKOTOV_WIKI_DB_PATH", db_path)
    monkeypatch.setenv("EKOTOV_WIKI_VIDEOS_DIR", str(tmp_path / "videos"))
    monkeypatch.setenv("EKOTOV_WIKI_CONVERTER", "off")
    with TestClient(app) as test_client:
        test_client.cookies.set(SESSION_COOKIE_NAME, "contract-token")
        yield test_client


def test_contract_paths_match_live(client):
    """TC-vid-110: замороженная спека = живой /openapi.json, 1:1 (path-items)."""
    frozen = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    live = client.get("/openapi.json").json()
    assert set(frozen["paths"]) == set(live["paths"])
    assert set(frozen["paths"]) == EXPECTED_PATHS


def test_contract_operations_match_live(client):
    """TC-vid-111: множества МЕТОДОВ каждого пути тоже 1:1 (14 операций)."""
    frozen = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    live = client.get("/openapi.json").json()
    http_methods = {"get", "post", "put", "patch", "delete"}
    frozen_ops = {
        (path, method)
        for path, item in frozen["paths"].items()
        for method in item
        if method in http_methods
    }
    live_ops = {
        (path, method)
        for path, item in live["paths"].items()
        for method in item
        if method in http_methods
    }
    assert frozen_ops == live_ops
    assert len(frozen_ops) == EXPECTED_OPERATIONS


def test_contract_error_schemas_present():
    """TC-vid-112: ОВ-7 — Error-схема в спеке, $ref на 401-ответах,
    internal-пометка authcheck (задача 2.2)."""
    frozen = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    error = frozen["components"]["schemas"]["Error"]
    assert error["required"] == ["error"]
    ref_401 = frozen["paths"]["/api/videos"]["post"]["responses"]["401"]
    assert ref_401["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/Error"
    }
    assert "internal" in frozen["paths"]["/api/videos/authcheck"]["get"]["description"]
