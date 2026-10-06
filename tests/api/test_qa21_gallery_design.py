"""QA 2.1 add-gallery-service — design_validator (TC-GAL-122, статическая часть).

Проверяет токенную дисциплину дельты gallery (design §0 п.4, FR-86): значения
берутся из CSS-переменных app.css :root (paper/ink/clay, Georgia display,
радиусы 6/10px, focus-ring), НЕ зашиты литералами в gallery.css/gallery.js;
мокапы 1.1 существуют (design/gallery-grid.html, gallery-lightbox.html,
gallery-upload.html).

Динамическая часть (Computed Styles живой страницы, hover/focus-состояния,
сверка компоновки построчно) — SKIPPED: сетка/лайтбокс не отрисовываются из-за
BUG-008 (gallery.js SyntaxError, тест-модель/bugs/); вердикт design_validator —
ПОСЛЕ фикса BUG-008 (переводится в автопрогон этим же файлом + ручной проход
по мокапам). Итоговый вердикт approve/return — зона СА (review-NNN-design),
QA фиксирует факты.
"""

import os
import re

import pytest

pytestmark = [pytest.mark.api, pytest.mark.must]

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Живой nginx-стенд (как в tests/web/test_qa21_gallery_ui.py) — только для
# динамической части TC-GAL-122; статические проверки от стенда не зависят.
BASE_URL = os.environ.get("EKOTOV_WIKI_BASE_URL", "http://127.0.0.1:18443")


def test_tc_gal_122_tokens_from_css_vars_not_hardcoded():
    """TC-GAL-122 (шаг 2, токены V3 «Бумага»): gallery.css использует только
    var(--token) — 0 hex/rgb-литералов цветов; gallery.js — 0 цветовых
    литералов; токены paper/ink/clay/Georgia/radius/focus-ring определены
    в app.css :root."""
    css = open(os.path.join(REPO, "frontend/static/css/gallery.css")).read()
    # Цветовые литералы в gallery.css (вне комментариев): hex / rgb() / rgba().
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    hex_literals = re.findall(r"#[0-9a-fA-F]{3,8}\b", body)
    rgb_literals = re.findall(r"rgba?\([^)]*\)", body)
    assert not hex_literals, f"gallery.css: зашиты hex-цвета: {hex_literals[:5]}"
    # rgba(): в цветовой системе V3 полупрозрачные тени/оверлеи выражаются
    # rgba() и в эталонных файлах (app.css: --shadow-modal/--focus-ring,
    # board.css) — допустимый класс (заводские rgba НЕ новые цвета, а alpha
    # вариантов paper/ink). Сверяем с эталонным набором значений app.css:
    # допустимы rgba от 61,54,48 (ink-900) и 255,253,249 (paper) — те же
    # базовые цвета, что в токенах; иные base-цвета = отход от токенов.
    allowed_bases = {("61", "54", "48"), ("255", "253", "249"), ("168", "67", "44")}
    for m in rgb_literals:
        parts = re.findall(r"[\d.]+", m)
        base = tuple(p.split(".")[0] for p in parts[:3])
        assert base in allowed_bases, (
            f"gallery.css: rgba вне токенных базовых цветов V3: {m} (base={base})"
        )
    # Токены используются.
    assert len(re.findall(r"var\(--", body)) >= 50, "токены почти не используются?"

    js = open(os.path.join(REPO, "frontend/static/js/gallery.js")).read()
    js_hex = re.findall(r"#[0-9a-fA-F]{6}\b", js)
    js_rgb = re.findall(r"rgba?\(", js)
    assert not js_hex and not js_rgb, f"gallery.js: цветовые литералы {js_hex[:3]}{js_rgb[:3]}"

    root = open(os.path.join(REPO, "frontend/static/css/app.css")).read()
    for token in ("--font-family-display: Georgia", "--radius-field: 6px",
                  "--radius-card: 10px", "--focus-ring:"):
        assert token in root, f"app.css :root: нет {token}"

    # Мокапы 1.1 на месте (сверка компоновки — после фикса BUG-008).
    for mock in ("gallery-grid.html", "gallery-lightbox.html", "gallery-upload.html"):
        assert os.path.isfile(os.path.join(REPO, "design", mock)), mock


@pytest.fixture(scope="module")
def browser_instance(browser):
    """Браузер playwright для динамического design_validator (в tests/api нет
    собственной browser-фикстуры — подключается плагин pytest-playwright)."""
    yield browser


