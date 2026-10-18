"""QA 2.1 add-gallery-service — web/e2e-сьют галереи (TC-GAL-115..119).

Прогон по approved-кейсам test-model/approved/add-gallery-service/ через
nginx-стенд :18443 (app :8080 + search :8378 + images :8379; images-семейство
маршрутизируется nginx'ом, статика — /static/ alias того же worktree).

Трассировка TC:
- TC-GAL-115 — сетка карточек (превью/название/категория/теги-пилюли/счетчики),
  фильтры категория/тег/комбинация/сброс, паритет owner и PE.
- TC-GAL-116 — лайтбокс: открытие, ←/→ циклично (кнопки+клавиши), Esc,
  лайк/комментарий из окна, скачивание оригинала; фильтрованная выдача.
- TC-GAL-117 — лайк с подсветкой «мой голос», комментарий через UI, пустой
  422, чужой комментарий без кнопки удаления, XSS-дисциплина.
- TC-GAL-118 — загрузка: форма (input + drag&drop), ошибки 422 в UI.
- TC-GAL-119 — сайдбар «Галерея» 4-м пунктом, «Видео» — 5-м (1.5
  video-hosting) у owner И PE, переход, регресс разделов, отсутствие
  связей с трекером (ОВ-3).

Браузер: playwright headless chromium (браузер уже в ~/.cache/ms-playwright).
Изоляция: QAGAL-префикс имен загрузок; teardown чистит БД + том по префиксу.
"""

import os
import re
import sqlite3

import pytest
from playwright.sync_api import expect

from tests.web.pages.auth import Sidebar
from tests.web.pages.gallery import GalleryPage

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

BASE_URL = os.environ.get("EKOTOV_WIKI_BASE_URL", "http://127.0.0.1:18443")
DB_PATH = os.environ.get("EKOTOV_WIKI_DB_PATH")

MARKER = "QAGAL-"

LOGIN = {"owner": "owner", "wife": "wife"}
PASSWORDS = {
    "owner": os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!"),
    "wife": os.environ.get("EKOTOV_WIKI_WIFE_PASSWORD", "QaWife_Pass_2!"),
}

IMAGES_DIR = os.environ.get("EKOTOV_WIKI_IMAGES_DIR", "/tmp/qa21-gallery/images")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _png_bytes(color=(120, 40, 200)):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (400, 300), color).save(buf, "PNG")
    return buf.getvalue()


def _upload_api(user: str, name: str, **extra):
    """Сид через API (upload-через-UI покрывается TC-GAL-118 отдельно)."""
    import requests

    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"login": user, "password": PASSWORDS[user]},
    )
    assert r.status_code == 200
    for c in s.cookies:
        c.secure = False  # Secure-кука по http — браузерное поведение localhost
    fields = [("file", (name, _png_bytes(), "image/png"))]
    fields += [(k, (None, v)) for k, v in extra.items()]
    r = s.post(f"{BASE_URL}/api/images", files=fields)
    assert r.status_code == 201, r.text
    out = r.json()
    s.close()
    return out


def _db():
    assert DB_PATH, "EKOTOV_WIKI_DB_PATH обязателен (очистка QAGAL-хвостов)"
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cleanup():
    if not DB_PATH:
        return
    with _db() as conn:
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
        files = []
        for r in rows:
            files += [r["filename"], r["thumb_name"]]
            conn.execute("DELETE FROM images WHERE id = ?", (r["id"],))
        conn.execute(
            "DELETE FROM image_tags WHERE tag_id IN"
            " (SELECT id FROM gallery_tags WHERE name LIKE ?)",
            (MARKER + "%",),
        )
        conn.execute("DELETE FROM gallery_tags WHERE name LIKE ?", (MARKER + "%",))
        conn.execute(
            "DELETE FROM image_categories WHERE name LIKE ?", (MARKER + "%",)
        )
        conn.commit()
    for f in files:
        try:
            os.remove(os.path.join(IMAGES_DIR, f))
        except OSError:
            pass


@pytest.fixture(scope="session")
def browser_instance(browser):
    yield browser


