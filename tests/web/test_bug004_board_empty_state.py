"""BUG-004: пустой state доски рисуется ПОД шапкой колонки (redesign-1).

Трассировка: TC-bug004-101…103 (BUG-004-регресс к домену доски,
test-model/bugs/BUG-004-board-empty-state-above-header.md).

Дефект: cards.js вешал board-column-empty на СЕКЦИЮ .board-column, CSS
рисовал пунктир и ::before с текстом «Пока пусто — задачи появятся здесь»
на секции — псевдоэлемент рендерился первым боксом секции, НАД .col-head
(LED + название + mono-код + счетчик). Фикс: класс ставится на контейнер
карточек .board-column-cards — рамка и текст идут после шапки колонки.

Кейсы:
- TC-bug004-101: пустая колонка — .board-column-empty на контейнере,
  .col-head ВЫШЕ контейнера (bounding-box y), текст ::before присутствует,
  контейнер видим (рамка пунктиром на контейнере — TC-vis-102);
- TC-bug004-102: непустая колонка — класс снят (появление задачи);
- TC-bug004-103: fastline-зона (P23, ОВ-3) — пустые столбцы зоны БЕЗ
  подсказки: класс board-column-empty не ставится, ::before-контента нет.

Среда: автостенд tests/web (conftest), маркер web.
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.web, pytest.mark.must]


def _delete_all_tasks(web_owner_session, web_base_url) -> int:
    """Полная очистка доски (пустое состояние) — как в test_redesign_console."""
    resp = web_owner_session.get(f"{web_base_url}/api/board")
    assert resp.status_code == 200, resp.text
    columns = resp.json().get("columns", {})
    count = 0
    for tasks in columns.values():
        for task in tasks or []:
            web_owner_session.delete(f"{web_base_url}/api/tasks/{task['id']}")
            count += 1
    return count


def test_bug004_empty_column_head_above_empty_state(
    board_page, web_owner_session, web_base_url
):
    """TC-bug004-101: пустая колонка — порядок чтения сверху вниз:
    шапка колонки (.col-head) ВЫШЕ пустого state (контейнер
    .board-column-cards с классом board-column-empty); текст «Пока
    пусто — задачи появятся здесь» присутствует (::before не none);
    рамка пунктиром — на контейнере, не на секции."""
    page = board_page
    _delete_all_tasks(web_owner_session, web_base_url)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    column = page.locator('.board-column[data-status="in_progress"]')
    cards = column.locator(".board-column-cards")
    expect(cards).to_contain_class("board-column-empty")
    expect(column).not_to_contain_class("board-column-empty")

    # Порядок: шапка выше контейнера пустого state (дефект BUG-004).
    head_box = column.locator(".col-head").bounding_box()
    empty_box = cards.bounding_box()
    assert head_box["y"] < empty_box["y"], (head_box, empty_box)

    # Текст подсказки живет в ::before контейнера и виден.
    content = page.evaluate(
        """() => getComputedStyle(
            document.querySelector(
              '.board-column[data-status="in_progress"] .board-column-cards'
            ), "::before").content"""
    )
    assert "Пока пусто" in content, content
    expect(cards).to_be_visible()
    border = page.evaluate(
        """() => getComputedStyle(
            document.querySelector(
              '.board-column[data-status="in_progress"] .board-column-cards'
            )).borderTopStyle"""
    )
    assert border == "dashed", border


def test_bug004_nonempty_column_class_removed(
    board_page, web_owner_session, web_base_url, web_cleanup_created
):
    """TC-bug004-102: появление задачи в колонке снимает
    board-column-empty с контейнера (рамки/подсказки нет)."""
    page = board_page
    _delete_all_tasks(web_owner_session, web_base_url)
    resp = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-bug004-заполнение", "priority": "high"},
    )
    assert resp.status_code in (200, 201), resp.text
    task_id = resp.json()["id"]
    web_cleanup_created(task_id)
    moved = web_owner_session.post(
        f"{web_base_url}/api/tasks/{task_id}/move", json={"status": "in_progress"}
    )
    assert moved.status_code == 200, moved.text
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    cards = page.locator(
        '.board-column[data-status="in_progress"] .board-column-cards'
    )
    expect(cards.locator(".task-card").first).to_be_visible()
    expect(cards).not_to_contain_class("board-column-empty")
    content = page.evaluate(
        """() => getComputedStyle(
            document.querySelector(
              '.board-column[data-status="in_progress"] .board-column-cards'
            ), "::before").content"""
    )
    assert content in ("none", "normal", ""), content


def test_bug004_fastline_empty_columns_no_hint(
    board_page, web_owner_session, web_base_url
):
    """TC-bug004-103 (P23, ОВ-3): пустые столбцы fastline-зоны — БЕЗ
    подсказки: класс board-column-empty на контейнер зоны не ставится,
    ::before-контента нет; высоту держит контейнер (min-height 72px)."""
    page = board_page
    _delete_all_tasks(web_owner_session, web_base_url)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    containers = page.locator("#fastline .fastline-column .board-column-cards")
    assert containers.count() == 3, containers.count()
    expect(page.locator("#fastline .board-column-empty")).to_have_count(0)
    contents = page.evaluate(
        """() => [...document.querySelectorAll(
                '#fastline .fastline-column .board-column-cards')]
            .map(el => getComputedStyle(el, "::before").content)"""
    )
    assert all(c in ("none", "normal", "") for c in contents), contents
