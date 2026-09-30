"""Поиск по assigned/creator (5.2, change add-r4-user-profile-ticket-view).

Контракт (sdd §3.5 Релиз 4; дельта search «Поиск через API» MODIFIED):
- GET /api/search: параметры `assigned` (login | none = без исполнителя),
  `creator` (login); несуществующий логин → 422; ответ — Task с полями
  creator/assigned (логины; assigned=null у задачи без исполнителя).
- POST /api/search/advanced: грамматика дополнена полями assigned/creator
  с операторами `=` и `IS NULL`; normalized_query синхронно; 400 на
  синтаксическую ошибку.

TC-ID: TC-search-r4-001…008. Формат: 1 кейс = 1 тест (contract 6).
Трассировка: FR-46 (фильтры assigned/creator, «без исполнителя», = /
IS NULL, 422 на невозможное значение), FR-45 (creator/assigned в каждой
строке ответа поиска), ОВ-24 (assigned=null / «Unassigned»).
Тесты по задачам пакета и сценариям дельты search (approved-кейсов qa
на R4.2 нет — QA-цикл 6.1 впереди; в отчете ПМ).
"""

import pytest

pytestmark = [pytest.mark.api]

# Логины seed-пользователей (tests/api/conftest.py: owner/wife).
OWNER = "owner"
WIFE = "wife"


@pytest.fixture
def r4_search_fixtures(api):
    """Данные 5.2: t-assigned (assigned=wife), t-unassigned (assigned=null);
    creator у обеих — owner (сессия api). Назначение — PATCH
    assigned_to_id (контракт 5.1, sdd §3.2)."""
    with_assigned = api.create_ok("QAT-R4S-с-исполнителем")
    resp = api.session.get(f"{api.base_url}/api/users")
    assert resp.status_code == 200
    users = {u["login"]: u["id"] for u in resp.json()["users"]}
    resp = api.patch(with_assigned["id"], assigned_to_id=users[WIFE])
    assert resp.status_code == 200, resp.text

    unassigned = api.create_ok("QAT-R4S-без-исполнителя")
    return {
        "with_assigned": with_assigned,
        "unassigned": unassigned,
        "user_ids": users,
    }


def _titles(resp):
    return [t["title"] for t in resp.json()["results"]]


@pytest.mark.must
def test_search_filter_by_assigned(api, r4_search_fixtures):
    """TC-search-r4-001 (FR-46): GET /api/search?assigned=wife — только
    задачи с исполнителем wife; каждая с полями assigned/creator (FR-45)."""
    resp = api.search(assigned=WIFE)
    assert resp.status_code == 200
    titles = _titles(resp)
    assert "QAT-R4S-с-исполнителем" in titles
    assert "QAT-R4S-без-исполнителя" not in titles
    for task in resp.json()["results"]:
        assert task["assigned"] == WIFE
        assert task["creator"] == OWNER


@pytest.mark.must
def test_search_filter_assigned_none_unassigned_only(api, r4_search_fixtures):
    """TC-search-r4-002 (FR-46, ОВ-24): GET /api/search?assigned=none —
    только задачи БЕЗ исполнителя (assigned_to_id IS NULL)."""
    resp = api.search(assigned="none")
    assert resp.status_code == 200
    titles = _titles(resp)
    assert "QAT-R4S-без-исполнителя" in titles
    assert "QAT-R4S-с-исполнителем" not in titles
    for task in resp.json()["results"]:
        assert task["assigned"] is None


@pytest.mark.must
def test_search_filter_by_creator(api, r4_search_fixtures):
    """TC-search-r4-003 (FR-46): GET /api/search?creator=owner — задачи,
    созданные owner (обе тестовые); creator в каждой строке (FR-45)."""
    resp = api.search(creator=OWNER)
    assert resp.status_code == 200
    titles = _titles(resp)
    assert "QAT-R4S-с-исполнителем" in titles
    assert "QAT-R4S-без-исполнителя" in titles
    for task in resp.json()["results"]:
        assert task["creator"] == OWNER


@pytest.mark.must
def test_search_unknown_user_422(api):
    """TC-search-r4-004 (FR-46, «422 на невозможное значение»):
    assigned/creator = несуществующий логин → 422."""
    resp = api.search(assigned="no-such-user")
    assert resp.status_code == 422
    resp = api.search(creator="no-such-user")
    assert resp.status_code == 422


@pytest.mark.must
def test_search_results_contain_creator_assigned(api, r4_search_fixtures):
    """TC-search-r4-005 (FR-45, ОВ-24, sdd §3.2): ЛЮБОЙ ответ поиска
    (в т.ч. без фильтров) содержит creator (login) и assigned
    (login | null) в каждой задаче."""
    resp = api.search()
    assert resp.status_code == 200
    for task in resp.json()["results"]:
        assert "creator" in task and isinstance(task["creator"], str)
        assert "assigned" in task
        assert task["assigned"] is None or isinstance(task["assigned"], str)


@pytest.mark.must
def test_advanced_assigned_eq_and_is_null(api, r4_search_fixtures):
    """TC-search-r4-006 (FR-46): advanced `assigned = "wife"` и
    `assigned IS NULL` — выборка по исполнителю/без; normalized_query
    синхронно отражает условие."""
    resp = api.advanced(f'assigned = "{WIFE}"')
    assert resp.status_code == 200
    assert resp.json()["normalized_query"] == f'assigned = "{WIFE}"'
    assert "QAT-R4S-с-исполнителем" in _titles(resp)
    assert "QAT-R4S-без-исполнителя" not in _titles(resp)

    resp = api.advanced("assigned IS NULL")
    assert resp.status_code == 200
    assert resp.json()["normalized_query"] == "assigned IS NULL"
    assert "QAT-R4S-без-исполнителя" in _titles(resp)
    assert "QAT-R4S-с-исполнителем" not in _titles(resp)


@pytest.mark.must
def test_advanced_creator_eq_combined(api, r4_search_fixtures):
    """TC-search-r4-007 (FR-46): advanced `creator = "owner" AND
    assigned IS NULL` — комбинация И; normalized синхронен."""
    resp = api.advanced(f'creator = "{OWNER}" AND assigned IS NULL')
    assert resp.status_code == 200
    assert (
        resp.json()["normalized_query"]
        == f'creator = "{OWNER}" AND assigned IS NULL'
    )
    assert _titles(resp) == ["QAT-R4S-без-исполнителя"]


@pytest.mark.must
def test_advanced_assigned_creator_syntax_errors_400(api):
    """TC-search-r4-008 (FR-46, дельта «Негативный: некорректный фильтр»):
    `assigned != ...` (не поддерживается), `assigned IS` / `IS null`
    (незакрытый/строчный NULL), неизвестное поле — 400 filter syntax."""
    for bad in ('assigned != "wife"', "assigned IS", "assigned IS null"):
        resp = api.advanced(bad)
        assert resp.status_code == 400, (bad, resp.status_code, resp.text)
        assert resp.json()["error"].startswith("filter syntax")
