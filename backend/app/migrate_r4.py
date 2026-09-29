"""Миграция схемы Релиза 4: профиль пользователя + creator/assigned задач
(tasks.md 1.1; design.md пакета §1; sdd r10 §3.1a-ter, §4; FR-36, FR-37,
FR-38, NFR-9, ОВ-21, ОВ-23).

Одноразовый идемпотентный скрипт внедрения Релиза 4 (ОГР-19) — по образцу
`migrate_categories.py` (Релиз 2, NFR-8). Запуск из каталога backend/
(DB_PATH/SECRET_KEY из окружения, как у python -m app.db):

    DB_PATH=/path/to/wiki.db SECRET_KEY=x python -m app.migrate_r4

Шаги (design.md §1):
1. Снимок «до»: все поля всех задач + логины/хеши паролей пользователей
   (для сверки NFR-9 «0 потерь»).
2. ALTER users: + display_name, + role, + bio, + avatar_path,
   + avatar_updated_at — только при отсутствии колонки (PRAGMA
   table_info), как сделано для done_at в db.py. Для свежих БД колонки
   создает SCHEMA_SQL — здесь они не отсутствуют, шаг пропускается.
3. ALTER tasks: + creator_id INTEGER REFERENCES users(id),
   + assigned_to_id INTEGER REFERENCES users(id) — аналогично; плюс
   служебная колонка r4_backfill (метка первого наката, МСК — граница
   «существующие на момент накатки» для повторных прогонов; в контракты
   API не входит).
   Индексы tasks(creator_id), tasks(assigned_to_id) (фильтры поиска
   FR-46) — CREATE INDEX IF NOT EXISTS, применяется к обеим редакциям.
4. Бэкфилл (одна транзакция с ALTER, design.md §1):
   - tasks.creator_id = id пользователя «owner» у ВСЕХ задач (FR-38);
   - tasks.assigned_to_id = id «owner» у всех существующих задач
     (ОВ-23 — ни одна существующая задача не остается без исполнителя);
   - users.role: owner → 'Product manager', wife → 'Product engineer'
     (ОВ-21 — значения по умолчанию для существующих записей; guard
     `role IS NULL` — уже проставленная роль повторным запуском не
     перезаписывается);
   - пользователь «owner» отсутствует при непустом tasks → FAIL ДО
     commit: транзакция откатывается, БД не меняется (бэкфилл FR-38
     невыполним — внедрение не считается завершенным).
5. Автосверка «после» (NFR-9):
   (а) прежние поля всех задач = снимку «до» (0 измененных);
   (б) логины и хеши паролей пользователей = снимку (вход работает);
   (в) COUNT(tasks WHERE creator_id IS NULL) = 0 (FR-38, 100%);
   (г) ни одна задача из снимка не осталась без assigned (ОВ-23);
       NULL assigned допустим только у задач, созданных ПОСЛЕ миграции
       (на момент накатки их 0);
   (д) роли по умолчанию проставлены (ОВ-21);
   (е) PRAGMA foreign_key_check пуст (целостность ссылок на users).
   Расхождение → провал (exit 1), внедрение не завершено.

Идемпотентность: повторный запуск на уже смигрированной БД — ALTER
пропускается (колонки есть), бэкфилл не находит NULL-значений, роли
под guard'ом, сверка снова зеленая (сценарий «Идемпотентность миграции»).

Атомарность: ALTER и бэкфилл — ОДНА явная транзакция BEGIN IMMEDIATE
(прецедент migrate_categories.py, ревью 001 замечание 3): краш между
шагами не оставляет частично мигрированной БД.

Deploy (sdd §3.1a-ter, шаг «4b/6 миграция R4» — метка по M-1 ревью
review-002): шаг deploy.sh после схемы `python -m app.db`, СТРОГО до
рестарта; падение шага прерывает деплой, БД восстановима из бэкапа.
Миграция прода — строго после бэкапа БД + каталога аватаров (ОГР-19,
C-3 ревью). Остановка uvicorn не требуется: короткая транзакция
совместима с работающим SQLite WAL.

Выход: 0 — сверка зеленая; 1 — расхождение (внедрение не завершено).
Отчет сверки печатается в stdout — переносится в отчет задачи.
"""

