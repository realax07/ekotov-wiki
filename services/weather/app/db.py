"""Локальный db-слой weather-сервиса (change weather-service, design §5).

Паритет services/video/app/db.py, но профиль ТОЛЬКО НА ЧТЕНИЕ: сервис
работает БЕЗ своей БД (граница PLAN — миграций нет, своих таблиц нет);
единственное чтение — валидация сессии (SELECT sessions, сессионный
middleware). Запись в БД ЗАПРЕЩЕНА кодом сервиса.

- путь БД — env EKOTOV_WIKI_DB_PATH, дефолт /data/wiki.db (тот же том
  wiki-data; в compose маунт ro — паритет search);
- открытие ТОЛЬКО НА ЧТЕНИЕ: mode=ro с fallback immutable=1 (паритет
  search, см. services/search/app/db.py) — на ro-маунте обычный connect
  не работает;
- PRAGMA journal_mode НЕ трогаем (режим журнала принадлежит писателю-ядру);
- PRAGMA busy_timeout=5000 (сосуществование с писателем-ядром).
"""

import os
import sqlite3
from urllib.parse import quote as _uri_quote

# Тот же путь БД, что у ядра в контейнере (deploy/compose.yaml: DB_PATH=/data/wiki.db).
DEFAULT_DB_PATH = "/data/wiki.db"

BUSY_TIMEOUT_MS = 5000


def _open_readonly(path: str) -> sqlite3.Connection:
    """Read-only соединение (паритет services/search/app/db.py).

    mode=ro требует живого -shm для чтения wal; без него (app в простое)
    sqlite не может пересоздать -shm на ro-маунте → OperationalError, и
    открываем immutable=1 (снапшот main-db, только чтение). Проба SELECT
    сразу после connect: sqlite откладывает открытие wal-index до первого
    запроса — без нее fallback не сработал бы в момент connect.
    """
    uri = f"file:{_uri_quote(path)}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return conn
    except sqlite3.Error:
        try:
            conn.close()  # type: ignore[possibly-undefined]
        except NameError:
            pass
    # immutable=1 запрещает sqlite ЛЮБОЙ доступ на запись, включая чтение
    # wal; здесь ожидаемо читается main-db (см. докстринг модуля search).
    conn = sqlite3.connect(f"file:{_uri_quote(path)}?immutable=1", uri=True)
    conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    return conn


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Соединение с общей БД (только SELECT sessions — код сервиса).

    Путь — аргумент, иначе env EKOTOV_WIKI_DB_PATH, иначе дефолт
    /data/wiki.db. Сервис НЕ имеет ни своих таблиц, ни права писать
    в sessions (design §5: «только чтение своей сессии, без права писать
    в sessions») — удаление истекших записей и продление TTL остается ядру.

    Открытие ТОЛЬКО НА ЧТЕНИЕ (mode=ro → immutable=1, паритет search):
    том wiki-data маунтится ro — обычный connect пытается открыть файл
    RW и падает «unable to open database file» (find-фикс stand'а).
    """
    path = db_path or os.environ.get("EKOTOV_WIKI_DB_PATH") or DEFAULT_DB_PATH
    conn = _open_readonly(path)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn
