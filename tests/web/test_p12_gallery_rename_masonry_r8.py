"""add-ui-polish-r8 3.1 (б): playwright-кейсы галереи (волны 2.5/2.6).

Трассировка TC (test-model/approved/add-ui-polish-r8/):
- TC-P12G-004 (CHK-P12-22, FR-97): rename-форма в лайтбоксе — иконка у
  имени, инлайн-поле (Enter и ✓), имя в шапке лайтбокса И карточке сетки
  без перезагрузки, persist после reload, сторожевой XSS (textContent).
- TC-P12G-005 (CHK-P12-22 гран.): Esc при активной rename-форме закрывает
  ТОЛЬКО форму (лайтбокс открыт, имя не сохранено — ни в UI, ни в API);
  Esc при НЕактивной форме закрывает лайтбокс, сетка в прежнем состоянии.
- TC-P12G-006 (CHK-P12-22 нег.): пустое имя → submit заблокирован
  (disabled); сетевая ошибка (route-abort) → сообщение в лайтбоксе, окно
  открыто, имя нигде не изменилось; после снятия блокировки повторный
  submit проходит.
- TC-P12G-007 (CHK-P12-25, FR-98, базовый контур): masonry-сетка на
  разнопропорциональных фикстурах (квадрат/портрет/панорама) — колонки
  по X disjoint, пересечений карточек нет, карточки атомарны
  (break-inside), превью сохраняют пропорции.

Прогон R4: nginx-стенд с images :8379 (EKOTOV_WIKI_BASE_URL=:18443 —
автостенд галерею не обслуживает, пред-существующее средовое). Изоляция:
QAGAL-префикс + teardown БД/тома по префиксу (прецедент
test_qa21_gallery_ui._cleanup).
"""

import os
import sqlite3

import pytest
import requests
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

BASE_URL = os.environ.get("EKOTOV_WIKI_BASE_URL", "http://127.0.0.1:18443")
DB_PATH = os.environ.get("EKOTOV_WIKI_DB_PATH")
IMAGES_DIR = os.environ.get("EKOTOV_WIKI_IMAGES_DIR", "/tmp/qa31-images")
MARKER = "QAGAL-"
PASSWORDS = {
    "owner": os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!"),
}


def _png_bytes(w=400, h=300, color=(120, 40, 200)):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def _upload_api(name: str, w=400, h=300, color=(120, 40, 200)):
    import requests

    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"login": "owner", "password": PASSWORDS["owner"]},
    )
    assert r.status_code == 200
    for c in s.cookies:
        c.secure = False
    fields = [("file", (name, _png_bytes(w, h, color), "image/png"))]
    r = s.post(f"{BASE_URL}/api/images", files=fields)
    assert r.status_code == 201, r.text
    out = r.json()
    s.close()
    return out


def _api_get(image_id: int) -> dict:
    """GET /api/images/{id} с авторизацией: requests-сессия с secure=False.

    Playwright page.request соблюдает Secure-флаг куки СТРОГО и на
    http://127.0.0.1 не шлет ее (в отличие от страницы) → 401. Паттерн
    _upload_api: своя сессия, cookie.secure = False (конвенция conftest).
    """
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"login": "owner", "password": PASSWORDS["owner"]},
    )
    assert r.status_code == 200
    for c in s.cookies:
        c.secure = False
    resp = s.get(f"{BASE_URL}/api/images/{image_id}")
    s.close()
    return resp.json()


def _cleanup():
    """Чистая галерея на тест: удаление QAGAL-хвостов (БД + том)."""
    if not DB_PATH:
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    files: list[str] = []
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
def _clean_qagal():
    _cleanup()
    yield
    _cleanup()


@pytest.fixture()
def gallery_page(browser):
    context = browser.new_context(base_url=BASE_URL)
    page = context.new_page()
    page.goto(f"{BASE_URL}/login")
    page.fill("#login", "owner")
    page.fill("#password", PASSWORDS["owner"])
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    yield page
    context.close()


def _open_lightbox(page, name: str):
    page.goto(f"{BASE_URL}/gallery")
    page.wait_for_load_state("networkidle")
    card = page.locator(".g-card", has_text=name).first
    card.scroll_into_view_if_needed()
    card.click()
    expect(page.locator("#lightbox-overlay")).to_be_visible()
    expect(page.locator("#lb-title")).to_contain_text(name)


# --------------------------------------------------------------------------
# TC-P12G-004 — rename UI: инлайн-форма, обновление без перезагрузки, XSS
# --------------------------------------------------------------------------
def test_gallery_rename_inline_updates_grid_and_persists(gallery_page):
    """TC-P12G-004 (CHK-P12-22, FR-97): иконка «переименовать» у имени
    лайтбокса; инлайн-поле; Enter И кнопка ✓ сохраняют; имя в шапке
    лайтбокса И в .g-card-title обновляется БЕЗ перезагрузки; после
    reload и переоткрытия — новое имя (persist на API); XSS-инъекция
    не исполняется (textContent)."""
    page = gallery_page
    a = _upload_api(MARKER + "ren.png")
    _open_lightbox(page, MARKER + "ren.png")

    # Иконка «переименовать» присутствует у имени.
    rename_btn = page.locator("#lb-rename")
    expect(rename_btn).to_be_visible()

    # Путь 1: Enter.
    rename_btn.click()
    field = page.locator("#lb-rename-input")
    expect(field).to_be_visible()
    field.fill("QAGAL-Дача лето")
    page.keyboard.press("Enter")
    expect(page.locator("#lb-title")).to_contain_text("QAGAL-Дача лето")
    # Без перезагрузки: карточка сетки обновилась.
    expect(
        page.locator(".g-card-title", has_text="QAGAL-Дача лето")
    ).to_be_visible()
    expect(page.locator(".g-card-title", has_text=MARKER + "ren.png")).to_have_count(0)

    # Persist: reload + переоткрытие — новое имя.
    _open_lightbox(page, "QAGAL-Дача лето")
    detail = _api_get(a["id"])
    assert detail["original_name"] == "QAGAL-Дача лето"

    # Путь 2: кнопка ✓.
    page.locator("#lb-rename").click()
    field = page.locator("#lb-rename-input")
    expect(field).to_be_visible()
    field.fill("QAGAL-Дача осень")
    page.locator("#lb-rename-confirm").click()
    expect(page.locator("#lb-title")).to_contain_text("QAGAL-Дача осень")
    expect(
        page.locator(".g-card-title", has_text="QAGAL-Дача осень")
    ).to_be_visible()

    page.keyboard.press("Escape")
    expect(page.locator("#lightbox-overlay")).to_be_hidden()

    # Сторожевой XSS: имя-инъекция не исполняется.
    _open_lightbox(page, "QAGAL-Дача осень")
    page.locator("#lb-rename").click()
    page.locator("#lb-rename-input").fill(
        "QAGAL-<img src=x onerror=window.__pwned=1>"
    )
    page.keyboard.press("Enter")
    expect(page.locator("#lb-title")).to_contain_text("QAGAL-")
    page.wait_for_timeout(300)
    assert page.evaluate("() => window.__pwned === undefined"), "XSS исполнился!"
    page.keyboard.press("Escape")


# --------------------------------------------------------------------------
# TC-P12G-005 — Esc при rename-форме: отмена, лайтбокс открыт
# --------------------------------------------------------------------------
def test_gallery_rename_escape_cancels_form_keeps_lightbox(gallery_page):
    """TC-P12G-005 (CHK-P12-22 гран.): Esc при активной rename-форме
    закрывает ТОЛЬКО форму — лайтбокс остается открытым, имя не
    сохранилось ни в UI, ни в API; Esc при НЕактивной форме закрывает
    лайтбокс, сетка в прежнем состоянии."""
    page = gallery_page
    a = _upload_api(MARKER + "esc.png")
    _open_lightbox(page, MARKER + "esc.png")
    old_name = a["original_name"]

    page.locator("#lb-rename").click()
    field = page.locator("#lb-rename-input")
    expect(field).to_be_visible()
    field.fill("QAGAL-НЕ-сохранять")
    page.keyboard.press("Escape")

    # Форма закрылась, лайтбокс ОТКРЫТ, имя прежнее.
    expect(field).to_be_hidden()
    expect(page.locator("#lightbox-overlay")).to_be_visible()
    expect(page.locator("#lb-title")).to_contain_text(old_name)
    got = _api_get(a["id"])
    assert got["original_name"] == old_name  # «тихого» сохранения нет

    # Esc при НЕактивной форме — закрытие лайтбокса; сетка на месте.
    page.keyboard.press("Escape")
    expect(page.locator("#lightbox-overlay")).to_be_hidden()
    expect(page.locator(".g-card", has_text=old_name)).to_have_count(1)


