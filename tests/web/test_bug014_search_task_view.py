"""BUG-014: просмотр карточки из advanced-поиска — единый рендер с доской.

Трассировка: BUG-014-SM-001 (BUG-014-search-task-view-unify.md, критерий
закрытия «Карточка из advanced-поиска открывается визуально идентично
окну из доски»); BUG-013 закрыт как дубль (жалоба п.1 — тот же старый
рендер из поиска).

Смоук унификации (Флоу 2, фикс-цикл BUG-014):
- разметка окна на /search — дословно досочная (search.html = board.html:
  #task-view-close, role=dialog, #task-edit-button, футер actions);
- открытие карточки из ПОИСКА строит блоки мокапа
  design/polish-ticket-modal.html: шапка .task-view-head (кикер +
  .badge-row с бейджами приоритета/статуса), тело .task-view-body с
  сеткой признаков .attr-grid (категория/срок/fast line/оценка);
- СТАРАЯ разметка отсутствует: заголовок больше не «голый» h2 до шапки
  (title живет внутри .task-view-head), локальный старый рендер
  search.js выведен из эксплуатации;
- контракт сохранен: #task-detail-attrs содержит ровно значения задачи
  (TC-UI-009), бейдж «Архивная» при archived_at, комментарии;
- из поиска «Редактировать» недоступен (форма задачи живет на доске) —
  кнопка скрыта;
- computed styles ключевых селекторов совпадают с окном доски (та же
  разметка + board.css в base.html — стили общие).

Среда: автостенд tests/web (conftest), маркер web.
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.web, pytest.mark.must]

OVERLAY = "#task-detail-overlay"


def _create_task(web_owner_session, web_base_url, web_cleanup_created, title):
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": title,
            "description": "Описание задачи BUG-014",
            "priority": "high",
            "category": "Дом",
            "due_date": "2026-12-31",
            "tags": ["bug014"],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    web_cleanup_created(task_id)
    return task_id


def _open_from_advanced_search(page, web_base_url, title):
    """Контракт «Открыть из результатов поиска»: advanced-режим → фильтр
    по тегу → «Найти» → клик по карточке в выдаче."""
    page.goto(f"{web_base_url}/search")
    page.get_by_role("button", name="Advanced").click()
    query_box = page.get_by_label("Фильтр (SQL-подобный синтаксис)")
    query_box.fill('tag IN ("bug014")')
    page.locator("#search-advanced").get_by_role(
        "button", name="Найти"
    ).click()
    card = page.locator("#search-results").get_by_role("article").filter(
        has_text=title
    )
    expect(card).to_be_visible()
    card.click()
    expect(page.locator(OVERLAY)).to_be_visible()


def test_search_task_view_uses_board_render(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """BUG-014: карточка из advanced-поиска — разметка task-view доски.

    .task-view-head (шапка мокапа) + .badge-row + .task-view-body с
    .attr-grid присутствуют; старый локальный рендер отсутствует
    (заголовок внутри шапки, голых элементов старого окна нет);
    #task-detail-attrs содержит значения задачи; бейдж «Архивная» и
    комментарии на месте; «Редактировать» из поиска скрыт.
    """
    page = logged_in_page
    _create_task(
        web_owner_session, web_base_url, web_cleanup_created, "QAT-bug014"
    )

    _open_from_advanced_search(page, web_base_url, "QAT-bug014")

    modal = page.locator(f"{OVERLAY} .modal")

    # Рендер тела асинхронен (GET /api/tasks/{id}) — ждем сетку признаков.
    expect(modal.locator(".task-view-head")).to_be_visible()
    expect(modal.locator(".task-view-body")).to_be_visible()
    expect(modal.locator(".attr-grid")).to_be_visible()

    # Кикер шапки мокапа («Задача · STAND-<id>») и бейдж-ряд.
    kicker = modal.locator(".task-view-kicker")
    expect(kicker).to_contain_text("Задача · STAND-")
    expect(modal.locator(".badge-row")).to_be_visible()
    expect(modal.locator(".badge-row .badge").first).to_be_visible()

    # Заголовок — внутри шапки (рендер task-detail.js), не «голый» h2
    # старого окна; текст = название задачи.
    expect(modal.locator(".task-view-head #task-detail-title")).to_have_text(
        "QAT-bug014"
    )

    # СТАРЫЙ рендер отсутствует: признаки сеткой (.attr-grid) — а не
    # только старым dt/dd-списком без сетки; старого «плоского» окна
    # (h2 до какой-либо шапки) нет по построению разметки.
    grid_terms = modal.locator(".attr-grid .attr dt")
    expect(grid_terms).to_have_count(4)  # категория/срок/fast line/оценка

    # Контракт attrs (TC-UI-009): ровно значения задачи.
    attrs = modal.locator("#task-detail-attrs")
    for value in ("high", "Дом", "2026-12-31", "bug014"):
        expect(attrs.get_by_text(value, exact=True)).to_be_visible()

    # Комментарии: секция на месте (пусто — элементов нет, данных нет).
    expect(modal.locator(".task-view-comments")).to_be_visible()

    # «Редактировать» из поиска недоступен (форма задачи — на доске):
    # кнопка есть в разметке (дословно досочной), но скрыта.
    edit_button = modal.locator("#task-edit-button")
    expect(edit_button).to_be_hidden()

    # Крестик (#task-view-close) — досочный путь закрытия.
    expect(modal.locator("#task-view-close")).to_be_visible()
    modal.locator("#task-view-close").click()
    expect(page.locator(OVERLAY)).to_be_hidden()


def test_search_task_view_computed_styles_match_board(
    board_page, logged_in_page, web_base_url, web_owner_session,
    web_cleanup_created,
):
    """BUG-014, критерий закрытия: computed styles окна из ПОИСКА = окну
    из ДОСКИ по ключевым селекторам (та же разметка + общий board.css).

    Окно открывается из поиска, стили сравниваются с эталонными
    значениями мокапа, зафиксированными регрессионным тестом доски
    (TC-view-110, test_bug013_attrs_padding.py).
    """
    page = logged_in_page
    _create_task(
        web_owner_session, web_base_url, web_cleanup_created, "QAT-bug014-st"
    )
    # board_page в сигнатуре фиксирует, что доска загружается на той же
    # странице-фикстуре (единый контекст браузера, как в других кейсах).
    del board_page

    _open_from_advanced_search(page, web_base_url, "QAT-bug014-st")

    styles = page.evaluate(
        """() => {
          const modal = document.querySelector(
            "#task-detail-overlay .modal");
          const body = modal.querySelector(".task-view-body");
          const grid = modal.querySelector(".attr-grid");
          const attr = modal.querySelector(".attr");
          const head = modal.querySelector(".task-view-head");
          return {
            modalClass: modal.className,
            headPadding: getComputedStyle(head).padding,
            bodyPadding: getComputedStyle(body).padding,
            gridDisplay: getComputedStyle(grid).display,
            gridColumns: getComputedStyle(grid).gridTemplateColumns,
            attrPadding: getComputedStyle(attr).padding,
            editHidden: modal.querySelector("#task-edit-button").hidden,
          };
        }"""
    )

    # Мокап (арбитр polish-ticket-modal.html; эталон — TC-view-110):
    # шапка var(--space-3) var(--space-4) var(--space-2) = 24px 32px 16px;
    # тело var(--space-2) var(--space-4) = 16px 32px; карточка признака
    # var(--space-1) var(--space-2) = 8px 16px; сетка — 2 колонки.
    assert styles["modalClass"] == "modal task-view", styles
    assert styles["headPadding"] == "24px 32px 16px", styles
    assert styles["bodyPadding"] == "16px 32px", styles
    assert styles["gridDisplay"] == "grid", styles
    assert len(styles["gridColumns"].split()) == 2, styles
    assert styles["attrPadding"] == "8px 16px", styles
    assert styles["editHidden"] is True, styles
