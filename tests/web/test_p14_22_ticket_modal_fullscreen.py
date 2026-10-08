"""add-responsive-mobile 2.2 — playwright-кейсы fullscreen-модалки тикета (TC-P14-221).

Трассировка (openspec/changes/add-responsive-mobile):
- specs/board/spec.md Scenario «Fullscreen-модалка на мобильном» (FR-102,
  ОВ-4; device-эмуляция 375×812): модалка занимает весь вьюпорт (inset 0);
  просмотр и редактирование — в одной fullscreen-оболочке («Редактировать»
  заменяет содержимое, возврат — в просмотр); закрытие возвращает на доску
  в прежнюю scroll-позицию.
- Scenario «Поля без авто-зума и клавиатура не перекрывает поле»: инпуты
  font-size ≥16px (NFR-24); фокус → scrollIntoView активного поля (design §4).
- NFR-23: крестик ≥44px (кнопки ≥44px).
- Scenario «Desktop-модалки не меняются» (NFR-29): ≥1024px — модалки в
  существующем desktop-виде (центрированное окно max-width, паддинг подложки).
- Действующая 480px-ветка формы FR-62 (одна колонка, full-width) сохранена.

Прогон: живой процессный nginx-стенд :18443 (app :8080 + search :8378;
изоляция — QAT22-префикс задач + teardown БД по префиксу; паттерн
test_p14_41_lightbox_swipe.py).

Запуск (одной командой, ≤30 сек):
  pytest tests/web/test_p14_22_ticket_modal_fullscreen.py -q
"""

import os
import sqlite3

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

BASE_URL = os.environ.get("EKOTOV_WIKI_BASE_URL", "http://127.0.0.1:18443")
DB_PATH = os.environ.get("EKOTOV_WIKI_DB_PATH", "/tmp/qa2141/app.db")
MARKER = "QAT22-"
PASSWORD = os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!")

VIEW_OVERLAY = "#task-detail-overlay"
FORM_OVERLAY = "#task-form-overlay"


