"""Миграция: создание таблиц видео-сервиса (tasks 1.1 + 2.1, video-hosting;
design §7; sdd §4; Requirement «Отдельный контейнерный сервис…»).

Одноразовый идемпотентный скрипт внедрения, паттерн app.migrate_gallery /
app.migrate_wiki. Запуск из каталога backend/ (DB_PATH из окружения):

    DB_PATH=/path/to/wiki.db SECRET_KEY=x python -m app.migrate_video

Что создает (sdd §4 — дословно):

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
  + category_id INTEGER REFERENCES image_categories(id)  -- кусок D (r2, tasks 2.1):
                                     -- NULL = «Без категории»; FK на СУЩЕСТВУЮЩИЙ
                                     -- справочник галереи (новый НЕ создается)
  video_comments (
    id         TEXT PK,              -- uuid4
    video_id   TEXT NOT NULL REFERENCES video_videos(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    text       TEXT NOT NULL,        -- непустой (валидация API, 422)
    created_at TEXT NOT NULL
  )
  video_reactions (
    video_id   TEXT NOT NULL REFERENCES video_videos(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    value      INTEGER NOT NULL CHECK (value IN (1, -1)),  -- лайк/дизлайк
    created_at TEXT NOT NULL,
    PRIMARY KEY (video_id, user_id)  -- уникальность голоса (toggle=DELETE,
                                     -- перенос=UPDATE value)
  )

Идемпотентность: CREATE TABLE IF NOT EXISTS + ALTER ADD COLUMN только при
отсутствии колонки — повторный запуск на смигрированной БД — no-op
(на БД куска A категория досоздается ALTER'ом, на чистой — тем же путем
после CREATE по схеме куска A). Атомарность: DDL в ОДНОЙ явной транзакции
BEGIN IMMEDIATE (паттерн migrate_gallery, ревью 001 замечание 3).

Автосверка (задачи 1.1/2.1: «состав колонок/таблиц соответствует sdd §4»)
— структурные проверки по PRAGMA: таблицы существуют; состав/типы/NOT NULL/
DEFAULT колонок; PK video_videos=id (TEXT), video_reactions=(video_id,
user_id); FK (uploaded_by → users; video_id → video_videos CASCADE;
user_id → users; category_id → image_categories); CHECK value IN (1,-1)
на video_reactions (по DDL в sqlite_master). Расхождение → печать в
stdout + exit 1.

Владелец схемы — сервис video (design §7): ядро после миграции в таблицы
НЕ пишет (первичное создание — one-shot миграция ядра по запросу
владельца; включение в деплой — MIGRATE_MODULE в 6.1, строго до up).

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
    """,
    # Социальный слой (кусок D, r2; паттерн image_comments/image_reactions
    # галереи — FR-81/82). CASCADE — удаление видео чистит comments/reactions.
    """
    CREATE TABLE IF NOT EXISTS video_comments (
      id         TEXT NOT NULL PRIMARY KEY,
      video_id   TEXT NOT NULL REFERENCES video_videos(id) ON DELETE CASCADE,
      user_id    INTEGER NOT NULL REFERENCES users(id),
      text       TEXT NOT NULL,
      created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS video_reactions (
      video_id   TEXT NOT NULL REFERENCES video_videos(id) ON DELETE CASCADE,
      user_id    INTEGER NOT NULL REFERENCES users(id),
      value      INTEGER NOT NULL CHECK (value IN (1, -1)),
      created_at TEXT NOT NULL,
      PRIMARY KEY (video_id, user_id)
    )
    """,
]

# Кусок D: категория — FK на СУЩЕСТВУЮЩИЙ справочник галереи (image_categories,
# RO у сервиса video; новый справочник НЕ создается). Досоздается ALTER'ом
# (идемпотентно — проверка наличия колонки перед ALTER, tasks 2.1-б).
CATEGORY_COLUMN_SQL = (
    "ALTER TABLE video_videos ADD COLUMN category_id INTEGER"
    " REFERENCES image_categories(id)"
)

VIDEO_TABLES = ("video_videos", "video_comments", "video_reactions")

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
    # Кусок D (r2): NULL = «Без категории»; FK image_categories.
    "category_id": ("INTEGER", 0, None),
}

# Социальный слой (sdd §4): {таблица: (колонки, PK, FK-пары (колонка, таблица))}.
EXPECTED_SOCIAL: dict[str, tuple[dict[str, tuple[str, int]], list[str], set[tuple[str, str]]]] = {
    "video_comments": (
        {
            "id": ("TEXT", 1),
            "video_id": ("TEXT", 1),
            "user_id": ("INTEGER", 1),
            "text": ("TEXT", 1),
            "created_at": ("TEXT", 1),
        },
        ["id"],
        {("video_id", "video_videos"), ("user_id", "users")},
    ),
    "video_reactions": (
        {
            "video_id": ("TEXT", 1),
            "user_id": ("INTEGER", 1),
            "value": ("INTEGER", 1),
            "created_at": ("TEXT", 1),
        },
        ["video_id", "user_id"],
        {("video_id", "video_videos"), ("user_id", "users")},
    ),
}

# CASCADE у FK video_id (удаление видео чистит комментарии/реакции).
EXPECTED_CASCADE = {("video_comments", "video_id"), ("video_reactions", "video_id")}

EXPECTED_FKS = {("uploaded_by", "users"), ("category_id", "image_categories")}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def _video_columns(conn: sqlite3.Connection) -> set[str]:
    return {
        row[1]
        for row in conn.execute("PRAGMA table_info(video_videos)").fetchall()
    }


