"""add-responsive-mobile 4.1 — playwright-кейсы свайпов лайтбокса.

Трассировка (openspec/changes/add-responsive-mobile):
- specs/gallery/spec.md Scenario «Листание свайпом по изображению»
  (device-эмуляция 375×812, синтетический touch-свайп): сдвиг ≥50px,
  |dx| > |dy| — следующий/предыдущий циклично, паритет стрелкам (FR-105).
- Scenario «Короткое или диагональное движение — это тап»: движение
  <50px НЕ листает (существующее поведение тапа не меняется).
- Scenario «Скролл комментариев не перехватывается жестом листания»:
  touch-обработчики только на #lb-image — панель комментариев скроллится
  сама, ее жест не листает картинки.
- Scenario «Desktop-способы листания не деградировали» (NFR-29):
  стрелки-зоны и клавиатура ≥1024px работают как прежде.
- Дополнительно: нет прокрутки страницы по X на 375×812 (design §7),
  паритет свайпа и стрелок (та же цель navigateLightbox).

Прогон: процессный nginx-стенд :18443 (app :8080 + search :8378 +
images :8389; прецедент tests/REPORT-2.1-gallery-qa.md §1 — автостенд
conftest галерею не обслуживает). Изоляция: QAGAL-префикс + teardown
БД/тома по префиксу (паттерн test_p12_gallery_rename_masonry_r8).

Запуск (одной командой, ≤30 сек):
  pytest tests/web/test_p14_41_lightbox_swipe.py -q
"""

import io
import os
import sqlite3

import pytest
import requests
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

BASE_URL = os.environ.get("EKOTOV_WIKI_BASE_URL", "http://127.0.0.1:18443")
DB_PATH = os.environ.get("EKOTOV_WIKI_DB_PATH", "/tmp/qa2141/app.db")
IMAGES_DIR = os.environ.get("EKOTOV_WIKI_IMAGES_DIR", "/tmp/qa2141/images")
MARKER = "QAGAL41-"
PASSWORD = os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!")


def _png_bytes(w=375, h=250, color=(90, 60, 200)):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def _session():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"login": "owner", "password": PASSWORD},
    )
    assert r.status_code == 200
    for c in s.cookies:
        c.secure = False
    return s


def _upload_three():
    """Три изображения с различимым порядком. Важно: выдача — created_at
    DESC (последнее загруженное — 1-е в лайтбоксе), а timestamp хранится
    с микросекундами, но три подряд POST могут попасть в одну
    микросекунду — между загрузками пауза."""
    s = _session()
    import time
    for i in range(3):
        r = s.post(
            f"{BASE_URL}/api/images",
            files=[("file", (f"{MARKER}sw{i}.png", _png_bytes(color=(90 * (i + 1), 60, 200)), "image/png"))],
        )
        assert r.status_code == 201, r.text
        time.sleep(1.05)  # создан различимый created_at (DESC-выдача)
    s.close()


def _cleanup():
    """Чистая галерея на тест: удаление QAGAL41-хвостов (БД + том)."""
    if not DB_PATH or not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    files = []
    try:
        rows = conn.execute(
            "SELECT id, filename, thumb_name FROM images WHERE original_name LIKE ?",
            (MARKER + "%",),
        ).fetchall()
        if not rows:
            return
        ids = [r["id"] for r in rows]
        q = ",".join("?" * len(ids))
        for table in ("image_tags", "image_reactions", "image_comments"):
            conn.execute(f"DELETE FROM {table} WHERE image_id IN ({q})", ids)
        for r in rows:
            files += [r["filename"], r["thumb_name"]]
            conn.execute("DELETE FROM images WHERE id = ?", (r["id"],))
        conn.execute(
            "DELETE FROM image_tags WHERE tag_id IN"
            " (SELECT id FROM gallery_tags WHERE name LIKE ?)",
            (MARKER + "%",),
        )
        conn.execute("DELETE FROM gallery_tags WHERE name LIKE ?", (MARKER + "%",))
        conn.execute("DELETE FROM image_categories WHERE name LIKE ?", (MARKER + "%",))
        conn.commit()
    finally:
        conn.close()
    for f in files:
        try:
            os.remove(os.path.join(IMAGES_DIR, f))
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _clean_qagal41():
    _cleanup()
    _upload_three()  # фикстуры-данные: 3 изображения (sw0 → sw2 в выдаче)
    yield
    _cleanup()


