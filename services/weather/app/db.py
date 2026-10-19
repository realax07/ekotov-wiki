"""Локальный db-слой weather-сервиса (change weather-service, design §5).

Паритет services/video/app/db.py, но профиль ТОЛЬКО НА ЧТЕНИЕ: сервис
работает БЕЗ своей БД (граница PLAN — миграций нет, своих таблиц нет);
единственное чтение — валидация сессии (SELECT sessions, сессионный
middleware). Запись в БД ЗАПРЕЩЕНА кодом сервиса.

- путь БД — env EKOTOV_WIKI_DB_PATH, дефолт /data/wiki.db (тот же том
  wiki-data; в compose маунт ro — паритет search);
- PRAGMA journal_mode НЕ трогаем (режим журнала принадлежит писателю-ядру);
- PRAGMA busy_timeout=5000 (сосуществование с писателем-ядром).
"""

import os
import sqlite3

# Тот же путь БД, что у ядра в контейнере (deploy/compose.yaml: DB_PATH=/data/wiki.db).
DEFAULT_DB_PATH = "/data/wiki.db"

BUSY_TIMEOUT_MS = 5000


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Соединение с общей БД (только SELECT sessions — код сервиса).

    Путь — аргумент, иначе env EKOTOV_WIKI_DB_PATH, иначе дефолт
    /data/wiki.db. Сервис НЕ имеет ни своих таблиц, ни права писать в
    sessions (design §5: «только чтение своей сессии, без права писать
    в sessions») — удаление истекших записей и продление TTL остается ядру.
    """
    path = db_path or os.environ.get("EKOTOV_WIKI_DB_PATH") or DEFAULT_DB_PATH
    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn
