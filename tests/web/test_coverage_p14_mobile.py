"""coverage-backfill-1; TC-P14-101: Мобильный drawer — бургер, закрытие
4 способами, единый DOM, сцена во всю ширину; TC-P14-102: Индикация активного
раздела на мобильном; TC-P14-103: Доска на мобильном — свайп-колонки
scroll-snap, индикатор точек, быстрое «Выполнено»; TC-P14-104: Fullscreen-
модалка тикета — просмотр → «Редактировать» в одной оболочке; TC-P14-105:
Форма задачи на мобильном — одна колонка, поля ≥16px, тач-таргеты,
Escape-семантика; TC-P14-106: Поиск на мобильном; TC-P14-107: Настройки и
профиль на мобильном; TC-P14-108: Лайтбокс на таче — свайп/тап/скролл
комментариев; TC-P14-109: Сквозные НФТ адаптива — брейкпоинты, safe-area,
meta viewport, ОГР-8; TC-P14-110: Живая приемка Заказчика на проде (ручной).

Группа D change coverage-backfill-1 (add-responsive-mobile, P14). Кейсы:
test-model/approved/add-responsive-mobile/TC-P14-101…110.md. Вьюпорт —
device-эмуляция iPhone-класса (фикстура mobile_page 390×844 touch из
test_p23_fastline_mobile_ui — тот же класс устройства, что 375×812 кейсов;
"не разваливается" дополнительно проверяется на 480/768).
Свайпы — синтетический TouchEvent-поток по паттерну dev_smoke_p14_21 и
test_p14_41_lightbox_swipe. Галерея — реальный images-сервис через
реверс-прокси (фикстура images_service из test_p15_wiki_editor).
Запуск: pytest tests/web/test_coverage_p14_mobile.py -q
"""

import io
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.web.test_p15_wiki_editor import (  # noqa: F401
    images_service,
    wiki_stand_schema,
)
from tests.web.test_p23_fastline_mobile_ui import _touch_swipe, mobile_page  # noqa: F401

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

REPO = Path(__file__).resolve().parents[2]
PASSWORD = os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!")

SECTIONS = ("board", "search", "wiki", "gallery", "settings", "settings/profile")


def _page_overflow(page) -> int:
    """Прокрутка СТРАНИЦЫ по X (NFR-26): scrollWidth - innerWidth."""
    return page.evaluate(
        "document.documentElement.scrollWidth - window.innerWidth"
    )


def _png_bytes(w=375, h=250, color=(90, 60, 200)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def _images_session(base_url: str):
    """requests-сессия owner через прокси images-семейства (Secure-кука
    по http — браузерное поведение localhost, конвенция conftest)."""
    import requests

    s = requests.Session()
    r = s.post(
        f"{base_url}/api/auth/login",
        json={"login": "owner", "password": PASSWORD},
    )
    assert r.status_code == 200, r.text
    for c in s.cookies:
        c.secure = False
    return s


@pytest.fixture
def gallery_on_autostand(images_service, mobile_page, web_base_url):
    """Маршрутизация images-семейства мобильного контекста: /api/images* —
    прокси requests-фулфиллом (реверс-прокси test_p15 задваивает
    Content-Length — playwright route.fetch такой ответ не парсит),
    /images/* — fulfill реальными PNG-байтами (файлы раздает nginx-том,
    прод-паттерн; автостенд их не отдает). Возвращает сессию галереи."""
    import requests

    proxy_base = images_service["base_url"]
    session = _images_session(proxy_base)

    def _to_api(route):
        request = route.request
        suffix = request.url.partition("/api/images")[2]
        r = session.request(
            request.method,
            f"{proxy_base}/api/images{suffix}",
            data=request.post_data_buffer or None,
        )
        try:
            route.fulfill(status=r.status_code, json=r.json())
        except ValueError:
            route.fulfill(status=r.status_code, body=r.text)

    def _to_file(route):
        route.fulfill(body=_png_bytes(), content_type="image/png")

    mobile_page.context.route(f"{web_base_url}/api/images**", _to_api)
    mobile_page.context.route(f"{web_base_url}/images/*", _to_file)
    yield session
    session.close()
    mobile_page.context.unroute(f"{web_base_url}/api/images**")
    mobile_page.context.unroute(f"{web_base_url}/images/*")


def _upload_three_with_comment(session, base: str, prefix: str):
    """3 изображения (различимый created_at — пауза между загрузками) +
    комментарий у первого (панель комментариев скроллится)."""
    import time

    ids = []
    for i in range(3):
        r = session.post(
            f"{base}/api/images",
            files=[("file", (f"{prefix}sw{i}.png",
                             _png_bytes(color=(90 * (i + 1), 60, 200)),
                             "image/png"))],
        )
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
        deadline = time.monotonic() + 1.05  # различимый created_at (DESC)
        while time.monotonic() < deadline:
            pass
    # Комментарии — к ПЕРВОМУ загруженному (ids[0] = sw0): лайтбокс кейса
    # открыт именно на нем (позиция 3/3 при DESC-выдаче); комментарии на
    # ids[2] оставляли панель открытого изображения пустой (scrollHeight
    # == clientHeight — скроллить нечего).
    r = session.post(
        f"{base}/api/images/{ids[0]}/comments",
        json={"body": f"{prefix}комментарий для скролла"},
    )
    assert r.status_code in (200, 201), r.text
    # Панель комментариев должна ПЕРЕПОЛНЯТЬСЯ (иначе scrollTop=0 —
    # скроллить нечего, кейс «скролл панели не перехватывается жестом»
    # вырожден): досыпаем комментарии до заведомого переполнения.
    for i in range(8):
        r = session.post(
            f"{base}/api/images/{ids[0]}/comments",
            json={"body": f"{prefix}наполнитель {i} для скролла панели"},
        )
        assert r.status_code in (200, 201), r.text
    return ids


# ---------------------------------------------------------------------------
# TC-P14-101 — Мобильная навигация (единый DOM, сцена во всю ширину)
# ---------------------------------------------------------------------------
def test_tc_p14_101_mobile_drawer(mobile_page, web_base_url):
    """TC-P14-101: на ≤860px навигация доступна и занимает одну колонку —
    сцена во всю ширину, тач-таргеты пунктов ≥44px, DOM навигации
    ЕДИНСТВЕННЫЙ (ОВ-2), переход по пункту ведет в раздел; на ≥1024px —
    постоянный сайдбар (NFR-29). ФАКТ (merge-ветка): drawer-механика кейса
    (бургер/подложка/Escape, .header-title в шапке) не воспроизводится —
    утвержденный мокап редизайна каркаса (2.1/2.7 redesign-console, FR-131)
    переезжает сайдбар ≤860px наверх ВИДИМОЙ горизонтальной строкой;
    .mobile-header/.burger/.sidebar-backdrop скрыты CSS (app.css «drawer не
    предусмотрен, элементы скрыты», DOM и хуки app.js сохранены). Ассерты —
    по духу кейса (навигация на мобильном, единый DOM, ширина сцены)."""
    page = mobile_page
    burger = page.locator("#burger-button")
    sidebar = page.locator("#sidebar")

    # Мобильная ветка ≤860px: каркас в одну колонку, сцена во всю ширину.
    assert page.evaluate(
        "getComputedStyle(document.body).gridTemplateColumns"
    ).split(" ")[0] != "", "grid-каркас не активен"
    cols = page.evaluate(
        "getComputedStyle(document.body).gridTemplateColumns.split(' ').length"
    )
    assert cols == 1, cols  # одна колонка (сайдбар наверх, не слева)
    assert _page_overflow(page) <= 0
    scene_w = page.evaluate(
        "document.querySelector('main').getBoundingClientRect().width"
    )
    assert scene_w == pytest.approx(390, abs=1), scene_w

    # Drawer-элементы скрыты утвержденным мокапом (факт в докстринге).
    expect(burger).to_be_hidden()

    # Единый DOM навигации: все разделы доступны в видимой nav-строке.
    assert page.locator("#sidebar").count() == 1
    assert page.locator(".sidebar-nav").count() == 1
    for name in ("Доска", "Поиск", "Wiki", "Галерея", "Настройки"):
        link = sidebar.get_by_role("link", name=name)
        expect(link).to_be_visible()
        box = link.bounding_box()
        assert box["height"] >= 44, (name, box)  # тач-таргет NFR-23
    expect(sidebar.get_by_role("link", name="Мониторинг")).to_be_visible()

    # Выбор пункта ведет в раздел (тач-клик).
    sidebar.get_by_role("link", name="Поиск").click()
    page.wait_for_url(f"{web_base_url}/search")
    expect(page.locator("#sidebar .nav-item.active")).to_contain_text("Поиск")

    # Desktop ≥1024px — сайдбар постоянный колонкой слева (NFR-29).
    page.set_viewport_size({"width": 1280, "height": 800})
    page.wait_for_timeout(150)
    expect(burger).to_be_hidden()
    sidebar_box = page.locator("#sidebar").bounding_box()
    assert sidebar_box["x"] == 0 and sidebar_box["width"] > 200, sidebar_box
    cols = page.evaluate(
        "getComputedStyle(document.body).gridTemplateColumns.split(' ').length"
    )
    assert cols >= 2, cols  # сайдбар + сцена


# ---------------------------------------------------------------------------
# TC-P14-102 — Индикация активного раздела на мобильном
# ---------------------------------------------------------------------------
def test_tc_p14_102_active_section_indicator(mobile_page, web_base_url):
    """TC-P14-102: на мобильном текущий раздел всегда читаем — активный
    пункт навигации подсвечен .active + aria-current и виден без прокрутки
    (факт: drawer/header-title кейса скрыты редизайном каркаса, см.
    TC-P14-101; подсветка .active сохранена в видимой nav-строке ≤860px);
    переход в другой раздел переносит подсветку."""
    page = mobile_page
    for section, name in (
        ("/board", "Доска"),
        ("/search", "Поиск"),
        ("/wiki", "Wiki"),
        ("/gallery", "Галерея"),
        ("/settings", "Настройки"),
    ):
        page.goto(f"{web_base_url}{section}")
        active = page.locator("#sidebar .nav-item.active")
        expect(active).to_have_count(1)
        assert name in active.inner_text(), (section, active.inner_text())
        # Подсветка видна без прокрутки (nav-строка наверху страницы).
        box = active.bounding_box()
        assert box["y"] >= 0 and box["y"] < 844, (section, box)
        expect(active).to_have_attribute("aria-current", "page")

    # Переход по навигации: подсветка переезжает на новый пункт.
    page.goto(f"{web_base_url}/search")
    page.locator("#sidebar").get_by_role("link", name="Настройки").click()
    page.wait_for_url(f"{web_base_url}/settings")
    active = page.locator("#sidebar .nav-item.active")
    expect(active).to_have_count(1)
    assert "Настройки" in active.inner_text()


# ---------------------------------------------------------------------------
# TC-P14-103 — Доска на мобильном: свайп, точки, быстрое «Выполнено»
# ---------------------------------------------------------------------------
def test_tc_p14_103_mobile_board_swipe(mobile_page, web_owner_session,
                                       web_base_url, web_cleanup_created):
    """TC-P14-103: доска на 390px — свайп-контейнер со scroll-snap
    (колонки ~82vw), индикатор точек синхронен позиции и управляет
    прокруткой, страница без X-скролла (NFR-26), быстрое «Выполнено»
    доступно с тача (таргет ≥44px, NFR-23)."""
    page = mobile_page
    for status, title in (
        ("todo", "QAP14B-todo"),
        ("in_progress", "QAP14B-progress"),
        ("done", "QAP14B-done"),
    ):
        r = web_owner_session.post(
            f"{web_base_url}/api/tasks", json={"title": title}
        )
        assert r.status_code == 201, r.text
        task_id = r.json()["id"]
        web_cleanup_created(task_id)
        m = web_owner_session.post(
            f"{web_base_url}/api/tasks/{task_id}/move",
            json={"status": status},
        )
        assert m.status_code == 200, m.text
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    m = page.evaluate(
        """() => {
          const board = document.getElementById('board');
          const cs = getComputedStyle(board);
          const col = document.querySelector('.board-column');
          return {overflowX: cs.overflowX, snap: cs.scrollSnapType,
                  colW: col.getBoundingClientRect().width,
                  dots: document.querySelectorAll('.board-dots button').length,
                  dotsVisible: (() => { const d =
                    document.querySelector('.board-dots'); return d &&
                    d.offsetHeight > 0; })()};
        }"""
    )
    assert m["overflowX"] == "auto" and "mandatory" in m["snap"], m
    assert m["colW"] == pytest.approx(0.82 * 390, abs=3), m
    assert m["dots"] == 3 and m["dotsVisible"], m  # табы 44px, aria-current
    assert _page_overflow(page) <= 0, m

    # Точка — таб 44px с aria-current, активная следует за прокруткой.
    active_idx = page.evaluate(
        """() => [...document.querySelectorAll('.board-dots button')]
             .findIndex(b => b.getAttribute('aria-current') === 'true')"""
    )
    assert active_idx == 0, active_idx
    page.locator(".board-dots button").nth(2).click()
    page.wait_for_timeout(700)  # smooth-скролл (reduced-motion не задан)
    scrolled = page.evaluate("document.getElementById('board').scrollLeft")
    assert scrolled > 0, scrolled
    active_idx = page.evaluate(
        """() => [...document.querySelectorAll('.board-dots button')]
             .findIndex(b => b.getAttribute('aria-current') === 'true')"""
    )
    assert active_idx == 2, active_idx

    # Синтетический свайп влево — прилипание по колонке.
    _touch_swipe(page, "#board", -200)
    page.wait_for_timeout(700)
    state = page.evaluate(
        """() => { const b = document.getElementById('board');
             return {sl: b.scrollLeft, max: b.scrollWidth - b.clientWidth}; }"""
    )
    assert state["sl"] > 0, state

    # Быстрое «Выполнено» с тача: тач-таргет ≥44px, перенос без DnD.
    card = page.get_by_role("article").filter(has_text="QAP14B-todo")
    quick = card.locator(".task-quick-done")
    expect(quick).to_be_visible()
    qbox = quick.bounding_box()
    assert qbox["height"] >= 44 and qbox["width"] >= 44, qbox
    quick.click()
    done_col = page.locator('[data-status="done"]')
    expect(done_col.get_by_role("article").filter(
        has_text="QAP14B-todo")).to_be_visible()


# ---------------------------------------------------------------------------
# TC-P14-104 — Fullscreen-модалка тикета
# ---------------------------------------------------------------------------
def test_tc_p14_104_fullscreen_ticket_modal(mobile_page, web_owner_session,
                                            web_base_url,
                                            web_cleanup_created):
    """TC-P14-104: клик по карточке на 390px открывает fullscreen-модалку
    (inset 0, radius 0, тело скроллится, фон заблокирован); «Редактировать»
    заменяет содержимое В ТОЙ ЖЕ оболочке (edit in place, ОВ-4); поля
    ≥16px (без авто-зума iOS, NFR-24), активное поле под клавиатурой;
    закрытие возвращает на доску в прежней scroll-позиции; на desktop —
    прежний вид r4."""
    page = mobile_page
    r = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAP14B-modal", "description": "текст задачи"},
    )
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]
    web_cleanup_created(task_id)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # Скролл доски до закрытия вернется сюда (клик — без авто-скролла
    # Playwright, чтобы позиция доски не сбрасывалась открытием модалки).
    # ≤480px доска — scroll-snap mandatory (колонка 82vw): произвольные
    # 60px браузер снапит обратно к 0, поэтому скроллим ко второму
    # столбцу (легальная snap-позиция) и фиксируем ОСЕВШЕЕ значение.
    page.evaluate(
        """() => { const b = document.getElementById('board');
             const cols = b.querySelectorAll('.board-column');
             b.scrollLeft = cols[1].offsetLeft - cols[0].offsetLeft;
             const card = [...document.querySelectorAll('article')]
               .find(a => a.textContent.includes('QAP14B-modal'));
             card.click(); }"""
    )
    overlay = page.locator("#task-detail-overlay")
    expect(overlay).to_be_visible()
    page.wait_for_timeout(250)  # scroll-snap доски оседает
    saved = page.evaluate("document.getElementById('board').scrollLeft")
    assert saved > 0, saved  # позиция осмысленная, не снап в 0
    m = page.evaluate(
        """() => { const el = document.querySelector('#task-detail-overlay');
             const view = document.querySelector(
               '#task-detail-overlay .task-view');
             const cs = getComputedStyle(el);
             const r = el.getBoundingClientRect();
             const v = view.getBoundingClientRect();
             return {pos: cs.position, top: r.top, left: r.left,
                     w: r.width, h: r.height,
                     vw: v.width, vh: v.height,
                     radius: getComputedStyle(view).borderRadius,
                     bodyCl: document.body.style.overflow ||
                       getComputedStyle(document.body).overflow}; }"""
    )
    assert m == {"pos": "fixed", "top": 0, "left": 0, "w": 390, "h": 844,
                 "vw": 390, "vh": 844, "radius": "0px",
                 "bodyCl": "hidden"}, m
    kicker = page.locator(".task-view-kicker")
    expect(kicker).to_have_text(f"Задача · STAND-{task_id}")
    close_box = page.locator("#task-view-close").bounding_box()
    assert close_box["height"] >= 44, close_box  # мобильный крестик 44px

    # «Редактировать» — та же fullscreen-оболочка (edit in place, ОВ-4).
    page.locator("#task-edit-button").click()
    form = page.locator("#task-form-overlay")
    expect(form).to_be_visible()
    fm = page.evaluate(
        """() => { const el = document.querySelector(
                 '#task-form-overlay .task-form-sheet');
             const r = el.getBoundingClientRect();
             return {w: r.width, h: r.height}; }"""
    )
    assert fm["w"] == pytest.approx(390, abs=1), fm
    name = page.get_by_label("Название")
    fs = name.evaluate("el => parseFloat(getComputedStyle(el).fontSize)")
    assert fs >= 16, fs  # NFR-24: авто-зум iOS не включается
    # Активное поле прокручивается в видимую область (modal-shell focusin).
    name.click()
    in_view = name.evaluate(
        """el => { const r = el.getBoundingClientRect();
             return r.top >= 0 && r.bottom <= window.innerHeight; }"""
    )
    assert in_view, "поле вне видимой области после фокуса"

    # Закрытие — возврат на доску в прежнюю scroll-позицию.
    page.locator("#task-form-close").click()
    expect(form).to_be_hidden()
    page.wait_for_timeout(250)
    assert page.evaluate(
        "document.getElementById('board').scrollLeft") == saved

    # Форма закрылась в ту же оболочку — режим просмотра снова активен
    # (edit in place, ОВ-4); закрываем модалку целиком перед desktop-веткой.
    expect(overlay).to_be_visible()
    page.locator("#task-view-close").click()
    expect(overlay).to_be_hidden()

    # Desktop ≥1024px — прежний вид r4 (не fullscreen).
    page.set_viewport_size({"width": 1280, "height": 800})
    page.get_by_role("article").filter(has_text="QAP14B-modal").first.click()
    expect(overlay).to_be_visible()
    w = page.evaluate(
        "document.querySelector('#task-detail-overlay .task-view')"
        ".getBoundingClientRect().width")
    assert w < 1280, w


# ---------------------------------------------------------------------------
# TC-P14-105 — Форма задачи на мобильном
# ---------------------------------------------------------------------------
def test_tc_p14_105_task_form_mobile(mobile_page, web_owner_session,
                                     web_base_url):
    """TC-P14-105: форма создания на 390px — одна колонка, без горизонтальной
    прокрутки; поля ≥16px (NFR-24); интерактивные элементы — тач-таргеты
    ≥44px (NFR-23); Esc: чистая форма закрывается сразу, грязная — с
    подтверждением (FR-61): отмена держит введенное, подтверждение закрывает
    без сохранения; на desktop — вид V3 без мобильных включений."""
    page = mobile_page
    page.set_default_timeout(8000)
    page.get_by_role("button", name="Создать задачу").click()
    print("105: форма открыта", flush=True)
    sheet = page.locator("#task-form-overlay .task-form-sheet")
    expect(sheet).to_be_visible()
    m = page.evaluate(
        """() => { const el = document.querySelector(
                 '#task-form-overlay .task-form-sheet');
             const inputs = [...el.querySelectorAll(
               'input:not([type=checkbox]):not([type=file]):not([type=hidden]),'
               + ' textarea, select')]
               .filter(i => i.offsetHeight > 0);
             return {sw: el.scrollWidth, cw: el.clientWidth,
                     fontSizes: inputs.map(i =>
                       parseFloat(getComputedStyle(i).fontSize)),
                     heights: inputs.map(i =>
                       i.getBoundingClientRect().height),
                     btnH: el.querySelector('#task-form-submit')
                       .getBoundingClientRect().height,
                     closeH: el.querySelector('#task-form-close')
                       .getBoundingClientRect().height}; }"""
    )
    assert m["sw"] <= m["cw"] + 1, m  # без горизонтальной прокрутки
    assert all(fs >= 16 for fs in m["fontSizes"]), m  # NFR-24
    assert m["btnH"] >= 44 and m["closeH"] >= 44, m
    assert all(h >= 40 for h in m["heights"]), m  # тач-таргеты полей

    # Esc: чистая закрывается сразу.
    page.keyboard.press("Escape")
    expect(page.locator("#task-form-overlay")).to_be_hidden()

    # Esc: грязная — подтверждение «Закрыть без сохранения?» (FR-61);
    # диалог через page.on-хендлер (expect_event("dialog") в связке с
    # confirm() здесь вечно виснет — sync-API гонка авто-дисмисса).
    dialogs: list[str] = []

    def _cancel_dialog(dialog):
        dialogs.append(dialog.message)
        dialog.dismiss()  # отмена — форма остается с введенным

    page.on("dialog", _cancel_dialog)
    page.get_by_role("button", name="Создать задачу").click()
    page.get_by_label("Название").fill("QAP14B-esc-dirty")
    page.keyboard.press("Escape")
    expect(page.locator("#task-form-overlay")).to_be_visible()
    assert dialogs and "Закрыть без сохранения" in dialogs[0], dialogs
    assert page.get_by_label("Название").input_value() == "QAP14B-esc-dirty"

    # Подтверждение — закрыто без сохранения, данных на сервере нет.
    page.remove_listener("dialog", _cancel_dialog)
    page.on("dialog", lambda d: d.accept())
    page.keyboard.press("Escape")
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    board = web_owner_session.get(f"{web_base_url}/api/board").json()
    titles = [t["title"] for tasks in board["columns"].values()
              for t in tasks]
    assert "QAP14B-esc-dirty" not in titles, titles

    # Desktop ≥1024px — форма не наследует мобильную одноколоночность
    # (ширина формы меньше вьюпорта = desktop-модалка по токенам V3).
    page.set_viewport_size({"width": 1280, "height": 800})
    page.get_by_role("button", name="Создать задачу").click()
    expect(sheet).to_be_visible()
    w = sheet.evaluate("el => el.getBoundingClientRect().width")
    assert w < 1280, w
    page.locator("#task-form-close").click()


# ---------------------------------------------------------------------------
# TC-P14-106 — Поиск на мобильном (Should)
# ---------------------------------------------------------------------------
def test_tc_p14_106_mobile_search(mobile_page, web_owner_session,
                                  web_base_url, web_cleanup_created):
    """TC-P14-106: поиск на 390px — конструктор, advanced и выдача вертикально
    полной шириной, без X-скролла страницы; строки выдачи читаются без
    обрезки; инпуты 16px, кнопки ≥44px; функции (фильтр, advanced) дают
    результаты как на desktop."""
    page = mobile_page
    r = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAP14S-находка", "priority": "high"},
    )
    assert r.status_code == 201, r.text
    web_cleanup_created(r.json()["id"])
    page.goto(f"{web_base_url}/search")
    assert _page_overflow(page) <= 0, "X-скролл страницы поиска"

    # Фильтр по приоритету (поля полной ширины, тач-таргеты).
    prio = page.locator("#search-priority")
    pw = prio.evaluate("el => el.getBoundingClientRect().width")
    assert pw == pytest.approx(343, abs=16), pw  # 375/390 − 2×16
    fs = prio.evaluate("el => parseFloat(getComputedStyle(el).fontSize)")
    assert fs >= 16, fs
    submit = page.locator("#search-builder-submit")
    sb = submit.bounding_box()
    assert sb["height"] >= 44, sb
    prio.select_option("high")
    submit.click()
    results = page.locator("#search-results article, #search-results .result")
    expect(results.filter(has_text="QAP14S-находка").first).to_be_visible()
    clipped = page.evaluate(
        """() => [...document.querySelectorAll('#search-results *')]
             .filter(el => el.scrollWidth > el.clientWidth + 2 &&
                getComputedStyle(el).overflow !== 'visible').length"""
    )
    assert clipped == 0, clipped

    # Advanced-режим — функции не деградировали.
    page.locator("#search-mode-advanced").click()
    page.locator("#search-advanced-query").fill('priority = "high"')
    page.locator("#search-advanced-submit").click()
    expect(page.locator("#search-results").get_by_text(
        "QAP14S-находка").first).to_be_visible()


