"""P23 fix-mobile (рапорт Заказчика с прода: «все поехало» — зона FASTLINE
не адаптирована; требование: «должно быть идентично с основным бордом»).

Зона FASTLINE на мобильных ведет себя как колонки канбана ≤480px
(board.css, P14-паттерн): свайп-контейнер со scroll-snap, колонка 82vw
с превью края следующей, страница вне зоны без прокрутки по X (NFR-26),
тач-таргеты ≥44px (NFR-23), быстрое «Выполнено» — тач-путь переноса.
Ветка 481–768px — десктопная раскладка (ряд колонок ≥220px), как у
канбана. Вьюпорт тестов — iPhone-класс 390×844 (device-эмуляция,
has_touch/is_mobile); скриншоты — design/p23-fastline/mobile/.
"""

from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.web.conftest import OWNER_LOGIN, OWNER_PASSWORD
from tests.web.dnd_helpers import dnd_dispatch

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

# iPhone 14/15-класс (task fix-mobile: 390×844).
MOBILE_VIEWPORT = {"width": 390, "height": 844}

# Live-скриншоты — в репозиторий, design/p23-fastline/mobile/ (task).
SHOT_DIR = (
    Path(__file__).resolve().parents[2] / "design" / "p23-fastline" / "mobile"
)


def _zone_column(page, stage: str):
    """Столбец зоны по этапу (data-fastline-stage = status)."""
    return page.locator(
        f'#fastline .fastline-column[data-fastline-stage="{stage}"]'
    )


def _touch_swipe(page, selector: str, dx: int, steps: int = 8) -> None:
    """Реальный touch-свайп через CDP Input.dispatchTouchEvent (паттерн
    dev_smoke_p14_21_board_swipe: нативный скролл-движок реагирует только
    на настоящий инпут-поток)."""
    box = page.locator(selector).bounding_box()
    sx = box["x"] + box["width"] / 2
    sy = box["y"] + box["height"] / 2
    cdp = page.context.new_cdp_session(page)
    cdp.send(
        "Input.dispatchTouchEvent",
        {"type": "touchStart", "touchPoints": [{"x": sx, "y": sy, "id": 1}]},
    )
    for i in range(1, steps + 1):
        cdp.send(
            "Input.dispatchTouchEvent",
            {
                "type": "touchMove",
                "touchPoints": [{"x": sx + (dx * i) / steps, "y": sy, "id": 1}],
            },
        )
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()


@pytest.fixture
def mobile_page(page, web_base_url, web_server):
    """Страница с device-эмуляцией iPhone-класса 390×844 и той же
    маршрутизацией стенда, что у `page` (роль nginx: /static/* и
    /api/search* на соседние процессы)."""
    context = page.context.browser.new_context(
        base_url=web_base_url,
        viewport=MOBILE_VIEWPORT,
        has_touch=True,
        is_mobile=True,
        device_scale_factor=2,
    )
    static_url = web_server["static_url"]
    search_url = web_server.get("search_url")

    if static_url:
        def _to_static(route):
            new_url = static_url + route.request.url.partition("/static")[2]
            route.fulfill(response=route.fetch(url=new_url))

        context.route(f"{web_base_url}/static/**", _to_static)
    if search_url:
        def _to_search(route):
            suffix = route.request.url.partition("/api/")[2]
            route.fulfill(response=route.fetch(url=f"{search_url}/api/{suffix}"))

        for path in ("/api/search", "/api/search/", "/api/suggestions", "/api/suggestions/"):
            context.route(f"{web_base_url}{path}*", _to_search)

    p = context.new_page()
    p.goto(f"{web_base_url}/login")
    p.get_by_label("Логин").fill(OWNER_LOGIN)
    p.get_by_label("Пароль").fill(OWNER_PASSWORD)
    p.get_by_role("button", name="Войти").click()
    p.get_by_role("heading", name="Доска", exact=True).wait_for()
    expect(p.locator("#board")).to_have_attribute("data-loaded", "true")
    yield p
    context.close()


def _fastline_metrics(page) -> dict:
    """Наблюдаемая геометрия/стили зоны на мобильной ветке."""
    return page.evaluate(
        """() => {
          const zone = document.getElementById('fastline');
          const fb = document.querySelector('.fastline-board');
          const cols = [...document.querySelectorAll('.fastline-column')];
          const cs = getComputedStyle(fb);
          const first = cols[0].getBoundingClientRect();
          const fbRect = fb.getBoundingClientRect();
          const doc = document.documentElement;
          return {
            zoneVisible: zone.offsetHeight > 0 && zone.offsetWidth > 0,
            overflowX: cs.overflowX,
            snapType: cs.scrollSnapType,
            flexWrap: cs.flexWrap,
            colFlexBasis: getComputedStyle(cols[0]).flexBasis,
            colSnapAlign: getComputedStyle(cols[0]).scrollSnapAlign,
            colCount: cols.length,
            colWidth: first.width,
            boardClientW: fb.clientWidth,
            boardScrollW: fb.scrollWidth,
            boardLeft: fbRect.left,
            colLeft: first.left,
            pageOverflowX: doc.scrollWidth - window.innerWidth,
          };
        }"""
    )


