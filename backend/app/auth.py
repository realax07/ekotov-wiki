"""Авторизация: POST /api/auth/login (tasks.md 2.1; sdd.md §3.1; design.md §2–3).

Механика (design.md §2): сессия = криптостойкий случайный токен (secrets,
256 бит энтропии ≥ 128 требуемых), выдаваемый после успешного логина; токен
в куку HttpOnly + SameSite=Lax + Secure; запись в таблицу sessions БД.
Без фреймворковых «магических» сессий — явный механизм (design.md §2).

TTL: 30 дней (design.md §2 «например, 30 дней бездействия»; FR-14 — сессии
«сохраняют логин»). Скользящее продление TTL при запросах — задача 2.2
(middleware); здесь фиксируется только начальный expires_at.

Проверка пароля (design.md §3): bcrypt.checkpw; для несуществующего логина
выполняется контрольная проверка против dummy-хеша той же стоимости — время
ответа не раскрывает существование логина (sdd §3.1, NFR-7).

Logout (POST /api/auth/logout) — контракт sdd.md §3.1, реализован в задаче
2.2 в app/main.py (роутер /api/auth + зависимость от middleware-проверки
сессии; в этом модуле намеренно не дублируется).
"""

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter
from pydantic import BaseModel
from starlette.responses import JSONResponse

from app.db import get_connection

router = APIRouter(prefix="/api/auth")

SESSION_COOKIE_NAME = "session"
SESSION_TTL = timedelta(days=30)  # design.md §2; источник TTL зафиксирован в отчете задачи 2.1
SESSION_TTL_SECONDS = int(SESSION_TTL.total_seconds())

# Единый текст ошибки для неверного логина И неверного пароля
# (sdd.md §3.1: «не раскрывать существование логина, NFR-7»).
INVALID_CREDENTIALS_BODY = {"error": "invalid credentials"}

# Dummy-хеш той же bcrypt-стоимости: проверка для несуществующего логина
# занимает сопоставимое время с проверкой реального пользователя.
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"\x00dummy-invalid-\x00", bcrypt.gensalt())


class LoginRequest(BaseModel):
    login: str
    password: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def unauthorized() -> JSONResponse:
    """401 с единым телом (sdd.md §3.1)."""
    return JSONResponse(status_code=401, content=INVALID_CREDENTIALS_BODY)


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    """Создает запись сессии (sdd.md §4), возвращает токен."""
    token = secrets.token_urlsafe(32)  # 256 бит энтропии (design.md §2: ≥128)
    now = _utcnow()
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (
            token,
            user_id,
            now.isoformat(),
            (now + SESSION_TTL).isoformat(),
        ),
    )
    conn.commit()
    return token


@router.post("/login")
def login(body: LoginRequest) -> JSONResponse:
    """Вход (sdd.md §3.1). 200 + кука сессии; 401 — единый текст ошибки."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE login = ?",
            (body.login,),
        ).fetchone()

        stored_hash = row[1].encode("ascii") if row is not None else _DUMMY_PASSWORD_HASH
        if not bcrypt.checkpw(body.password.encode("utf-8"), stored_hash):
            return unauthorized()

        token = create_session(conn, row[0])
    finally:
        conn.close()

    response = JSONResponse(content={"ok": True, "user": body.login})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=True,
        path="/",
    )
    return response