import sqlite3
import sys

from app.config import settings
from app.db import get_connection

FAIL = 1

# Новые колонки Релиза 4 (design.md §1, sdd §4): таблица → (колонка, DDL).
NEW_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "users": (
        ("display_name", "ALTER TABLE users ADD COLUMN display_name TEXT"),
        ("role", "ALTER TABLE users ADD COLUMN role TEXT"),
        ("bio", "ALTER TABLE users ADD COLUMN bio TEXT"),
        ("avatar_path", "ALTER TABLE users ADD COLUMN avatar_path TEXT"),
        ("avatar_updated_at", "ALTER TABLE users ADD COLUMN avatar_updated_at TEXT"),
    ),
    "tasks": (
        (
            "creator_id",
            "ALTER TABLE tasks ADD COLUMN creator_id INTEGER REFERENCES users(id)",
        ),
        (
            "assigned_to_id",
            "ALTER TABLE tasks ADD COLUMN assigned_to_id INTEGER REFERENCES users(id)",
        ),
        # Служебная метка первого наката (tasks.md 1.1, внутренняя): момент
        # миграции (МСК) — граница «существующие на момент накатки» для
        # повторных прогонов; после задачи 5.1 (creator ставит сервер)
        # не бэкфиллятся повторным запуском. Не входит в контракты API.
        (
            "r4_backfill",
            "ALTER TABLE tasks ADD COLUMN r4_backfill TEXT",
        ),
    ),
}

# Индексы фильтров поиска FR-46 (design.md §1; те же, что в SCHEMA_SQL —
# IF NOT EXISTS, применяются к обеим редакциям БД).
INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_tasks_creator_id ON tasks(creator_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to_id ON tasks(assigned_to_id)",
)

# Бэкфилл ролей существующих пользователей (ОВ-21): логин → роль по умолчанию.
DEFAULT_ROLES = {"owner": "Product manager", "wife": "Product engineer"}

OWNER_LOGIN = "owner"