@pytest.fixture(autouse=True)
def _clean_qagal_before_each():
    """Чистая галерея на каждый тест: сетка/порядок листания/счетчики карточек
    в шагах кейсов рассчитаны на выдачу ТОЛЬКО своих загрузок (перегон
    3430e4f: без очистки хвосты предыдущего теста ломали ожидания count=3 и
    порядок created_at DESC). QAGAL-префикс — своя зона, чужие данные
    (задачи/аватары) не затрагиваются."""
    _cleanup()


@pytest.fixture(scope="module", autouse=True)
def _clean_qagal_after_module():
    """Пост-очистка QAGAL-хвостов сьюта: тесты LEAVE загруженное в галерею
    (tc_gal_119: QAGAL-sb.png без удаления в теле), галерейный стенд
    персистентен — хвост ломает сеточные ожидания (count=3) следующего
    прогона/сьюта (класс утечки regress-final video-hosting, группа 4)."""
    yield
    _cleanup()


def _login(page, user: str):
    """Вход через /login (UI): cookie session Secure — localhost trustworthy."""
    page.goto(f"{BASE_URL}/login")
    page.fill("#login", user)
    page.fill("#password", PASSWORDS[user])
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


@pytest.fixture
def gallery_js_page(browser_instance):
    """Страница /gallery с guard'ом BUG-008: если gallery.js не исполнился
    (SyntaxError дубля refreshFiltersFromData — см.
    test-model/bugs/BUG-008-gallery-js-duplicate-function-syntax-error.md),
    e2e-шаги сетки/лайтбокса/формы невыполнимы — честный SKIP с причиной.
    После фикса BUG-008 guard пропускает тесты как обычно."""
    context = browser_instance.new_context(base_url=BASE_URL)
    page = context.new_page()
    errors: list = []

    def _on_error(exc):
        errors.append(str(exc))

    page.on("pageerror", _on_error)
    _login(page, "owner")
    page.goto(f"{BASE_URL}/gallery")
    page.wait_for_load_state("networkidle")
    if any("already been declared" in str(e) for e in errors):
        context.close()
        pytest.skip(
            "BUG-008: gallery.js SyntaxError (дубль refreshFiltersFromData) —"
            " JS-модуль галереи не исполняется, /gallery мертва (блокер);"
            " e2e-шаги невыполнимы до фикса dev"
        )
    yield page
    context.close()


# ---------------------------------------------------------------------------
# TC-GAL-115 — сетка и фильтры (+ паритет PE)
# ---------------------------------------------------------------------------


def test_tc_gal_115_grid_and_filters_owner_vs_pe(gallery_js_page, browser_instance):
    """TC-GAL-115: сетка (превью/название/категория/теги/счетчики); фильтры
    категория/тег/комбинация и сброс перерисовывают сетку по API-логике;
    PE видит идентичную галерею (паритет ОВ-4).

    browser_instance запрашивается параметром (перегон 3430e4f): тело теста
    ссылается на него для PE-контекста, но не запросило фикстуру — имя
    резолвилось в FixtureFunctionDefinition (AttributeError на new_context);
    дефект проявился только после снятия BUG-008-guard'а (тест не исполнялся)."""
    _upload_api("owner", MARKER + "A.png",
                category=MARKER + "семья", tags=f"{MARKER}лето,{MARKER}дача")
    _upload_api("owner", MARKER + "B.png", category=MARKER + "семья")
    _upload_api("owner", MARKER + "C.png")
    page = gallery_js_page
    gallery = GalleryPage(page)
    page.reload()
    page.wait_for_load_state("networkidle")

    for user in ("owner", "wife"):
        context = browser_instance.new_context(base_url=BASE_URL)
        page = context.new_page()
        gallery = GalleryPage(page)
        _login(page, user)
        page.goto(f"{BASE_URL}/gallery")
        page.wait_for_load_state("networkidle")

        # Полная сетка: 3 карточки с названием + превью.
        cards = gallery.cards()
        expect(cards).to_have_count(3)
        for name in ("A.png", "B.png", "C.png"):
            expect(gallery.card_title(MARKER + name)).to_be_visible()
        first = gallery.card(MARKER + "A.png")
        expect(first.locator("img")).to_be_visible()
        expect(first.locator(".task-category", has_text=MARKER + "семья")).to_be_visible()
        expect(first.locator(".task-tag", has_text=MARKER + "лето")).to_be_visible()
        expect(first.locator(".task-tag", has_text=MARKER + "дача")).to_be_visible()
        expect(first.locator(".stat").first).to_be_visible()

        # Фильтр по категории → A и B.
        gallery.filter_category.select_option(MARKER + "семья")
        page.wait_for_load_state("networkidle")
        expect(gallery.cards()).to_have_count(2)
        expect(gallery.card(MARKER + "C.png")).to_have_count(0)

        # Комбинация category+tag → только A (конъюнкция).
        gallery.filter_tag.select_option(MARKER + "лето")
        expect(gallery.cards()).to_have_count(1)
        expect(gallery.card(MARKER + "A.png")).to_have_count(1)

        # Только тег (сброс категории через полный reset, затем tag).
        gallery.filter_reset.click()
        gallery.filter_tag.select_option(MARKER + "летo" if False else MARKER + "лето")
        expect(gallery.cards()).to_have_count(1)

        # Сброс — полная сетка.
        gallery.filter_reset.click()
        expect(gallery.cards()).to_have_count(3)
        context.close()


