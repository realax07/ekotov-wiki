"""Домен fastline: TC-UI-010, TC-UI-011 (CHK-E-10/11; approved/e2e-critical-path/ui-01.md).

P23 (openspec/changes/p23-fastline, tasks 4.4): fast-задача живет ТОЛЬКО в
зоне FASTLINE над канбаном (3 столбца-этапа) — ассерты переведены с колонок
канбана на зону (правка по impact §6, F2 ревью №1). Подсветка fast line
проверяется наблюдаемым DOM-состоянием (task-card-fast от cards.js —
соглашение п.5 кейсов); скриншот — приложение.
"""

from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

# Скриншоты — в артефакты прогонов (tests/web/artifacts/, вне git).
SCREENSHOT_DIR = Path(__file__).resolve().parent / "artifacts"

# Текст 409 «fast line occupied» = текст чипа-запрета зоны (P23 2.3).
FASTLINE_BUSY_TEXT = "В фастлайне уже есть задача — выполните текущую"


def _zone_column(page, status: str):
    """Столбец зоны FASTLINE по этапу (data-fastline-stage = status)."""
    return page.locator(f'#fastline .fastline-column[data-fastline-stage="{status}"]')


def _card_task_id(card) -> int:
    value = card.get_attribute("data-task-id")
    assert value is not None, "у карточки нет data-task-id"
    return int(value)


def test_fast_task_create_and_highlight(page, web_base_url, board_page, web_cleanup_created):
    """TC-UI-010 / TC-UIP-101 / TC-UIP-113 (FR-87, add-ui-polish-r8):
    fast-задача создана с отметкой; карточка с бейджем fast; подсветка
    ТОЛЬКО плитки (task-card-fast), столбец НЕ красится (класс has-fast
    ОТСУТСТВУЕТ — инверсия прежнего ассерта, правило .board-column.has-fast
    убрано из board.css §5.2). P23 (tasks 4.4): карточка в «Ожидает» ЗОНЫ
    FASTLINE; в столбцах канбана fast-карт нет."""
    # Предусловие: fast line свободна.
    expect(page.locator('article[data-fast="true"]')).to_have_count(0)

    create_task_via_ui(board_page, "Fast-первая", priority="high", is_fast=True)

    fast_card = page.locator('article[data-fast="true"]').filter(has_text="Fast-первая")
    expect(fast_card).to_be_visible()
    web_cleanup_created(_card_task_id(fast_card))
    expect(fast_card.get_by_text("fast", exact=True)).to_be_visible()

    # P23: карточка в «Ожидает» зоны; в канбане fast-карт нет.
    expect(_zone_column(page, "todo").get_by_role("article").filter(
        has_text="Fast-первая"
    )).to_be_visible()
    expect(page.locator("#board article[data-fast='true']")).to_have_count(0)

    # Подсветка только плитки (FR-87, TC-UIP-101): столбец не красится.
    todo = board_page.locator('#board [data-status="todo"]')
    assert "has-fast" not in (todo.get_attribute("class") or "")
    assert "task-card-fast" in fast_card.get_attribute("class")
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    page.screenshot(path=str(SCREENSHOT_DIR / "tc-ui-010-fastline.png"))

    # Единственность: в столбце «Ожидает» зоны ровно эта fast-карта.
    zone_cards = _zone_column(page, "todo").locator("[data-cards] article")
    expect(zone_cards).to_have_count(1)


def test_second_fast_task_rejected(page, web_base_url, board_page, web_cleanup_created):
    """TC-UI-011: вторая fast-задача отклонена с сообщением чипа-запрета
    зоны (P23 2.3: текст 409 переформулирован под зону), форма осталась
    открытой, задача не создана; после перерисовки доски из серверного
    состояния кнопка зоны disabled и чип показан."""
    # Предусловие: активная fast-задача «Fast-первая» (fast line занята).
    create_task_via_ui(board_page, "Fast-первая", priority="high", is_fast=True)
    first_card = page.locator('article[data-fast="true"]').filter(has_text="Fast-первая")
    expect(first_card).to_be_visible()
    web_cleanup_created(_card_task_id(first_card))
    expect(page.locator('article[data-fast="true"]')).to_have_count(1)

    board_page.get_by_role("button", name="Создать задачу").click()
    board_page.get_by_label("Название").fill("Fast-вторая")
    board_page.get_by_label("fast line").check()
    board_page.get_by_role("button", name="Создать", exact=True).click()

    # 409: сообщение чипа — в боксе ошибки формы (текст зоны, P23 2.3).
    form_error = board_page.locator("#task-form-error")
    expect(form_error).to_be_visible()
    assert form_error.inner_text().strip() == FASTLINE_BUSY_TEXT, form_error.inner_text()

    # Форма открыта, поля сохранены.
    expect(board_page.locator("#task-form-overlay")).to_be_visible()
    assert board_page.get_by_label("Название").input_value() == "Fast-вторая"
    assert board_page.get_by_label("fast line").is_checked()

    # P23 2.3: доска перерисована из серверного состояния — гейты зоны
    # встали по факту (кнопка disabled, чип виден).
    expect(board_page.locator("#fastline-add-button")).to_be_disabled()
    expect(board_page.locator("#fastline-blocked-hint")).to_be_visible()

    board_page.get_by_role("button", name="Отмена").click()
    expect(board_page.locator('article[data-fast="true"]')).to_have_count(1)
    expect(board_page.get_by_role("article").filter(has_text="Fast-вторая")).to_have_count(0)