def _msk_now_iso() -> str:
    """Текущий момент по МСК (UTC+3, sdd §3.3) в ISO — значение метки
    r4_backfill (граница «существующие на момент накатки»)."""
    from datetime import datetime, timedelta, timezone

    MSK = timezone(timedelta(hours=3))
    return datetime.now(MSK).isoformat()


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Имена колонок таблицы по порядку (PRAGMA table_info)."""
    return [
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    ]


def _snapshot_tasks(conn: sqlite3.Connection) -> dict[int, tuple]:
    """Снимок «до»: все поля всех задач (по именам колонок текущей схемы)."""
    columns = _table_columns(conn, "tasks")
    rows = conn.execute(
        f"SELECT {', '.join(columns)} FROM tasks ORDER BY id"
    ).fetchall()
    return {row[0]: tuple(row) for row in rows}


def _snapshot_users(conn: sqlite3.Connection) -> dict[int, tuple[str, str]]:
    """Снимок «до»: id → (login, password_hash) всех пользователей."""
    return {
        row[0]: (row[1], row[2])
        for row in conn.execute(
            "SELECT id, login, password_hash FROM users ORDER BY id"
        ).fetchall()
    }


def _add_missing_columns(conn: sqlite3.Connection) -> list[str]:
    """Шаги 2–3: ALTER только при отсутствии колонки (образец done_at,
    db.py). Выполняется ВНУТРИ открытой транзакции вызывающего кода.
    Возвращает список фактически выполненных ALTER."""
    applied: list[str] = []
    for table, columns in NEW_COLUMNS.items():
        existing = set(_table_columns(conn, table))
        if not existing:
            # Таблицы нет — сначала примените схему (python -m app.db);
            # миграция таблицы не создает (как migrate_categories).
            raise RuntimeError(f"таблицы {table} нет — сначала примените схему")
        for name, ddl in columns:
            if name not in existing:
                conn.execute(ddl)
                applied.append(f"{table}.{name}")
    return applied


def _backfill(conn: sqlite3.Connection, first_run: bool) -> dict[str, int]:
    """Шаг 4: бэкфилл в открытой транзакции (FR-38, ОВ-23, ОВ-21).

    ``first_run`` — True, если creator_id добавлен этим запуском (первый
    накат): бэкфиллятся ВСЕ задачи — они все «существующие на момент
    накатки» (FR-38, ОВ-23) и получают метку r4_backfill. Повторный
    запуск (first_run=False): бэкфиллятся только помеченные задачи
    (метка = существовала при накатке; у них creator/assigned не могут
    быть NULL после первого прогона — защита от ручных правок), задачи
    без метки созданы ПОСЛЕ миграции и не трогаются — их NULL-creator
    (аномалия вне прикладного слоя) ловит автосверка (в) → exit 1."""
    owner = conn.execute(
        "SELECT id FROM users WHERE login = ?", (OWNER_LOGIN,)
    ).fetchone()
    if owner is None:
        has_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if has_tasks:
            # Бэкфилл FR-38 невыполним — откат транзакции вызывающим кодом,
            # БД остается в исходном состоянии (негативный сценарий NFR-9).
            raise RuntimeError(
                f"пользователь '{OWNER_LOGIN}' не найден — бэкфилл "
                "creator/assigned (FR-38, ОВ-23) невыполним"
            )
        owner_id = None  # свежая БД без задач: бэкфillить некого и нечего
    else:
        owner_id = owner[0]

    stats: dict[str, int] = {"columns_altered": 0}
    if owner_id is not None:
        scope = "r4_backfill IS NOT NULL AND created_at <= r4_backfill"
        if first_run:
            scope = "1"  # первый накат: существующие = все задачи
        cur = conn.execute(
            f"UPDATE tasks SET creator_id = ? "
            f"WHERE creator_id IS NULL AND ({scope})",
            (owner_id,),
        )
        stats["creator_backfilled"] = cur.rowcount
        # ОВ-23: assigned = owner у всех существующих; позже созданные с
        # NULL assigned — валидны (FR-37: nullable).
        cur = conn.execute(
            f"UPDATE tasks SET assigned_to_id = ? "
            f"WHERE assigned_to_id IS NULL AND ({scope})",
            (owner_id,),
        )
        stats["assigned_backfilled"] = cur.rowcount
        if first_run:
            # Метка первого наката (момент миграции, МСК) — граница
            # «существующие на момент накатки» для повторных прогонов.
            conn.execute(
                "UPDATE tasks SET r4_backfill = ? WHERE r4_backfill IS NULL",
                (_msk_now_iso(),),
            )
    else:
        stats["creator_backfilled"] = 0
        stats["assigned_backfilled"] = 0

    stats["roles_set"] = 0
    for login, role in DEFAULT_ROLES.items():
        cur = conn.execute(
            "UPDATE users SET role = ? WHERE login = ? AND role IS NULL",
            (role, login),
        )
        stats["roles_set"] += cur.rowcount
    return stats


def _verify_after(
    conn: sqlite3.Connection,
    tasks_before: dict[int, tuple],
    users_before: dict[int, tuple[str, str]],
    task_columns_before: list[str],
) -> list[str]:
    """Шаг 5: автосверка «после» (NFR-9). Возвращает список расхождений
    (пустой = сверка зеленая)."""
    mismatches: list[str] = []

    # (а) прежние поля задач = снимку (0 измененных; новые колонки не смотрим).
    rows_after = conn.execute(
        f"SELECT {', '.join(task_columns_before)} FROM tasks ORDER BY id"
    ).fetchall()
    after = {row[0]: tuple(row) for row in rows_after}
    changed = [tid for tid, before in tasks_before.items() if after.get(tid) != before]
    lost = [tid for tid in after if tid not in tasks_before]
    if changed:
        mismatches.append(
            f"FAIL: изменены прежние поля задач: {sorted(changed)[:10]}"
        )
    if lost:
        mismatches.append(f"FAIL: задачи исчезли после миграции: {sorted(lost)[:10]}")

    # (б) логины и хеши паролей = снимку (вход работает, NFR-9).
    users_after = _snapshot_users(conn)
    for user_id, before in users_before.items():
        if users_after.get(user_id) != before:
            mismatches.append(
                f"FAIL: пользователь id={user_id} изменился "
                "(логин/хеш пароля не совпадают со снимком)"
            )

    # (в) creator заполнен у 100% задач (FR-38).
    null_creator = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE creator_id IS NULL"
    ).fetchone()[0]
    if null_creator:
        mismatches.append(
            f"FAIL: задач с creator_id IS NULL: {null_creator} (ожидалось 0, FR-38)"
        )

    # (г) ни одна СУЩЕСТВОВАВШАЯ на момент накатки задача не осталась без
    # assigned (ОВ-23). Граница — метка r4_backfill (первый прогон): задачи
    # с меткой существовали при накатке и обязаны иметь assigned = owner;
    # без метки — созданы после миграции, NULL assigned валиден (FR-37).
    null_assigned_marked = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE assigned_to_id IS NULL "
        "AND r4_backfill IS NOT NULL"
    ).fetchone()[0]
    if null_assigned_marked:
        mismatches.append(
            f"FAIL: существующих на момент накатки задач с assigned_to_id "
            f"IS NULL: {null_assigned_marked} (ОВ-23: бэкфилл = owner)"
        )

    # (д) роли по умолчанию проставлены (ОВ-21) — для существующих логинов.
    for login, role in DEFAULT_ROLES.items():
        row = conn.execute(
            "SELECT role FROM users WHERE login = ?", (login,)
        ).fetchone()
        if row is not None and row[0] != role:
            mismatches.append(
                f"FAIL: роль '{login}' = {row[0]!r}, ожидалось {role!r} (ОВ-21)"
            )

    # (е) FK-целостность ссылок на users после бэкфилла.
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        mismatches.append(
            f"FAIL: PRAGMA foreign_key_check не пуст: {fk_violations[:5]}"
        )

    return mismatches


def main() -> int:
    conn: sqlite3.Connection = get_connection()
    try:
        print("=== Миграция Релиза 4: users/tasks (tasks.md 1.1, FR-36…38/NFR-9) ===")
        print(f"БД: {settings.db_path}")

        # Шаг 1: снимок «до».
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing = [t for t in ("users", "tasks") if t not in tables]
        if missing:
            print(
                f"FAIL: таблиц(ы) {missing} нет — сначала примените схему "
                "(python -m app.db); миграция таблицы не создает."
            )
            return FAIL
        task_columns_before = _table_columns(conn, "tasks")
        tasks_before = _snapshot_tasks(conn)
        users_before = _snapshot_users(conn)
        print(
            f"До: задач={len(tasks_before)}, пользователей={len(users_before)}, "
            f"колонок tasks={len(task_columns_before)}"
        )

        # Шаги 2–4 — одна транзакция (атомарность, прецедент Р2).
        conn.execute("BEGIN IMMEDIATE")
        try:
            applied = _add_missing_columns(conn)
            print(f"ALTER выполнено: {len(applied)}: {', '.join(applied) or '—'}")
            for ddl in INDEXES_SQL:
                conn.execute(ddl)
            first_run = "tasks.creator_id" in applied
            stats = _backfill(conn, first_run)
            print(
                f"Бэкфилл: creator_id={stats['creator_backfilled']}, "
                f"assigned_to_id={stats['assigned_backfilled']}, "
                f"ролей проставлено={stats['roles_set']}"
            )
            conn.commit()
        except RuntimeError as exc:
            conn.rollback()
            print(f"FAIL: {exc} — транзакция откатана, БД не изменена.")
            return FAIL

        # Шаг 5: автосверка «после».
        mismatches = _verify_after(conn, tasks_before, users_before, task_columns_before)
        if mismatches:
            print("\n=== Сверка «после»: ПРОВАЛ (NFR-9) ===")
            for line in mismatches:
                print(line)
            print("Внедрение НЕ завершено: восстановите БД из бэкапа и повторите.")
            return FAIL

        print("\n=== Сверка «после»: ОК (NFR-9, 0 потерь) ===")
        print(
            f"Проверено: (а) прежние поля всех {len(tasks_before)} задач = снимку; "
            "(б) логины/хеши паролей не изменились; "
            "(в) creator_id заполнен у 100% задач (FR-38); "
            "(г) assigned_to_id = owner у всех существующих (ОВ-23); "
            "(д) роли owner/wife = PM/PE (ОВ-21); "
            "(е) PRAGMA foreign_key_check пуст."
        )
        print("Миграция Релиза 4 завершена.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
