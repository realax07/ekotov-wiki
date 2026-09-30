"""QA-цикл 6.1: stale-гвард сохранения формы (hotfix 71729ed).

Approved-кейс TC-assignu-201 (CHK-R4-104,
`test-model/new/add-r4-user-profile-ticket-view/`, review-009 APPROVE):
сбой/задержка GET /api/users НЕ превращает сохранение формы в молчаливую
очистку исполнителя (регрессия review-008 major: PATCH assigned_to_id:
null при незагруженном списке).

Механизм (примечание кейса, task-form.js): select наполняется только из
ответа GET /api/users (loadAssignedOptions); assignedLoaded поднимается
ТОЛЬКО в success-колбэке; collectTaskForm включает assigned_to_id в
payload ТОЛЬКО при assignedLoaded === true; токен assignedLoadGen
отсекает stale-ответы чужого открытия. Ключ не в payload → PATCH не
трогает колонку (model_fields_set).

Гонка моделируется route-перехватом **/api/users (abort / deferred
fulfill) — БЕЗ time.sleep; ожидания — только expect() c автоповтором
(прецеденты route-работы: test_view_modal_r4.py, test_r3_dnd_ui.py,
test_r3_profile_ui.py). Задачи — API-создание (по образцу TC-assignu-106)
+ web_cleanup_created.
"""

import json

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.web, pytest.mark.must]

WIFE = "wife"


def _card(page, title: str):
    return page.get_by_role("article").filter(has_text=title)


def _create_task_with_wife(web_owner_session, web_base_url, users, title) -> int:
    resp = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": title, "assigned_to_id": users[WIFE]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _reload_board(page):
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")


def _open_edit_form(page, title: str):
    """Клик по карточке → view → «Редактировать» → открытая форма."""
    _card(page, title).click()
    expect(page.locator("#task-detail-overlay")).to_be_visible()
    page.get_by_role("button", name="Редактировать").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()