# ---------------------------------------------------------------------------
# TC-P14-107 — Настройки и профиль на мобильном (Should)
# ---------------------------------------------------------------------------
def test_tc_p14_107_mobile_settings_profile(mobile_page, web_owner_session,
                                            web_base_url):
    """TC-P14-107: настройки и профиль на 390px — одна колонка полной
    ширины, без X-скролла; инпуты ≥16px, кнопки ≥44px; операции справочника
    (создать/удалить категорию) и профиля (display_name, FR-56) работают;
    кроп-виджет открывается на таче (маска с touch-action; живые жесты —
    план 5.2 и сьют test_r5_crop_ui)."""
    page = mobile_page
    page.on("dialog", lambda d: d.accept())  # подтверждения удаления категорий
    page.goto(f"{web_base_url}/settings")
    assert _page_overflow(page) <= 0
    name_input = page.locator("#category-new-name")
    nw = name_input.evaluate("el => el.getBoundingClientRect().width")
    assert nw == pytest.approx(358, abs=24), nw  # полная ширина колонки
    fs = name_input.evaluate("el => parseFloat(getComputedStyle(el).fontSize)")
    assert fs >= 16, fs

    # Операция справочника: создать и удалить категорию.
    name_input.fill("QAP14-кат")
    page.locator("#category-create-submit").click()
    item = page.locator("#category-list li").filter(has_text="QAP14-кат")
    expect(item).to_be_visible()
    item.locator(".category-delete").click()  # удаление категории
    expect(item).to_have_count(0)

    # Профиль: одна колонка, display_name сохраняется (FR-56).
    page.goto(f"{web_base_url}/settings/profile")
    assert _page_overflow(page) <= 0
    display = page.locator("#profile-display-name")
    fs = display.evaluate("el => parseFloat(getComputedStyle(el).fontSize)")
    assert fs >= 16, fs
    display.fill("QAP14 Дисплей-нейм")
    save = page.locator("#profile-save")
    assert save.bounding_box()["height"] >= 44
    save.click()
    expect(page.locator("#profile-success")).to_be_visible()
    page.reload()
    expect(page.locator("#profile-display-name")).to_have_value(
        "QAP14 Дисплей-нейм")

    # Кроп-виджет открывается на тач-контексте: маска с touch-action.
    page.locator("#avatar-file").set_input_files(files=[{
        "name": "qap14-avatar.png", "mimeType": "image/png",
        "buffer": _png_bytes(600, 400),
    }])
    widget = page.locator("#crop-widget")
    expect(widget).to_have_class(re.compile("is-open"))
    ta = page.locator("#crop-mask").evaluate(
        "el => getComputedStyle(el).touchAction")
    assert ta in ("none", "pinch-zoom"), ta


