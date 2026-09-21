"""Комментарии задачи: POST/GET /api/tasks/{task_id}/comments
(tasks.md 4.2; sdd.md §3.2, §4; домен tasks — Requirement «Признаки задачи»,
Scenario «Комментарии к задаче»).

Контракты — sdd.md §3.2 дословно:
- POST /api/tasks/{id}/comments «Добавить комментарий» — путь зафиксирован;
  код ответа sdd для него не специфицирует → 201 (как у POST /api/tasks,
  sdd §3.2: создание ресурса).
- GET списка: отдельного пути sdd не фиксирует — реализован симметричный
  GET /api/tasks/{task_id}/comments (sdd §3.2 описывает GET /api/tasks/{id}
  как «карточку со всеми признаками и комментариями», но схема Task в §3.2
  зафиксирована ровно 10 полями, без comments — поэтому список отдается
  отдельным ресурсом, Task-схема не расширяется).
- Порядок списка: created_at ASC (сценарий «Комментарии к задаче» —
  «сохраняется и отображается»: хронология добавления); идентичный
  created_at разрешается по id ASC (детерминизм).
- author_id — из сессии (cookie → sessions.user_id); из тела запроса не
  принимается никогда (sdd §4: author_id NOT NULL FK -> users.id).
- 404 — задача не существует (sdd §3: «Не найдено — 404»).
- 422 — пустой/отсутствующий текст (sdd §3: «Ошибки валидации — 422
  {"error", "details"}»; обработчик RequestValidationError из app.tasks).
- 401 — без валидной сессии; путь не в exempt-списке, отсекает middleware
  (app/middleware.py) — здесь повторно не проверяется.
- DELETE задачи каскадом удаляет комментарии: FK ON DELETE CASCADE
  (sdd §4, foreign_keys=ON в app/db.get_connection).

Объект Comment — по таблице comments (sdd §4):
{"id", "task_id", "author_id", "body", "created_at"}.
"""

import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator

from app.db import get_connection

router = APIRouter(prefix="/api/tasks")

NOT_FOUND_BODY = {"error": "not found"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_user_id(conn: sqlite3.Connection, request: Request) -> int | None:
    """user_id по токену сессии из куки (sdd §4 sessions).

    Токен к этому моменту валиден (middleware пропустил запрос), но lookup
    все равно явный: middleware user_id в request не кладет (зона задачи 2.2).
    """
    from app.auth import SESSION_COOKIE_NAME

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    row = conn.execute(
        "SELECT user_id FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    return row[0] if row is not None else None


class CommentCreate(BaseModel):
    """Тело POST /api/tasks/{id}/comments: обязателен непустой текст (sdd §4
    comments.body NOT NULL; пустой текст — 422). Поле author_id в теле не
    существует: автор всегда из сессии (extra=forbid отсекает подмену)."""

    model_config = ConfigDict(extra="forbid")

    body: str

    @field_validator("body")
    @classmethod
    def _body_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body must not be empty")
        return value


def _task_exists(conn: sqlite3.Connection, task_id: int) -> bool:
    return (
        conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone()
        is not None
    )


def _row_to_comment(row: tuple) -> dict[str, Any]:
    return {
        "id": row[0],
        "task_id": row[1],
        "author_id": row[2],
        "body": row[3],
        "created_at": row[4],
    }


@router.post("/{task_id}/comments", status_code=201)
def add_comment(task_id: int, body: CommentCreate, request: Request) -> JSONResponse:
    """Добавить комментарий (sdd §3.2): 201 + Comment; 404 — нет задачи;
    422 — пустой текст; автор — user_id сессии."""
    conn = get_connection()
    try:
        if not _task_exists(conn, task_id):
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        author_id = _session_user_id(conn, request)
        if author_id is None:
            # Оборонительная ветка: middleware не пускает запросы без сессии.
            return JSONResponse(status_code=401, content={"error": "unauthorized"})
        try:
            cur = conn.execute(
                "INSERT INTO comments (task_id, author_id, body, created_at) "
                "VALUES (?, ?, ?, ?)",
                (task_id, author_id, body.body, _utcnow()),
            )
            comment_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            # Страховка FK схемы (sdd §4) поверх явной проверки задачи.
            conn.rollback()
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        row = conn.execute(
            "SELECT id, task_id, author_id, body, created_at "
            "FROM comments WHERE id = ?",
            (comment_id,),
        ).fetchone()
    finally:
        conn.close()
    return JSONResponse(status_code=201, content=_row_to_comment(row))


@router.get("/{task_id}/comments")
def list_comments(task_id: int) -> JSONResponse:
    """Список комментариев задачи: 200 + {"comments": [Comment]} в порядке
    created_at ASC (tiebreak id ASC); 404 — нет задачи."""
    conn = get_connection()
    try:
        if not _task_exists(conn, task_id):
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        rows = conn.execute(
            "SELECT id, task_id, author_id, body, created_at "
            "FROM comments WHERE task_id = ? ORDER BY created_at ASC, id ASC",
            (task_id,),
        ).fetchall()
    finally:
        conn.close()
    return JSONResponse(content={"comments": [_row_to_comment(r) for r in rows]})
