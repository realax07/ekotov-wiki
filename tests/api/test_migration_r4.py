"""Домен migr-r4 (Релиз 4): миграция users/tasks (tasks.md 1.1; FR-36,
FR-37, FR-38, NFR-9, ОВ-21, ОВ-23; design.md пакета §1, sdd r10 §3.1a-ter).

Скрипт `python -m app.migrate_r4` (backend/app/migrate_r4.py):
ALTER users (+display_name, +role, +bio, +avatar_path, +avatar_updated_at)
и tasks (+creator_id, +assigned_to_id, индексы) → бэкфилл creator=owner
(FR-38), assigned=owner (ОВ-23), роли owner→PM, wife→PE (ОВ-21) →
автосверка до/после (NFR-9; расхождение = exit 1).

Прогоны — на ВРЕМЕННОЙ копии БД стенда в scratch (fixture ``r4_temp_db``,
conftest: sqlite3.Connection.backup со sweet-файлами WAL); прод не трогается
(NFR-5, зона задачи 1.1). Кейсы:
1. свежая БД → все колонки уже в SCHEMA_SQL, миграция no-op-сверка зеленая;
2. БД до Р4 → бэкфилл creator=owner (FR-38), assigned=owner (ОВ-23);
3. БД до Р4 → роли owner→PM, wife→PE (ОВ-21);
4. снимок NFR-9: прежние поля задач/логины/хеши не изменились;
5. повторный запуск — no-op (сценарий «Идемпотентность миграции»);
6. FK-целостность: PRAGMA foreign_key_check пуст после бэкфилла;
7. негатив: «owner» удален → FAIL до commit, БД не изменена.
"""

import os
import sqlite3
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.api]

BACKEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "backend",
)
PYTHON_ENV = os.environ.get("R2QA_PYTHON", sys.executable)

OWNER_LOGIN = "owner"
WIFE_LOGIN = "wife"

USERS_COLUMNS = (
    "display_name",
    "role",
    "bio",
    "avatar_path",
    "avatar_updated_at",
)
TASKS_COLUMNS = ("creator_id", "assigned_to_id")


