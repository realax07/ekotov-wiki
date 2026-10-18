"""Домен navigation/search/archive: TC-UI-016, TC-UI-017, TC-UI-018 (CHK-E-16…18).

TC-UI-017 — наблюдение ревьюера: renderCard в search.js не вешает
click-обработчик (продуктовый дефект-кандидат). Тест написан по кейсу
как есть: падение на шаге 7 = баг-репорт, код теста не подгоняется.
TC-UI-017/018 используют DB-крюк (UPDATE tasks SET done_at) через
временную БД стенда (env EKOTOV_WIKI_DB_PATH задается conftest).
"""

import sqlite3

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui, move_via_card_select
from tests.web.pages.auth import Sidebar
from tests.web.pages.board import BoardPage
from tests.web.pages.search import SearchPage
from tests.web.pages.task_detail import TaskDetailView
from tests.web.pages.wiki import WikiPage

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def test_sidebar_all_pages_and_wiki_stub(logged_in_page, web_base_url):
    """TC-UI-016: сайдбар (5 пунктов: Доска/Поиск/Wiki/Галерея/Видео + бейдж
    todo) на всех страницах; Доска ↔ Поиск переключаются в обе стороны;
    Wiki — раздел с деревом/тулбаром (add-wiki, прежняя «заглушка без
    функций» устарела). 5-й пункт «Видео» — 1.5 video-hosting (дельта
    specs/video-service, утвержденный мокап 0.2)."""
    page = logged_in_page
    sidebar = Sidebar(page)
    search = SearchPage(page)
    board = BoardPage(page)
    wiki = WikiPage(page)
    for path in ("/board", "/search", "/wiki"):
        page.goto(f"{web_base_url}{path}")
        expect(sidebar.board_link).to_be_visible()
        expect(sidebar.search_link).to_be_visible()
        expect(sidebar.wiki_link).to_be_visible()
        expect(sidebar.gallery_link).to_be_visible()
        expect(sidebar.video_link).to_be_visible()
        # Ровно 5 пунктов навигации (по образцу test_p12_nav_icons_favicon_r8).
        expect(page.locator(".sidebar-nav .nav-item")).to_have_count(5)
        # Бейдж todo снят (решение Заказчика 2026-10-11, 4.5 add-wiki).

    # Доска → Поиск.
    page.goto(f"{web_base_url}/board")
    sidebar.search_link.click()
    expect(search.heading_exact()).to_be_visible()
    assert page.url.endswith("/search")
    expect(search.constructor_button).to_be_visible()
    expect(search.advanced_button).to_be_visible()

    # Поиск → Доска.
    sidebar.board_link.click()
    expect(board.heading()).to_be_visible()
    assert page.url.endswith("/board")

    # Доска → Wiki (add-wiki: раздел с деревом и тулбаром — поиск по
    # разделу + «Создать страницу»; прежние ассерты «заглушка без
    # функций» устарели после поставки add-wiki, пред-существующий фейл
    # из 36d1b14 снят).
    sidebar.wiki_link.click()
    expect(wiki.heading).to_be_visible()
    assert page.url.endswith("/wiki")
    # Скоуп на тулбар (паттерн test_p15_wiki_tree): на ПУСТОЙ wiki-БД
    # tree.js рисует вторую кнопку .wiki-create в пустом состоянии
    # («Создать первую страницу») — голый .wiki-create = strict violation.
    expect(page.locator(".wiki-toolbar .wiki-create")).to_be_visible()
    expect(page.locator("#wiki-search")).to_be_visible()


