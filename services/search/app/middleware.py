"""Сессионный middleware search-сервиса — локальная копия backend/app/middleware.py@HEAD.

Задача 1.1 (add-microservices-full), design §2: «схема не публикуется
без сессии тем же middleware-паттерном». Различия от ядра — осознанные:

- страницы (302 → /login) сервису не нужны: сервис — чистый API, любой
  не-api запрос без сессии → 401 (в ядре страницы рендерит app; design §2
  «страницы /search в сервис НЕ входят»);
- роутера /api/auth/login в сервисе нет — путь оставлен в exempt-списке
  для дословного соответствия паттерну ядра (запрос не заматчится);
- валидация сессии — SELECT-only (ревью задачи 1.2): сервис читает том
  wiki-data:/data:ro, поэтому НИ удаление истекшей сессии, НИ скользящее
  продление TTL (UPDATE) невозможны — на ro-маунте они давали
  «attempt to write a readonly database» → 500. Проверка токена
  (сравнение expires_at с now) идентична ядру: безопасность не меняется.
  Скользящий TTL продлевает app (монолит обрабатывает все прочие запросы
  пользователя); истекшая сессия удаляет app своим _is_valid. Для сервиса
  истекшая сессия = просто «не валидна» (401), запись остается ядру.
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
    """Токен есть в sessions и не истек (design.md §2).

    SELECT-only (ro-маунт, ревью 1.2): в отличие от ядра истекшая запись
    НЕ удаляется (писать некуда) — для сервиса она просто «не валидна»;
    удаление выполняет app на своем запросе (backend/app/middleware.py).
    """
    row = conn.execute(
        "SELECT expires_at FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    if row is None:
        return False
    expires_at = datetime.fromisoformat(row[0])
    return expires_at > _utcnow()


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
