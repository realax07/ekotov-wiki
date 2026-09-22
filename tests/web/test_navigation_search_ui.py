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

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def test_sidebar_all_pages_and_wiki_stub(logged_in_page, web_base_url):
    """TC-UI-016: сайдбар (Доска/Поиск/Wiki + бейдж todo) на всех страницах;
    Доска ↔ Поиск переключаются в обе стороны; Wiki — заглушка без функций."""
    page = logged_in_page
    for path in ("/board", "/search", "/wiki"):
        page.goto(f"{web_base_url}{path}")
        expect(page.get_by_role("link", name="Доска")).to_be_visible()
        expect(page.get_by_role("link", name="Поиск")).to_be_visible()
        expect(page.get_by_role("link", name="Wiki")).to_be_visible()
        expect(page.get_by_role("link", name="Wiki").get_by_text("todo")).to_be_visible()

    # Доска → Поиск.
    page.goto(f"{web_base_url}/board")
    page.get_by_role("link", name="Поиск").click()
    expect(page.get_by_role("heading", name="Поиск", exact=True)).to_be_visible()
    assert page.url.endswith("/search")
    expect(page.get_by_role("button", name="Конструктор")).to_be_visible()
    expect(page.get_by_role("button", name="Advanced")).to_be_visible()

    # Поиск → Доска.
    page.get_by_role("link", name="Доска").click()
    expect(page.get_by_role("heading", name="Доска", exact=True)).to_be_visible()
    assert page.url.endswith("/board")

    # Доска → Wiki (заглушка).
    page.get_by_role("link", name="Wiki").click()
    expect(page.get_by_role("heading", name="Wiki")).to_be_visible()
    assert page.url.endswith("/wiki")
    expect(page.locator("main").get_by_role("textbox")).to_have_count(0)
    expect(page.locator("main").get_by_role("button")).to_have_count(0)


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

    # Подготовка (вариант Б): задача → done → done_at вчера → автоархивация.
    create_task_via_ui(
        board_page,
        "Архивная-поиск",
        priority="high",
        category="Дом",
        tags="архив2026",
    )
    card = board_page.get_by_role("article").filter(has_text="Архивная-поиск")
    expect(card).to_be_visible()
    web_cleanup_created(int(card.get_attribute("data-task-id")))
    move_via_card_select(board_page, "Архивная-поиск", "done")
    _shift_done_at(web_db_path, "Архивная-поиск", f"{yesterday}T15:00:00+03:00")
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    expect(page.get_by_role("article").filter(has_text="Архивная-поиск")).to_have_count(0)

    # Контрольная не-Дом задача: не должна попасть в результаты фильтра.
    create_task_via_ui(board_page, "Fast-первая", priority="high", is_fast=True)
    fast_card = page.get_by_role("article").filter(has_text="Fast-первая")
    expect(fast_card).to_be_visible()
    web_cleanup_created(int(fast_card.get_attribute("data-task-id")))

    # Шаг 1–2: конструктор — категория «Дом» (select из справочника,
    # select_option вместо fill — CHK-146), только архивные.
    page.goto(f"{web_base_url}/search")
    page.get_by_label("Категория").select_option("Дом")
    page.get_by_label("Архивность").select_option("true")
    page.locator("#search-builder").get_by_role("button", name="Найти").click()

    results = page.locator("#search-results")
    result_card = results.get_by_role("article").filter(has_text="Архивная-поиск")
    expect(result_card).to_be_visible()
    expect(result_card.get_by_text("Архивная", exact=True)).to_be_visible()
    expect(
        results.get_by_role("article").filter(has_text="Fast-первая")
    ).to_have_count(0)

    # Шаг 4: переключение в advanced — поле содержит фильтр конструктора.
    page.get_by_role("button", name="Advanced").click()
    query_box = page.get_by_label("Фильтр (SQL-подобный синтаксис)")
    value = query_box.input_value()
    assert 'category = "Дом"' in value, f"в поле нет category: {value!r}"
    assert "archived = true" in value, f"в поле нет archived: {value!r}"

    # Шаг 5: правка фильтра и применение.
    query_box.fill('priority = "high" AND archived = true')
    page.locator("#search-advanced").get_by_role("button", name="Найти").click()

    # Шаг 6: нормализованный фильтр показан, результат применен.
    normalized = page.locator("#search-advanced-normalized")
    expect(normalized).to_be_visible()
    assert normalized.inner_text().startswith("Нормализованный фильтр:")
    expect(
        page.locator("#search-results").get_by_role("article").filter(
            has_text="Архивная-поиск"
        )
    ).to_be_visible()

    # Шаг 7: клик по карточке архивной задачи открывает карточку
    # с признаками (FR-10 / CHK-E-17; наблюдение ревьюера — renderCard
    # в search.js не вешает click-обработчик: если шаг падает — дефект).
    # Якорь открытия — МОДАЛКА карточки (#task-detail-overlay): heading
    # «Архивная-поиск» без якоря матчит и заголовок карточки в результатах.
    page.locator("#search-results").get_by_role("article").filter(
        has_text="Архивная-поиск"
    ).click()
    expect(page.locator("#task-detail-overlay")).to_be_visible()
    expect(page.get_by_role("heading", name="Архивная-поиск")).to_be_visible()
    expect(page.locator("#task-detail-archive-badge")).to_be_visible()
    attrs = page.locator("#task-detail-attrs")
    for term_value in ("high", "Дом", "архив2026"):
        expect(attrs.get_by_text(term_value, exact=True)).to_be_visible()


