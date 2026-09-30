"""Домен assigned/creator в UI доски (change add-r4-user-profile-ticket-view,
tasks.md 5.1; FR-44, FR-45, ОВ-24/25/26, Д-10; дельта board MODIFIED —
«Отображение канбан-доски»; формат — tests/web/test_view_modal_r4.py;
TC-ID продолжают нумерацию Релиза 4: TC-assignu-101…).

board, Scenario «Строка исполнителя на карточке без assigned»:
- em «Unassigned» на карточке, курсивом (ОВ-24)
                                    → TC-assignu-101 test_card_unassigned_italic;
board, Scenario «Строка исполнителя на карточке с assigned» + «Открытие доски»:
- строка «assigned · creator» на карточках всех столбцов и fast line
  (FR-45)                          → TC-assignu-102 test_card_users_line_all_columns;
board, Scenario «Tooltip карточки показывает assigned и creator»:
- hover по карточке → всплывашка с assigned и creator (FR-44)
                                    → TC-assignu-103 test_card_tooltip_shows_users;
дельта board «Уменьшение движения отключает анимации всплывашек»:
- prefers-reduced-motion → показ без transition, содержание то же (ОГР-17)
                                    → TC-assignu-104 test_card_tooltip_reduced_motion;
tasks, Scenario «Select исполнителя — из пользователей системы» (форма
создания и редактирования; ОВ-26, Д-10):
- select #task-assigned наполняется из GET /api/users (owner, wife),
  опция «Не назначено» первой, подпись display_name||login
                                    → TC-assignu-105 test_create_form_assigned_select_from_users;
- выбранное значение приходит в задачу; редактирование — select показывает
  текущего исполнителя; очистка («Не назначено») → assigned=null
                                    → TC-assignu-106 test_edit_form_assigned_current_and_clear;
tasks, Scenario «Creator не выбирается в форме» (FR-37):
- поля creator в форме нет
                                    → TC-assignu-107 test_form_has_no_creator_field.
"""

import json

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui

pytestmark = [pytest.mark.web, pytest.mark.must]

OWNER_LOGIN = "owner"
WIFE_LOGIN = "wife"
WIFE_PASSWORD = "QaWife_Pass_2!"

TOOLTIP = "#app-tooltip"


def _card(page, title: str):
    return page.get_by_role("article").filter(has_text=title)


def _users_line(card):
    return card.locator(".task-card-users")


# --------------------------------------------------------------------------
# TC-assignu-101 — строка на карточке без assigned (ОВ-24)
# --------------------------------------------------------------------------
def test_card_unassigned_italic(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-assignu-101: задача без исполнителя → на карточке em «Unassigned»,
    курсивом; creator рядом (строка отображается ВСЕГДА)."""
    page = board_page
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "QAT-u-без-исполнителя"}
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    card = _card(page, "QAT-u-без-исполнителя")
    line = _users_line(card)
    expect(line).to_be_visible()
    unassigned = line.locator("em.task-card-unassigned")
    expect(unassigned).to_have_text("Unassigned")
    assert "italic" in unassigned.evaluate("el => getComputedStyle(el).fontStyle")
    expect(line.locator(".task-card-creator")).to_have_text(OWNER_LOGIN)


# --------------------------------------------------------------------------
# TC-assignu-102 — строка «assigned · creator» во всех столбцах и fast line
# --------------------------------------------------------------------------
def test_card_users_line_all_columns(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-assignu-102: карточки с assigned в todo и done и fast-карточка —
    везде строка «логин исполнителя · логин создателя» (FR-45, ОВ-24)."""
    page = board_page
    users = {
        u["login"]: u["id"]
        for u in web_owner_session.get(f"{web_base_url}/api/users").json()["users"]
    }
    todo = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": "QAT-u-todo",
            "assigned_to_id": users[WIFE_LOGIN],
        },
    )
    assert todo.status_code == 201, todo.text
    todo_id = todo.json()["id"]
    web_cleanup_created(todo_id)
    done = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": "QAT-u-done",
            "assigned_to_id": users[WIFE_LOGIN],
            "is_fast": True,
        },
    )
    assert done.status_code == 201, done.text
    done_id = done.json()["id"]
    web_cleanup_created(done_id)
    assert web_owner_session.post(
        f"{web_base_url}/api/tasks/{done_id}/move", json={"status": "done"}
    ).status_code == 200
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    for title, status in (("QAT-u-todo", "todo"), ("QAT-u-done", "done")):
        card = page.locator(f'[data-status="{status}"]').get_by_role("article").filter(
            has_text=title
        )
        line = _users_line(card)
        expect(line).to_be_visible()
        expect(line.locator(".task-card-assigned")).to_have_text(WIFE_LOGIN)
        expect(line.locator(".task-card-creator")).to_have_text(OWNER_LOGIN)

    # fast-карточка (done, is_fast) — строка та же (FR-45 «все столбцы
    # и fast line одинаково»).
    fast_card = page.locator('article[data-fast="true"]').filter(
        has_text="QAT-u-done"
    )
    expect(_users_line(fast_card)).to_be_visible()


