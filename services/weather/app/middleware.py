"""Сессионный middleware weather-сервиса — копия паттерна services/video
(а тот — services/images), БЕЗ authcheck-эндпоинта.

Change weather-service, design §5: auth_request в пакете НЕ используется
нигде (страница /weather рендерится ядром — nginx-локации для нее нет);
сессию проверяет этот middleware (без валидной сессии — 401
{"error": "unauthorized"}, NFR-7-паттерн). Валидация — SELECT-only
(app/db.py): удаление истекшей записи и скользящее продление TTL
остается ядру.

Exempt-список: только GET /api/health (healthcheck контейнера; без
бизнес-логики и без обращений к БД/провайдеру — design §6). /openapi.json
НЕ exempt — 401 анониму (паритет video/images).
"""

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.db import get_connection

# Имя куки сессии — дословно backend/app/middleware.py и services/*.
SESSION_COOKIE_NAME = "session"

# Исчерпывающий exempt-список (метод, путь) — healthcheck контейнера.
EXEMPT_API: set[tuple[str, str]] = {
    ("GET", "/api/health"),
}

# Единый текст middleware-401 (тот же текст, что у images/search/video/ядра).
UNAUTHORIZED_BODY = {"error": "unauthorized"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _user_id(conn, token: str) -> int | None:
    """id пользователя валидной сессии или None (SELECT-only)."""
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
        return await call_next(request)

    # Сервис — чистый API: без валидной сессии — 401, включая /openapi.json.
    # Обращений к провайдеру и к кэшу при этом НЕТ (spec «Негативный:
    # /api/weather без сессии»).
    return JSONResponse(status_code=401, content=UNAUTHORIZED_BODY)


def register(app) -> None:
    """Подключает middleware к приложению (вызывается из app.main)."""
    app.middleware("http")(dispatch)
