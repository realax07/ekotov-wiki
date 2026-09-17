"""Middleware авторизации (tasks.md 2.2; sdd.md r4 §3, §3.6; design.md §2).

Правило (sdd.md §3): все запросы, кроме exempt-списка авторизации, требуют
валидную сессионную куку, иначе 401 {"error": "unauthorized"} — это текст
именно middleware (текст 401 login'а — другой: "invalid credentials").

Exempt-список — исчерпывающий, двум путям (дельта auth, Requirement
«Авторизация обязательна для API»):
  - POST /api/auth/login  — сам вход: сессию получить можно только здесь;
  - GET  /api/health      — health-check монитором/deploy до входа.
Любой прочий /api/* расширительного толкования не допускает → 401.

Страницы (не /api, sdd.md §3.6): без сессии — редирект на /login; сама
страница /login доступна без сессии (иначе вход невозможен). Статика
раздается nginx'ом и до приложения не доходит (design.md §8) — здесь
не обрабатывается. Сами страницы появятся в задачах 2.3/3.x — до тех пор
защищенный не-api GET без сессии дает 302 (ветка проверяется на любом пути).

Валидация сессии (design.md §2): токен из куки против таблицы sessions
(user_id, expires_at); просроченная сессия = запись удаляется (design.md §2
«Истечение = удаление записи сессии»), ответ — как без сессии.

Скользящее TTL (design.md §2): «продление — обновлением TTL при каждом
запросе». Троттлинг «раз в N минут» в design.md НЕ задан, поэтому expires_at
продлевается на каждый валидный запрос (SESSION_TTL из app.auth — тот же
источник, что и Max-Age куки задачи 2.1).
"""

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from app.auth import SESSION_COOKIE_NAME, SESSION_TTL
from app.db import get_connection

# Исчерпывающий exempt-список (метод, путь) — sdd.md r4 §3, дельта auth.
EXEMPT_API: set[tuple[str, str]] = {
    ("POST", "/api/auth/login"),
    ("GET", "/api/health"),
}

LOGIN_PAGE_PATH = "/login"  # sdd.md §3.6: страница входа доступна без сессии

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

    if path.startswith("/api"):
        # API без валидной сессии — 401 (sdd.md §3).
        return JSONResponse(status_code=401, content=UNAUTHORIZED_BODY)

    if path == LOGIN_PAGE_PATH:
        # Форма входа должна быть достижима без сессии (sdd.md §3.6).
        return await call_next(request)

    # Страница без сессии — редирект на /login (sdd.md §3.6, дельта auth).
    return RedirectResponse(url=LOGIN_PAGE_PATH, status_code=302)


def register(app) -> None:
    """Подключает middleware к приложению (вызывается из app.main)."""
    app.middleware("http")(dispatch)
