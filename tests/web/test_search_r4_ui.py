"""UI поиска по assigned/creator (5.2, change add-r4-user-profile-ticket-view).

Сценарии дельты search (MODIFIED «Фильтр-конструктор», «Режим advanced»,
«Вкладка поиска старых задач»): фильтры assigned/creator в конструкторе
с подсказками из БД (механизм FR-35/DEF-001 — /api/suggestions/users) и
опцией «без исполнителя»; поля assigned/creator в advanced; выдача —
assigned/creator в каждой строке, «Unassigned» курсивом.

TC-ID: TC-search-r4-ui-001…004. Формат: 1 кейс = 1 тест (contract 6).
Трассировка: FR-46 (конструктор + advanced + подсказки из БД), FR-45
(assigned/creator в каждой строке выдачи), ОВ-24 («Unassigned» курсивом).
Тесты по задачам пакета и сценариям дельты search (approved-кейсов qa на
R4.2 нет — QA-цикл 6.1 впереди; в отчете ПМ).
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def _open_search(logged_in_page, web_base_url):
    """Открытая вкладка поиска (вход owner уже выполнен фикстурой)."""
    logged_in_page.goto(f"{web_base_url}/search")
    expect(logged_in_page.get_by_role("button", name="Конструктор")).to_be_visible()
    return logged_in_page


def _make_pair(web_owner_session, web_base_url, web_cleanup_created):
    """Пара задач через API: с исполнителем wife и без исполнителя."""
    resp = web_owner_session.get(f"{web_base_url}/api/users")
    assert resp.status_code == 200
    users = {u["login"]: u["id"] for u in resp.json()["users"]}

    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-R4UI-с-исполнителем"},
    )
    assert created.status_code == 201
    task_assigned = created.json()
    web_cleanup_created(task_assigned["id"])
    resp = web_owner_session.patch(
        f"{web_base_url}/api/tasks/{task_assigned['id']}",
        json={"assigned_to_id": users["wife"]},
    )
    assert resp.status_code == 200, resp.text

    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-R4UI-без-исполнителя"},
    )
    assert created.status_code == 201
    task_unassigned = created.json()
    web_cleanup_created(task_unassigned["id"])
    return task_assigned, task_unassigned


def test_builder_filters_assigned_creator_present_with_hints(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-search-r4-ui-001 (FR-46, подсказки из БД): в конструкторе есть
    фильтры «Исполнитель» и «Создатель»; у assigned — статическая опция
    «без исполнителя» (value=none); логины подсказываются из уникальных
    значений БД (GET /api/suggestions/users), а не из статического списка."""
    _make_pair(web_owner_session, web_base_url, web_cleanup_created)
    page = _open_search(logged_in_page, web_base_url)

    assigned = page.locator("#search-assigned")
    creator = page.locator("#search-creator")
    expect(assigned).to_be_visible()
    expect(creator).to_be_visible()

    # статические опции assigned: «любой» (пусто) + «без исполнителя» (none)
    expect(assigned.locator("option[value='none']")).to_have_text(
        "без исполнителя"
    )
    # creator: только «любой» до загрузки подсказок, без «none»
    expect(creator.locator("option[value='none']")).to_have_count(0)

    # подсказки из БД (механизм FR-35): логины из /api/suggestions/users
    resp = web_owner_session.get(f"{web_base_url}/api/suggestions/users")
    assert resp.status_code == 200
    users = resp.json()["users"]
    assert users, "подсказки пусты: задачи с creator/assigned не заведены"
    for login in users:
        expect(
            assigned.locator(f"option[value='{login}']")
        ).to_have_count(1)
        expect(
            creator.locator(f"option[value='{login}']")
        ).to_have_count(1)


def test_builder_filter_assigned_none_shows_unassigned_rows(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-search-r4-ui-002 (FR-46, ОВ-24, дельта «Фильтр «без исполнителя»»):
    выбор «без исполнителя» + «Найти» → в выдаче только задачи без
    исполнителя; в строке карточки — курсивный «Unassigned»."""
    _make_pair(web_owner_session, web_base_url, web_cleanup_created)
    page = _open_search(logged_in_page, web_base_url)

    page.locator("#search-assigned").select_option("none")
    page.locator("#search-builder-submit").click()

    results = page.locator("#search-results")
    expect(results.locator(".task-card")).to_have_count(1, timeout=5000)
    card = results.locator(".task-card").first
    expect(card).to_contain_text("QAT-R4UI-без-исполнителя")
    # ОВ-24: «Unassigned» — курсивный <em> в строке пользователей карточки
    unassigned = card.locator(".task-user-unassigned")
    expect(unassigned).to_have_text("Unassigned")
    expect(unassigned).to_have_css("font-style", "italic")
    # assigned-фильтр исключил задачу с исполнителем
    expect(results).not_to_contain_text("QAT-R4UI-с-исполнителем")


def test_builder_filter_assigned_by_login(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-search-r4-ui-003 (FR-46, дельта «Фильтр по исполнителю»):
    выбор исполнителя wife + «Найти» → только задачи с исполнителем wife;
    в строке карточки — логин исполнителя и создатель."""
    _make_pair(web_owner_session, web_base_url, web_cleanup_created)
    page = _open_search(logged_in_page, web_base_url)

    page.locator("#search-assigned").select_option("wife")
    page.locator("#search-builder-submit").click()

    results = page.locator("#search-results")
    expect(results.locator(".task-card")).to_have_count(1, timeout=5000)
    card = results.locator(".task-card").first
    expect(card).to_contain_text("QAT-R4UI-с-исполнителем")
    expect(card.locator(".task-user-assigned")).to_have_text("wife")
    expect(card.locator(".task-user-creator")).to_have_text("owner")
    expect(results).not_to_contain_text("QAT-R4UI-без-исполнителя")


def test_advanced_assigned_is_null_and_eq(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-search-r4-ui-004 (FR-46, дельта «Режим advanced»): в advanced
    условие `assigned = "wife"` и `assigned IS NULL` фильтруют выдачу;
    normalized_query показывается под полем (синхронизация)."""
    _make_pair(web_owner_session, web_base_url, web_cleanup_created)
    page = _open_search(logged_in_page, web_base_url)

    page.locator("#search-mode-advanced").click()
    query = page.locator("#search-advanced-query")

    query.fill('assigned = "wife"')
    page.locator("#search-advanced-submit").click()
    results = page.locator("#search-results")
    expect(results.locator(".task-card")).to_have_count(1, timeout=5000)
    expect(results).to_contain_text("QAT-R4UI-с-исполнителем")
    expect(page.locator("#search-advanced-normalized")).to_contain_text(
        'assigned = "wife"'
    )

    query.fill("assigned IS NULL")
    page.locator("#search-advanced-submit").click()
    expect(results.locator(".task-card")).to_have_count(1, timeout=5000)
    expect(results).to_contain_text("QAT-R4UI-без-исполнителя")
    # ОВ-24 в выдаче advanced-поиска: курсивный «Unassigned»
    unassigned = results.locator(".task-user-unassigned")
    expect(unassigned).to_have_text("Unassigned")
    expect(unassigned).to_have_css("font-style", "italic")
    expect(page.locator("#search-advanced-normalized")).to_contain_text(
        "assigned IS NULL"
    )