def _create_tables(conn: sqlite3.Connection) -> None:
    """Создание таблиц + колонки категории в ОДНОЙ транзакции (идемпотентно,
    паттерн migrate_categories): BEGIN IMMEDIATE + commit — краш между DDL не
    оставляет частично мигрированной БД. ALTER category_id — только при
    отсутствии колонки (БД куска A / чистая БД — оба пути сходятся)."""
    conn.execute("BEGIN IMMEDIATE")
    for stmt in VIDEO_DDL:
        conn.execute(stmt)
    if "category_id" not in _video_columns(conn):
        conn.execute(CATEGORY_COLUMN_SQL)
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

        # (г) FK: uploaded_by → users, category_id → image_categories.
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

    # (д) Социальный слой (кусок D): колонки/PK/FK + CASCADE + CHECK.
    for table, (columns, pk_cols_expected, fks) in EXPECTED_SOCIAL.items():
        if table not in tables:
            continue  # отсутствие таблицы уже записано выше
        info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        actual_cols = {row[1]: row for row in info}
        missing = set(columns) - set(actual_cols)
        extra = set(actual_cols) - set(columns)
        if missing:
            bad.append(f"FAIL: {table}: нет колонок {sorted(missing)}")
        if extra:
            bad.append(f"FAIL: {table}: лишние колонки {sorted(extra)}")
        for name, (ctype, notnull) in columns.items():
            if name not in actual_cols:
                continue
            row = actual_cols[name]
            if (row[2] or "").upper() != ctype:
                bad.append(f"FAIL: {table}.{name}: тип {row[2]}, ожидается {ctype}")
            if bool(row[3]) != bool(notnull):
                bad.append(
                    f"FAIL: {table}.{name}: NOT NULL={row[3]}, ожидается {notnull}"
                )
        pk_cols = [row[1] for row in sorted(info, key=lambda r: r[5]) if row[5] > 0]
        if pk_cols != pk_cols_expected:
            bad.append(
                f"FAIL: {table}: PK={pk_cols}, ожидается {pk_cols_expected}"
            )
        actual_fks = {
            (row[3], row[2], str(row[6]).upper())  # (from, to, on_delete)
            for row in conn.execute(
                f"PRAGMA foreign_key_list({table})"
            ).fetchall()
        }
        for col, ref in fks:
            matches = [fk for fk in actual_fks if fk[0] == col and fk[1] == ref]
            if not matches:
                bad.append(f"FAIL: {table}: нет FK {col} → {ref}")
            elif (table, col) in EXPECTED_CASCADE and all(
                fk[2] != "CASCADE" for fk in matches
            ):
                bad.append(f"FAIL: {table}.{col}: FK без ON DELETE CASCADE")

    # (е) CHECK value IN (1, -1) на video_reactions — по DDL в sqlite_master.
    if "video_reactions" in tables:
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'"
            " AND name='video_reactions'"
        ).fetchone()
        sql = (ddl[0] or "").upper() if ddl else ""
        if "CHECK" not in sql or "1" not in sql or "-1" not in sql:
            bad.append(
                "FAIL: video_reactions: нет CHECK (value IN (1, -1)) в DDL"
            )

    return bad


def main() -> int:
    conn: sqlite3.Connection = get_connection()
    try:
        print("=== Миграция: таблицы видео-сервиса (tasks 1.1 + 2.1 video-hosting) ===")
        print(f"БД: {settings.db_path}")

        tables = _table_names(conn)
        if "users" not in tables:
            print(
                "FAIL: таблицы users нет — сначала примените схему ядра "
                "(python -m app.db); video_videos.uploaded_by ссылается на users.id."
            )
            return FAIL
        if "image_categories" not in tables:
            print(
                "FAIL: таблицы image_categories нет — сначала примените миграцию "
                "галереи (python -m app.migrate_gallery); video_videos.category_id "
                "ссылается на существующий справочник галереи (кусок D, tasks 2.1)."
            )
            return FAIL

        existed = "video_videos" in tables
        print("До: таблица video_videos " + ("существует" if existed else "отсутствует (чистая БД)"))

        _create_tables(conn)

        created_now = [
            t for t in VIDEO_TABLES if t in _table_names(conn)
        ]
        created = len(created_now) == len(VIDEO_TABLES) and not existed
        print(
            f"Создано таблиц: {len(VIDEO_TABLES)} ({', '.join(VIDEO_TABLES)})"
            if created
            else "no-op — таблицы уже существовали (category_id досоздан при отсутствии)"
        )

        mismatches = _verify(conn)
        if mismatches:
            print("\n=== Сверка: ПРОВАЛ ===")
            for line in mismatches:
                print(line)
            print("Внедрение НЕ завершено: устраните расхождение и повторите.")
            return FAIL

        print("\n=== Сверка: ОК ===")
        print(
            "Проверено: video_videos (+category_id FK image_categories),"
            " video_comments, video_reactions — состав колонок = sdd §4;"
            " PK video_videos=id, video_reactions=(video_id, user_id);"
            " FK users/image_categories/video_videos (CASCADE);"
            " CHECK value IN (1, -1)."
        )
        print(
            "Внедрение таблиц видео-сервиса завершено (владелец схемы — сервис"
            " video; ядро в таблицы не пишет; image_categories — только SELECT"
            " у сервиса, справочник галереи)."
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
