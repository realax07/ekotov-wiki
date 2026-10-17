"""Миграция: создание таблицы video_videos (tasks.md 1.1, video-hosting
волна 1 кусок A; design §7; sdd §4; Requirement «Отдельный контейнерный
сервис…»).

Одноразовый идемпотентный скрипт внедрения, паттерн app.migrate_gallery /
app.migrate_wiki. Запуск из каталога backend/ (DB_PATH из окружения):

    DB_PATH=/path/to/wiki.db SECRET_KEY=x python -m app.migrate_video

Что создает (sdd §4 — дословно; кусок A, БЕЗ category_id — он добавляется
миграцией куска D, tasks 2.1):

  video_videos (
    id               TEXT PK,       -- uuid4; имя каталога в томе videos-data/<id>/
    filename         TEXT NOT NULL, -- исходное имя (метаданные; путь из него НЕ строится)
    status           TEXT NOT NULL, -- uploaded | converting | ready | error
    size_bytes       INTEGER NOT NULL,
    mime             TEXT,          -- исходный mime (по факту; белый список НЕ применяется)
    uploaded_by      INTEGER NOT NULL REFERENCES users(id),
    created_at       TEXT NOT NULL, -- ISO-8601
    convert_attempts INTEGER NOT NULL DEFAULT 0  -- 0..2; 2 + error = ретраи исчерпаны
  )

Идемпотентность: CREATE TABLE IF NOT EXISTS — повторный запуск на
смигрированной БД — no-op. Атомарность: DDL в ОДНОЙ явной транзакции
BEGIN IMMEDIATE (паттерн migrate_gallery, ревью 001 замечание 3).

Автосверка (задача 1.1: «состав колонок соответствует sdd §4») —
структурные проверки по PRAGMA: таблица существует, набор колонок и
DEFAULT convert_attempts=0, PK = id (TEXT), FK uploaded_by → users.
Расхождение → печать в stdout + exit 1.

Владелец схемы — сервис video (design §7): ядро после миграции в таблицу
НЕ пишет (первичное создание — one-shot миграцией ядра по запросу
владельца; включение в деплой — MIGRATE_MODULE в 6.1, строго до up).
Волна 2 (кусок D, tasks 2.1) расширяет ЭТОТ ЖЕ файл — таблицы
video_comments/video_reactions и ALTER category_id добавляются
последовательно (общая зона 1.1 → 2.1).

Выход: 0 — сверка зелёная; 1 — расхождение.
"""

import re
import sqlite3
import sys

from app.config import settings
from app.db import get_connection

FAIL = 1

