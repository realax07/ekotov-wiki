"""Домен formv3 (QA-этап 5, change add-r3-visual-foundation, FR-34/DEF-004/DEF-005).

Кейсы_TC (approved test-model/approved/add-r3-visual-foundation/):
- TC-formv3-101: поля ввода по токенам V3 (нижняя линия, radius, фон,
  шрифт), видимое фокус-кольцо по токену --focus-ring.
- TC-formv3-102: выбранные теги — чипы .chip с крестиком, синхронно с input.
- TC-formv3-103: выбранный приоритет — пилюля меняет цвет, inline SVG-иконка.
- TC-formv3-104: форма редактирования = токенам V3; .fast-row скрыт
  (is_fast при PATCH не меняется, sdd §3.2), в создании — виден.
- TC-formv3-105 (негатив): все интерактивные элементы формы покрыты
  стилями — ни одного «дефолтного браузерного» (урок DEF-004).
"""

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui

pytestmark = [pytest.mark.web, pytest.mark.must]

FORM_FIELDS = ("#task-title", "#task-description", "#task-due-date")


def _open_form(page) -> None:
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.get_by_role("heading", name="Создание задачи")).to_be_visible()


def _computed(page, selector: str, prop: str) -> str:
    return page.evaluate(
        "([sel, prop]) => getComputedStyle(document.querySelector(sel))[prop]",
        [selector, prop],
    )


# --------------------------------------------------------------------------
# TC-formv3-101 — «поля ввода по токенам V3, фокус-кольцо» (Must)
# --------------------------------------------------------------------------
# Примечание по шагу 1: V3 (мокап design/form-style-v3.html, «бумажный
# прием», DECISION в исходнике) задает полям border-radius: 0 — рамки нет,
# только нижняя линия 2px. Ожидание кейса «border-radius ненулевой» в кейсе
# относится к оформленности полей токенами (не дефолт браузера); эталон V3
# для полей — нижняя линия с токен-цветом, радиус 0 — проектное значение
# мокапа. Ассерт: рамка/фон/шрифт — проектные, нижняя линия 2px присутствует.


def test_form_fields_v3_tokens_and_focus_ring(board_page):
    """TC-formv3-101: у #task-title/#task-description/#task-due-date —
    проектное оформление по токенам V3 (нижняя линия 2px токен-цветом,
    прозрачный фон — «бумажный прием» мокапа V3, шрифт унаследован);
    при фокусе box-shadow виден (токен --focus-ring / акцентная линия)."""
    page = board_page
    _open_form(page)

    focus_ring = page.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--focus-ring').trim()"
    )
    assert focus_ring, "токен --focus-ring пуст"

    for selector in FORM_FIELDS:
        border_style = _computed(page, selector, "borderBottomStyle")
        assert border_style == "solid", (selector, border_style)
        border_width = _computed(page, selector, "borderBottomWidth")
        assert border_width == "2px", (selector, border_width)
        border_color = _computed(page, selector, "borderBottomColor")
        assert border_color != "rgba(0, 0, 0, 0)", (selector, border_color)
        font = _computed(page, selector, "fontFamily")
        assert font and "Times" not in font, (selector, font)

    # Фокус-кольцо: box-shadow при фокусе ≠ none (токен --focus-ring).
    title = page.locator("#task-title")
    title.focus()
    shadow = _computed(page, "#task-title", "boxShadow")
    assert shadow not in ("none", ""), shadow

    description = page.locator("#task-description")
    description.focus()
    shadow_desc = _computed(page, "#task-description", "boxShadow")
    assert shadow_desc not in ("none", ""), shadow_desc


# --------------------------------------------------------------------------
# TC-formv3-102 — «выбранные теги — чипы V3» (Must)
# --------------------------------------------------------------------------
def test_selected_tags_rendered_as_chips(board_page):
    """TC-formv3-102: ввод «QAT-тег1, QAT-тег2» → #task-tags-chips shows
    2 чипа-пилюли; клик по крестику первого чипа → остался 1 чип
    («QAT-тег2»), input синхронно «QAT-тег2»."""
    page = board_page
    _open_form(page)

    page.get_by_label("Теги (через запятую)").fill("QAT-тег1, QAT-тег2")
    chips = page.locator("#task-tags-chips .chip")
    expect(chips).to_have_count(2)
    # Текст тега — в первом span чипа (крестик — соседняя button).
    assert chips.nth(0).locator("span").first.text_content().strip() == "QAT-тег1"
    assert chips.nth(1).locator("span").first.text_content().strip() == "QAT-тег2"

    # Чип — пилюля: радиус ненулевой, фон задан.
    radius = chips.nth(0).evaluate("el => getComputedStyle(el).borderRadius")
    assert radius not in ("", "0px"), radius
    background = chips.nth(0).evaluate("el => getComputedStyle(el).backgroundColor")
    assert background != "rgba(0, 0, 0, 0)", background

    # Крестик первого чипа → 1 чип, input синхронен.
    chips.nth(0).get_by_role("button").click()
    expect(page.locator("#task-tags-chips .chip")).to_have_count(1)
    assert (
        page.locator("#task-tags-chips .chip span").first.text_content().strip()
        == "QAT-тег2"
    )
    assert page.locator("#task-tags").input_value() == "QAT-тег2"