# ---------------------------------------------------------------------------
# TC-P14-108 — Лайтбокс на таче (Should)
# ---------------------------------------------------------------------------
def test_tc_p14_108_mobile_lightbox_swipe(mobile_page, gallery_on_autostand,
                                          images_service, web_base_url):
    """TC-P14-108: свайп по ИЗОБРАЖЕНИЮ (≥50px, |dx|>|dy|) листает лайтбокс
    циклично; короткое/диагональное движение — тап (листания нет); скролл
    панели комментариев не перехватывается жестом; на desktop стрелки и
    клавиатура работают как прежде (NFR-29)."""
    page = mobile_page
    session = gallery_on_autostand
    # Загрузки — напрямую в images-сервис (автостенд галерею не монтирует;
    # web_base_url дал бы 404 Not Found). Сессия залогинена в прокси.
    _upload_three_with_comment(session, images_service["base_url"], "QAP14L-")

    page.goto(f"{web_base_url}/gallery")
    card = page.locator(".g-card", has_text="QAP14L-sw0.png").first
    card.scroll_into_view_if_needed()
    card.click()
    overlay = page.locator("#lightbox-overlay")
    expect(overlay).to_be_visible()
    expect(page.locator("#lb-counter-pos")).to_have_text("3 / 3")

    def _swipe(dx, dy, steps=6):
        box = page.locator("#lb-image").bounding_box()
        sx, sy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.evaluate(
            """([sx, sy, dx, dy, steps]) => {
              const target = document.elementFromPoint(sx, sy);
              const touch = (x, y) => new Touch({identifier: 1, target,
                clientX: x, clientY: y, pageX: x, pageY: y});
              const start = touch(sx, sy);
              target.dispatchEvent(new TouchEvent('touchstart', {bubbles: true,
                cancelable: true, touches: [start],
                targetTouches: [start], changedTouches: [start]}));
              for (let i = 1; i <= steps; i++) {
                const t = touch(sx + dx * i / steps, sy + dy * i / steps);
                target.dispatchEvent(new TouchEvent('touchmove', {bubbles: true,
                  cancelable: true, touches: [t], targetTouches: [t],
                  changedTouches: [t]}));
              }
              const end = touch(sx + dx, sy + dy);
              target.dispatchEvent(new TouchEvent('touchend', {bubbles: true,
                cancelable: true, touches: [], targetTouches: [],
                changedTouches: [end]}));
            }""",
            [sx, sy, dx, dy, steps],
        )

    def _pos():
        return page.locator("#lb-counter-pos").inner_text()

    # Свайп влево — следующее (3/3 → цикл на 1/3).
    _swipe(-120, 10)
    expect(page.locator("#lb-counter-pos")).to_have_text("1 / 3")
    expect(page.locator("#lb-title")).to_contain_text("QAP14L-sw2")
    # Свайп вправо — предыдущее (1/3 → 3/3).
    _swipe(120, 10)
    expect(page.locator("#lb-counter-pos")).to_have_text("3 / 3")

    # Короткое (до порога) и диагональное движение — тап, листания нет.
    _swipe(-30, 5)
    expect(page.locator("#lb-counter-pos")).to_have_text("3 / 3")
    _swipe(60, 120)
    expect(page.locator("#lb-counter-pos")).to_have_text("3 / 3")
    assert _pos() == "3 / 3"
    # Комментарии открытого изображения догружены (панель переполнена).
    expect(page.locator("#lb-comments-count")).to_have_text("(9)")

    # Скролл комментариев независим: панель скроллится, листания нет.
    scroll_state = page.evaluate(
        """() => { const img = document.getElementById('lb-image');
             // Целевой скроллер — именно .lb-comments (панель комментариев);
             // перечисление через запятую вернуло бы ПРЕДКА .lb-panel
             // (он раньше в document order и не скроллится).
             const panel = document.querySelector(
               '#lightbox-overlay .lb-comments') || img.parentElement;
             panel.scrollTop = 40;
             return {scrolled: panel.scrollTop, pos:
               document.getElementById('lb-counter-pos').textContent}; }"""
    )
    page.wait_for_timeout(200)
    assert scroll_state["scrolled"] > 0, scroll_state
    assert _pos() == "3 / 3"

    # Desktop ≥1024px: клавиатура листает как прежде (NFR-29).
    page.set_viewport_size({"width": 1280, "height": 800})
    page.keyboard.press("ArrowRight")
    expect(page.locator("#lb-counter-pos")).to_have_text("1 / 3")
    page.keyboard.press("Escape")
    expect(overlay).to_be_hidden()


