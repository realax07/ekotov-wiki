"""Rich-инструменты редактора Wiki (tasks.md 2.6/3.5/4.6/5.4 p12-rich-tools;
FR-118…FR-122) — web-кейсы Playwright по паттерну test_p15_wiki_editor.py.

Сьют НЕ наследует откаченный rich-v1 (урок aaa1900/design §7): имя файла —
test_rich_tools.py, откаченные модули не импортируются.

Покрытие по инструментам (edit + view, вложенность по матрице design §6,
XSS-векторы, undo-тест F4):

  Спойлер (FR-118):
    test_spoiler_insert_rename_toggle_save
    test_spoiler_collapsed_keeps_content_roundtrip
    test_spoiler_in_table_cell_compact
    test_spoiler_in_spoiler_independent
  Блок кода (FR-119):
    test_code_language_numbering_copy_highlight
    test_code_unknown_lang_plain_no_errors
    test_code_inside_spoiler
  Табуляция (FR-120):
    test_tabs_add_rename_delete_last_protected_limit8_scroll
    test_tabs_switching_active_not_saved
    test_tabs_inside_tab_nested
  H-toggle (FR-121):
    test_heading_toggle_clear_replace
    test_backspace_empty_heading_to_paragraph
    test_undo_after_heading_toggle (F4: execCommand — undo-стек жив)
  Таблица (FR-122):
    test_table_add_remove_row_col_last_disabled_delete_whole
    test_table_tab_navigation_enter_br
  Деградация/безопасность (NFR-39):
    test_matrix_view_activation_unknown_block_degrades
    test_xss_vectors_inside_blocks_not_executed
"""

import os
import re
from types import SimpleNamespace

import pytest
from playwright.sync_api import expect

from tests.web.pages.wiki import WikiEditor

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

BASE_URL_ENV = "EKOTOV_WIKI_BASE_URL"


# ---------------------------------------------------------------------------
# fixtures (паттерн wiki_api из test_p15_wiki_editor)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def wiki_stand_schema(web_server):
    """Схема wiki в tmp-БД стенда (идемпотентно; паттерн test_p15_wiki_editor).
    Внешний стенд (EKOTOV_WIKI_DB_PATH задан) уже смигрирован — пропуск."""
    import subprocess as sp
    import sys

    db_path = web_server.get("db_path") if isinstance(web_server, dict) else None
    if not db_path:
        return
    _repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    mig_env = dict(os.environ, DB_PATH=db_path, SECRET_KEY="web-tests-secret-key")
    mig_env.pop("PYTHONPATH", None)
    for module in ("app.migrate_wiki",):
        mig = sp.run(
            [sys.executable, "-m", module],
            cwd=str(_repo_root) + "/backend", env=mig_env,
            capture_output=True, text=True,
        )
        assert mig.returncode == 0, f"{module}: {mig.stderr}"


@pytest.fixture
def wiki_api(web_base_url, web_owner_session):
    """Парные хелперы create/delete wiki-страниц с teardown-очисткой."""
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

    def content_of(page_id):
        return web_owner_session.get(
            f"{web_base_url}/api/wiki/pages/{page_id}"
        ).json()["content"]

    api = SimpleNamespace(create=create, content_of=content_of, register=created.append)
    yield api
    for page_id in reversed(created):
        try:
            web_owner_session.delete(f"{web_base_url}/api/wiki/pages/{page_id}")
        except Exception:
            pass


@pytest.fixture
def editor_page(logged_in_page, page_errors):
    """Страница с ошибками-коллектором (pageerror/console-error)."""
    return logged_in_page


@pytest.fixture
def page_errors(page):
    """JS-ошибки страницы: ни один rich-сценарий не должен ронять консоль
    (NFR-39: деградация без ошибок)."""
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
# Спойлер (FR-118)
# ---------------------------------------------------------------------------