# --------------------------------------------------------------------------
# TC-assignu-103 — tooltip карточки: assigned + creator (FR-44)
# --------------------------------------------------------------------------
def test_card_tooltip_shows_users(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-assignu-103: hover по карточке (задержка attach ~300мс) →
    #app-tooltip c «Исполнитель: wife» и «Создатель: owner» (сценарий:
    creator «owner», исполнитель «wife»); тот же элемент #app-tooltip,
    что у профиля (ОГР-17 — механизм един)."""
    page = board_page
    users = {
        u["login"]: u["id"]
        for u in web_owner_session.get(f"{web_base_url}/api/users").json()["users"]
    }
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-u-tooltip", "assigned_to_id": users[WIFE_LOGIN]},
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    card = _card(page, "QAT-u-tooltip")
    card.hover()
    expect(page.locator(TOOLTIP)).to_have_class(
        __import__("re").compile(r"\btooltip-visible\b"), timeout=5_000
    )
    tooltip = page.locator(TOOLTIP)
    expect(tooltip.locator(".tooltip-task-row").filter(has_text="Исполнитель:")
           ).to_contain_text(WIFE_LOGIN)
    expect(tooltip.locator(".tooltip-task-row").filter(has_text="Создатель:")
           ).to_contain_text(OWNER_LOGIN)

    card.hover()  # курсор остается; уводим — всплывашка скрылась
    page.mouse.move(10, 10)
    expect(page.locator(TOOLTIP)).not_to_have_class(
        __import__("re").compile(r"\btooltip-visible\b"), timeout=5_000
    )


# --------------------------------------------------------------------------
# TC-assignu-104 — reduced-motion: показ без анимации (ОГР-17, TC-vis-105)
# --------------------------------------------------------------------------
def test_card_tooltip_reduced_motion(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-assignu-104: prefers-reduced-motion=reduce → всплывашка
    появляется мгновенно (transition: none), содержание не меняется
    (assigned + creator на месте)."""
    page = board_page
    page.emulate_media(reduced_motion="reduce")
    users = {
        u["login"]: u["id"]
        for u in web_owner_session.get(f"{web_base_url}/api/users").json()["users"]
    }
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-u-rm", "assigned_to_id": users[WIFE_LOGIN]},
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    card = _card(page, "QAT-u-rm")
    card.hover()
    tooltip = page.locator(TOOLTIP)
    expect(tooltip).to_have_class(
        __import__("re").compile(r"\btooltip-visible\b"), timeout=5_000
    )
    transition = tooltip.evaluate("el => getComputedStyle(el).transitionDuration")
    assert transition.strip() in ("0s", "0s, 0s", "0.000s"), transition
    expect(tooltip.locator(".tooltip-task-row").filter(has_text="Исполнитель:")
           ).to_contain_text(WIFE_LOGIN)
    expect(tooltip.locator(".tooltip-task-row").filter(has_text="Создатель:")
           ).to_contain_text(OWNER_LOGIN)
    page.emulate_media(reduced_motion="no-preference")


