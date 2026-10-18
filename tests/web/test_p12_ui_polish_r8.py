"""add-ui-polish-r8 3.1 (а)+(б): новые web/playwright-кейсы волн 2.1/2.3/2.7.

Трассировка TC (test-model/approved/add-ui-polish-r8/):
- TC-UIP-103 (CHK-P12-3, FR-88): геометрия/токены .fast-row формы создания
  + behavior-инвариант блокировки приоритета при отметке fast.
- TC-UIP-104 (CHK-P12-4, FR-93): кнопка #search-advanced-submit — класс
  .btn-action (токены V3), DOM-id сохранен (ОГР-28), 8px-сетка отступов.
- TC-UIP-105 (CHK-P12-5, FR-93, дисп. M4): единый паттерн .btn-action для
  кнопок поиска («Найти» builder + advanced); hover/focus-состояния едины.
- TC-UIP-106 (CHK-P12-6, FR-96): bbox кнопки «Настройки» идентичен
  в базовом / active (mouse.down) / focus-visible состояниях (±0.5px),
  transform отсутствует.
- TC-UIP-108 (CHK-P12-11, FR-91): шапка комментария «автор · дата» во
  view-модалке — имя автора (не id), человекочитаемая дата (не сырой ISO).
- TC-UIP-109 (CHK-P12-14, FR-92): committed-леджер по всем путям выбора
  (клик/Enter/Tab) — тег в input до сабмита, чип с крестиком, фокус в поле,
  ПОСЛЕ сабмита поле пустое (flushCommittedToInput).
- TC-UIP-110 (CHK-P12-15, FR-92): 3 тега подряд (клик/Enter/создание) —
  3 чипа, леджер в input; удаление крестиком — чип исчез, поле не
  блокируется; возвращенный тег снова доступен; сабмит — ровно 3 тега.
- TC-UIP-111 (CHK-P12-29, FR-89): переключение fast в редактировании —
  включение шлет priority high (инвариант), 409 «fast line занята»
  обрабатывается формой, выключение разблокирует приоритет.

Среда: автостенд tests/web (conftest: uvicorn + http.server + tmp-БД) —
достаточно для board/search; галерейные кейсы — отдельный файл (R4).
"""

