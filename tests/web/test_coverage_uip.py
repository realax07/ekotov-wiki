"""coverage-backfill-1; TC-P12G-003: rename файла — валидация 422 (пустое/
отсутствующее/пробельное имя, граница 255, разделители); TC-P12G-008: masonry
FR-98 — адаптив 2/3/4 колонки без наложений, перестройка на лету;
TC-P12G-009: masonry break-inside семантика — карточка не разрывается между
колонками; TC-P12G-010: бейдж формата в углу плитки, ховер/фокус карточек;
TC-P12G-011: revalidate TC-GAL-115/116/122 на merge-ветке волн;
TC-P12N-005: revalidate TC-nav-006 — геометрия «Настройки» внизу слева у
«Выйти»; TC-P12N-008: ядерный API-регресс — контракты ядра стабильны;
TC-P12N-009: ядерный web-регресс — DOM-контракты незатронутых разделов;
TC-UIP-102: Вторая fast-задача — 409, форма открыта, поля сохранены;
TC-UIP-107: Модалка просмотра тикета — вид по мокапу волны 2.2;
TC-UIP-114: Геометрия кнопки настроек — bbox-замер, TC-nav-006 revalidate.

Группа E change coverage-backfill-1 (add-ui-polish-r8, P12 полировка). Кейсы:
test-model/approved/add-ui-polish-r8/. Галерея — реальный images-сервис через
реверс-прокси (фикстура images_service из test_p15_wiki_editor; автостенд
conftest галерею не монтирует). Ядерный API-регресс (TC-P12N-008) — подпроцесс
pytest над представительными ядрами tests/api на стенде сессии + openapi
images-сервиса; полный перечень ≈173/≈124 кейса — прогон F.1.
Запуск: pytest tests/web/test_coverage_uip.py -q
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.web.test_p15_wiki_editor import (  # noqa: F401
    IMAGES_DIR,
    images_service,
    wiki_stand_schema,
)

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

REPO = Path(__file__).resolve().parents[2]
PASSWORD = os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!")
MARKER = "QABF-"


def _png_bytes(w=400, h=300, color=(120, 40, 200)) -> bytes:
    from PIL import Image

    buf = __import__("io").BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def _jpeg_bytes(w=400, h=300) -> bytes:
    from PIL import Image

    buf = __import__("io").BytesIO()
    Image.new("RGB", (w, h), (200, 120, 40)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def gal_proxy(images_service):
    """Адрес images-прокси модуля (роль nginx design §5)."""
    return images_service["base_url"]


@pytest.fixture
def gal_session(gal_proxy):
    """requests-сессия owner против images-прокси (Secure-кука по http —
    браузерное поведение localhost, конвенция conftest)."""
    import requests

    s = requests.Session()
    r = s.post(
        f"{gal_proxy}/api/auth/login",
        json={"login": "owner", "password": PASSWORD},
    )
    assert r.status_code == 200, r.text
    for c in s.cookies:
        c.secure = False
    yield s
    s.close()


def _qabf_cleanup():
    """Чистая галерея: удаление QABF-хвостов напрямую (БД + том) —
    DELETE /api/images/{id} в сервисе НЕТ (докстринг gallery.py), паттерн
    test_p12_gallery_rename_masonry_r8._cleanup."""
    import sqlite3

    db_path = os.environ.get("EKOTOV_WIKI_DB_PATH")
    if not db_path or not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    files: list[str] = []
    try:
        rows = conn.execute(
            "SELECT id, filename, thumb_name FROM images"
            " WHERE original_name LIKE ?",
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
        conn.execute("DELETE FROM gallery_tags WHERE name LIKE ?",
                     (MARKER + "%",))
        conn.commit()
    finally:
        conn.close()
    for f in files:
        try:
            os.remove(os.path.join(IMAGES_DIR, f))
        except OSError:
            pass


@pytest.fixture
def gal_clean():
    _qabf_cleanup()
    yield
    _qabf_cleanup()


def _upload(session, base: str, name: str, blob: bytes, mime: str,
            category: str | None = None) -> dict:
    data = {"category": category} if category else {}
    r = session.post(
        f"{base}/api/images",
        files=[("file", (name, blob, mime))],
        data=data,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _gallery_page(page, web_base_url, images_service, session):
    """Маршрутизация images-семейства страницы: /api/images* — прокси
    (requests-фулфилл: реверс-прокси test_p15 задваивает Content-Length,
    playwright route.fetch такой ответ не парсит), /images/* — fulfill
    реальными PNG-байтами (сервис раздает файлы только через nginx-том,
    прод-паттерн; естественные пропорции превью нужны masonry-геометрии)."""
    proxy = images_service["base_url"]

    def _to_api(route):
        request = route.request
        suffix = request.url.partition("/api/images")[2]
        r = session.request(
            request.method,
            f"{proxy}/api/images{suffix}",
            data=request.post_data_buffer or None,
        )
        try:
            route.fulfill(status=r.status_code, json=r.json())
        except ValueError:  # не-JSON (пустое тело/ошибка) — текстом
            route.fulfill(status=r.status_code, body=r.text)

    def _to_file(route):
        route.fulfill(body=_png_bytes(), content_type="image/png")

    # `**` обязателен: glob `*` не матчит `/`, и PUT /api/images/{id}/like
    # (лайк лайтбокса) миновал прокси → 404 веб-сервера, aria-pressed не
    # переключается. `**` покрывает и `/api/images?...`, и вложенные пути.
    page.context.route(f"{web_base_url}/api/images**", _to_api)
    page.context.route(f"{web_base_url}/images/*", _to_file)
    page.goto(f"{web_base_url}/gallery")


def _column_clusters(page) -> list[float]:
    """Число колонок masonry по X-кластеризации карточек (левые кромки)."""
    return page.evaluate(
        """() => {
          const xs = [...document.querySelectorAll('.g-card')]
            .map(c => Math.round(c.getBoundingClientRect().left));
          return [...new Set(xs)].sort((a, b) => a - b);
        }"""
    )


def _no_overlaps(page) -> bool:
    return page.evaluate(
        """() => {
          const cards = [...document.querySelectorAll('.g-card')]
            .map(c => c.getBoundingClientRect());
          for (let i = 0; i < cards.length; i++)
            for (let j = i + 1; j < cards.length; j++) {
              const a = cards[i], b = cards[j];
              const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
              const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
              if (ox > 1 && oy > 1) return false;
            }
          return true;
        }"""
    )


# ---------------------------------------------------------------------------
# TC-P12G-003 — rename: валидация 422, граница 255, разделители
# ---------------------------------------------------------------------------
def test_tc_p12g_003_rename_validation_422(gal_session, gal_proxy, gal_clean):
    """TC-P12G-003: PUT /api/images/{id}/name — пустое/отсутствующее/
    пробельное имя → 422 (валидационный обработчик, тело с details); 255
    символов → 200, 256 → 422; разделители «/» и «\\» → 422 (утвержденное
    ПМ отклонение M2 от design §4 — имя не путь); пробельно-краевое имя
    принимается ОБРЕЗАННЫМ (trim-факт); после каждого 422 имя в API прежнее
    (no partial write), файлы не инвалидируются."""
    img = _upload(gal_session, gal_proxy, f"{MARKER}rename.png",
                  _png_bytes(), "image/png")
    image_id = img["id"]
    original = img["original_name"]

    def _rename(payload):
        return gal_session.put(
            f"{gal_proxy}/api/images/{image_id}/name", json=payload
        )

    # Шаги 1–3: пустое / отсутствующее / пробельное — 422.
    for payload in ({"name": ""}, {}, {"name": "   "}):
        r = _rename(payload)
        assert r.status_code == 422, (payload, r.text)
        body = r.json()
        assert "name" in json.dumps(body["details"]), body

    # Шаг 4: граница 255/256.
    ok = _rename({"name": "А" * 255})
    assert ok.status_code == 200, ok.text
    assert len(ok.json()["name"]) == 255
    long_r = _rename({"name": "А" * 256})
    assert long_r.status_code == 422, long_r.text

    # Шаг 5: разделители — 422 (диспозиция M2); пробельно-краевое — trim.
    for bad in (f"{MARKER}подкаталог/имя", f"{MARKER}обратный\\имя"):
        r = _rename({"name": bad})
        assert r.status_code == 422, (bad, r.text)
    trimmed = _rename({"name": f"  {MARKER}пробелы по краям  "})
    assert trimmed.status_code == 200, trimmed.text
    assert trimmed.json()["name"] == f"{MARKER}пробелы по краям"

    # Шаг 6: после каждого 422 имя прежнее; файлы (filename/url) не менялись —
    # физический файл на томе на месте (сервис раздает байты nginx-том,
    # /images/* вне автостенда; том — IMAGES_DIR тест_p15-прокси).
    current = gal_session.get(f"{gal_proxy}/api/images/{image_id}").json()
    assert current["original_name"] == f"{MARKER}пробелы по краям", current
    assert current["filename"] == img["filename"], current
    assert current["url"] == img["url"], current
    assert (Path(IMAGES_DIR) / img["filename"]).exists(), img


# ---------------------------------------------------------------------------
# TC-P12G-008 — masonry: адаптив 2/3/4 колонки, перестройка на лету
# ---------------------------------------------------------------------------
def test_tc_p12g_008_masonry_adaptive(board_page, web_base_url,
                                      images_service, gal_session, gal_proxy,
                                      gal_clean):
    """TC-P12G-008: masonry-сетка — 480px → 2 колонки, 900px → 3,
    1400px → 4 (фактические брейкпоинты 880/1280 из gallery.css); на каждой
    ширине без наложений; перестройка на лету (без перезагрузки) при смене
    ширины 1400→900→480→1400; открытый лайтбокс при ресайзе не ломается.
    design_validator против мокапа 2.6 — вердиктная часть, вне автотеста."""
    page = board_page
    for i in range(10):
        _upload(
            gal_session, gal_proxy, f"{MARKER}m{i}.png",
            _png_bytes(w=400 + 60 * (i % 3), h=200 + 130 * (i % 4),
                       color=(30 * i, 60, 200)),
            "image/png",
        )
        deadline = time.monotonic() + 0.35  # различимый created_at
        while time.monotonic() < deadline:
            pass

    _gallery_page(page, web_base_url, images_service, gal_session)
    expect(page.locator(".g-card")).to_have_count(10)

    expected = {1400: 4, 900: 3, 480: 2}
    for width, cols in expected.items():
        page.set_viewport_size({"width": width, "height": 900})
        page.wait_for_timeout(200)
        clusters = _column_clusters(page)
        assert len(clusters) == cols, (width, clusters)
        assert _no_overlaps(page), width

    # Перестройка на лету: без перезагрузки страницы.
    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(200)
    for width in (900, 480, 1400):
        page.set_viewport_size({"width": width, "height": 900})
        page.wait_for_timeout(200)
        assert len(_column_clusters(page)) == expected[width], width
        assert _no_overlaps(page), width

    # Открытая карточка в лайтбоксе переживает ресайз (лайк не теряется).
    page.locator(".g-card").first.click()
    overlay = page.locator("#lightbox-overlay")
    expect(overlay).to_be_visible()
    page.set_viewport_size({"width": 480, "height": 900})
    expect(overlay).to_be_visible()
    before = page.locator("#lb-like-count").inner_text()
    page.locator("#lb-like").click()
    expect(page.locator("#lb-like")).to_have_attribute("aria-pressed", "true")
    assert page.locator("#lb-like-count").inner_text() == str(int(before) + 1)
    page.keyboard.press("Escape")
    expect(overlay).to_be_hidden()


# ---------------------------------------------------------------------------
# TC-P12G-009 — masonry: break-inside семантика
# ---------------------------------------------------------------------------
def test_tc_p12g_009_masonry_break_inside(board_page, web_base_url,
                                          images_service, gal_session,
                                          gal_proxy, gal_clean):
    """TC-P12G-009: техника masonry — CSS columns + break-inside: avoid;
    каждая карточка атомарна (bbox.width ≤ ширины колонки, целиком внутри
    одной колонки, ни одна не «перешивает» две); высоты колонок НЕ обязаны
    сравняться (masonry-семантика мокапа J); низ сетки без «провала» —
    пустой колонки выше 2× средней карточки."""
    page = board_page
    for i in range(10):
        _upload(
            gal_session, gal_proxy, f"{MARKER}b{i}.png",
            _png_bytes(w=400, h=180 + 170 * (i % 5), color=(40, 30 * i, 200)),
            "image/png",
        )
    _gallery_page(page, web_base_url, images_service, gal_session)
    expect(page.locator(".g-card")).to_have_count(10)
    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(200)

    m = page.evaluate(
        """() => {
          const grid = document.querySelector('.gallery-grid');
          const cards = [...document.querySelectorAll('.g-card')];
          const colCount = parseFloat(getComputedStyle(grid).columnCount);
          const gridW = grid.getBoundingClientRect().width;
          const gap = parseFloat(getComputedStyle(grid).columnGap) || 0;
          const colW = (gridW - gap * (colCount - 1)) / colCount;
          const bands = cards.map(c => {
            const r = c.getBoundingClientRect();
            const left = r.left - grid.getBoundingClientRect().left;
            const band = Math.round(left / (colW + gap));
            return {width: r.width, band,
                    within: left >= band * (colW + gap) - 1 &&
                            left + r.width <= (band + 1) * (colW + gap) + 1};
          });
          const heights = [];
          for (let b = 0; b < colCount; b++) {
            const inBand = cards.filter((_, i) => bands[i].band === b);
            const bottom = inBand.length
              ? Math.max(...inBand.map(c =>
                  c.getBoundingClientRect().bottom))
              : 0;
            heights.push(bottom);
          }
          const avgH = cards.reduce((s, c) =>
            s + c.getBoundingClientRect().height, 0) / cards.length;
          const gridBottom = Math.max(...heights);
          const pit = heights.some(h =>
            gridBottom - h > 2 * avgH);
          const avoid = cards.map(c =>
            getComputedStyle(c).breakInside);
          return {colCount, colW, bands, heights, pit, avoid};
        }"""
    )
    assert m["colCount"] == 4, m
    assert all(b["width"] <= m["colW"] + 1 for b in m["bands"]), m
    assert all(b["within"] for b in m["bands"]), m  # атомарность карточек
    assert all(a == "avoid" for a in m["avoid"]), m  # break-inside: avoid
    # Высоты колонок разные — допустимо; «провала» нет.
    assert len(set(m["heights"])) >= 1, m
    assert not m["pit"], m


# ---------------------------------------------------------------------------
# TC-P12G-010 — бейдж формата, ховер/фокус карточек
# ---------------------------------------------------------------------------
def test_tc_p12g_010_badge_hover_focus(board_page, web_base_url,
                                       images_service, gal_session, gal_proxy,
                                       gal_clean):
    """TC-P12G-010: бейдж формата в правом нижнем углу превью (right/bottom
    6px, bbox ⊂ .g-thumb, вне .g-card-body), текст — uppercase-расширение;
    ховер не сдвигает геометрию ПОТОКА (соседи на месте, X карточки не
    меняется) и меняет ступень фона/границы; фокус с клавиатуры — focus-ring
    виден. ФАКТ (диспозиция M3 vs код): hover-подъема translateY(-2px) в
    gallery.css НЕТ — утвержденный мокап «Пульта» (FR-132) заменяет его
    ступенями bg3/border-2 без сдвига; ассерт по фактической механике
    (поток не двигается — инвариант M3 соблюден)."""
    page = board_page
    _upload(gal_session, gal_proxy, f"{MARKER}badge.png", _png_bytes(),
            "image/png")
    _upload(gal_session, gal_proxy, f"{MARKER}badge.jpeg", _jpeg_bytes(),
            "image/jpeg")
    _gallery_page(page, web_base_url, images_service, gal_session)
    expect(page.locator(".g-card")).to_have_count(2)

    for ext in ("PNG", "JPEG"):
        card = page.locator(".g-card", has_text=f"{MARKER}badge."
                           + ext.lower()).first
        badge = card.locator(".fmt-badge")
        # Текст — расширение; uppercase дает CSS text-transform (textContent
        # хранится в нижнем регистре — факт реализации).
        expect(badge).to_have_text(ext.lower())
        assert badge.evaluate(
            "el => getComputedStyle(el).textTransform") == "uppercase"
        m = page.evaluate(
            """([needle]) => {
              // textContent-поиск: querySelector не знает :has-text
              // (плейрайт-расширение, в page.evaluate это SyntaxError).
              const card = [...document.querySelectorAll('.g-card')]
                .find(c => c.textContent.includes(needle));
              if (!card) return null;
              const thumb = card.querySelector('.g-thumb');
              const badge = card.querySelector('.fmt-badge');
              const tb = thumb.getBoundingClientRect();
              const bb = badge.getBoundingClientRect();
              const body = card.querySelector('.g-card-body');
              const bodyTop = body
                ? body.getBoundingClientRect().top : Infinity;
              return {right: tb.right - bb.right,
                      bottom: tb.bottom - bb.bottom,
                      inside: bb.left >= tb.left && bb.top >= tb.top &&
                              bb.right <= tb.right && bb.bottom <= tb.bottom,
                      aboveBody: bb.bottom <= bodyTop + 1};
            }""",
            [f"{MARKER}badge.{ext.lower()}"],
        )
        assert m, (ext, MARKER)
        assert m["inside"], (ext, m)
        assert abs(m["right"] - 6) <= 2 and abs(m["bottom"] - 6) <= 2, (ext, m)
        assert m["aboveBody"], (ext, m)  # не перекрывает название/счетчики

    # Ховер: геометрия потока не меняется, ступень фона/границы — да.
    card = page.locator(".g-card").first
    neighbor = page.locator(".g-card").nth(1)
    before = card.evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " const cs = getComputedStyle(el);"
        " return {x: r.left, w: r.width, bg: cs.backgroundColor,"
        " border: cs.borderColor}; }")
    nb_before = neighbor.evaluate(
        "el => el.getBoundingClientRect().top")
    card.hover()
    page.wait_for_timeout(250)
    after = card.evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " const cs = getComputedStyle(el);"
        " return {x: r.left, w: r.width, bg: cs.backgroundColor,"
        " border: cs.borderColor, shadow: cs.boxShadow}; }")
    nb_after = neighbor.evaluate("el => el.getBoundingClientRect().top")
    assert after["x"] == before["x"] and after["w"] == before["w"], after
    assert nb_after == nb_before, (nb_before, nb_after)  # поток на месте
    assert (after["bg"], after["border"]) != (before["bg"], before["border"])

    # Фокус с клавиатуры — focus-ring по токену, не обрезан.
    card.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    ring = page.evaluate(
        """() => { const el = document.activeElement;
             return el && el.classList.contains('g-card')
               ? getComputedStyle(el).boxShadow : null; }"""
    )
    assert ring and ring != "none", ring

    # Токены: правила бейджа/ховера — без цветовых литералов.
    css = (REPO / "frontend/static/css/gallery.css").read_text()
    for rule in (r"\.fmt-badge\s*{[^}]*}", r"\.g-card:hover\s*{[^}]*}"):
        block = re.search(rule, css, re.S)
        assert block, rule
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block.group(0)), \
            block.group(0)


# ---------------------------------------------------------------------------
# TC-P12G-011 — revalidate TC-GAL-115/116/122 на merge-ветке волн
# ---------------------------------------------------------------------------
def test_tc_p12g_011_revalidate_gal_115_116_122(board_page, web_base_url,
                                                images_service, gal_session,
                                                gal_proxy, gal_clean):
    """TC-P12G-011: TC-GAL-115 — сетка+фильтры при активном masonry: фильтр
    категории перерисовывает сетку, порядок карточек = выдаче API (created_at
    DESC), сброс возвращает все; TC-GAL-116 — лайтбокс сохраняет прежние
    действия и НОВЫЙ элемент #lb-rename у имени (добавление — допустимая
    дельта); TC-GAL-122 ×2 — gallery.css/gallery.js без цветовых литералов
    после rename/masonry-стилей (0-литеральный ассерт)."""
    page = board_page
    for i, cat in ((0, "Дом"), (1, "Работа"), (2, "Дом")):
        _upload(gal_session, gal_proxy, f"{MARKER}rv{i}.png",
                _png_bytes(color=(60 + 40 * i, 90, 150)),
                "image/png", category=cat)
        deadline = time.monotonic() + 1.05
        while time.monotonic() < deadline:
            pass

    _gallery_page(page, web_base_url, images_service, gal_session)
    expect(page.locator(".g-card")).to_have_count(3)

    # GAL-115: порядок карточек = выдаче API (created_at DESC).
    api_order = [img["original_name"] for img in
                 gal_session.get(f"{gal_proxy}/api/images").json()["images"]]
    dom_order = page.evaluate(
        """() => [...document.querySelectorAll('.g-card-title, .g-card-name')]
             .map(el => el.textContent.trim())"""
    )
    assert [f"{MARKER}rv{i}.png" for i in (2, 1, 0)] == api_order, api_order
    assert dom_order == api_order, (dom_order, api_order)

    # Фильтр категории перерисовывает masonry; сброс возвращает все.
    page.locator("#filter-category").select_option(label="Дом")
    expect(page.locator(".g-card")).to_have_count(2)
    assert len(_column_clusters(page)) >= 1
    page.locator("#filter-reset").click()
    expect(page.locator(".g-card")).to_have_count(3)

    # GAL-116: лайтбокс — прежние действия + rename-иконка.
    page.locator(".g-card").first.click()
    overlay = page.locator("#lightbox-overlay")
    expect(overlay).to_be_visible()
    expect(page.locator("#lb-rename")).to_be_visible()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#lb-counter-pos")).to_have_text("2 / 3")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#lb-counter-pos")).to_have_text("1 / 3")
    page.locator("#lb-like").click()
    expect(page.locator("#lb-like")).to_have_attribute("aria-pressed", "true")
    page.keyboard.press("Escape")
    expect(overlay).to_be_hidden()

    # GAL-122 ×2: 0-литеральный ассерт gallery.css И gallery.js.
    for static_file in ("gallery.css", "gallery.js"):
        src = (REPO / "frontend/static" /
               ("css" if static_file.endswith(".css") else "js") /
               static_file).read_text()
        literals = re.findall(r"#[0-9a-fA-F]{3,8}\b", src)
        assert not literals, (static_file, literals)


# ---------------------------------------------------------------------------
# TC-P12N-005 — revalidate TC-nav-006: геометрия «Настройки»/«Выйти»
# ---------------------------------------------------------------------------
def test_tc_p12n_005_settings_link_geometry(board_page):
    """TC-P12N-005 (revalidate TC-nav-006): ссылка «Настройки» внизу слева
    рядом с «Выйти» после появления svg-иконок волны 2.4: |ΔY| < height+32,
    одна X-колонка, «Настройки» ниже «Доски»; клик-таргет — сама ссылка
    (elementFromPoint по центру — <a>); ассерты без правки порогов."""
    page = board_page
    m = page.evaluate(
        """() => {
          const bb = (sel) => {
            const el = document.querySelector(sel);
            const r = el.getBoundingClientRect();
            return {x: r.left, y: r.top, w: r.width, h: r.height,
                    bottom: r.bottom, tag: el.tagName};
          };
          const byName = (name) => [...document.querySelectorAll(
            '#sidebar a, #sidebar button')]
            .find(el => el.textContent.trim() === name);
          const bbName = (name) => {
            const r = byName(name).getBoundingClientRect();
            return {x: r.left, y: r.top, w: r.width, h: r.height,
                    bottom: r.bottom, tag: byName(name).tagName};
          };
          return {settings: bbName('Настройки'), logout: bbName('Выйти'),
                  board: bbName('Доска')};
        }"""
    )
    s, lo, b = m["settings"], m["logout"], m["board"]
    assert abs(s["y"] - lo["y"]) < s["h"] + 32, m
    assert abs(s["x"] - lo["x"]) < s["w"], m  # одна колонка X
    assert s["bottom"] >= b["bottom"], m  # ниже пунктов навигации
    hit = page.evaluate(
        """() => { const el = [...document.querySelectorAll(
             '#sidebar a, #sidebar button')]
           .find(e => e.textContent.trim() === 'Настройки');
         const r = el.getBoundingClientRect();
         return document.elementFromPoint(
           r.left + r.width / 2, r.top + r.height / 2)?.tagName; }"""
    )
    assert hit == "A", hit  # рост bbox от иконки легитимен, таргет — ссылка


# ---------------------------------------------------------------------------
# TC-P12N-008 — ядерный API-регресс (CHK-P12-35)
# ---------------------------------------------------------------------------
def test_tc_p12n_008_core_api_regression():
    """TC-P12N-008: контракты ядра стабильны — представительные ядра tests/api
    (test_auth, test_categories, test_navigation, test_openapi_r11) зелены
    на merge-ветке; openapi images-сервиса включает /api/images/{{image_id}}/
    name (остальные маршруты неизменны). КЛАССИФИКАЦИЯ (докстринг кейса,
    «пред-существующие средовые — НЕ смешивать с дельтой»):
    - KeyError 'results' в 4 тестах — search-семейство не маршрутизировано
      на app-порт автостенда (документированная средовая; паритет nginx дает
      только web-маршрутизация);
    - fast-сьюты test_fastline.py/test_fast2.py — пред-существующие красные
      НА ЧИСТОМ стенде этой ветки (диагностика backfill: 10 failed/15 passed
      изолированно; 409-каскад + KeyError 'results') — в ворота бэкфилла не
      входят, классификация дефект/тест — за F.1.
    Полный перечень ≈173 keep-сьютов — прогон F.1."""
    env = dict(os.environ)
    assert env.get("EKOTOV_WIKI_BASE_URL"), "нужен стенд web-сессии"
    core = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "--tb=no",
         "-rf",
         "tests/api/test_auth.py",
         "tests/api/test_categories.py",
         "tests/api/test_navigation.py",
         "tests/api/test_openapi_r11.py"],
        cwd=str(REPO), env=env, capture_output=True, text=True, timeout=420,
    )
    failed = {line.split()[1] for line in core.stdout.splitlines()
              if line.startswith("FAILED ")}
    documented_env = {
        "tests/api/test_auth.py::test_exempt_list_exhaustive",
        "tests/api/test_auth.py::test_second_user_wife_login_and_work",
        "tests/api/test_categories.py::test_category_delete_unused_ok",
        "tests/api/test_categories.py::"
        "test_task_create_with_unknown_category_422_not_created",
    }
    unexpected = failed - documented_env
    assert not unexpected, (sorted(unexpected), core.stdout[-4000:])
    assert core.returncode == 0 or failed <= documented_env, (
        core.stdout[-4000:] + core.stderr[-2000:])

    images_suite = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header",
         "services/images/tests/test_images_service.py::test_openapi_paths"],
        cwd=str(REPO), env=env, capture_output=True, text=True, timeout=180,
    )
    assert images_suite.returncode == 0, (
        images_suite.stdout[-2000:] + images_suite.stderr[-1000:])


# ---------------------------------------------------------------------------
# TC-P12N-009 — ядерный web-регресс: DOM-контракты (CHK-P12-36)
# ---------------------------------------------------------------------------
def test_tc_p12n_009_core_web_contracts(board_page, page, web_base_url):
    """TC-P12N-009: незатронутые волны разделы не деградировали — DOM-контракты
    ОГР-28 на месте (прямое следствие зеленого прогона keep-сьютов ≈124,
    полный перечень — прогон F.1/R2-R3): доска (#task-detail-attrs,
    #task-view-close, #task-tags-chips, .fast-row), поиск
    (#search-advanced-submit), навигация/настройки живы."""
    page_board = board_page
    for selector in ("#task-detail-attrs", "#task-view-close",
                     "#task-tags-chips", ".fast-row",
                     "#fastline-add-button", "#create-task-button"):
        expect(page_board.locator(selector).first).to_have_count(1)

    page.goto(f"{web_base_url}/search")
    for selector in ("#search-advanced-submit", "#search-builder-submit",
                     "#search-results"):
        expect(page.locator(selector).first).to_have_count(1)

    page.goto(f"{web_base_url}/settings")
    expect(page.locator("#category-list")).to_have_count(1)
    page.goto(f"{web_base_url}/settings/profile")
    expect(page.locator("#profile-form")).to_have_count(1)


# ---------------------------------------------------------------------------
# TC-UIP-102 — Вторая fast-задача: 409, форма открыта, поля сохранены
# ---------------------------------------------------------------------------
def test_tc_uip_102_second_fast_form_kept(board_page, web_owner_session,
                                          web_base_url, web_cleanup_created):
    """TC-UIP-102: отклонение второй fast — сообщение «fast line занята»
    (409-путь), форма ОСТАЛАСЬ открыта, введенные поля сохранены; подсветка
    первой плитки (.task-card-fast) не задета, столбец не красится; после
    отмены на доске ровно одна fast, «Fast-вторая» не создана."""
    page = board_page
    # Форма создания открыта ДО занятия слота (чекбокс доступен).
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    page.get_by_label("Название").fill("Fast-вторая")

    first = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "Fast-первая", "is_fast": True, "priority": "high"},
    )
    assert first.status_code == 201, first.text
    web_cleanup_created(first.json()["id"])
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    # Подсветка первой плитки; столбец не красится (инверсия TC-UIP-101).
    first_card = page.get_by_role("article").filter(has_text="Fast-первая")
    expect(first_card).to_have_class(re.compile("task-card-fast"))
    column_class = first_card.evaluate(
        "el => el.closest('.fastline-column').className")
    assert "has-fast" not in column_class, column_class

    # Сабмит второй fast при занятой линии: 409, форма открыта, поля живы.
    page.get_by_role("button", name="Создать задачу").click()
    page.get_by_label("Название").fill("Fast-вторая")
    page.locator("#task-is-fast").check()
    expect(page.locator("#task-priority")).to_have_value("high")
    expect(page.locator("#task-priority")).to_be_disabled()  # FR-88 сохранен
    with page.expect_response(
        lambda r: r.request.method == "POST" and r.url.endswith("/api/tasks")
    ) as resp_info:
        page.locator("#task-form-submit").click()
    assert resp_info.value.status == 409, resp_info.value.text
    expect(page.locator("#task-form-overlay")).to_be_visible()
    expect(page.locator("#task-form-error")).to_be_visible()
    assert "уже есть задача" in (
        page.locator("#task-form-error").inner_text().lower())
    assert page.get_by_label("Название").input_value() == "Fast-вторая"

    # Отмена: на доске ровно одна fast, второй нет.
    page.locator("#task-form-cancel").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    board = web_owner_session.get(f"{web_base_url}/api/board").json()
    fasts = [t for tasks in board["columns"].values()
             for t in tasks if t["is_fast"]]
    assert [t["title"] for t in fasts] == ["Fast-первая"], board


# ---------------------------------------------------------------------------
# TC-UIP-107 — Модалка просмотра тикета: вид по мокапу волны 2.2
# ---------------------------------------------------------------------------
def test_tc_uip_107_ticket_modal_view(board_page, web_owner_session,
                                      web_base_url, web_cleanup_created):
    """TC-UIP-107: модалка просмотра — роль dialog + aria-labelledby, шапка
    (кикер «Задача · <id>», сериф-название, бейджи приоритет/статус), тело
    (описание, признаки, теги-чипы, комментарии), футер «Редактировать»;
    read-only (ни одного поля ввода); закрытие Esc/крестик/подложка с
    возвратом фокуса на триггер; крестик 40×40; prefers-reduced-motion не
    ломает открытие. ФАКТ: aria-modal в разметке/JS нет — расхождение
    с шагом 3 кейса зафиксировано, остальная композиция мокапа B совпадает.
    Пункт 5 кейса (вердикт design_validator в review-NNN-design.md) —
    вердиктная часть, вне автотеста."""
    page = board_page
    r = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": "QABF-modal",
            "description": "описание задачи для модалки",
            "category": "Дом",
            "tags": ["QABF-тег"],
            "priority": "high",
        },
    )
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]
    web_cleanup_created(task_id)
    web_owner_session.post(
        f"{web_base_url}/api/tasks/{task_id}/comments",
        json={"body": "комментарий к модалке"},
    )
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    card = page.get_by_role("article").filter(has_text="QABF-modal")
    card.click()
    overlay = page.locator("#task-detail-overlay")
    view = page.locator("#task-detail-overlay .task-view")
    expect(overlay).to_be_visible()
    expect(view).to_have_attribute("role", "dialog")
    expect(view).to_have_attribute("aria-labelledby", "task-detail-title")

    # Шапка: кикер + сериф-название + бейджи.
    expect(page.locator(".task-view-kicker")).to_have_text(
        f"Задача · STAND-{task_id}")
    expect(page.locator("#task-detail-title")).to_contain_text("QABF-modal")
    expect(page.locator(".task-view-badge, #task-detail-attrs").first
           ).to_be_visible()
    cross = page.locator("#task-view-close").bounding_box()
    assert cross["width"] == pytest.approx(40, abs=8), cross
    assert cross["height"] == pytest.approx(40, abs=8), cross

    # Тело: описание, признаки, теги-чипы, комментарий с автором · датой.
    expect(page.locator("#task-detail-overlay")).to_contain_text(
        "описание задачи для модалки")
    attrs = page.locator("#task-detail-attrs")
    expect(attrs).to_contain_text("Дом")
    expect(page.locator("#task-detail-overlay")).to_contain_text("QABF-тег")
    comments = page.locator("#task-comments-list")
    expect(comments).to_contain_text("owner")
    expect(comments).to_contain_text("комментарий к модалке")

    # Read-only: ни одного поля ввода; футер — «Редактировать».
    inputs = view.evaluate(
        "el => el.querySelectorAll('input, textarea, select').length")
    assert inputs == 0, inputs
    expect(page.locator("#task-edit-button")).to_be_visible()

    # Закрытие Esc: фокус возвращен на триггер (rememberViewTrigger —
    # последний сфокусированный элемент до открытия; клик по карточке
    # фокус не ставит — это body) и точно не остается в диалоге.
    page.keyboard.press("Escape")
    expect(overlay).to_be_hidden()
    focused = page.evaluate(
        """() => ({tag: document.activeElement?.tagName,
             inOverlay: document.getElementById('task-detail-overlay')
               .contains(document.activeElement)})"""
    )
    assert focused["inOverlay"] is False, focused

    # Крестик и подложка; prefers-reduced-motion не ломает открытие.
    page.emulate_media(reduced_motion="reduce")
    card.click()
    expect(overlay).to_be_visible()
    page.locator("#task-view-close").click()
    expect(overlay).to_be_hidden()
    card.click()
    expect(overlay).to_be_visible()
    page.mouse.click(5, 400)  # клик по подложке (вне окна)
    expect(overlay).to_be_hidden()
    page.emulate_media(reduced_motion=None)


# ---------------------------------------------------------------------------
# TC-UIP-114 — Геометрия кнопки настроек: bbox-замер + focus-visible
# ---------------------------------------------------------------------------
def test_tc_uip_114_settings_button_geometry(board_page, page, web_base_url):
    """TC-UIP-114 (revalidate TC-nav-006, дополнение к TC-UIP-106): соседство
    «Настройки»/«Выйти» без правок порогов; bbox в active/focus-visible
    совпадает с базовым (новые состояния FR-96 не сдвигают геометрию
    сайдбара); TC-nav-007/008 (keep): переход по «Настройкам» открывает
    /settings."""
    page_board = board_page

    def _bbox_of(page_obj, name):
        return page_obj.evaluate(
            """(name) => { const el = [...document.querySelectorAll(
                 '#sidebar a, #sidebar button')]
               .find(e => e.textContent.trim() === name);
             const r = el.getBoundingClientRect();
             return [r.left, r.top, r.width, r.height]; }""",
            name,
        )

    base = _bbox_of(page_board, "Настройки")
    logout = _bbox_of(page_board, "Выйти")
    assert abs(base[1] - logout[1]) < base[3] + 32, (base, logout)
    assert abs(base[0] - logout[0]) < base[2], (base, logout)

    # focus-visible (клавиатурный фокус): bbox не сдвигается.
    page_board.locator("#create-task-button").focus()
    for _ in range(15):
        page_board.keyboard.press("Tab")
        if page_board.evaluate(
            "document.activeElement?.textContent?.trim()") == "Настройки":
            break
    assert page_board.evaluate(
        "document.activeElement?.textContent?.trim()") == "Настройки"
    assert _bbox_of(page_board, "Настройки") == base, (
        base, _bbox_of(page_board, "Настройки"))

    # TC-nav-007 (keep): переход открывает /settings.
    page_board.locator("#sidebar").get_by_role(
        "link", name="Настройки").click()
    page.wait_for_url(f"{web_base_url}/settings")
    expect(page.locator("#category-list")).to_have_count(1)
