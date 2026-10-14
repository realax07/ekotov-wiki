"""Домен view-модалки карточки (change add-r4-user-profile-ticket-view,
tasks.md 4.1; FR-47, Д-9, ОГР-18; дельта board ADDED Requirement
«Просмотр карточки задачи — модальное окно read-only», все 5 сценариев —
первичный источник поведения; формат — tests/web/test_tooltip_r4.py;
TC-ID продолжают нумерацию Релиза 4: TC-view-101…).

board, ADDED «Просмотр карточки задачи — модальное окно read-only»:
- клик по карточке → view со всеми данными, комментарии видны,
  ввод и сохранение недоступны (сценарий 1, FR-47)
                                    → TC-view-101 test_card_click_opens_readonly_view;
- view не содержит элементов редактирования, кроме «Редактировать»
  (сценарий 2, ОГР-18)
                                    → TC-view-102 test_view_has_no_edit_elements;
- «Редактировать» → существующая форма редактирования (сценарий 3, Д-9)
                                    → TC-view-103 test_edit_button_opens_task_form;
- Escape и крестик закрывают view, данные не изменяются (сценарий 5)
                                    → TC-view-104 test_escape_closes_view
                                    → TC-view-105 test_cross_closes_view;
- assigned/creator в view: ряды при наличии полей в ответе API,
  «Unassigned» em при пустом (сценарий 4, ОВ-24)
                                    → TC-view-106 test_user_rows_when_api_provides
                                    → TC-view-107 test_unassigned_em_when_empty;
- fast-задача корректна во view (признак «Fast line: да»)
                                    → TC-view-108 test_fast_task_shown_in_view;
- клик по карточке из результатов поиска → view (BUG-001-регресс,
  FR-10/CHK-E-17 на новой механике 4.1)
                                    → TC-view-109 test_search_card_click_opens_view.

Комментарии во view (сценарии 1/4) — read-only список; форма добавления —
в task-form (режим редактирования), ее регресс покрыт test_board_tasks_ui
(TC-UI-014/015, адаптированы под 4.1).
"""

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui
from tests.web.pages.board import BoardPage
from tests.web.pages.search import SearchPage
from tests.web.pages.task_detail import TaskDetailView
from tests.web.pages.task_form import TaskForm

pytestmark = [pytest.mark.web, pytest.mark.must]





def _card_task_id(card) -> int:
    return int(card.get_attribute("data-task-id"))


def _open_view(page, title: str):
    """Клик по карточке → открыта view-модалка с заголовком задачи
    (якорь — #task-detail-title: heading матчится и на заголовок карточки)."""
    board = BoardPage(page)
    detail = TaskDetailView(page)
    board.card(title).click()
    detail.wait_open()
    expect(detail.title).to_have_text(title)


