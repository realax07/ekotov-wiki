"""Домен migr (Релиз 2): TC-migr-001…006 (CHK-97…102;
approved/add-r2-categories-settings/TC-migr-*.md).

Миграция справочника категорий (FR-22, NFR-8; sdd r2 §2/§5) — скрипт
`python -m app.migrate_categories` (backend/app/migrate_categories.py):
снимок «до» → INSERT DISTINCT непустых category (1:1, Д-2) → автосверка
«после» (расхождение = exit 1) → приведение fast-задач к priority='high'.

Все кейсы метки `candidate-archive` (impact §3 п.2 — разовая проверка
внедрения). Прогоны — на ВРЕМЕННОЙ копии БД стенда (fixture
``migr_temp_db``, conftest): миграция не трогает рабочий стенд.
Seed справочника в этих кейсах НЕ выполняется — миграция сама создает
категории из значений задач (предусловие кейсов).
"""

import csv
import os
import sqlite3

import pytest

pytestmark = [pytest.mark.api]

# QAT-данные «до миграции» (тестовые данные кейсов TC-migr-001…003).
MIGR_CATEGORIES = ("QAT-m-home", "QAT-m-Home", "QAT-m-work")


@pytest.mark.must
def test_migration_unique_values_become_categories_1to1(migr_temp_db):
    """TC-migr-001: три уникальных непустых значения (`QAT-m-home`,
    `QAT-m-Home`, `QAT-m-work`) → ровно три категории 1:1; слияния по
    регистру нет (Д-2, ОГР-9). Состав справочника читается из временной БД
    (миграция выполнялась на копии; шаг 4 кейса)."""
    db_path, run_migration, execute = migr_temp_db

    execute(
        "INSERT INTO tasks (title, category, status, is_fast, created_at, updated_at) "
        "VALUES ('QAT-m-з1','QAT-m-home','todo',0,datetime('now'),datetime('now')), "
        "('QAT-m-з2','QAT-m-Home','todo',0,datetime('now'),datetime('now')), "
        "('QAT-m-з3','QAT-m-work','todo',0,datetime('now'),datetime('now'))"
    )
    # контроль «до» (шаг 2 кейса): ровно 3 значения, категорий QAT-m-% нет
    before = execute(
        "SELECT DISTINCT category FROM tasks WHERE category LIKE 'QAT-m-%'"
    )
    assert sorted(row[0] for row in before) == sorted(MIGR_CATEGORIES)
    assert execute(
        "SELECT COUNT(*) FROM categories WHERE name LIKE 'QAT-m-%'"
    )[0][0] == 0

    result = run_migration()
    assert result.returncode == 0, f"миграция упала: {result.stdout} {result.stderr}"

    conn = sqlite3.connect(db_path)
    try:
        migrated = [row[0] for row in conn.execute(
            "SELECT name FROM categories WHERE name LIKE 'QAT-m-%'"
        ).fetchall()]
    finally:
        conn.close()
    assert sorted(migrated) == sorted(MIGR_CATEGORIES)