def _shift_done_at(db_path: str, title: str, done_at: str) -> None:
    """DB-крюк кейсов: смещение done_at в прошлое (вариант Б)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE tasks SET done_at = ? WHERE title = ?", (done_at, title))
        conn.commit()
    finally:
        conn.close()


def _msk_dates() -> tuple[str, str]:
    from datetime import datetime, timedelta, timezone

    MSK = timezone(timedelta(hours=3))
    now = datetime.now(MSK)
    return now.date().isoformat(), (now - timedelta(days=1)).date().isoformat()


def test_search_archived_task_builder_advanced_card(
    page, web_base_url, board_page, web_db_path, web_cleanup_created
):
    """TC-UI-017: поиск архивной задачи — конструктор (только совпавшие,
    бейдж «Архивная») → advanced (SQL-текст фильтра, правка применяется,
    нормализованный фильтр показан) → карточка архивной задачи открывается
    с признаками.

    CHK-146/TC-UI-017-update: категория в фильтре-конструкторе — select из
    справочника (FR-19/FR-30), ввод только select_option (ни одного .fill()
    на поле категории); «Дом» гарантирована seed'ом (CHK-139)."""
    today, yesterday = _msk_dates()
    board = BoardPage(page)
    search = SearchPage(page)
    detail = TaskDetailView(page)

    # Подготовка (вариант Б): задача → done → done_at вчера → автоархивация.
    create_task_via_ui(
        board_page,
        "Архивная-поиск",
        priority="high",
        category="Дом",
        tags="архив2026",
    )
    card = board.card("Архивная-поиск")
    expect(card).to_be_visible()
    web_cleanup_created(int(card.get_attribute("data-task-id")))
    move_via_card_select(board_page, "Архивная-поиск", "done")
    _shift_done_at(web_db_path, "Архивная-поиск", f"{yesterday}T15:00:00+03:00")
    page.reload()
    board.wait_loaded()
    expect(board.card("Архивная-поиск")).to_have_count(0)

    # Контрольная не-Дом задача: не должна попасть в результаты фильтра.
    create_task_via_ui(board_page, "Fast-первая", priority="high", is_fast=True)
    fast_card = board.card("Fast-первая")
    expect(fast_card).to_be_visible()
    web_cleanup_created(int(fast_card.get_attribute("data-task-id")))

    # Шаг 1–2: конструктор — категория «Дом» (select из справочника,
    # select_option вместо fill — CHK-146), только архивные.
    search.open(web_base_url)
    search.category_by_label().select_option("Дом")
    search.archived_select().select_option("true")
    search.builder_find_button().click()

    result_card = search.result_card("Архивная-поиск")
    expect(result_card).to_be_visible()
    expect(result_card.get_by_text("Архивная", exact=True)).to_be_visible()
    expect(search.result_card("Fast-первая")).to_have_count(0)

    # Шаг 4: переключение в advanced — поле содержит фильтр конструктора.
    search.advanced_button.click()
    query_box = search.filter_sql_input()
    value = query_box.input_value()
    assert 'category = "Дом"' in value, f"в поле нет category: {value!r}"
    assert "archived = true" in value, f"в поле нет archived: {value!r}"

    # Шаг 5: правка фильтра и применение.
    query_box.fill('priority = "high" AND archived = true')
    search.find_button().click()

    # Шаг 6: нормализованный фильтр показан, результат применен.
    normalized = search.normalized()
    expect(normalized).to_be_visible()
    assert normalized.inner_text().startswith("Нормализованный фильтр:")
    expect(search.result_card("Архивная-поиск")).to_be_visible()

    # Шаг 7: клик по карточке архивной задачи открывает карточку
    # с признаками (FR-10 / CHK-E-17; наблюдение ревьюера — renderCard
    # в search.js не вешает click-обработчик: если шаг падает — дефект).
    # Якорь открытия — МОДАЛКА карточки (#task-detail-overlay): heading
    # «Архивная-поиск» без якоря матчит и заголовок карточки в результатах.
    search.result_card("Архивная-поиск").click()
    detail.wait_open()
    # 4.1: якорь — #task-detail-title (heading матчится и на заголовок
    # карточки в результатах: strict violation).
    expect(detail.title).to_have_text("Архивная-поиск")
    expect(detail.archive_badge).to_be_visible()
    for term_value in ("high", "Дом", "архив2026"):
        expect(detail.attrs.get_by_text(term_value, exact=True)).to_be_visible()


def test_final_path_autoarchive_and_fast_release(
    page, web_base_url, board_page, web_db_path, web_cleanup_created
):
    """TC-UI-018: финал пути — done сегодня видима; смещение done_at на
    вчерашний МСК-день → автоархивация при первом чтении доски; задача
    найдена через поиск с бейджем «Архивная»; fast line освобождена."""
    today, yesterday = _msk_dates()
    board = BoardPage(page)
    search = SearchPage(page)

    # Шаг 0 подготовки: активная fast-задача «Fast-первая» (изолированный
    # setup вместо цепочки с TC-UI-010) → done → fast line свободна.
    create_task_via_ui(board_page, "Fast-первая", priority="high", is_fast=True)
    first_card = board.card("Fast-первая")
    expect(first_card).to_be_visible()
    web_cleanup_created(int(first_card.get_attribute("data-task-id")))
    move_via_card_select(board_page, "Fast-первая", "done")
    expect(board.card_in_column("done", "Fast-первая")).to_be_visible()
    # Сложный составной CSS-селектор fast-линии (todo+in_progress) — прямой
    # локатор оставлен (правило «PO — не догма»).
    expect(
        page.locator(
            '[data-status="todo"] article[data-fast="true"],'
            ' [data-status="in_progress"] article[data-fast="true"]'
        )
    ).to_have_count(0)

    # Шаг 1: новая fast-задача → done.
    create_task_via_ui(board_page, "Fast-финал", priority="high", is_fast=True)
    final_card = board.card("Fast-финал")
    expect(final_card).to_be_visible()
    web_cleanup_created(int(final_card.get_attribute("data-task-id")))
    move_via_card_select(board_page, "Fast-финал", "done")

    # Шаг 2: задача текущего МСК-дня видима в «Выполнено».
    expect(board.card_in_column("done", "Fast-финал")).to_be_visible()

    # Шаги 3–4: эмуляция следующего МСК-дня + перезагрузка доски
    # (ленивая автоархивация при первом чтении).
    _shift_done_at(web_db_path, "Fast-финал", f"{yesterday}T15:00:00+03:00")
    page.reload()

    # Шаг 5: задачи нет ни в одном столбце.
    board.wait_loaded()
    expect(board.card("Fast-финал")).to_have_count(0)

    # Шаг 6: найдена через поиск с бейджем «Архивная».
    search.open(web_base_url)
    search.archived_select().select_option("true")
    search.builder_find_button().click()
    found = search.result_card("Fast-финал")
    expect(found).to_be_visible()
    expect(found.get_by_text("Архивная", exact=True)).to_be_visible()

    # Шаги 7–8: создание НОВОЙ fast-задачи успешно — линия освобождена.
    board.open(web_base_url)
    create_task_via_ui(board_page, "Fast-новая", is_fast=True)
    new_card = board.card_in_column("todo", "Fast-новая")
    expect(new_card).to_be_visible()
    # Изоляция (дефект Р3): id регистрируется в cleanup ДО прочих ассертов —
    # иначе упавший ассерт оставляет АКТИВНУЮ fast-задачу и роняет setup
    # TC-dnd-103/106 («fast line occupied») в совместном прогоне сессии.
    web_cleanup_created(int(new_card.get_attribute("data-task-id")))
    expect(page.get_by_text("fast line занята")).to_have_count(0)
    assert "task-card-fast" in new_card.get_attribute("class")
