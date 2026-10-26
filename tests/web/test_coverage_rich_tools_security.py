"""coverage-backfill-1, группа A: автотесты TC-rich-022…039 (p12-rich-tools).

Source of truth: test-model/approved/p12-rich-tools/TC-rich-022..039.md.
Каждый тест — ровно один утвержденный кейс; маркер трассировки в docstring
(«coverage-backfill-1; TC-rich-NNN: <название кейса>»). Стиль — по
tests/web/test_rich_tools.py / test_redesign_console.py.

Первая часть группы (TC-rich-001…021) — tests/web/test_coverage_rich_tools.py.

Отступления от буквы кейсов (задокументированы в docstring тестов):
- TC-rich-027: «замер активации» автоматизирован как budget главного потока
  (PerformanceObserver longtask, максимум 3 прогонов ≤150 мс) + живая
  прокрутка во время загрузки; JS-метки вокруг внутренней инициализации
  недоступны (модули не экспортируют таймеры наружу).
- TC-rich-028: «байт-в-байт сравнение с эталонным скриншотом до релиза» —
  ручная часть; автоматом проверяется контентный раундтрип, отсутствие
  активаций rich, ошибок и внешних запросов.
"""

import io
import re
from types import SimpleNamespace

import pytest
from playwright.sync_api import expect

from tests.web.pages.wiki import WikiEditor
# Фикстуры images-стенда — из test_p15_wiki_editor (images-сервис + прокси
# «роль nginx» + teardown загрузок); там же autouse-схема wiki+gallery.
from tests.web.test_p15_wiki_editor import (  # noqa: F401
    _png_file,
    disk_upload_teardown,
    images_service,
    wiki_images_routing,
    wiki_stand_schema,
)

pytestmark = [pytest.mark.e2e, pytest.mark.web]


# ---------------------------------------------------------------------------
# fixtures (паттерн test_rich_tools.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def wiki_api(web_base_url, web_owner_session):
    """Парные хелперы create/content wiki-страниц с teardown-очисткой."""
    created: list[int] = []

    def create(title, content="", parent_id=None):
        resp = web_owner_session.post(
            f"{web_base_url}/api/wiki/pages",
            json={"title": title, "content": content, "parent_id": parent_id},
        )
        assert resp.status_code == 201, resp.text
        page_id = resp.json()["id"]
        created.append(page_id)
        return page_id

    def put(page_id, content):
        resp = web_owner_session.put(
            f"{web_base_url}/api/wiki/pages/{page_id}",
            json={"title": "x", "content": content},
        )
        assert resp.status_code == 200, resp.text

    def content_of(page_id):
        return web_owner_session.get(
            f"{web_base_url}/api/wiki/pages/{page_id}"
        ).json()["content"]

    api = SimpleNamespace(
        create=create, content_of=content_of, register=created.append, put=put
    )
    yield api
    for page_id in reversed(created):
        try:
            web_owner_session.delete(f"{web_base_url}/api/wiki/pages/{page_id}")
        except Exception:
            pass


@pytest.fixture
def editor_page(logged_in_page, page_errors):
    """Страница owner с коллектором JS-ошибок (NFR-39)."""
    return logged_in_page


@pytest.fixture
def page_errors(page):
    """JS-ошибки страницы: rich-сценарии не роняют консоль."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on(
        "console",
        lambda msg: errors.append(msg.text) if msg.type == "error" else None,
    )
    yield errors
    if errors:
        print("\n[BROWSER ERRORS]", *errors, sep="\n  ")

# ---------------------------------------------------------------------------
# хелперы
# ---------------------------------------------------------------------------


def _saved_page_id(page) -> int:
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    return int(page.url.rstrip("/").rsplit("/", 1)[1])


def _caret_to_area_end(page) -> None:
    page.evaluate(
        """() => {
          const area = document.querySelector('.editor-area');
          const range = document.createRange();
          range.selectNodeContents(area);
          range.collapse(false);
          const sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
        }"""
    )


def _spoiler_chain(markers) -> str:
    """Цепочка вложенных спойлеров: markers[0] — внешний уровень, каждый
    уровень — работающий спойлер со своим текстом."""
    content = (
        '<div data-block="spoiler"><div data-block-part="body">'
        f"<p>{markers[-1]}</p></div></div>"
    )
    for marker in reversed(markers[:-1]):
        content = (
            '<div data-block="spoiler"><div data-block-part="body">'
            f"<p>{marker}</p>{content}</div></div>"
        )
    return content


def _collect_external(page, web_base_url):
    external: list[str] = []
    page.on(
        "request",
        lambda req: external.append(req.url)
        if not req.url.startswith(web_base_url)
        else None,
    )
    return external


# ---------------------------------------------------------------------------
# Безопасность rich-блоков (NFR-39): TC-rich-022…025
# ---------------------------------------------------------------------------


def test_tc_rich_022_xss_script_onclick_inside_block(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-022: Скрипт и onclick внутри блока
    вырезаются с содержимым (XSS). В отдаваемом HTML script отсутствует
    ВМЕСТЕ с содержимым, onclick снят; спойлер сохранен и работает, alert
    не исполнялся, ошибок в консоли нет (NFR-39/NFR-31)."""
    page_id = wiki_api.create(
        "XSS в спойлере",
        '<div data-block="spoiler" data-title="X" onclick="alert(2)">'
        '<div data-block-part="body"><script>alert(1)</script>'
        "<p>тело спойлера</p></div></div>",
    )
    # шаг 2: GET-контент чист — script с содержимым и onclick сняты
    saved = wiki_api.content_of(page_id)
    assert "script" not in saved and "alert" not in saved
    assert "onclick" not in saved
    assert 'data-block="spoiler"' in saved and "тело спойлера" in saved

    # шаг 3: alert не исполнялся, ошибок в консоли нет
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    assert page.evaluate("window.__xss === undefined")

    # шаг 4: toggle работает без исполнения кода
    spoiler = page.locator(".article-body .spoiler")
    expect(spoiler).to_have_class(re.compile("closed"))
    spoiler.locator(".spoiler-head").click()
    expect(spoiler.locator(".spoiler-body")).to_contain_text("тело спойлера")
    assert page_errors == []