def _mobile_page(browser):
    """375×812 (iPhone X-class), touch включен (has_touch) — свайпы работают."""
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
    return context, page


def _open_lightbox(page, name: str, pos: int, total: int = 3):
    """Открыть лайтбокс по карточке с именем name; pos — её позиция в
    выдаче (created_at DESC: последнее загруженное — 1-е)."""
    page.goto(f"{BASE_URL}/gallery")
    page.wait_for_load_state("networkidle")
    card = page.locator(".g-card", has_text=name).first
    card.scroll_into_view_if_needed()
    card.click()
    expect(page.locator("#lightbox-overlay")).to_be_visible()
    expect(page.locator("#lb-title")).to_contain_text(name)
    _expect_counter(page, pos, total)


def _swipe_on_image(page, dx: int, dy: int, steps: int = 6):
    """Синтетический touch-свайп по #lb-image (design §7, 5.1а)."""
    box = page.locator("#lb-image").bounding_box()
    assert box, "#lb-image должен иметь bounding box в открытом лайтбоксе"
    sx = box["x"] + box["width"] / 2
    sy = box["y"] + box["height"] / 2
    page.touchscreen.tap(sx, sy)  # калибровка тач-стека (безопасный тап)
    page.evaluate(
        """([sx, sy, dx, dy, steps]) => {
        const target = document.elementFromPoint(sx, sy);
        const opts = (x, y) => ({
          bubbles: true, cancelable: true, touches: undefined,
          changedTouches: [new Touch({
            identifier: 1, target,
            clientX: x, clientY: y, pageX: x, pageY: y,
          })],
        });
        const start = new Touch({
          identifier: 1, target,
          clientX: sx, clientY: sy, pageX: sx, pageY: sy,
        });
        target.dispatchEvent(new TouchEvent("touchstart", {
          bubbles: true, cancelable: true, touches: [start],
          targetTouches: [start], changedTouches: [start],
        }));
        for (let i = 1; i <= steps; i++) {
          const x = sx + (dx * i) / steps, y = sy + (dy * i) / steps;
          const t = new Touch({
            identifier: 1, target,
            clientX: x, clientY: y, pageX: x, pageY: y,
          });
          target.dispatchEvent(new TouchEvent("touchmove", {
            bubbles: true, cancelable: true, touches: [t],
            targetTouches: [t], changedTouches: [t],
          }));
        }
        const end = new Touch({
          identifier: 1, target,
          clientX: sx + dx, clientY: sy + dy,
          pageX: sx + dx, pageY: sy + dy,
        });
        target.dispatchEvent(new TouchEvent("touchend", {
          bubbles: true, cancelable: true, touches: [],
          targetTouches: [], changedTouches: [end],
        }));
      }""",
        [sx, sy, dx, dy, steps],
    )


def _expect_counter(page, pos: int, total: int = 3):
    expect(page.locator("#lb-counter-pos")).to_have_text(f"{pos} / {total}")


