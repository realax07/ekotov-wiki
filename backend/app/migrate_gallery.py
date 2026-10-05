"""Миграция: создание 6 таблиц gallery (задача 1.3, add-gallery-service;
design.md §2/§7; FR-79…FR-82; спека services: «Схему создает ядро»).

Одноразовый идемпотентный скрипт внедрения (ОГР-9), паттерн app.migrate_categories.
Запуск из каталога backend/ (DB_PATH из окружения, как у python -m app.db):

    DB_PATH=/path/to/wiki.db SECRET_KEY=x python -m app.migrate_gallery

Что создает (design §2 — дословно):
  image_categories (id, name UNIQUE NOT NULL)
  images           (метаданные; FK category_id → image_categories, uploaded_by → users)
  gallery_tags     (id, name UNIQUE NOT NULL)
  image_tags       (PK(image_id, tag_id); image_id CASCADE)
  image_reactions  (PK(image_id, user_id) — один голос FR-81; value CHECK IN (1,-1);
                    image_id CASCADE)
  image_comments   (image_id CASCADE)
  + индексы: images(category_id), images(created_at) — сортировка сетки,
    image_tags(tag_id) — фильтр по тегу, image_comments(image_id).

Идемпотентность: CREATE TABLE/INDEX IF NOT EXISTS — повторный запуск на
смигрированной БД ничего не создает (no-op, «created=0») и снова проходит
сверку. Атомарность: все DDL — в ОДНОЙ явной транзакции BEGIN IMMEDIATE
(паттерн migrate_categories, ревью 001 замечание 3) — краш не оставляет
частично мигрированной БД.

Автосверка (design §7: «таблицы существуют, инварианты схемы; exit 1 при
расхождении») — структурные инварианты, без записи данных в БД:
  (а) все 6 таблиц существуют;
  (б) наборы колонок каждой таблицы = design §2;
  (в) составные PK: image_tags(image_id, tag_id), image_reactions(image_id, user_id);
  (г) FK-цели и ON DELETE CASCADE (PRAGMA foreign_key_list);
  (д) CHECK value IN (1, -1) на image_reactions (DDL в sqlite_master);
  (е) UNIQUE на image_categories.name / gallery_tags.name (PRAGMA index_list);
  (ж) все 4 индекса существуют на своих таблицах/колонках.
Расхождение → печать в stdout + exit 1 (внедрение не завершено).

Владелец схемы — сервис images (RW-профиль, design §2): ядро после миграции
таблицы gallery не читает и не пишет. Повторный прогон на копии прод-БД —
обязательный шаг 2.2 до боевой накатки (правило deploy-спеки, урок Р4).

Выход: 0 — сверка зелёная; 1 — расхождение.
"""

import re
import sqlite3
import sys

from app.config import settings
from app.db import get_connection

FAIL = 1

