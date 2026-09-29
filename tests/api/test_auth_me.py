"""Дельта auth (Релиз 3, change add-r3-visual-foundation, FR-33/NFR-7).

Requirement «API текущего пользователя»
(openspec/changes/add-r3-visual-foundation/specs/auth/spec.md):
GET /api/auth/me — 200 {"user": "<login>"} из действующей сессии;
401 {"error": "unauthorized"} без сессии (эндпоинт вне exempt-списка,
NFR-7); read-only (ОГР-13). login резолвится JOIN sessions→users по
токену куки — middleware логин не резолвит (З-1 ревью-001).

Кейсы_TC (файл теста по Scenario дельты; TC-трассировка в docstring):
- TC-auth-018 (Scenario «Текущий пользователь определен по сессии»):
  вход owner → GET /api/auth/me — 200, тело точно {"user": "owner"}.
- TC-auth-019 (Scenario «Второй пользователь получает свой логин»):
  параллельная сессия wife → 200 {"user": "wife"}; логин соответствует
  своей сессии (JOIN по токену, а не «первый пользователь системы»).
- TC-auth-020 (Scenario «Негативный: без сессии — 401»): без куки — 401
  {"error": "unauthorized"}; с просроченной сессией — 401 (сессия не
  принимается); exempt-список не расширен (login/health — единственные
  без-сессионные пути, дельта auth NFR-7).
"""

import pytest
import requests

pytestmark = [pytest.mark.api]

UNAUTHORIZED = {"error": "unauthorized"}

# Импорты из conftest (pytest добавляет tests/api в sys.path)
from conftest import login_session, OWNER_LOGIN  # noqa: E402


# --------------------------------------------------------------------------
# TC-auth-018 — Scenario «Текущий пользователь определен по сессии» (Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_me_returns_login_of_session(base_url, owner_session):
    """TC-auth-018: пользователь авторизован (действующая сессия, логин
    owner); GET /api/auth/me — 200 с ключом "user": "owner" (логин
    соответствует сессии, JOIN sessions→users по токену куки, З-1
    ревью-001). Состав ответа Р4 (change add-r4-user-profile-ticket-view,
    tasks.md 2.1, MODIFIED-дельта) добавляет display_name/role/bio/
    avatar_url; здесь проверяется ключевая обратная совместимость — ключ
    "user" с логином сессии."""
    resp = owner_session.get(f"{base_url}/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["user"] == OWNER_LOGIN


# --------------------------------------------------------------------------
# TC-auth-019 — Scenario «Второй пользователь получает свой логин» (Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_me_second_user_gets_own_login(base_url, owner_session, wife_session):
    """TC-auth-019: wife авторизована в СВОЕЙ сессии (owner — в своей);
    GET /api/auth/me из сессии wife — 200 с "user": "wife": каждый
    пользователь получает логин своей сессии, не чужой (состав Р4 см.
    test_auth_me.py TC-auth-018 / test_profile_r4.py)."""
    resp_wife = wife_session.get(f"{base_url}/api/auth/me")
    assert resp_wife.status_code == 200
    assert resp_wife.json()["user"] == "wife"

    # сессии не смешиваются: owner в этот же момент получает свой логин
    resp_owner = owner_session.get(f"{base_url}/api/auth/me")
    assert resp_owner.status_code == 200
    assert resp_owner.json()["user"] == "owner"


# --------------------------------------------------------------------------
# TC-auth-020 — Scenario «Негативный: без сессии — 401» (Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_me_without_session_401(base_url, http, owner_session, expire_session):
    """TC-auth-020: без сессии (нет куки) — 401, тело точно
    {"error": "unauthorized"} (текст middleware — эндпоинт вне
    exempt-списка, NFR-7); после истечения expires_at в БД та же кука —
    тоже 401 (сессия не принимается); Set-Cookie в 401 нет."""
    # 1) запрос вовсе без куки
    resp = http.get(f"{base_url}/api/auth/me")
    assert resp.status_code == 401
    assert resp.json() == UNAUTHORIZED
    assert "set-cookie" not in {k.lower() for k in resp.headers}

    # 2) просроченная сессия — middleware не пропускает (design.md §2)
    expire_session(owner_session)
    resp_expired = owner_session.get(f"{base_url}/api/auth/me")
    assert resp_expired.status_code == 401
    assert resp_expired.json() == UNAUTHORIZED

    # 3) вход в этот же тесте работает (exempt не тронут), сессия жива
    fresh = login_session(base_url, OWNER_LOGIN, "QaOwner_Pass_1!")
    try:
        assert fresh.get(f"{base_url}/api/auth/me").status_code == 200
    finally:
        fresh.close()
