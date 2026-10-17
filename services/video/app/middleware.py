"""Сессионный middleware video-сервиса — копия паттерна services/images.

Tasks 1.2 (video-hosting волна 1), design §8: все /api/videos* — за
сессионным middleware; без сессии — 401 {"error": "unauthorized"} (NFR-36).
Валидация сессии — SELECT-only (удаление истекшей записи и скользящее
продление TTL остается ядру); сервис НЕ имеет права писать в sessions
(design §7).

Отличие от images по exempt-списку (design §8 / sdd §3): плюс
GET /api/videos/authcheck — стык nginx auth_request (design §5):
subrequest без тяжелых БД-чтений; 200/401 эндпоинт решает сам
(app/videos.py). D-эндпоинты (кусок D) отдельных exempt-ов НЕ получают
(NFR-38) — они появятся уже за этим же middleware.
"""

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.db import get_connection

# Имя куки сессии — дословно backend/app/middleware.py и services/*.
SESSION_COOKIE_NAME = "session"

# Исчерпывающий exempt-список (метод, путь) — sdd §3: /api/health и
# /api/videos/authcheck; логина в сервисе нет.
EXEMPT_API: set[tuple[str, str]] = {
    ("GET", "/api/health"),
    ("GET", "/api/videos/authcheck"),
}

# Единый текст middleware-401 (sdd §3 — тот же текст, что у images/search/ядра).
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
        # Требование эндпоинтов: загрузка привязана к пользователю
        # (uploaded_by) — id кладем в request.state (паритет images).
        request.state.user_id = user_id
        return await call_next(request)

    # Сервис — чистый API: без валидной сессии — 401, включая /openapi.json.
    return JSONResponse(status_code=401, content=UNAUTHORIZED_BODY)


def register(app) -> None:
    """Подключает middleware к приложению (вызывается из app.main)."""
    app.middleware("http")(dispatch)
