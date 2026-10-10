"""Миграция: создание таблиц pages и page_versions (задача 2.1, add-wiki;
design.md §1/§2; FR-107…FR-116; NFR-32; спека wiki: «Миграция таблиц pages
и page_versions»).

Одноразовый идемпотентный скрипт внедрения (ОГР-9), паттерн
app.migrate_gallery. Запуск из каталога backend/ (DB_PATH из окружения,
как у python -m app.db):

    DB_PATH=/path/to/wiki.db SECRET_KEY=x python -m app.migrate_wiki

Что создает (design §1 — дословно):
  pages         (id, parent_id NULL FK→pages ON DELETE RESTRICT — NULL =
                 корневая, title NOT NULL, content NOT NULL DEFAULT ''
                 — пустая строка, не NULL: упрощает санитизацию, author_id
                 NOT NULL FK→users, created_at, updated_at NOT NULL)
  page_versions (id, page_id NOT NULL FK→pages ON DELETE CASCADE,
                 content NOT NULL, author_id NOT NULL FK→users, created_at)
  + индексы: pages(parent_id) — выборка дерева, pages(title) — LIKE-префикс
    по заголовку, page_versions(page_id, id) — история от новых к старым
    (ORDER BY id DESC) без сортировки по created_at.

Идемпотентность: CREATE TABLE/INDEX IF NOT EXISTS — повторный запуск на
смигрированной БД ничего не создает (no-op, «created=0») и снова проходит
сверку. Атомарность: все DDL — в ОДНОЙ явной транзакции BEGIN IMMEDIATE
(паттерн migrate_gallery) — краш не оставляет частично мигрированной БД.

Автосверка (design §2; NFR-32) — структурные инварианты, без записи данных
в БД:
  (а) обе таблицы существуют;
  (б) наборы колонок каждой таблицы = design §1;
  (в) NOT NULL на обязательных колонках (PRAGMA table_info notnull);
  (г) DEFAULT '' на pages.content (PRAGMA table_info dflt_value);
  (д) FK-цели и ON DELETE RESTRICT/CASCADE (PRAGMA foreign_key_list);
  (е) все 3 индекса существуют на своих таблицах/колонках.
Расхождение → печать в stdout + exit 1 (внедрение не завершено).

Владелец схемы — монолит (design §1: таблицы в общей wiki.db). Повторный
прогон на копии прод-БД — обязательный шаг 4.4 до боевой накатки (урок Р4).

Выход: 0 — сверка зелёная; 1 — расхождение.
"""

import sqlite3
import sys

from app.config import settings
from app.db import get_connection

FAIL = 1