def test_spoiler_insert_rename_toggle_save(editor_page, page_errors, web_base_url):
    """Спойлер: вставка кнопкой, инлайн-переименование, toggle по всей шапке,
    сохранение → в статье спойлер с названием и зоной содержимого."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Спойлер").click()

    spoiler = editor.area.locator('.spoiler')
    expect(spoiler).to_have_count(1)
    expect(spoiler.locator(".spoiler-title")).to_have_text("Спойлер")

    # инлайн-переименование: клик по названию → input → «Скрытые детали»
    spoiler.locator(".spoiler-title").click()
    name_input = spoiler.locator(".spoiler-title-input")
    expect(name_input).to_be_visible()
    name_input.fill("Скрытые детали")
    name_input.press("Enter")
    expect(spoiler.locator(".spoiler-title")).to_have_text("Скрытые детали")

    # зона содержимого: клик по телу — каретка внутри, печатаем
    spoiler.locator(".spoiler-body").click()
    page.keyboard.type("Тело спойлера")
    expect(spoiler.locator(".spoiler-body")).to_contain_text("Тело спойлера")

    # toggle по шапке (не по названию): клик по шеврону сворачивает
    spoiler.locator(".spoiler-caret").click()
    expect(spoiler).to_have_class(re.compile("closed"))
    # содержимое в DOM (свернутый сохраняет содержимое)
    expect(spoiler.locator(".spoiler-body p")).to_have_text("Тело спойлера")
    spoiler.locator(".spoiler-caret").click()
    expect(spoiler).to_have_class(re.compile("open"))

    editor.title_input.fill("Страница со спойлером")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))

    body = page.locator(".article-body")
    article_spoiler = body.locator(".spoiler")
    expect(article_spoiler).to_have_count(1)
    expect(article_spoiler.locator(".spoiler-title")).to_have_text("Скрытые детали")
    # в рендере спойлер развернут (состояние не сохраняется, §1)
    expect(article_spoiler).to_have_class(re.compile("open"))
    expect(article_spoiler.locator(".spoiler-body")).to_contain_text("Тело спойлера")
    # toggle в статье: вся шапка кликабельна (ОВ-1)
    article_spoiler.locator(".spoiler-head").click()
    expect(article_spoiler).to_have_class(re.compile("closed"))
    article_spoiler.locator(".spoiler-head").click()
    expect(article_spoiler.locator(".spoiler-body")).to_contain_text("Тело спойлера")


def test_spoiler_collapsed_keeps_content_roundtrip(editor_page, wiki_api, web_base_url):
    """Свернутый в редакторе спойлер сохраняет содержимое: в БД тело есть,
    при открытии статьи спойлер развернут (§1, сценарий FR-118)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Спойлер").click()
    spoiler = editor.area.locator(".spoiler")
    page.keyboard.type("Секретное содержимое")
    spoiler.locator(".spoiler-caret").click()
    expect(spoiler).to_have_class(re.compile("closed"))

    editor.title_input.fill("Свернутый спойлер")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    page_id = int(page.url.rstrip("/").rsplit("/", 1)[1])

    # в сохраненном контенте тело есть (не потеряно свернутостью)
    assert "Секретное содержимое" in wiki_api.content_of(page_id)

    page.goto(f"{web_base_url}/wiki/{page_id}")
    article_spoiler = page.locator(".article-body .spoiler")
    expect(article_spoiler).to_have_class(re.compile("open"))  # развернут
    expect(article_spoiler.locator(".spoiler-body")).to_contain_text(
        "Секретное содержимое"
    )


