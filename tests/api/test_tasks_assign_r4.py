"""Домен assigned/creator в контрактах задач (change
add-r4-user-profile-ticket-view, tasks.md 5.1; FR-37, FR-44/45 — серверная
основа; sdd r10 §3.2; дельта tasks MODIFIED — «Создание задачи»,
«Признаки задачи», «Редактирование задачи»; формат — tests/api/test_users_r4.py;
TC-ID продолжают нумерацию Релиза 4: TC-assign-101…).

tasks, Scenario «Создание задачи с заполненными признаками» / «без исполнителя»:
- POST с assigned_to_id существующего → 201, assigned = его логин,
  creator = пользователь сессии (FR-37, ОВ-26)
                                    → TC-assign-101 test_post_with_assigned;
- POST без assigned_to_id → assigned = null (ОВ-26 опционально)
                                    → TC-assign-102 test_post_without_assigned;
- POST с assigned_to_id=null → null (легально, FR-37 nullable)
                                    → TC-assign-103 test_post_assigned_null;

tasks, Scenario «Негативный: assigned — только существующий пользователь»:
- POST с несуществующим assigned_to_id → 422, задача НЕ создана (FR-37)
                                    → TC-assign-104 test_post_unknown_user_422;
- PATCH с несуществующим → 422, значение не изменилось (та же валидация)
                                    → TC-assign-105 test_patch_unknown_user_422;

tasks, Scenario «Creator задачи неизменяем»:
- POST с creator_id в теле → 422 (поле не входит в контракт создания —
  сервер ставит сам, FR-37)
                                    → TC-assign-106 test_post_creator_id_rejected;
- PATCH с creator_id в теле → 422; без него creator не меняется
                                    → TC-assign-107 test_patch_creator_id_rejected;
- creator = пользователь сессии (owner создает — creator owner;
  wife создает — creator wife), смена исполнителя creator не трогает
                                    → TC-assign-108 test_creator_is_session_user;

tasks, Scenario «Признаки задачи» / «Просмотр признаков в карточке»:
- GET /api/tasks/{id} содержит creator и assigned (логины; null при
  пустом assigned) — состав ответа sdd §3.2
                                    → TC-assign-109 test_get_task_contains_users;
- GET /api/board — каждый Task содержит creator и assigned (ОВ-24)
                                    → TC-assign-110 test_board_contains_users;

tasks, Scenario «Назначение и смена исполнителя» / «Очистка исполнителя»:
- PATCH assigned_to_id → смена; PATCH assigned_to_id=null → очистка
  (assigned снова null)             → TC-assign-111 test_patch_assign_and_clear.
"""

import pytest

pytestmark = [pytest.mark.api, pytest.mark.must]

OWNER_LOGIN = "owner"
WIFE_LOGIN = "wife"


def _users_by_login(base_url, session) -> dict:
    resp = session.get(f"{base_url}/api/users")
    assert resp.status_code == 200, resp.text
    return {u["login"]: u["id"] for u in resp.json()["users"]}