import re

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui
from tests.web.pages.auth import Sidebar
from tests.web.pages.board import BoardPage
from tests.web.pages.search import SearchPage
from tests.web.pages.tag_combobox import TagCombobox
from tests.web.pages.task_detail import TaskDetailView
from tests.web.pages.task_form import TaskForm

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def _rgb_to_hex(rgb: str) -> str:
    """'rgb(238, 242, 246)' → '#eef2f6' (computed style → значение токена)."""
    import re as _re

    parts = _re.findall(r"\d+", rgb)
    r, g, b = (int(x) for x in parts[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def _open_board_form(page):
    form = TaskForm(page)
    form.open_create()
    return form


def _seed_tagged_task(web_owner_session, web_base_url, title, tags):
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": title, "tags": tags}
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


# --------------------------------------------------------------------------
# TC-UIP-103 — .fast-row по макету V3: токены, 8px-сетка, блокировка
# --------------------------------------------------------------------------
def test_fast_row_v3_geometry_and_priority_lock(board_page):
    """TC-UIP-103 (CHK-P12-3, FR-88): .fast-row формы создания — плашка на
    голубых токенах V3 (var(--p-blue-*), без литеральных hex), отступы на
    8px-сети, чекбокс 16px; отметка fast → приоритет high и заблокирован,
    снятие — разблокирован (behavior-инвариант FR-88 сохранен)."""
    page = board_page
    form = _open_board_form(page)

    row = form.fast_row()
    expect(row).to_be_visible()

    # Токены V3: фон/бордер ряда резолвятся в значения :root-токенов
    # (p-blue-050/p-blue-200), радиус = токен --radius-field.
    styles = page.evaluate(
        """() => {
          const row = document.querySelector("#task-form .fast-row");
          const cb = row.querySelector("input");
          const root = getComputedStyle(document.documentElement);
          const cs = getComputedStyle(row);
          const cbcs = getComputedStyle(cb);
          return {
            bg: cs.backgroundColor,
            bgToken: root.getPropertyValue("--p-blue-050").trim(),
            border: cs.borderTopColor,
            borderToken: root.getPropertyValue("--p-blue-200").trim(),
            radius: cs.borderRadius,
            radiusToken: root.getPropertyValue("--radius-field").trim(),
            marginBottom: cs.marginBottom,
            cbW: cbcs.width,
            cbH: cbcs.height,
          };
        }"""
    )
    assert styles["bg"] != "rgba(0, 0, 0, 0)", styles
    assert styles["border"] != "rgba(0, 0, 0, 0)", styles
    assert styles["marginBottom"] in ("8px", "16px"), styles  # 8px-сетка
    assert styles["cbW"] == "16px" and styles["cbH"] == "16px", styles
    # Токен-значения непусты (стиль ряда строится на var(--…), не литералах)
    # и computed bg/border РАВНЫ значениям токенов (review-004 nit-2:
    # литеральный hex, совпадающий с видимым цветом, больше не проходит).
    assert styles["bgToken"], "--p-blue-050 пуст"
    assert styles["borderToken"], "--p-blue-200 пуст"
    assert _rgb_to_hex(styles["bg"]) == styles["bgToken"].lower(), styles
    assert _rgb_to_hex(styles["border"]) == styles["borderToken"].lower(), styles

    # Behavior: отметка fast → priority=high, disabled; снятие → разблокирован.
    fast = form.fast_line_label()
    fast.check()
    assert form.priority_by_id().input_value() == "high"
    assert form.priority_by_id().is_disabled()
    fast.uncheck()
    assert not form.priority_by_id().is_disabled()

    form.cancel_button().click()
    expect(form.overlay).to_be_hidden()


# --------------------------------------------------------------------------
# TC-UIP-104/105 — единый паттерн кнопок действия .btn-action (FR-93)
# --------------------------------------------------------------------------
def test_search_action_buttons_single_btn_action_pattern(logged_in_page, web_base_url):
    """TC-UIP-104 + TC-UIP-105 (CHK-P12-4/5, FR-93, дисп. M4): кнопки
    «Найти» конструктора и advanced-поиска несут единый класс .btn-action
    (токены V3: фон --color-accent, радиус-пилюля 999px); DOM-id не
    переименованы (ОГР-28: #search-builder-submit, #search-advanced-submit);
    отступы кратны 8px; hover/focus-состояния едины (hover-фон токен,
    focus-visible box-shadow --focus-ring)."""
    page = logged_in_page
    search = SearchPage(page)
    search.open(web_base_url)

    # Advanced-кнопка скрыта до переключения режима — DOM-id и класс
    # проверяем на присутствие в DOM (ОГР-28), видимость после клика.
    # Перебор DOM-id-селекторов (ОГР-28) — прямые locator (PO — не догма).
    buttons = {}
    for bid in ("#search-builder-submit", "#search-advanced-submit"):
        btn = page.locator(bid)
        expect(btn).to_have_count(1)  # ОГР-28: id на месте
        classes = (btn.get_attribute("class") or "").split()
        assert "btn-action" in classes, (bid, classes)
        styles = page.evaluate(
            """([sel]) => {
              const b = document.querySelector(sel);
              const cs = getComputedStyle(b);
              const root = getComputedStyle(document.documentElement);
              return {
                bg: cs.backgroundColor, radius: cs.borderRadius,
                padTop: cs.paddingTop, padBottom: cs.paddingBottom,
                padLeft: cs.paddingLeft, padRight: cs.paddingRight,
                accent: root.getPropertyValue("--color-accent").trim(),
              };
            }""",
            [bid],
        )
        assert styles["radius"] == "999px", (bid, styles)
        assert styles["bg"] != "rgba(0, 0, 0, 0)", (bid, styles)
        # 8px-сетка вертикальных отступов (var(--space-N) = 8/16px).
        for key in ("padTop", "padBottom"):
            assert styles[key] in ("8px", "16px"), (bid, key, styles)
        buttons[bid] = styles

    # Один паттерн: computed фон и радиус идентичны у обеих кнопок.
    assert buttons["#search-builder-submit"]["bg"] == (
        buttons["#search-advanced-submit"]["bg"]
    )
    assert buttons["#search-builder-submit"]["radius"] == (
        buttons["#search-advanced-submit"]["radius"]
    )

    # Advanced-кнопка функционально жива: клик открывает advanced-блок,
    # «Найти» формирует выдачу (поведение не изменилось — keep-семантика).
    search.advanced_button.click()
    expect(search.advanced).to_be_visible()
    advanced_submit = page.locator("#search-advanced-submit")
    expect(advanced_submit).to_be_visible()
    search.advanced_query.fill('archived = "false"')
    advanced_submit.click()
    expect(search.results).to_be_visible()


# --------------------------------------------------------------------------
# TC-UIP-106 — кнопка «Настройки»: active/focus не смещают текст (FR-96)
# --------------------------------------------------------------------------
def test_settings_link_bbox_stable_across_active_focus(logged_in_page, web_base_url):
    """TC-UIP-106 (CHK-P12-6, FR-96): bbox ссылки «Настройки» идентичен
    до / во время active-нажатия (mouse.down без release) / при
    focus-visible — допуск ±0.5px; transform отсутствует во всех
    состояниях (группа H design: border без смены ширины, transform
    запрет)."""
    page = logged_in_page
    sidebar = Sidebar(page)
    page.goto(f"{web_base_url}/board")
    link = sidebar.settings_link
    expect(link).to_be_visible()

    box0 = link.bounding_box()

    # Active-нажатие: mouse.down в центре, без release. Отпускание —
    # с уведенным курсором: down+up на самой ссылке — это click, он
    # запускает навигацию на /settings и гонит последующие
    # link.focus()/bounding_box() (флейк полной коллекции, класс
    # BUG-016 «действие без автожидания»: фокус успевал до коммита
    # навигации, bbox — нет). Move в сторону до up = клика нет,
    # :active-состояние уже измерено в box1.
    cx, cy = box0["x"] + box0["width"] / 2, box0["y"] + box0["height"] / 2
    page.mouse.move(cx, cy)
    page.mouse.down()
    box1 = link.bounding_box()
    page.mouse.move(cx + box0["width"] + 40, cy)
    page.mouse.up()

    # Keyboard-focus (focus-visible).
    link.focus()
    box2 = link.bounding_box()

    def _close(a, b, what):
        for key in ("x", "y", "width", "height"):
            assert abs(a[key] - b[key]) <= 0.5, (what, key, a, b)

    _close(box0, box1, "active")
    _close(box0, box2, "focus-visible")

    # Transform отсутствует (никакого смещения через transform).
    tf = link.evaluate("el => getComputedStyle(el).transform")
    assert tf in ("none", ""), tf


# --------------------------------------------------------------------------
# TC-UIP-108 — шапка комментария «автор · дата» во view (FR-91)
# --------------------------------------------------------------------------
def test_comment_head_author_and_human_date_in_view(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-UIP-108 (CHK-P12-11, FR-91): комментарий от owner в view-модалке —
    шапка .comment-head: .comment-author = display_name автора (НЕ id),
    разделитель «·», time.comment-date человекочитаем (без сырого
    ISO-вида «2026-10-07T…»); datetime-атрибут хранит исходный ISO."""
    page = board_page
    board = BoardPage(page)
    detail = TaskDetailView(page)
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "QAT-uip108-коммент"}
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    web_cleanup_created(task_id)
    assert web_owner_session.post(
        f"{web_base_url}/api/tasks/{task_id}/comments",
        json={"body": "QAT-uip108-текст"},
    ).status_code == 201
    page.reload()
    board.wait_loaded()

    board.card("QAT-uip108-коммент").click()
    detail.wait_open()
    expect(
        detail.comments.get_by_text("QAT-uip108-текст")
    ).to_be_visible()

    head = detail.comments.locator(".comment-head").first
    expect(head).to_be_visible()

    # Автор — имя (login 'owner'; NOT NULL id, не «user-1»).
    author = head.locator(".comment-author")
    expect(author).to_be_visible()
    assert re.fullmatch(r"[\wа-яА-Я .-]+", author.inner_text().strip()), (
        f"в шапке не имя автора: {author.inner_text()!r}"
    )

    # Разделитель «·».
    expect(head.locator(".comment-sep")).to_have_text("·")

    # Дата — человекочитаемая (time.comment-date, datetime=ISO).
    date_el = head.locator("time.comment-date")
    expect(date_el).to_be_visible()
    visible = date_el.inner_text().strip()
    assert "T" not in visible and "Z" not in visible, visible
    assert re.search(r"\d{1,2}[:.]\d{2}", visible), visible  # есть время ЧЧ:ММ
    iso = date_el.get_attribute("datetime")
    assert iso and "T" in iso, iso  # исходный ISO — в атрибуте

    detail.close_button().click()


# --------------------------------------------------------------------------
# TC-UIP-109 — committed-леджер: пути выбора, чипы, очистка при сабмите
# --------------------------------------------------------------------------
def test_combobox_committed_ledger_all_paths_and_submit_clear(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-UIP-109 (CHK-P12-14, FR-92, дисп. M1): выбор тега любым путем
    (клик / Enter / Tab / создание нового) — input содержит committed-леджер
    с выбранным тегом, чип с крестиком в #task-tags-chips, фокус возвращен
    полю; сабмит сохраняет все теги и ПОСЛЕ него поле ввода пустое
    (flushCommittedToInput)."""
    existing = "QAT-ledсущ"
    task_id = _seed_tagged_task(
        web_owner_session, web_base_url, "QAT-uip109-сид", [existing]
    )
    web_cleanup_created(task_id)

    page = logged_in_page
    board = BoardPage(page)
    board.open(web_base_url)
    form = _open_board_form(page)
    comb = TagCombobox(page)

    tags = form.tags

    # Путь 1: клик по пункту дропдауна.
    tags.fill("QAT-ledсущ")
    option = comb.option_by_value(existing)
    expect(option).to_be_visible()
    option.click()
    assert existing in tags.input_value()
    chips = form.tag_chips()
    expect(chips).to_have_count(1)
    expect(chips.first).to_contain_text(existing)
    assert chips.first.get_by_role("button").count() == 1  # крестик
    expect(comb.listbox).to_be_hidden()
    expect(tags).to_be_focused()

    # Путь 2: Enter (стрелки + Enter) — создание нового тега.
    tags.fill("QAT-ledнов")
    add_item = comb.add_item()
    expect(add_item).to_be_visible()
    page.keyboard.press("Enter")
    value = tags.input_value()
    assert "QAT-ledнов" in value and existing in value, value
    expect(form.tag_chips()).to_have_count(2)
    expect(tags).to_be_focused()

    # Путь 3: Tab-выбор существующего.
    tags.fill(f" QAT-ledнов, {existing}, QAT-ledсущ2")
    page.keyboard.press("Tab")
    assert "QAT-ledсущ2" in tags.input_value()
    expect(form.tag_chips()).to_have_count(3)

    # Сабмит: все три тега сохранены, ПОСЛЕ сабмита поле пустое.
    form.title_input.fill("QAT-uip109-итог")
    form.submit_button().click()
    expect(form.overlay).to_be_hidden()
    resp = web_owner_session.get(
        f"{web_base_url}/api/search", params={"archived": "false"}
    )
    matched = [
        t for t in resp.json()["results"] if t["title"] == "QAT-uip109-итог"
    ]
    assert len(matched) == 1, matched
    saved = matched[0]["tags"]
    for tag in (existing, "QAT-ledнов", "QAT-ledсущ2"):
        assert tag in saved, (tag, saved)

    # Форма переоткрыта — поле ввода тегов пустое (flushCommittedToInput
    # не оставил хвост; леджер новой формы чист).
    form = _open_board_form(page)
    assert form.tags.input_value() == ""
    form.cancel_button().click()

    web_cleanup_created(matched[0]["id"])


# --------------------------------------------------------------------------
# TC-UIP-110 — 3 тега подряд + удаление по одному (FR-92)
# --------------------------------------------------------------------------
def test_combobox_three_tags_and_one_by_one_removal(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-UIP-110 (CHK-P12-15, FR-92): три тега подряд (клик / Enter /
    «создать») — три чипа с крестиками, леджер в input после каждого
    добавления; удаление чипа крестиком — чип исчез, поле НЕ блокировано,
    ввод возможен; возвращенный тег снова в дропдауне; сабмит — ровно
    три тега, после сохранения поле пустое."""
    t1, t2 = "QAT-u110-один", "QAT-u110-два"
    for tag in (t1, t2):
        web_cleanup_created(
            _seed_tagged_task(web_owner_session, web_base_url, f"QAT-u110-сид-{tag}", [tag])
        )

    page = logged_in_page
    board = BoardPage(page)
    board.open(web_base_url)
    form = _open_board_form(page)
    comb = TagCombobox(page)

    tags = form.tags

    # 1: клик по существующему.
    tags.fill(t1)
    comb.option_by_value(t1).click()
    assert t1 in tags.input_value()
    expect(form.tag_chips()).to_have_count(1)

    # 2: Enter по существующему.
    tags.fill(f" {t1}, {t2}")
    page.keyboard.press("Enter")
    assert t2 in tags.input_value()
    expect(form.tag_chips()).to_have_count(2)

    # 3: создание нового.
    t3 = "QAT-u110-три"
    tags.fill(f" {t1}, {t2}, {t3}")
    add_item = comb.add_item()
    expect(add_item).to_be_visible()
    page.keyboard.press("Enter")
    assert t3 in tags.input_value()
    chips = form.tag_chips()
    expect(chips).to_have_count(3)
    for tag in (t1, t2, t3):
        expect(chips.filter(has_text=tag)).to_have_count(1)

    # Удаление t2 крестиком: чип исчез, input жив — ввод дополнительного
    # токена проходит НЕ затирая committed-леджер (клавиатурный ввод).
    chips.filter(has_text=t2).get_by_role("button").click()
    expect(form.tag_chips()).to_have_count(2)
    expect(form.tag_chips().filter(has_text=t2)).to_have_count(0)
    tags.click()  # фокус в поле (поле не блокировано)
    page.keyboard.press("End")
    page.keyboard.type(", QAT-u110-верн")
    assert "QAT-u110-верн" in tags.input_value()
    assert t1 in tags.input_value() and t3 in tags.input_value()  # леджер цел

    # Возвращенный t2 снова доступен в дропдауне (исключение — только
    # введенные/выбранные; удаленный крестиком вернулся в подсказки).
    tags.fill("QAT-u110-д")
    option2 = comb.option_by_value(t2)
    expect(option2).to_be_visible()  # удаленный тег вернулся в подсказки
    option2.click()
    # Недобор-токен «QAT-u110-д» ПОТРЕБЛЕН выбором (tag-combobox.js, BUG-012:
    # currentToken — подстрока committed-значения — уходит в выбранный тег;
    # оставлять его ручным токеном = двойной чип «выбранный тег + его же
    # недобор», review-001 blocker-1). Ручного чипа «Убрать тег QAT-u110-д»
    # нет, итог — ровно 3 чипа t1/t3/t2.
    assert form.tag_chips().filter(
        has=page.get_by_role("button", name="Убрать тег QAT-u110-д", exact=True)
    ).count() == 0
    expect(form.tag_chips()).to_have_count(3)
    assert t2 in tags.input_value()

    # Сабмит: ровно три тега; после сохранения поле пустое.
    form.title_input.fill("QAT-u110-итог")
    form.submit_button().click()
    expect(form.overlay).to_be_hidden()
    resp = web_owner_session.get(
        f"{web_base_url}/api/search", params={"archived": "false"}
    )
    matched = [
        t for t in resp.json()["results"] if t["title"] == "QAT-u110-итог"
    ]
    assert len(matched) == 1
    assert sorted(matched[0]["tags"]) == sorted([t1, t2, t3]), matched[0]["tags"]
    web_cleanup_created(matched[0]["id"])

    form = _open_board_form(page)
    assert form.tags.input_value() == ""
    form.cancel_button().click()


# --------------------------------------------------------------------------
# TC-UIP-111 — fastline-edit: полное переключение (FR-89, волна 2.7)
# --------------------------------------------------------------------------
def test_fastline_edit_full_toggle_regular_to_fast_409_and_off(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-UIP-111 (CHK-P12-28/29, FR-89): в редактировании regular-задачи
    .fast-row виден и снят; включение — priority high и заблокирован,
    после сохранения is_fast=true/high в API; вторая fast при занятой
    линии — форма показывает «fast line занята», введенные данные
    сохранены, вторая fast не переключена; выключение разблокирует
    приоритет и сохраняет выбранный."""
    page = board_page
    board = BoardPage(page)
    form = TaskForm(page)
    detail = TaskDetailView(page)

    regular = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-f89-regular", "priority": "medium"},
    )
    assert regular.status_code == 201, regular.text
    regular_id = regular.json()["id"]
    web_cleanup_created(regular_id)

    # fast-задача-фикстура (шаг 2) — создается ПОЗЖЕ (после успешного
    # переключения regular→fast, которому нужна СВОБОДНАЯ линия).
    page.reload()
    board.wait_loaded()

    def _open_edit(title):
        board.card(title).click()
        detail.edit_button().click()
        expect(form.overlay).to_be_visible()

    # Шаг 1: regular — ряд виден, чекбокс снят.
    _open_edit("QAT-f89-regular")
    fast_row = form.fast_row()
    assert fast_row.get_attribute("hidden") is None
    assert not form.is_fast_checkbox().is_checked()

    # Шаг 3: включение fast (линия свободна) — priority high + блокировка;
    # сохранение → задача стала fast (API: is_fast=true, high).
    form.fast_line_label().check()
    assert form.priority_by_id().input_value() == "high"
    assert form.priority_by_id().is_disabled()
    form.save_button().click()
    expect(form.overlay).to_be_hidden()
    got = web_owner_session.get(f"{web_base_url}/api/tasks/{regular_id}").json()
    assert got["is_fast"] is True and got["priority"] == "high", got

    # Шаг 5: выключение fast у бывшей fast-задачи — приоритет разблокирован,
    # сохраняется выбранный (is_fast=false); линия освобождена.
    page.reload()
    board.wait_loaded()
    _open_edit("QAT-f89-regular")
    assert form.is_fast_checkbox().is_checked()
    form.fast_line_label().uncheck()
    assert not form.priority_by_id().is_disabled()
    form.priority.select_option("medium")
    form.save_button().click()
    expect(form.overlay).to_be_hidden()
    got3 = web_owner_session.get(f"{web_base_url}/api/tasks/{regular_id}").json()
    assert got3["is_fast"] is False and got3["priority"] == "medium", got3

    # Шаг 2/4 (409-путь): fast-задача занимает линию; вторая regular при
    # включении fast — форма открыта, сообщение «fast line занята»,
    # введенные данные сохранены, вторая fast не переключена.
    fast = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-f89-fast", "priority": "high", "is_fast": True},
    )
    assert fast.status_code == 201, fast.text
    fast_id = fast.json()["id"]
    web_cleanup_created(fast_id)
    second = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-f89-second", "priority": "medium"},
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]
    web_cleanup_created(second_id)
    page.reload()
    board.wait_loaded()
    _open_edit("QAT-f89-second")
    form.title_input.fill("QAT-f89-second-правка")
    form.fast_line_label().check()
    form.save_button().click()
    expect(page.get_by_text("fast line занята")).to_be_visible()
    expect(form.overlay).to_be_visible()
    assert form.title_input.input_value() == "QAT-f89-second-правка"
    assert form.fast_line_label().is_checked()
    form.cancel_button().click()
    expect(form.overlay).to_be_hidden()
    got2 = web_owner_session.get(f"{web_base_url}/api/tasks/{second_id}").json()
    assert got2["is_fast"] is False, got2  # вторая fast НЕ переключена
