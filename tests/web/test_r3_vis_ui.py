"""Домен vis (QA-этап 5, change add-r3-visual-foundation, FR-32/ОГР-12/ОВ-20).

Кейсы_TC (approved test-model/approved/add-r3-visual-foundation/):
- TC-vis-101: hover-переход карточки (обязательный минимум пресета В):
  transition с ненулевой длительностью, hover → transform/box-shadow,
  заголовок — терракотовый акцент (--p-clay-700).
- TC-vis-102: оформленный пустой state столбца: .board-column-empty,
  dashed 2px, min-height ≥ 48px, ::before-контент, градиент пресета В;
  появление задачи снимает класс.
- TC-vis-103: плавное перемещение карточки: подсветка drop-target при
  dragover, анимация v-in (duration ~0.32s, fill backwards) после drop.
- TC-vis-104: анимация появления новой карточки: v-in, cubic-bezier,
  после отыгрыша карточка в кадре без смещений.
- TC-vis-105 (НФТ): prefers-reduced-motion: reduce отключает анимации
  (animation-name none, transition 0s), функциональность сохранена
  (drop-target применяется, drag-ghost теряет наклон, drop работает).
  Механика DnD — dispatchEvent с DataTransfer (dnd_helpers).

Примечание к TC-vis-101/103: в рамках BUG-003 (test-model/bugs/
BUG-003-dnd-drop-target-lost-todo-inprogress.md) класс drop-target
удерживается только на столбце done (дефект onDragOver в cards.js);
соответствующие ассерты targetClass в dnd-домене падают на todo/
in_progress. Здесь подсветка проверяется на столбце done, где класс
удерживается (перенос в «Выполнено»), — кейсам это разрешает шаг «на
столбце-приемнике» без фиксации конкретного столбца.
"""

import json

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui
from tests.web.dnd_helpers import dnd_dispatch
from tests.web.test_r3_dnd_ui import _card, _column, _wait_board

pytestmark = [pytest.mark.web, pytest.mark.must]


def _computed(page, selector: str, prop: str, pseudo: str | None = None) -> str:
    return page.evaluate(
        "([sel, prop, pseudo]) => getComputedStyle(document.querySelector(sel), pseudo)[prop]",
        [selector, prop, pseudo],
    )


# --------------------------------------------------------------------------
# TC-vis-101 — «hover-переход карточки (обязательный минимум)» (Must)
# --------------------------------------------------------------------------
def test_card_hover_transition_and_accent_title(board_page, web_cleanup_created):
    """TC-vis-101: #board несет preset-v; transition ненулевой; hover →
    transform ≠ none (подъем −4px / масштаб 1.01) и box-shadow ≠ none;
    цвет заголовка меняется на терракотовый (--p-clay-700)."""
    page = board_page
    create_task_via_ui(page, "QAT-vis-hover")
    card = _card(page, "QAT-vis-hover")
    expect(card).to_be_visible()
    web_cleanup_created(int(card.get_attribute("data-task-id")))

    assert "preset-v" in page.locator("#board").get_attribute("class")

    def _card_prop(prop: str) -> str:
        return card.evaluate(f"el => getComputedStyle(el)['{prop}']")

    before = {"transform": _card_prop("transform"), "boxShadow": _card_prop("boxShadow")}
    transition = _card_prop("transitionDuration")
    assert any(part not in ("0s", "0.000000s") for part in transition.split(", ")), transition

    card.hover()
    page.wait_for_timeout(300)  # отыгрыш transition (160ms токен)

    after_transform = _card_prop("transform")
    after_shadow = _card_prop("boxShadow")
    assert after_transform != "none", after_transform
    assert after_transform != before["transform"]
    assert after_shadow not in ("none", ""), after_shadow

    title_color = card.evaluate(
        "el => getComputedStyle(el.querySelector('.task-card-title')).color"
    )
    clay = page.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--p-clay-700').trim()"
    )
    assert clay, "токен --p-clay-700 пуст"
    # Сверка по значению цвета: computed отдаёт rgb(), токен — hex (#rrggbb).
    hex = clay.lstrip("#")
    clay_rgb = f"rgb({int(hex[0:2], 16)}, {int(hex[2:4], 16)}, {int(hex[4:6], 16)})"
    assert clay_rgb == title_color, (clay, clay_rgb, title_color)


