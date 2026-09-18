"""Доска: GET /api/board (tasks.md 4.3, 6.1; sdd.md r5 §3.3; домен board —
«Отображение канбан-доски», «Три фиксированных столбца», «Столбец
«Выполнено» показывает задачи текущего МСК-дня»; FR-1, FR-2, FR-4).

Контракт — дословно sdd.md r5 §3.3:
- ПЕРЕД формированием ответа — ленивая автоархивация (FR-4, новая
  редакция; design.md §5): один UPDATE
    UPDATE tasks SET archived_at = <now>
    WHERE status = 'done' AND archived_at IS NULL
      AND done_at < <начало текущего календарного дня МСК>.
  Задачи, выполненные вчера по МСК или ранее, получают archived_at и
  исчезают с доски. Фонового процесса нет (design.md §5) — доска читается
  часто, задержка до первого чтения после полуночи МСК неотличима от
  календарной границы.
- Ответ 200: `{"columns": {"todo": [Task], "in_progress": [Task],
  "done": [Task]}}` — только не архивные (archived_at IS NULL).
  Столбец done — РЕАЛЬНЫЙ список Task: done-задачи с done_at текущего
  календарного дня по МСК (UTC+3); архив в ответ не попадает.
  (done_note из прежней редакции §3.3 удален — sdd r5 §3.3 дословно.)
- Ошибки: только 401 (middleware, app/middleware.py; здесь не дублируется).

Часовой пояс (зафиксировано sdd §3.3/design §5): «начало текущего дня»
вычисляется в фиксированном UTC+3 независимо от локального TZ
сервера/контейнера. Механика (app/board.py _msk_day_start): текущий
момент в UTC сдвигается на +3 часа (timezone(timedelta(hours=3)) —
фиксированная зона, без переходов на летнее время), из него берется дата
и собирается полночь 00:00 этого МСК-дня; сравнение с done_at —
лексикографическое по ISO-строкам: done_at хранится в UTC+03:00
.isoformat() (move, app/tasks.py), строки одного формата
"YYYY-MM-DDTHH:MM:SS±HH:MM" сортируются хронологически. При любом
серверном TZ: datetime.now(tz) дает один и тот же момент, а граница
всегда 00:00 UTC+3.

Порядок внутри столбцов (sdd.md §3.3): fast-задача выделена и
отсортирована по приоритету — fast идет первым, далее по убыванию
приоритета (high → medium → low → без приоритета), внутри одного
приоритета — по id. Визуальное выделение fast line — задача 5.2.

Пустая доска (дельта board, сценарий «Открытие пустой доски»): 200 с
тремя пустыми столбцами по той же структуре, без ошибок.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db import get_connection

router = APIRouter(prefix="/api/board")

TASK_COLUMNS = (
    "id, title, description, priority, category, due_date, "
    "is_fast, status, done_at, archived_at"
)

# Порядок строк: fast первым, затем приоритет high→medium→low→NULL, по id.
ORDER_SQL = (
    "ORDER BY is_fast DESC, "
    "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 "
    "WHEN 'low' THEN 2 ELSE 3 END, id"
)

# Столбцы доски (дельта board, «Три фиксированных столбца», ОГР-3;
# sdd r5 §3.3: done — реальный список задач текущего МСК-дня).
BOARD_STATUSES = ("todo", "in_progress", "done")

# Фиксированный МСК = UTC+3 (sdd §3.3): без летнего времени, независим
# от локали сервера/контейнера.
MSK = timezone(timedelta(hours=3), name="MSK")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _msk_day_start_iso() -> str:
    """Начало текущего календарного дня по МСК (00:00 UTC+3), ISO-строка.

    Конструкция TZ-независимости (sdd §3.3, design §5): момент now
    берется в UTC (не наивным localnow()!) и переводится в фиксированную
    зону UTC+3 — datetime.now(tz) дает один и тот же момент при любом
    системном TZ; дата и полночь берутся уже в МСК.
    """
    now_msk = datetime.now(timezone.utc).astimezone(MSK)
    day_start = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start.isoformat()


def autoarchive_done_tasks(conn: sqlite3.Connection) -> None:
    """Ленивая автоархивация (sdd r5 §3.3, design.md §5 — один UPDATE).

    Архивируются done-задачи без archived_at, момент перевода в done
    (done_at) которых наступил до начала текущего МСК-дня. done_at и
    граница — ISO-строки одного формата (UTC+03:00), сравнение
    лексикографическое = хронологическое.
    """
    conn.execute(
        "UPDATE tasks SET archived_at = ? "
        "WHERE status = 'done' AND archived_at IS NULL "
        "AND done_at IS NOT NULL AND done_at < ?",
        (_utcnow_iso(), _msk_day_start_iso()),
    )
    conn.commit()


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
        "done_at": row[8],
        "archived_at": row[9],
    }


@router.get("")
def get_board() -> JSONResponse:
    """Столбцы доски (sdd r5 §3.3): 200; без сессии — 401 (middleware)."""
    conn = get_connection()
    try:
        autoarchive_done_tasks(conn)
        rows = conn.execute(
            f"SELECT {TASK_COLUMNS} FROM tasks "
            "WHERE archived_at IS NULL "
            f"{ORDER_SQL}"
        ).fetchall()
        columns: dict[str, Any] = {status: [] for status in BOARD_STATUSES}
        for row in rows:
            columns[row[7]].append(_row_to_task(conn, row))
    finally:
        conn.close()
    return JSONResponse(content={"columns": columns})