# design §1 — дословно.
WIKI_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS pages (
      id         INTEGER PRIMARY KEY,
      parent_id  INTEGER REFERENCES pages(id) ON DELETE RESTRICT,
      title      TEXT NOT NULL,
      content    TEXT NOT NULL DEFAULT '',
      author_id  INTEGER NOT NULL REFERENCES users(id),
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pages_parent ON pages(parent_id)",
    "CREATE INDEX IF NOT EXISTS idx_pages_title ON pages(title)",
    """
    CREATE TABLE IF NOT EXISTS page_versions (
      id         INTEGER PRIMARY KEY,
      page_id    INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      content    TEXT NOT NULL,
      author_id  INTEGER NOT NULL REFERENCES users(id),
      created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_page_versions_page ON page_versions(page_id, id)",
]

WIKI_TABLES = ("pages", "page_versions")

# Ожидаемые колонки (набор, порядок не сверяем — SQLite не гарантирует).
EXPECTED_COLUMNS: dict[str, set[str]] = {
    "pages": {"id", "parent_id", "title", "content", "author_id",
              "created_at", "updated_at"},
    "page_versions": {"id", "page_id", "content", "author_id", "created_at"},
}

# NOT NULL-колонки (id INTEGER PRIMARY KEY — ROWID alias, notnull в PRAGMA = 0).
EXPECTED_NOT_NULL: dict[str, set[str]] = {
    "pages": {"title", "content", "author_id", "created_at", "updated_at"},
    "page_versions": {"page_id", "content", "author_id", "created_at"},
}

# DEFAULT-значения: таблица → колонка → dflt_value (строка из PRAGMA).
EXPECTED_DEFAULTS: dict[str, dict[str, str]] = {
    "pages": {"content": "''"},
}

# Ожидаемые FK: таблица → {(колонка, цель, on_delete)}.
EXPECTED_FKS: dict[str, set[tuple[str, str, str]]] = {
    "pages": {
        ("parent_id", "pages", "RESTRICT"),
        ("author_id", "users", "NO ACTION"),
    },
    "page_versions": {
        ("page_id", "pages", "CASCADE"),
        ("author_id", "users", "NO ACTION"),
    },
}

# Индексы: имя → (таблица, колонки).
EXPECTED_INDEXES: dict[str, tuple[str, tuple[str, ...]]] = {
    "idx_pages_parent": ("pages", ("parent_id",)),
    "idx_pages_title": ("pages", ("title",)),
    "idx_page_versions_page": ("page_versions", ("page_id", "id")),
}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def _create_tables(conn: sqlite3.Connection) -> None:
    """Создание таблиц/индексов wiki в ОДНОЙ транзакции (идемпотентно).

    Открывает BEGIN IMMEDIATE и commit'ит — краш между CREATE не оставляет
    частично мигрированной БД (паттерн migrate_gallery). Факт создания
    считает вызывающий код по снимкам sqlite_master «до/после»."""
    conn.execute("BEGIN IMMEDIATE")
    for stmt in WIKI_DDL:
        conn.execute(stmt)
    conn.commit()


def _verify(conn: sqlite3.Connection) -> list[str]:
    """Автосверка (design §2, NFR-32): таблицы/колонки/NOT NULL/DEFAULT/
    FK + ON DELETE/индексы.

    Только структурные проверки (PRAGMA + sqlite_master) — данных в БД
    миграция не пишет и существующие записи не трогает. Возвращает список
    расхождений (пустой = зелёная)."""
    bad: list[str] = []
    tables = _table_names(conn)

    # (а) обе таблицы существуют.
    for table in WIKI_TABLES:
        if table not in tables:
            bad.append(f"FAIL: таблица {table} отсутствует")

    # (б) наборы колонок = design §1; (в) NOT NULL; (г) DEFAULT.
    for table, expected in EXPECTED_COLUMNS.items():
        if table not in tables:
            continue
        info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        actual = {row[1] for row in info}
        missing = expected - actual
        extra = actual - expected
        if missing:
            bad.append(f"FAIL: {table}: нет колонок {sorted(missing)}")
        if extra:
            bad.append(f"FAIL: {table}: лишние колонки {sorted(extra)}")
        # (в) NOT NULL.
        expected_nn = EXPECTED_NOT_NULL.get(table, set())
        actual_nn = {row[1] for row in info if row[3]}
        for col in expected_nn - actual_nn:
            bad.append(f"FAIL: {table}.{col}: NOT NULL не найден")
        # (г) DEFAULT.
        actual_dflt = {row[1]: row[4] for row in info if row[4] is not None}
        for col, dflt in EXPECTED_DEFAULTS.get(table, {}).items():
            if actual_dflt.get(col) != dflt:
                bad.append(
                    f"FAIL: {table}.{col}: DEFAULT {actual_dflt.get(col)!r}, "
                    f"ожидается {dflt}"
                )

    # (д) FK: цель и ON DELETE.
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

    # (е) индексы: имя, таблица, колонки.
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
        print("=== Миграция: таблицы pages и page_versions (задача 2.1, add-wiki) ===")
        print(f"БД: {settings.db_path}")

        tables = _table_names(conn)
        if "users" not in tables:
            print(
                "FAIL: таблицы users нет — сначала примените схему ядра "
                "(python -m app.db); pages.author_id и page_versions.author_id "
                "ссылаются на users.id."
            )
            return FAIL

        before = {t: (t in tables) for t in WIKI_TABLES}
        existing = [t for t, was in before.items() if was]
        print(
            f"До: таблиц wiki существует {len(existing)}/2"
            + (f": {existing}" if existing else " (чистая БД)")
        )

        # Создание (идемпотентно, одна транзакция).
        _create_tables(conn)

        tables_after = _table_names(conn)
        created = [t for t in WIKI_TABLES if t not in tables and t in tables_after]
        print(f"Создано таблиц: {len(created)}" + (f": {created}" if created else " (no-op — все существовали)"))
        print("Создано/подтверждено индексов: 3")

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
            "Проверено: 2 таблицы; колонки = design §1; NOT NULL обязательных "
            "колонок; DEFAULT '' на pages.content; FK pages.parent_id → pages "
            "ON DELETE RESTRICT, page_versions.page_id → pages ON DELETE "
            "CASCADE, author_id → users; 3 индекса (pages.parent_id, "
            "pages.title, page_versions(page_id, id))."
        )
        print("Внедрение таблиц wiki завершено (владелец схемы — монолит).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