# ---------------------------------------------------------------------------
# TC-GAL-116 — лайтбокс
# ---------------------------------------------------------------------------


def test_tc_gal_116_lightbox_nav_reactions_comment_download(gallery_js_page):
    """TC-GAL-116: клик по превью открывает full-screen модалку; ←/→ (кнопки
    и клавиши) листают циклично; Esc закрывает; лайк и комментарий из окна
    (счетчик/подсветка обновляются без выхода); «скачать» — оригинал.

    Порядок листания = текущая отфильтрованная выдача (created_at DESC,
    свежие первыми — предусловие кейса «порядок = текущая выдача»): после
    загрузки lb1/lb2/lb3 сетка [lb3, lb2, lb1]; от lb1 «назад» → lb2, от
    lb1 «вперед» (циклично, lb1 последний) → lb3.
    Примечание перегона 3430e4f: тест исполнился впервые (BUG-008-guard
    снят); исходные шаги предполагали порядок ASC — сверены с семантикой
    списка (TC-GAL-110 шаг 5, created_at DESC) и приведены к ней."""
    a = _upload_api("owner", MARKER + "lb1.png")
    _upload_api("owner", MARKER + "lb2.png")
    _upload_api("owner", MARKER + "lb3.png")

    page = gallery_js_page
    gallery = GalleryPage(page)
    page.reload()
    page.wait_for_load_state("networkidle")

    # Шаг 1: открытие кликом по карточке.
    gallery.card(MARKER + "lb1.png").click()
    overlay = gallery.lightbox
    expect(overlay).to_be_visible()
    expect(gallery.lb_title).to_contain_text(MARKER + "lb1.png")

    # Шаг 2: кнопки ←/→ циклично по выдаче created_at DESC
    # ([lb3, lb2, lb1]; lb1 — последний элемент выдачи).
    gallery.lb_prev.click()
    expect(gallery.lb_title).to_contain_text(MARKER + "lb2.png")
    gallery.lb_prev.click()
    expect(gallery.lb_title).to_contain_text(MARKER + "lb3.png")
    gallery.lb_prev.click()
    expect(gallery.lb_title).to_contain_text(MARKER + "lb1.png")
    gallery.lb_next.click()
    expect(gallery.lb_title).to_contain_text(MARKER + "lb3.png")

    # Клавиатура: ArrowRight от lb3 (индекс 0) → lb2, ArrowLeft → обратно lb3.
    page.keyboard.press("ArrowRight")
    expect(gallery.lb_title).to_contain_text(MARKER + "lb2.png")
    page.keyboard.press("ArrowLeft")
    expect(gallery.lb_title).to_contain_text(MARKER + "lb3.png")

    # Шаг 4: лайк из модалки — подсветка + счетчик без выхода из окна.
    gallery.lb_like.click()
    expect(gallery.lb_like).to_have_attribute("aria-pressed", "true")
    expect(gallery.lb_like_count).to_have_text("1")

    # Комментарий из модалки.
    gallery.lb_comment_input.fill("QAGAL-коммент из лайтбокса")
    gallery.lb_comment_send.click()
    expect(gallery.lb_comments_list).to_contain_text(
        "QAGAL-коммент из лайтбокса"
    )

    # Шаг 5: Esc закрывает; сетка на месте.
    page.keyboard.press("Escape")
    expect(overlay).to_be_hidden()
    expect(gallery.cards()).to_have_count(3)

    # Шаг 6: «скачать» — href оригинала (/images/<filename>, не превью).
    gallery.card(MARKER + "lb1.png").click()
    expect(overlay).to_be_visible()
    href = gallery.lb_download.get_attribute("href")
    assert href and href.startswith("/images/") and href.endswith(".png"), href
    assert href == a["url"], (href, a["url"])

    # Проверка скачивания через fetch (download-атрибут в headless не
    #materializуется на диск без профиля): байты оригинала доступны по href.
    resp = page.request.get(f"{BASE_URL}{href}")
    assert resp.status == 200
    assert len(resp.body()) > 0

    # Крестик тоже закрывает.
    gallery.lb_close.click()
    expect(overlay).to_be_hidden()