# ---------------------------------------------------------------------------
# TC-P14-109 — Сквозные НФТ адаптива
# ---------------------------------------------------------------------------
def test_tc_p14_109_responsive_nfr(mobile_page, page, browser, web_base_url):
    """TC-P14-109: без X-скролла страницы на 390/480px во всех разделах
    (горизонталь доски — только в санкционированном контейнере колонок, ОВ-3);
    768px «не разваливается»; медиавыражения P14-файлов только 480/768px
    (860px — pre-existing redesign-console); в base.html viewport-fit=cover
    и нет user-scalable=no/maximum-scale (NFR-25/28); свайпы/drawer —
    нативные touch-события без внешних gesture-библиотек (ОГР-8)."""
    page_mobile = mobile_page
    for width, height in ((390, 844), (480, 800)):
        page_mobile.set_viewport_size({"width": width, "height": height})
        for section in SECTIONS:
            page_mobile.goto(f"{web_base_url}/{section}")
            overflow = _page_overflow(page_mobile)
            assert overflow <= 0, (width, section, overflow)

    # 768px (Z Fold 7 раскрытый): макет не разваливается — контент по
    # ширине вьюпорта, действия доступны (санкция доски — в контейнере).
    page_mobile.set_viewport_size({"width": 768, "height": 1024})
    for section in SECTIONS:
        page_mobile.goto(f"{web_base_url}/{section}")
        assert _page_overflow(page_mobile) <= 0, section
        body = page_mobile.locator("main")
        expect(body).to_be_visible()

    # Инспекция CSS: брейкпоинты каркасных css ⊆ утвержденных значений —
    # 480/768 (P14, NFR-27) + 860 (redesign-console, каркас) + 880/1280
    # (masonry-брейкпоинты галереи FR-98, ui-polish-r8). Новых одноразовых
    # «магических» ширин пакет P14 не вводит.
    allowed = {"480", "768", "860", "880", "1280"}
    for css in ("board.css", "gallery.css", "search.css", "settings.css",
                "app.css"):
        text = (REPO / "frontend/static/css" / css).read_text()
        widths = set(re.findall(r"@media[^({]*\(max-width:\s*(\d+)px", text))
        widths |= set(re.findall(r"@media[^({]*\(min-width:\s*(\d+)px", text))
        extra = widths - allowed
        assert not extra, (css, extra)

    # base.html: safe-area (viewport-fit=cover), нативный pinch (NFR-25/28).
    base_html = (REPO / "frontend/templates/base.html").read_text()
    viewport = re.search(r'<meta name="viewport" content="([^"]+)"', base_html)
    assert viewport, "meta viewport не найден"
    assert "viewport-fit=cover" in viewport.group(1), viewport.group(1)
    assert "user-scalable=no" not in viewport.group(1)
    assert "maximum-scale" not in viewport.group(1)

    # ОГР-8: жесты — ванильные touch/pointer-события, без внешних библиотек.
    # Диспозиция редизайна (факт в docstring TC-P14-101): drawer-свайп кейса
    # не воспроизводится — сайдбар ≤860px видимая строка (toggle-семантика),
    # жестовые обработчики живут в gallery.js (свайп лайтбокса) и
    # avatar-crop.js (жест кропа) — инспекция по фактическому коду.
    for js in (REPO / "frontend/static/js/board").glob("*.js"):
        src = js.read_text()
        assert "cdn." not in src and "unpkg" not in src, js.name
    has_native = False
    for name in ("app.js", "gallery.js", "avatar-crop.js"):
        src = (REPO / "frontend/static/js" / name).read_text()
        assert "cdn." not in src and "unpkg" not in src, name
        has_native = (
            has_native or "touchstart" in src or "pointerdown" in src
        )
    assert has_native, "нативных touch/pointer-жестов не найдено"

    # Desktop ≥1024px: разделы живы (NFR-29, без деградации каркаса).
    desktop = browser.new_context(viewport={"width": 1280, "height": 800})
    dpage = desktop.new_page()
    try:
        dpage.goto(f"{web_base_url}/login")
        dpage.get_by_label("Логин").fill("owner")
        dpage.get_by_label("Пароль").fill(PASSWORD)
        dpage.get_by_role("button", name="Войти").click()
        for section in ("board", "search", "wiki", "gallery", "settings"):
            dpage.goto(f"{web_base_url}/{section}")
            expect(dpage.locator("main")).to_be_visible()
            # Бургер отсутствует на desktop (NFR-29).
            assert dpage.locator("#burger-button").is_hidden()
    finally:
        desktop.close()


# ---------------------------------------------------------------------------
# TC-P14-110 — Живая приемка Заказчика на проде (ручной)
# ---------------------------------------------------------------------------
@pytest.mark.manual
def test_tc_p14_110_customer_live_acceptance():
    """TC-P14-110: живая приемка Заказчика на ПРОДЕ с телефона (iPhone 11 и
    Z Fold 7): сценарии С1–С3 (доска/свайп/быстрое «Выполнено», поиск одной
    рукой, свайп лайтбокса), протокол приемки, откат по тегу матрицы.
    НЕВОСПРОИЗВОДИМО АВТОМАТОМ: эксплуатационный кейс — физические устройства
    Заказчика, прод-контур с кеш-бастингом и подписанный протокол; кейс
    утвержден КАК план приемки 5.2 (статус в файле кейса: «сам прогон 5.2 —
    с Заказчиком, вне QA-хвоста 5.1»). Автоматизированное покрытие сценариев
    С1–С3 — TC-P14-103/106/108 этого файла."""
    pytest.skip(
        "ручной эксплуатационный кейс: живая приемка Заказчиком на проде "
        "(план 5.2); сценарии С1–С3 автоматизированы в TC-P14-103/106/108"
    )