@pytest.mark.must
def test_migration_tasks_keep_category_values(migr_temp_db):
    """TC-migr-002: задача QAT-m-носитель с category=QAT-m-work после
    миграции сохраняет значение (посимвольно); значение присутствует в
    справочнике (не «осиротевший» текст) — FR-22. Значение читается из
    временной БД по id носителя (шаг 3 кейса)."""
    db_path, run_migration, execute = migr_temp_db
    execute(
        "INSERT INTO tasks (title, category, status, is_fast, created_at, updated_at) "
        "VALUES ('QAT-m-носитель','QAT-m-work','todo',0,datetime('now'),datetime('now'))"
    )
    task_id = execute(
        "SELECT id FROM tasks WHERE title = 'QAT-m-носитель'"
    )[0][0]

    result = run_migration()
    assert result.returncode == 0, f"миграция упала: {result.stdout} {result.stderr}"

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT category FROM tasks WHERE id = ?", (task_id,)).fetchone()
        in_directory = conn.execute(
            "SELECT COUNT(*) FROM categories WHERE name = 'QAT-m-work'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert row[0] == "QAT-m-work"
    assert in_directory == 1


@pytest.mark.must
def test_migration_empty_values_create_no_records(migr_temp_db):
    """TC-migr-003: задачи с NULL и '' не создают записей справочника
    (INSERT DISTINCT непустых — sdd r2 §5); после миграции остались без
    категории, задача с QAT-m-home — со своей."""
    db_path, run_migration, execute = migr_temp_db
    execute(
        "INSERT INTO tasks (title, category, status, is_fast, created_at, updated_at) "
        "VALUES ('QAT-m-null',NULL,'todo',0,datetime('now'),datetime('now')), "
        "('QAT-m-пустая','','todo',0,datetime('now'),datetime('now')), "
        "('QAT-m-с-дом','QAT-m-home','todo',0,datetime('now'),datetime('now'))"
    )
    assert execute(
        "SELECT COUNT(*) FROM tasks WHERE category IS NULL OR category = ''"
    )[0][0] >= 2

    result = run_migration()
    assert result.returncode == 0, f"миграция упала: {result.stdout} {result.stderr}"

    conn = sqlite3.connect(db_path)
    try:
        empty_like = conn.execute(
            "SELECT COUNT(*) FROM categories WHERE name IS NULL OR TRIM(name) = ''"
        ).fetchone()[0]
        null_task = conn.execute(
            "SELECT category FROM tasks WHERE title = 'QAT-m-null'"
        ).fetchone()[0]
        blank_task = conn.execute(
            "SELECT category FROM tasks WHERE title = 'QAT-m-пустая'"
        ).fetchone()[0]
        home_task = conn.execute(
            "SELECT category FROM tasks WHERE title = 'QAT-m-с-дом'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert empty_like == 0
    assert null_task is None
    assert blank_task in (None, "")
    assert home_task == "QAT-m-home"


@pytest.mark.must
def test_migration_all_nonempty_categories_valid(migr_temp_db):
    """TC-migr-004: после миграции каждое непустое category каждой задачи
    (включая архивные) присутствует в справочнике — 0 нарушений (FR-21 не
    нарушен ни для одной существующей задачи). Сверка — SQL-скрипт шага 4."""
    db_path, run_migration, execute = migr_temp_db
    execute(
        "INSERT INTO tasks (title, category, status, is_fast, created_at, updated_at) "
        "VALUES ('QAT-m-з1','QAT-m-home','todo',0,datetime('now'),datetime('now')), "
        "('QAT-m-з2','QAT-m-Home','todo',0,datetime('now'),datetime('now')), "
        "('QAT-m-з3','QAT-m-work','todo',0,datetime('now'),datetime('now'))"
    )
    result = run_migration()
    assert result.returncode == 0, f"миграция упала: {result.stdout} {result.stderr}"

    conn = sqlite3.connect(db_path)
    try:
        violations = conn.execute(
            "SELECT COUNT(*) FROM tasks t "
            "WHERE t.category IS NOT NULL AND t.category <> '' "
            "AND NOT EXISTS (SELECT 1 FROM categories c WHERE c.name = t.category)"
        ).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        nonempty = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE category IS NOT NULL AND category <> ''"
        ).fetchone()[0]
    finally:
        conn.close()
    assert violations == 0, f"нарушений сверки: {violations} (задач {total}, непустых {nonempty})"


@pytest.mark.must
def test_migration_zero_loss_snapshot_verification(migr_temp_db, verify_snapshot_dir):
    """TC-migr-005 (NFR-8): снимок «до» (CSV: id,category всех задач; число
    уникальных непустых U; число fast-нарушителей F_bad_before) → миграция →
    снимок «после»: CSV идентичны построчно; COUNT(categories) == U (+ не
    было категорий до миграции — справочник чистой копии пуст); все fast
    приведены к high (F_bad_after == 0)."""
    db_path, run_migration, execute = migr_temp_db
    execute(
        "INSERT INTO tasks (title, category, status, is_fast, priority, created_at, updated_at) "
        "VALUES ('QAT-m-з1','QAT-m-home','todo',0,NULL,datetime('now'),datetime('now')), "
        "('QAT-m-з2','QAT-m-Home','todo',0,NULL,datetime('now'),datetime('now')), "
        "('QAT-m-з3','QAT-m-work','todo',0,NULL,datetime('now'),datetime('now')), "
        "('QAT-m-фаст','QAT-m-work','todo',1,'low',datetime('now'),datetime('now'))"
    )
    # справочник копии пуст ДО миграции (шаг 1 кейса: C_seed зафиксирован)
    assert execute("SELECT COUNT(*) FROM categories")[0][0] == 0

    def write_snapshot(path: str) -> None:
        rows = execute("SELECT id, category FROM tasks ORDER BY id")
        with open(path, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "category"])
            writer.writerows(rows)

    before_csv = os.path.join(verify_snapshot_dir, "snapshot_tasks_before.csv")
    write_snapshot(before_csv)
    unique_before = execute(
        "SELECT COUNT(DISTINCT category) FROM tasks "
        "WHERE category IS NOT NULL AND category <> ''"
    )[0][0]
    f_bad_before = execute(
        "SELECT COUNT(*) FROM tasks WHERE is_fast = 1 AND priority != 'high'"
    )[0][0]

    result = run_migration()
    assert result.returncode == 0, f"миграция упала: {result.stdout} {result.stderr}"

    after_csv = os.path.join(verify_snapshot_dir, "snapshot_tasks_after.csv")
    write_snapshot(after_csv)
    with open(before_csv) as handle:
        before_rows = list(csv.reader(handle))
    with open(after_csv) as handle:
        after_rows = list(csv.reader(handle))
    assert before_rows == after_rows, "значения категорий задач изменились миграцией"

    c_total = execute("SELECT COUNT(*) FROM categories")[0][0]
    f_bad_after = execute(
        "SELECT COUNT(*) FROM tasks WHERE is_fast = 1 AND priority != 'high'"
    )[0][0]
    assert c_total == unique_before, f"COUNT(categories)={c_total} != U={unique_before}"
    assert f_bad_after == 0, f"fast-нарушителей после миграции: {f_bad_after} (до: {f_bad_before})"
    assert f_bad_before >= 1, "в снимке «до» должен быть нарушитель инварианта fast"


