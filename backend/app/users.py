"""Пользователи системы: GET /api/users (sdd.md r10 §3.1a-кватер-бис;
design.md §6, major B-1 ревью review-001; строка 5.1 tasks.md пакета).

Контракт (sdd.md §3.1a-кватер-бис):
- GET /api/users → 200 {"users": [{"id": int, "login": str,
  "display_name": str|null}]} — ВСЕ пользователи системы (NFR-4:
  заведены двое seed'ом, регистрация отсутствует), отсортированы по login.
- Вне exempt-списка: 401 без сессии (NFR-7) — отсекает middleware
  (app/middleware.py), exempt-список не расширяется.
- Read-only: состояние не изменяет, прав не вводит (ОВ-21 — роль
  только отображение); никаких INSERT/UPDATE/DELETE.
- display_name NULL → null в JSON: fallback «display_name или логин»
  решает клиент (Д-10), сервер значение не подставляет.

Потребители: select исполнителя в форме создания/редактирования задачи
(ОВ-26; подпись опции = display_name или логин, Д-10) и tooltip'ы при
недостающих данных assigned/creator. Хардкод состава («owner, wife») в
клиенте отклонен ревью: состав пользователей — данные, а не код.
"""

from fastapi import APIRouter

from app.db import get_connection

router = APIRouter(prefix="/api/users")

# Сортировка по login — контракт sdd §3.1a-кватер-бис (не «как в БД»).
_USERS_SQL = """
SELECT id, login, display_name
FROM users
ORDER BY login
"""


@router.get("")
def users() -> dict:
    """GET /api/users → {"users": [{id, login, display_name}]} (см. docstring модуля)."""
    conn = get_connection()
    try:
        rows = conn.execute(_USERS_SQL).fetchall()
    finally:
        conn.close()
    return {
        "users": [
            {"id": row[0], "login": row[1], "display_name": row[2]}
            for row in rows
        ]
    }
