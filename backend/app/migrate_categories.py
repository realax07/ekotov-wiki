"""Миграция: справочник категорий + приведение fast-задач (tasks.md 1.3;
sdd r2 §2, §5/NFR-8; design.md §1.2, §4; FR-22, NFR-8, FR-27-приведение).

Одноразовый идемпотентный скрипт внедрения Релиза 2 (ОГР-9). Запуск из
каталога backend/ (DB_PATH из окружения, как у python -m app.db):

    DB_PATH=/path/to/wiki.db SECRET_KEY=x python -m app.migrate_categories

Шаги (design.md §1.2):
1. Снимок «до»: список уникальных непустых значений tasks.category +
   категории каждой задачи (для сверки NFR-8).
2. INSERT DISTINCT непустых category в categories — маппинг 1:1
   (Д-2), пустые/NULL значения записей не создают; повторный запуск
   не создает дублей (INSERT OR IGNORE + UNIQUE name). Слияние
   «синонимов» НЕ выполняется (Д-2, ОГР-9): «home» и «Home» —
   разные категории.
3. Задачи не трогаются: их значения не изменяются — совпадают
   с созданными записями справочника.
4. Автосверка «после» (NFR-8):
   (а) каждое непустое значение category каждой задачи присутствует
   в categories;
   (б) COUNT(categories) = COUNT(DISTINCT непустых category «до»);
   (в) категории каждой задачи = значениям снимка (0 измененных).
   Расхождение → провал (exit 1), внедрение не завершено
   (Scenario «Негативный: расхождение сверки останавливает внедрение»).
5. Приведение fast-задач к инварианту FR-27 `is_fast ⇒ priority='high'`:
   UPDATE tasks SET priority='high' WHERE is_fast=1 AND priority != 'high'
   (design.md §4: разовое приведение при внедрении; сц. дельты fastline
   «Приведение существующих»). Приведенные задачи учитываются в отчете.

Идемпотентность: повторный запуск на уже смигрированной БД — свершений
не меняет (справочник уже содержит значения), сверка снова зеленая.
Задачи скриптом не изменяются, кроме детерминированного приведения fast
(после первого запуска приводить нечего — ссылок на инвариант нет).

Атомарность (ревью 001, замечание 3): шаги 2 (INSERT категорий) и 5
(приведение fast) выполняются в ОДНОЙ явной транзакции — BEGIN IMMEDIATE
перед первым INSERT, commit после приведения; краш между шагами не
оставляет частично мигрированной БД (частичный отказ ранее доводился
повторным запуском — теперь исключен вовсе).

Выход: 0 — сверка зелёная; 1 — расхождение (внедрение не завершено).
Отчет сверки печатается в stdout — переносится в отчет задачи.
"""

import sqlite3
import sys

from app.config import settings
from app.db import get_connection

FAIL = 1


def _snapshot_before(conn: sqlite3.Connection) -> tuple[list[str], dict[int, str | None]]:
    """Снимок «до» (design.md §1.2 п.1): уникальные непустые category +
    категории каждой задачи (task_id → значение, для сверки «не изменено»)."""
    unique_non_empty = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT category FROM tasks "
            "WHERE category IS NOT NULL AND category <> ''"
        ).fetchall()
    ]
    per_task = {
        row[0]: row[1]
        for row in conn.execute("SELECT id, category FROM tasks").fetchall()
    }
    return unique_non_empty, per_task


def _insert_categories(conn: sqlite3.Connection, names: list[str]) -> int:
    """Шаг 2: INSERT DISTINCT непустых category (1:1, Д-2; пустые мимо).

    INSERT OR IGNORE: повторный запуск не падает на UNIQUE и не создает
    дублей — идемпотентность (design.md §1.2).
    Открывает явную транзакцию BEGIN IMMEDIATE (ревью 001, замечание 3):
    commit делает вызывающий код после шага 5 — INSERT и приведение fast
    атомарны вместе, частично мигрированная БД исключена."""
    conn.execute("BEGIN IMMEDIATE")
    inserted = 0
    for name in names:
        cur = conn.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,)
        )
        inserted += cur.rowcount
    return inserted