@pytest.mark.must
def test_migration_mismatch_fails_verification(migr_temp_db):
    """TC-migr-006 (негатив NFR-8): подставленное расхождение (UPDATE задачи
    на QAT-m-призрак после миграции) → автосверка фиксирует провал — exit 1
    и FAIL-строка с призраком в stdout; внедрение не завершено (идемпотентная
    цепочка: штатная миграция → расхождение → повторная сверка FAIL)."""
    db_path, run_migration, execute = migr_temp_db
    execute(
        "INSERT INTO tasks (title, category, status, is_fast, created_at, updated_at) "
        "VALUES ('QAT-m-носитель','QAT-m-work','todo',0,datetime('now'),datetime('now'))"
    )
    first = run_migration()
    assert first.returncode == 0, f"штатная миграция упала: {first.stdout} {first.stderr}"

    # моделируем расхождение (шаг 2 кейса)
    execute(
        "UPDATE tasks SET category = 'QAT-m-призрак' WHERE title = 'QAT-m-носитель'"
    )
    verify = run_migration()
    assert verify.returncode == 1, (
        f"сверка не зафиксировала провал (exit {verify.returncode}): {verify.stdout}"
    )
    assert "ПРОВАЛ" in verify.stdout
    assert "QAT-m-призрак" in verify.stdout or "отсутствующей в справочнике" in verify.stdout