# sdd §4 — дословно (кусок A: без category_id — миграция 2.1 добавит ALTER'ом).
VIDEO_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS video_videos (
      id               TEXT NOT NULL PRIMARY KEY,
      filename         TEXT NOT NULL,
      status           TEXT NOT NULL,
      size_bytes       INTEGER NOT NULL,
      mime             TEXT,
      uploaded_by      INTEGER NOT NULL REFERENCES users(id),
      created_at       TEXT NOT NULL,
      convert_attempts INTEGER NOT NULL DEFAULT 0
    )
    """
]

VIDEO_TABLES = ("video_videos",)

# Ожидаемые колонки: {колонка: (тип, notnull, default)} — набор = sdd §4.
EXPECTED_COLUMNS: dict[str, tuple[str, int, str | None]] = {
    "id": ("TEXT", 1, None),
    "filename": ("TEXT", 1, None),
    "status": ("TEXT", 1, None),
    "size_bytes": ("INTEGER", 1, None),
    "mime": ("TEXT", 0, None),
    "uploaded_by": ("INTEGER", 1, None),
    "created_at": ("TEXT", 1, None),
    "convert_attempts": ("INTEGER", 1, "0"),
}

EXPECTED_FKS = {("uploaded_by", "users")}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def _create_tables(conn: sqlite3.Connection) -> None:
    """Создание таблицы в ОДНОЙ транзакции (идемпотентно, паттерн
    migrate_categories): BEGIN IMMEDIATE + commit — краш между CREATE не
    оставляет частично мигрированной БД."""
    conn.execute("BEGIN IMMEDIATE")
    for stmt in VIDEO_DDL:
        conn.execute(stmt)
    conn.commit()


def _verify(conn: sqlite3.Connection) -> list[str]:
    """Автосверка: таблица/колонки (тип, NOT NULL, DEFAULT)/PK/FK.

    Только структурные проверки (PRAGMA) — данных миграция не пишет.
    Возвращает список расхождений (пустой = зелёная)."""
    bad: list[str] = []
    tables = _table_names(conn)

    for table in VIDEO_TABLES:
        if table not in tables:
            bad.append(f"FAIL: таблица {table} отсутствует")

    if "video_videos" in tables:
        # (б) колонки: набор, тип, NOT NULL, DEFAULT (sdd §4).
        info = conn.execute("PRAGMA table_info(video_videos)").fetchall()
        actual = {row[1]: row for row in info}
        missing = set(EXPECTED_COLUMNS) - set(actual)
        extra = set(actual) - set(EXPECTED_COLUMNS)
        if missing:
            bad.append(f"FAIL: video_videos: нет колонок {sorted(missing)}")
        if extra:
            bad.append(f"FAIL: video_videos: лишние колонки {sorted(extra)}")
        for name, (ctype, notnull, dflt) in EXPECTED_COLUMNS.items():
            if name not in actual:
                continue
            row = actual[name]
            if (row[2] or "").upper() != ctype:
                bad.append(f"FAIL: video_videos.{name}: тип {row[2]}, ожидается {ctype}")
            if bool(row[3]) != bool(notnull):
                bad.append(
                    f"FAIL: video_videos.{name}: NOT NULL={row[3]}, ожидается {notnull}"
                )
            actual_default = "" if row[4] is None else str(row[4]).strip("'\"")
            expected_default = "" if dflt is None else dflt
            if actual_default != expected_default:
                bad.append(
                    f"FAIL: video_videos.{name}: DEFAULT {row[4]!r},"
                    f" ожидается {dflt!r}"
                )

        # (в) PK — id (одноколоночный TEXT; PRIMARY KEY в table_info pk=1).
        pk_cols = [row[1] for row in sorted(info, key=lambda r: r[5]) if row[5] > 0]
        if pk_cols != ["id"]:
            bad.append(f"FAIL: video_videos: PK={pk_cols}, ожидается ['id']")

        # (г) FK: uploaded_by → users.
        actual_fks = {
            (row[3], row[2])
            for row in conn.execute("PRAGMA foreign_key_list(video_videos)").fetchall()
        }
        missing_fks = EXPECTED_FKS - actual_fks
        if missing_fks:
            bad.append(
                f"FAIL: video_videos: нет/не те FK: {sorted(missing_fks)}"
                f" (факт: {sorted(actual_fks)})"
            )

    return bad


def main() -> int:
    conn: sqlite3.Connection = get_connection()
    try:
        print("=== Миграция: таблица video_videos (tasks 1.1 video-hosting) ===")
        print(f"БД: {settings.db_path}")

        tables = _table_names(conn)
        if "users" not in tables:
            print(
                "FAIL: таблицы users нет — сначала примените схему ядра "
                "(python -m app.db); video_videos.uploaded_by ссылается на users.id."
            )
            return FAIL

        existed = "video_videos" in tables
        print("До: таблица video_videos " + ("существует" if existed else "отсутствует (чистая БД)"))

        _create_tables(conn)

        created = "video_videos" in _table_names(conn) and not existed
        print("Создано таблиц: 1 (video_videos)" if created else "no-op — таблица существовала")

        mismatches = _verify(conn)
        if mismatches:
            print("\n=== Сверка: ПРОВАЛ ===")
            for line in mismatches:
                print(line)
            print("Внедрение НЕ завершено: устраните расхождение и повторите.")
            return FAIL

        print("\n=== Сверка: ОК ===")
        print(
            "Проверено: video_videos; колонки = sdd §4 (id TEXT PK uuid4, filename,"
            " status, size_bytes, mime, uploaded_by FK users, created_at,"
            " convert_attempts DEFAULT 0); PK id; FK uploaded_by → users."
        )
        print(
            "Внедрение таблицы video_videos завершено (владелец схемы — сервис video;"
            " ядро в таблицу не пишет; кусок D расширит файл миграции — tasks 2.1)."
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
