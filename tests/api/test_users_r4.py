"""Пользователи системы: GET /api/users (sdd.md r10 §3.1a-кватер-бис;
design.md §6; major B-1 ревью review-001; строка 5.1 tasks.md пакета).

TC-ID: TC-users-001, TC-users-002, TC-users-003, TC-users-004.
Формат: 1 кейс = 1 тест (contract 6); кейсы утверждаются QA-контуром
(задача 6.1 пакета, п. I3 — «GET /api/users: состав, сортировка, 401
без сессии»); настоящий файл — фикстуры запуска dev'а по контракту
sdd §3.1a-кватер-бис, трассировка ниже в docstring каждого теста.

Сценарии (по контракту sdd §3.1a-кватер-бис + design §6):
- 200 {"users": [{id, login, display_name}]} — все пользователи,
  сортировка по login (двое seed: owner, wife);
- display_name NULL → null в JSON (fallback «display_name или логин»
  решает клиент, Д-10 — сервер не подставляет);
- 401 без сессии (вне exempt-списка, NFR-7; единый текст middleware);
- сессия (owner) видит обоих пользователей; read-only — состав
  повторного ответа идентичен (состояние не изменяется, ОВ-21).

Условия прогона: живой стенд (EKOTOV_WIKI_BASE_URL) с seed owner/wife
(tests/README.md); состав пользователей — данные БД, тесты сверяются
с фиксированным seed-составом NFR-4 (регистрация отсутствует).
"""

import requests

from conftest import OWNER_LOGIN, WIFE_LOGIN

ENDPOINT = "/api/users"
MIDDLEWARE_401_BODY = {"error": "unauthorized"}  # app/middleware.py


def test_users_200_sorted_by_login_with_both_seed_users(
    base_url, owner_session
):
    """200: оба seed-пользователя, отсортированы по login, полный состав полей."""
    resp = owner_session.get(f"{base_url}{ENDPOINT}")
    assert resp.status_code == 200, f"{resp.status_code} {resp.text}"
    body = resp.json()
    assert set(body.keys()) == {"users"}, f"ключи тела: {body.keys()}"
    users = body["users"]
    # NFR-4: заведены двое seed'ом, регистрация отсутствует
    assert [u["login"] for u in users] == [OWNER_LOGIN, WIFE_LOGIN], (
        f"состав/сортировка: {users}"
    )
    for user in users:
        assert set(user.keys()) == {"id", "login", "display_name"}, user
        assert isinstance(user["id"], int), user
        assert isinstance(user["login"], str) and user["login"], user
        assert user["display_name"] is None or isinstance(
            user["display_name"], str
        ), user


def test_users_display_name_null_until_profile_filled(
    base_url, owner_session
):
    """display_name NULL → null в JSON до заполнения профиля (Д-10, клиент решает)."""
    resp = owner_session.get(f"{base_url}{ENDPOINT}")
    assert resp.status_code == 200, f"{resp.status_code} {resp.text}"
    by_login = {u["login"]: u for u in resp.json()["users"]}
    for login in (OWNER_LOGIN, WIFE_LOGIN):
        assert login in by_login, f"нет seed-пользователя {login!r}"
        assert by_login[login]["display_name"] is None, (
            f"display_name {login!r} до заполнения профиля должен быть null: "
            f"{by_login[login]}"
        )


def test_users_401_without_session(base_url):
    """Негатив: без сессии — 401 с единым текстом middleware (NFR-7, вне exempt)."""
    resp = requests.get(f"{base_url}{ENDPOINT}")
    assert resp.status_code == 401, f"{resp.status_code} {resp.text}"
    assert resp.json() == MIDDLEWARE_401_BODY, resp.text


def test_users_read_only_session_owner_sees_both_users(
    base_url, owner_session
):
    """Сессия видит обоих; read-only (ОВ-21): повторный вызов дает идентичный состав."""
    first = owner_session.get(f"{base_url}{ENDPOINT}")
    second = owner_session.get(f"{base_url}{ENDPOINT}")
    assert first.status_code == 200, f"{first.status_code} {first.text}"
    assert second.status_code == 200, f"{second.status_code} {second.text}"
    assert first.json() == second.json(), (
        f"read-only нарушен: {first.json()} != {second.json()}"
    )
    logins = [u["login"] for u in second.json()["users"]]
    assert OWNER_LOGIN in logins and WIFE_LOGIN in logins, logins
