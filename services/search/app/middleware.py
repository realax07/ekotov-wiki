"""Сессионный middleware search-сервиса — локальная копия backend/app/middleware.py@HEAD.

Задача 1.1 (add-microservices-full), design §2: «схема не публикуется
без сессии тем же middleware-паттерном». Различия от ядра — осознанные:

- страницы (302 → /login) сервису не нужны: сервис — чистый API, любой
  не-api запрос без сессии → 401 (в ядре страницы рендерит app; design §2
  «страницы /search в сервис НЕ входят»);
- роутера /api/auth/login в сервисе нет — путь оставлен в exempt-списке
  для дословного соответствия паттерну ядра (запрос не заматчится);
- валидация сессии (таблица sessions, скользящий TTL) — дословно ядро.
"""

from datetime import datetime, timedelta, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.db import get_connection

# Дословно backend/app/auth.py (константы сессии; SESSION_TTL используется
# скользящим продлением ниже — тот же источник, что Max-Age куки ядра).
SESSION_COOKIE_NAME = "session"
SESSION_TTL = timedelta(days=30)

# Исчерпывающий exempt-список (метод, путь) — как в backend/app/middleware.py.
EXEMPT_API: set[tuple[str, str]] = {
    ("POST", "/api/auth/login"),
    ("GET", "/api/health"),
}

# Единый текст middleware-401 (sdd.md r4 §3).
UNAUTHORIZED_BODY = {"error": "unauthorized"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_valid(conn, token: str) -> bool:
    """Токен есть в sessions и не истек (design.md §2)."""
    row = conn.execute(
        "SELECT expires_at FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    if row is None:
        return False
    expires_at = datetime.fromisoformat(row[0])
    if expires_at <= _utcnow():
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        return False
    return True


def _slide_ttl(conn, token: str) -> None:
    """Скользящее продление: expires_at = now + TTL (design.md §2)."""
    conn.execute(
        "UPDATE sessions SET expires_at = ? WHERE token = ?",
        ((_utcnow() + SESSION_TTL).isoformat(), token),
    )
    conn.commit()


async def dispatch(request: Request, call_next):
    path = request.url.path

    if (request.method, path) in EXEMPT_API:
        return await call_next(request)

    token = request.cookies.get(SESSION_COOKIE_NAME)
    valid = False
    if token:
        conn = get_connection()
        try:
            valid = _is_valid(conn, token)
            if valid:
                _slide_ttl(conn, token)
        finally:
            conn.close()
    if valid:
        return await call_next(request)

    # Сервис — чистый API (design §2: страницы /search не входят):
    # без валидной сессии — 401, включая /openapi.json (схема не
    # публикуется без сессии — тот же запрет, что в ядре).
    return JSONResponse(status_code=401, content=UNAUTHORIZED_BODY)


def register(app) -> None:
    """Подключает middleware к приложению (вызывается из app.main)."""
    app.middleware("http")(dispatch)
