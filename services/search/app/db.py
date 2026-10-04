"""Локальный db-слой search-сервиса (задача 1.1, add-microservices-full).

Копия get_connection из backend/app/db.py (design пакета §2: общий модуль
НЕ шарится между образами — дублирование осознанное, «механический перенос»).
Трассировка на источник: backend/app/db.py@ddd9fb616feded9dfbfadabb393eb04ae8ce5393
(HEAD ветки add-microservices-full на момент задачи 1.1).

Отличия от ядра (осознанные, задача 1.1; ro-фикс — ревью задачи 1.2):
- путь БД берется из env EKOTOV_WIKI_DB_PATH (дефолт /data/wiki.db — тот же
  путь, что DB_PATH в deploy/compose.yaml ядра; сервис — read-only потребитель
  того же тома, маунт wiki-data:/data:ro);
- монолитный backend/app/config.py не переносится: он требует SECRET_KEY и
  AVATARS_DIR, которые сервису не нужны; сервис читает только путь;
- READ-ONLY ОТКРЫТИЕ (вместо PRAGMA journal_mode=WAL ядра): сервис открывает
  БД по URI mode=ro и НИКОГДА не пишет. PRAGMA journal_mode=WAL ядра на
  ro-маунте падает «attempt to write a readonly database» — это запись в
  заголовок БД. Гибрид mode=ro → immutable=1 (см. open_readonly):
  - mode=ro при живых -wal/-shm (app работает) читает свежие данные
    писателя, включая незачекпоинченные;
  - если -wal/-shm отсутствуют (app в простое закрыл все соединения —
    sqlite удаляет их), mode=ro падает (sqlite не может пересоздать -shm),
    fallback immutable=1 читает main-db (состояние последнего checkpoint'а;
    новые задачи появляются после ближайшей транзакции app, воссоздающей
    wal, — осознанный компромисс простоя, не данных);
  - immutable=1 при живом -wal НЕ используется (игнорирует wal — несвежие
    данные): он только для случая «wal отсутствует физически».
- foreign_keys=ON сохранен (connection-level PRAGMA — не запись в файл).
Схему сервис НЕ мигрирует и не пишет в БД (design §2: инварианты монолита
не нарушаются).
"""

import os
import sqlite3
from urllib.parse import quote as _uri_quote

# Тот же путь БД, что у ядра в контейнере (deploy/compose.yaml: DB_PATH=/data/wiki.db).
DEFAULT_DB_PATH = "/data/wiki.db"


def _open_readonly(path: str) -> sqlite3.Connection:
    """Read-only соединение: mode=ro, fallback immutable=1 (см. докстринг модуля).

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
    except sqlite3.OperationalError:
        try:
            conn.close()  # type: ignore[possibly-undefined]
        except NameError:
            pass
    conn = sqlite3.connect(f"file:{_uri_quote(path)}?immutable=1", uri=True)
    conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    return conn


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Read-only соединение с БД; FK-контроль включен.

    Путь — аргумент, иначе env EKOTOV_WIKI_DB_PATH, иначе дефолт
    /data/wiki.db (как в ядре). Отличие от ядра (backend/app/db.py@HEAD):
    БД открывается только для чтения (ro-маунт тома, design §2) — см.
    докстринг модуля.
    """
    path = db_path or os.environ.get("EKOTOV_WIKI_DB_PATH") or DEFAULT_DB_PATH
    conn = _open_readonly(path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