# --------------------------------------------------------------------------
# TC-vis-102 — «оформленный пустой state пустого столбца» (Must)
# --------------------------------------------------------------------------
def test_empty_column_state_styled_and_cleared(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-vis-102: столбец «В работе» освобождается самим кейсом
    (чужие задачи — переводом в «Ожидает», не удалением); пустой столбец
    — .board-column-empty, dashed 2px, min-height ≥ 48px, ::before не
    none, фон с linear-gradient; создание задачи снимает класс."""
    page = board_page

    # Освободить «В работе»: чужие задачи — в «Ожидает» (не портим).
    body = web_owner_session.get(f"{web_base_url}/api/board").json()
    for task in body["columns"]["in_progress"]:
        moved = web_owner_session.post(
            f"{web_base_url}/api/tasks/{task['id']}/move",
            json={"status": "todo"},
        )
        assert moved.status_code in (200, 409), moved.text
    page.reload()
    _wait_board(page)

    column = page.locator('.board-column[data-status="in_progress"]')
    expect(column).to_contain_class("board-column-empty")

    border_style = _computed(page, '[data-status="in_progress"]', "borderTopStyle")
    border_width = _computed(page, '[data-status="in_progress"]', "borderTopWidth")
    min_height = _computed(page, '[data-status="in_progress"]', "minHeight")
    assert border_style == "dashed", border_style
    assert border_width == "2px", border_width
    assert int(float(min_height.rstrip("px"))) >= 48, min_height

    before_content = _computed(
        page, '[data-status="in_progress"]', "content", "::before"
    )
    assert before_content not in ("none", "normal", ""), before_content
    background = _computed(page, '[data-status="in_progress"]', "backgroundImage")
    assert "linear-gradient" in background, background

    # Шаг 4: задача в столбце → класс снят (создание + перевод селектом
    # «Столбец» — механика move_via_card_select; новая задача создается
    # в «Ожидает», сdd §3.2).
    create_task_via_ui(page, "QAT-vis-заполнение", priority="high")
    card = _card(page, "QAT-vis-заполнение")
    expect(card).to_be_visible()
    web_cleanup_created(int(card.get_attribute("data-task-id")))
    card.click()
    page.get_by_label("Столбец").select_option("in_progress")
    new_card = _column(page, "in_progress").get_by_role("article").filter(
        has_text="QAT-vis-заполнение"
    )
    expect(new_card).to_be_visible()
    expect(column).not_to_contain_class("board-column-empty")


# --------------------------------------------------------------------------
# TC-vis-103 — «плавное перемещение карточки (без телепорта)» (Must)
# --------------------------------------------------------------------------
def test_card_move_animated_v_in(board_page, web_cleanup_created):
    """TC-vis-103: dragstart/dragover/drop (в «Выполнено» — столбец, где
    подсветка удерживается, см. примечание модуля); после drop карточка
    отрисована с анимацией v-in: animation-name v-in, duration ~0.32s,
    fill-mode backwards; при dragover drop-target на приемнике."""
    page = board_page
    create_task_via_ui(page, "QAT-vis-move")
    card = _card(page, "QAT-vis-move")
    expect(card).to_be_visible()
    web_cleanup_created(int(card.get_attribute("data-task-id")))

    result = dnd_dispatch(page, card, _column(page, "done"), drop=False)
    # Подсветка приемника при dragover (см. примечание модуля: done).
    assert "drop-target" in result["targetClass"], result
    # drop не выполнялся (drop=False) — завершаем жест вручную.
    page.evaluate(
        """() => {
          const card = document.querySelector('.task-card.drag-ghost');
          if (card) { card.dispatchEvent(new DragEvent("dragend", {bubbles: true})); }
          document.querySelectorAll('.board-column.drop-target').forEach(
            (col) => col.classList.remove("drop-target"));
        }"""
    )
    result = dnd_dispatch(page, card, _column(page, "done"))
    expect(_column(page, "done").get_by_role("article").filter(
        has_text="QAT-vis-move"
    )).to_be_visible()

    # Computed-параметры анимации читаемы в любой фазе, пока класс применен
    # (перерисовка после drop вешает v-in на ВСЕ карточки — читаем с нашей).
    anim_name = card.evaluate("el => getComputedStyle(el).animationName")
    anim_duration = card.evaluate("el => getComputedStyle(el).animationDuration")
    anim_fill = card.evaluate("el => getComputedStyle(el).animationFillMode")
    assert anim_name == "v-in", anim_name
    assert anim_duration == "0.32s", anim_duration
    assert anim_fill == "backwards", anim_fill


# --------------------------------------------------------------------------
# TC-vis-104 — «анимация появления карточек» (Must)
# --------------------------------------------------------------------------
def test_new_card_entrance_animation_v_in(board_page, web_cleanup_created):
    """TC-vis-104: задача создана через UI-форму; карточка появляется с
    v-in (duration ~0.32s, timing — cubic-bezier); после отыгрыша — в
    кадре (opacity 1, без смещения)."""
    page = board_page
    create_task_via_ui(page, "QAT-vis-появление")
    card = _card(page, "QAT-vis-появление")
    expect(card).to_be_visible()
    web_cleanup_created(int(card.get_attribute("data-task-id")))

    anim_name = card.evaluate("el => getComputedStyle(el).animationName")
    anim_duration = card.evaluate("el => getComputedStyle(el).animationDuration")
    timing = card.evaluate("el => getComputedStyle(el).animationTimingFunction")
    assert anim_name == "v-in", anim_name
    assert anim_duration == "0.32s", anim_duration
    assert "cubic-bezier" in timing, timing

    page.wait_for_timeout(400)  # отыгрыш 320ms
    opacity = card.evaluate("el => getComputedStyle(el).opacity")
    transform = card.evaluate("el => getComputedStyle(el).transform")
    assert opacity == "1", opacity
    assert transform in ("none", "matrix(1, 0, 0, 1, 0, 0)"), transform


# --------------------------------------------------------------------------
# TC-vis-105 — «prefers-reduced-motion отключает анимации» (Must, НФТ)
# --------------------------------------------------------------------------
def test_reduced_motion_disables_animations_keeps_function(
    browser, web_server, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-vis-105 (CHK-168): контекст с emulateMedia prefers-reduced-motion:
    animation-name none, transition-duration 0s; drop-target применяется
    мгновенно (функциональность сохранена); drag-ghost теряет наклон
    (transform none), полупрозрачность остается; drop → задача в «В работе»."""
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    static_url = web_server["static_url"]
    if static_url:
        page.route(
            f"{web_base_url}/static/**",
            lambda route: route.fulfill(
                response=route.fetch(
                    url=static_url + route.request.url.partition("/static")[2]
                )
            ),
        )
    try:
        page.goto(f"{web_base_url}/login")
        page.get_by_label("Логин").fill("owner")
        page.get_by_label("Пароль").fill("QaOwner_Pass_1!")
        page.get_by_role("button", name="Войти").click()
        page.get_by_role("heading", name="Доска", exact=True).wait_for()
        _wait_board(page)

        created = web_owner_session.post(
            f"{web_base_url}/api/tasks", json={"title": "QAT-vis-rm"}
        )
        assert created.status_code == 201, created.text
        task_id = created.json()["id"]
        web_cleanup_created(task_id)
        page.reload()
        _wait_board(page)

        card = _card(page, "QAT-vis-rm")
        expect(card).to_be_visible()

        # Шаг 1: анимации отключены.
        assert card.evaluate("el => getComputedStyle(el).animationName") == "none"
        durations = card.evaluate(
            "el => getComputedStyle(el).transitionDuration"
        ).split(", ")
        assert all(d == "0s" for d in durations), durations

        # Шаг 2: DnD в «В работе»; dragover — подсветка применяется мгновенно.
        result = dnd_dispatch(page, card, _column(page, "in_progress"))
        assert "drop-target" in result["targetClass"], result

        # Шаг 4: drag-призрак — transform none, полупрозрачность осталась.
        # Дефект Р3 (гонка): moveTask с шага 2 может быть еще в полете
        # (dragInProgress=true) — onDragStart делает preventDefault, и
        # drag-ghost не ставится. dragInProgress — переменная модуля
        # (type="module", в окне недоступна); наблюдаемое следствие
        # завершения move — перерисовка доски renderBoard'ом: карточка
        # QAT-vis-rm появляется в «В работе» (новый DOM-узел). Ждем именно
        # этого (expect-поллинг, не sleep) и берем карточку по её
        # АКТУАЛЬНОМУ местоположению — слепой селектор «первая карточка
        # todo» после перерисовки либо null, либо чужая карточка.
        expect(_column(page, "in_progress").get_by_role("article").filter(
            has_text="QAT-vis-rm"
        )).to_be_visible()
        page.evaluate(
            """() => {
              window.__qaCard = document.querySelector(
                '.board-column[data-status="in_progress"] article');
              const ev = new DragEvent("dragstart", {bubbles: true, cancelable: true});
              Object.defineProperty(ev, "dataTransfer", {value: new DataTransfer()});
              window.__qaCard.dispatchEvent(ev);
            }"""
        )
        ghost_class = page.evaluate(
            "() => new Promise(r => requestAnimationFrame(() => r(window.__qaCard.className)))"
        )
        assert "drag-ghost" in ghost_class, ghost_class
        ghost_style = page.evaluate(
            """() => {
              const el = window.__qaCard;
              const cs = getComputedStyle(el);
              return { transform: cs.transform, opacity: cs.opacity };
            }"""
        )
        assert ghost_style["transform"] in ("none", ""), ghost_style
        assert 0 < float(ghost_style["opacity"]) < 1, ghost_style
        page.evaluate(
            """() => {
              window.__qaCard.dispatchEvent(
                new DragEvent("dragend", {bubbles: true}));
            }"""
        )

        # Шаг 3: drop выполнен — задача в «В работе».
        expect(_column(page, "in_progress").get_by_role("article").filter(
            has_text="QAT-vis-rm"
        )).to_be_visible()
    finally:
        context.close()