# --------------------------------------------------------------------------
# TC-assignu-105 — select формы создания из GET /api/users (ОВ-26, Д-10)
# --------------------------------------------------------------------------
def test_create_form_assigned_select_from_users(board_page, web_base_url):
    """TC-assignu-105: открытие формы создания → #task-assigned содержит
    «Не назначено» (первая) + пользователей из GET /api/users (owner,
    wife); состав — данные эндпоинта, не хардкод."""
    page = board_page
    page.get_by_role("button", name="Создать задачу").click()
    select = page.locator("#task-assigned")
    expect(select.locator("option")).to_have_count(3, timeout=5_000)
    options = select.locator("option")
    expect(options.nth(0)).to_have_text("Не назначено")
    labels = [options.nth(i).inner_text() for i in range(3)]
    assert "owner" in labels and "wife" in labels, labels
    # Значения опций — id пользователей из /api/users (не логины).
    assert options.nth(1).get_attribute("value").isdigit()
    page.get_by_role("button", name="Отмена").click()


# --------------------------------------------------------------------------
# TC-assignu-106 — редактирование: текущее значение и очистка (ОВ-26)
# --------------------------------------------------------------------------
def test_edit_form_assigned_current_and_clear(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-assignu-106: задача с исполнителем wife → форма редактирования
    показывает wife; выбор «Не назначено» и сохранение → на карточке
    «Unassigned» курсивом; POST формы создает задачу с выбранным
    исполнителем (select_option → assigned_to_id в payload)."""
    page = board_page
    users = {
        u["login"]: u["id"]
        for u in web_owner_session.get(f"{web_base_url}/api/users").json()["users"]
    }
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-u-edit", "assigned_to_id": users[WIFE_LOGIN]},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    web_cleanup_created(task_id)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # Создание через форму: select исполнителя → задача получает wife.
    page.get_by_role("button", name="Создать задачу").click()
    page.get_by_label("Название").fill("QAT-u-create-select")
    page.get_by_label("Исполнитель").select_option(label=WIFE_LOGIN)
    page.get_by_role("button", name="Создать", exact=True).click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    new_card = _card(page, "QAT-u-create-select")
    expect(_users_line(new_card).locator(".task-card-assigned")
           ).to_have_text(WIFE_LOGIN)
    # Вторая задача тоже под cleanup (изоляция стенда: без этого она
    # переживает teardown и ломает count-ожидания соседних search-тестов —
    # assigned=none/wife возвращали лишнюю карточку).
    new_task_id = int(new_card.get_attribute("data-task-id"))
    web_cleanup_created(new_task_id)

    # Редактирование: select показывает текущего исполнителя (wife),
    # очистка «Не назначено» → сохранение → «Unassigned» на карточке.
    new_card.click()
    page.get_by_role("button", name="Редактировать").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    select = page.locator("#task-assigned")
    expect(select).to_have_value(str(users[WIFE_LOGIN]))
    select.select_option(label="Не назначено")
    page.get_by_role("button", name="Сохранить").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    unassigned = _users_line(new_card).locator("em.task-card-unassigned")
    expect(unassigned).to_have_text("Unassigned")
    assert "italic" in unassigned.evaluate("el => getComputedStyle(el).fontStyle")


# --------------------------------------------------------------------------
# TC-assignu-107 — creator в форме отсутствует (FR-37)
# --------------------------------------------------------------------------
def test_form_has_no_creator_field(board_page):
    """TC-assignu-107: в форме создания/редактирования нет поля creator —
    создатель определяется системой (сценарий «Creator не выбирается
    в форме»)."""
    page = board_page
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    assert page.locator("#task-form [name='creator_id']").count() == 0
    assert page.get_by_label("Создатель").count() == 0
    page.get_by_role("button", name="Отмена").click()