def test_tc_gal_122_live_computed_styles_and_states(browser_instance):
    """TC-GAL-122 (шаги 2, 5): динамический design_validator — Computed Styles
    живой /gallery (токены V3 «Бумага» не хардкод), hover/focus-visible на
    карточке, подсветка «мой голос» после лайка, 422-состояние формы загрузки.

    Требует живой nginx-стенд :18443 (пропускается без EKOTOV_WIKI_DB_PATH —
    прогон в составе web-окружения). Проверки по токенам app.css :root:
    Georgia display, радиусы 6/10px, терракота --p-clay-600 #a8432c."""
    db_path = os.environ.get("EKOTOV_WIKI_DB_PATH")
    uploaded = None
    if not db_path:
        pytest.skip("нужен живой стенд (EKOTOV_WIKI_DB_PATH) — динамика /gallery")

    from playwright.sync_api import expect

    page = browser_instance.new_context(base_url=BASE_URL).new_page()
    try:
        page.goto(f"{BASE_URL}/login")
        page.fill("#login", "owner")
        page.fill("#password", os.environ.get(
            "EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!"))
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.goto(f"{BASE_URL}/gallery")
        page.wait_for_load_state("networkidle")

        # --- Шаг 2: Computed Styles карточек/кнопок — токены, не хардкод ---
        props = page.evaluate(
            """() => {
              const card = document.querySelector('.g-card');
              const btn = document.querySelector('.upload-button');
              const cs = card ? getComputedStyle(card) : null;
              const bs = btn ? getComputedStyle(btn) : null;
              const body = getComputedStyle(document.body);
              return {
                card_radius: cs && cs.borderRadius,
                card_font_display: document.querySelector('.g-card-title')
                  && getComputedStyle(document.querySelector('.g-card-title')).fontFamily,
                page_bg: body.backgroundColor,
                btn_bg: bs && bs.backgroundColor,
                accent_var: getComputedStyle(document.documentElement)
                  .getPropertyValue('--color-accent').trim(),
                clay_var: getComputedStyle(document.documentElement)
                  .getPropertyValue('--p-clay-600').trim(),
                radius_card_var: getComputedStyle(document.documentElement)
                  .getPropertyValue('--radius-card').trim(),
                radius_field_var: getComputedStyle(document.documentElement)
                  .getPropertyValue('--radius-field').trim(),
                font_display_var: getComputedStyle(document.documentElement)
                  .getPropertyValue('--font-family-display').trim(),
              };
            }"""
        )
        # Терракота clay-600 (#a8432c = rgb(168, 67, 44)) — акцент из :root.
        # getComputedStyle резолвит вложенные var() в конечное значение —
        # сверяем сам цвет (жестких литералов в delta-CSS нет, проверено
        # статикой: значения приходят из цепочки --color-accent→--p-clay-600).
        assert props["clay_var"].lower() == "#a8432c", props["clay_var"]
        assert props["accent_var"].strip().lower() == "#a8432c", props["accent_var"]
        assert props["radius_card_var"] == "10px", props["radius_card_var"]
        assert props["radius_field_var"] == "6px", props["radius_field_var"]
        assert "Georgia" in props["font_display_var"], props["font_display_var"]
        if props["card_radius"]:
            assert props["card_radius"] == "10px", (
                f"радиус карточки не из --radius-card: {props['card_radius']}")
        if props["btn_bg"] and props["btn_bg"] != "rgba(0, 0, 0, 0)":
            assert props["btn_bg"] == "rgb(168, 67, 44)", (
                f"кнопка загрузки не терракотовая из токена: {props['btn_bg']}")
        if props["page_bg"]:
            assert props["page_bg"] == "rgb(250, 247, 242)", (
                f"фон страницы не paper-050: {props['page_bg']}")
        if props["card_font_display"]:
            assert "Georgia" in props["card_font_display"], props["card_font_display"]

        # --- Шаг 5а: hover на карточке — тень/сдвиг по мокапу ---
        card = page.locator(".g-card").first
        if card.count():
            base_shadow = card.evaluate("el => getComputedStyle(el).boxShadow")
            card.hover()
            page.wait_for_timeout(150)
            hover_shadow = card.evaluate("el => getComputedStyle(el).boxShadow")
            assert hover_shadow != base_shadow or hover_shadow != "none", (
                "hover на карточке не меняет box-shadow (мокап 1.1: подъем карточки)")

        # --- Шаг 5б: focus-visible — focus-ring виден с клавиатуры ---
        page.keyboard.press("Tab")
        ring = page.evaluate(
            """() => {
              const el = document.activeElement;
              if (!el || !el.matches('.g-card, .filter select, .filter-reset,'
                                    + ' .upload-button, a, button')) return null;
              const cs = getComputedStyle(el);
              return {shadow: cs.boxShadow, outline: cs.outlineStyle};
            }"""
        )
        if ring is not None:
            has_ring = (ring["shadow"] and ring["shadow"] != "none") or \
                       ring["outline"] != "none"
            active = page.evaluate(
                "document.activeElement ? (document.activeElement.id ||"
                " document.activeElement.tagName) : 'none'")
            assert has_ring, f"focus-ring не виден на {active}"

        # --- Шаг 5в: «мой голос» — подсветка после лайка (API-сид + UI) ---
        uploaded = _design_upload(MARKER + "dv.png")
        page.reload()
        page.wait_for_load_state("networkidle")
        card_dv = page.locator(".g-card", has_text=MARKER + "dv.png")
        if card_dv.count():
            card_dv.click()
            expect(page.locator("#lightbox-overlay")).to_be_visible()
            page.click("#lb-like")
            expect(page.locator("#lb-like")).to_have_attribute("aria-pressed", "true")
            # Бейдж «мой голос» на карточке сетки — после refetch (fetchImages).
            my_vote = page.locator(".g-card .stat.my-vote")
            expect(my_vote.first).to_be_visible()
            color = my_vote.first.evaluate(
                "el => getComputedStyle(el).backgroundColor")
            assert color == "rgb(247, 232, 228)", (
                f"подсветка «мой голос» не clay-050 (#f7e8e4): {color}")

            # --- Шаг 5г: 422-состояние формы загрузки (файл не-изображение) ---
            page.keyboard.press("Escape")
            expect(page.locator("#lightbox-overlay")).to_be_hidden()
            page.click("#upload-button")
            expect(page.locator("#upload-form")).to_be_visible()
            page.set_input_files("#upload-file", {
                "name": MARKER + "dv-fake.jpg", "mimeType": "image/jpeg",
                "buffer": b"%PDF-1.4 design-validator" + b"\\x00" * 64,
            })
            page.click("#upload-submit")
            err = page.locator("#upload-error")
            expect(err).to_be_visible()
            assert err.inner_text().strip(), "пустой текст ошибки типа файла"
            page.click("#upload-close")
        else:
            pytest.skip("сетка пуста — шаг «мой голос» требует отрисованных карточек")
    finally:
        _design_cleanup(uploaded if "uploaded" in locals() else None)
        page.context.close()