# --------------------------------------------------------------------------
# TC-assignu-201, вариант А — route.abort: упавший GET /api/users
# --------------------------------------------------------------------------
def test_assignu_201_abort_users_save_keeps_assigned(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-assignu-201 вариант А (нег., Must): GET /api/users abort —
    форма редактирования открыта с пустым select; сохранение без выбора
    → PATCH-payload НЕ содержит ключ assigned_to_id (гвард assignedLoaded;
    не null!); карточка после закрытия формы по-прежнему показывает wife —
    молчаливой очистки НЕТ (регрессия hotfix 71729ed)."""
    page = board_page
    users = {
        u["login"]: u["id"]
        for u in web_owner_session.get(f"{web_base_url}/api/users").json()["users"]
    }
    task_id = _create_task_with_wife(
        web_owner_session, web_base_url, users, "QAT-u-stale"
    )
    web_cleanup_created(task_id)
    _reload_board(page)

    # Шаг 1: /api/users падает → select «Исполнитель» — только «Не
    # назначено» (список не загрузился: onError → fillAssignedSelect([],)),
    # assignedLoaded НЕ поднят (onError флаг не поднимает).
    page.route("**/api/users", lambda route: route.abort())
    _open_edit_form(page, "QAT-u-stale")
    select = page.locator("#task-assigned")
    expect(select.locator("option").first).to_have_text("Не назначено")
    expect(select).to_have_value("")

    # Шаг 2–3: сохранение, не выбирая ничего; перехват PATCH — payload
    # без ключа assigned_to_id (ключ отсутствует, не null).
    captured: list[dict] = []

    def capture_patch(route):
        request = route.request
        if request.method == "PATCH":
            captured.append(request.post_data_json)
        route.fallback()

    page.route("**/api/tasks/*", capture_patch)
    page.get_by_role("button", name="Сохранить").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    page.unroute("**/api/tasks/*")
    page.unroute("**/api/users")

    assert len(captured) == 1, f"ожидался ровно один PATCH: {captured}"
    assert "assigned_to_id" not in captured[0], (
        f"гвард нарушен: assigned_to_id в payload → молчаливая очистка: {captured[0]}"
    )

    # Карточка после закрытия формы — wife (не «Unassigned»): форма
    # перерисовывает доску только при успехе PATCH (refreshBoard), поэтому
    # карточка уже актуальна; состояние БД сверяем чтением API.
    line = _users_line_of(page, "QAT-u-stale")
    expect(line.locator(".task-card-assigned")).to_have_text(WIFE)
    assert not line.locator("em.task-card-unassigned").count()
    read_back = web_owner_session.get(f"{web_base_url}/api/tasks/{task_id}")
    assert read_back.status_code == 200
    assert read_back.json()["assigned"] == WIFE, read_back.json()


def _users_line_of(page, title: str):
    return _card(page, title).locator(".task-card-users")


# --------------------------------------------------------------------------
# TC-assignu-201, вариант Б — задержка fulfill: users приходят ПОСЛЕ save
# --------------------------------------------------------------------------
def test_assignu_201_deferred_users_fulfill_save_order(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-assignu-201 вариант Б (нег., Must): форма открыта при НЕ
    загруженном списке → «Сохранить» → PATCH ушел БЕЗ assigned_to_id
    (гвард не поднялся) → ПОТОМ приходит users (deferred fulfill — без
    sleep, из route-колбэка) → select наполняется в фоновой форме, второй
    PATCH не уходит; исполнитель в БД — wife. Альтернативный порядок
    (users пришли ДО сохранения, assignedLoaded=true) — ПАТТЕРН-КЛАДКА:
    payload содержит assigned_to_id=<id wife>, карточка — wife; оба
    исхода НЕ меняют исполнителя."""
    page = logged_in_page
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    users = {
        u["login"]: u["id"]
        for u in web_owner_session.get(f"{web_base_url}/api/users").json()["users"]
    }
    wife_id = users[WIFE]
    task_id = _create_task_with_wife(
        web_owner_session, web_base_url, users, "QAT-u-stale-2"
    )
    web_cleanup_created(task_id)
    _reload_board(page)

    deferred: list = []
    patches: list[dict] = []

    def hold_users(route):
        # Задержка без sleep: fulfill вызывается ПОЗЖЕ (после сохранения),
        # сам запрос висит, пока тест не разрешит.
        deferred.append(route)

    page.route("**/api/users", hold_users)
    _open_edit_form(page, "QAT-u-stale-2")
    # Список удержан: select пуст (опций нет, значение «Не назначено»).
    select = page.locator("#task-assigned")
    expect(select).to_have_value("")
    assert select.locator("option").count() == 0
    def capture_patch(route):
        if route.request.method == "PATCH":
            patches.append(route.request.post_data_json)
        route.fallback()

    page.route("**/api/tasks/*", capture_patch)
    page.get_by_role("button", name="Сохранить").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()

    # Форма закрылась; PATCH-порядок детерминирован: сохранение ушло при
    # незагруженном списке.
    assert len(patches) == 1, f"ровно один PATCH: {patches}"
    saved_before_users = "assigned_to_id" not in patches[0]

    # Отпускаем удержанный users: ответ приходит в фоновую (закрытую)
    # форму; второй PATCH не уходит (сохранение одно).
    for route in deferred:
        route.fallback()  # снять свой перехват → запрос уходит на стенд
    page.unroute("**/api/users")
    page.unroute("**/api/tasks/*")
    expect(_users_line_of(page, "QAT-u-stale-2").locator(".task-card-assigned")
           ).to_have_text(WIFE)

    if saved_before_users:
        # Основной порядок кейса: PATCH ушел БЕЗ assigned_to_id (гвард) —
        # поле не тронуто, БД: assigned = wife.
        assert "assigned_to_id" not in patches[0]
    else:
        # ПАТТЕРН-КЛАДКА: users успели до сохранения (assignedLoaded=true) —
        # payload легально содержит id wife (не null!).
        assert patches[0].get("assigned_to_id") == wife_id, patches[0]
    assert len(patches) == 1, "второй PATCH после прихода users не должен уходить"

    # Инвариант обоих порядков: исполнитель в БД не изменился; 5xx нет
    # (форма закрыта, карточка wife).
    read_back = web_owner_session.get(f"{web_base_url}/api/tasks/{task_id}")
    assert read_back.status_code == 200
    assert read_back.json()["assigned"] == WIFE, read_back.json()
    assert not _users_line_of(page, "QAT-u-stale-2").locator(
        "em.task-card-unassigned"
    ).count()


# --------------------------------------------------------------------------
# TC-assignu-201, вариант В — stale между задачами (токен assignedLoadGen)
# --------------------------------------------------------------------------
def test_assignu_201_stale_answer_of_task1_does_not_leak_into_task2(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-assignu-201 вариант В (нег., Must): открыта форма задачи-1
    (wife) → «Отмена» → открыта форма задачи-2 (без исполнителя);
    задержанный users-ответ ОТКРЫТИЯ задачи-1 приходит после открытия
    формы-2: select формы-2 НЕ получает значения задачи-1 (токен
    assignedLoadGen отсекает stale-ответ); сохранение формы-2 уходит с
    корректным assigned_to_id (null = легальная очистка ПОЛЬЗОВАТЕЛЕМ
    при загруженном списке, не системой)."""
    page = logged_in_page
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    users = {
        u["login"]: u["id"]
        for u in web_owner_session.get(f"{web_base_url}/api/users").json()["users"]
    }
    t1 = _create_task_with_wife(
        web_owner_session, web_base_url, users, "QAT-u-stale-т1"
    )
    t2_resp = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "QAT-u-stale-т2"}
    )
    assert t2_resp.status_code == 201, t2_resp.text
    t2 = t2_resp.json()["id"]
    web_cleanup_created(t1)
    web_cleanup_created(t2)
    _reload_board(page)

    # Форма задачи-1 открыта при удержанном users (задержка первого ответа).
    deferred: list = []
    generations: list[int] = []

    def hold_first_only(route):
        generations.append(1)
        if len(generations) == 1:
            deferred.append(route)  # только ПЕРВЫЙ запрос (открытие т1)
            return
        route.fallback()

    page.route("**/api/users", hold_first_only)
    _open_edit_form(page, "QAT-u-stale-т1")
    expect(page.locator("#task-assigned")).to_have_value("")

    # Закрыть «Отменой», открыть форму задачи-2 — второй users-ответ
    # проходит свободно (наполняет select формы-2, легальная очистка
    # возможна только теперь).
    page.get_by_role("button", name="Отмена").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    _open_edit_form(page, "QAT-u-stale-т2")
    select = page.locator("#task-assigned")
    # Список формы-2 загружен (второй запрос не удерживался): есть опции,
    # значение — «Не назначено» (у т2 исполнителя нет).
    expect(select.locator("option").first).to_have_text("Не назначено")
    expect(select).to_have_value("")

    # Освобождаем stale-ответ задачи-1: токен assignedLoadGen отсекает его —
    # select формы-2 НЕ подменяется значением т1 (wife).
    for route in deferred:
        route.fallback()
    page.unroute("**/api/users")
    expect(select).to_have_value("")  # не str(wife_id) — stale не применился

    # Сохранение формы-2: пользователь явно выбирает «Не назначено» →
    # payload assigned_to_id = null (легальная очистка пользователем,
    # список загружен); исполнитель т1 не затронут.
    patches: list[dict] = []

    def capture_patch(route):
        if route.request.method == "PATCH":
            patches.append(route.request.post_data_json)
        route.fallback()

    page.route("**/api/tasks/*", capture_patch)
    page.get_by_label("Название").fill("QAT-u-stale-т2-переименована")
    page.get_by_role("button", name="Сохранить").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    page.unroute("**/api/tasks/*")

    assert len(patches) == 1, f"ровно один PATCH формы-2: {patches}"
    assert patches[0].get("assigned_to_id", "absent") in (None,), (
        f"загруженный список → явный выбор «Не назначено» = null: {patches[0]}"
    )
    r1 = web_owner_session.get(f"{web_base_url}/api/tasks/{t1}")
    assert r1.status_code == 200 and r1.json()["assigned"] == WIFE, r1.json()
    r2 = web_owner_session.get(f"{web_base_url}/api/tasks/{t2}")
    assert r2.status_code == 200 and r2.json()["assigned"] is None, r2.json()