def test_fastline_empty_zone_swipes_like_board(mobile_page):
    """TC-p23-122: Пустая зона на 390×844 = свайп-паттерн канбана ≤480px: контейнер
    overflow-x auto + snap mandatory, колонка 82vw (≈319.8px на 390),
    3 столбца, зона скроллится, страница по X не скроллит (NFR-26),
    пустые столбцы без подсказок (ОВ-3). Скриншот — design/. """
    page = mobile_page
    m = _fastline_metrics(page)
    assert m["zoneVisible"], m
    assert m["colCount"] == 3, m
    # Дословно паттерн .board ≤480px (board.css, P14).
    assert m["overflowX"] == "auto", m
    assert "mandatory" in m["snapType"], m
    assert m["flexWrap"] == "nowrap", m
    assert m["colSnapAlign"] == "start", m
    # 82vw на 390px ≈ 319.8px (мокап 03; тот же flex-basis, что .board-column).
    assert abs(m["colWidth"] - 0.82 * 390) <= 2, m
    # Три колонки 82vw не влезают в 390px → зона скроллится, как канбан.
    assert m["boardScrollW"] > m["boardClientW"], m
    # NFR-26: страница вне контейнеров — без прокрутки по X.
    assert m["pageOverflowX"] <= 0, m
    # Пустые столбцы зоны без подсказок (ОВ-3, v2-empty).
    expect(page.locator(".fastline .board-column-empty")).to_have_count(0)
    # Пустой столбец держит высоту (контейнер карточек, v2: 72px).
    height = _zone_column(page, "todo").locator("[data-cards]").evaluate(
        "el => el.getBoundingClientRect().height"
    )
    assert height >= 72, height

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOT_DIR / "after-empty-390.png"), full_page=True)


def test_fastline_occupied_touch_targets_and_swipe(mobile_page, web_owner_session, web_base_url, web_cleanup_created):
    """TC-p23-123: Занятая зона на 390×844: карточка в столбце зоны, тач-таргеты
    ≥44px (NFR-23: «+ Fast-задача» и быстрое «Выполнено» — тач-путь
    переноса, как в канбане), реальный touch-свайп листает зону со
    snap-оседанием на колонке. Скриншот — design/."""
    page = mobile_page
    # Fast-задача через API (предусловие; карточку чистит фабрика).
    resp = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAP23MOB-fast", "is_fast": True, "priority": "high"},
    )
    assert resp.status_code == 201, resp.text
    task_id = resp.json()["id"]
    web_cleanup_created(task_id)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    card = _zone_column(page, "todo").locator("article").filter(has_text="QAP23MOB-fast")
    expect(card).to_be_visible()

    # Тач-таргеты ≥44px (NFR-23, P14-стандарт).
    add_h = page.locator("#fastline-add-button").evaluate(
        "el => el.getBoundingClientRect().height"
    )
    assert add_h >= 44, add_h
    quick = card.locator(".task-quick-done")
    expect(quick).to_be_visible()
    quick_h = quick.evaluate("el => el.getBoundingClientRect().height")
    assert quick_h >= 44, quick_h

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOT_DIR / "after-occupied-390.png"), full_page=True)

    # Реальный touch-свайп влево по зоне → листание со snap-оседанием.
    _touch_swipe(page, ".fastline-board", -200)
    page.wait_for_timeout(700)  # инерция + snap (паттерн dev_smoke P14)
    state = page.evaluate(
        """() => {
          const fb = document.querySelector('.fastline-board');
          const col = document.querySelectorAll('.fastline-column')[1];
          const colScroll =
            col.getBoundingClientRect().left - fb.getBoundingClientRect().left +
            fb.scrollLeft;
          return {scrollLeft: fb.scrollLeft, maxScroll: fb.scrollWidth - fb.clientWidth,
                  colScroll};
        }"""
    )
    assert state["scrollLeft"] > 0, state
    settled = min(state["colScroll"], state["maxScroll"])
    assert abs(state["scrollLeft"] - settled) <= 2, state

    # Тач-перенос этапа: быстрое «Выполнено» уводит карточку в «Выполнено»
    # ЗОНЫ (тач-замена DnD, как у канбана ≤480px).
    quick.click()
    done_card = _zone_column(page, "done").locator("article").filter(
        has_text="QAP23MOB-fast"
    )
    expect(done_card).to_be_visible()
    expect(_zone_column(page, "todo").locator("article")).to_have_count(0)