def test_spoiler_in_table_cell_compact(editor_page, wiki_api, web_base_url):
    """Спойлер в ячейке таблицы: компактный класс (по closest('td,th')),
    сохранение → в статье сворачивается/разворачивается (FR-118)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Таблица").click()
    cell = editor.area.locator("tbody tr").nth(0).locator("td").nth(1)
    cell.click()
    editor.toolbar_button("Спойлер").click()

    spoiler = editor.area.locator("td .spoiler")
    expect(spoiler).to_have_count(1)
    expect(spoiler).to_have_class(re.compile("rich-compact"))  # компакт (мокап)
    page.keyboard.type("В ячейке")

    editor.title_input.fill("Спойлер в ячейке")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    body = page.locator(".article-body")
    cell_spoiler = body.locator("td .spoiler")
    expect(cell_spoiler).to_have_count(1)
    cell_spoiler.locator(".spoiler-head").click()
    expect(cell_spoiler).to_have_class(re.compile("closed"))
    cell_spoiler.locator(".spoiler-head").click()
    expect(cell_spoiler.locator(".spoiler-body")).to_contain_text("В ячейке")


def test_spoiler_in_spoiler_independent(editor_page, wiki_api, web_base_url):
    """Спойлер в спойлере: независимые состояния, контент обоих сохраняется
    (урок rich-v1 «потеря контента при вложении» — не повторяется)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Спойлер").click()
    outer = editor.area.locator(".spoiler").nth(0)
    page.keyboard.type("Внешнее тело")
    editor.toolbar_button("Спойлер").click()  # каретка в body внешнего
    inner = outer.locator(".spoiler")
    expect(inner).to_have_count(1)
    page.keyboard.type("Внутреннее тело")

    # независимые состояния: внутренний свернут — внешний развернут
    inner.locator(".spoiler-caret").click()
    expect(inner).to_have_class(re.compile("closed"))
    expect(outer).to_have_class(re.compile("open"))

    editor.title_input.fill("Вложенные спойлеры")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    body = page.locator(".article-body")
    nested = body.locator(".spoiler .spoiler")
    expect(nested).to_have_count(1)
    expect(nested.locator(".spoiler-body")).to_contain_text("Внутреннее тело")
    # сворачивание внешнего скрывает внутренний целиком
    body.locator(".spoiler").first.locator("> .spoiler-head").click()
    expect(body.locator(".spoiler").first).to_have_class(re.compile("closed"))
    expect(nested.locator(".spoiler-body")).to_be_hidden()
    expect(
        body.locator(".spoiler").first.locator("> .spoiler-body")
    ).to_contain_text("Внутреннее тело")  # контент в DOM — не потерян


# ---------------------------------------------------------------------------
# Блок кода (FR-119)
# ---------------------------------------------------------------------------