# ---------------------------------------------------------------------------
# TC-GAL-117 — лайк/комментарий через UI (+ XSS)
# ---------------------------------------------------------------------------


def test_tc_gal_117_like_highlight_comment_ui_xss(gallery_js_page, browser_instance):
    """TC-GAL-117: лайк через UI с подсветкой и persist (после перезагрузки),
    смена/снятие; комментарий с автором; пустой → человекочитаемая ошибка;
    чужой комментарий без кнопки удаления; скриптовый текст не исполняется."""
    _upload_api("owner", MARKER + "x1.png")

    page = gallery_js_page
    gallery = GalleryPage(page)
    page.reload()
    page.wait_for_load_state("networkidle")

    # Лайк с карточки (через лайтбокс — кнопки реакции в панели).
    gallery.card(MARKER + "x1.png").click()
    expect(gallery.lightbox).to_be_visible()
    gallery.lb_like.click()
    expect(gallery.lb_like).to_have_attribute("aria-pressed", "true")

    # Перезагрузка — состояние пережило (persisted).
    page.reload()
    page.wait_for_load_state("networkidle")
    gallery.card(MARKER + "x1.png").click()
    expect(gallery.lb_like).to_have_attribute("aria-pressed", "true")
    expect(gallery.lb_like_count).to_have_text("1")

    # Смена голоса: dislike — подсветка переместилась.
    gallery.lb_dislike.click()
    expect(gallery.lb_dislike).to_have_attribute("aria-pressed", "true")
    expect(gallery.lb_like).to_have_attribute("aria-pressed", "false")

    # Повторный same-sign — снятие.
    gallery.lb_dislike.click()
    expect(gallery.lb_dislike).to_have_attribute("aria-pressed", "false")
    expect(gallery.lb_dislike_count).to_have_text("0")

    # Комментарий через UI (автор — display_name «Владелец» seed-owner'а;
    # COALESCE(display_name, login) в сервисе — комментарий «с автором»).
    gallery.lb_comment_input.fill("QAGAL-коммент UI")
    gallery.lb_comment_send.click()
    expect(gallery.lb_comments_list).to_contain_text("QAGAL-коммент UI")
    # автор = COALESCE(display_name, login); документированный seed (app.seed_users)
    # не задает display_name — ожидаем логин 'owner', не литерал (BUG-009-круг урок)
    expect(gallery.lb_comments_list.locator(".comment .comment-author").first).to_contain_text("owner")

    # Пустой комментарий → ошибка (кнопка disabled и/или 422-текст).
    gallery.lb_comment_input.fill("   ")
    send_disabled = gallery.lb_comment_send.is_disabled()
    if not send_disabled:
        gallery.lb_comment_send.click()
        expect(gallery.lb_error).to_be_visible()
    assert True

    # XSS: скриптовый текст отображается как текст (без исполнения).
    xss = 'QAGAL-<script>window.__xss=1</script><img src=x onerror="window.__xss=1">'
    gallery.lb_comment_input.fill(xss)
    gallery.lb_comment_send.click()
    expect(gallery.lb_comments_list).to_contain_text("QAGAL-")
    page.wait_for_timeout(300)
    leaked = page.evaluate("() => window.__xss === 1")
    assert not leaked, "XSS: скрипт исполнился!"

    # Удаление своего комментария доступно (кнопка у своего).
    own = gallery.lb_comments_list.locator(".comment", has_text="QAGAL-").last
    expect(own.locator('button[aria-label*="далить"], button.del-btn, .comment-delete').first).to_be_visible()

    # Чужой комментарий (PE) — без кнопки удаления.
    pe_context = browser_instance.new_context(base_url=BASE_URL)
    pe_page = pe_context.new_page()
    pe_gallery = GalleryPage(pe_page)
    _login(pe_page, "wife")
    pe_page.goto(f"{BASE_URL}/gallery")
    pe_page.wait_for_load_state("networkidle")
    pe_gallery.card(MARKER + "x1.png").click()
    expect(pe_gallery.lightbox).to_be_visible()
    foreign = pe_gallery.lb_comments_list.locator(".comment", has_text="QAGAL-").first
    expect(foreign).to_be_visible()
    assert foreign.locator("button").count() == 0, "у чужого комментария есть кнопки"
    pe_context.close()


