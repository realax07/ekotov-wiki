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

import re

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui
from tests.web.pages.board import BoardPage
from tests.web.pages.task_detail import TaskDetailView
from tests.web.pages.task_form import TaskForm

pytestmark = [pytest.mark.web, pytest.mark.must]

FORM_FIELDS = ("#task-title", "#task-description", "#task-due-date")

# F1: подсвеченная кнопка сегмента приоритета (.is-checked).
_SEG_CHECKED_RE = re.compile(r"\bis-checked\b")


def _open_form(page) -> None:
    form = TaskForm(page)
    form.open_button().click()
    expect(form.heading_create).to_be_visible()


def _computed(page, selector: str, prop: str) -> str:
    return page.evaluate(
        "([sel, prop]) => getComputedStyle(document.querySelector(sel))[prop]",
        [selector, prop],
    )


# --------------------------------------------------------------------------
# TC-formv3-101 — «поля ввода по токенам, фокус-кольцо» (Must)
# --------------------------------------------------------------------------
# UPDATE F1 (PLAN-FORM-F1, эталон design-forge/extra/form-v1/create.html):
# «бумажный прием» V3 (нижняя линия 2px) заменен БОКСАМИ на raised
# (эталон .input: рамка 1px + radius-field + фон raised); фокус —
# рамка токеном --color-accent. Ассерт: рамка/фон/шрифт — проектные
# токены, не дефолт браузера.


def test_form_fields_v3_tokens_and_focus_ring(board_page):
    """TC-formv3-101 (F1): у #task-title/#task-description/#task-due-date —
    оформление по токенам (рамка 1px solid токен-цветом, фон raised,
    шрифт унаследован); при фокусе рамка — токен --color-accent."""
    page = board_page
    form = TaskForm(page)
    _open_form(page)

    focus_ring = page.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--focus-ring').trim()"
    )
    assert focus_ring, "токен --focus-ring пуст"
    raised = page.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--color-raised').trim()"
    )
    accent = page.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--color-accent').trim()"
    )
    assert raised, "токен --color-raised пуст"

    def _hex(rgb: str) -> str:
        # rgb(r, g, b) → "#rrggbb" (browser вычисляет var-токены в rgb).
        import re as _re

        parts = _re.findall(r"[\d.]+", rgb)
        if len(parts) < 3:
            return rgb
        r, g, b = (int(float(p)) for p in parts[:3])
        return f"#{r:02x}{g:02x}{b:02x}"

    for selector in FORM_FIELDS:
        border_style = _computed(page, selector, "borderBottomStyle")
        assert border_style == "solid", (selector, border_style)
        border_width = _computed(page, selector, "borderBottomWidth")
        assert border_width == "1px", (selector, border_width)
        border_color = _computed(page, selector, "borderBottomColor")
        assert border_color != "rgba(0, 0, 0, 0)", (selector, border_color)
        background = _computed(page, selector, "backgroundColor")
        assert _hex(background) == raised.lower(), (selector, background)
        font = _computed(page, selector, "fontFamily")
        assert font and "Times" not in font, (selector, font)

    # Фокус: рамка поля — токен --color-accent (эталон .input:focus).
    title = form.title_by_id()
    title.focus()
    border = _hex(_computed(page, "#task-title", "borderBottomColor"))
    assert border == accent.lower(), border

    description = form.description_by_id()
    description.focus()
    border_desc = _hex(_computed(page, "#task-description", "borderBottomColor"))
    assert border_desc == accent.lower(), border_desc


# --------------------------------------------------------------------------
# TC-formv3-102 — «выбранные теги — чипы V3» (Must)
# --------------------------------------------------------------------------
def test_selected_tags_rendered_as_chips(board_page):
    """TC-formv3-102: ввод «QAT-тег1, QAT-тег2» → #task-tags-chips shows
    2 чипа-пилюли; клик по крестику первого чипа → остался 1 чип
    («QAT-тег2»), input синхронно «QAT-тег2»."""
    page = board_page
    form = TaskForm(page)
    _open_form(page)

    form.tags.fill("QAT-тег1, QAT-тег2")
    chips = form.tag_chips()
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
    expect(form.tag_chips()).to_have_count(1)
    assert form.tag_chips().locator("span").first.text_content().strip() == "QAT-тег2"
    assert form.tags_by_id().input_value() == "QAT-тег2"


# --------------------------------------------------------------------------
# TC-formv3-103 — «выбранный приоритет: подсветка сегмента F1» (Must)
# UPDATE F1 (PLAN-FORM-F1, эталон design-forge/extra/form-v1/create.html):
# пилюля .priority-field-pill заменена СЕГМЕНТОМ из 3 кнопок; нативный
# select сохранен (контракт). Для каждого значения ровно одна кнопка
# сегмента подсвечена (.is-checked), подсветка (computed style) различается
# попарно; при сбросе «—» подсвеченных нет.
# --------------------------------------------------------------------------
def test_priority_segment_follows_select(board_page):
    """TC-formv3-103 (F1): select_option(low/medium/high) — ровно одна
    подсвеченная кнопка сегмента (та самая), фоны .is-checked попарно
    различны; при сбросе «—» подсвеченных нет; клик по кнопке сегмента
    пишет значение в нативный select (синхронизация task-form.js)."""
    page = board_page
    form = TaskForm(page)
    _open_form(page)

    checked = form.priority_checked_seg()

    form.priority_by_id().select_option("")
    # Пустой выбор: ни одна кнопка не подсвечена.
    assert checked.count() == 0

    backgrounds = {}
    for value in ("low", "medium", "high"):
        form.priority_by_id().select_option(value)
        expect(form.priority_seg_button(value)).to_have_class(
            _SEG_CHECKED_RE
        )
        assert checked.count() == 1, value
        assert checked.get_attribute("data-priority-value") == value
        backgrounds[value] = checked.evaluate(
            "el => getComputedStyle(el).borderColor"
        )

    # Подсветка различает приоритеты (3 разных рамки; 55%-микс сегмента).
    assert len(set(backgrounds.values())) == 3, backgrounds

    # Обратная синхронизация: клик по кнопке сегмента — value в select.
    form.priority_seg_button("low").click()
    assert form.priority_by_id().input_value() == "low"
    expect(form.priority_seg_button("low")).to_have_class(_SEG_CHECKED_RE)



