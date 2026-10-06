"""Локальный db-слой images-сервиса (задача 1.2, add-gallery-service).

По образцу services/search/app/db.py, с осознанным отличием: images —
ПЕРВЫЙ сервис-писатель (design §2, «RW-профиль images»), поэтому БД
открывается на чтение-запись (не mode=ro, как у search):

- путь БД — env EKOTOV_WIKI_DB_PATH, дефолт /data/wiki.db (тот же том
  wiki-data, маунт rw — спека services: «RW-маунт общей БД»);
- PRAGMA journal_mode НЕ трогаем (design §2: «WAL не переключается» —
  режим журнала принадлежит писателю-ядру; переключение с DELETE на WAL
  это запись в заголовок БД, чужая для сервиса);
- PRAGMA busy_timeout=5000 (design §2: короткие транзакции,
  busy_timeout — сосуществование с писателем-ядром);
- PRAGMA foreign_keys=ON (паритет ядра и search);
- сессия валидируется SELECT-only — check/UPDATE sessions (скользящий
  TTL) остается ядру (паттерн services/search/app/middleware.py).
"""

import os
import sqlite3

# Тот же путь БД, что у ядра в контейнере (deploy/compose.yaml: DB_PATH=/data/wiki.db).
DEFAULT_DB_PATH = "/data/wiki.db"

BUSY_TIMEOUT_MS = 5000


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """RW-соединение с общей БД; FK-контроль и busy_timeout включены.

    Путь — аргумент, иначе env EKOTOV_WIKI_DB_PATH, иначе дефолт
    /data/wiki.db (как в ядре и search). Сервис пишет ТОЛЬКО таблицы
    gallery (спека services: «Границы записи»); users — только чтение.
    """
    path = db_path or os.environ.get("EKOTOV_WIKI_DB_PATH") or DEFAULT_DB_PATH
    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn
