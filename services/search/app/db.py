"""Локальный db-слой search-сервиса (задача 1.1, add-microservices-full).

Копия get_connection из backend/app/db.py (design пакета §2: общий модуль
НЕ шарится между образами — дублирование осознанное, «механический перенос»).
Трассировка на источник: backend/app/db.py@ddd9fb616feded9dfbfadabb393eb04ae8ce5393
(HEAD ветки add-microservices-full на момент задачи 1.1).

Отличия от ядра (осознанные, задача 1.1):
- путь БД берется из env EKOTOV_WIKI_DB_PATH (дефолт /data/wiki.db — тот же
  путь, что DB_PATH в deploy/compose.yaml ядра; сервис — read-only потребитель
  того же тома, маунт wiki-data:/data:ro);
- монолитный backend/app/config.py не переносится: он требует SECRET_KEY и
  AVATARS_DIR, которые сервису не нужны; сервис читает только путь.
Схему сервис НЕ мигрирует и не пишет в БД (design §2: инварианты монолита
не нарушаются; WAL/journal — свойства файла БД, не запись в нее).
"""

import os
import sqlite3

# Тот же путь БД, что у ядра в контейнере (deploy/compose.yaml: DB_PATH=/data/wiki.db).
DEFAULT_DB_PATH = "/data/wiki.db"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Соединение с БД в WAL-режиме (NFR-5/§5); FK-контроль включен.

    Тот же паттерн, что backend/app/db.py@HEAD: PRAGMA journal_mode=WAL +
    PRAGMA foreign_keys=ON при каждом соединении. Путь — аргумент, иначе
    env EKOTOV_WIKI_DB_PATH, иначе дефолт /data/wiki.db (как в ядре).
    """
    path = db_path or os.environ.get("EKOTOV_WIKI_DB_PATH") or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