def _session():
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
    r = s.post(
        f"{BASE_URL}/api/tasks",
        json={"title": title, "description": "Тело описания задачи 2.2"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _cleanup():
    """Чистая доска на тест: удаление QAT22-хвостов (FK: task_tags первым)."""
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
        conn.execute(
            "DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM task_tags)"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _clean_qat22():
    _cleanup()
    yield
    _cleanup()


def _mobile_page(browser):
    """375×812 (iPhone X-class), touch включен."""
    context = browser.new_context(
        base_url=BASE_URL,
        viewport={"width": 375, "height": 812},
        has_touch=True,
        is_mobile=True,
        device_scale_factor=2,
    )
    page = context.new_page()
    page.goto(f"{BASE_URL}/login")
    page.fill("#login", "owner")
    page.fill("#password", PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    return context, page


def _open_view(page, title):
    card = page.locator(".task-card", has_text=title).first
    card.scroll_into_view_if_needed()
    card.click()
    expect(page.locator(VIEW_OVERLAY)).to_be_visible()


def _rect(page, selector):
    return page.evaluate(
        "([sel]) => { const r = document.querySelector(sel).getBoundingClientRect();"
        " return {top: r.top, left: r.left, width: r.width, height: r.height}; }",
        [selector],
    )


def _inner(page):
    return page.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")


# --------------------------------------------------------------------------
# TC-P14-2.2-01 — просмотр: fullscreen (inset 0), крестик ≥44px, тело
# скроллится, подложка (страница) не скроллится
# --------------------------------------------------------------------------
def test_view_modal_fullscreen_on_mobile(browser):
    s = _session()
    title = MARKER + "fullscreen-view"
    _create_task(s, title)
    s.close()

    context, page = _mobile_page(browser)
    try:
        _open_view(page, title)
        vp = _inner(page)
        overlay = _rect(page, VIEW_OVERLAY)
        modal = _rect(page, f"{VIEW_OVERLAY} .modal")
        # fullscreen: панель и подложка = вьюпорт (inset 0, зазор ≤1px)
        assert overlay["width"] == vp["w"] and overlay["height"] == vp["h"], overlay
        assert abs(modal["top"]) <= 1 and abs(modal["left"]) <= 1, modal
        assert abs(modal["width"] - vp["w"]) <= 1, modal
        assert abs(modal["height"] - vp["h"]) <= 1, modal

        # крестик ≥44px (NFR-23)
        close_box = _rect(page, f"{VIEW_OVERLAY} .modal-close")
        assert close_box["width"] >= 44 and close_box["height"] >= 44, close_box

        # тело скроллится (длинный контент), подложка-страница — нет
        scrollable = page.evaluate(
            """([sel]) => {
              const body = document.querySelector('#task-detail-overlay .task-view-body');
              const doc = document.documentElement;
              return { bodyScroll: body.scrollHeight - body.clientHeight,
                       pageX: doc.scrollWidth - window.innerWidth,
                       bodyOverflowY: getComputedStyle(body).overflowY };
            }""",
            [VIEW_OVERLAY],
        )
        assert scrollable["bodyOverflowY"] == "auto", scrollable
        assert scrollable["pageX"] <= 0, scrollable
        # page overflow hidden (подложка не скроллится)
        body_overflow = page.evaluate(
            "() => getComputedStyle(document.body).overflow"
        )
        assert body_overflow == "hidden", body_overflow
    finally:
        context.close()


# --------------------------------------------------------------------------
# TC-P14-2.2-02 — «Редактировать» заменяет содержимое на форму ТОЙ ЖЕ
# оболочки (ОВ-4); выход из формы возвращает в просмотр (Escape, dirty —
# после confirm, FR-61)
# --------------------------------------------------------------------------
def test_edit_swaps_to_same_shell_and_back(browser):
    s = _session()
    title = MARKER + "edit-shell"
    _create_task(s, title)
    s.close()

    context, page = _mobile_page(browser)
    try:
        _open_view(page, title)
        vp = _inner(page)
        page.get_by_role("button", name="Редактировать").click()
        expect(page.locator(FORM_OVERLAY)).to_be_visible()
        expect(page.locator(VIEW_OVERLAY)).to_be_hidden()

        # та же fullscreen-оболочка (ОВ-4): форма занимает тот же вьюпорт,
        # крестик формы ≥44px (NFR-23)
        modal = _rect(page, f"{FORM_OVERLAY} .modal")
        assert abs(modal["width"] - vp["w"]) <= 1, modal
        assert abs(modal["height"] - vp["h"]) <= 1, modal
        close_box = _rect(page, f"{FORM_OVERLAY} .modal-close")
        assert close_box["width"] >= 44 and close_box["height"] >= 44, close_box

        # возврат в просмотр: Escape на ЧИСТОЙ форме (FR-61, без confirm) —
        # форма закрывается на просмотр той же задачи
        page.keyboard.press("Escape")
        expect(page.locator(FORM_OVERLAY)).to_be_hidden()
        expect(page.locator(VIEW_OVERLAY)).to_be_visible()
        modal_view = _rect(page, f"{VIEW_OVERLAY} .modal")
        assert abs(modal_view["width"] - vp["w"]) <= 1, modal_view

        # повторный заход: грязная форма (правка названия) — Escape после
        # confirm возвращает в просмотр (FR-61 не регрессировал)
        page.get_by_role("button", name="Редактировать").click()
        expect(page.locator(FORM_OVERLAY)).to_be_visible()
        page.get_by_label("Название").fill(title + " правка")
        page.once("dialog", lambda d: d.accept())
        page.keyboard.press("Escape")
        expect(page.locator(FORM_OVERLAY)).to_be_hidden()
        expect(page.locator(VIEW_OVERLAY)).to_be_visible()
    finally:
        context.close()


# --------------------------------------------------------------------------
# TC-P14-2.2-03 — закрытие возвращает доску в ТОЧНО прежнюю scroll-позицию
# --------------------------------------------------------------------------
def test_close_restores_exact_board_scroll(browser):
    s = _session()
    title = MARKER + "scroll-restore"
    _create_task(s, title)
    s.close()

    context, page = _mobile_page(browser)
    try:
        # длинная доска: 12 задач, чтобы скролл был возможен
        s2 = _session()
        for i in range(12):
            _create_task(s2, MARKER + f"filler-{i:02d}")
        s2.close()
        page.reload()
        expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

        page.evaluate("window.scrollTo(0, 250)")
        page.wait_for_timeout(50)
        before = page.evaluate("window.scrollY")
        assert before == 250, "доска должна проскроллиться (задач много)"

        # JS-клик по карточке: без автоскролла Playwright к карточке —
        # позиция на момент открытия модалки = 250 (продукт сохраняет
        # именно ее; физклики автоскроллят страницу перед кликом)
        page.evaluate(
            """(title) => {
              const cards = [...document.querySelectorAll('.task-card')];
              const card = cards.find(c => c.textContent.includes(title));
              card.click();
            }""",
            title,
        )
        expect(page.locator(VIEW_OVERLAY)).to_be_visible()
        # блокировка подложки: скролл страницы заморожен
        assert page.evaluate("getComputedStyle(document.body).overflow") == "hidden"
        page.get_by_role("button", name="Закрыть", exact=True).click()
        expect(page.locator(VIEW_OVERLAY)).to_be_hidden()
        page.wait_for_timeout(50)
        after = page.evaluate("window.scrollY")
        assert after == before, f"scrollY: до={before}, после={after}"

        # и через крестик (повторное открытие — тот же сохран)
        page.evaluate(
            """(title) => {
              const cards = [...document.querySelectorAll('.task-card')];
              const card = cards.find(c => c.textContent.includes(title));
              card.click();
            }""",
            title,
        )
        expect(page.locator(VIEW_OVERLAY)).to_be_visible()
        page.locator("#task-view-close").click()
        expect(page.locator(VIEW_OVERLAY)).to_be_hidden()
        page.wait_for_timeout(50)
        assert page.evaluate("window.scrollY") == before
    finally:
        context.close()


# --------------------------------------------------------------------------
# TC-P14-2.2-04 — инпуты формы ≥16px (NFR-24) + фокус → scrollIntoView
# (клавиатура iOS): активное поле прокручивается в видимую область
# --------------------------------------------------------------------------
def test_inputs_16px_and_focus_scroll_into_view(browser):
    s = _session()
    title = MARKER + "inputs"
    _create_task(s, title)
    s.close()

    context, page = _mobile_page(browser)
    try:
        page.get_by_role("button", name="Создать задачу").click()
        expect(page.locator(FORM_OVERLAY)).to_be_visible()

        # font-size всех полей формы ≥16px (NFR-24)
        sizes = page.evaluate(
            """() => {
              const sels = ['#task-title', '#task-description', '#task-priority',
                            '#task-category', '#task-due-date', '#task-tags'];
              return sels.map(sel => {
                const el = document.querySelector(sel);
                return { sel, fs: parseFloat(getComputedStyle(el).fontSize) };
              });
            }"""
        )
        for item in sizes:
            assert item["fs"] >= 16, item

        # тач-таргеты кнопок формы ≥44px (NFR-23)
        heights = page.evaluate(
            """() => ['#task-form-submit', '#task-form-cancel'].map(sel => {
              const r = document.querySelector(sel).getBoundingClientRect();
              return { sel, h: r.height };
            })"""
        )
        for item in heights:
            assert item["h"] >= 44, item

        # scrollIntoView при фокусе: длинное описание внизу — фокус на
        # поле «Теги» (ниже вьюпорта) прокручивает его в видимую область
        vp_h = _inner(page)["h"]
        page.evaluate("document.querySelector('#task-tags').focus()")
        page.wait_for_timeout(100)
        tags_box = _rect(page, "#task-tags")
        in_view = tags_box["top"] >= 0 and tags_box["top"] < vp_h
        assert in_view, f"поле не в видимой области после фокуса: {tags_box}"
    finally:
        context.close()


# --------------------------------------------------------------------------
# TC-P14-2.2-05 — FR-62 сохранена: форма ≤480px одной колонкой, поля
# full-width, без прокрутки страницы по X
# --------------------------------------------------------------------------
def test_form_480_single_column_fullwidth_kept(browser):
    s = _session()
    s.close()

    context, page = _mobile_page(browser)
    try:
        page.get_by_role("button", name="Создать задачу").click()
        expect(page.locator(FORM_OVERLAY)).to_be_visible()
        vp = _inner(page)
        metrics = page.evaluate(
            """(vw) => {
              const sels = ['#task-title', '#task-description', '#task-priority',
                            '#task-category', '#task-due-date', '#task-tags'];
              return {
                widths: sels.map(sel => document.querySelector(sel).getBoundingClientRect().width),
                pageX: document.documentElement.scrollWidth - vw,
              };
            }""",
            vp["w"],
        )
        for w in metrics["widths"]:
            assert w >= vp["w"] * 0.9, f"поле не full-width: {w} при {vp['w']}"
        assert metrics["pageX"] <= 0, metrics
    finally:
        context.close()


# --------------------------------------------------------------------------
# TC-P14-2.2-06 — desktop ≥1024: модалки в прежнем desktop-виде (NFR-29):
# центрированное окно max-width 520/640, подложка с паддингом, body не
# блокируется
# --------------------------------------------------------------------------
def test_desktop_modals_unchanged(browser, web_base_url):
    s = _session()
    title = MARKER + "desktop-unchanged"
    _create_task(s, title)
    s.close()

    context = browser.new_context(
        base_url=BASE_URL, viewport={"width": 1280, "height": 800}
    )
    page = context.new_page()
    try:
        page.goto(f"{BASE_URL}/login")
        page.fill("#login", "owner")
        page.fill("#password", PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

        # просмотр: окно НЕ fullscreen — max-width 640, фон-подложка видна
        _open_view(page, title)
        modal = _rect(page, f"{VIEW_OVERLAY} .modal")
        assert modal["width"] <= 640 + 2, modal
        assert modal["height"] < 800, modal
        close_box = _rect(page, f"{VIEW_OVERLAY} .modal-close")
        assert 39 < close_box["width"] < 41, close_box  # desktop 40×40 (FR-28)
        assert page.evaluate("getComputedStyle(document.body).overflow") == "visible"

        # форма: max-width 520
        page.get_by_role("button", name="Редактировать").click()
        expect(page.locator(FORM_OVERLAY)).to_be_visible()
        modal_form = _rect(page, f"{FORM_OVERLAY} .modal")
        assert modal_form["width"] <= 520 + 2, modal_form
        assert page.evaluate("getComputedStyle(document.body).overflow") == "visible"
    finally:
        context.close()