def _normalize_fast_priority(conn: sqlite3.Connection) -> int:
    """Шаг 5: приведение `is_fast ⇒ priority='high'` (FR-27, design.md §4).

    Выполняется в транзакции шага 2 (ревью 001, замечание 3); commit —
    в main после этого шага."""
    cur = conn.execute(
        "UPDATE tasks SET priority = 'high' "
        "WHERE is_fast = 1 AND (priority IS NULL OR priority != 'high')"
    )
    return cur.rowcount


def _verify_after(
    conn: sqlite3.Connection,
    unique_before: list[str],
    per_task_before: dict[int, str | None],
) -> list[str]:
    """Шаг 4: автосверка «после» (NFR-8). Возвращает список расхождений
    (пустой = сверка зелёная):
    (а) каждое непустое category каждой задачи есть в categories;
    (б) COUNT(categories) = COUNT(DISTINCT непустых «до»);
    (в) значения категорий задач = снимку «до» (0 потерянных/измененных).
    """
    mismatches: list[str] = []

    missing = conn.execute(
        "SELECT COUNT(*) FROM tasks t "
        "WHERE t.category IS NOT NULL AND t.category <> '' "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM categories c WHERE c.name = t.category"
        ")"
    ).fetchone()[0]
    if missing:
        mismatches.append(
            f"FAIL: {missing} задач(и) с категорией, отсутствующей в справочнике"
        )

    total_categories = conn.execute(
        "SELECT COUNT(*) FROM categories"
    ).fetchone()[0]
    if total_categories != len(unique_before):
        mismatches.append(
            f"FAIL: COUNT(categories)={total_categories} != "
            f"COUNT(DISTINCT непустых category до)={len(unique_before)}"
        )

    per_task_after = {
        row[0]: row[1]
        for row in conn.execute("SELECT id, category FROM tasks").fetchall()
    }
    changed = [
        task_id
        for task_id, before in per_task_before.items()
        if per_task_after.get(task_id) != before
    ]
    if changed:
        mismatches.append(
            f"FAIL: изменены значения категорий задач: {sorted(changed)[:10]}"
        )

    return mismatches


def main() -> int:
    conn: sqlite3.Connection = get_connection()
    try:
        print("=== Миграция: справочник категорий (tasks.md 1.3, FR-22/NFR-8) ===")
        print(f"БД: {settings.db_path}")

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "categories" not in tables:
            print(
                "FAIL: таблицы categories нет — сначала примените схему "
                "(python -m app.db); миграция справочник не создает."
            )
            return FAIL

        # Шаг 1: снимок «до».
        unique_before, per_task_before = _snapshot_before(conn)
        tasks_total = len(per_task_before)
        print(
            f"До: задач={tasks_total}, уникальных непустых category="
            f"{len(unique_before)}: {sorted(unique_before)}"
        )

        # Шаги 2–3: INSERT DISTINCT (1:1), задачи не трогаются.
        inserted = _insert_categories(conn, unique_before)
        print(f"Создано записей справочника: {inserted}")

        # Шаг 5: приведение fast-задач (FR-27-приведение).
        fast_normalized = _normalize_fast_priority(conn)
        print(f"fast-задач приведено к priority='high': {fast_normalized}")

        # Единый commit шагов 2+5 (одна транзакция, ревью 001, замечание 3).
        conn.commit()

        # Шаг 4: автосверка «после».
        mismatches = _verify_after(conn, unique_before, per_task_before)
        if mismatches:
            print("\n=== Сверка «после»: ПРОВАЛ (NFR-8) ===")
            for line in mismatches:
                print(line)
            print("Внедрение НЕ завершено: устраните расхождение и повторите.")
            return FAIL

        print("\n=== Сверка «после»: ОК (NFR-8, 0 потерь) ===")
        print(
            f"Проверено: (а) каждое непустое category всех {tasks_total} задач "
            "есть в справочнике; "
            f"(б) COUNT(categories)={len(unique_before)} = уникальным непустым «до»; "
            "(в) значения категорий задач = снимку (0 измененных)."
        )
        print("Внедрение справочника завершено.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
