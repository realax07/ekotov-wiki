"""CRUD задач: POST /api/tasks, GET/PATCH/DELETE /api/tasks/{id}
(tasks.md 4.1; sdd.md §3.2; домен tasks — Создание/Редактирование/Удаление,
Перемещение через API).

Контракты — дословно sdd.md §3.2:
- POST: обязателен title; остальные признаки опциональны; ответ 201 Task.
  Ошибки: 422 — нет названия. 409 {"error": "fast line occupied"} —
  is_fast=true при наличии активной (todo/in_progress) fast-задачи
  (задача 5.1; проверка + вставка — одна транзакция, design.md §4).
  Priority-lock (Релиз 2, 4.2; FR-27, ОГР-10): is_fast=true с явным
  priority ≠ high → 422 {"error": "validation", "details": {"priority":
  "fast requires high"}} (дословно sdd r2 §3.2); is_fast=true без
  priority → приоритет 'high'. PATCH: изменение priority существующей
  fast-задачи — тот же 422 (инвариант is_fast ⇒ high).
- GET: Task; 404 на несуществующий id.
- PATCH: частичное обновление — только переданные поля; 200 Task; ошибки 404, 422.
  status в PATCH не входит: статус меняется через POST /{id}/move (sdd §3.2),
  ручная простановка обошла бы archived_at (задача 4.4/6.1).
- POST /{id}/move: {"status": "todo|in_progress|done"}; 200 Task;
  при done — done_at проставлен (задача ОСТАЕТСЯ на доске в столбце
  «Выполнено», archived_at не ставится — sdd r5 §3.2); при обратном
  переводе из done снимаются ОБА (done_at, archived_at — NULL);
  ошибки 404, 422 (недопустимый статус). Ленивая автоархивация —
  GET /api/board (app/board.py, задача 6.1, design.md §5). Возврат
  fast-задачи из done в todo/in_progress проверяет инвариант fast ≤1
  (409, задача 5.1 — расширение сверх спеки fastline, дыра из
  review-4.4-001).
- DELETE: физическое удаление; каскады task_tags/comments — FK ON DELETE
  CASCADE (sdd §4), foreign_keys=ON включен в get_connection (app/db.py).

Task-объект — по схеме sdd §3.2 (id, title, description, priority, category,
due_date, tags, is_fast, status, archived_at; Релиз 4: + done_at, + creator,
+ assigned). Владельца у задачи нет — модель sdd §4 не имеет колонки user_id
в tasks (общая доска, sdd §7 допущения).

Релиз 4 (FR-37, ОВ-23/26; sdd r10 §3.2): ответы содержат creator и assigned —
логины (LEFT JOIN users). POST опционально принимает assigned_to_id
(существующий пользователь или null; несуществующий → 422), creator_id
ставит сервер = пользователю сессии и от клиента НЕ принимается
(TaskCreate extra="forbid" — creator_id в теле → 422). PATCH допускает
assigned_to_id (та же валидация; null = очистить исполнителя); creator_id
в контракте не входит — creator не изменяется. Базовый TASK_COLUMNS
не расширяется: search.py (задача 5.2) импортирует его для своей выборки.

Тела ошибок: 401 — middleware (app/middleware.py); 422 —
{"error", "details"} по sdd §3 (обработчик RequestValidationError,
install_error_handlers); 404 — {"error": "not found"} (sdd §3 фиксирует
только код).
"""

import sqlite3
from datetime import date, datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth import SESSION_COOKIE_NAME
from app.board import msk_now_iso
from app.categories import category_exists
from app.db import get_connection

router = APIRouter(prefix="/api/tasks")

# CHECK из схемы (sdd §4): priority IN ('low','medium','high') OR NULL.
Priority = Literal["low", "medium", "high"]

TASK_COLUMNS = (
    "id, title, description, priority, category, due_date, "
    "is_fast, status, done_at, archived_at"
)

NOT_FOUND_BODY = {"error": "not found"}

