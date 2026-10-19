"""Общая обвязка сервисных тестов weather (волна 3, задачи 3.1–3.2).

По конвенции services/video/tests: TestClient над app.main; БД — временная
sqlite в фикстуре (EKOTOV_WIKI_DB_PATH на время теста — только users/sessions);
кэш — временный файл (EKOTOV_WEATHER_CACHE_PATH на время теста).

Провайдер в сети НЕ мокается — ЗАМЕНЯЕТСЯ: тесты роутера подменяют
app.provider.fetch (async-стаб со счетчиком вызовов); тесты клиента
(app/provider.py) ходят через httpx.MockTransport (транспорт — аргумент
fetch, сети нет). Общие хелперы — tests/helpers.py (пакетный импорт,
НЕ голый conftest — урок BUG-video-001).
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("EKOTOV_WEATHER_USER_AGENT", "ekotov-wiki-weather-tests/1.0")

from tests.helpers import SESSION_TOKEN  # noqa: E402

# users/sessions ядра — минимально достаточный DDL (паритет
# services/video/tests): сервис читает ТОЛЬКО sessions.
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
"""

# Валидная сессия — далеко в будущем (продление TTL остается ядру).
SESSION_EXPIRES_AT = (
    datetime.now(timezone.utc) + timedelta(days=7)
).isoformat()


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Временная sqlite с users/sessions; env сервиса на нее переключен."""
    path = str(tmp_path / "wiki.db")
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO users (id, login, password_hash, display_name)"
            " VALUES (1, 'owner', 'x', 'Owner')"
        )
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at)"
            " VALUES (?, 1, ?, ?)",
            (
                SESSION_TOKEN,
                datetime.now(timezone.utc).isoformat(),
                SESSION_EXPIRES_AT,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("EKOTOV_WIKI_DB_PATH", path)
    return path


@pytest.fixture()
def cache_file(tmp_path, monkeypatch):
    """Временный кэш-файл (пустой том weather-cache на время теста)."""
    target = tmp_path / "weather-cache" / "weather.json"
    monkeypatch.setenv("EKOTOV_WEATHER_CACHE_PATH", str(target))
    return target


@pytest.fixture()
def client(db_path, cache_file):
    """TestClient над app.main с изолированными env (БД + кэш)."""
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