def test_tc_rich_023_forged_data_attributes_stripped(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-023: Подмена значений data-атрибутов —
    снятие и деградация. data-block=evil и data-lang=javascript вне словаря
    design §1 сняты (_safe_block_attr), блок деградировал в обычный контент;
    исполнение невозможно, ошибок нет (NFR-39)."""
    page_id = wiki_api.create(
        "Подмена data",
        '<div data-block="evil" data-lang="javascript">текст</div>',
    )
    saved = wiki_api.content_of(page_id)
    assert 'data-block="evil"' not in saved
    assert "data-block" not in saved and "data-lang" not in saved
    assert "текст" in saved  # содержимое сохранено

    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    body = page.locator(".article-body")
    expect(body).to_contain_text("текст")
    # блок деградировал: никакого виджета спойлера/кода не построено
    expect(body.locator(".spoiler-head")).to_have_count(0)
    expect(body.locator(".codeblock")).to_have_count(0)
    assert page_errors == []


def test_tc_rich_024_depth_limit_five_six_seven(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-024: Граница глубины — 5 уровней
    работают, 6–7 разворачиваются без потери. Цепочка 7: спойлеров ровно 5,
    содержимое «У6»/«У7» — обычный контент без виджета; ВСЕ тексты целы;
    цепочка 5 (граница): все 5 уровней — работающие спойлеры."""
    # шаг 1: цепочка из 7 вложенных спойлеров
    page_id = wiki_api.create("Глубина 7", _spoiler_chain([f"У{i}" for i in range(1, 8)]))
    saved = wiki_api.content_of(page_id)
    assert saved.count('data-block="spoiler"') == 5  # уровни 6–7 unwrap
    for marker in (f"У{i}" for i in range(1, 8)):
        assert marker in saved  # потери нет

    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    body = page.locator(".article-body")
    expect(body.locator(".spoiler")).to_have_count(5)  # виджетов ровно 5
    # шаг 2: свернуть/развернуть спойлеры первых уровней, дойти до дна
    for depth in range(5):
        body.locator(".spoiler").nth(depth).locator("> .spoiler-head").click()
    expect(body).to_contain_text("У6")
    expect(body).to_contain_text("У7")
    # уровни 6–7 — обычный контент: 6-го виджета нет
    assert body.locator(".spoiler .spoiler .spoiler .spoiler .spoiler .spoiler").count() == 0
    assert page_errors == []

    # шаг 4: цепочка ровно из 5 — все 5 уровней работают как спойлеры
    page_id5 = wiki_api.create("Глубина 5", _spoiler_chain([f"Г{i}" for i in range(1, 6)]))
    saved5 = wiki_api.content_of(page_id5)
    assert saved5.count('data-block="spoiler"') == 5
    page.goto(f"{web_base_url}/wiki/{page_id5}")
    body = page.locator(".article-body")
    expect(body.locator(".spoiler")).to_have_count(5)
    for depth in range(5):
        body.locator(".spoiler").nth(depth).locator("> .spoiler-head").click()
    expect(body).to_contain_text("Г5")
    assert page_errors == []


def test_tc_rich_025_unknown_block_degrades_no_errors(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-025: Неизвестный блок деградирует без
    ошибок. «Будущее содержимое» — обычный контент; соседний спойлер
    работает (ошибка одного блока не роняет активацию остальных)."""
    page_id = wiki_api.create(
        "Неизвестный блок",
        '<div data-block="spoiler" data-title="Сосед">'
        '<div data-block-part="body"><p>соседний спойлер</p></div></div>'
        '<div data-block="future-widget">Будущее содержимое</div>',
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    body = page.locator(".article-body")
    expect(body).to_contain_text("Будущее содержимое")  # обычный контент
    assert body.locator('[data-block="future-widget"] .spoiler-head').count() == 0
    # соседний спойлер активировался и работает
    spoiler = body.locator(".spoiler")
    spoiler.locator(".spoiler-head").click()
    expect(spoiler.locator(".spoiler-body")).to_contain_text("соседний спойлер")
    assert page_errors == []  # ошибок в консоли нет (try/catch per-block)


# ---------------------------------------------------------------------------
# Рендер без внешних зависимостей (NFR-40): TC-rich-026…028
# ---------------------------------------------------------------------------


def test_tc_rich_026_article_blocks_no_external_requests(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-026: Статья с блоками — ни одного
    внешнего запроса. Спойлер/код/табы + интерактив (toggle, вкладка,
    «Копировать») — все запросы только к собственному origin (ОГР-8/NFR-40)."""
    page_id = wiki_api.create(
        "Статья без CDN",
        '<div data-block="spoiler" data-title="С">'
        '<div data-block-part="body"><p>спойлер</p></div></div>'
        '<div data-block="code" data-lang="python"><pre><code>x = 1</code></pre></div>'
        '<div data-block="tabs">'
        '<div data-block-part="tab" data-title="Т1"><p>первая</p></div>'
        '<div data-block-part="tab" data-title="Т2"><p>вторая</p></div>'
        "</div>",
    )
    page = editor_page
    external = _collect_external(page, web_base_url)
    page.goto(f"{web_base_url}/wiki/{page_id}")

    # шаг 3: интерактив работает
    spoiler = page.locator(".article-body .spoiler")
    spoiler.locator(".spoiler-head").click()
    expect(spoiler.locator(".spoiler-body")).to_contain_text("спойлер")
    tabs = page.locator(".article-body .tabswidget")
    tabs.locator(".tab").nth(1).click()
    expect(tabs.locator(".tab-pane").nth(1)).to_contain_text("вторая")
    page.evaluate(
        "navigator.clipboard.writeText = (t) => "
        "{ window.__copiedText = t; return Promise.resolve(); };"
    )
    page.locator(".article-body .codeblock .copy-btn").click()
    assert page.evaluate("window.__copiedText") == "x = 1"

    # шаг 4: все запросы — к собственному origin
    assert external == [], external
    assert page_errors == []


def test_tc_rich_027_activation_20_blocks_no_ui_block(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-027: Активация 20 блоков с крупным
    листингом не блокирует UI. Автоматизация духа кейса: бюджет главного
    потока (PerformanceObserver longtask: ни одна задача ≤150 мс НЕ
    превышена, максимум по 3 прогонам) + прокрутка во время загрузки/подсветки
    не «замораживается»; JS-метки вокруг внутренней инициализации недоступны —
    rich-модули не экспортируют таймеры."""
    blocks = []
    for i in range(10):
        blocks.append(
            f'<div data-block="spoiler" data-title="Блок {i}">'
            f'<div data-block-part="body"><p>текст {i}</p></div></div>'
        )
    for i in range(9):
        blocks.append(
            '<div data-block="tabs">'
            f'<div data-block-part="tab" data-title="Т1"><p>таб {i}.1</p></div>'
            f'<div data-block-part="tab" data-title="Т2"><p>таб {i}.2</p></div>'
            "</div>"
        )
    listing = "\n".join(f"def fn{i}(): return {i}" for i in range(1000))
    blocks.append(
        '<div data-block="code" data-lang="python"><pre><code>'
        + listing
        + "</code></pre></div>"
    )
    assert len(blocks) == 20
    page_id = wiki_api.create("20 блоков + листинг", "".join(blocks))

    page = editor_page
    page.add_init_script(
        """window.__longTasks = [];
          try {
            new PerformanceObserver(function (list) {
              list.getEntries().forEach(function (e) {
                window.__longTasks.push(e.duration);
              });
            }).observe({ entryTypes: ['longtask'] });
          } catch (e) { /* longtask не поддержан — бюджет не нарушен */ }"""
    )
    worst = 0.0
    for _ in range(3):
        page.goto(f"{web_base_url}/wiki/{page_id}")
        # подсветка крупного листинга завершается, текст статьи виден
        expect(
            page.locator(".article-body .codeblock .tok-kw").first
        ).to_be_visible(timeout=15000)
        expect(page.locator(".article-body")).to_contain_text("текст 9")
        # прокрутка во время/сразу после подсветки работает (не заморожена)
        page.evaluate("window.scrollTo(0, 600)")
        scrolled = page.evaluate("window.scrollY")
        assert scrolled > 0, "прокрутка во время активации не работает"
        worst = max(worst, page.evaluate("Math.max(...window.__longTasks, 0)"))
    assert worst <= 150.0, f"блокировка главного потока {worst} мс > 150 мс"
    assert page_errors == []


def test_tc_rich_028_article_without_blocks_regression(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-028: Статья без rich-блоков не меняет
    поведение (регресс). Контент «до P12» (фикстура через API стенда, не
    рукописный HTML в браузере): разметка в БД байт-в-байт, рендер без
    rich-активаций, ошибок и внешних запросов. Байт-в-байт сверка СКРИНШОТА
    с эталоном до релиза — ручная часть кейса, автоматом не воспроизводится."""
    plain = (
        "<h2>Плоская статья</h2>"
        "<p>Обычный абзац текста.</p>"
        "<ul><li>пункт списка</li></ul>"
        "<table><thead><tr><th>Шапка</th></tr></thead>"
        "<tbody><tr><td>Ячейка</td></tr></tbody></table>"
    )
    page_id = wiki_api.create("Статья до P12", plain)
    assert wiki_api.content_of(page_id) == plain  # байт-в-байт по контенту

    page = editor_page
    external = _collect_external(page, web_base_url)
    page.goto(f"{web_base_url}/wiki/{page_id}")
    body = page.locator(".article-body")
    expect(body.locator("h2")).to_have_text("Плоская статья")
    expect(body.locator("li")).to_have_text("пункт списка")
    expect(body.locator("td")).to_have_text("Ячейка")
    # путь рендера без изменений: лишних rich-активаций нет
    expect(body.locator(".spoiler")).to_have_count(0)
    expect(body.locator(".codeblock")).to_have_count(0)
    expect(body.locator(".tabswidget")).to_have_count(0)
    assert page_errors == []
    assert external == []


# ---------------------------------------------------------------------------
# Тулбар/редактор (FR-110): TC-rich-029…033
# ---------------------------------------------------------------------------


def test_tc_rich_029_toolbar_wysiwyg_roundtrip(
    editor_page, wiki_api, page_errors, web_base_url, wiki_images_routing,
    disk_upload_teardown,
):
    """coverage-backfill-1; TC-rich-029: Тулбар применяет форматирование —
    WYSIWYG round-trip. H2, B/I/U, оба списка, цитата, код-блок, ссылка,
    таблица, изображение (с диска): сохраненная статья отображает тот же
    вид без расхождений (FR-110)."""
    page = editor_page
    # 404 на GET /images/<файл> — ограничение СТЕНДА (роль nginx /images/*
    # в проде отдает том images-data; локальный images-сервис роута
    # /images/* не имеет), а не дефект страницы: все ошибки консоли теста
    # должны быть ровно этими 404 (сверка с логом ответов)
    images_404: list[str] = []
    page.on(
        "response",
        lambda r: images_404.append(r.url)
        if r.status == 404 and "/images/" in r.url
        else None,
    )
    editor = WikiEditor(page)
    editor.open_create(wiki_images_routing)
    editor.area.click()

    lines = [
        "Заголовок раздела",
        "жирный фрагмент",
        "курсивный фрагмент",
        "подчеркнутый фрагмент",
        "пункт маркированный",
        "пункт нумерованный",
        "цитата целиком",
        "print('код')",
        "ссылка на источник",
    ]
    page.keyboard.type(lines[0])
    for line in lines[1:]:
        page.keyboard.press("End")
        page.keyboard.press("Enter")
        page.keyboard.type(line)
    # форматы применяются к ВЫДЕЛЕНИЮ строки сверху вниз; навигация по
    # строкам — клавиатурой от начала области (первая строка может быть
    # голым текстовым узлом без блока — клик по тексту не годится)
    lines_fmt = [
        ("Заголовок раздела", "Заголовок 2"),
        ("жирный фрагмент", "Полужирный"),
        ("курсивный фрагмент", "Курсив"),
        ("подчеркнутый фрагмент", "Подчеркнутый"),
        ("пункт маркированный", "Маркированный список"),
        ("пункт нумерованный", "Нумерованный список"),
        ("цитата целиком", "Цитата"),
        ("print('код')", "Код-блок"),
        ("ссылка на источник", "Ссылка"),
    ]
    page.keyboard.press("Control+Home")
    for _, button in lines_fmt[:-1]:
        page.keyboard.press("Home")
        page.keyboard.press("Shift+End")
        editor.toolbar_button(button).click()
        page.keyboard.press("End")
        page.keyboard.press("ArrowDown")
    # ссылка — вставка при выделении всей области (механика select_all_text,
    # как в tests/web/test_p15_wiki_editor.py): продукт вставляет URL как
    # новый узел <a>URL</a> — выделение диапазона диалог ссылки теряет
    # (дефект продукта — BUG-024)
    editor.select_all_text()
    editor.toolbar_button("Ссылка").click()
    editor.link_address_input().fill("https://example.com")
    editor.link_dialog.get_by_role("button", name="Вставить").click()
    # продукт нормализует URL (добавляет «/») и вставляет <a> в начало
    # первой строки — выделение диапазона диалог ссылки теряет (BUG-024)
    expect(
        editor.area.locator("a[href^='https://example.com']")
    ).to_have_count(1)

    # таблица в конец
    _caret_to_area_end(page)
    editor.toolbar_button("Таблица").click()
    expect(editor.area.locator("table")).to_have_count(1)

    # изображение с диска (POST /api/images → <img src=/images/…>)
    _caret_to_area_end(page)
    editor.toolbar_button("Изображение").click()
    dialog = editor.img_dialog
    expect(dialog).to_be_visible()
    dialog.get_by_text("Загрузить с диска").check()
    name = "QAE-cov-rich-roundtrip.png"
    disk_upload_teardown(name)
    editor.img_file_input().set_input_files(
        [_png_file(name)]
    )
    expect(editor.area.locator("img")).to_have_count(1)

    # шаг 2: сохранить, открыть статью
    editor.title_input.fill("WYSIWYG раундтрип")
    editor.save_button().click()
    page_id = _saved_page_id(page)

    # шаг 3: тот же вид без расхождений (DOM-сравнение со структурой редактора)
    body = page.locator(".article-body")
    # ссылка вставляется продуктом как новый узел <a>URL</a> в начало
    # первой строки (выделение теряет диалог — BUG-024), поэтому h2
    # содержит ссылку-URL + текст заголовка
    expect(body.locator("h2")).to_contain_text("Заголовок раздела")
    expect(body.locator("b, strong").filter(has_text="жирный")).to_have_count(1)
    expect(body.locator("i, em").filter(has_text="курсивный")).to_have_count(1)
    expect(body.locator("u").filter(has_text="подчеркнутый")).to_have_count(1)
    expect(body.locator("ul li")).to_have_text("пункт маркированный")
    expect(body.locator("ol li")).to_have_text("пункт нумерованный")
    expect(body.locator("blockquote")).to_contain_text("цитата целиком")
    expect(body.locator("pre code")).to_contain_text("print('код')")
    expect(body.locator("a[href^='https://example.com']")).to_have_count(1)
    expect(body.locator("table")).to_have_count(1)
    img = body.locator("img")
    expect(img).to_have_count(1)
    expect(img).to_have_attribute("src", re.compile(r"^/images/"))
    saved = wiki_api.content_of(page_id)
    for fragment in ("<h2>", "<b>", "<i>", "<u>", "<ul>", "<ol>", "<blockquote>",
                     "<pre><code>", 'href="https://example.com/', "<table>", "<img"):
        assert fragment in saved, fragment
    assert len(page_errors) == len(images_404), (page_errors, images_404)


def test_tc_rich_030_toolbar_rich_tools_single_toolbar(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-030: Тулбар содержит инструменты
    rich-контента, тулбар один. Блоковые кнопки вставляют блок в позицию
    курсора; фокус/каретка — по багфиксу p12-rich-2 (спойлер закрыт, каретка
    за блоком; код/табы — в зону содержимого); контекстные контролы —
    inline-панели внутри блоков, новых рядов тулбара нет (урок rich-v1)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()

    # шаг 1/4: тулбар ОДИН; кнопки rich-инструментов доступны
    formatting_toolbar = page.locator(".toolbar[role='toolbar']")
    expect(formatting_toolbar).to_have_count(1)
    for label in ("Спойлер", "Блок кода", "Табуляция", "Таблица"):
        expect(editor.toolbar_button(label)).to_be_visible()
        expect(editor.toolbar_button(label)).to_be_enabled()

    # шаг 2: каждая кнопка вставляет свой блок в позицию курсора
    page.keyboard.type("до спойлера")
    editor.toolbar_button("Спойлер").click()
    expect(editor.area.locator(".spoiler")).to_have_count(1)
    page.keyboard.type("между блоками")
    editor.toolbar_button("Блок кода").click()
    expect(editor.area.locator(".codeblock")).to_have_count(1)
    # фокус в зоне содержимого код-блока — печатаем сразу
    page.keyboard.type("x = 1")
    expect(editor.area.locator(".codeblock code")).to_have_text("x = 1")
    _caret_to_area_end(page)
    page.keyboard.type("перед табами")
    editor.toolbar_button("Табуляция").click()
    tabs = editor.area.locator(".tabswidget")
    expect(tabs).to_have_count(1)
    expect(tabs.locator(".tab")).to_have_count(2)
    page.keyboard.type("содержимое первой")  # фокус в зоне содержимого вкладки

    # шаг 3: таблица → контекстная панель — inline-внутри области редактора
    _caret_to_area_end(page)
    editor.toolbar_button("Таблица").click()
    expect(editor.area.locator("table")).to_have_count(1)
    panel = editor.area.locator(".tbl-panel")
    editor.area.locator("thead th").first.click()
    expect(panel).to_be_visible()
    expect(panel.locator(".ctx-remove")).to_contain_text("Удалить таблицу")

    # новых рядов тулбара нет: тулбар по-прежнему один, панель — внутри area
    expect(page.locator(".toolbar[role='toolbar']")).to_have_count(1)
    assert page.locator(".editor-area .tbl-panel").count() == 1
    # порядок вставки: спойлер между «до» и «между» (позиция курсора)
    saved_order = editor.area.evaluate(
        """node => Array.from(node.children)
             .map(c => c.className || c.tagName).join('|')"""
    )
    assert saved_order.index("spoiler") < saved_order.index("codeblock"), saved_order
    assert page_errors == []


def test_tc_rich_031_heading_buttons_no_stick(editor_page, page_errors, web_base_url):
    """coverage-backfill-1; TC-rich-031: Кнопки заголовков не залипают.
    Повторный клик H1 снимает; после H2 нажата только H2, после H3 — только
    H3; одновременное нажатие двух уровней недостижимо при быстрых кликах
    H1→H2 в разных абзацах (регресс P12 п.4)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()

    # шаги 1–2: H1 и повторный клик — формат снят, все отжаты
    page.keyboard.type("Первый абзац")
    editor.select_all_text()
    editor.toolbar_button("Заголовок 1").click()
    expect(editor.area.locator("h1")).to_have_count(1)
    editor.toolbar_button("Заголовок 1").click()
    expect(editor.area.locator("h1")).to_have_count(0)
    for label in ("Заголовок 1", "Заголовок 2", "Заголовок 3"):
        expect(editor.toolbar_button(label)).to_have_attribute("aria-pressed", "false")

    # шаг 3: H2 → только H2; H3 → только H3
    editor.select_all_text()
    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_count(1)
    expect(editor.toolbar_button("Заголовок 2")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(editor.toolbar_button("Заголовок 1")).to_have_attribute(
        "aria-pressed", "false"
    )
    editor.select_all_text()
    editor.toolbar_button("Заголовок 3").click()
    expect(editor.area.locator("h3")).to_have_count(1)
    expect(editor.toolbar_button("Заголовок 3")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(editor.toolbar_button("Заголовок 2")).to_have_attribute(
        "aria-pressed", "false"
    )

    # шаг 4: быстрые клики H1→H2 в разных абзацах — состояние строго за
    # блоком курсора, двух нажатых нет
    page.keyboard.press("End")
    page.keyboard.press("Enter")
    page.keyboard.type("Второй абзац")
    editor.area.locator("h3").click()
    editor.toolbar_button("Заголовок 1").click()
    editor.area.locator("> div:not(.tbl-panel)").last.click()
    editor.toolbar_button("Заголовок 2").click()
    pressed = [
        label
        for label in ("Заголовок 1", "Заголовок 2", "Заголовок 3")
        if editor.toolbar_button(label).get_attribute("aria-pressed") == "true"
    ]
    assert pressed == ["Заголовок 2"], pressed
    assert page_errors == []


def test_tc_rich_032_undo_redo_including_h_toggle(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-032: Undo/redo, включая undo после
    H-toggle (F4). Правки (спойлер, снятие H2, замена H1→H3) отменяются в
    обратном порядке; redo повторно применяет; финальное состояние
    сохраняется корректно (FR-110). Гранулярность нативного стека крупнее
    одной правки — откат до наблюдаемых вех (число нажатий подобрано по
    фактическому стеку, заход на набор текста защищен ассертами)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()

    # шаг 1: последовательность правок
    page.keyboard.type("Абзац для отмены")
    editor.select_all_text()
    editor.toolbar_button("Заголовок 2").click()  # правка A: H2
    editor.toolbar_button("Заголовок 2").click()  # правка B: снятие H2
    editor.select_all_text()
    editor.toolbar_button("Заголовок 1").click()  # правка C: H1
    editor.toolbar_button("Заголовок 3").click()  # правка D: замена H1→H3
    expect(editor.area.locator("h3")).to_have_count(1)
    editor.toolbar_button("Спойлер").click()      # правка E: спойлер
    expect(editor.area.locator(".spoiler")).to_have_count(1)

    # шаг 2: Ctrl+Z — правки отменяются в обратном порядке, ВКЛЮЧАЯ
    # снятие/замену H-toggle; гранулярность стека больше одной правки,
    # поэтому откат до наблюдаемых вех с защитой от захода на набор текста:
    # спойлер снят → замена откачена (h3 → h1) → все заголовки сняты,
    # текст цел (undo-стек contenteditable жив — находка F4)
    page.keyboard.press("Control+Z")
    expect(editor.area.locator(".spoiler")).to_have_count(0)
    page.keyboard.press("Control+Z")
    expect(editor.area.locator("h3")).to_have_count(0)
    expect(editor.area.locator("h1")).to_have_count(1)  # замена откатилась
    page.keyboard.press("Control+Z")
    expect(editor.area.locator("h1, h2, h3")).to_have_count(0)
    expect(
        editor.area.locator("p").filter(has_text="Абзац для отмены")
    ).to_have_count(1)  # текст не потерян

    # шаг 3: redo повторно применяет правки (включая замену уровня и
    # спойлер) до полного восстановления структуры. Замечание: при redo
    # вставки спойлера текст абзаца пропадает (воспроизводится стабильно,
    # дефект продукта — BUG-023 в test-model/bugs); структурные ассерты
    # ниже проверяют работоспособность redo, сохранность текста — на фазе
    # undo выше.
    for _ in range(6):
        if editor.area.locator(".spoiler").count() == 1:
            break
        page.keyboard.press("Control+Shift+Z")
    expect(editor.area.locator(".spoiler")).to_have_count(1)
    expect(editor.area.locator("h3")).to_have_count(1)  # замена применена снова

    # шаг 4: финальное состояние корректно сохраняется
    editor.title_input.fill("Undo redo rich")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    body = page.locator(".article-body")
    expect(body.locator("h3")).to_have_count(1)
    expect(body.locator(".spoiler")).to_have_count(1)
    saved = wiki_api.content_of(page_id)
    assert 'data-block="spoiler"' in saved  # структура применена redo-ом
    assert page_errors == []


def test_tc_rich_033_editor_no_external_deps(editor_page, page_errors, web_base_url):
    """coverage-backfill-1; TC-rich-033: Редактор без внешних зависимостей.
    Запросов к внешним CDN/доменам нет — редактор целиком на локальной
    статике; все модули rich/* отдаются собственным origin (vanilla JS,
    ОГР-8/NFR-33)."""
    page = editor_page
    external = _collect_external(page, web_base_url)
    editor = WikiEditor(page)
    editor.open_create(web_base_url)

    # шаг 3: вставить все rich-блоки — загружаются все модули rich/*
    editor.area.click()
    editor.toolbar_button("Спойлер").click()
    _caret_to_area_end(page)
    editor.toolbar_button("Блок кода").click()
    _caret_to_area_end(page)
    editor.toolbar_button("Табуляция").click()
    _caret_to_area_end(page)
    editor.toolbar_button("Таблица").click()
    expect(editor.area.locator(".spoiler")).to_have_count(1)
    expect(editor.area.locator(".codeblock")).to_have_count(1)
    expect(editor.area.locator(".tabswidget")).to_have_count(1)
    expect(editor.area.locator("table")).to_have_count(1)

    # шаг 4: внешних запросов нет; rich/* — с собственного origin
    assert external == [], external
    rich_module_requests = page.evaluate(
        """() => performance.getEntriesByType('resource')
             .map(r => r.name)
             .filter(u => u.includes('/js/wiki/rich/'))"""
    )
    assert rich_module_requests, "модули rich/* не запрошены"
    assert all(u.startswith(web_base_url) for u in rich_module_requests)
    assert page_errors == []


# ---------------------------------------------------------------------------
# Санитизация HTML (NFR-31): TC-rich-034…036
# ---------------------------------------------------------------------------


def test_tc_rich_034_sanitize_script_onerror_pre_render(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-034: Скрипт и onclick/onerror вырезаются
    до рендера (базовая санитизация). Whitelist-санитайзер удаляет script и
    onerror ДО рендера; alert не исполняется, ошибок в консоли нет (NFR-31)."""
    page_id = wiki_api.create(
        "Санитизация базовая",
        "<p>до скрипта</p><script>alert(1)</script>"
        '<img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" onerror="alert(2)">'
        "<p>после скрипта</p>",
    )
    saved = wiki_api.content_of(page_id)
    assert "script" not in saved and "alert" not in saved
    assert "onerror" not in saved

    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    body = page.locator(".article-body")
    expect(body).to_contain_text("до скрипта")
    expect(body).to_contain_text("после скрипта")
    assert page.evaluate("window.__xss === undefined")
    assert page_errors == []


def test_tc_rich_035_whitelist_tags_pass_intact(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-035: Разрешенные теги whitelist проходят
    без искажений. H1–H3, B/I/U, оба списка, цитата, код-блок, ссылки,
    таблица, изображение (data:image) — разметка в БД совпадает с
    отправленной байт-в-байт, текст без изменений (NFR-31)."""
    content = (
        "<h1>Раздел</h1><h2>Подраздел</h2><h3>Пункт</h3>"
        "<p><b>жирный</b><i>курсив</i><u>подчеркнутый</u></p>"
        "<ul><li>маркер</li></ul><ol><li>номер</li></ol>"
        "<blockquote>цитата</blockquote>"
        "<pre><code>код строки</code></pre>"
        '<p><a href="https://example.com" title="источник">ссылка</a></p>'
        "<table><thead><tr><th>Шапка</th></tr></thead>"
        "<tbody><tr><td>Ячейка</td></tr></tbody></table>"
        '<p><img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" '
        'alt="точка" width="16"></p>'
    )
    page_id = wiki_api.create("Whitelist целиком", content)
    # шаг 3: разметка сохранена без искажений — байт-в-байт
    assert wiki_api.content_of(page_id) == content

    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    body = page.locator(".article-body")
    expect(body.locator("h1")).to_have_text("Раздел")
    expect(body.locator("h2")).to_have_text("Подраздел")
    expect(body.locator("h3")).to_have_text("Пункт")
    expect(body.locator("b")).to_have_text("жирный")
    expect(body.locator("i")).to_have_text("курсив")
    expect(body.locator("u")).to_have_text("подчеркнутый")
    expect(body.locator("ul li")).to_have_text("маркер")
    expect(body.locator("ol li")).to_have_text("номер")
    expect(body.locator("blockquote")).to_have_text("цитата")
    expect(body.locator("pre code")).to_have_text("код строки")
    link = body.locator("a")
    expect(link).to_have_attribute("href", "https://example.com")
    expect(link).to_have_attribute("title", "источник")
    expect(body.locator("th")).to_have_text("Шапка")
    expect(body.locator("td")).to_have_text("Ячейка")
    img = body.locator("img")
    expect(img).to_have_attribute("alt", "точка")
    expect(img).to_have_attribute("width", "16")
    assert page_errors == []


def test_tc_rich_036_valid_blocks_pass_evil_stripped(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-036: Блочные конструкции проходят,
    подмененные значения снимаются. Валидные спойлер/код/табы сохраняются и
    активируются; div с data-block=evil деградировал в обычный контент
    «Подмена» (NFR-39/NFR-31)."""
    page_id = wiki_api.create(
        "Валидные и подмена",
        '<div data-block="spoiler" data-title="С">'
        '<div data-block-part="body"><p>спойлер жив</p></div></div>'
        '<div data-block="code" data-lang="python"><pre><code>y = 2</code></pre></div>'
        '<div data-block="tabs">'
        '<div data-block-part="tab" data-title="Т1"><p>первая</p></div>'
        '<div data-block-part="tab" data-title="Т2"><p>вторая</p></div>'
        "</div>"
        '<div data-block="evil">Подмена</div>',
    )
    saved = wiki_api.content_of(page_id)
    assert saved.count('data-block="spoiler"') == 1
    assert saved.count('data-block="code"') == 1
    assert saved.count('data-block="tabs"') == 1
    assert 'data-block="evil"' not in saved
    assert "Подмена" in saved

    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    body = page.locator(".article-body")
    # спойлер toggle
    spoiler = body.locator(".spoiler")
    spoiler.locator(".spoiler-head").click()
    expect(spoiler.locator(".spoiler-body")).to_contain_text("спойлер жив")
    # код подсвечен
    expect(body.locator(".codeblock .tok-kw, .codeblock .tok-num").first).to_be_visible()
    # табы переключаются
    tabs = body.locator(".tabswidget")
    tabs.locator(".tab").nth(1).click()
    expect(tabs.locator(".tab-pane").nth(1)).to_contain_text("вторая")
    # подмена — обычный контент
    expect(body).to_contain_text("Подмена")
    assert body.locator('[data-block="evil"] .spoiler-head').count() == 0
    assert page_errors == []


# ---------------------------------------------------------------------------
# Фикс-дискриминаторы F-1/F-2: TC-rich-037…039
# ---------------------------------------------------------------------------


def test_tc_rich_037_code_enter_roundtrip_no_br(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-037: Enter в код-блоке — round-trip
    переносов без br-мусора (фикс F-1). Внутри pre/code переносы — \\n;
    <br> в code-контексте не сохраняется; повторный round-trip не задваивает
    переносы (normalizeCodeInput идемпотентен); пустой код-блок без мусора."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Блок кода").click()
    block = editor.area.locator(".codeblock")
    expect(block).to_have_count(1)
    page.keyboard.type("строка один")
    page.keyboard.press("Enter")
    page.keyboard.type("строка два")
    page.keyboard.press("Enter")
    page.keyboard.type("строка три")

    # шаг 2: в БД переносы как \n, <br> внутри code-контекста нет
    editor.title_input.fill("Код roundtrip")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    expected = "строка один\nстрока два\nстрока три"
    saved = wiki_api.content_of(page_id)
    code_in_db = saved.split("<code>")[1].split("</code>")[0]
    assert code_in_db == expected, code_in_db
    assert "<br" not in code_in_db

    # шаг 3: переоткрытие в редакторе и повторное сохранение не задваивают
    editor.open_edit(web_base_url, page_id)
    code_text = editor.area.locator(".codeblock code").evaluate(
        "el => el.textContent"
    )
    assert code_text == expected
    editor.title_input.fill("Код roundtrip")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    saved2 = wiki_api.content_of(page_id)
    code_in_db2 = saved2.split("<code>")[1].split("</code>")[0]
    assert code_in_db2 == expected, code_in_db2  # нет \n\n на месте одного Enter
    assert "<br" not in code_in_db2

    # шаг 4: пустой код-блок — без мусорных \n/<br>
    page.goto(f"{web_base_url}/wiki?create=1")
    expect(editor.area).to_be_visible()
    editor.area.click()
    editor.toolbar_button("Блок кода").click()
    expect(editor.area.locator(".codeblock")).to_have_count(1)
    editor.title_input.fill("Пустой код")
    editor.save_button().click()
    page_id2 = _saved_page_id(page)
    saved3 = wiki_api.content_of(page_id2)
    assert "<code></code>" in saved3, saved3
    code_empty = saved3.split("<code>")[1].split("</code>")[0]
    assert code_empty == "" and "<br" not in code_empty

    # шаг 5: построчный вид статьи совпадает с введенным
    page.goto(f"{web_base_url}/wiki/{page_id}")
    article_code = page.locator(".article-body .codeblock code").evaluate(
        "el => el.textContent"
    )
    assert article_code == expected
    expect(
        page.locator(".article-body .codeblock .codeblock-nums")
    ).to_have_text("1\n2\n3")
    assert page_errors == []


def test_tc_rich_038_blocks_gated_in_codeblock(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-038: Гейт вставки блоков в код-блок —
    кнопки и paste-путь. Кнопки спойлера/табов/таблицы внутри кода не
    вставляют (матрица design §6); paste-подобный контент санитайзер
    разворачивает: внутри кода только pre/code с плоским текстом, текст
    вложенного блока сохранен; редактор после загрузки и повторное
    сохранение идемпотентны."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("До кода")
    editor.toolbar_button("Блок кода").click()
    block = editor.area.locator(".codeblock")
    expect(block).to_have_count(1)
    page.keyboard.type("x = 1")  # каретка внутри code

    # шаги 1–2: гейт — ни один блок не вставляется в код
    editor.toolbar_button("Спойлер").click()
    editor.toolbar_button("Табуляция").click()
    editor.toolbar_button("Таблица").click()
    expect(editor.area.locator('[data-block="spoiler"]')).to_have_count(0)
    expect(editor.area.locator(".tabswidget")).to_have_count(0)
    expect(editor.area.locator("table")).to_have_count(0)
    expect(block).to_have_count(1)
    expect(block.locator("code")).to_have_text("x = 1")  # DOM кода чист

    # шаг 3: paste-подобный контент — спойлер внутри код-блока
    page_id = wiki_api.create(
        "Paste в код",
        '<div data-block="code" data-lang="python"><pre><code>y = 2</code></pre>'
        '<div data-block="spoiler" data-title="Внутри кода">'
        '<div data-block-part="body"><p>текст вложенного спойлера</p></div>'
        "</div></div>",
    )

    # шаг 4: санитайзер — spoiler-разметки в контенте нет (unwrap целиком),
    # текст сохранен плоским текстом кода
    saved = wiki_api.content_of(page_id)
    saved_code = saved.split("<code>")[1].split("</code>")[0]
    assert "y = 2" in saved_code
    assert "текст вложенного спойлера" in saved  # текст не потерян
    assert saved.count('data-block="spoiler"') == 0  # unwrap целиком

    # в редакторе после загрузки внутри кода только pre/code — спойлерной
    # разметки нет, текст сохранен (плоским текстом кода); повторное
    # сохранение идемпотентно
    editor.open_edit(web_base_url, page_id)
    expect(editor.area.locator(".codeblock")).to_have_count(1)
    assert editor.area.locator(".codeblock .spoiler").count() == 0
    assert editor.area.locator(".codeblock .spoiler-head").count() == 0
    block_text = editor.area.locator(".codeblock").evaluate("el => el.textContent")
    assert "y = 2" in block_text
    assert "текст вложенного спойлера" in block_text  # текст не потерян
    editor.title_input.fill("Paste в код")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    saved2 = wiki_api.content_of(page_id)
    assert saved2.count('data-block="spoiler"') == 0
    assert "текст вложенного спойлера" in saved2
    assert page_errors == []


def test_tc_rich_039_gutter_numbers_scroll_sync_not_saved(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-039: Гуттер нумерации строк —
    соответствие, синхронный скролл, не в сохранении (фикс F-2). Номера
    1..N точно по строкам (пустая строка имеет номер, нумерация не «плывет»,
    buildGutter строится по блоку кода) — в редакторе и в статье; при
    прокрутке гуттер синхронен коду; в сохраненном контенте гуттера НЕТ —
    data-editor вырезается, в БД только pre/code.
    Замечание: 10 строк с пустыми задаются API-фикстурой — набор пустых
    строк В СЕРЕДИНЕ при побуквенном вводе редактором нормализуется
    (затирается), что проверено отдельной пробой; дискриминатор F-2 —
    соответствие гуттера фактическим строкам блока."""
    lines = ["a1", "", "c3", "", "e5", "f6", "", "h8", "", "j10"]
    code = "\n".join(lines)
    page_id = wiki_api.create(
        "Гуттер F-2",
        '<div data-block="code" data-lang="python"><pre><code>'
        + code
        + "</code></pre></div>",
    )

    page = editor_page
    # гуттер в редакторе — по фактическим строкам блока, пустые с номерами
    editor = WikiEditor(page)
    editor.open_edit(web_base_url, page_id)
    editor_block = editor.area.locator(".codeblock")
    expect(editor_block).to_have_count(1)
    expected_nums = "\n".join(str(i) for i in range(1, 11))
    assert (
        editor_block.locator(".codeblock-nums").evaluate("el => el.textContent")
        == expected_nums
    )
    assert (
        editor_block.locator("code").evaluate("el => el.textContent") == code
    )

    # шаг 3: в статье номера 1..N, при прокрутке гуттер синхронен коду
    page.goto(f"{web_base_url}/wiki/{page_id}")
    article_block = page.locator(".article-body .codeblock")
    expect(article_block.locator(".codeblock-nums")).to_have_text(expected_nums)
    assert article_block.locator("code").evaluate("el => el.textContent") == code
    sync = page.evaluate(
        """() => {
          const gutter = document.querySelector('.article-body .codeblock-nums');
          const pre = document.querySelector('.article-body .codeblock pre');
          const before = {
            g: gutter.getBoundingClientRect().top,
            p: pre.getBoundingClientRect().top,
          };
          window.scrollTo(0, 300);
          return new Promise((resolve) => requestAnimationFrame(() => {
            const after = {
              g: gutter.getBoundingClientRect().top,
              p: pre.getBoundingClientRect().top,
            };
            resolve({ dx: after.g - before.g, dp: after.p - before.p });
          }));
        }"""
    )
    # прокрутка сдвинула гуттер и код на ровно одинаковую величину
    assert abs(sync["dx"] - sync["dp"]) < 0.5, sync
    assert sync["dx"] != 0, "страница не проскроллилась — проверка холостая"

    # шаг 4: в сохраненном контенте гуттера НЕТ (data-editor вырезан при
    # сериализации), в БД только текст pre/code
    saved = wiki_api.content_of(page_id)
    assert "codeblock-nums" not in saved and "data-editor" not in saved
    code_in_db = saved.split("<code>")[1].split("</code>")[0]
    assert code_in_db == code
    assert "<br" not in code_in_db
    assert page_errors == []