# design §2 — дословно (та же схема, что фикстура services/images/tests —
# сверка двух представлений выполнена в задаче 1.3).
GALLERY_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS image_categories (
      id   INTEGER PRIMARY KEY,
      name TEXT UNIQUE NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS images (
      id            INTEGER PRIMARY KEY,
      filename      TEXT NOT NULL,
      thumb_name    TEXT NOT NULL,
      original_name TEXT NOT NULL,
      mime          TEXT NOT NULL,
      size          INTEGER NOT NULL,
      category_id   INTEGER REFERENCES image_categories(id),
      uploaded_by   INTEGER NOT NULL REFERENCES users(id),
      created_at    TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_images_category ON images(category_id)",
    "CREATE INDEX IF NOT EXISTS idx_images_created_at ON images(created_at)",
    """
    CREATE TABLE IF NOT EXISTS gallery_tags (
      id    INTEGER PRIMARY KEY,
      name  TEXT UNIQUE NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS image_tags (
      image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
      tag_id   INTEGER NOT NULL REFERENCES gallery_tags(id),
      PRIMARY KEY (image_id, tag_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_image_tags_tag ON image_tags(tag_id)",
    """
    CREATE TABLE IF NOT EXISTS image_reactions (
      image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
      user_id  INTEGER NOT NULL REFERENCES users(id),
      value    INTEGER NOT NULL CHECK (value IN (1, -1)),
      PRIMARY KEY (image_id, user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS image_comments (
      id         INTEGER PRIMARY KEY,
      image_id   INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
      user_id    INTEGER NOT NULL REFERENCES users(id),
      body       TEXT NOT NULL,
      created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_image_comments_image ON image_comments(image_id)",
]

GALLERY_TABLES = (
    "image_categories",
    "images",
    "gallery_tags",
    "image_tags",
    "image_reactions",
    "image_comments",
)

# Ожидаемые колонки (набор, порядок не сверяем — SQLite не гарантирует).
EXPECTED_COLUMNS: dict[str, set[str]] = {
    "image_categories": {"id", "name"},
    "images": {
        "id", "filename", "thumb_name", "original_name", "mime",
        "size", "category_id", "uploaded_by", "created_at",
    },
    "gallery_tags": {"id", "name"},
    "image_tags": {"image_id", "tag_id"},
    "image_reactions": {"image_id", "user_id", "value"},
    "image_comments": {"id", "image_id", "user_id", "body", "created_at"},
}

# Составные PK (порядок значим — PRAGMA table_info pk=1..n).
EXPECTED_PKS: dict[str, tuple[str, ...]] = {
    "image_tags": ("image_id", "tag_id"),       # FR-79: связь картинка—тег
    "image_reactions": ("image_id", "user_id"), # FR-81: один голос на картинку
}

# Ожидаемые FK: таблица → {(колонка, цель, on_delete)}.
EXPECTED_FKS: dict[str, set[tuple[str, str, str]]] = {
    "images": {
        ("category_id", "image_categories", "NO ACTION"),
        ("uploaded_by", "users", "NO ACTION"),
    },
    "image_tags": {
        ("image_id", "images", "CASCADE"),
        ("tag_id", "gallery_tags", "NO ACTION"),
    },
    "image_reactions": {
        ("image_id", "images", "CASCADE"),
        ("user_id", "users", "NO ACTION"),
    },
    "image_comments": {
        ("image_id", "images", "CASCADE"),
        ("user_id", "users", "NO ACTION"),
    },
}

# UNIQUE-колонки (одноколоночные, кроме PK): таблица → колонка.
EXPECTED_UNIQUE: dict[str, str] = {
    "image_categories": "name",
    "gallery_tags": "name",
}

# Индексы: имя → (таблица, колонки).
EXPECTED_INDEXES: dict[str, tuple[str, tuple[str, ...]]] = {
    "idx_images_category": ("images", ("category_id",)),
    "idx_images_created_at": ("images", ("created_at",)),
    "idx_image_tags_tag": ("image_tags", ("tag_id",)),
    "idx_image_comments_image": ("image_comments", ("image_id",)),
}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def _create_tables(conn: sqlite3.Connection) -> int:
    """Создание таблиц/индексов gallery в ОДНОЙ транзакции (идемпотентно).

    Возвращает число фактически выполненных CREATE (по sqlite3_changes
    судить нельзя — DDL не DML; считаем реально созданные объекты через
    снимок sqlite_master «до/после» у вызывающего кода).
    Открывает BEGIN IMMEDIATE и commit'ит — краш между CREATE не оставляет
    частично мигрированной БД (паттерн migrate_categories)."""
    conn.execute("BEGIN IMMEDIATE")
    for stmt in GALLERY_DDL:
        conn.execute(stmt)
    conn.commit()
    return 0  # факт создания считает вызывающий код по снимкам sqlite_master


def _verify(conn: sqlite3.Connection) -> list[str]:
    """Автосверка (design §7): таблицы/колонки/PK/FK/CHECK/UNIQUE/индексы.

    Только структурные проверки (PRAGMA + sqlite_master) — данных в БД
    миграция не пишет и существующие записи не трогает. Возвращает список
    расхождений (пустой = зелёная)."""
    bad: list[str] = []
    tables = _table_names(conn)

    # (а) все 6 таблиц существуют.
    for table in GALLERY_TABLES:
        if table not in tables:
            bad.append(f"FAIL: таблица {table} отсутствует")

    # (б) наборы колонок = design §2.
    for table, expected in EXPECTED_COLUMNS.items():
        if table not in tables:
            continue
        actual = {
            row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        missing = expected - actual
        extra = actual - expected
        if missing:
            bad.append(f"FAIL: {table}: нет колонок {sorted(missing)}")
        if extra:
            bad.append(f"FAIL: {table}: лишние колонки {sorted(extra)}")

    # (в) составные PK (одноколоночные PK SQLite гарантирует схемой ROWID;
    # сверяем только составные — там, где инвариант спеки: FR-79/FR-81).
    for table, expected_pk in EXPECTED_PKS.items():
        if table not in tables:
            continue
        actual_pk = tuple(
            row[1]
            for row in sorted(
                conn.execute(f"PRAGMA table_info({table})").fetchall(),
                key=lambda r: r[5],
            )
            if row[5] > 0
        )
        if actual_pk != expected_pk:
            bad.append(
                f"FAIL: {table}: PK={actual_pk}, ожидается {expected_pk}"
            )

    # (г) FK: цель и ON DELETE.
    for table, expected_fks in EXPECTED_FKS.items():
        if table not in tables:
            continue
        actual_fks = {
            (row[3], row[2], row[6])
            for row in conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        }
        missing = expected_fks - actual_fks
        if missing:
            bad.append(
                f"FAIL: {table}: нет/не те FK: {sorted(missing)} "
                f"(факт: {sorted(actual_fks)})"
            )

    # (д) CHECK value IN (1, -1) на image_reactions (один голос, FR-81):
    # PRAGMA не показывает CHECK — сверяем DDL в sqlite_master.
    if "image_reactions" in tables:
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'"
            " AND name='image_reactions'"
        ).fetchone()[0] or ""
        normalized = re.sub(r"\s+", " ", ddl).replace("'", '"')
        if "CHECK" not in normalized.upper() or "1" not in normalized or "-1" not in normalized:
            bad.append(
                "FAIL: image_reactions: CHECK (value IN (1, -1)) не найден в DDL"
            )

    # (е) UNIQUE на name справочников.
    for table, column in EXPECTED_UNIQUE.items():
        if table not in tables:
            continue
        unique_cols: set[str] = set()
        for idx in conn.execute(f"PRAGMA index_list({table})").fetchall():
            if idx[2]:  # unique=1
                cols = [
                    r[2]
                    for r in conn.execute(f"PRAGMA index_info({idx[1]})").fetchall()
                ]
                if len(cols) == 1:
                    unique_cols.add(cols[0])
        if column not in unique_cols:
            bad.append(f"FAIL: {table}.{column}: UNIQUE-ограничение не найдено")

    # (ж) индексы: имя, таблица, колонки.
    for name, (table, expected_cols) in EXPECTED_INDEXES.items():
        row = conn.execute(
            "SELECT tbl_name FROM sqlite_master WHERE type='index' AND name=?",
            (name,),
        ).fetchone()
        if row is None:
            bad.append(f"FAIL: индекс {name} отсутствует")
            continue
        if row[0] != table:
            bad.append(f"FAIL: индекс {name} на таблице {row[0]}, ожидается {table}")
            continue
        actual_cols = tuple(
            r[2] for r in conn.execute(f"PRAGMA index_info({name})").fetchall()
        )
        if actual_cols != expected_cols:
            bad.append(
                f"FAIL: индекс {name}: колонки {actual_cols}, ожидается {expected_cols}"
            )

    return bad


def main() -> int:
    conn: sqlite3.Connection = get_connection()
    try:
        print("=== Миграция: таблицы gallery (задача 1.3, FR-79…FR-82) ===")
        print(f"БД: {settings.db_path}")

        tables = _table_names(conn)
        if "users" not in tables:
            print(
                "FAIL: таблицы users нет — сначала примените схему ядра "
                "(python -m app.db); images.uploaded_by ссылается на users.id."
            )
            return FAIL

        before = {t: (t in tables) for t in GALLERY_TABLES}
        existing = [t for t, was in before.items() if was]
        print(
            f"До: таблиц gallery существует {len(existing)}/6"
            + (f": {existing}" if existing else " (чистая БД)")
        )

        # Создание (идемпотентно, одна транзакция).
        _create_tables(conn)

        tables_after = _table_names(conn)
        created = [t for t in GALLERY_TABLES if t not in tables and t in tables_after]
        print(f"Создано таблиц: {len(created)}" + (f": {created}" if created else " (no-op — все существовали)"))
        print("Создано/подтверждено индексов: 4")

        # Автосверка.
        mismatches = _verify(conn)
        if mismatches:
            print("\n=== Сверка: ПРОВАЛ ===")
            for line in mismatches:
                print(line)
            print("Внедрение НЕ завершено: устраните расхождение и повторите.")
            return FAIL

        print("\n=== Сверка: ОК ===")
        print(
            "Проверено: 6 таблиц; колонки = design §2; PK image_tags(image_id, tag_id) "
            "и image_reactions(image_id, user_id); FK-цели + ON DELETE CASCADE; "
            "CHECK value IN (1, -1); UNIQUE name справочников; 4 индекса "
            "(images.category_id, images.created_at, image_tags.tag_id, "
            "image_comments.image_id)."
        )
        print("Внедрение таблиц gallery завершено (владелец схемы — сервис images).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
