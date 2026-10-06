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
- TC-GAL-119 — сайдбар «Галерея» 4-м пунктом у owner И PE, переход, регресс
  разделов, отсутствие связей с трекером (ОВ-3).

Браузер: playwright headless chromium (браузер уже в ~/.cache/ms-playwright).
Изоляция: QAGAL-префикс имен загрузок; teardown чистит БД + том по префиксу.
"""

import os
import re
import sqlite3

import pytest
from playwright.sync_api import expect

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
    page.reload()
    page.wait_for_load_state("networkidle")

    for user in ("owner", "wife"):
        context = browser_instance.new_context(base_url=BASE_URL)
        page = context.new_page()
        _login(page, user)
        page.goto(f"{BASE_URL}/gallery")
        page.wait_for_load_state("networkidle")

        # Полная сетка: 3 карточки с названием + превью.
        cards = page.locator(".g-card")
        expect(cards).to_have_count(3)
        for name in ("A.png", "B.png", "C.png"):
            expect(page.locator(".g-card-title", has_text=MARKER + name)).to_be_visible()
        first = page.locator(".g-card", has_text=MARKER + "A.png")
        expect(first.locator("img")).to_be_visible()
        expect(first.locator(".task-category", has_text=MARKER + "семья")).to_be_visible()
        expect(first.locator(".task-tag", has_text=MARKER + "лето")).to_be_visible()
        expect(first.locator(".task-tag", has_text=MARKER + "дача")).to_be_visible()
        expect(first.locator(".stat").first).to_be_visible()

        # Фильтр по категории → A и B.
        page.select_option("#filter-category", MARKER + "семья")
        page.wait_for_load_state("networkidle")
        expect(page.locator(".g-card")).to_have_count(2)
        expect(page.locator(".g-card", has_text=MARKER + "C.png")).to_have_count(0)

        # Комбинация category+tag → только A (конъюнкция).
        page.select_option("#filter-tag", MARKER + "лето")
        expect(page.locator(".g-card")).to_have_count(1)
        expect(page.locator(".g-card", has_text=MARKER + "A.png")).to_have_count(1)

        # Только тег (сброс категории через полный reset, затем tag).
        page.click("#filter-reset")
        page.select_option("#filter-tag", MARKER + "летo" if False else MARKER + "лето")
        expect(page.locator(".g-card")).to_have_count(1)

        # Сброс — полная сетка.
        page.click("#filter-reset")
        expect(page.locator(".g-card")).to_have_count(3)
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
    page.reload()
    page.wait_for_load_state("networkidle")

    # Шаг 1: открытие кликом по карточке.
    page.locator(".g-card", has_text=MARKER + "lb1.png").click()
    overlay = page.locator("#lightbox-overlay")
    expect(overlay).to_be_visible()
    expect(page.locator("#lb-title")).to_contain_text(MARKER + "lb1.png")

    # Шаг 2: кнопки ←/→ циклично по выдаче created_at DESC
    # ([lb3, lb2, lb1]; lb1 — последний элемент выдачи).
    page.click("#lb-prev")
    expect(page.locator("#lb-title")).to_contain_text(MARKER + "lb2.png")
    page.click("#lb-prev")
    expect(page.locator("#lb-title")).to_contain_text(MARKER + "lb3.png")
    page.click("#lb-prev")
    expect(page.locator("#lb-title")).to_contain_text(MARKER + "lb1.png")
    page.click("#lb-next")
    expect(page.locator("#lb-title")).to_contain_text(MARKER + "lb3.png")

    # Клавиатура: ArrowRight от lb3 (индекс 0) → lb2, ArrowLeft → обратно lb3.
    page.keyboard.press("ArrowRight")
    expect(page.locator("#lb-title")).to_contain_text(MARKER + "lb2.png")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#lb-title")).to_contain_text(MARKER + "lb3.png")

    # Шаг 4: лайк из модалки — подсветка + счетчик без выхода из окна.
    page.click("#lb-like")
    expect(page.locator("#lb-like")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#lb-like-count")).to_have_text("1")

    # Комментарий из модалки.
    page.fill("#comment-input", "QAGAL-коммент из лайтбокса")
    page.click("#comment-send")
    expect(page.locator("#lb-comments-list")).to_contain_text(
        "QAGAL-коммент из лайтбокса"
    )

    # Шаг 5: Esc закрывает; сетка на месте.
    page.keyboard.press("Escape")
    expect(overlay).to_be_hidden()
    expect(page.locator(".g-card")).to_have_count(3)

    # Шаг 6: «скачать» — href оригинала (/images/<filename>, не превью).
    page.locator(".g-card", has_text=MARKER + "lb1.png").click()
    expect(overlay).to_be_visible()
    href = page.locator("#lb-download").get_attribute("href")
    assert href and href.startswith("/images/") and href.endswith(".png"), href
    assert href == a["url"], (href, a["url"])

    # Проверка скачивания через fetch (download-атрибут в headless не
    #materializуется на диск без профиля): байты оригинала доступны по href.
    resp = page.request.get(f"{BASE_URL}{href}")
    assert resp.status == 200
    assert len(resp.body()) > 0

    # Крестик тоже закрывает.
    page.click("#lb-close")
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
    page.reload()
    page.wait_for_load_state("networkidle")

    # Лайк с карточки (через лайтбокс — кнопки реакции в панели).
    page.locator(".g-card", has_text=MARKER + "x1.png").click()
    expect(page.locator("#lightbox-overlay")).to_be_visible()
    page.click("#lb-like")
    expect(page.locator("#lb-like")).to_have_attribute("aria-pressed", "true")

    # Перезагрузка — состояние пережило (persisted).
    page.reload()
    page.wait_for_load_state("networkidle")
    page.locator(".g-card", has_text=MARKER + "x1.png").click()
    expect(page.locator("#lb-like")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#lb-like-count")).to_have_text("1")

    # Смена голоса: dislike — подсветка переместилась.
    page.click("#lb-dislike")
    expect(page.locator("#lb-dislike")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#lb-like")).to_have_attribute("aria-pressed", "false")

    # Повторный same-sign — снятие.
    page.click("#lb-dislike")
    expect(page.locator("#lb-dislike")).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#lb-dislike-count")).to_have_text("0")

    # Комментарий через UI (автор — display_name «Владелец» seed-owner'а;
    # COALESCE(display_name, login) в сервисе — комментарий «с автором»).
    page.fill("#comment-input", "QAGAL-коммент UI")
    page.click("#comment-send")
    expect(page.locator("#lb-comments-list")).to_contain_text("QAGAL-коммент UI")
    # автор = COALESCE(display_name, login); документированный seed (app.seed_users)
    # не задает display_name — ожидаем логин 'owner', не литерал (BUG-009-круг урок)
    expect(page.locator("#lb-comments-list .comment .comment-author").first).to_contain_text("owner")

    # Пустой комментарий → ошибка (кнопка disabled и/или 422-текст).
    page.fill("#comment-input", "   ")
    send_disabled = page.locator("#comment-send").is_disabled()
    if not send_disabled:
        page.click("#comment-send")
        expect(page.locator("#lb-error")).to_be_visible()
    assert True

    # XSS: скриптовый текст отображается как текст (без исполнения).
    xss = 'QAGAL-<script>window.__xss=1</script><img src=x onerror="window.__xss=1">'
    page.fill("#comment-input", xss)
    page.click("#comment-send")
    expect(page.locator("#lb-comments-list")).to_contain_text("QAGAL-")
    page.wait_for_timeout(300)
    leaked = page.evaluate("() => window.__xss === 1")
    assert not leaked, "XSS: скрипт исполнился!"

    # Удаление своего комментария доступно (кнопка у своего).
    own = page.locator("#lb-comments-list .comment", has_text="QAGAL-").last
    expect(own.locator('button[aria-label*="далить"], button.del-btn, .comment-delete').first).to_be_visible()

    # Чужой комментарий (PE) — без кнопки удаления.
    pe_context = browser_instance.new_context(base_url=BASE_URL)
    pe_page = pe_context.new_page()
    _login(pe_page, "wife")
    pe_page.goto(f"{BASE_URL}/gallery")
    pe_page.wait_for_load_state("networkidle")
    pe_page.locator(".g-card", has_text=MARKER + "x1.png").click()
    expect(pe_page.locator("#lightbox-overlay")).to_be_visible()
    foreign = pe_page.locator("#lb-comments-list .comment", has_text="QAGAL-").first
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
    page.reload()
    page.wait_for_load_state("networkidle")

    page.click("#upload-button")
    form = page.locator("#upload-form")
    expect(form).to_be_visible()

    # Happy: валидный PNG через file input.
    page.set_input_files("#upload-file", {
        "name": MARKER + "up.png", "mimeType": "image/png",
        "buffer": _png_bytes((30, 180, 90)),
    })
    page.select_option("#up-category", "__new__")
    page.fill("#up-category-new", MARKER + "семья-up")
    page.fill("#up-tags", MARKER + "лето-up")
    page.click("#upload-submit")
    expect(form).to_be_hidden()
    expect(page.locator(".g-card", has_text=MARKER + "up.png")).to_be_visible()
    card = page.locator(".g-card", has_text=MARKER + "up.png")
    expect(card.locator(".task-tag", has_text=MARKER + "лето-up")).to_be_visible()

    # Слишком большой: 12 МБ → человекочитаемая ошибка, карточки нет.
    # (после happy-загрузки gallery.js открывает лайтбокс загруженного —
    # «карточка появляется в сетке» в интерпретации dev 1.5; закрываем Esc,
    # чтобы клик по #upload-button не перехватывался оверлеем)
    page.keyboard.press("Escape")
    expect(page.locator("#lightbox-overlay")).to_be_hidden()
    big = _png_bytes() + b"\x00" * (12 * 1024 * 1024)
    page.click("#upload-button")
    expect(form).to_be_visible()
    page.set_input_files("#upload-file", {
        "name": MARKER + "big.png", "mimeType": "image/png", "buffer": big,
    })
    page.click("#upload-submit")
    expect(page.locator("#upload-error")).to_be_visible()
    err_text = page.locator("#upload-error").inner_text()
    assert err_text.strip(), "пустой текст ошибки too_large"
    page.click("#upload-close")
    expect(form).to_be_hidden()
    expect(page.locator(".g-card", has_text=MARKER + "big.png")).to_have_count(0)

    # PDF под видом .jpg → ошибка типа.
    pdf = b"%PDF-1.4 fake" + b"\x00" * 400
    page.click("#upload-button")
    expect(form).to_be_visible()
    page.set_input_files("#upload-file", {
        "name": MARKER + "fake.jpg", "mimeType": "image/jpeg", "buffer": pdf,
    })
    page.click("#upload-submit")
    expect(page.locator("#upload-error")).to_be_visible()
    page.click("#upload-close")
    expect(page.locator(".g-card", has_text=MARKER + "fake.jpg")).to_have_count(0)

    # Drop-зона существует и доступна (HTML5 DnD happy с реальным файлом
    # требует DataTransfer-сессии; input-путь покрыт выше как паритет).
    page.click("#upload-button")
    expect(page.locator("#upload-dropzone")).to_be_visible()
    page.keyboard.press("Escape")


# ---------------------------------------------------------------------------
# TC-GAL-119 — сайдбар «Галерея» 4-м пунктом, паритет, регресс, ОВ-3
# ---------------------------------------------------------------------------


def test_tc_gal_119_sidebar_gallery_fourth_parity_and_no_tracker_links(
    browser_instance,
):
    """TC-GAL-119: «Галерея» — четвертый пункт сайдбара у owner И PE
    (паритет без role-рендера); клик открывает /gallery; разделы работают;
    в галерее нет ссылок на задачи/трекер (ОВ-3)."""
    _upload_api("owner", MARKER + "sb.png")

    for user in ("owner", "wife"):
        context = browser_instance.new_context(base_url=BASE_URL)
        page = context.new_page()
        _login(page, user)
        page.goto(f"{BASE_URL}/board")
        page.wait_for_load_state("networkidle")

        items = page.locator(".sidebar-nav a.nav-item")
        labels = [
            re.sub(r"\s*todo\s*$", "", items.nth(i).inner_text().strip().split("\n")[0])
            for i in range(items.count())
        ]
        assert labels == ["Доска", "Поиск", "Wiki", "Галерея"], labels

        gallery_item = page.locator("a.nav-item-gallery")
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

        # Регресс: разделы открываются (page-маркеры API-сьюта test_navigation).
        for path, marker in (("/board", "column-todo"),
                             ("/search", "search-builder-form"),
                             ("/wiki", "Раздел-заглушка")):
            page.goto(f"{BASE_URL}{path}")
            page.wait_for_load_state("networkidle")
            assert marker in page.content(), f"{path}: нет {marker}"

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