# --------------------------------------------------------------------------
# Scenario: Листание свайпом по изображению (375×812, ≥50px, |dx|>|dy|)
# --------------------------------------------------------------------------
def test_swipe_left_navigates_next_on_mobile(browser):
    """Выдача DESC: grid = [sw2, sw1, sw0] — sw0 открыт последним (3/3).
    Свайп влево — следующий: 3 → цикл на 1 (sw2) → 2 (sw1) → 3 (sw0)."""
    context, page = _mobile_page(browser)
    try:
        _open_lightbox(page, MARKER + "sw0.png", pos=3)
        _swipe_on_image(page, -120, 10)  # влево — следующее
        _expect_counter(page, 1)
        expect(page.locator("#lb-title")).to_contain_text(MARKER + "sw2")
        _swipe_on_image(page, -120, 10)
        _expect_counter(page, 2)
        expect(page.locator("#lb-title")).to_contain_text(MARKER + "sw1")
        # Цикличность: со второй позиции через третью — снова первая
        _swipe_on_image(page, -120, 10)
        _expect_counter(page, 3)
        _swipe_on_image(page, -120, 10)
        _expect_counter(page, 1)
        expect(page.locator("#lb-title")).to_contain_text(MARKER + "sw2")
    finally:
        context.close()


def test_swipe_right_navigates_prev_cyclically(browser):
    context, page = _mobile_page(browser)
    try:
        _open_lightbox(page, MARKER + "sw0.png", pos=3)
        _swipe_on_image(page, 120, 10)  # вправо — предыдущее (3 → 2)
        _expect_counter(page, 2)
        expect(page.locator("#lb-title")).to_contain_text(MARKER + "sw1")
        _swipe_on_image(page, 120, 10)  # 2 → 1
        _expect_counter(page, 1)
        expect(page.locator("#lb-title")).to_contain_text(MARKER + "sw2")
        # Цикличность: вправо с первой — на последнюю (3)
        _swipe_on_image(page, 120, 10)
        _expect_counter(page, 3)
        expect(page.locator("#lb-title")).to_contain_text(MARKER + "sw0")
    finally:
        context.close()


def test_swipe_parity_with_keyboard_arrows(browser):
    """Паритет: свайп и клавиатурная стрелка приводят к одному изображению."""
    context, page = _mobile_page(browser)
    try:
        _open_lightbox(page, MARKER + "sw1.png", pos=2)
        _swipe_on_image(page, -120, 10)  # свайп влево: 2 → 3 (sw0)
        _expect_counter(page, 3)
        expect(page.locator("#lb-title")).to_contain_text(MARKER + "sw0")
        page.keyboard.press("ArrowRight")  # стрелка: с 3-го — цикл на 1-е (sw2)
        _expect_counter(page, 1)
        page.keyboard.press("ArrowLeft")  # стрелка назад: снова 3-е (sw0)
        _expect_counter(page, 3)
        _swipe_on_image(page, 120, 10)  # свайп вправо: 3 → 2 (sw1)
        _expect_counter(page, 2)
        expect(page.locator("#lb-title")).to_contain_text(MARKER + "sw1")
    finally:
        context.close()


# --------------------------------------------------------------------------
# Scenario: Короткое или диагональное движение — это тап
# --------------------------------------------------------------------------
def test_short_and_diagonal_swipes_do_not_navigate(browser):
    context, page = _mobile_page(browser)
    try:
        _open_lightbox(page, MARKER + "sw0.png", pos=3)
        _swipe_on_image(page, -40, 0)  # короче порога (<50px)
        _expect_counter(page, 3)
        _swipe_on_image(page, -120, 150)  # диагональный: |dy| > |dx|
        _expect_counter(page, 3)
        _swipe_on_image(page, 120, 160)  # то же вправо
        _expect_counter(page, 3)
        expect(page.locator("#lightbox-overlay")).to_be_visible()
    finally:
        context.close()