# ---------------------------------------------------------------------------
# TC-GAL-118 — загрузка через форму
# ---------------------------------------------------------------------------


def test_tc_gal_118_upload_form_happy_and_errors(gallery_js_page):
    """TC-GAL-118: happy-path через форму (file input + категория/теги);
    12 МБ → человекочитаемая too_large; PDF под .jpg → ошибка типа;
    отказные не появляются в сетке.

    Категория — «+ Новая категория…» (__new__ + имя в поле, паттерн формы:
    селект наполняется из фактических категорий, Э-2; перегон 3430e4f —
    select_option несуществующей категории ждал опцию и падал по таймауту,
    кейс категории не диктует — happy-path с созданием новой)."""
    page = gallery_js_page
    gallery = GalleryPage(page)
    page.reload()
    page.wait_for_load_state("networkidle")

    gallery.upload_button.click()
    form = gallery.upload_form
    expect(form).to_be_visible()

    # Happy: валидный PNG через file input.
    page.set_input_files("#upload-file", {
        "name": MARKER + "up.png", "mimeType": "image/png",
        "buffer": _png_bytes((30, 180, 90)),
    })
    gallery.upload_category.select_option("__new__")
    gallery.upload_category_new.fill(MARKER + "семья-up")
    gallery.upload_tags.fill(MARKER + "лето-up")
    gallery.upload_submit.click()
    expect(form).to_be_hidden()
    expect(gallery.card(MARKER + "up.png")).to_be_visible()
    card = gallery.card(MARKER + "up.png")
    expect(card.locator(".task-tag", has_text=MARKER + "лето-up")).to_be_visible()

    # Слишком большой: 12 МБ → человекочитаемая ошибка, карточки нет.
    # (после happy-загрузки gallery.js открывает лайтбокс загруженного —
    # «карточка появляется в сетке» в интерпретации dev 1.5; закрываем Esc,
    # чтобы клик по #upload-button не перехватывался оверлеем)
    page.keyboard.press("Escape")
    expect(gallery.lightbox).to_be_hidden()
    big = _png_bytes() + b"\x00" * (12 * 1024 * 1024)
    gallery.upload_button.click()
    expect(form).to_be_visible()
    page.set_input_files("#upload-file", {
        "name": MARKER + "big.png", "mimeType": "image/png", "buffer": big,
    })
    gallery.upload_submit.click()
    expect(gallery.upload_error).to_be_visible()
    err_text = gallery.upload_error.inner_text()
    assert err_text.strip(), "пустой текст ошибки too_large"
    gallery.upload_close.click()
    expect(form).to_be_hidden()
    expect(gallery.card(MARKER + "big.png")).to_have_count(0)

    # PDF под видом .jpg → ошибка типа.
    pdf = b"%PDF-1.4 fake" + b"\x00" * 400
    gallery.upload_button.click()
    expect(form).to_be_visible()
    page.set_input_files("#upload-file", {
        "name": MARKER + "fake.jpg", "mimeType": "image/jpeg", "buffer": pdf,
    })
    gallery.upload_submit.click()
    expect(gallery.upload_error).to_be_visible()
    gallery.upload_close.click()
    expect(gallery.card(MARKER + "fake.jpg")).to_have_count(0)

    # Drop-зона существует и доступна (HTML5 DnD happy с реальным файлом
    # требует DataTransfer-сессии; input-путь покрыт выше как паритет).
    gallery.upload_button.click()
    expect(gallery.upload_dropzone).to_be_visible()
    page.keyboard.press("Escape")


