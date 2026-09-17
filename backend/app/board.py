"""Доска: GET /api/board (tasks.md 4.3; sdd.md §3.3; домен board —
«Отображение канбан-доски», «Три фиксированных столбца», FR-1, FR-2).

Контракт — дословно sdd.md §3.3:
- Ответ 200: `{"columns": {"todo": [Task], "in_progress": [Task],
  "done_note": "…"}}` — только активные (не архивные) задачи
  (archived_at IS NULL; дельта archive, сценарий «Архивная задача не
  возвращается на доску сама»; sdd.md §3.3 «только активные»).
- Ошибки: только 401 (middleware, app/middleware.py; здесь не дублируется).

Столбец «Выполнено» списка задач не имеет: по FR-4 перевод в «Выполнено»
одновременно отправляет задачу в архив (реализует 4.4 через
POST /{id}/move), поэтому на доске выполненных задач не бывает — столбец
выражен примечанием done_note (sdd.md §3.3). Задача со status='done', но
archived_at IS NULL через API возникнуть не может (POST создает только
'todo', PATCH status не принимает, move — 4.4), поэтому в выборку не
включается — на доске ей места нет.

Порядок внутри столбцов (sdd.md §3.3): fast-задача выделена и отсортирована
по приоритету — fast идет первым, далее по убыванию приоритета
(high → medium → low → без приоритета), внутри одного приоритета — по id.
Визуальное выделение fast line на доске — задача 5.2, здесь не делается.

Пустая доска (дельта board, сценарий «Открытие пустой доски»): 200 с тремя
пустыми столбцами по той же структуре, без ошибок.
"""

import sqlite3
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db import get_connection

router = APIRouter(prefix="/api/board")

# Примечание столбца «Выполнено» (sdd.md §3.3: done_note): задачи после
# «Выполнено» уходят в архив (FR-4) и на доске не отображаются.
DONE_NOTE = "Выполненные задачи уходят в архив — доступны через поиск."

TASK_COLUMNS = (
    "id, title, description, priority, category, due_date, "
    "is_fast, status, archived_at"
)

# Порядок строк: fast первым, затем приоритет high→medium→low→NULL, по id.
ORDER_SQL = (
    "ORDER BY is_fast DESC, "
    "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 "
    "WHEN 'low' THEN 2 ELSE 3 END, id"
)

# Столбцы доски (дельта board, «Три фиксированных столбца», ОГР-3):
# ровно todo и in_progress с задачами; «Выполнено» — done_note.
BOARD_STATUSES = ("todo", "in_progress")


def _load_tags(conn: sqlite3.Connection, task_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT t.name FROM tags t "
        "JOIN task_tags tt ON tt.tag_id = t.id "
        "WHERE tt.task_id = ? ORDER BY t.id",
        (task_id,),
    ).fetchall()
    return [row[0] for row in rows]


def _row_to_task(conn: sqlite3.Connection, row: tuple) -> dict:
    """Строка tasks → Task-объект по схеме sdd §3.2 (как в app/tasks.py)."""
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


@router.get("")
def get_board() -> JSONResponse:
    """Активные задачи по столбцам (sdd §3.3): 200; без сессии — 401 (middleware)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT {TASK_COLUMNS} FROM tasks "
            "WHERE archived_at IS NULL AND status IN ('todo', 'in_progress') "
            f"{ORDER_SQL}"
        ).fetchall()
        columns: dict[str, Any] = {status: [] for status in BOARD_STATUSES}
        for row in rows:
            columns[row[7]].append(_row_to_task(conn, row))
        columns["done_note"] = DONE_NOTE
    finally:
        conn.close()
    return JSONResponse(content={"columns": columns})
