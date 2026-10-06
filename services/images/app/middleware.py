"""Сессионный middleware images-сервиса — копия паттерна services/search.

Задача 1.2 (add-gallery-service), design §3: «401 без сессии (NFR-7-паттерн
ядра)», OpenAPI включен, но не публикуется без сессии. Отличие от search
только в докстринге: images открывает БД в RW-профиле (app/db.py), но
валидация сессии — по-прежнему SELECT-only (удаление истекшей записи и
скользящее продление TTL остается ядру).

Отличие от search по exempt-списку: none. Роутера логина в сервисе нет —
путь POST /api/auth/login оставлен для дословного паритета паттерна.
"""

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.db import get_connection

# Имя куки сессии — дословно backend/app/middleware.py и services/search.
SESSION_COOKIE_NAME = "session"

# Исчерпывающий exempt-список (метод, путь) — как в services/search.
EXEMPT_API: set[tuple[str, str]] = {
    ("POST", "/api/auth/login"),
    ("GET", "/api/health"),
}

# Единый текст middleware-401 (sdd ядра §3 — тот же текст, что у search).
UNAUTHORIZED_BODY = {"error": "unauthorized"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _user_id(conn, token: str) -> int | None:
    """id пользователя валидной сессии или None (SELECT-only).

    Токен есть в sessions и не истек (тот же критерий, что в search и
    ядре). Скользящее продление TTL и удаление истекших записей делает
    app на своих запросах — сервису писать в sessions запрещено
    (спека services: «таблицы ядра не изменены»).
    """
    row = conn.execute(
        "SELECT user_id, expires_at FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    if row is None:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at <= _utcnow():
        return None
    return int(row["user_id"])


async def dispatch(request: Request, call_next):
    path = request.url.path

    if (request.method, path) in EXEMPT_API:
        return await call_next(request)

    token = request.cookies.get(SESSION_COOKIE_NAME)
    user_id = None
    if token:
        conn = get_connection()
        try:
            user_id = _user_id(conn, token)
        finally:
            conn.close()
    if user_id is not None:
        # Требование эндпоинтов: действия привязаны к пользователю
        # (uploaded_by, голос, автор комментария) — id кладем в request.state.
        request.state.user_id = user_id
        return await call_next(request)

    # Сервис — чистый API: без валидной сессии — 401, включая /openapi.json.
    return JSONResponse(status_code=401, content=UNAUTHORIZED_BODY)


def register(app) -> None:
    """Подключает middleware к приложению (вызывается из app.main)."""
    app.middleware("http")(dispatch)