# Инвариант fast line ≤1 (FR-3, ОГР-5; design.md §4): в активных статусах
# (todo/in_progress — «Ожидает»/«В работе») не более одной fast-задачи.
# Тело 409 — дословно sdd.md §3.2.
FAST_LINE_OCCUPIED_BODY = {"error": "fast line occupied"}

# Активные статусы «Ожидает»/«В работе» (ОГР-3); done = архив, линию не занимает.
ACTIVE_STATUSES = ("todo", "in_progress")


# Тело 422 несуществующего исполнителя (Релиз 4, FR-37/ОВ-26) — в форме
# {"error": "validation", "details": {...}}, как остальные жесткие 422.
ASSIGNED_NOT_FOUND_422 = {
    "error": "validation",
    "details": {"assigned_to_id": "user not found"},
}


def _assigned_not_found_422() -> JSONResponse:
    return JSONResponse(status_code=422, content=ASSIGNED_NOT_FOUND_422)


def _user_exists(conn: sqlite3.Connection, user_id: int | None) -> bool:
    """Есть ли пользователь с таким id (валидация assigned_to_id, sdd §3.2)."""
    if user_id is None:
        return True  # null = «без исполнителя» — легально (FR-37 nullable)
    row = conn.execute(
        "SELECT 1 FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return row is not None


def _assigned_to_id_422(
    conn: sqlite3.Connection, body: Any
) -> JSONResponse | None:
    """Валидация assigned_to_id POST/PATCH (Релиз 4, FR-37, ОВ-26).

    Проверяется только если поле передано в теле; null = очистить
    исполнителя — легально; несуществующий пользователь → 422
    ASSIGNED_NOT_FOUND_422 (сценарий «Негативный: assigned — только
    существующий пользователь»). Проверка ДО любых записей — при 422
    задача не создается/не изменяется.
    """
    if "assigned_to_id" not in body.model_fields_set:
        return None
    if not _user_exists(conn, body.assigned_to_id):
        return _assigned_not_found_422()
    return None


def _session_user_id(request: Request) -> int | None:
    """id пользователя сессии (Релиз 4, FR-37: creator_id ставит сервер).

    Запрос уже прошел middleware (401 без сессии) — сессия валидна;
    токен без строки в sessions здесь практически невозможен, но
    None-возврат страховкой дает creator_id = NULL, а не падение.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT user_id FROM sessions WHERE token = ?", (token,)
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row is not None else None


def _begin_immediate(conn: sqlite3.Connection) -> None:
    """BEGIN IMMEDIATE: захват блокировки записи ДО проверочного SELECT.

    Иначе «проверка + запись» не одна транзакция: SELECT в autocommit не
    держит снапшот, два параллельных is_fast-POST оба видят 0 и оба
    вставляют (воспроизведено смоуком). С BEGIN IMMEDIATE второй запрос
    ждет блокировку и его проверка видит уже закоммиченную первую
    fast-задачу — инвариант детерминирован (design.md §4 «Гонки»).
    """
    conn.execute("BEGIN IMMEDIATE")


def _utcnow() -> str:
    """Момент now для updated_at/created_at (UTC, ...+00:00).

    Для КАЛЕНДАРНО-СРАВНИВАЕМОГО done_at не используется: он пишется
    через app.board.msk_now_iso (фиксированный UTC+3, тот же формат, что
    у границы дня в autoarchive — см. докстринг msk_now_iso).
    """
    return datetime.now(timezone.utc).isoformat()


class TaskCreate(BaseModel):
    """Тело POST /api/tasks: title обязателен, остальное опционально (sdd §3.2)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    priority: Priority | None = None
    category: str | None = None
    due_date: date | None = None  # YYYY-MM-DD (sdd §4); иное — 422
    tags: list[str] = Field(default_factory=list)
    is_fast: bool = False  # ручное назначение только при создании (ОГР-5)
    # Релиз 4 (FR-37, ОВ-26): опционально; null = без исполнителя;
    # несуществующий пользователь → 422 (проверка _assigned_to_id_422).
    assigned_to_id: int | None = None
    # creator_id от клиента НЕ принимается (FR-37): extra="forbid" дает
    # 422 (creator_id не входит в контракт создания); сервер ставит
    # creator_id = пользователю сессии (_session_user_id).

    @field_validator("title")
    @classmethod
    def _title_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be empty")
        return value


class TaskUpdate(BaseModel):
    """Тело PATCH /api/tasks/{id}: все поля опциональны, применяется только
    переданное (model_fields_set). status/is_fast/archived_at не входят
    (см. докстринг модуля)."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    priority: Priority | None = None  # None = очистить признак
    category: str | None = None
    due_date: date | None = None
    tags: list[str] | None = None
    # Релиз 4 (ОВ-26): допускается; null = очистить исполнителя;
    # несуществующий пользователь → 422 (_assigned_to_id_422).
    assigned_to_id: int | None = None
    # creator_id в контракте PATCH не входит (FR-37) — extra="forbid"
    # отклоняет его 422; creator задачи не изменяется никем.

    @field_validator("title")
    @classmethod
    def _title_not_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("title must not be empty")
        return value


class TaskMove(BaseModel):
    """Тело POST /api/tasks/{id}/move (sdd §3.2 дословно):
    {"status": "todo|in_progress|done"}; иное значение — 422."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["todo", "in_progress", "done"]


def _load_tags(conn: sqlite3.Connection, task_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT t.name FROM tags t "
        "JOIN task_tags tt ON tt.tag_id = t.id "
        "WHERE tt.task_id = ? ORDER BY t.id",
        (task_id,),
    ).fetchall()
    return [row[0] for row in rows]


def _task_with_users_sql(select_cols: str) -> str:
    """SELECT tasks-колонок с JOIN users (Релиз 4, sdd §3.2 дословно:
    creator/assigned в ответах — логины; LEFT JOIN — задача может быть
    без creator/assigned (NULL в схеме nullable). tasks.* первым —
    порядок колонок row соответствует TASK_COLUMNS/_row_to_task.
    Используется всеми чтениями задач этого модуля."""
    return (
        f"SELECT {select_cols} "
        "FROM tasks "
        "LEFT JOIN users creator ON creator.id = tasks.creator_id "
        "LEFT JOIN users assigned ON assigned.id = tasks.assigned_to_id "
    )


def _row_to_task(
    conn: sqlite3.Connection, row: tuple, users: tuple | None = None
) -> dict:
    """Строка tasks → Task-объект по схеме sdd §3.2 (r5: с done_at;
    Релиз 4: с creator/assigned — логины, sdd r10 §3.2).

    users — (creator_login, assigned_login) из JOIN; None (старый
    вызов без JOIN) → поля creator/assigned НЕ включаются (гвард
    hasOwnProperty в task-detail.js не оживит ряды без данных —
    данные не выдумываются)."""
    task = {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "priority": row[3],
        "category": row[4],
        "due_date": row[5],
        "tags": _load_tags(conn, row[0]),
        "is_fast": bool(row[6]),
        "status": row[7],
        "done_at": row[8],
        "archived_at": row[9],
    }
    if users is not None:
        task["creator"] = users[0]
        task["assigned"] = users[1]
    return task


def _get_task_row(conn: sqlite3.Connection, task_id: int) -> tuple | None:
    return conn.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()


def _get_task_row_with_users(
    conn: sqlite3.Connection, task_id: int
) -> tuple[tuple, tuple] | None:
    """(строка задачи, (creator_login, assigned_login)) одним запросом
    (Релиз 4, sdd r10 §3.2: GET-ответы содержат creator и assigned).

    Плейн-колонки TASK_COLUMNS квалифицируются tasks. — после LEFT JOIN
    users они без префикса двусмысленны (title/priority есть только в
    tasks, но id есть в обеих таблицах)."""
    plain = ", ".join(f"tasks.{name.strip()}" for name in TASK_COLUMNS.split(","))
    row = conn.execute(
        _task_with_users_sql(
            f"{plain}, creator.login, assigned.login"
        )
        + "WHERE tasks.id = ?",
        (task_id,),
    ).fetchone()
    if row is None:
        return None
    return row[: len(TASK_COLUMNS.split(","))], (row[-2], row[-1])


def _set_tags(conn: sqlite3.Connection, task_id: int, names: list[str]) -> None:
    """Перезаписывает набор тегов задачи (tags — get-or-create по UNIQUE name)."""
    conn.execute("DELETE FROM task_tags WHERE task_id = ?", (task_id,))
    for raw in names:
        name = raw.strip()
        if not name:
            continue
        row = conn.execute(
            "SELECT id FROM tags WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
            tag_id = cur.lastrowid
        else:
            tag_id = row[0]
        conn.execute(
            "INSERT OR IGNORE INTO task_tags (task_id, tag_id) VALUES (?, ?)",
            (task_id, tag_id),
        )


def _fast_line_busy(conn: sqlite3.Connection) -> bool:
    """Есть ли активная fast-задача (инвариант ≤1, FR-3/ОГР-5; design.md §4)."""
    placeholders = ", ".join("?" for _ in ACTIVE_STATUSES)
    row = conn.execute(
        f"SELECT COUNT(*) FROM tasks "
        f"WHERE is_fast = 1 AND status IN ({placeholders})",
        ACTIVE_STATUSES,
    ).fetchone()
    return row[0] >= 1


# Тело 422 жесткой валидации категории (FR-21) — дословно sdd r2 §3.2.
CATEGORY_NOT_IN_CATEGORIES_422 = {
    "error": "validation",
    "details": {"category": "not in categories"},
}


def _category_not_in_directory_422(
    conn: sqlite3.Connection, category: str | None
) -> JSONResponse | None:
    """Жесткая валидация категории (FR-21, tasks.md 1.2; design.md §1.3).

    Непустая category, отсутствующая в справочнике categories → 422
    CATEGORY_NOT_IN_CATEGORIES_422 (дословно sdd r2 §3.2); пустая
    (NULL/пустая строка) проходит — nullable-модель данных, Д-2
    (Scenario «Пустая категория жесткой валидацией не запрещена»).
    Точка проверки — API-слой: обход через API невозможен (FR-21).
    """
    if not category:
        return None
    if not category_exists(conn, category):
        return JSONResponse(
            status_code=422, content=CATEGORY_NOT_IN_CATEGORIES_422
        )
    return None


# Тело 422 priority-lock (FR-27, ОГР-10) — дословно sdd r2 §3.2.
FAST_REQUIRES_HIGH_422 = {
    "error": "validation",
    "details": {"priority": "fast requires high"},
}


def _priority_lock_422(is_fast: bool, priority: str | None) -> JSONResponse | None:
    """Priority-lock fast line (FR-27, ОГР-10; tasks.md 4.2; design.md §4).

    Инвариант is_fast ⇒ priority='high': явный приоритет, отличный от
    high, при is_fast=true отклоняется 422 FAST_REQUIRES_HIGH_422
    (дословно sdd r2 §3.2) — отклонение, а НЕ молчаливая правка
    (наблюдаемое поведение дельты fastline, негативные сценарии «fast-задача
    с приоритетом не-high через API» и «снятие блокировки в UI не меняет
    приоритет»). is_fast=true без priority (NULL) проходит — приоритет
    устанавливается 'high' вызывающим кодом (sdd r2 §3.2).
    Обычная (не fast) задача любым приоритетом не ограничена.
    """
    if is_fast and priority is not None and priority != "high":
        return JSONResponse(status_code=422, content=FAST_REQUIRES_HIGH_422)
    return None


def _explicit_null_priority_422(body: Any) -> JSONResponse | None:
    """BUG-002 (TC-fast2-004, CHK-130): «явный null» ≠ «поле отсутствует».

    pydantic не различает их в значении (None в обоих случаях) — единственный
    источник различия: model_fields_set. Если "priority" передан в теле со
    значением null и is_fast=true — это явное значение ≠ high → 422
    FAST_REQUIRES_HIGH_422 (sdd r2 §3.2; эскалация (а) impact-001).
    Используется только в create_task: у TaskUpdate null-очистка приоритета
    обычной задачи легальна, а PATCH на fast-задаче уже отклоняет любое
    значение ≠ high, включая null («priority» in model_fields_set).
    """
    if "priority" in body.model_fields_set and body.priority is None:
        return JSONResponse(status_code=422, content=FAST_REQUIRES_HIGH_422)
    return None


@router.post("", status_code=201)
def create_task(body: TaskCreate, request: Request) -> JSONResponse:
    """Создание задачи (sdd §3.2): 201 + Task; 422 — нет/пустое название;
    409 {"error": "fast line occupied"} — is_fast=true при активной fast-задаче.

    Релиз 4 (FR-37, ОВ-26; sdd r10 §3.2): assigned_to_id опционально —
    существующий пользователь или null, несуществующий → 422;
    creator_id ставит сервер = пользователю сессии (клиентом не
    принимается — TaskCreate extra="forbid").

    Проверка инварианта fast ≤1 и INSERT — одна транзакция (design.md §4):
    SQLite WAL, один writer — между SELECT и INSERT сторонняя запись не
    вклинивается; при 409 rollback ничего не оставляет в БД.
    """
    conn = get_connection()
    try:
        # Жесткая валидация категории (FR-21) до любых записей (design.md §1.3).
        invalid = _category_not_in_directory_422(conn, body.category)
        if invalid is not None:
            return invalid
        # Валидация исполнителя (Релиз 4, FR-37/ОВ-26): до любых записей,
        # в той же группе валидаций тела, что категория/приоритет.
        invalid = _assigned_to_id_422(conn, body)
        if invalid is not None:
            return invalid
        # Priority-lock (FR-27, ОГР-10; design.md §4): fast с явным
        # приоритетом ≠ high → 422 (отклонение, не молчаливая правка);
        # fast без priority → приоритет 'high' (инвариант is_fast ⇒ high).
        invalid = _priority_lock_422(body.is_fast, body.priority)
        if invalid is not None:
            return invalid
        # BUG-002: явный null при is_fast — тоже «значение ≠ high» (CHK-130);
        # проверка в той же группе валидаций тела, ДО 409 fast line (порядок
        # как в TC-fast2-012/CHK-138: валидации priority — до занятости линии).
        invalid = _explicit_null_priority_422(body) if body.is_fast else None
        if invalid is not None:
            return invalid
        priority = "high" if body.is_fast else body.priority
        now = _utcnow()
        # creator_id = пользователь сессии (FR-37, сервер ставит сам;
        # assigned_to_id — проверенный выше id или NULL).
        creator_id = _session_user_id(request)
        assigned_to_id = (
            body.assigned_to_id
            if "assigned_to_id" in body.model_fields_set
            else None
        )
        try:
            if body.is_fast:
                # Инвариант до вставки; BEGIN IMMEDIATE делает «проверка +
                # вставка» атомарными (design.md §4 «Гонки»).
                _begin_immediate(conn)
                if _fast_line_busy(conn):
                    conn.rollback()
                    return JSONResponse(
                        status_code=409, content=FAST_LINE_OCCUPIED_BODY
                    )
            cur = conn.execute(
                "INSERT INTO tasks (title, description, priority, category, "
                "due_date, is_fast, status, done_at, archived_at, "
                "creator_id, assigned_to_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'todo', NULL, NULL, ?, ?, ?, ?)",
                (
                    body.title,
                    body.description,
                    priority,
                    body.category,
                    body.due_date.isoformat() if body.due_date is not None else None,
                    int(body.is_fast),
                    creator_id,
                    assigned_to_id,
                    now,
                    now,
                ),
            )
            task_id = cur.lastrowid
            _set_tags(conn, task_id, body.tags)
            conn.commit()
        except sqlite3.IntegrityError:
            # Страховка CHECK-ограничений схемы (sdd §4) — валидация формы
            # уже отсекла известные случаи; это defenses-in-depth → 422.
            conn.rollback()
            return JSONResponse(
                status_code=422,
                content={"error": "invalid task data", "details": {}},
            )
        pair = _get_task_row_with_users(conn, task_id)
        task = _row_to_task(conn, pair[0], pair[1])
    finally:
        conn.close()
    return JSONResponse(status_code=201, content=task)


@router.get("/{task_id}")
def get_task(task_id: int) -> JSONResponse:
    """Карточка задачи (sdd §3.2): 200 + Task; 404 — несуществующий id.

    Релиз 4 (sdd r10 §3.2): Task содержит creator и assigned (логины,
    LEFT JOIN users; null — поле nullable).
    """
    conn = get_connection()
    try:
        pair = _get_task_row_with_users(conn, task_id)
        if pair is None:
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        task = _row_to_task(conn, pair[0], pair[1])
    finally:
        conn.close()
    return JSONResponse(content=task)


@router.patch("/{task_id}")
def update_task(task_id: int, body: TaskUpdate) -> JSONResponse:
    """Частичное редактирование (sdd §3.2): 200 + Task; ошибки 404, 422.

    Обновляются только переданные поля (model_fields_set); tags при наличии
    в теле заменяется целиком.
    """
    conn = get_connection()
    try:
        row = _get_task_row(conn, task_id)
        if row is None:
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)

        # Жесткая валидация категории (FR-21, sdd r2 §3.2 — «та же валидация»
        # для PATCH): проверяется только если категория передана в теле.
        if "category" in body.model_fields_set:
            invalid = _category_not_in_directory_422(conn, body.category)
            if invalid is not None:
                return invalid

        # Валидация исполнителя (Релиз 4, FR-37/ОВ-26 — «та же валидация»
        # для PATCH): null = очистить (легально), несуществующий → 422;
        # проверяется до любых записей.
        invalid = _assigned_to_id_422(conn, body)
        if invalid is not None:
            return invalid

        # Priority-lock в PATCH (FR-27, ОГР-10 — инвариант is_fast ⇒ high):
        # is_fast в PATCH не входит (fast назначается только при создании,
        # ОГР-5), но PATCH может ИЗМЕНИТЬ приоритет существующей fast-задачи.
        # Любое значение ≠ high — включая NULL («очистить признак») —
        # отклоняется 422: NULL не равен high (дельта fastline считает
        # отклоняемым «low», «medium» ИЛИ NULL). Обычные задачи не ограничены.
        if "priority" in body.model_fields_set and bool(row[6]) and body.priority != "high":
            return JSONResponse(status_code=422, content=FAST_REQUIRES_HIGH_422)

        updates: dict[str, Any] = {}
        for name in ("title", "description", "priority", "category"):
            if name in body.model_fields_set:
                updates[name] = getattr(body, name)
        if "due_date" in body.model_fields_set:
            updates["due_date"] = (
                body.due_date.isoformat() if body.due_date is not None else None
            )
        if "assigned_to_id" in body.model_fields_set:
            updates["assigned_to_id"] = body.assigned_to_id

        try:
            if updates:
                sets = ", ".join(f"{name} = ?" for name in updates)
                conn.execute(
                    f"UPDATE tasks SET {sets}, updated_at = ? WHERE id = ?",
                    (*updates.values(), _utcnow(), task_id),
                )
            if "tags" in body.model_fields_set:
                _set_tags(conn, task_id, body.tags or [])
            conn.commit()
        except sqlite3.IntegrityError:
            # Спокойление CHECK схемы (sdd §4) поверх pydantic-валидации.
            conn.rollback()
            return JSONResponse(
                status_code=422,
                content={"error": "invalid task data", "details": {}},
            )
        pair = _get_task_row_with_users(conn, task_id)
        task = _row_to_task(conn, pair[0], pair[1])
    finally:
        conn.close()
    return JSONResponse(content=task)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int) -> Response:
    """Физическое удаление (sdd §3.2, design §5): 204; 404 — несуществующий id.

    task_tags/comments уходят по ON DELETE CASCADE (sdd §4; FK включен).
    """
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cur.rowcount == 0:
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        conn.commit()
    finally:
        conn.close()
    return Response(status_code=204)


