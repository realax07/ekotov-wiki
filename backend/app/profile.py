"""API профиля текущего пользователя (tasks.md 2.1/2.2; sdd.md §3.1a-кватер).

Контракты (sdd.md §3.1a-кватер):
- GET  /api/profile          → 200 {"login", "display_name", "role", "bio",
                               "avatar_url"}; 401 (middleware);
- PUT  /api/profile          → 200 (обновленный профиль); 422 — role вне
                               справочника, display_name/bio неверного типа;
- POST /api/profile/password → 200 {"ok": true} (сессии не трогаются, Д-11);
                               422 неверный текущий / пустой новый.

Все эндпоинты — вне exempt-списка (NFR-7): без сессии запрос не доходит до
роутера — middleware отвечает 401 {"error": "unauthorized"}. Оперируют только
пользователем сессии (JOIN sessions→users по токену куки — свой профиль,
FR-39; паттерн app/auth.py me, З-1 ревью-001).

Роль (ОВ-21): серверная валидация по фиксированному справочнику
['Product manager', 'Product engineer']; отображаемое поле — прав не
вводит (NFR-4). Пустой display_name допустим (Д-10: клиент показывает
логин); avatar_url не принимается от клиента — задается задачей 2.3
(POST /api/profile/avatar).

Смена пароля (Д-11): bcrypt.checkpw(current) → bcrypt.hashpw(new);
записи sessions не изменяются и не удаляются — текущая сессия (и прочие)
продолжают жить, принудительный re-login не требуется. Ошибка текущего
пароля — 422 {"error": "invalid current password"} (единый текст, не
раскрывать лишнее — по духу NFR-7); пароль при этом не меняется. Пустой
новый пароль — 422 {"error": "empty new password"}. Новый пароль хранится
только хешем (NFR-7). Требований к минимальной сложности нового пароля
(NFR) в спеке нет — проверяется только непустота (сд Scenario «Успешная
смена пароля»); политику сложности вводить запрещено (вне tasks.md).
"""

import sqlite3
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter
from pydantic import BaseModel, field_validator
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth import SESSION_COOKIE_NAME
from app.db import get_connection

router = APIRouter(prefix="/api/profile")

# Справочник ролей (ОВ-21) — фиксированный список значений.
VALID_ROLES = ("Product manager", "Product engineer")

# 422 role вне справочника (sdd §3.1a-кватер; ОВ-21).
ROLE_NOT_ALLOWED_422 = {
    "error": "validation error",
    "details": {"role": "not in directory"},
}

# 422 неверного текущего пароля — единый текст (design §2: не раскрывать
# лишнее, по духу NFR-7).
INVALID_CURRENT_PASSWORD_422 = {"error": "invalid current password"}

# 422 пустого нового пароля (sdd §3.1a-кватер: «пустой новый»).
EMPTY_NEW_PASSWORD_422 = {"error": "empty new password"}


class ProfileUpdate(BaseModel):
    # display_name/bio: str | None — типовая валидация каркасом
    # (не str → RequestValidationError → 422 {"error": "validation error",
    # "details": ...} через install_error_handlers, sdd §3). Пустая строка
    # нормализуется в None: null в ответах/БД = «не задано» (sdd
    # §3.1a-кватер: «пустые значения — null»), единое представление
    # для Д-10 (fallback на логин).
    display_name: str | None = None
    role: str | None = None
    bio: str | None = None

    @field_validator("display_name", "bio")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        return value if value not in ("",) else None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_by_session_token(conn: sqlite3.Connection, token: str | None):
    """Строка пользователя сессии (JOIN sessions→users по токену куки)."""
    if not token:
        return None
    return conn.execute(
        "SELECT u.id, u.login, u.display_name, u.role, u.bio,"
        " u.avatar_path, u.avatar_updated_at"
        " FROM sessions s JOIN users u ON u.id = s.user_id"
        " WHERE s.token = ?",
        (token,),
    ).fetchone()


def _avatar_url(row) -> str | None:
    """URL аватара (B-3 ревью review-001): NULL, если аватара нет —
    URL не строится, клиент рисует кружок с буквой (FR-33)."""
    if row[5] is None:
        return None
    return f"/avatars/{row[0]}.png?v={row[6]}"


def _profile_body(row) -> dict:
    return {
        "login": row[1],
        "display_name": row[2],
        "role": row[3],
        "bio": row[4],
        "avatar_url": _avatar_url(row),
    }


@router.get("")
def get_profile(request: Request) -> JSONResponse:
    """Профиль пользователя сессии (FR-36, FR-40; sdd §3.1a-кватер)."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    conn = get_connection()
    try:
        row = _user_by_session_token(conn, token)
    finally:
        conn.close()
    if row is None:
        # Сессия прошла middleware, но пользователь исчез — нет такого.
        return JSONResponse(status_code=404, content={"error": "not found"})
    return JSONResponse(content=_profile_body(row))


@router.put("")
def update_profile(body: ProfileUpdate, request: Request) -> JSONResponse:
    """Сохранение display_name/role/bio (FR-40; sdd §3.1a-кватер).

    Валидации: role — только из справочника (ОВ-21) → 422; типы полей —
    каркасом (pydantic → RequestValidationError → 422). Редактируется
    ТОЛЬКО пользователь сессии (FR-39). avatar_* поля не входят в контракт.
    """
    if body.role is not None and body.role not in VALID_ROLES:
        return JSONResponse(status_code=422, content=ROLE_NOT_ALLOWED_422)

    token = request.cookies.get(SESSION_COOKIE_NAME)
    conn = get_connection()
    try:
        row = _user_by_session_token(conn, token)
        if row is None:
            return JSONResponse(status_code=404, content={"error": "not found"})
        conn.execute(
            "UPDATE users SET display_name = ?, role = ?, bio = ? WHERE id = ?",
            (body.display_name, body.role, body.bio, row[0]),
        )
        conn.commit()
        updated = _user_by_session_token(conn, token)
    finally:
        conn.close()
    return JSONResponse(content=_profile_body(updated))


@router.post("/password")
def change_password(body: PasswordChange, request: Request) -> JSONResponse:
    """Смена пароля (FR-41, Д-11; sdd §3.1a-кватер).

    422 при неверном текущем пароле (пароль не меняется) или пустом новом;
    200 {"ok": true} — sessions не трогаются (текущая сессия живет, Д-11).
    """
    if not body.new_password:
        return JSONResponse(status_code=422, content=EMPTY_NEW_PASSWORD_422)

    token = request.cookies.get(SESSION_COOKIE_NAME)
    conn = get_connection()
    try:
        row = _user_by_session_token(conn, token)
        if row is None:
            return JSONResponse(status_code=404, content={"error": "not found"})
        user_id = row[0]

        stored = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        stored_hash = stored[0].encode("ascii")
        if not bcrypt.checkpw(body.current_password.encode("utf-8"), stored_hash):
            # Пароль НЕ меняется (дельта auth: «вход со старым паролем
            # продолжает работать»).
            return JSONResponse(
                status_code=422, content=INVALID_CURRENT_PASSWORD_422
            )

        new_hash = bcrypt.hashpw(
            body.new_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("ascii")
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id)
        )
        # Д-11: UPDATE/DELETE по sessions отсутствует намеренно —
        # текущая сессия (и параллельные) сохраняются.
        conn.commit()
    finally:
        conn.close()
    return JSONResponse(content={"ok": True})