def test_final_path_autoarchive_and_fast_release(
    page, web_base_url, board_page, web_db_path, web_cleanup_created
):
    """TC-UI-018: финал пути — done сегодня видима; смещение done_at на
    вчерашний МСК-день → автоархивация при первом чтении доски; задача
    найдена через поиск с бейджем «Архивная»; fast line освобождена."""
    today, yesterday = _msk_dates()

    # Шаг 0 подготовки: активная fast-задача «Fast-первая» (изолированный
    # setup вместо цепочки с TC-UI-010) → done → fast line свободна.
    create_task_via_ui(board_page, "Fast-первая", priority="high", is_fast=True)
    first_card = board_page.get_by_role("article").filter(has_text="Fast-первая")
    expect(first_card).to_be_visible()
    web_cleanup_created(int(first_card.get_attribute("data-task-id")))
    move_via_card_select(board_page, "Fast-первая", "done")
    expect(
        page.locator('[data-status="done"]').get_by_role("article").filter(
            has_text="Fast-первая"
        )
    ).to_be_visible()
    expect(
        page.locator(
            '[data-status="todo"] article[data-fast="true"],'
            ' [data-status="in_progress"] article[data-fast="true"]'
        )
    ).to_have_count(0)

    # Шаг 1: новая fast-задача → done.
    create_task_via_ui(board_page, "Fast-финал", priority="high", is_fast=True)
    final_card = board_page.get_by_role("article").filter(has_text="Fast-финал")
    expect(final_card).to_be_visible()
    web_cleanup_created(int(final_card.get_attribute("data-task-id")))
    move_via_card_select(board_page, "Fast-финал", "done")

    # Шаг 2: задача текущего МСК-дня видима в «Выполнено».
    expect(
        page.locator('[data-status="done"]').get_by_role("article").filter(
            has_text="Fast-финал"
        )
    ).to_be_visible()

    # Шаги 3–4: эмуляция следующего МСК-дня + перезагрузка доски
    # (ленивая автоархивация при первом чтении).
    _shift_done_at(web_db_path, "Fast-финал", f"{yesterday}T15:00:00+03:00")
    page.reload()

    # Шаг 5: задачи нет ни в одном столбце.
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    expect(page.get_by_role("article").filter(has_text="Fast-финал")).to_have_count(0)

    # Шаг 6: найдена через поиск с бейджем «Архивная».
    page.goto(f"{web_base_url}/search")
    page.get_by_label("Архивность").select_option("true")
    page.locator("#search-builder").get_by_role("button", name="Найти").click()
    found = page.locator("#search-results").get_by_role("article").filter(
        has_text="Fast-финал"
    )
    expect(found).to_be_visible()
    expect(found.get_by_text("Архивная", exact=True)).to_be_visible()

    # Шаги 7–8: создание НОВОЙ fast-задачи успешно — линия освобождена.
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    create_task_via_ui(board_page, "Fast-новая", is_fast=True)
    new_card = page.locator('[data-status="todo"]').get_by_role("article").filter(
        has_text="Fast-новая"
    )
    expect(new_card).to_be_visible()
    expect(page.get_by_text("fast line занята")).to_have_count(0)
    assert "task-card-fast" in new_card.get_attribute("class")
