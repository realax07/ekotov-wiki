"""Локальный db-слой video-сервиса (tasks 1.2, video-hosting волна 1).

По образцу services/images/app/db.py (тот же RW-профиль «своя схема»):

- путь БД — env EKOTOV_WIKI_DB_PATH, дефолт /data/wiki.db (тот же том
  wiki-data, маунт rw — compose задачи 1.2);
- PRAGMA journal_mode НЕ трогаем (design §2/§7: режим журнала принадлежит
  писателю-ядру);
- PRAGMA busy_timeout=5000 (design §2: короткие транзакции,
  busy_timeout — сосуществование с писателем-ядром);
- PRAGMA foreign_keys=ON (паритет ядра и search/images).

Владение схемой (design §7): RW только video_videos (кусок D добавит
video_comments/video_reactions); SELECT users (имя загрузившего);
запись в sessions и чужие таблицы ЗАПРЕЩЕНА — гарантируется кодом
сервиса (каждый запрос — короткая транзакция, только свои таблицы).
"""

import os
import sqlite3

# Тот же путь БД, что у ядра в контейнере (deploy/compose.yaml: DB_PATH=/data/wiki.db).
DEFAULT_DB_PATH = "/data/wiki.db"

BUSY_TIMEOUT_MS = 5000


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """RW-соединение с общей БД; FK-контроль и busy_timeout включены.

    Путь — аргумент, иначе env EKOTOV_WIKI_DB_PATH, иначе дефолт
    /data/wiki.db. Сервис пишет ТОЛЬКО таблицу video_videos (design §7);
    users/sessions — только чтение (SELECT).
    """
    path = db_path or os.environ.get("EKOTOV_WIKI_DB_PATH") or DEFAULT_DB_PATH
    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn
