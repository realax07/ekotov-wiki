"""Домен fastline: TC-UI-010, TC-UI-011 (CHK-E-10/11; approved/e2e-critical-path/ui-01.md).

Подсветка fast line проверяется наблюдаемым DOM-состоянием (классы has-fast /
task-card-fast от board.js — соглашение п.5 кейсов); скриншот — приложение.
"""

from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

# Скриншоты — в артефакты прогонов (tests/web/artifacts/, вне git).
SCREENSHOT_DIR = Path(__file__).resolve().parent / "artifacts"


def _card_task_id(card) -> int:
    value = card.get_attribute("data-task-id")
    assert value is not None, "у карточки нет data-task-id"
    return int(value)


def test_fast_task_create_and_highlight(page, web_base_url, board_page, web_cleanup_created):
    """TC-UI-010: fast-задача создана с отметкой; карточка с бейджем fast,
    столбец подсвечен (has-fast/task-card-fast), fast-карточка первая
    в столбце."""
    # Предусловие: fast line свободна.
    expect(page.locator('article[data-fast="true"]')).to_have_count(0)

    create_task_via_ui(board_page, "Fast-первая", priority="high", is_fast=True)

    fast_card = board_page.get_by_role("article").filter(has_text="Fast-первая")
    expect(fast_card).to_be_visible()
    web_cleanup_created(_card_task_id(fast_card))
    expect(fast_card.get_by_text("fast", exact=True)).to_be_visible()

    # Подсветка столбца и карточки — наблюдаемое DOM-состояние (п.5).
    todo = board_page.locator('[data-status="todo"]')
    assert "has-fast" in todo.get_attribute("class")
    assert "task-card-fast" in fast_card.get_attribute("class")
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    page.screenshot(path=str(SCREENSHOT_DIR / "tc-ui-010-fastline.png"))

    # Первоочередность: fast-карточка первая в столбце (sdd §3.3).
    first_card = board_page.locator('[data-status="todo"] [data-cards] article').first
    expect(first_card).to_contain_text("Fast-первая")


def test_second_fast_task_rejected(page, web_base_url, board_page, web_cleanup_created):
    """TC-UI-011: вторая fast-задача отклонена с сообщением точно
    «fast line занята», форма осталась открытой, задача не создана."""
    # Предусловие: активная fast-задача «Fast-первая» (fast line занята).
    create_task_via_ui(board_page, "Fast-первая", priority="high", is_fast=True)
    first_card = board_page.get_by_role("article").filter(has_text="Fast-первая")
    expect(first_card).to_be_visible()
    web_cleanup_created(_card_task_id(first_card))
    expect(page.locator('article[data-fast="true"]')).to_have_count(1)

    board_page.get_by_role("button", name="Создать задачу").click()
    board_page.get_by_label("Название").fill("Fast-вторая")
    board_page.get_by_label("fast line").check()
    board_page.get_by_role("button", name="Создать", exact=True).click()

    expect(board_page.get_by_text("fast line занята")).to_be_visible()

    # Форма открыта, поля сохранены.
    expect(board_page.locator("#task-form-overlay")).to_be_visible()
    assert board_page.get_by_label("Название").input_value() == "Fast-вторая"
    assert board_page.get_by_label("fast line").is_checked()

    board_page.get_by_role("button", name="Отмена").click()
    expect(board_page.locator('article[data-fast="true"]')).to_have_count(1)
    expect(board_page.get_by_role("article").filter(has_text="Fast-вторая")).to_have_count(0)