def test_code_language_numbering_copy_highlight(editor_page, wiki_api, web_base_url):
    """Блок кода: вставка, выбор языка (ОВ-2), нумерация строк, подсветка в
    статье, «Копировать» → чистый текст и «✓ Скопировано» (FR-119)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Блок кода").click()

    block = editor.area.locator(".codeblock")
    expect(block).to_have_count(1)
    expect(block.locator(".codeblock-lang")).to_contain_text("python")
    expect(block.locator(".codeblock-nums")).to_be_visible()

    # выбор языка: дропдаун → sql
    block.locator(".codeblock-lang").click()
    block.locator(".lang-menu .lang-opt").filter(has_text="sql").click()
    expect(block.locator(".codeblock-lang")).to_contain_text("sql")

    page.keyboard.type("SELECT id FROM users WHERE id = 1")

    # нумерация строк: одна строка → «1»
    assert block.locator(".codeblock-nums").inner_text().strip() == "1"

    editor.title_input.fill("Код-блок страница")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    page_id = int(page.url.rstrip("/").rsplit("/", 1)[1])

    # в БД чистый текст — спанов подсветки нет (§1)
    saved = wiki_api.content_of(page_id)
    assert "tok-kw" not in saved and "SELECT id FROM users" in saved

    # в статье: подсветка лексером + нумерация + язык
    article_block = page.locator(".article-body .codeblock")
    expect(article_block.locator(".codeblock-lang")).to_have_text("sql")
    expect(article_block.locator(".tok-kw").first).to_be_visible()
    expect(article_block.locator(".codeblock-nums")).to_have_text("1")

    # «Копировать»: чистый текст без спанов (стаб writeText перехватывает
    # вызов — сам Clipboard API браузера не тестируем)
    page.evaluate(
        "navigator.clipboard.writeText = (t) => "
        "{ window.__copiedText = t; return Promise.resolve(); };"
    )
    article_block.locator(".copy-btn").click()
    expect(article_block.locator(".copy-btn")).to_have_text("✓ Скопировано")
    assert page.evaluate("window.__copiedText") == "SELECT id FROM users WHERE id = 1"
    # через 1,5 с кнопка возвращается
    page.wait_for_timeout(1700)
    expect(article_block.locator(".copy-btn")).to_have_text("Копировать")


def test_code_unknown_lang_plain_no_errors(editor_page, wiki_api, page_errors,
                                           web_base_url):
    """Поврежденный/чужой data-lang (санитайзер снимает) → plain без
    подсветки и без ошибок, текст полностью сохранен (NFR-39)."""
    page_id = wiki_api.create(
        "Код без языка",
        '<div data-block="code" data-lang="cobol"><pre><code>MOVE A TO B.'
        "</code></pre></div>",
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    block = page.locator(".article-body .codeblock")
    expect(block).to_have_count(1)
    expect(block.locator(".tok-kw")).to_have_count(0)  # подсветки нет — plain
    expect(block.locator("code")).to_contain_text("MOVE A TO B.")  # текст цел
    assert page_errors == []


def test_code_inside_spoiler(editor_page, wiki_api, web_base_url):
    """Код-блок внутри спойлера: подсветка/копирование работают,
    сворачивание спойлера код не теряет (FR-119 + FR-118)."""
    page_id = wiki_api.create(
        "Код в спойлере",
        '<div data-block="spoiler" data-title="Скрипт">'
        '<div data-block-part="body">'
        '<div data-block="code" data-lang="python">'
        "<pre><code>def f():\n    return 1</code></pre></div>"
        "</div></div>",
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    spoiler = page.locator(".article-body .spoiler")
    code_block = spoiler.locator(".codeblock")
    expect(code_block.locator(".tok-kw").first).to_be_visible()
    spoiler.locator(".spoiler-head").click()
    expect(code_block).to_be_hidden()
    spoiler.locator(".spoiler-head").click()
    expect(code_block.locator("code")).to_contain_text("def f():")


# ---------------------------------------------------------------------------
# Табуляция (FR-120)
# ---------------------------------------------------------------------------


def test_tabs_add_rename_delete_last_protected_limit8_scroll(
    editor_page, web_base_url
):
    """Табы: «+», dblclick-переименование, «×» на hover неактивной,
    последнюю удалить нельзя, лимит 8, переполнение — горизонтальный скролл
    (ОВ-2/ОВ-3, FR-120)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Табуляция").click()

    widget = editor.area.locator(".tabswidget")
    expect(widget.locator(".tab")).to_have_count(2)

    # «+» добавляет вкладку
    widget.locator(".tab-add").click()
    expect(widget.locator(".tab")).to_have_count(3)

    # dblclick-переименование третьей
    third = widget.locator(".tab").nth(2)
    third.dblclick()
    rename = widget.locator(".tab-rename")
    expect(rename).to_be_visible()
    rename.fill("Детали")
    rename.press("Enter")
    expect(third).to_contain_text("Детали")

    # «×» удаляет неактивную (последнюю); × скрыт CSS-ом до hover —
    # dispatch_event обходит actionability видимости
    third.locator(".tab-close").dispatch_event("click")
    expect(widget.locator(".tab")).to_have_count(2)

    # единственную вкладку удалить нельзя: «×» скрыт (CSS :only-of-type)
    widget.locator(".tab").nth(1).hover()
    widget.locator(".tab").nth(1).locator(".tab-close").dispatch_event("click")
    expect(widget.locator(".tab")).to_have_count(1)
    assert not widget.locator(".tab .tab-close").first.is_visible()

    # лимит 8: «+» до отказа, потом disabled
    for _ in range(7):
        widget.locator(".tab-add").click()
    expect(widget.locator(".tab")).to_have_count(8)
    expect(widget.locator(".tab-add")).to_be_disabled()

    # переполнение таб-бара — горизонтальный скролл (ОВ-3)
    page.evaluate(
        """() => {
          const bar = document.querySelector('.editor-area .tabbar');
          bar.querySelectorAll('.tab').forEach((tab, i) => {
            if (!tab.querySelector('input')) {
              tab.firstChild.textContent = 'Очень длинное название вкладки ' + (i + 1);
            }
          });
        }"""
    )
    overflow = page.evaluate(
        """() => {
          const bar = document.querySelector('.editor-area .tabbar');
          return {
            overflow: getComputedStyle(bar).overflowX,
            scrolls: bar.scrollWidth >= bar.clientWidth,
          };
        }"""
    )
    assert overflow["overflow"] == "auto"
    assert overflow["scrolls"]