# --------------------------------------------------------------------------
# TC-assign-101/102/103 — POST: assigned опционально (ОВ-26), creator сервер
# --------------------------------------------------------------------------
def test_post_with_assigned(base_url, owner_session):
    """TC-assign-101: POST с assigned_to_id=wife → 201; assigned='wife'
    в ответе; creator='owner' (пользователь сессии, FR-37)."""
    users = _users_by_login(base_url, owner_session)
    resp = owner_session.post(
        f"{base_url}/api/tasks",
        json={
            "title": "QAT-assign-с-исполнителем",
            "assigned_to_id": users[WIFE_LOGIN],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["assigned"] == WIFE_LOGIN
    assert body["creator"] == OWNER_LOGIN
    owner_session.delete(f"{base_url}/api/tasks/{body['id']}")


def test_post_without_assigned(base_url, owner_session):
    """TC-assign-102: POST без assigned_to_id → 201; assigned=null
    (ОВ-26: при создании опционально)."""
    resp = owner_session.post(
        f"{base_url}/api/tasks", json={"title": "QAT-assign-без-поля"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["assigned"] is None
    assert body["creator"] == OWNER_LOGIN
    owner_session.delete(f"{base_url}/api/tasks/{body['id']}")


def test_post_assigned_null(base_url, owner_session):
    """TC-assign-103: POST с assigned_to_id=null → 201; assigned=null
    (null = «без исполнителя», легально — FR-37 nullable)."""
    resp = owner_session.post(
        f"{base_url}/api/tasks",
        json={"title": "QAT-assign-явный-null", "assigned_to_id": None},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["assigned"] is None
    owner_session.delete(f"{base_url}/api/tasks/{body['id']}")


# --------------------------------------------------------------------------
# TC-assign-104/105 — негативный: assigned — только существующий пользователь
# --------------------------------------------------------------------------
def test_post_unknown_user_422(base_url, owner_session):
    """TC-assign-104: POST с несуществующим assigned_to_id → 422;
    задача не создана (сценарий «…задача не создается/не изменяется»)."""
    resp = owner_session.post(
        f"{base_url}/api/tasks",
        json={"title": "QAT-assign-чужак", "assigned_to_id": 10**9},
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error"] == "validation"
    # Найденный по названию задачи не существует — задача НЕ создана.
    found = owner_session.get(
        f"{base_url}/api/search", params={"archived": "all"}
    ).json()["results"]
    assert not any(t["title"] == "QAT-assign-чужак" for t in found)


def test_patch_unknown_user_422(base_url, owner_session):
    """TC-assign-105: PATCH с несуществующим assigned_to_id → 422;
    текущий исполнитель не изменился."""
    users = _users_by_login(base_url, owner_session)
    created = owner_session.post(
        f"{base_url}/api/tasks",
        json={
            "title": "QAT-assign-patch-чужак",
            "assigned_to_id": users[WIFE_LOGIN],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    try:
        resp = owner_session.patch(
            f"{base_url}/api/tasks/{task_id}", json={"assigned_to_id": 10**9}
        )
        assert resp.status_code == 422, resp.text
        after = owner_session.get(f"{base_url}/api/tasks/{task_id}").json()
        assert after["assigned"] == WIFE_LOGIN
    finally:
        owner_session.delete(f"{base_url}/api/tasks/{task_id}")


# --------------------------------------------------------------------------
# TC-assign-106/107 — creator не входит в контракт (FR-37)
# --------------------------------------------------------------------------
def test_post_creator_id_rejected(base_url, owner_session):
    """TC-assign-106: creator_id в теле POST → 422 (поле не принимается
    от клиента; creator ставит сервер)."""
    users = _users_by_login(base_url, owner_session)
    resp = owner_session.post(
        f"{base_url}/api/tasks",
        json={
            "title": "QAT-assign-creator-в-post",
            "creator_id": users[WIFE_LOGIN],
        },
    )
    assert resp.status_code == 422, resp.text


def test_patch_creator_id_rejected(base_url, owner_session, wife_session):
    """TC-assign-107: creator_id в теле PATCH → 422; creator задачи
    не изменяется (сценарий «Creator задачи неизменяем»)."""
    created = owner_session.post(
        f"{base_url}/api/tasks", json={"title": "QAT-assign-creator-patch"}
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    try:
        users = _users_by_login(base_url, wife_session)
        resp = wife_session.patch(
            f"{base_url}/api/tasks/{task_id}",
            json={"creator_id": users[WIFE_LOGIN]},
        )
        assert resp.status_code == 422, resp.text
        after = owner_session.get(f"{base_url}/api/tasks/{task_id}").json()
        assert after["creator"] == OWNER_LOGIN
    finally:
        owner_session.delete(f"{base_url}/api/tasks/{task_id}")


# --------------------------------------------------------------------------
# TC-assign-108 — creator = пользователь сессии, при любом редакторе
# --------------------------------------------------------------------------
def test_creator_is_session_user(base_url, owner_session, wife_session):
    """TC-assign-108: wife создает — creator='wife'; owner меняет
    исполнителя — creator остается 'wife' (FR-37: creator ставит сервер
    при создании и не изменяется редактированием)."""
    users = _users_by_login(base_url, owner_session)
    created = wife_session.post(
        f"{base_url}/api/tasks", json={"title": "QAT-assign-wife-автор"}
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    try:
        assert created.json()["creator"] == WIFE_LOGIN
        patched = owner_session.patch(
            f"{base_url}/api/tasks/{task_id}",
            json={"assigned_to_id": users[OWNER_LOGIN]},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["creator"] == WIFE_LOGIN
        assert patched.json()["assigned"] == OWNER_LOGIN
    finally:
        owner_session.delete(f"{base_url}/api/tasks/{task_id}")


# --------------------------------------------------------------------------
# TC-assign-109/110 — состав ответов GET /api/tasks/{id} и GET /api/board
# --------------------------------------------------------------------------
def test_get_task_contains_users(base_url, owner_session):
    """TC-assign-109: GET /api/tasks/{id} содержит creator (login) и
    assigned (login|null) — sdd r10 §3.2; при очистке assigned → null."""
    users = _users_by_login(base_url, owner_session)
    created = owner_session.post(
        f"{base_url}/api/tasks",
        json={
            "title": "QAT-assign-get",
            "assigned_to_id": users[WIFE_LOGIN],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    try:
        body = owner_session.get(f"{base_url}/api/tasks/{task_id}").json()
        assert body["creator"] == OWNER_LOGIN
        assert body["assigned"] == WIFE_LOGIN
        assert owner_session.patch(
            f"{base_url}/api/tasks/{task_id}", json={"assigned_to_id": None}
        ).status_code == 200
        body = owner_session.get(f"{base_url}/api/tasks/{task_id}").json()
        assert body["assigned"] is None
        assert body["creator"] == OWNER_LOGIN
    finally:
        owner_session.delete(f"{base_url}/api/tasks/{task_id}")


def test_board_contains_users(base_url, owner_session):
    """TC-assign-110: каждый Task в GET /api/board содержит creator и
    assigned (ОВ-24 — данные для строки карточки)."""
    users = _users_by_login(base_url, owner_session)
    created = owner_session.post(
        f"{base_url}/api/tasks",
        json={
            "title": "QAT-assign-board",
            "assigned_to_id": users[WIFE_LOGIN],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    try:
        columns = owner_session.get(f"{base_url}/api/board").json()["columns"]
        flat = [t for tasks in columns.values() for t in tasks]
        target = next(t for t in flat if t["id"] == task_id)
        assert target["creator"] == OWNER_LOGIN
        assert target["assigned"] == WIFE_LOGIN
        # Поля в КАЖДОЙ задаче ответа (строка на карточке — всегда, ОВ-24).
        assert all("creator" in t and "assigned" in t for t in flat)
    finally:
        owner_session.delete(f"{base_url}/api/tasks/{task_id}")


# --------------------------------------------------------------------------
# TC-assign-111 — смена и очистка исполнителя через PATCH
# --------------------------------------------------------------------------
def test_patch_assign_and_clear(base_url, owner_session):
    """TC-assign-111: PATCH меняет исполнителя; PATCH assigned_to_id=null
    очищает (assigned снова null) — сценарии «Назначение и смена…»,
    «Очистка исполнителя…»."""
    users = _users_by_login(base_url, owner_session)
    created = owner_session.post(
        f"{base_url}/api/tasks", json={"title": "QAT-assign-смена"}
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    try:
        first = owner_session.patch(
            f"{base_url}/api/tasks/{task_id}",
            json={"assigned_to_id": users[WIFE_LOGIN]},
        )
        assert first.status_code == 200 and first.json()["assigned"] == WIFE_LOGIN
        second = owner_session.patch(
            f"{base_url}/api/tasks/{task_id}",
            json={"assigned_to_id": users[OWNER_LOGIN]},
        )
        assert second.status_code == 200 and second.json()["assigned"] == OWNER_LOGIN
        cleared = owner_session.patch(
            f"{base_url}/api/tasks/{task_id}", json={"assigned_to_id": None}
        )
        assert cleared.status_code == 200 and cleared.json()["assigned"] is None
    finally:
        owner_session.delete(f"{base_url}/api/tasks/{task_id}")
