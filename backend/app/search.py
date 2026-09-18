"""Поиск: GET /api/search (tasks.md 7.1; sdd.md r5 §3.5; домен search).

Контракт — дословно sdd.md §3.5:
- Query-параметры (все опциональны; пустой набор = ВСЕ задачи, включая
  архивные — спека search, Scenario «Поиск без заданных условий»):
  `priority`, `category`, `tag` (повторяемый), `due_before`, `due_after`,
  `archived=true|false|all` (по умолчанию `all`).
- Ответ 200: {"results": [Task]} — Task по схеме sdd §3.2 (11 полей,
  включая done_at и archived_at; archived_at = признак архивности, FR-10).
- Ошибки: 422 (невозможное значение параметра — невалидный priority/
  дата/archived); 401 — middleware (без сессии).

Семантика фильтра (design.md §6):
- разные признаки объединяются по И (спека search, Scenario
  «Комбинация условий по нескольким признакам»: «удовлетворяющие
  ОБОИМ условиям»);
- НЕСКОЛЬКО значений одного признака (повторяемый tag) — через IN,
  т.е. ИЛИ внутри признака: сериализация в design.md §6 —
  `tag IN ("home", "car")`.

Безопасность (NFR-7): SQL только параметризованный — значения фильтра
никогда не конкатенируются в текст запроса, только bind-параметры;
имена полей/операторы — белый список, зашитый в build_where().

Разделение для переиспользования задачей 7.2 (parse/build):
- валидация query-параметров → SearchFilters (pydantic/FastAPI, 422);
- построение WHERE из валидного фильтра → build_where() (чистая функция,
  без FastAPI). 7.2 строит SearchFilters-эквивалент из распарсенного
  текста и вызывает тот же build_where.
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder

from app.db import get_connection
from app.tasks import TASK_COLUMNS, _row_to_task

router = APIRouter(prefix="/api/search")

# Белый список значений (sdd §3.5, §3.2 CHECK): иное — 422.
Priority = Literal["low", "medium", "high"]
Archived = Literal["true", "false", "all"]


@dataclass
class SearchFilters:
    """Валидированный структурированный фильтр (внутреннее представление).

    Экземпляр этого класса — точка стыковки с задачей 7.2: parse() текста
    advanced-фильтра построит такой же объект, и исполнение пойдет через
    тот же build_where (design.md §6: «исполнитель превращает предикаты
    в параметризованный SQL WHERE»).
    """

    priority: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    due_before: date | None = None
    due_after: date | None = None
    archived: str = "all"


def build_where(f: SearchFilters) -> tuple[str, list]:
    """SearchFilters → (WHERE-фрагмент, bind-параметры).

    Чистая функция без FastAPI. Каждый предикат — фиксированный шаблон
    с плейсхолдерами; значения ТОЛЬКО через bind-параметры (NFR-7):
    инъекционный текст в tag/category/priority просто не совпадет
    со значением в БД, SQL он не меняет. Имена полей — не из ввода.
    """
    clauses: list[str] = []
    params: list = []

    if f.priority is not None:
        clauses.append("tasks.priority = ?")
        params.append(f.priority)

    if f.category is not None:
        clauses.append("tasks.category = ?")
        params.append(f.category)

    # Повторяемый tag: ИЛИ внутри признака = IN (design.md §6:
    # сериализация `tag IN ("home", "car")`). EXISTS — задача обязана
    # иметь ВСЕ проверяемые... нет: ХОТЯ БЫ ОДИН из перечисленных тегов.
    if f.tags:
        placeholders = ", ".join("?" for _ in f.tags)
        clauses.append(
            "EXISTS (SELECT 1 FROM task_tags tt "
            "JOIN tags t ON t.id = tt.tag_id "
            f"WHERE tt.task_id = tasks.id AND t.name IN ({placeholders}))"
        )
        params.extend(f.tags)

    # Границы срока — ВКЛЮЧИТЕЛЬНО (due_before = «срок не позднее»).
    # В спеке/design инклюзивность не оговорена — см. ОТЧЕТ 7.1 (вопрос 2).
    if f.due_before is not None:
        clauses.append("tasks.due_date <= ?")
        params.append(f.due_before.isoformat())

    if f.due_after is not None:
        clauses.append("tasks.due_date >= ?")
        params.append(f.due_after.isoformat())

    # Архивность (sdd §3.5): true → только архивные, false → только
    # активные, all (дефолт) → без условия (и архив, и активные).
    if f.archived == "true":
        clauses.append("tasks.archived_at IS NOT NULL")
    elif f.archived == "false":
        clauses.append("tasks.archived_at IS NULL")
    # "all" — предиката нет (пустой фильтр не ограничивает выборку).

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def run_search(conn: sqlite3.Connection, f: SearchFilters) -> list[dict]:
    """Выполняет параметризованный SELECT, возвращает Task-объекты."""
    where, params = build_where(f)
    rows = conn.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks{where} ORDER BY tasks.id",
        params,
    ).fetchall()
    return [_row_to_task(conn, row) for row in rows]


@router.get("")
def search(
    request: Request,
    priority: Priority | None = Query(default=None),
    category: str | None = Query(default=None),
    tag: list[str] = Query(default_factory=list),
    due_before: date | None = Query(default=None),
    due_after: date | None = Query(default=None),
    archived: Archived = Query(default="all"),
) -> dict:
    """GET /api/search — структурированные условия (sdd §3.5, FR-10/11/8).

    Валидация типов/значений — FastAPI/pydantic: невалидный priority,
    дата не формата YYYY-MM-DD, archived вне true|false|all → 422
    (обработчик RequestValidationError, sdd §3). 401 без сессии —
    middleware. Пустой набор параметров = все задачи.
    """
    filters = SearchFilters(
        priority=priority,
        category=category,
        tags=tag,
        due_before=due_before,
        due_after=due_after,
        archived=archived,
    )
    conn = get_connection()
    try:
        results = run_search(conn, filters)
    finally:
        conn.close()
    return {"results": jsonable_encoder(results)}
