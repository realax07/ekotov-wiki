"""add-ui-polish-r8 3.1 fix-цикл review-004 (major-1): TC-P12N-004.

Трассировка TC (test-model/approved/add-ui-polish-r8/TC-P12N-004.md):
сайдбар-viewport (.sidebar height 100vh + sticky + overflow-y auto;
внутренний скролл .content УБРАН — BUG-011: он глушил документный
скролл, регресс 9b1e4f1): на галерее с длинной сеткой footer сайдбара
(«Настройки»/«Выйти») остается в viewport при любой прокрутке, оба
элемента кликабельны (elementFromPoint); прокрутка идет ДОКУМЕНТОМ
(window.scrollY), сайдбар sticky не смещается (bbox footer'а до/после
прокрутки идентичен, ≤1px).

Буква шага 1 кейса (documentElement.scrollHeight > innerHeight)
действительна вновь: BUG-011-фикс вернул документный скролл (временное
отклонение «документ не растягивается» эпохи #50 отменено).

Фикстуры — QAGAL-префикс через API images (≥30 плиток — сетка длиннее
viewport); teardown по префиксу — копия test_p12_gallery_rename_masonry_r8
(_cleanup БД+том). Предусловие кейса «документ длинный» проверяется
precondition-check'ом (на короткой странице кейс невалиден).

Среда: nginx-стенд с images-маршрутизацией (:18443; автостенд conftest
галерею не обслуживает — пред-существующее средовое, как R4-сьюты).
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
# ≥30 плиток (кейс: «≥30–60») — гарантия scrollHeight > viewport.
TILES = 32


def _png_bytes(w=400, h=300, color=(120, 40, 200)):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def _owner_session() -> requests.Session:
    """requests-сессия owner с secure=False (конвенция R4-сьютов: браузер
    считает 127.0.0.1 trustworthy, requests — нет)."""
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"login": "owner", "password": PASSWORDS["owner"]},
    )
    assert r.status_code == 200
    for c in s.cookies:
        c.secure = False
    return s


def _upload_api(name: str) -> dict:
    s = _owner_session()
    fields = [("file", (name, _png_bytes(), "image/png"))]
    r = s.post(f"{BASE_URL}/api/images", files=fields)
    s.close()
    assert r.status_code == 201, r.text
    return r.json()


def _cleanup():
    """Чистая галерея: удаление QAGAL-хвостов (БД + том).

    Без EKOTOV_WIKI_DB_PATH чистка невозможна (endpoints DELETE у images
    нет) — тест ниже требует env явно (внятный skip вместо накопления
    хвостов на стенде, урок minor-2 review-004).
    """
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
    if not DB_PATH:
        pytest.skip(
            "нужен EKOTOV_WIKI_DB_PATH: teardown QAGAL-фикстур идет через БД "
            "(DELETE /api/images нет); без env сьют копил бы хвосты на стенде"
        )
    _cleanup()
    yield
    _cleanup()


@pytest.fixture()
def gallery_page(browser):
    context = browser.new_context(base_url=BASE_URL, viewport={"width": 1280, "height": 720})
    page = context.new_page()
    page.goto(f"{BASE_URL}/login")
    page.fill("#login", "owner")
    page.fill("#password", PASSWORDS["owner"])
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    yield page
    context.close()


def test_sidebar_footer_visible_on_long_gallery(gallery_page):
    """TC-P12N-004 (микрофикс #50, FR-13/FR-94, NFR-22): на галерее с длинной
    сеткой (≥30 плиток) — документ выше viewport; bbox .sidebar-footer
    («Настройки»/«Выйти») полностью в viewport и кликабелен
    (elementFromPoint); прокрутка контента не смещает сайдбар (bbox
    footer'а до/после идентичен, ≤1px); клик «Настройки» открывает
    /settings (кнопка работает с длинной страницы)."""
    # Фикстуры: 32 плитки через API images (том пустым не считаем —
    # сетка должна растянуть контент и на повторном прогоне).
    uploaded = []
    try:
        for i in range(TILES):
            uploaded.append(_upload_api(f"{MARKER}p12n004-{i:02d}.png"))

        page = gallery_page
        page.goto(f"{BASE_URL}/gallery")
        page.wait_for_load_state("networkidle")

        # Шаг 1, precondition-check: документ «длинный» — сетка растянула
        # ДОКУМЕНТ (BUG-011: документный скролл восстановлен, временное
        # отклонение эпохи #50 «документ не растягивается» отменено).
        grid_count = page.locator(".g-card").count()
        assert grid_count >= TILES, (
            f"сетка короче фикстур: {grid_count} < {TILES} — "
            "закройте/почистите чужие QAGAL-хвосты"
        )
        geo0 = page.evaluate(
            "() => ({ scroll: document.documentElement.scrollHeight,"
            " inner: window.innerHeight,"
            " cScroll: document.querySelector('.content').scrollHeight,"
            " cClient: document.querySelector('.content').clientHeight })"
        )
        assert geo0["scroll"] > geo0["inner"], (
            f"документ НЕ растянут выше viewport ({geo0}) — precondition "
            "кейса (сетка должна растягивать документ)"
        )
        assert geo0["cScroll"] >= geo0["cClient"], (
            f"область контента пуста ({geo0}) — precondition кейса "
            "(сетка должна отдавать контент)"
        )

        # Шаг 2: bbox footer'а в исходном скролле — целиком в viewport;
        # «Настройки» и «Выйти» кликабельны (elementFromPoint — footer).
        footer = page.locator(".sidebar-footer")
        expect(footer).to_be_visible()
        box0 = footer.bounding_box()
        vh = geo0["inner"]
        assert box0["y"] >= 0 and box0["y"] + box0["height"] <= vh + 0.5, (
            f"footer вне viewport: {box0}, innerHeight={vh}"
        )
        hits = page.evaluate(
            """() => {
              const f = document.querySelector('.sidebar-footer');
              const fr = f.getBoundingClientRect();
              const hitSettings = document.elementFromPoint(
                fr.x + fr.width / 2, fr.y + fr.height / 2);
              const btn = document.getElementById('logout-button');
              const br = btn.getBoundingClientRect();
              const hitLogout = document.elementFromPoint(
                br.x + br.width / 2, br.y + br.height / 2);
              return {
                settings: !!hitSettings && (hitSettings === f || f.contains(hitSettings)
                  || hitSettings.closest('.sidebar-footer') === f),
                logout: !!hitLogout && (hitLogout === btn || btn.contains(hitLogout)),
              };
            }"""
        )
        assert hits["settings"], f"«Настройки» перекрыта: {hits}"
        assert hits["logout"], f"«Выйти» перекрыта: {hits}"

        # Шаг 3: прокрутка колесом над сеткой — ДОКУМЕНТНАЯ (BUG-011),
        # сайдбар sticky — bbox footer'а до/после идентичен (≤1px).
        page.locator("#gallery-grid").hover()
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(200)
        geo1 = page.evaluate(
            "() => ({ scroll: document.documentElement.scrollHeight,"
            " inner: window.innerHeight,"
            " winY: window.scrollY,"
            " contentTop: document.querySelector('.content').scrollTop })"
        )
        assert geo1["winY"] > 0, (
            f"документ не проскроллился (window.scrollY={geo1['winY']}) — "
            "документный скролл потерян (регресс BUG-011)"
        )
        assert geo1["contentTop"] == 0, (
            f".content скроллится внутри ({geo1['contentTop']}) — внутренний "
            "скролл #50 вернулся, документный скролл заглушен"
        )
        box1 = footer.bounding_box()
        for key in ("x", "y", "width", "height"):
            assert abs(box0[key] - box1[key]) <= 1, (key, box0, box1)

        # Шаг 4: функциональность на длинной странице — «Настройки» работает.
        footer.get_by_role("link", name="Настройки").click()
        page.wait_for_url("**/settings")
        assert page.url.endswith("/settings"), page.url
    finally:
        # Хвосты чистит autouse-teardown; список uploaded — для ясности
        # (реальное удаление — БД+том по префиксу).
        del uploaded
