"""Колонки и маппинг строки tasks → Task-объект: ЛОКАЛЬНАЯ КОПИЯ для search-сервиса.

копия из backend/app/tasks.py@ddd9fb616feded9dfbfadabb393eb04ae8ce5393,
задача 1.1 (add-microservices-full) — при изменении колонок обновлять синхронно.

Источник: константа TASK_COLUMNS и функция _row_to_task из backend/app/tasks.py
(без users-хвоста — creator/assigned в поиске добавляет сам search.py своей
проекцией _row_to_task_with_users). Расхождение копии с ядром ловит
контрактный тест (design пакета §4).
"""

import sqlite3

# CHECK из схемы (sdd §4): priority IN ('low','medium','high') OR NULL.
# Дословно backend/app/tasks.py (TASK_COLUMNS).
TASK_COLUMNS = (
    "id, title, description, priority, category, due_date, "
    "is_fast, status, done_at, archived_at"
)


# Дословно backend/app/tasks.py (_row_to_task) за вычетом параметра users:
# search-роутер вызывает эту функцию только для базовых 10 колонок.
def _row_to_task(conn: sqlite3.Connection, row: tuple) -> dict:
    """Строка tasks → Task-объект по схеме sdd §3.2 (r5: с done_at)."""
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


def _load_tags(conn: sqlite3.Connection, task_id: int) -> list[str]:
    """Теги задачи (тот же SELECT, что tasks._load_tags — копия, зона 1.1)."""
    rows = conn.execute(
        "SELECT t.name FROM tags t "
        "JOIN task_tags tt ON tt.tag_id = t.id "
        "WHERE tt.task_id = ? ORDER BY t.id",
        (task_id,),
    ).fetchall()
    return [row[0] for row in rows]