def test_fastline_dnd_states_on_mobile(mobile_page, web_owner_session, web_base_url, web_cleanup_created):
    """TC-p23-124: DnD-состояния зоны на мобильном вьюпорте идентичны desktop
    (классы ставит cards.js): fast-карта над столбцом зоны — голубой
    drop-target (перенос этапов); обычная карта над зоной — красный
    drop-forbidden с бейджем запрета (Э2)."""
    page = mobile_page
    fast = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAP23MOB-dnd-fast", "is_fast": True},
    )
    assert fast.status_code == 201, fast.text
    plain = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "QAP23MOB-dnd-plain"}
    )
    assert plain.status_code == 201, plain.text
    web_cleanup_created(fast.json()["id"])
    web_cleanup_created(plain.json()["id"])
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # fast → столбец зоны: разрешенный приемник (drop-target).
    # drop=False: подсветка ставится на dragover; drop не нужен и увел бы
    # жест в POST (dragInProgress заблокировал бы второй жест).
    fast_card = page.locator('article[data-task-id="%d"]' % fast.json()["id"])
    result = dnd_dispatch(page, fast_card, _zone_column(page, "in_progress"), drop=False)
    assert "drop-target" in result["targetClass"], result

    # обычная → столбец зоны: запрет (drop-forbidden + бейдж).
    plain_card = page.locator('article[data-task-id="%d"]' % plain.json()["id"])
    result = dnd_dispatch(page, plain_card, _zone_column(page, "todo"), drop=False)
    assert "drop-forbidden" in result["targetClass"], result
    assert result["dragoverPrevented"] is False, result  # drop не дается

    # Бейдж запрета виден В МОМЕНТ жеста (dragend в dnd_dispatch гасит
    # подсветку — читаем display бейджа между dragover и dragend).
    badge_display = page.evaluate(
        """(taskId) => new Promise((resolve) => {
          const card = document.querySelector('article[data-task-id="' + taskId + '"]');
          const target = document.querySelector(
            '.fastline-column[data-fastline-stage="todo"]');
          const dt = new DataTransfer();
          const fire = (el, type) => {
            const ev = new DragEvent(type, {bubbles: true, cancelable: true});
            Object.defineProperty(ev, "dataTransfer", {value: dt});
            el.dispatchEvent(ev);
          };
          fire(card, "dragstart");
          requestAnimationFrame(() => {
            fire(target, "dragover");
            const badge = target.querySelector(".drop-forbidden-badge");
            const display = getComputedStyle(badge).display;
            const forbidden = target.classList.contains("drop-forbidden");
            fire(card, "dragend");
            resolve({display, forbidden});
          });
        })""",
        plain.json()["id"],
    )
    assert badge_display == {"display": "flex", "forbidden": True}, badge_display


def test_fastline_768_row_layout_like_board(mobile_page):
    """TC-p23-125: Ветка 481–768px (проверка 768): у зоны и канбана одна десктопная
    раскладка — ряд из 3 колонок (≥220px), контейнер НЕ свайп-контейнер;
    мобильные включения зоны (82vw/snap) не протекают выше 480px."""
    page = mobile_page
    page.set_viewport_size({"width": 768, "height": 1024})
    page.wait_for_timeout(150)
    m = page.evaluate(
        """() => {
          const fb = document.querySelector('.fastline-board');
          const cols = [...document.querySelectorAll('.fastline-column')];
          const board = document.getElementById('board');
          return {
            fbOverflowX: getComputedStyle(fb).overflowX,
            fbFlexWrap: getComputedStyle(fb).flexWrap,
            colWidths: cols.map(c => Math.round(c.getBoundingClientRect().width)),
            colMinW: getComputedStyle(cols[0]).minWidth,
            boardOverflowX: getComputedStyle(board).overflowX,
            colsInRow: cols[0].getBoundingClientRect().top === cols[2].getBoundingClientRect().top,
          };
        }"""
    )
    # Раскладка ряда — как канбан (у канбана ≤768px свайпа тоже нет).
    assert m["fbOverflowX"] == "visible", m
    assert m["fbFlexWrap"] == "nowrap", m
    assert m["boardOverflowX"] == "visible", m
    assert m["colsInRow"], m
    for w in m["colWidths"]:
        assert w >= 220, m  # desktop-минимум колонки зоны вернулся