# --------------------------------------------------------------------------
# TC-view-101 — сценарий 1: клик по карточке открывает окно просмотра
# --------------------------------------------------------------------------
def test_card_click_opens_readonly_view(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-view-101: задача со всеми признаками и комментарием; клик по
    карточке → view: название, описание, приоритет, категория, срок, теги,
    комментарий — все значения видны; полей ввода и сохранения нет (FR-47)."""
    board = BoardPage(board_page)
    form = TaskForm(board_page)
    detail = TaskDetailView(board_page)
    page = board_page
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": "QAT-view-полная",
            "description": "Описание для просмотра",
            "priority": "high",
            "category": "Дом",
            "due_date": "2026-12-31",
            "tags": ["дом", "просмотр"],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    web_cleanup_created(task_id)
    assert web_owner_session.post(
        f"{web_base_url}/api/tasks/{task_id}/comments",
        json={"body": "Коммент во view"},
    ).status_code == 201, "комментарий не создался"
    page.reload()
    expect(board.board).to_have_attribute("data-loaded", "true")

    _open_view(page, "QAT-view-полная")

    attrs = detail.attrs
    for value in ("Описание для просмотра", "high", "Дом", "2026-12-31",
                  "дом, просмотр"):
        expect(attrs.get_by_text(value, exact=True)).to_be_visible()
    # Комментарии видны во view (сценарии 1/4) — read-only список.
    expect(detail.comments.get_by_text("Коммент во view")
           ).to_be_visible()
    # Ввод и сохранение недоступны: ни одного input/textarea/select
    # внутри view-модалки (без «Редактировать» данные не изменить).
    assert detail.inputs().count() == 0


# --------------------------------------------------------------------------
# TC-view-102 — сценарий 2: окно просмотра отлично от форм (ОГР-18)
# --------------------------------------------------------------------------
def test_view_has_no_edit_elements(board_page, web_cleanup_created):
    """TC-view-102: во view нет полей ввода, кнопки сохранения, удаления
    и селекта «Столбец»; из действий — только «Редактировать» (Д-9) и
    закрытие. Оформление — класс .task-view (не .task-form)."""
    board = BoardPage(board_page)
    form = TaskForm(board_page)
    detail = TaskDetailView(board_page)
    page = board_page
    create_task_via_ui(page, "QAT-view-чистая")
    card = board.card("QAT-view-чистая")
    web_cleanup_created(_card_task_id(card))

    _open_view(page, "QAT-view-чистая")

    modal = detail.modal
    assert "task-view" in (modal.get_attribute("class") or "")
    assert "task-form" not in (modal.get_attribute("class") or "")
    assert detail.inputs().count() == 0
    buttons = detail.buttons()
    names = sorted(t for t in buttons.all_inner_texts() if t)
    assert names == sorted(["Редактировать", "Закрыть"]), names
    # Крестик — отдельная кнопка закрытия view (aria-label).
    expect(detail.close_cross).to_be_visible()
    # Форма комментария — не во view (она в режиме редактирования, скрыта).
    assert not form.comment_form.is_visible()


# --------------------------------------------------------------------------
# TC-view-103 — сценарий 3: «Редактировать» открывает форму (Д-9)
# --------------------------------------------------------------------------
def test_edit_button_opens_task_form(board_page, web_cleanup_created):
    """TC-view-103: «Редактировать» из view → существующая форма
    редактирования ЭТОЙ задачи (заголовок, поля заполнены значениями)."""
    board = BoardPage(board_page)
    form = TaskForm(board_page)
    detail = TaskDetailView(board_page)
    page = board_page
    create_task_via_ui(page, "QAT-view-редактор", description="до правки")
    card = board.card("QAT-view-редактор")
    web_cleanup_created(_card_task_id(card))

    _open_view(page, "QAT-view-редактор")
    detail.edit_button().click()

    expect(form.overlay).to_be_visible()
    expect(detail.overlay).to_be_hidden()
    expect(form.heading_edit
           ).to_be_visible()
    assert form.title_by_id().input_value() == "QAT-view-редактор"
    assert form.description_by_id().input_value() == "до правки"
    # Действия задачи — в форме редактирования (4.1): селект «Столбец»,
    # «Удалить», комментарии.
    expect(form.actions).to_be_visible()
    expect(form.delete_button()).to_be_visible()
    expect(form.comment_form).to_be_visible()
    # Обратный путь без изменений — «Отмена» закрывает форму.
    page.get_by_role("button", name="Отмена").click()
    expect(form.overlay).to_be_hidden()


# --------------------------------------------------------------------------
# TC-view-104/105 — сценарий 5: закрытие (Escape, крестик) без изменений
# --------------------------------------------------------------------------
def test_escape_closes_view(board_page, web_base_url, web_owner_session,
                            web_cleanup_created):
    """TC-view-104: Escape закрывает view; данные задачи не изменяются
    (после закрытия карточка на месте, значения прежние)."""
    board = BoardPage(board_page)
    form = TaskForm(board_page)
    detail = TaskDetailView(board_page)
    page = board_page
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-view-escape", "priority": "low"},
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])
    page.reload()
    expect(board.board).to_have_attribute("data-loaded", "true")

    _open_view(page, "QAT-view-escape")
    page.keyboard.press("Escape")
    expect(detail.overlay).to_be_hidden()

    # Данные не изменены (сценарий 5): переоткрытие — те же значения.
    _open_view(page, "QAT-view-escape")
    expect(detail.attrs.get_by_text("low", exact=True)
           ).to_be_visible()
    detail.close_button().click()


def test_cross_closes_view(board_page, web_cleanup_created):
    """TC-view-105: крестик (#task-view-close) закрывает view без
    изменения данных; доска в прежнем состоянии."""
    board = BoardPage(board_page)
    form = TaskForm(board_page)
    detail = TaskDetailView(board_page)
    page = board_page
    create_task_via_ui(page, "QAT-view-крестик")
    card = board.card("QAT-view-крестик")
    web_cleanup_created(_card_task_id(card))

    _open_view(page, "QAT-view-крестик")
    detail.close_cross.click()
    expect(detail.overlay).to_be_hidden()
    expect(card).to_be_visible()


# --------------------------------------------------------------------------
# TC-view-106/107 — сценарий 4: assigned/creator (ОВ-24, гвард по hasOwnProperty)
# --------------------------------------------------------------------------
def test_user_rows_when_api_provides(board_page, web_base_url,
                                     web_owner_session, web_cleanup_created):
    """TC-view-106: assigned/creator-ряды выводятся ТОЛЬКО при наличии
    полей в ответе GET /api/tasks/{id} (задача 5.1; данные не выдумываются):
    фильтр-роут перехватывает ответ API, добавляет поля — ряды появляются
    с логинами; при пустом assigned — курсивом «Unassigned» (ОВ-24)."""
    board = BoardPage(board_page)
    form = TaskForm(board_page)
    detail = TaskDetailView(board_page)
    page = board_page
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "QAT-view-юзеры"}
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])
    page.reload()
    expect(board.board).to_have_attribute("data-loaded", "true")

    def with_users(route):
        import json
        response = route.fetch()
        body = json.loads(response.text())
        body["assigned"] = None  # пустой assigned → «Unassigned»
        body["creator"] = "owner"
        route.fulfill(response=response, json=body)

    page.route("**/api/tasks/*", with_users)
    _open_view(page, "QAT-view-юзеры")

    attrs = detail.attrs
    expect(attrs.get_by_text("Создатель")).to_be_visible()
    expect(attrs.get_by_text("owner", exact=True)).to_be_visible()
    expect(attrs.get_by_text("Исполнитель")).to_be_visible()
    unassigned = attrs.locator("em.task-view-unassigned")
    expect(unassigned).to_be_visible()
    assert unassigned.inner_text() == "Unassigned"
    assert "italic" in unassigned.evaluate("el => getComputedStyle(el).fontStyle")
    page.unroute("**/api/tasks/*")


def test_unassigned_em_when_empty(board_page, web_base_url,
                                  web_owner_session, web_cleanup_created):
    """TC-view-107 (после 5.1): задача создана без исполнителя →
    в view-модалке ряд «Исполнитель» показывает курсивный
    «Unassigned» (ОВ-24), ряд «Создатель» — логин создателя
    (контракт 5.1: creator/assigned в ответе всегда)."""
    board = BoardPage(board_page)
    form = TaskForm(board_page)
    detail = TaskDetailView(board_page)
    page = board_page
    create_task_via_ui(page, "QAT-view-без-юзеров")
    card = board.card("QAT-view-без-юзеров")
    web_cleanup_created(_card_task_id(card))

    _open_view(page, "QAT-view-без-юзеров")
    attrs = detail.attrs
    unassigned = attrs.locator("em.task-view-unassigned")
    expect(unassigned).to_have_text("Unassigned")
    expect(unassigned).to_have_css("font-style", "italic")
    expect(attrs.get_by_text("owner")).to_be_visible()


# --------------------------------------------------------------------------
# TC-view-108 — fast-задача корректна во view
# --------------------------------------------------------------------------
def test_fast_task_shown_in_view(board_page, web_base_url, web_owner_session,
                                 web_cleanup_created):
    """TC-view-108: fast-задача в view показывает признак «Fast line: да»;
    заголовок на месте (fast line не мешает открытию просмотра)."""
    board = BoardPage(board_page)
    form = TaskForm(board_page)
    detail = TaskDetailView(board_page)
    page = board_page
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-view-fast", "is_fast": True},
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])
    page.reload()
    expect(board.board).to_have_attribute("data-loaded", "true")

    _open_view(page, "QAT-view-fast")
    attrs = detail.attrs
    expect(attrs.get_by_text("Fast line")).to_be_visible()
    expect(attrs.get_by_text("да", exact=True)).to_be_visible()
    detail.close_button().click()


# --------------------------------------------------------------------------
# TC-view-109 — BUG-001-регресс: клик из поиска открывает view
# --------------------------------------------------------------------------
def test_search_card_click_opens_view(page, web_base_url, board_page,
                                      web_owner_session, web_cleanup_created):
    """TC-view-109: REGRESSION BUG-001 (FR-10/CHK-E-17) на механике 4.1 —
    клик по карточке из результатов поиска открывает view-модалку с
    признаками задачи (read-only), комментарии видны."""
    board = BoardPage(board_page)
    form = TaskForm(board_page)
    detail = TaskDetailView(board_page)
    search = SearchPage(page)
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": "QAT-view-поиск",
            "description": "найди меня",
            "priority": "medium",
            "tags": ["поиск2026"],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    web_cleanup_created(task_id)
    assert web_owner_session.post(
        f"{web_base_url}/api/tasks/{task_id}/comments",
        json={"body": "Коммент из поиска"},
    ).status_code == 201

    page.goto(f"{web_base_url}/search")
    # Режим advanced — фильтр по тегу (поля фильтра: priority/category/
    # tag/due/due_before/due_after/archived; свободного текста нет).
    search.advanced_button.click()
    search.advanced_query.fill('tag IN ("поиск2026")')
    search.find_button().click()
    results = search.results
    expect(results.get_by_role("article").filter(
        has_text="QAT-view-поиск")).to_be_visible()

    results.get_by_role("article").filter(has_text="QAT-view-поиск").click()
    expect(detail.overlay).to_be_visible()
    # Локатор скоуплен на OVERLAY: карточка в #search-results за модалкой —
    # тоже heading с тем же именем, голый get_by_role дает strict violation.
    expect(detail.overlay.get_by_role(
        "heading", name="QAT-view-поиск")).to_be_visible()
    attrs = detail.attrs
    expect(attrs.get_by_text("найди меня", exact=True)).to_be_visible()
    expect(attrs.get_by_text("medium", exact=True)).to_be_visible()
    expect(attrs.get_by_text("поиск2026", exact=True)).to_be_visible()
    expect(detail.comments.get_by_text("Коммент из поиска")
           ).to_be_visible()
    # Search-модалка тоже read-only (4.1): без полей ввода.
    assert detail.inputs().count() == 0
    detail.close_button().click()
    expect(detail.overlay).to_be_hidden()