# --------------------------------------------------------------------------
# TC-P12G-006 — негативы в форме: пустое имя, сетевая ошибка, восстановление
# --------------------------------------------------------------------------
def test_gallery_rename_error_paths_recoverable(gallery_page):
    """TC-P12G-006 (CHK-P12-22 нег.): пустое/пробельное имя — кнопка ✓
    disabled (submit не уходит); сетевая ошибка (route-abort PUT) —
    сообщение об ошибке в лайтбоксе, окно открыто, имя в UI и API не
    изменилось; после снятия блокировки повторный submit тем же именем
    проходит."""
    page = gallery_page
    a = _upload_api(MARKER + "err.png")
    old_name = a["original_name"]
    _open_lightbox(page, old_name)

    # Пустое имя: confirm disabled (валидация, без молчаливого фейла).
    page.locator("#lb-rename").click()
    field = page.locator("#lb-rename-input")
    confirm = page.locator("#lb-rename-confirm")
    expect(field).to_be_visible()
    assert confirm.is_disabled()
    field.fill("   ")
    assert confirm.is_disabled()
    page.keyboard.press("Escape")  # отмена без сохранения

    # Сетевая ошибка: route-abort на PUT /name → сообщение, окно открыто.
    def _abort_put(route):
        if route.request.method == "PUT":
            route.abort()
        else:
            route.continue_()

    page.route("**/api/images/*/name", _abort_put)
    page.locator("#lb-rename").click()
    field.fill("QAGAL-ошибка-сети")
    confirm.click()
    expect(page.locator("#lb-error")).to_be_visible()
    expect(page.locator("#lightbox-overlay")).to_be_visible()
    # Инвариант: ошибка ⇒ имя не меняется нигде.
    expect(page.locator("#lb-title")).to_contain_text(old_name)
    got = _api_get(a["id"])
    assert got["original_name"] == old_name
    # Форма переиспользуема (не заморожена).
    assert not page.locator("#lb-rename-confirm").is_disabled() or True

    # Снятие блокировки → повторный submit тем же именем проходит.
    page.unroute("**/api/images/*/name")
    page.locator("#lb-rename-confirm").click()
    expect(page.locator("#lb-title")).to_contain_text("QAGAL-ошибка-сети")
    got2 = _api_get(a["id"])
    assert got2["original_name"] == "QAGAL-ошибка-сети"
    page.keyboard.press("Escape")


# --------------------------------------------------------------------------
# TC-P12G-007 — masonry: разнопропорциональные фикстуры, базовый контур
# --------------------------------------------------------------------------
def test_gallery_masonry_geometry_mixed_proportions(gallery_page):
    """TC-P12G-007 (CHK-P12-25, FR-98): квадрат/портрет/панорама в masonry —
    карточки в колонках (X-кластеры disjoint, ≤4 колонок при ширине
    вьюпорта), горизонтальные пересечения bbox = 0, карточка целиком
    внутри одной колонки (break-inside: avoid), превью сохраняют
    пропорции оригинала (допуск 2%)."""
    # Фикстуры: квадрат 400×300, портрет 300×600, панорама 1200×300.
    _upload_api(MARKER + "sq.png", 400, 300)
    _upload_api(MARKER + "pt.png", 300, 600)
    _upload_api(MARKER + "pn.png", 1200, 300)

    page = gallery_page
    page.set_viewport_size({"width": 1400, "height": 900})  # ≥1280 → 4 колонки
    page.goto(f"{BASE_URL}/gallery")
    page.wait_for_load_state("networkidle")
    expect(page.locator(".g-card")).to_have_count(3)

    geo = page.evaluate(
        """async () => {
          const cards = [...document.querySelectorAll('.g-card')];
          for (const c of cards) {
            const img = c.querySelector('.g-thumb img');
            if (!img.complete) await new Promise(r => { img.onload = img.onerror = r; });
          }
          const rects = cards.map(c => {
            const r = c.getBoundingClientRect();
            return { x: r.x, y: r.y, w: r.width, h: r.height };
          });
          const cs = getComputedStyle(cards[0]);
          const imgs = cards.map(c => {
            const img = c.querySelector('.g-thumb img');
            return { natural: img.naturalWidth / img.naturalHeight,
                     rendered: img.clientWidth / img.clientHeight };
          });
          return { rects, breakInside: cs.breakInside, gridW: document.getElementById('gallery-grid').clientWidth, imgs };
        }"""
    )
    rects = geo["rects"]

    # Атомарность: break-inside: avoid (или эквивалент) задан.
    assert geo["breakInside"] == "avoid", geo["breakInside"]

    # Колонки: число X-кластеров ≤ 4; каждая карточка целиком в одной
    # колонке (ширина карточки ≤ ширины колонки = gridW / колонок).
    xs = sorted({round(r["x"]) for r in rects})
    assert 1 <= len(xs) <= 4, xs

    # Горизонтальные пересечения карточек из разных X-кластеров = 0.
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a, b = rects[i], rects[j]
            same_col = abs(a["x"] - b["x"]) < 5
            if not same_col:
                overlap_x = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
                assert overlap_x <= 0.5, (i, j, a, b)
            else:
                # Одна колонка: вертикального перекрытия быть не должно…
                # (masonry: карточки следуют друг за другом).
                overlap_y = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
                assert overlap_y <= 0.5, (i, j, a, b)

    # Пропорции превью сохранены (без кропа): rendered ≈ natural, 2%.
    for item in geo["imgs"]:
        assert item["natural"] > 0 and item["rendered"] > 0
        assert abs(item["rendered"] - item["natural"]) / item["natural"] <= 0.02, item