def test_tabs_switching_active_not_saved(editor_page, wiki_api, web_base_url):
    """Переключение вкладок в редакторе; активная вкладка НЕ сохраняется —
    при открытии статьи активна первая (§1)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Табуляция").click()
    widget = editor.area.locator(".tabswidget")
    page.keyboard.type("Содержимое первой")
    widget.locator(".tab").nth(1).click()
    expect(widget.locator(".tab").nth(1)).to_have_class(re.compile("active"))
    page.keyboard.type("второй")

    editor.title_input.fill("Табы страница")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    page_id = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved = wiki_api.content_of(page_id)
    assert "Содержимое первой" in saved and "второй" in saved

    page.goto(f"{web_base_url}/wiki/{page_id}")
    widget = page.locator(".article-body .tabswidget")
    expect(widget.locator(".tab").first).to_have_class(re.compile("active"))
    expect(widget.locator(".tab-pane").first).to_contain_text("Содержимое первой")
    # клик по второй вкладке в статье — переключение (FR-120)
    widget.locator(".tab").nth(1).click()
    expect(widget.locator(".tab").nth(1)).to_have_class(re.compile("active"))
    expect(widget.locator(".tab-pane").nth(1)).to_contain_text("второй")
    expect(widget.locator(".tab-pane").first).to_be_hidden()


def test_tabs_inside_tab_nested(editor_page, wiki_api, web_base_url):
    """Табы внутри вкладки: оба виджета независимы, контент всех вкладок
    сохраняется (design §6, FR-120)."""
    page_id = wiki_api.create(
        "Табы в табе",
        '<div data-block="tabs">'
        '<div data-block-part="tab" data-title="Снаружи">'
        "<p>до вложения</p>"
        '<div data-block="tabs">'
        '<div data-block-part="tab" data-title="Внутри"><p>глубоко</p></div>'
        '<div data-block-part="tab" data-title="Рядом"><p>соседняя</p></div>'
        "</div></div>"
        '<div data-block-part="tab" data-title="Вторая"><p>обычная</p></div>'
        "</div>",
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    widget = page.locator(".article-body .tabswidget").first
    nested = widget.locator(".tabswidget")
    expect(nested).to_have_count(1)
    expect(nested.locator(".tab-pane").first).to_contain_text("глубоко")
    nested.locator(".tab").nth(1).click()
    expect(nested.locator(".tab-pane").nth(1)).to_contain_text("соседняя")
    # внешний виджет переключается независимо (селекторы — прямые дети:
    # вкладки/панели внутреннего виджета не должны попадать в выборку)
    widget.locator("> .tabbar > .tab").nth(1).click()
    expect(widget.locator("> .tab-pane").nth(1)).to_contain_text("обычная")


# ---------------------------------------------------------------------------
# H-toggle (FR-121)
# ---------------------------------------------------------------------------


def test_heading_toggle_clear_replace(editor_page, web_base_url):
    """H1/H2/H3 — toggle: повторный клик снимает (текст → абзац, CLEAR),
    клик по соседней заменяет уровень; одновременных нажатий нет (FR-121)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("Строка заголовка")
    editor.select_all_text()

    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_text("Строка заголовка")
    expect(editor.toolbar_button("Заголовок 2")).to_have_attribute(
        "aria-pressed", "true"
    )

    # повторный клик H2 — снимает формат, текст не теряется (CLEAR)
    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_count(0)
    expect(editor.area).to_contain_text("Строка заголовка")
    for label in ("Заголовок 1", "Заголовок 2", "Заголовок 3"):
        expect(editor.toolbar_button(label)).to_have_attribute(
            "aria-pressed", "false"
        )

    # замена уровня: H1 → H3, нажата ровно одна кнопка
    editor.select_all_text()
    editor.toolbar_button("Заголовок 1").click()
    expect(editor.area.locator("h1")).to_have_count(1)
    editor.toolbar_button("Заголовок 3").click()
    expect(editor.area.locator("h3")).to_have_text("Строка заголовка")
    expect(editor.area.locator("h1")).to_have_count(0)
    expect(editor.toolbar_button("Заголовок 3")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(editor.toolbar_button("Заголовок 1")).to_have_attribute(
        "aria-pressed", "false"
    )


def test_backspace_empty_heading_to_paragraph(editor_page, web_base_url):
    """Backspace в пустом заголовке снимает формат: пустой абзац с курсором
    (ОВ-5, канон Notion — FR-121)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_count(1)
    page.keyboard.press("Backspace")
    expect(editor.area.locator("h2")).to_have_count(0)
    expect(editor.area.locator("p")).to_have_count(1)


def test_undo_after_heading_toggle(editor_page, web_base_url):
    """Undo после toggle заголовка (F4): Ctrl+Z откатывает toggle — формат
    вернулся, текст не потерян (undo-стек execCommand жив)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("Абзац для отмены")
    editor.select_all_text()
    editor.toolbar_button("Заголовок 1").click()
    expect(editor.area.locator("h1")).to_have_count(1)
    page.keyboard.press("Control+Z")
    expect(editor.area.locator("h1")).to_have_count(0)
    expect(editor.area).to_contain_text("Абзац для отмены")
    # повтор → redo возвращает заголовок
    page.keyboard.press("Control+Shift+Z")
    expect(editor.area.locator("h1")).to_have_count(1)
    expect(editor.area.locator("h1")).to_have_text("Абзац для отмены")


# ---------------------------------------------------------------------------
# Таблица (FR-122)
# ---------------------------------------------------------------------------


def test_table_add_remove_row_col_last_disabled_delete_whole(
    editor_page, web_base_url
):
    """Таблица: «+»/«−» строк/столбцов относительно целевой ячейки; последняя
    строка/столбец — disabled с подсказкой; удаление целиком — ОТДЕЛЬНОЙ
    кнопкой (ОВ-4, FR-122)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("До таблицы")
    editor.toolbar_button("Таблица").click()

    cell = editor.area.locator("tbody tr").nth(0).locator("td").nth(1)
    cell.click()
    panel = editor.area.locator(".tbl-panel")
    expect(panel).to_be_visible()
    cell.click()  # после фокуса в панели каретка могла уйти — целевая та же

    # «+» строка ниже целевой, «+» столбец правее целевой
    panel.get_by_role("button", name="Добавить строку ниже").click()
    expect(editor.area.locator("tr")).to_have_count(4)  # thead + 2 + новая
    cell = editor.area.locator("tbody tr").nth(0).locator("td").nth(1)
    cell.click()
    panel.get_by_role("button", name="Добавить столбец справа").click()
    expect(editor.area.locator("thead th")).to_have_count(4)

    # «−» удаляет обратно (последнюю добавленную); delRow удаляет СТРОКУ
    # ПОД кареткой — панель прячется, перед следующим «−» кликаем ячейку
    panel.get_by_role("button", name="Удалить строку").click()
    expect(editor.area.locator("tr")).to_have_count(3)
    cell = editor.area.locator("tbody tr").nth(0).locator("td").nth(1)
    cell.click()
    expect(panel).to_be_visible()
    panel.get_by_role("button", name="Удалить столбец").click()
    expect(editor.area.locator("thead th")).to_have_count(3)

    # сводим к 1×1: после каждого удаления каретка переносится в соседнюю
    # ячейку — панель не гаснет, «−» доступны до достижения 1×1
    for _ in range(6):
        rows = editor.area.locator("tr").count()
        cols = editor.area.locator("tr").first.locator("th,td").count()
        if rows > 1:
            panel.get_by_role("button", name="Удалить строку").click()
        elif cols > 1:
            panel.get_by_role("button", name="Удалить столбец").click()
        else:
            break
    expect(editor.area.locator("tr")).to_have_count(1)
    expect(editor.area.locator("th")).to_have_count(1)
    # панель видна: клик по единственной ячейке — цель есть
    editor.area.locator("thead th").first.click()
    del_row = panel.get_by_role("button", name="Последнюю строку удалить нельзя")
    expect(del_row).to_be_disabled()
    del_col = panel.get_by_role("button", name="Последний столбец удалить нельзя")
    expect(del_col).to_be_disabled()

    # удаление таблицы — отдельной кнопкой, остальной контент цел
    panel.get_by_role("button", name="Удалить таблицу целиком").click()
    expect(editor.area.locator("table")).to_have_count(0)
    expect(editor.area).to_contain_text("До таблицы")

    editor.title_input.fill("Таблица удалена")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    expect(page.locator(".article-body table")).to_have_count(0)


def test_table_tab_navigation_enter_br(editor_page, wiki_api, web_base_url):
    """Tab — следующая ячейка; Enter — перенос <br> внутри ячейки (не новая
    строка таблицы); переносы видны в сохраненной статье (FR-122)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Таблица").click()
    first_cell = editor.area.locator("tbody tr").nth(0).locator("td").nth(0)
    first_cell.click()
    page.keyboard.type("первая")
    page.keyboard.press("Tab")
    page.keyboard.type("вторая")
    # каретка в следующей ячейке (anchorNode — текстовый узел: нормализуем)
    caret_cell = page.evaluate(
        """() => {
          const n = window.getSelection().anchorNode;
          const e = n && (n.nodeType === 1 ? n : n.parentNode);
          const cell = e && (e.closest ? e.closest('td,th') : null);
          return cell ? cell.textContent : '';
        }"""
    )
    assert "вторая" in caret_cell
    page.keyboard.press("Enter")  # перенос ВНУТРИ ячейки
    page.keyboard.type("третья строка")
    cells = editor.area.locator("tbody tr").nth(0).locator("td")
    expect(cells).to_have_count(3)  # новой строки таблицы не появилось
    expect(cells.nth(1)).to_contain_text("вторая")

    editor.title_input.fill("Таблица навигация")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    article_cell = page.locator(".article-body tbody tr").nth(0).locator("td").nth(1)
    expect(article_cell.locator("br")).to_have_count(1)
    expect(article_cell).to_contain_text("вторая")
    expect(article_cell).to_contain_text("третья строка")


# ---------------------------------------------------------------------------
# Матрица вложенности §6 + деградация + XSS (NFR-39)
# ---------------------------------------------------------------------------


def _matrix_content() -> str:
    """Матрица design §6 (разрешенные связки) — как в API-ругтрипе."""
    return (
        '<div data-block="spoiler" data-title="Внешний">'
        '<div data-block-part="body">'
        '<div data-block="spoiler" data-title="Внутренний">'
        '<div data-block-part="body"><p>спойлер-в-спойлере</p></div></div>'
        "</div></div>"
        '<div data-block="code" data-lang="python"><pre><code>def f():'
        "\n    return 1</code></pre></div>"
        '<div data-block="tabs">'
        '<div data-block-part="tab" data-title="Обзор"><p>первая</p></div>'
        '<div data-block-part="tab" data-title="Внутри">'
        '<div data-block="spoiler" data-title="Во вкладке">'
        '<div data-block-part="body"><p>таб-в-табе-спойлер</p></div></div>'
        "</div></div>"
        "<table><thead><tr><th>Этап</th></tr></thead><tbody><tr><td>"
        '<div data-block="spoiler" data-title="Компакт">'
        '<div data-block-part="body"><p>в-ячейке</p></div></div>'
        "</td></tr></tbody></table>"
    )


def test_matrix_view_activation_unknown_block_degrades(
    editor_page, wiki_api, page_errors, web_base_url
):
    """Сквозная активация матрицы §6 в статье + неизвестный блок деградирует
    без потери контента и ошибок; внешних запросов нет (ОГР-8, NFR-39)."""
    content = _matrix_content() + '<div data-block="future-widget">неизвестный</div>'
    page_id = wiki_api.create("Матрица вложенности", content)
    page = editor_page

    external: list[str] = []
    page.on(
        "request",
        lambda req: external.append(req.url)
        if not req.url.startswith(web_base_url)
        else None,
    )
    page.goto(f"{web_base_url}/wiki/{page_id}")

    body = page.locator(".article-body")
    # спойлер в спойлере
    nested = body.locator(".spoiler .spoiler")
    expect(nested).to_have_count(1)
    expect(nested.locator(".spoiler-body")).to_contain_text("спойлер-в-спойлере")
    # подсветка кода
    expect(body.locator(".codeblock .tok-kw").first).to_be_visible()
    # табы со спойлером во вкладке
    tabs = body.locator(".tabswidget")
    expect(tabs.locator(".tab")).to_have_count(2)
    tabs.locator(".tab").nth(1).click()
    expect(tabs.locator(".tab-pane").nth(1)).to_contain_text("таб-в-табе-спойлер")
    # компактный спойлер в ячейке
    expect(body.locator("td .spoiler .spoiler-body")).to_contain_text("в-ячейке")
    # неизвестный блок — контент виден, виджета нет
    expect(body).to_contain_text("неизвестный")
    assert body.locator('[data-block="future-widget"] .spoiler-head').count() == 0
    # ошибок JS нет, внешних запросов нет
    assert page_errors == []
    assert external == []


def test_xss_vectors_inside_blocks_not_executed(
    editor_page, wiki_api, page_errors, web_base_url
):
    """XSS-векторы внутри блоков (script с содержимым, onclick, javascript:)
    не исполняются и не сохраняются; сам блок и текст живы (NFR-39/§8)."""
    dirty = (
        '<div data-block="spoiler" data-title="X" onclick="evil()">'
        '<div data-block-part="body"><script>window.__xss=1</script>'
        '<p>окей</p><a href="javascript:alert(2)">тыкни</a>'
        '<img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" '
        'onerror="window.__xss=2" alt="вектор"></div></div>'
    )
    page_id = wiki_api.create("XSS в блоках", dirty)
    saved = wiki_api.content_of(page_id)
    assert "script" not in saved and "alert" not in saved
    assert "onclick" not in saved and "onerror" not in saved
    assert 'data-block="spoiler"' in saved and "<p>окей</p>" in saved

    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    expect(page.locator(".article-body .spoiler .spoiler-body")).to_contain_text(
        "окей"
    )
    assert page.evaluate("window.__xss === undefined")
    assert page_errors == []