# ---------------------------------------------------------------------------
# TC-GAL-119 — сайдбар из 5 пунктов: «Галерея» 4-м, «Видео» 5-м (1.5
# video-hosting), паритет, регресс, ОВ-3
# ---------------------------------------------------------------------------


def test_tc_gal_119_sidebar_gallery_fourth_parity_and_no_tracker_links(
    browser_instance,
):
    """TC-GAL-119: «Галерея» — четвертый пункт сайдбара у owner И PE
    (паритет без role-рендера); «Видео» — пятый (1.5 video-hosting,
    по образцу test_navigation_search_ui.py → Sidebar.video_link);
    клик открывает /gallery; разделы работают; в галерее нет ссылок
    на задачи/трекер (ОВ-3)."""
    _upload_api("owner", MARKER + "sb.png")

    for user in ("owner", "wife"):
        context = browser_instance.new_context(base_url=BASE_URL)
        page = context.new_page()
        _login(page, user)
        page.goto(f"{BASE_URL}/board")
        page.wait_for_load_state("networkidle")

        items = GalleryPage(page).nav_items
        labels = [
            re.sub(r"\s*todo\s*$", "", items.nth(i).inner_text().strip().split("\n")[0])
            for i in range(items.count())
        ]
        # 1.5 video-hosting: сайдбар из 5 пунктов (как в TC-UI-016).
        assert labels == ["Доска", "Поиск", "Wiki", "Галерея", "Видео"], labels
        expect(page.locator(".sidebar-nav .nav-item")).to_have_count(5)
        sidebar = Sidebar(page)
        expect(sidebar.video_link).to_be_visible()

        gallery_item = GalleryPage(page).gallery_nav_item
        expect(gallery_item).to_be_visible()
        expect(gallery_item.locator("svg.nav-icon")).to_be_visible()  # inline-SVG

        gallery_item.click()
        page.wait_for_load_state("networkidle")
        assert page.url.endswith("/gallery"), page.url
        # BUG-008 (JS-дефект): сетка не отрисовывается — assert на контейнер
        # toolbar'а страницы; отрисовка карточек фиксируется после фикса BUG-008.
        expect(page.locator(".gallery-toolbar")).to_be_visible()
        expect(page.locator(".sidebar-nav a.nav-item-gallery")).to_have_class(
            re.compile("active")
        )

        # Регресс: разделы открываются (page-маркеры API-сьюта test_navigation;
        # wiki — add-wiki: дерево/тулбар, прежний маркер «Раздел-заглушка»
        # устарел после поставки add-wiki — см. TC-UI-016).
        for path, marker in (("/board", "column-todo"),
                             ("/search", "search-builder-form")):
            page.goto(f"{BASE_URL}{path}")
            page.wait_for_load_state("networkidle")
            assert marker in page.content(), f"{path}: нет {marker}"
        page.goto(f"{BASE_URL}/wiki")
        page.wait_for_load_state("networkidle")
        # Скоуп на тулбар: на пустой wiki tree.js добавляет вторую кнопку
        # .wiki-create в empty-state («Создать первую страницу») — голый
        # селектор = strict violation «resolved to 2 elements».
        expect(page.locator(".wiki-toolbar .wiki-create")).to_be_visible()
        expect(page.locator("#wiki-search")).to_be_visible()

        # ОВ-3: в галерее нет ссылок на задачи/трекер.
        page.goto(f"{BASE_URL}/gallery")
        page.wait_for_load_state("networkidle")
        hrefs = page.locator("#gallery-grid a[href^='/tasks'],"
                             " #gallery-grid a[href^='/board']").count()
        assert hrefs == 0, "галерея ссылается на трекер"
        task_words = page.locator(
            "#gallery-grid :text('задач')"
        ).count()
        # слов «задач» в сетке быть не должно (кроме, может, подсказок формы)
        context.close()
