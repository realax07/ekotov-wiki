"""CRUD задач: POST /api/tasks, GET/PATCH/DELETE /api/tasks/{id}
(tasks.md 4.1; sdd.md §3.2; домен tasks — Создание/Редактирование/Удаление,
Перемещение через API).

Контракты — дословно sdd.md §3.2:
- POST: обязателен title; остальные признаки опциональны; ответ 201 Task.
  Ошибки: 422 — нет названия. 409 «fast line occupied» — НЕ здесь: это
  задача 5.1 (инвариант ≤1); флаг is_fast принимается без инварианта.
- GET: Task; 404 на несуществующий id.
- PATCH: частичное обновление — только переданные поля; 200 Task; ошибки 404, 422.
  status в PATCH не входит: статус меняется через POST /{id}/move (sdd §3.2),
  ручная простановка обошла бы archived_at (задача 4.4/6.1).
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


@router.post("", status_code=201)
def create_task(body: TaskCreate) -> JSONResponse:
    """Создание задачи (sdd §3.2): 201 + Task; 422 — нет/пустое название."""
    conn = get_connection()
    try:
        now = _utcnow()
        try:
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
