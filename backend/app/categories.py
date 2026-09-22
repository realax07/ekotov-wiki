"""Справочник категорий: CRUD /api/categories (tasks.md 1.1; sdd.md r2 §3.1;
design.md §1.1, §1.4; домен categories — Справочник, Управление справочником).

Контракты — дословно sdd.md r2 §3.1:
- GET    /api/categories        200 {"categories": [{"id", "name"}, ...]}
                               (отсортировано по name); 401 — middleware.
- POST   /api/categories        201 {"id", "name"}; 422 — пустое/пробельное имя;
                               409 — дубль имени.
- PATCH  /api/categories/{id}   200 {"id", "name"}; 404 — нет такого id;
                               422 — пустое имя; 409 — дубль имени.
                               Переименование применяется ко всем задачам
                               (FR-20): задачи хранят ссылку по значению
                               (tasks.category = TEXT, design.md §1.1),
                               поэтому в одной транзакции с UPDATE categories
                               выполняется UPDATE tasks — перенос значения
                               у всех задач-ссылок.
- DELETE /api/categories/{id}   200 {"ok": true}; 404; 409
                               {"error": "category in use",
                                "details": {"tasks": N}} — категория
                               используется задачами (Д-1): порядок «проверить
                               использование → удалить», отказ с числом задач.

Тела ошибок: 401 — middleware (app/middleware.py, exempt-список не расширяется);
422 — {"error": "validation", "details": {"name": ...}} по sdd r2 §3
(ошибки валидации — 422 {"error": "validation", "details": {...}});
409 — {"error": "category already exists"} (текст sdd r2 §3.1 не фиксирует,
фиксируется код — как в существующих 409 роутерах).
"""

import sqlite3
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, field_validator

from app.db import get_connection

router = APIRouter(prefix="/api/categories")

NOT_FOUND_BODY = {"error": "not found"}

# Тело 409 при удалении используемой категории — дословно sdd r2 §3.1.
IN_USE_BODY = {"error": "category in use"}

# Тела ошибок валидации (sdd r2 §3: 422 {"error": "validation", "details": {...}}).
VALIDATION_ERROR = "validation"

INVALID_NAME_422 = {
    "error": VALIDATION_ERROR,
    "details": {"name": "must not be empty"},
}
DUPLICATE_NAME_409 = {"error": "category already exists"}


def category_exists(conn: sqlite3.Connection, name: str) -> bool:
    """Есть ли категория с таким именем в справочнике (сверка FR-21).

    Общая с валидацией задач (app.tasks) точка сверки —
    SELECT 1 FROM categories WHERE name = ? (design.md §1.3).
    """
    return (
        conn.execute(
            "SELECT 1 FROM categories WHERE name = ?", (name,)
        ).fetchone()
        is not None
    )


class CategoryCreate(BaseModel):
    """Тело POST /api/categories: только name (sdd r2 §3.1)."""

    model_config = ConfigDict(extra="forbid")

    name: str

    @field_validator("name")
    @classmethod
    def _name_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value


class CategoryUpdate(BaseModel):
    """Тело PATCH /api/categories/{id}: только name (sdd r2 §3.1)."""

    model_config = ConfigDict(extra="forbid")

    name: str

    @field_validator("name")
    @classmethod
    def _name_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be empty")
        return value


@router.get("")
def list_categories() -> JSONResponse:
    """GET /api/categories → 200 {"categories": [...]} по name (sdd r2 §3.1)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name FROM categories ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return JSONResponse(
        content={"categories": [{"id": row[0], "name": row[1]} for row in rows]}
    )


@router.post("", status_code=201)
def create_category(body: CategoryCreate) -> JSONResponse:
    """Создать категорию (design.md §1.4): 201; 422 пустое имя; 409 дубль.

    Проверка на непустое имя — после trim (pydantic-валидатор); уникальность —
    на уровне БД (UNIQUE name, design.md §1.1): IntegrityError → 409.
    """
    name = body.name.strip()
    conn = get_connection()
    try:
        try:
            cur = conn.execute(
                "INSERT INTO categories (name) VALUES (?)", (name,)
            )
            category_id: Any = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            return JSONResponse(status_code=409, content=DUPLICATE_NAME_409)
    finally:
        conn.close()
    return JSONResponse(status_code=201, content={"id": category_id, "name": name})


@router.patch("/{category_id}")
def rename_category(category_id: int, body: CategoryUpdate) -> JSONResponse:
    """Переименовать (design.md §1.4): 200; 404; 422 пустое имя; 409 дубль.

    Задачи ссылаются по значению (tasks.category = TEXT), поэтому один
    атомарный UPDATE categories.name автоматически меняет категорию у всех
    задач-ссылок — наблюдаемое «применяется ко всем задачам» (FR-20,
    design.md §1.1).
    """
    name = body.name.strip()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT name FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if row is None:
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        old_name = row[0]
        try:
            # Сценарий FR-20 «Переименование применяется ко всем задачам»:
            # хранение по значению (design.md §1.1) само задачи не обновляет —
            # перенос значения выполняется явным UPDATE tasks в той же
            # транзакции (атомарность из design.md §1.4).
            conn.execute(
                "UPDATE categories SET name = ? WHERE id = ?",
                (name, category_id),
            )
            conn.execute(
                "UPDATE tasks SET category = ? WHERE category = ?",
                (name, old_name),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # UNIQUE name: другое имя уже занято → 409 дубль (design.md §1.4).
            conn.rollback()
            return JSONResponse(status_code=409, content=DUPLICATE_NAME_409)
    finally:
        conn.close()
    return JSONResponse(content={"id": category_id, "name": name})


@router.delete("/{category_id}")
def delete_category(category_id: int) -> JSONResponse:
    """Удалить (Д-1): 200 {"ok": true}; 404; 409 если используется задачами.

    Порядок — design.md §1.4: проверить использование
    (SELECT COUNT(*) FROM tasks WHERE category = ?) → удалить; использующие
    задачи получают отказ с их числом (перевести задачи → удалить). Гонка с
    параллельной установкой категории закрыта серверной валидацией FR-21
    (design.md §1.4): задача с уже удаленной категорией не сохранится.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT name FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if row is None:
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        name = row[0]
        in_use = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE category = ?", (name,)
        ).fetchone()[0]
        if in_use > 0:
            body = {
                "error": IN_USE_BODY["error"],
                "details": {"tasks": in_use},
            }
            return JSONResponse(status_code=409, content=body)
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
    finally:
        conn.close()
    return JSONResponse(content={"ok": True})
