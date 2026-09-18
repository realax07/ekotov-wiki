"""CRUD задач: POST /api/tasks, GET/PATCH/DELETE /api/tasks/{id}
(tasks.md 4.1; sdd.md §3.2; домен tasks — Создание/Редактирование/Удаление,
Перемещение через API).

Контракты — дословно sdd.md §3.2:
- POST: обязателен title; остальные признаки опциональны; ответ 201 Task.
  Ошибки: 422 — нет названия. 409 {"error": "fast line occupied"} —
  is_fast=true при наличии активной (todo/in_progress) fast-задачи
  (задача 5.1; проверка + вставка — одна транзакция, design.md §4).
- GET: Task; 404 на несуществующий id.
- PATCH: частичное обновление — только переданные поля; 200 Task; ошибки 404, 422.
  status в PATCH не входит: статус меняется через POST /{id}/move (sdd §3.2),
  ручная простановка обошла бы archived_at (задача 4.4/6.1).
- POST /{id}/move: {"status": "todo|in_progress|done"}; 200 Task;
  при done — archived_at проставлен (задача уходит в архив, с доски
  исчезает); при обратном переводе — archived_at снимается (FR-6 «и
  обратно»); ошибки 404, 422 (недопустимый статус). Возврат archived
  fast-задачи в todo/in_progress проверяет инвариант fast ≤1 (409,
  задача 5.1 — расширение сверх спеки fastline, дыра из review-4.4-001).
- DELETE: физическое удаление; каскады task_tags/comments — FK ON DELETE
  CASCADE (sdd §4), foreign_keys=ON включен в get_connection (app/db.py).

Task-объект — по схеме sdd §3.2 (id, title, description, priority, category,
due_date, tags, is_fast, status, archived_at). Владельца у задачи нет — модель
sdd §4 не имеет колонки user_id в tasks (общая доска, sdd §7 допущения).

Тела ошибок: 401 — middleware (app/middleware.py); 422 —
{"error", "details"} по sdd §3 (обработчик RequestValidationError,
install_error_handlers); 404 — {"error": "not found"} (sdd §3 фиксирует
только код).
"""

import sqlite3
from datetime import date, datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db import get_connection

router = APIRouter(prefix="/api/tasks")

# CHECK из схемы (sdd §4): priority IN ('low','medium','high') OR NULL.
Priority = Literal["low", "medium", "high"]

TASK_COLUMNS = (
    "id, title, description, priority, category, due_date, "
    "is_fast, status, archived_at"
)

NOT_FOUND_BODY = {"error": "not found"}

# Инвариант fast line ≤1 (FR-3, ОГР-5; design.md §4): в активных статусах
# (todo/in_progress — «Ожидает»/«В работе») не более одной fast-задачи.
# Тело 409 — дословно sdd.md §3.2.
FAST_LINE_OCCUPIED_BODY = {"error": "fast line occupied"}

# Активные статусы «Ожидает»/«В работе» (ОГР-3); done = архив, линию не занимает.
ACTIVE_STATUSES = ("todo", "in_progress")


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


def _row_to_task(conn: sqlite3.Connection, row: tuple) -> dict:
    """Строка tasks → Task-объект по схеме sdd §3.2."""
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "priority": row[3],
        "category": row[4],
        "due_date": row[5],
        "tags": _load_tags(conn, row[0]),
        "is_fast": bool(row[6]),
        "status": row[7],
        "archived_at": row[8],
    }


def _get_task_row(conn: sqlite3.Connection, task_id: int) -> tuple | None:
    return conn.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()


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


@router.post("", status_code=201)
def create_task(body: TaskCreate) -> JSONResponse:
    """Создание задачи (sdd §3.2): 201 + Task; 422 — нет/пустое название;
    409 {"error": "fast line occupied"} — is_fast=true при активной fast-задаче.

    Проверка инварианта fast ≤1 и INSERT — одна транзакция (design.md §4):
    SQLite WAL, один writer — между SELECT и INSERT сторонняя запись не
    вклинивается; при 409 rollback ничего не оставляет в БД.
    """
    conn = get_connection()
    try:
        now = _utcnow()
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
                "due_date, is_fast, status, archived_at, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'todo', NULL, ?, ?)",
                (
                    body.title,
                    body.description,
                    body.priority,
                    body.category,
                    body.due_date.isoformat() if body.due_date is not None else None,
                    int(body.is_fast),
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
        task = _row_to_task(conn, _get_task_row(conn, task_id))
    finally:
        conn.close()
    return JSONResponse(status_code=201, content=task)


@router.get("/{task_id}")
def get_task(task_id: int) -> JSONResponse:
    """Карточка задачи (sdd §3.2): 200 + Task; 404 — несуществующий id."""
    conn = get_connection()
    try:
        row = _get_task_row(conn, task_id)
        if row is None:
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        task = _row_to_task(conn, row)
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

        updates: dict[str, Any] = {}
        for name in ("title", "description", "priority", "category"):
            if name in body.model_fields_set:
                updates[name] = getattr(body, name)
        if "due_date" in body.model_fields_set:
            updates["due_date"] = (
                body.due_date.isoformat() if body.due_date is not None else None
            )

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
        task = _row_to_task(conn, _get_task_row(conn, task_id))
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
    """Перевод в другой столбец (tasks.md 4.4; sdd.md §3.2 дословно).

    Запрос: {"status": "todo|in_progress|done"}; ответ 200: Task;
    ошибки: 404 — несуществующий id, 422 — недопустимый статус
    (Literal отсекает, обработчик RequestValidationError дает тело
    {"error", "details"} по sdd §3).

    archived_at (sdd §4: NOT NULL <=> в архиве; FR-4, FR-6 «и обратно»):
    - target done → проставляется (задача уходит в архив и исчезает
      с доски — GET /api/board фильтрует archived_at IS NULL);
    - target todo/in_progress → снимается (NULL): обратный перевод
      возвращает задачу на доску (дельта board, «Обратное перемещение»).
      Источник не проверяется — прямой перевод в «Выполнено» из любого
      столбца разрешен (дельта board, «Быстрый доступ к действию
      "Выполнено"»); перевод из «Выполнено» обратно разрешен контрактом
      (все три статуса цели дают 200) и FR-6 «и обратно».

    is_fast move не меняет. Перевод fast-задачи в done освобождает fast
    line сам собой (design.md §4 «Освобождение»).

    Инвариант fast ≤1 в move (расширение сверх спеки fastline — там
    прописан только сценарий создания; дыра из review-4.4-001):
    возврат архивной fast-задачи (done → todo/in_progress) при активной
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
        archived_at = now if body.status == "done" else None
        # Инвариант ≤1: возвращаемая в активный статус задача должна быть
        # fast, а линия — уже занята другой fast (не этой же: она archived).
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
            "UPDATE tasks SET status = ?, archived_at = ?, updated_at = ? "
            "WHERE id = ?",
            (body.status, archived_at, now, task_id),
        )
        conn.commit()
        task = _row_to_task(conn, _get_task_row(conn, task_id))
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