# --------------------------------------------------------------------------
# Scenario: Скролл комментариев не перехватывается жестом листания
# --------------------------------------------------------------------------
def test_comments_panel_scroll_does_not_navigate(browser):
    context, page = _mobile_page(browser)
    try:
        _open_lightbox(page, MARKER + "sw0.png", pos=3)
        # Комментарий к текущему изображению (панель получит контент)
        s = _session()
        r = s.get(f"{BASE_URL}/api/images")
        img_id = r.json()["images"][0]["id"]
        r = s.post(f"{BASE_URL}/api/images/{img_id}/comments", json={"body": "коммент свайп-теста"})
        assert r.status_code == 201
        s.close()
        page.reload()
        page.wait_for_load_state("networkidle")
        page.locator(".g-card", has_text=MARKER + "sw0").first.click()
        expect(page.locator("#lightbox-overlay")).to_be_visible()
        _expect_counter(page, 3)
        # Вертикальный жест по ПАНЕЛИ (не по изображению) — не листает
        panel = page.locator("#lb-comments-list").bounding_box()
        assert panel, "#lb-comments-list должен быть видим"
        page.evaluate(
            """(box) => {
            const target = document.elementFromPoint(
              box.x + box.width / 2, box.y + Math.min(box.height / 2, 40)) ||
              document.getElementById("lb-comments-list");
            const mk = (x, y) => new Touch({
              identifier: 2, target,
              clientX: x, clientY: y, pageX: x, pageY: y,
            });
            const s = mk(box.x + box.width / 2, box.y + 30);
            target.dispatchEvent(new TouchEvent("touchstart", {
              bubbles: true, cancelable: true, touches: [s],
              targetTouches: [s], changedTouches: [s],
            }));
            const e = mk(box.x + box.width / 2, box.y + 130);
            target.dispatchEvent(new TouchEvent("touchend", {
              bubbles: true, cancelable: true, touches: [],
              targetTouches: [], changedTouches: [e],
            }));
          }""",
            panel,
        )
        _expect_counter(page, 3)  # жест панели не листает изображения
        expect(page.locator("#lightbox-overlay")).to_be_visible()
        # Панель комментариев скроллится сама (overflow-y: auto на .lb-comments)
        assert page.evaluate(
            "getComputedStyle(document.querySelector('.lb-comments')).overflowY"
        ) == "auto"
    finally:
        context.close()


# --------------------------------------------------------------------------
# Scenario: Desktop-способы листания не деградировали (NFR-29)
# --------------------------------------------------------------------------
def test_desktop_arrows_buttons_and_no_x_scroll(browser):
    context = browser.new_context(base_url=BASE_URL, viewport={"width": 1280, "height": 800})
    page = context.new_page()
    try:
        page.goto(f"{BASE_URL}/login")
        page.fill("#login", "owner")
        page.fill("#password", PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.goto(f"{BASE_URL}/gallery")
        page.wait_for_load_state("networkidle")
        # Desktop: touch-action на изображении НЕ переопределен (ветка ≤480px)
        assert page.evaluate(
            "getComputedStyle(document.getElementById('lb-image')).touchAction"
        ) != "none"
        page.locator(".g-card", has_text=MARKER + "sw0").first.click()
        expect(page.locator("#lightbox-overlay")).to_be_visible()
        _expect_counter(page, 3)
        page.locator("#lb-next").click()  # next: 3 → 1
        _expect_counter(page, 1)
        page.locator("#lb-next").click()  # next: 1 → 2
        _expect_counter(page, 2)
        page.keyboard.press("ArrowLeft")  # клавиатура: 2 → 1
        _expect_counter(page, 1)
        page.keyboard.press("ArrowRight")  # 1 → 2
        _expect_counter(page, 2)
        page.locator("#lb-prev").click()  # prev: 2 → 1
        _expect_counter(page, 1)
        # Нет прокрутки страницы по X (design §7)
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
    finally:
        context.close()


def test_mobile_no_page_x_scroll(browser):
    context, page = _mobile_page(browser)
    try:
        page.goto(f"{BASE_URL}/gallery")
        page.wait_for_load_state("networkidle")
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        page.locator(".g-card", has_text=MARKER + "sw0").first.click()
        expect(page.locator("#lightbox-overlay")).to_be_visible()
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
    finally:
        context.close()