# --------------------------------------------------------------------------
# TC-formv3-104 — «форма редактирования = V3; .fast-row показан с текущим
# is_fast» (Must) — UPDATE (TC-UIP-112, FR-89 add-ui-polish-r8 волна 2.7):
# в редактировании .fast-row ВИДЕН и отражает is_fast задачи.
# --------------------------------------------------------------------------
def test_edit_form_matches_v3_and_shows_fast_row(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-formv3-104 / TC-UIP-112 (FR-89): у задачи-эталона
    (title/description/priority=high) «Редактирование задачи»: поля
    содержат значения, стили полей идентичны форме создания; .fast-row в
    редактировании ВИДЕН и чекбокс отражает is_fast (regular → снят;
    fast-задача → отмечен, приоритет high заблокирован — инвариант FR-88);
    в создании ряд виден как прежде."""
    page = board_page
    board = BoardPage(page)
    form = TaskForm(page)
    detail = TaskDetailView(page)
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
    board.wait_loaded()

    # Открыть карточку → «Редактировать».
    board.card("QAT-form-edit").click()
    detail.edit_button().click()
    expect(form.overlay).to_be_visible()

    heading = form.heading_by_id().inner_text()
    # F1 (эталон edit.html): заголовок режима редактирования —
    # «Редактирование».
    assert heading == "Редактирование", heading
    assert form.title_by_id().input_value() == "QAT-form-edit"
    assert (
        form.description_by_id().input_value()
        == "QAT-edit-description-текст"
    )
    assert form.priority_by_id().input_value() == "high"

    # Стили полей редактирования == стилям формы создания (токены V3).
    edit_styles = {}
    for selector, prop in (
        ("#task-title", "borderRadius"),
        ("#task-title", "borderBottomColor"),
        ("#task-description", "fontFamily"),
        ("#task-priority", "borderRadius"),
    ):
        edit_styles[(selector, prop)] = _computed(page, selector, prop)

    fast_row = form.fast_row()
    assert fast_row.count() == 1
    # FR-89 (TC-UIP-112): в редактировании .fast-row ВИДЕН (не hidden) и
    # чекбокс отражает is_fast задачи: у regular-эталона — снят.
    assert fast_row.get_attribute("hidden") is None
    is_fast_cb = form.is_fast_checkbox()
    assert is_fast_cb.is_visible()
    assert not is_fast_cb.is_checked()
    assert form.priority_by_id().input_value() == "high"

    # Fast-задача: чекбокс отмечен; приоритет high и заблокирован
    # (инвариант is_fast ⇒ high — FR-88 в редактировании, волна 2.7).
    fast_created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-form-edit-fast", "priority": "high", "is_fast": True},
    )
    assert fast_created.status_code == 201, fast_created.text
    fast_id = fast_created.json()["id"]
    web_cleanup_created(fast_id)
    form.cancel_button().click()
    expect(form.overlay).to_be_hidden()
    page.reload()
    board.wait_loaded()
    board.card("QAT-form-edit-fast").click()
    detail.edit_button().click()
    expect(form.overlay).to_be_visible()
    assert form.fast_row().get_attribute("hidden") is None
    assert form.is_fast_checkbox().is_checked()
    assert form.priority_by_id().input_value() == "high"
    assert form.priority_by_id().is_disabled()

    # Закрыть форму; форма создания: .fast-row видим как прежде.
    form.cancel_button().click()
    expect(form.overlay).to_be_hidden()
    _open_form(page)
    assert form.fast_row().get_attribute("hidden") is None

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
    form = TaskForm(page)
    _open_form(page)
    form.tags.fill("QAT-стили")

    # Классификация «не покрыт» по кейсу (appearance auto + border
    # none/hidden + прозрачный фон) с поправкой на собственный шаг 3
    # кейса и мокап V3: элементы, чье покрытие дают focus/hover-правила
    # (:focus-visible / :focus-within, урок DEF-004 — .modal-close,
    # крестик чипа, чекбокс fast в его контейнере) — не «дефолтные».
    uncovered = page.evaluate(
        """() => {
          const defaults = new Set(["auto", "menulist-button", "textfield", "searchfield"]);
          // F1: #task-priority — НАТИВНЫЙ select контракта, скрытый внутри
          // сегмента (opacity:0, вне потока; значение держит select,
          // отображение — сегмент .seg). Действия e2e (select_option)
          // идут по нему напрямую — визуальное покрытие не требуется.
          const focusCovered = new Set(["task-form-close", "task-is-fast", "task-priority"]);
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