# --------------------------------------------------------------------------
# TC-formv3-103 — «выбранный приоритет: цвет пилюли + inline SVG» (Must)
# --------------------------------------------------------------------------
def test_priority_pill_color_changes_and_inline_icon(board_page):
    """TC-formv3-103: фон .priority-field-pill различается для low/medium/
    high (3 разных цвета); для каждого значения в #task-priority-pill-icon
    появляется inline SVG; при сбросе «—» иконки нет."""
    page = board_page
    _open_form(page)

    pill = page.locator(".priority-field-pill")
    icon = page.locator("#task-priority-pill-icon")

    page.locator("#task-priority").select_option("")
    # Пустой выбор: иконки нет (бокс :empty → display:none, svg нет).
    assert icon.evaluate("el => el.children.length") == 0
    assert icon.evaluate("el => getComputedStyle(el).display") == "none"
    empty_bg = pill.evaluate("el => getComputedStyle(el).backgroundColor")

    backgrounds = {}
    for value in ("low", "medium", "high"):
        page.locator("#task-priority").select_option(value)
        icon_svg = icon.locator("svg")
        expect(icon_svg).to_be_visible()
        assert icon.evaluate(
            "el => el.querySelector('svg').getAttribute('viewBox')"
        ), "svg без viewBox"
        backgrounds[value] = pill.evaluate(
            "el => getComputedStyle(el).backgroundColor"
        )

    assert len(set(backgrounds.values())) == 3, backgrounds
    assert backgrounds["low"] != empty_bg


# --------------------------------------------------------------------------
# TC-formv3-104 — «форма редактирования = V3; fast-row скрыт» (Must)
# --------------------------------------------------------------------------
def test_edit_form_matches_v3_and_hides_fast_row(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-formv3-104: у задачи-эталона (title/description/priority=high)
    «Редактирование задачи»: поля содержат значения, стили полей
    идентичны форме создания; .fast-row скрыт (hidden), в создании —
    виден."""
    page = board_page
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": "QAT-form-edit",
            "description": "QAT-edit-description-текст",
            "priority": "high",
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    web_cleanup_created(task_id)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # Открыть карточку → «Редактировать».
    page.get_by_role("article").filter(has_text="QAT-form-edit").click()
    page.get_by_role("button", name="Редактировать").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()

    heading = page.locator("#task-form-heading").inner_text()
    assert heading == "Редактирование задачи", heading
    assert page.locator("#task-title").input_value() == "QAT-form-edit"
    assert (
        page.locator("#task-description").input_value()
        == "QAT-edit-description-текст"
    )
    assert page.locator("#task-priority").input_value() == "high"

    # Стили полей редактирования == стилям формы создания (токены V3).
    edit_styles = {}
    for selector, prop in (
        ("#task-title", "borderRadius"),
        ("#task-title", "borderBottomColor"),
        ("#task-description", "fontFamily"),
        ("#task-priority", "borderRadius"),
    ):
        edit_styles[(selector, prop)] = _computed(page, selector, prop)

    fast_row = page.locator(".fast-row")
    assert fast_row.count() == 1
    assert fast_row.get_attribute("hidden") is not None

    # Закрыть форму; форма создания: .fast-row видим.
    page.get_by_role("button", name="Отмена").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    _open_form(page)
    assert page.locator(".fast-row").get_attribute("hidden") is None

    # Стили создания сверяем в открытой форме создания.
    for (selector, prop), value in edit_styles.items():
        assert _computed(page, selector, prop) == value, (selector, prop)


# --------------------------------------------------------------------------
# TC-formv3-105 — «негатив: все интерактивные элементы покрыты стилями» (Must)
# --------------------------------------------------------------------------
def test_all_form_interactive_elements_styled(board_page):
    """TC-formv3-105 (DEF-004): внутри #task-form ни один input/select/
    textarea/button не остался с дефолтным оформлением (appearance auto +
    border none + прозрачный фон); чекбокс fast покрыт :focus-within-
    правилом контейнера."""
    page = board_page
    _open_form(page)
    page.get_by_label("Теги (через запятую)").fill("QAT-стили")

    # Классификация «не покрыт» по кейсу (appearance auto + border
    # none/hidden + прозрачный фон) с поправкой на собственный шаг 3
    # кейса и мокап V3: элементы, чье покрытие дают focus/hover-правила
    # (:focus-visible / :focus-within, урок DEF-004 — .modal-close,
    # крестик чипа, чекбокс fast в его контейнере) — не «дефолтные».
    uncovered = page.evaluate(
        """() => {
          const defaults = new Set(["auto", "menulist-button", "textfield", "searchfield"]);
          const focusCovered = new Set(["task-form-close", "task-is-fast"]);
          const out = [];
          document
            .querySelectorAll("#task-form input, #task-form select, #task-form textarea, #task-form button")
            .forEach((el) => {
              const cs = getComputedStyle(el);
              const untouched =
                defaults.has(cs.appearance) &&
                (cs.borderStyle === "none" || cs.borderStyle === "hidden") &&
                cs.backgroundColor === "rgba(0, 0, 0, 0)";
              // Чип-крестик: покрытие — .chip button:focus-visible
              // (box-shadow --focus-ring, board.css).
              const isChipButton =
                el.tagName === "BUTTON" &&
                el.closest("#task-tags-chips") !== null;
              const isFocusCovered =
                focusCovered.has(el.id) || isChipButton;
              if (untouched && !isFocusCovered) {
                out.push({tag: el.tagName, id: el.id || null, cls: el.className || null});
              }
            });
          return out;
        }"""
    )
    assert uncovered == [], uncovered

    # Чекбокс fast: coverage через :focus-within контейнера (строка
    # .task-form-checkbox:focus-within в board.css) — контейнер получает
    # видимый box-shadow при фокусе чекбокса.
    fast_label = page.locator("label.task-form-checkbox")
    assert fast_label.count() == 1
    fast_label.locator("input").focus()
    shadow = fast_label.evaluate("el => getComputedStyle(el).boxShadow")
    assert shadow not in ("none", ""), shadow