def _table_columns(db_path: str, table: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    finally:
        conn.close()


def _run_migrate_r4(db_path: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DB_PATH"] = db_path
    env["SECRET_KEY"] = env.get("SECRET_KEY", "qa-migration-secret")
    env.pop("EKOTOV_WIKI_DB_PATH", None)
    return subprocess.run(
        [PYTHON_ENV, "-m", "app.migrate_r4"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture
def r4_tmp_db(tmp_path):
    """Свежая БД по SCHEMA_SQL (прод не трогается: файл в tmp_path/scratch)."""
    db_path = str(tmp_path / "r4_fresh.db")
    env = dict(os.environ)
    env["DB_PATH"] = db_path
    env["SECRET_KEY"] = env.get("SECRET_KEY", "qa-migration-secret")
    env.pop("EKOTOV_WIKI_DB_PATH", None)
    proc = subprocess.run(
        [PYTHON_ENV, "-m", "app.db"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"python -m app.db упал: {proc.stdout} {proc.stderr}"
    return db_path


@pytest.fixture
def r4_pre_release_db(r4_tmp_db):
    """БД в редакции ДО Релиза 4: схема без колонок Р4 (колонки удаляются
    пересозданием таблиц — SQLite ALTER DROP не гарантирует до 3.35; данные
    копируются), пользователи owner/wife + задачи в разных статусах."""
    db_path = r4_tmp_db
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE users_old (
              id INTEGER PRIMARY KEY,
              login TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL
            );
            INSERT INTO users_old (id, login, password_hash) VALUES
              (1, 'owner', '$2b$12$QATpreReleaseOwnerHashPlaceholder00000000000000000000'),
              (2, 'wife',  '$2b$12$QATpreReleaseWifeHashPlaceholder000000000000000000000');
            CREATE TABLE tasks_old (
              id INTEGER PRIMARY KEY,
              title TEXT NOT NULL,
              description TEXT,
              priority TEXT CHECK(priority IN ('low','medium','high') OR priority IS NULL),
              category TEXT,
              due_date TEXT,
              is_fast INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'todo'
                CHECK(status IN ('todo','in_progress','done')),
              done_at TEXT,
              archived_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            INSERT INTO tasks_old
              (id, title, description, priority, category, due_date, is_fast,
               status, done_at, archived_at, created_at, updated_at)
            VALUES
              (1, 'QAT-r4-активная', 'desc1', 'high', 'дом', '2026-10-01', 0,
               'todo', NULL, NULL, '2026-09-01T10:00:00+00:00', '2026-09-01T10:00:00+00:00'),
              (2, 'QAT-r4-фаст', NULL, 'high', NULL, NULL, 1,
               'in_progress', NULL, NULL, '2026-09-02T10:00:00+00:00', '2026-09-02T10:00:00+00:00'),
              (3, 'QAT-r4-done', 'desc3', 'medium', 'работа', NULL, 0,
               'done', '2026-09-20T15:00:00+03:00', NULL,
               '2026-09-03T10:00:00+00:00', '2026-09-20T15:00:00+03:00'),
              (4, 'QAT-r4-архив', NULL, 'low', NULL, NULL, 0,
               'done', '2026-09-10T15:00:00+03:00', '2026-09-11T00:00:00+00:00',
               '2026-09-04T10:00:00+00:00', '2026-09-10T15:00:00+03:00');
            DROP TABLE tasks;
            DROP TABLE users;
            ALTER TABLE tasks_old RENAME TO tasks;
            ALTER TABLE users_old RENAME TO users;
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def _execute(db_path: str, sql: str, params: tuple = ()) -> list:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(sql, params).fetchall()
        conn.commit()
        return rows
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Кейс 1: свежая БД → все колонки (SCHEMA_SQL), миграция зеленая.
# ---------------------------------------------------------------------------


@pytest.mark.must
def test_r4_fresh_db_has_all_columns(r4_tmp_db):
    """Свежая БД: SCHEMA_SQL создает все колонки Р4; миграция проходит
    (сверка NFR-9 зеленая, ALTER-ов не требуется)."""
    users_cols = _table_columns(r4_tmp_db, "users")
    tasks_cols = _table_columns(r4_tmp_db, "tasks")
    for col in USERS_COLUMNS:
        assert col in users_cols, f"users.{col} нет в SCHEMA_SQL"
    for col in TASKS_COLUMNS:
        assert col in tasks_cols, f"tasks.{col} нет в SCHEMA_SQL"

    result = _run_migrate_r4(r4_tmp_db)
    assert result.returncode == 0, f"миграция упала: {result.stdout} {result.stderr}"
    assert "ОК" in result.stdout


@pytest.mark.must
def test_r4_fresh_db_indexes(r4_tmp_db):
    """Индексы FR-46 созданы (SCHEMA_SQL; после миграции — тоже)."""
    names = [
        row[0]
        for row in _execute(
            r4_tmp_db,
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'",
        )
    ]
    assert "idx_tasks_creator_id" in names
    assert "idx_tasks_assigned_to_id" in names


# ---------------------------------------------------------------------------
# Кейсы 2–4: БД до Р4 → бэкфилл.
# ---------------------------------------------------------------------------


@pytest.mark.must
def test_r4_pre_release_backfill_creator_and_assigned(r4_pre_release_db):
    """БД до Р4 (FR-38, ОВ-23): после миграции у КАЖДОЙ задачи (100%,
    включая fast/done/архивные) creator = owner и assigned = owner."""
    db_path = r4_pre_release_db
    owner_id = _execute(db_path, "SELECT id FROM users WHERE login = 'owner'")[0][0]

    result = _run_migrate_r4(db_path)
    assert result.returncode == 0, f"миграция упала: {result.stdout} {result.stderr}"

    rows = _execute(
        db_path, "SELECT id, creator_id, assigned_to_id FROM tasks ORDER BY id"
    )
    assert len(rows) == 4, "предусловие: 4 задачи редакции до Р4"
    for task_id, creator_id, assigned_id in rows:
        assert creator_id == owner_id, f"задача {task_id}: creator != owner (FR-38)"
        assert assigned_id == owner_id, f"задача {task_id}: assigned != owner (ОВ-23)"


@pytest.mark.must
def test_r4_pre_release_default_roles(r4_pre_release_db):
    """БД до Р4 (ОВ-21): owner → 'Product manager', wife → 'Product engineer'."""
    db_path = r4_pre_release_db
    result = _run_migrate_r4(db_path)
    assert result.returncode == 0, f"миграция упала: {result.stdout} {result.stderr}"

    roles = dict(_execute(db_path, "SELECT login, role FROM users"))
    assert roles["owner"] == "Product manager"
    assert roles["wife"] == "Product engineer"


@pytest.mark.must
def test_r4_snapshot_zero_loss(r4_pre_release_db):
    """NFR-9: прежние поля всех задач, логины и хеши паролей не изменились
    миграцией (снимок «до» = «после»); вход-данные не потеряны."""
    db_path = r4_pre_release_db
    pre_cols = [
        c
        for c in _table_columns(db_path, "tasks")
        if c not in TASKS_COLUMNS
    ]
    tasks_before = {
        row[0]: tuple(row)
        for row in _execute(
            db_path, f"SELECT {', '.join(pre_cols)} FROM tasks ORDER BY id"
        )
    }
    users_before = dict(
        _execute(db_path, "SELECT id, login || '|' || password_hash FROM users")
    )

    result = _run_migrate_r4(db_path)
    assert result.returncode == 0, f"миграция упала: {result.stdout} {result.stderr}"

    tasks_after = {
        row[0]: tuple(row)
        for row in _execute(
            db_path, f"SELECT {', '.join(pre_cols)} FROM tasks ORDER BY id"
        )
    }
    assert tasks_after == tasks_before, "прежние поля задач изменились миграцией"
    users_after = dict(
        _execute(db_path, "SELECT id, login || '|' || password_hash FROM users")
    )
    assert users_after == users_before, "логины/хеши паролей изменились миграцией"


@pytest.mark.must
def test_r4_foreign_key_check_empty(r4_pre_release_db):
    """FK-целостность (design.md §1, п.6 ТЗ): после бэкфилла
    PRAGMA foreign_key_check пуст."""
    db_path = r4_pre_release_db
    result = _run_migrate_r4(db_path)
    assert result.returncode == 0, f"миграция упала: {result.stdout} {result.stderr}"
    violations = _execute(db_path, "PRAGMA foreign_key_check")
    assert violations == [], f"foreign_key_check не пуст: {violations}"


# ---------------------------------------------------------------------------
# Кейс 5: идемпотентность — повторный запуск no-op.
# ---------------------------------------------------------------------------


@pytest.mark.must
def test_r4_rerun_is_noop(r4_pre_release_db):
    """Повторный запуск (сценарий «Идемпотентность миграции»): значения
    creator/assigned/ролей и прежних полей не меняются, exit 0.
    no-op проверяется по состоянию БД (review-001-1.1, R-5а: не по
    человекочитаемому stdout) — creator/assigned остаются owner у всех,
    счетчик измененных строк = 0."""
    db_path = r4_pre_release_db
    first = _run_migrate_r4(db_path)
    assert first.returncode == 0, f"первый прогон упал: {first.stdout} {first.stderr}"

    tasks_before = _execute(
        db_path,
        "SELECT id, title, creator_id, assigned_to_id FROM tasks ORDER BY id",
    )
    roles_before = _execute(db_path, "SELECT id, login, role FROM users ORDER BY id")

    second = _run_migrate_r4(db_path)
    assert second.returncode == 0, f"повторный прогон упал: {second.stdout} {second.stderr}"

    # no-op по состоянию БД (R-5а): все задачи по-прежнему creator=assigned=owner,
    # метки r4_backfill проставлены всем и не перезаписаны новым моментом.
    owner_id = _execute(db_path, "SELECT id FROM users WHERE login = 'owner'")[0][0]
    rows = _execute(
        db_path, "SELECT id, creator_id, assigned_to_id FROM tasks ORDER BY id"
    )
    assert len(rows) == 4
    for task_id, creator_id, assigned_id in rows:
        assert creator_id == owner_id, f"задача {task_id}: creator перезаписан повтором"
        assert assigned_id == owner_id, f"задача {task_id}: assigned перезаписан повтором"
    marks = _execute(
        db_path, "SELECT COUNT(DISTINCT r4_backfill) FROM tasks WHERE r4_backfill IS NOT NULL"
    )[0][0]
    assert marks == 1, f"метка r4_backfill должна быть одна (фактически {marks} разных)"

    assert (
        _execute(
            db_path,
            "SELECT id, title, creator_id, assigned_to_id FROM tasks ORDER BY id",
        )
        == tasks_before
    ), "повторный запуск изменил creator/assigned"
    assert (
        _execute(db_path, "SELECT id, login, role FROM users ORDER BY id")
        == roles_before
    ), "повторный запуск изменил роли"


# ---------------------------------------------------------------------------
# Кейс 6b (review-001-1.1, R-5б): «owner» отсутствует при ПУСТОМ tasks —
# допустимый путь owner_id=None: бэкфиллить некого и нечего, миграция
# завершается успешно (exit 0), роли не проставляются (некому).
# ---------------------------------------------------------------------------


@pytest.mark.must
def test_r4_owner_missing_empty_tasks_ok(r4_tmp_db):
    """Свежая БД без задач и без пользователя «owner» (допустимая ветка
    owner_id=None в _backfill): миграция проходит, exit 0, сверка зеленая,
    задач не появляется."""
    db_path = r4_tmp_db
    _execute(db_path, "DELETE FROM users WHERE login = 'owner'")
    assert _execute(db_path, "SELECT COUNT(*) FROM tasks")[0][0] == 0
    assert _execute(db_path, "SELECT COUNT(*) FROM users WHERE login = 'owner'")[0][0] == 0

    result = _run_migrate_r4(db_path)
    assert result.returncode == 0, (
        f"ветка owner_id=None должна проходить: {result.stdout} {result.stderr}"
    )
    assert "ОК" in result.stdout
    assert _execute(db_path, "SELECT COUNT(*) FROM tasks")[0][0] == 0


# ---------------------------------------------------------------------------
# Кейс 7: негатив — «owner» отсутствует при непустых tasks.
# ---------------------------------------------------------------------------


@pytest.mark.must
def test_r4_negative_owner_missing_fails_without_changes(r4_pre_release_db):
    """Негатив (NFR-9): «owner» удален → бэкфилл FR-38 невыполним;
    миграция завершается exit 1 с FAIL, БД НЕ изменяется (откат транзакции):
    колонок Р4 нет, прежние данные нетронуты."""
    db_path = r4_pre_release_db
    _execute(db_path, "DELETE FROM users WHERE login = 'owner'")

    result = _run_migrate_r4(db_path)
    assert result.returncode == 1, f"ожидался провал: {result.stdout} {result.stderr}"
    assert "FAIL" in result.stdout
    assert "owner" in result.stdout

    # БД не изменена: ALTER не применились (колонок Р4 нет), данные целы.
    users_cols = _table_columns(db_path, "users")
    for col in USERS_COLUMNS:
        assert col not in users_cols, f"{col} добавлен вопреки провалу — откат не сработал"
    tasks_cols = _table_columns(db_path, "tasks")
    for col in TASKS_COLUMNS:
        assert col not in tasks_cols, f"{col} добавлен вопреки провалу — откат не сработал"
    rows = _execute(db_path, "SELECT id, title FROM tasks ORDER BY id")
    assert len(rows) == 4 and rows[0][1] == "QAT-r4-активная"


# ---------------------------------------------------------------------------
# Кейс 8 (негатив NFR-9): расхождение сверки — exit 1 (образец TC-migr-006).
# ---------------------------------------------------------------------------


@pytest.mark.must
def test_r4_verification_mismatch_fails(r4_pre_release_db):
    """Негатив (NFR-9, образец TC-migr-006): после миграции в БД появилась
    задача с creator_id IS NULL (аномалия — после релиза creator ставит
    сервер, design §1: сверка (в) = 0 безусловно) → повторный запуск
    фиксирует расхождение: exit 1, FAIL-строка в stdout; значения
    существующих задач при этом не искажены."""
    db_path = r4_pre_release_db
    first = _run_migrate_r4(db_path)
    assert first.returncode == 0, f"штатная миграция упала: {first.stdout} {first.stderr}"

    # симулируем аномалию: задача без creator (вне прикладного слоя, direct SQL)
    _execute(
        db_path,
        "INSERT INTO tasks (title, status, is_fast, created_at, updated_at) "
        "VALUES ('QAT-r4-аномалия', 'todo', 0, datetime('now'), datetime('now'))",
    )
    second = _run_migrate_r4(db_path)
    assert second.returncode == 1, (
        f"сверка не зафиксировала провал (exit {second.returncode}): {second.stdout}"
    )
    assert "ПРОВАЛ" in second.stdout
    assert "creator_id IS NULL" in second.stdout

    # значения существующих задач повторным запуском не искажены (NFR-9)
    rows = _execute(
        db_path, "SELECT id, title, creator_id, assigned_to_id FROM tasks ORDER BY id"
    )
    assert len(rows) == 5
    for task_id, _title, creator_id, assigned_id in rows[:4]:
        assert creator_id is not None and assigned_id is not None
