"""Дельта auth/me (Релиз 3, change add-r3-visual-foundation, FR-33/NFR-7).

Дополняет tests/api/test_auth_me.py (TC-auth-018/019/020) кейсами
QA-этапа 5: TC-authme-001…003 — изоляция параллельных сессий,
401 (без сессии и с истекшей), read-only семантика повторных вызовов.

Кейсы_TC (approved test-model/approved/add-r3-visual-foundation/):
- TC-authme-001: сессии owner и wife не смешиваются — каждый /api/auth/me
  возвращает логин СВОЕЙ сессии (тело ТОЧНО {"user": "<login>"}).
- TC-authme-002: без куки — 401 {"error": "unauthorized"} без Set-Cookie;
  сессия с expires_at в прошлом — тоже 401 с тем же телом (эндпоинт вне
  exempt-списка, NFR-7).
- TC-authme-003: read-only (ОГР-13) — 4 повторных вызова дают идентичные
  200-ответы, повторный вход owner по тому же паролю работает.
"""

import pytest
import requests

pytestmark = [pytest.mark.api]

UNAUTHORIZED = {"error": "unauthorized"}

# Импорты из conftest (pytest добавляет tests/api в sys.path)
from conftest import (  # noqa: E402
    OWNER_LOGIN,
    OWNER_PASSWORD,
    WIFE_LOGIN,
    WIFE_PASSWORD,
    login_session,
)


# --------------------------------------------------------------------------
# TC-authme-001 — «GET /api/auth/me: 200 с логином своей сессии» (Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_me_parallel_sessions_keep_own_logins(base_url):
    """TC-authme-001: две параллельные сессии (owner, wife); /api/auth/me
    в каждой — 200 с ключом "user" = логин СВОЕЙ сессии (состав ответа
    расширен в Релизе 4 — change add-r4-user-profile-ticket-view,
    tasks.md 2.1; ключ "user" сохранен, sdd §3.1a-кватер); сессии не
    смешиваются (шаги 2 и 4 кейса)."""
    session_a = login_session(base_url, OWNER_LOGIN, OWNER_PASSWORD)  # шаг 1
    session_b = login_session(base_url, WIFE_LOGIN, WIFE_PASSWORD)  # шаг 3
    try:
        resp_a = session_a.get(f"{base_url}/api/auth/me")  # шаг 2
        assert resp_a.status_code == 200
        assert resp_a.json()["user"] == "owner"

        resp_b = session_b.get(f"{base_url}/api/auth/me")  # шаг 4 (B)
        assert resp_b.status_code == 200
        assert resp_b.json()["user"] == "wife"

        resp_a2 = session_a.get(f"{base_url}/api/auth/me")  # шаг 4 (A снова)
        assert resp_a2.status_code == 200
        assert resp_a2.json()["user"] == "owner"
    finally:
        session_a.close()
        session_b.close()


# --------------------------------------------------------------------------
# TC-authme-002 — «401 без сессии и с истекшей сессией» (Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_me_401_without_session_and_expired(base_url, owner_session, expire_session):
    """TC-authme-002: шаг 1 — без куки 401 с телом ТОЧНО
    {"error": "unauthorized"} и без Set-Cookie; шаг 2 — после сдвига
    expires_at в БД та же сессия — тоже 401 с тем же телом (middleware,
    эндпоинт вне exempt-списка, NFR-7)."""
    # Шаг 1 (+ повторная сверка шага 3): свежая сессия БЕЗ куки.
    fresh = requests.Session()
    try:
        resp = fresh.get(f"{base_url}/api/auth/me")
        assert resp.status_code == 401
        assert resp.json() == UNAUTHORIZED
        assert "set-cookie" not in {k.lower() for k in resp.headers}
    finally:
        fresh.close()

    # Шаг 2: прямой сдвиг expires_at в БД (EKOTOV_WIKI_DB_PATH стенда).
    expire_session(owner_session)
    resp_expired = owner_session.get(f"{base_url}/api/auth/me")
    assert resp_expired.status_code == 401
    assert resp_expired.json() == UNAUTHORIZED
    assert "set-cookie" not in {k.lower() for k in resp_expired.headers}


# --------------------------------------------------------------------------
# TC-authme-003 — «read-only: повторные вызовы не меняют состояние» (Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_me_read_only_repeated_calls_stable(base_url):
    """TC-authme-003: 4 вызова /api/auth/me в одной сессии — 200 с
    идентичным телом и неизменным логином сессии (read-only, никаких
    INSERT/UPDATE; состав тела расширен в Релизе 4 — ключ "user"
    сохранен, sdd §3.1a-кватер); повторный вход owner по тому же паролю
    работает."""
    session = login_session(base_url, OWNER_LOGIN, OWNER_PASSWORD)
    try:
        first = session.get(f"{base_url}/api/auth/me")
        assert first.status_code == 200
        expected = first.json()
        assert expected["user"] == "owner"

        # Шаг 2: три повторных вызова — идентичный результат.
        for _ in range(3):
            resp = session.get(f"{base_url}/api/auth/me")
            assert resp.status_code == 200
            assert resp.json() == expected

        # Шаг 3: повторный вход owner тем же паролем работает.
        again = login_session(base_url, OWNER_LOGIN, OWNER_PASSWORD)
        try:
            resp = again.get(f"{base_url}/api/auth/me")
            assert resp.status_code == 200
            assert resp.json()["user"] == "owner"
        finally:
            again.close()
    finally:
        session.close()
