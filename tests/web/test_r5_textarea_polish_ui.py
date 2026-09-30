"""Р5 polish (прод-репорт Заказчика): авто-высота textarea формы задачи
и комментария; tooltip карточки — только на строке пользователей.

Задача Р5 (UI-polish, решение ПМ согласовано с Заказчиком):
- (Б) textarea «Описание» и «Новый комментарий»: старт ~2 строки,
  рост по вводу, потолок ~10 строк затем скролл, курсор в начале,
  placeholder-подсказка внутри поля; label над полем остается;
  сброс высоты при очистке формы.
  → TC-r5ta-101 test_textarea_initial_height_two_rows;
  → TC-r5ta-102 test_textarea_grows_with_input;
  → TC-r5ta-103 test_textarea_resets_after_form_clear;
  → TC-r5ta-104 test_textarea_placeholder_and_label;
- (A) tooltip creator/assignee — поведение по зонам карточки — покрыто
  TC-assignu-103 (tests/web/test_board_assign_ui.py, обновлен в этой
  же задаче: hover заголовок → скрыт, hover users-строка → виден).

Формат — tests/web/test_board_assign_ui.py (фикстуры conftest.py).
"""

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui, expect_form_hidden

pytestmark = [pytest.mark.web, pytest.mark.must]

DESCRIPTION = "#task-description"
COMMENT = "#comment-body"

TWO_ROWS_MAX_PX = 68  # ~2.5 строки (старт 52px + допуск на паддинги)
GROWTH_LINES = "line1\nline2\nline3\nline4\nline5"


def _height(page, selector: str) -> int:
    return page.locator(selector).evaluate("el => el.getBoundingClientRect().height")


# --------------------------------------------------------------------------
# TC-r5ta-101 — начальная высота ~2 строки (≈52px)
# --------------------------------------------------------------------------
def test_textarea_initial_height_two_rows(board_page):
    """TC-r5ta-101: открытая форма создания — «Описание» стартует ~2
    строки (≤ ~2.5 строки), не высокая (прод-репорт: «курсор в середине
    пустоты»). Поле комментария — тоже (проверка через редактирование
    задачи ниже не нужна: класс и CSS общие)."""
    page = board_page
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    assert _height(page, DESCRIPTION) <= TWO_ROWS_MAX_PX
    page.get_by_role("button", name="Отмена").click()
    expect_form_hidden(page)


# --------------------------------------------------------------------------
# TC-r5ta-102 — рост по вводу (5 строк) и потолок
# --------------------------------------------------------------------------
def test_textarea_grows_with_input(board_page):
    """TC-r5ta-102: ввод 5 строк → высота выросла за пределы старта
    (input-событие → height=auto→scrollHeight); потолок ~10 строк
    (max-height) не превышается даже при 20 строках."""
    page = board_page
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    initial = _height(page, DESCRIPTION)

    box = page.locator(DESCRIPTION)
    box.fill(GROWTH_LINES)
    grown = _height(page, DESCRIPTION)
    assert grown > initial, (initial, grown)

    box.fill("\n".join(f"row{i}" for i in range(20)))
    capped = _height(page, DESCRIPTION)
    assert capped >= grown - 5  # не сжался обратно
    assert capped <= 265, capped  # max-height 260 + допуск

    page.get_by_role("button", name="Отмена").click()
    expect_form_hidden(page)


# --------------------------------------------------------------------------
# TC-r5ta-103 — сброс высоты при очистке формы
# --------------------------------------------------------------------------
def test_textarea_resets_after_form_clear(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r5ta-103: описания из 5 строк → высота выросла; «Отмена» →
    повторное открытие формы (clearTaskForm) — высота сброшена к старту.
    Также редактирование задачи с длинным описанием открывает поле сразу
    нужной высоты (fillTaskForm → autoresize)."""
    page = board_page
    long_text = "\n".join(f"строка {i} описания" for i in range(5))
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-ta-reset", "description": long_text},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    web_cleanup_created(task_id)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # Редактирование: поле открывается СРАЗУ под длинный текст.
    page.get_by_role("article").filter(has_text="QAT-ta-reset").click()
    page.get_by_role("button", name="Редактировать").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    grown = _height(page, DESCRIPTION)
    assert grown > TWO_ROWS_MAX_PX, grown

    # «Отмена» → открытие заново (clearTaskForm) — высота стартовая.
    page.get_by_role("button", name="Отмена").click()
    expect_form_hidden(page)
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    import os as _os
    if _os.environ.get("R5TA_DEBUG"):
        print("DEBUG heights:", page.locator(DESCRIPTION).evaluate(
            "el => ({h: el.getBoundingClientRect().height,"
            " inline: el.style.height, scroll: el.scrollHeight,"
            " rows: el.rows, lh: getComputedStyle(el).lineHeight,"
            " fs: getComputedStyle(el).fontSize, minH: getComputedStyle(el).minHeight})"
        ))
    assert _height(page, DESCRIPTION) <= TWO_ROWS_MAX_PX

    page.get_by_role("button", name="Отмена").click()
    expect_form_hidden(page)


# --------------------------------------------------------------------------
# TC-r5ta-104 — placeholder внутри поля, label на месте
# --------------------------------------------------------------------------
def test_textarea_placeholder_and_label(board_page):
    """TC-r5ta-104: placeholder-подсказка ВНУТРИ поля («Описание
    задачи…», «Новый комментарий…»); видимый label над полем сохранен
    (доступность не деградирует: get_by_label работает)."""
    page = board_page
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    expect(page.locator(DESCRIPTION)).to_have_attribute(
        "placeholder", "Описание задачи…"
    )
    # Label связан с полем (обертка label): автожидание get_by_label.
    expect(page.get_by_label("Описание")).to_be_visible()
    page.get_by_role("button", name="Отмена").click()
    expect_form_hidden(page)

    # Поле комментария существует в разметке (показывается в режиме
    # редактирования) и несет placeholder уже на этапе загрузки страницы.
    expect(page.locator(COMMENT)).to_have_attribute(
        "placeholder", "Новый комментарий…"
    )
    assert page.get_by_label("Новый комментарий").count() == 1
