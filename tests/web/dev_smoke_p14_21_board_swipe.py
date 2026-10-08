"""Смоук-проверка задачи 2.1 add-responsive-mobile (dev-самопроверка,
НЕ QA-артефакт): доска ≤480px — свайп-колонки со scroll-snap, индикатор
точек, быстрое «Выполнено» ≥44px; desktop ≥1024 — без изменений.

Запуск (одной командой, против стенда :18443):
  EKOTOV_WIKI_BASE_URL=http://127.0.0.1:18443 EKOTOV_WIKI_DB_PATH=/tmp/qa2141/app.db \
  .venv/bin/python -m pytest tests/web/dev_smoke_p14_21_board_swipe.py -q
"""

import os
import sqlite3

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web]

BASE_URL = os.environ.get("EKOTOV_WIKI_BASE_URL", "http://127.0.0.1:18443")
DB_PATH = os.environ.get("EKOTOV_WIKI_DB_PATH", "/tmp/qa2141/app.db")
MARKER = "QASM21-"
PASSWORD = os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!")


def _session():
    """Сессия с локальным сбросом Secure-флага куки (стенд по http; браузер
    считает localhost trustworthy, requests — нет; паттерн LocalhostSession
    tests/api/conftest.py: Secure-кука меняется в jar после логина)."""
    import requests

    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"login": "owner", "password": PASSWORD},
    )
    assert r.status_code == 200
    for c in s.cookies:
        c.secure = False
    return s


def _create_task(s, title):
    r = s.post(f"{BASE_URL}/api/tasks", json={"title": title})
    assert r.status_code == 201, r.text
    return r.json()


def _cleanup():
    if not DB_PATH or not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        ids = [
            r[0]
            for r in conn.execute(
                "SELECT id FROM tasks WHERE title LIKE ?", (MARKER + "%",)
            ).fetchall()
        ]
        if not ids:
            return
        q = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM task_tags WHERE task_id IN ({q})", ids)
        conn.execute(f"DELETE FROM comments WHERE task_id IN ({q})", ids)
        conn.execute(f"DELETE FROM tasks WHERE id IN ({q})", ids)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _clean():
    _cleanup()
    yield
    _cleanup()