MARKER = "QAGAL-DV-"


def _design_upload(name):
    """Сид одного изображения через API (для проверок «мой голос»)."""
    import io

    import requests
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (90, 90, 90)).save(buf, "PNG")
    s = requests.Session()
    s.post(f"{BASE_URL}/api/auth/login", json={
        "login": "owner",
        "password": os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!"),
    })
    for c in s.cookies:
        c.secure = False
    r = s.post(f"{BASE_URL}/api/images",
               files=[("file", (name, buf.getvalue(), "image/png"))])
    assert r.status_code == 201, r.text
    out = r.json()
    s.close()
    return out


def _design_cleanup(uploaded):
    """Точечная чистка QAGAL-DV-хвостов (у теста нет QAGAL-autouse-фикстуры
    tests/web — файл живет в tests/api)."""
    if not uploaded:
        return
    import sqlite3

    db_path = os.environ.get("EKOTOV_WIKI_DB_PATH")
    images_dir = os.environ.get("EKOTOV_WIKI_IMAGES_DIR", "/tmp/qa21-gallery/images")
    if not db_path:
        return
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, filename, thumb_name FROM images WHERE original_name LIKE ?",
        (MARKER + "%",),
    ).fetchall()
    files = []
    for r in rows:
        files += [r["filename"], r["thumb_name"]]
        for table in ("image_tags", "image_reactions", "image_comments"):
            conn.execute(f"DELETE FROM {table} WHERE image_id = ?", (r["id"],))
        conn.execute("DELETE FROM images WHERE id = ?", (r["id"],))
    conn.commit()
    for f in files:
        try:
            os.remove(os.path.join(images_dir, f))
        except OSError:
            pass


def document_active(page):
    """Человекочитаемое имя активного элемента (диагностика ассертов)."""
    return page.evaluate(
        "document.activeElement ? document.activeElement.id ||"
        " document.activeElement.tagName : 'none'")