@router.post("/{task_id}/move")
def move_task(task_id: int, body: TaskMove) -> JSONResponse:
    """Перевод в другой столбец (tasks.md 4.4/6.1; sdd.md r5 §3.2 дословно).

    Запрос: {"status": "todo|in_progress|done"}; ответ 200: Task;
    ошибки: 404 — несуществующий id, 422 — недопустимый статус
    (Literal отсекает, обработчик RequestValidationError дает тело
    {"error", "details"} по sdd §3).

    done_at/archived_at (sdd r5 §3.2 move; sdd §4 инвариант FR-4):
    - target done → done_at = msk_now_iso() (момент в фиксированном
      UTC+3 — тот же формат, что у границы дня в autoarchive; источник
      app.board.msk_now_iso); archived_at НЕ трогается: задача
      ОСТАЕТСЯ на доске в столбце «Выполнено» до ленивой автоархивации
      следующим МСК-днем (GET /api/board, app/board.py, design.md §5);
    - target todo/in_progress (обратный перевод из done) → снимаются
      ОБА: done_at = NULL, archived_at = NULL (sdd §3.2 дословно;
      archived_at снимается «на случай ручного возврата», design §5).
    Переходы todo↔in_progress колонки не меняют (оба поля остаются
    NULL — POST создает с NULL, иные пути простановки нет).

    is_fast move не меняет. Перевод fast-задачи в done освобождает fast
    line сам собой (design.md §4 «Освобождение»).

    Инвариант fast ≤1 в move (расширение сверх спеки fastline — там
    прописан только сценарий создания; дыра из review-4.4-001):
    возврат done fast-задачи (→ todo/in_progress) при активной
    другой fast-задаче создал бы две активные fast → 409. Проверка и
    UPDATE — одна транзакция (design.md §4). is_fast при PATCH
    невозможен (задача 4.1), иных путей перевода в fast нет.
    """
    conn = get_connection()
    try:
        row = _get_task_row(conn, task_id)
        if row is None:
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        now = _utcnow()
        if body.status == "done":
            # done_at — момент перевода в done в фиксированном МСК
            # (msk_now_iso, формат ...+03:00): ленивая автоархивация
            # сравнивает его с границей дня ЛЕКСИКОГРАФИЧЕСКИ, форматы
            # обязаны совпадать (blocker review-6.1-001).
            done_at = msk_now_iso()
            # archived_at НЕ трогается (sdd r5 §3.2) — записываем как было.
            archived_at = row[9]
        else:
            # Обратный перевод: снимаются ОБА поля (sdd r5 §3.2).
            done_at = None
            archived_at = None
        # Инвариант ≤1: возвращаемая в активный статус задача должна быть
        # fast, а линия — уже занята другой fast (не этой же: она done).
        if (
            bool(row[6])
            and body.status in ACTIVE_STATUSES
            and row[7] not in ACTIVE_STATUSES
        ):
            _begin_immediate(conn)
            others = conn.execute(
                "SELECT COUNT(*) FROM tasks "
                "WHERE is_fast = 1 AND status IN (?, ?) AND id != ?",
                (*ACTIVE_STATUSES, task_id),
            ).fetchone()[0]
            if others >= 1:
                conn.rollback()
                return JSONResponse(
                    status_code=409, content=FAST_LINE_OCCUPIED_BODY
                )
        conn.execute(
            "UPDATE tasks SET status = ?, done_at = ?, archived_at = ?, "
            "updated_at = ? WHERE id = ?",
            (body.status, done_at, archived_at, now, task_id),
        )
        conn.commit()
        pair = _get_task_row_with_users(conn, task_id)
        task = _row_to_task(conn, pair[0], pair[1])
    finally:
        conn.close()
    return JSONResponse(content=task)


def install_error_handlers(app) -> None:
    """422 в форме sdd §3: {"error": "<сообщение>", "details": {...}}.

    Подключается из app.main вместе с роутером; действует на все
    RequestValidationError (до этого 422 каркаса имел тело {"detail": ...}).
    """

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation error",
                "details": jsonable_encoder(exc.errors()),
            },
        )