def _page(browser, width=375, height=812, reduced_motion=False):
    context = browser.new_context(
        base_url=BASE_URL,
        viewport={"width": width, "height": height},
        has_touch=True,
        is_mobile=True,
        device_scale_factor=2,
        reduced_motion="reduce" if reduced_motion else "no-preference",
    )
    page = context.new_page()
    page.goto(f"{BASE_URL}/login")
    page.fill("#login", "owner")
    page.fill("#password", PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    return context, page


def _seed_three_columns():
    """По задаче в каждом из трех столбцов (todo/in_progress/done)."""
    s = _session()
    a = _create_task(s, MARKER + "col-todo")["id"]
    b = _create_task(s, MARKER + "col-progress")["id"]
    c = _create_task(s, MARKER + "col-done")["id"]
    for tid, status in ((b, "in_progress"), (c, "done")):
        r = s.post(
            f"{BASE_URL}/api/tasks/{tid}/move", json={"status": status}
        )
        assert r.status_code == 200, r.text
    s.close()
    return a, b, c


def _swipe_board(page, dx, steps=8):
    """Реальный touch-свайп по контейнеру #board через CDP Input.dispatchTouchEvent:
    нативный скролл-движок реагирует только на настоящий инпут-поток
    (синтетические TouchEvent скролл не двигают)."""
    box = page.locator("#board").bounding_box()
    sx = box["x"] + box["width"] / 2
    sy = box["y"] + box["height"] / 2
    cdp = page.context.new_cdp_session(page)
    cdp.send(
        "Input.dispatchTouchEvent",
        {
            "type": "touchStart",
            "touchPoints": [{"x": sx, "y": sy, "id": 1}],
        },
    )
    for i in range(1, steps + 1):
        cdp.send(
            "Input.dispatchTouchEvent",
            {
                "type": "touchMove",
                "touchPoints": [
                    {"x": sx + (dx * i) / steps, "y": sy, "id": 1}
                ],
            },
        )
    cdp.send(
        "Input.dispatchTouchEvent",
        {
            "type": "touchEnd",
            "touchPoints": [],
        },
    )
    cdp.detach()


# --------------------------------------------------------------------------
# 1. Свайп-колонки: snap, листание, край следующей колонки, dots follow
# --------------------------------------------------------------------------
def test_board_swipe_snap_and_dots_follow(browser):
    _seed_three_columns()
    context, page = _page(browser)
    try:
        board = page.locator("#board")
        # Контейнер: overflow-x auto + snap mandatory (board.css ≤480px)
        styles = page.evaluate(
            """() => {
              const cs = getComputedStyle(document.getElementById('board'));
              const col = document.querySelector('#board .board-column');
              const ccs = getComputedStyle(col);
              const doc = document.documentElement;
              return {
                overflowX: cs.overflowX,
                snapType: cs.scrollSnapType,
                colFlexBasis: ccs.flexBasis,
                colSnapAlign: ccs.scrollSnapAlign,
                colWidth: col.getBoundingClientRect().width,
                boardScrollWidth: document.getElementById('board').scrollWidth,
                pageScrollWidthX: doc.scrollWidth - window.innerWidth,
              };
            }"""
        )
        assert styles["overflowX"] == "auto", styles
        assert "mandatory" in styles["snapType"], styles
        assert styles["colSnapAlign"] == "start", styles
        # 82vw на 375px ≈ 307px (мокап 03: 307px)
        assert abs(styles["colWidth"] - 0.82 * 375) <= 2, styles
        # три колонки не влезают в контейнер → он скроллится
        assert styles["boardScrollWidth"] > 375, styles
        # NFR-26: страница вне контейнера — без прокрутки по X
        assert styles["pageScrollWidthX"] <= 0, styles

        # Индикатор точек: 3 точки, первая активна
        dots = page.locator(".board-dots button")
        expect(dots).to_have_count(3)
        expect(page.locator('.board-dots button[aria-current="true"]')).to_have_count(1)
        assert page.locator('.board-dots button[aria-current="true"]').evaluate(
            "b => Array.from(b.parentNode.children).indexOf(b)"
        ) == 0

        # Свайп влево → вторая колонка; snap: scrollLeft прилипает к колонке.
        # Граница колонки в координатах скролла: rect.left колонки минус
        # rect.left контейнера (offsetLeft тут = сдвиг от offsetParent
        # app-shell, НЕ от контейнера — урок реализации).
        _swipe_board(page, -200)
        page.wait_for_timeout(700)  # инерция + snap
        state = page.evaluate(
            """() => {
              const board = document.getElementById('board');
              const col = board.querySelectorAll('.board-column')[1];
              const colScroll =
                col.getBoundingClientRect().left - board.getBoundingClientRect().left +
                board.scrollLeft;
              return {
                scrollLeft: board.scrollLeft,
                maxScroll: board.scrollWidth - board.clientWidth,
                colScroll,
                active: Array.from(document.querySelectorAll('.board-dots button'))
                  .findIndex(b => b.getAttribute('aria-current') === 'true'),
              };
            }"""
        )
        # Прилипание по колонке: вторая колонка выровнена по левому краю
        # контейнера с учетом переполнения (snap-оседание: scrollLeft = min(
        # colScroll, maxScroll), ±2px). Mandatory-snap дотягивает каретку.
        settled = min(state["colScroll"], state["maxScroll"])
        assert abs(state["scrollLeft"] - settled) <= 2, state
        # Активная точка следует за скроллом
        assert state["active"] == 1, state

        # Тап по третьей точке → скролл к третьей колонке
        page.locator(".board-dots button").nth(2).click()
        page.wait_for_timeout(900)  # smooth-скролл
        state2 = page.evaluate(
            """() => {
              const board = document.getElementById('board');
              const col = board.querySelectorAll('.board-column')[2];
              const colScroll =
                col.getBoundingClientRect().left - board.getBoundingClientRect().left +
                board.scrollLeft;
              return {
                scrollLeft: board.scrollLeft,
                maxScroll: board.scrollWidth - board.clientWidth,
                colScroll,
                active: Array.from(document.querySelectorAll('.board-dots button'))
                  .findIndex(b => b.getAttribute('aria-current') === 'true'),
              };
            }"""
        )
        settled2 = min(state2["colScroll"], state2["maxScroll"])
        assert abs(state2["scrollLeft"] - settled2) <= 2, state2
        assert state2["active"] == 2, state2
    finally:
        context.close()


# --------------------------------------------------------------------------
# 2. Быстрое «Выполнено»: тач-таргет ≥44px, работает с тача, без drag
# --------------------------------------------------------------------------
def test_quick_done_touch_target_and_action(browser):
    s = _session()
    tid = _create_task(s, MARKER + "quick")["id"]
    s.close()
    context, page = _page(browser)
    try:
        card = page.locator(".task-card", has_text=MARKER + "quick").first
        quick = card.locator(".task-quick-done")
        expect(quick).to_be_visible()
        box = quick.bounding_box()
        assert box["height"] >= 44, box  # NFR-23
        assert box["width"] >= 44, box

        # Тач-тап по кнопке — задача переезжает в «Выполнено» (без DnD)
        quick.tap()
        page.wait_for_load_state("networkidle")
        done_col = page.locator("#column-done [data-cards]")
        expect(done_col.locator(".task-card", has_text=MARKER + "quick")).to_have_count(1)

        s = _session()
        r = s.get(f"{BASE_URL}/api/tasks/{tid}")
        assert r.json()["status"] == "done", r.text
        s.close()
    finally:
        context.close()


# --------------------------------------------------------------------------
# 3. prefers-reduced-motion: тап по точке — скролл без анимации (ОГР-17)
# --------------------------------------------------------------------------
def test_dots_scroll_instant_under_reduced_motion(browser):
    _seed_three_columns()
    context, page = _page(browser, reduced_motion=True)
    try:
        board = page.locator("#board")
        scroll_behavior = page.evaluate(
            "() => getComputedStyle(document.getElementById('board')).scrollBehavior"
        )
        assert scroll_behavior == "auto", scroll_behavior

        t0 = page.evaluate("() => performance.now()")
        page.locator(".board-dots button").nth(1).click()
        page.wait_for_function(
            """() => document.getElementById('board').scrollLeft > 100""",
            timeout=2000,
        )
        elapsed = page.evaluate("() => performance.now()") - t0
        # Мгновенный скролл: прыжок за <200ms (smooth занял бы ~300-500ms)
        assert elapsed < 200, elapsed
    finally:
        context.close()


# --------------------------------------------------------------------------
# 4. Desktop ≥1024: доска без изменений (NFR-29)
# --------------------------------------------------------------------------
def test_desktop_board_unchanged(browser):
    _seed_three_columns()
    context, page = _page(browser, width=1280, height=800)
    try:
        styles = page.evaluate(
            """() => {
              const cs = getComputedStyle(document.getElementById('board'));
              const doc = document.documentElement;
              return {
                overflowX: cs.overflowX,
                snapType: cs.scrollSnapType,
                wrap: cs.flexWrap,
                dotsCount: document.querySelectorAll('.board-dots button').length,
                dotsHidden: document.querySelector('.board-dots')
                  ? document.querySelector('.board-dots').hidden : null,
                quickCount: document.querySelectorAll('.task-quick-done').length,
                colWidths: Array.from(document.querySelectorAll('#board .board-column'))
                  .map(c => Math.round(c.getBoundingClientRect().width)),
                pageScrollWidthX: doc.scrollWidth - window.innerWidth,
              };
            }"""
        )
        # Три колонки рядом: без свайп-контейнера, без точек, без quick-done
        assert styles["overflowX"] == "visible", styles
        assert styles["snapType"] in ("none", ""), styles
        assert styles["wrap"] == "nowrap" or styles["wrap"] == "initial", styles
        # Точки скрыты на desktop: DOM-заготовка есть (buildDots не зависит
        # от ширины), но hidden + display:none (CSS-ветка только ≤480px)
        dots_hidden = page.evaluate(
            """() => {
              const dots = document.querySelector('.board-dots');
              if (!dots) return true;
              return dots.hidden || getComputedStyle(dots).display === 'none';
            }"""
        )
        assert dots_hidden, styles
        # Quick-done: DOM строится на всех ширинах (инвариант рендера), но
        # на desktop НЕ ВИДЕН (display:none вне ≤480px; перенос через DnD,
        # NFR-29 «desktop без изменений»)
        quick_visible = page.evaluate(
            """() => Array.from(document.querySelectorAll('.task-quick-done'))
              .filter(b => getComputedStyle(b).display !== 'none').length"""
        )
        assert quick_visible == 0, styles
        # Колонки равные (flex:1), все видны в контейнере
        assert len(styles["colWidths"]) == 3, styles
        assert all(abs(w - styles["colWidths"][0]) <= 2 for w in styles["colWidths"]), styles
        assert styles["pageScrollWidthX"] <= 0, styles
    finally:
        context.close()
