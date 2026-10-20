"""QA-сьют p12-rich-tools — e2e-часть (Playwright против живого стенда).

Прогон по чек-листу test-model/cases/p12-rich-tools/ (TC-rich-001..041).
Один тест = один кейс (ID в имени); sanitize-GET/paste-дубли тех же кейсов —
tests/api/test_p12_rich_qa_api.py. Требует поднятый стенд
(scripts/qa_stand_up.sh): EKOTOV_WIKI_BASE_URL + EKOTOV_WIKI_DB_PATH.

Паттерны селекторов унаследованы от tests/web/test_rich_tools.py (dev-сьют).
"""

import os
import re
import tempfile

import pytest
from playwright.sync_api import expect

from tests.web.pages.wiki import WikiEditor

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

SPOILER = (
    '<div data-block="spoiler" data-title="{t}">'
    "<div data-block-part=\"body\">{b}</div></div>"
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def page_errors(page):
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on(
        "console",
        lambda msg: errors.append(msg.text) if msg.type == "error" else None,
    )
    yield errors
    if errors:
        print("\n[BROWSER ERRORS]", *errors, sep="\n  ")


@pytest.fixture
def editor_page(logged_in_page, page_errors):
    return logged_in_page


@pytest.fixture
def qa(web_owner_session, web_base_url):
    """create/put/get/delete wiki-страниц через API стенда."""
    created: list[int] = []

    def make(title, content=""):
        resp = web_owner_session.post(
            f"{web_base_url}/api/wiki/pages",
            json={"title": title, "content": content},
        )
        assert resp.status_code == 201, resp.text
        pid = resp.json()["id"]
        created.append(pid)
        return pid

    def put(pid, content):
        resp = web_owner_session.put(
            f"{web_base_url}/api/wiki/pages/{pid}", json={"content": content}
        )
        assert resp.status_code == 200, resp.text

    def get(pid):
        return web_owner_session.get(
            f"{web_base_url}/api/wiki/pages/{pid}"
        ).json()["content"]

    from types import SimpleNamespace

    ns = SimpleNamespace(make=make, put=put, get=get, ids=created)
    yield ns
    for pid in reversed(created):
        try:
            web_owner_session.delete(f"{web_base_url}/api/wiki/pages/{pid}")
        except Exception:
            pass


def _caret_to_end(page) -> None:
    """Каретка в конец редактируемой области (после таблицы и т.п.)."""
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


# ---------------------------------------------------------------------------
# Спойлер (FR-118): TC-rich-001..005
# ---------------------------------------------------------------------------


def test_tc_rich_001_spoiler_insert_rename_save_get(editor_page, qa, web_base_url):
    """TC-rich-001 (Must): вставка, инлайн-rename, тело; GET — data-block +
    data-title, data-editor-узлов нет."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Спойлер").click()

    spoiler = editor.area.locator(".spoiler")
    expect(spoiler).to_have_count(1)
    expect(spoiler.locator(".spoiler-title")).to_have_text("Спойлер")

    spoiler.locator(".spoiler-title").click()
    name_input = spoiler.locator(".spoiler-title-input")
    expect(name_input).to_be_visible()
    name_input.fill("Скрытые детали")
    name_input.press("Enter")
    expect(spoiler.locator(".spoiler-title")).to_have_text("Скрытые детали")

    spoiler.locator(".spoiler-body").click()
    page.keyboard.type("Тело спойлера")

    editor.title_input.fill("QA-001 спойлер")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])

    saved = qa.get(pid)
    assert 'data-block="spoiler" data-title="Скрытые детали"' in saved
    assert "Тело спойлера" in saved
    assert "data-editor" not in saved

    article = page.locator(".article-body .spoiler")
    expect(article.locator(".spoiler-title")).to_have_text("Скрытые детали")
    expect(article.locator(".spoiler-body")).to_contain_text("Тело спойлера")


def test_tc_rich_002_spoiler_head_anywhere_toggles(editor_page, qa, page_errors, web_base_url):
    """TC-rich-002 (Must, ОВ-1): клик по любой точке шапки (шеврон/название/
    пустое место) toggle; клик по телу — НЕ toggle."""
    pid = qa.make(
        "QA-002 шапка",
        SPOILER.format(t="Заголовок", b="<p>Содержимое тела</p>"),
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{pid}")
    spoiler = page.locator(".article-body .spoiler")
    expect(spoiler).to_have_class(re.compile("open"))

    # шеврон
    spoiler.locator(".spoiler-caret").click()
    expect(spoiler).to_have_class(re.compile("closed"))
    # название
    spoiler.locator(".spoiler-title").click()
    expect(spoiler).to_have_class(re.compile("open"))
    # пустое место шапки (правый край, не title/caret)
    box = spoiler.locator(".spoiler-head").bounding_box()
    page.mouse.click(box["x"] + box["width"] - 10, box["y"] + box["height"] / 2)
    expect(spoiler).to_have_class(re.compile("closed"))
    # содержимое без потерь после разворота
    spoiler.locator(".spoiler-title").click()
    expect(spoiler.locator(".spoiler-body")).to_contain_text("Содержимое тела")
    # клик по телу не сворачивает
    spoiler.locator(".spoiler-body").click()
    expect(spoiler).to_have_class(re.compile("open"))
    assert page_errors == []


def test_tc_rich_003_spoiler_in_cell_compact_not_saved(editor_page, qa, web_base_url):
    """TC-rich-003 (Must): спойлер в ячейке компакт; компакт-маркер в контент
    НЕ пишется."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Таблица").click()
    cell = editor.area.locator("tbody tr").nth(0).locator("td").nth(0)
    cell.click()
    editor.toolbar_button("Спойлер").click()

    spoiler = editor.area.locator("td .spoiler")
    expect(spoiler).to_have_class(re.compile("rich-compact"))
    spoiler.locator(".spoiler-body").click()
    page.keyboard.type("В ячейке")

    editor.title_input.fill("QA-003 компакт")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved = qa.get(pid)
    assert "rich-compact" not in saved  # компактность не хранится
    assert 'data-block="spoiler"' in saved and "В ячейке" in saved

    cell_spoiler = page.locator(".article-body td .spoiler")
    expect(cell_spoiler).to_have_class(re.compile("rich-compact"))  # при активации
    cell_spoiler.locator(".spoiler-head").click()
    expect(cell_spoiler).to_have_class(re.compile("closed"))
    cell_spoiler.locator(".spoiler-head").click()
    expect(cell_spoiler.locator(".spoiler-body")).to_contain_text("В ячейке")


def test_tc_rich_004_spoiler_in_spoiler_independent(editor_page, qa, web_base_url):
    """TC-rich-004 (Must): вложенные спойлеры независимы, контент без потерь,
    в контенте вложенный spoiler внутри body."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Спойлер").click()
    outer = editor.area.locator(".spoiler").nth(0)
    outer.locator(".spoiler-title").click()
    outer.locator(".spoiler-title-input").fill("Внешний")
    outer.locator(".spoiler-title-input").press("Enter")
    outer.locator(".spoiler-body").click()
    page.keyboard.type("Текст внешний")
    editor.toolbar_button("Спойлер").click()
    inner = outer.locator(".spoiler")
    expect(inner).to_have_count(1)
    inner.locator(".spoiler-title").click()
    inner.locator(".spoiler-title-input").fill("Внутренний")
    inner.locator(".spoiler-title-input").press("Enter")
    inner.locator(".spoiler-body").click()
    page.keyboard.type("Текст внутренний")

    editor.title_input.fill("QA-004 вложенные")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved = qa.get(pid)
    assert 'data-title="Внутренний"' in saved
    # вложенный спойлер — внутри тела внешнего (урок rich-v1: без потерь)
    assert '<p>Текст внешний</p><div data-block="spoiler" data-title="Внутренний">' in saved
    assert "Текст внешний" in saved and "Текст внутренний" in saved

    body = page.locator(".article-body")
    nested = body.locator(".spoiler .spoiler")
    expect(nested).to_have_count(1)
    nested.locator(".spoiler-head").click()
    expect(nested).to_have_class(re.compile("closed"))
    body.locator(".spoiler").first.locator("> .spoiler-head").click()
    expect(nested.locator(".spoiler-body")).to_be_hidden()
    body.locator(".spoiler").first.locator("> .spoiler-head").click()
    expect(nested).to_have_class(re.compile("closed"))  # состояние внутреннего живо
    expect(nested.locator(".spoiler-body")).to_contain_text("Текст внутренний")


def test_tc_rich_005_collapsed_spoiler_keeps_content_no_state(editor_page, qa, web_base_url):
    """TC-rich-005 (Must): свернутый в редакторе спойлер сохраняет тело;
    состояние отображения в контенте не хранится."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Спойлер").click()
    spoiler = editor.area.locator(".spoiler")
    page.keyboard.type("Секретный текст")
    spoiler.locator(".spoiler-caret").click()
    expect(spoiler).to_have_class(re.compile("closed"))

    editor.title_input.fill("QA-005 свернутый")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved = qa.get(pid)
    assert "Секретный текст" in saved
    assert "closed" not in saved and "collapsed" not in saved

    page.goto(f"{web_base_url}/wiki/{pid}")
    article = page.locator(".article-body .spoiler")
    expect(article).to_have_class(re.compile("open"))
    expect(article.locator(".spoiler-body")).to_contain_text("Секретный текст")

    editor.open_edit(web_base_url, pid)
    expect(page.locator(".editor-area .spoiler-body")).to_contain_text(
        "Секретный текст"
    )


# ---------------------------------------------------------------------------
# Блок кода (FR-119): TC-rich-006..009
# ---------------------------------------------------------------------------


PY_CODE = 'def calc(x):\n    name = "wiki"\n    total = 42\n    # итог\n    return x + 1'


def test_tc_rich_006_code_python_highlight_numbers_clean_db(editor_page, qa, web_base_url):
    """TC-rich-006 (Must): язык python, подсветка ключ/строки/числа/коммент,
    нумерация; в БД чистый текст без tok-спанов."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Блок кода").click()
    block = editor.area.locator(".codeblock")
    expect(block.locator(".codeblock-lang")).to_contain_text("python")

    page.keyboard.type(PY_CODE)
    editor.title_input.fill("QA-006 код python")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])

    saved = qa.get(pid)
    assert 'data-lang="python"' in saved
    assert PY_CODE in saved
    assert "tok-" not in saved  # подсветка не хранится

    article = page.locator(".article-body .codeblock")
    expect(article.locator(".codeblock-nums")).to_have_text(
        "1\n2\n3\n4\n5"
    )
    for cls in ("tok-kw", "tok-str", "tok-num", "tok-com"):
        expect(article.locator(f".{cls}").first).to_be_visible()
    expect(article.locator("code")).to_contain_text("return x + 1")


def test_tc_rich_007_copy_clean_text_and_revert(editor_page, qa, web_base_url):
    """TC-rich-007 (Should): «Копировать» — чистый textContent без номеров/
    спанов; «✓ Скопировано» ~1,5 с, затем исходная надпись (clipboard —
    стаб writeText: реальный Clipboard API не тестируем)."""
    code = "def calc():\n    total = 41\n    name = 'qa'\n    # строка\n    return total + 1"
    pid = qa.make(
        "QA-007 копировать",
        f'<div data-block="code" data-lang="python"><pre><code>{code}</code></pre></div>',
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{pid}")
    block = page.locator(".article-body .codeblock")
    expect(block.locator(".tok-kw").first).to_be_visible()

    page.evaluate(
        "navigator.clipboard.writeText = (t) => "
        "{ window.__copiedText = t; return Promise.resolve(); };"
    )
    block.locator(".copy-btn").click()
    expect(block.locator(".copy-btn")).to_have_text("✓ Скопировано")
    assert page.evaluate("window.__copiedText") == code  # без номеров и спанов
    page.wait_for_timeout(1700)
    expect(block.locator(".copy-btn")).to_have_text("Копировать")


def test_tc_rich_008_code_inside_spoiler_no_loss_copy(editor_page, qa, web_base_url):
    """TC-rich-008 (Must): код в спойлере — toggle без потери символа,
    копирование работает, вложение в контенте."""
    code = "def run():\n    a = 1\n    b = 2\n    # счет\n    return a + b + 1"
    pid = qa.make(
        "QA-008 код в спойлере",
        SPOILER.format(
            t="Скрипт",
            b=f'<div data-block="code" data-lang="python"><pre><code>{code}</code></pre></div>',
        ),
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{pid}")
    spoiler = page.locator(".article-body .spoiler")
    block = spoiler.locator(".codeblock")
    expect(block.locator(".tok-kw").first).to_be_visible()
    before = block.locator("code").evaluate("el => el.textContent")

    spoiler.locator(".spoiler-head").click()
    expect(block).to_be_hidden()
    spoiler.locator(".spoiler-head").click()
    after = block.locator("code").evaluate("el => el.textContent")
    assert before == after == code  # ни символа не потеряно

    page.evaluate(
        "navigator.clipboard.writeText = (t) => "
        "{ window.__copiedText = t; return Promise.resolve(); };"
    )
    block.locator(".copy-btn").click()
    assert page.evaluate("window.__copiedText") == code

    saved = qa.get(pid)
    assert saved.index('data-block-part="body"') < saved.index('data-block="code"')


def test_tc_rich_009_unknown_lang_plain_no_errors(editor_page, qa, page_errors, web_base_url):
    """TC-rich-009 (Should): data-lang="cobol" — plain без подсветки, текст
    посимвольно цел, консоль чистая (GET-часть — в api-сьюте)."""
    pid = qa.make(
        "QA-009 cobol",
        '<div data-block="code" data-lang="cobol"><pre><code>'
        "MOVE A TO B.\nDISPLAY A.</code></pre></div>",
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{pid}")
    block = page.locator(".article-body .codeblock")
    expect(block.locator(".tok-kw")).to_have_count(0)
    assert block.locator("code").evaluate("el => el.textContent") == "MOVE A TO B.\nDISPLAY A."
    assert page_errors == []


# ---------------------------------------------------------------------------
# Табуляция (FR-120): TC-rich-010..013
# ---------------------------------------------------------------------------


def _tabs_content(titles_bodies):
    parts = "".join(
        f'<div data-block-part="tab" data-title="{t}"><p>{b}</p></div>'
        for t, b in titles_bodies
    )
    return f'<div data-block="tabs">{parts}</div>'


def test_tc_rich_010_tabs_switching_in_article(editor_page, qa, page_errors, web_base_url):
    """TC-rich-010 (Must): переключение вкладок в статье, активная не
    сохраняется (открывается первая)."""
    pid = qa.make(
        "QA-010 табы",
        _tabs_content([("Обзор", "маркер-обзор"), ("Детали", "маркер-детали"),
                       ("Пример", "маркер-пример")]),
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{pid}")
    widget = page.locator(".article-body .tabswidget")
    tabs = widget.locator(".tab")
    expect(tabs).to_have_count(3)
    expect(widget.locator(".tab-pane").first).to_contain_text("маркер-обзор")

    tabs.nth(1).click()
    expect(tabs.nth(1)).to_have_class(re.compile("active"))
    expect(widget.locator(".tab-pane").nth(1)).to_contain_text("маркер-детали")
    expect(widget.locator(".tab-pane").first).to_be_hidden()

    tabs.nth(2).click()
    expect(widget.locator(".tab-pane").nth(2)).to_contain_text("маркер-пример")
    tabs.nth(0).click()
    expect(widget.locator(".tab-pane").first).to_contain_text("маркер-обзор")
    assert page_errors == []
    # активная вкладка не сохранена: перезагрузка — снова первая
    page.reload()
    widget2 = page.locator(".article-body .tabswidget")
    expect(widget2.locator(".tab").first).to_have_class(re.compile("active"))


def test_tc_rich_011_tabs_add_rename_delete_last_protected(editor_page, qa, web_base_url):
    """TC-rich-011 (Must): «+», dblclick-rename, удаление крестиком,
    единственную удалить нельзя; статья показывает итог."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Табуляция").click()
    widget = editor.area.locator(".tabswidget")
    expect(widget.locator(".tab")).to_have_count(2)

    # привести к одной «Обзор»
    first = widget.locator(".tab").nth(0)
    # переименование dblclick первой
    first.dblclick()
    rename = widget.locator(".tab-rename")
    expect(rename).to_be_visible()
    rename.fill("Обзор")
    rename.press("Enter")
    # удалить вторую
    widget.locator(".tab").nth(1).locator(".tab-close").dispatch_event("click")
    expect(widget.locator(".tab")).to_have_count(1)

    # «+» → новая, dblclick → «Детали»
    widget.locator(".tab-add").click()
    expect(widget.locator(".tab")).to_have_count(2)
    second = widget.locator(".tab").nth(1)
    second.dblclick()
    rename = widget.locator(".tab-rename")
    expect(rename).to_be_visible()
    rename.fill("Детали")
    rename.press("Enter")
    expect(second).to_contain_text("Детали")

    # удалить «Обзор» — можно (осталась одна)
    widget.locator(".tab").nth(0).locator(".tab-close").dispatch_event("click")
    expect(widget.locator(".tab")).to_have_count(1)
    # единственную удалить нельзя: крестик скрыт (CSS :only-of-type)
    widget.locator(".tab").nth(0).hover()
    widget.locator(".tab").nth(0).locator(".tab-close").dispatch_event("click")
    expect(widget.locator(".tab")).to_have_count(1)
    assert not widget.locator(".tab .tab-close").first.is_visible()

    editor.title_input.fill("QA-011 табы")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved = qa.get(pid)
    assert "Обзор" not in saved and 'data-title="Детали"' in saved
    article_tabs = page.locator(".article-body .tab")
    expect(article_tabs).to_have_count(1)
    expect(article_tabs.first).to_contain_text("Детали")


def test_tc_rich_012_tabs_limit8_overflow_scroll(editor_page, qa, web_base_url):
    """TC-rich-012 (Must, ОВ-3): лимит 8 (9-я не создается), переполненный
    таб-бар скроллится горизонтально; в контенте ровно 8 tab-частей."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Табуляция").click()
    widget = editor.area.locator(".tabswidget")

    for _ in range(6):  # старт 2 → 8
        widget.locator(".tab-add").click()
    expect(widget.locator(".tab")).to_have_count(8)
    expect(widget.locator(".tab-add")).to_be_disabled()
    widget.locator(".tab-add").click(force=True)  # 9-я попытка (disabled)
    expect(widget.locator(".tab")).to_have_count(8)

    # длинные названия (30+ символов)
    page.evaluate(
        """() => {
          const bar = document.querySelector('.editor-area .tabbar');
          bar.querySelectorAll('.tab').forEach((tab, i) => {
            if (!tab.querySelector('input')) {
              tab.firstChild.textContent = 'Длинное название вкладки номер ' + (i + 1) + ' для скролла';
            }
          });
        }"""
    )
    page.set_viewport_size({"width": 1024, "height": 800})
    overflow = page.evaluate(
        """() => {
          const bar = document.querySelector('.editor-area .tabbar');
          return {
            overflow: getComputedStyle(bar).overflowX,
            scrolls: bar.scrollWidth > bar.clientWidth,
            wrap: getComputedStyle(bar).flexWrap,
          };
        }"""
    )
    assert overflow["overflow"] == "auto"
    assert overflow["scrolls"]
    assert overflow["wrap"] in ("nowrap", "normal")  # без выпадающего списка

    editor.title_input.fill("QA-012 лимит табов")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    assert qa.get(pid).count('data-block-part="tab"') == 8


def test_tc_rich_013_tabs_inside_tab_editor_insert(editor_page, qa, web_base_url):
    """TC-rich-013 (Must): табы внутри вкладки через тулбар; 4 таб-части в
    контенте, виджеты независимы."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Табуляция").click()
    outer = editor.area.locator(".tabswidget").first
    page.keyboard.type("В1.1")  # каретка в первой вкладке внешнего

    editor.toolbar_button("Табуляция").click()  # вложенный виджет в той же вкладке
    inner = outer.locator(".tabswidget")
    expect(inner).to_have_count(1)
    page.keyboard.type("В2.1")
    inner.locator("> .tabbar > .tab").nth(1).click()
    page.keyboard.type("В2.2")

    outer.locator("> .tabbar > .tab").nth(1).click()
    page.keyboard.type("В1.2")

    editor.title_input.fill("QA-013 табы в табе")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved = qa.get(pid)
    assert saved.count('data-block="tabs"') == 2
    assert saved.count('data-block-part="tab"') == 4
    for m in ("В1.1", "В1.2", "В2.1", "В2.2"):
        assert m in saved, m

    body = page.locator(".article-body")
    ow = body.locator(".tabswidget").first
    iw = ow.locator(".tabswidget")
    # независимость: переключили внутренний — внешний на первой
    iw.locator("> .tabbar > .tab").nth(1).click()
    expect(iw.locator("> .tab-pane").nth(1)).to_contain_text("В2.2")
    expect(ow.locator("> .tab-pane").first).to_contain_text("В1.1")
    # переключили внешний — внутренний остался на второй
    ow.locator("> .tabbar > .tab").nth(1).click()
    expect(ow.locator("> .tab-pane").nth(1)).to_contain_text("В1.2")
    expect(iw.locator("> .tabbar > .tab").nth(1)).to_have_class(re.compile("active"))


# ---------------------------------------------------------------------------
# H-переключатель (FR-121): TC-rich-014..017
# ---------------------------------------------------------------------------


def _pressed_labels(editor, labels=("Заголовок 1", "Заголовок 2", "Заголовок 3")):
    return [
        lb for lb in labels
        if editor.toolbar_button(lb).get_attribute("aria-pressed") == "true"
    ]


def expect_pressed(editor, expected):
    """aria-pressed следует за курсором с задержкой selectionchange —
    поллинг до 1 с (факт: мгновенное чтение сразу после клика гонится)."""
    labels = ("Заголовок 1", "Заголовок 2", "Заголовок 3")
    current = None
    for _ in range(20):
        current = [
            lb for lb in labels
            if editor.toolbar_button(lb).get_attribute("aria-pressed") == "true"
        ]
        if current == expected:
            return
        editor.page.wait_for_timeout(50)
    assert current == expected, f"ожидались {expected}, факт {current}"


def _fill_cell(page, cell, text):
    """Заменить содержимое ячейки детерминированно (клик ставит каретку
    в середину текста «Колонка N» или под overlay панели)."""
    cell.evaluate(
        """(el, t) => {
          el.textContent = t;
          el.dispatchEvent(new InputEvent('input', {bubbles: true}));
        }""",
        text,
    )


def test_tc_rich_014_h2_reclick_clears_undo_alive(editor_page, web_base_url):
    """TC-rich-014 (Must, F4): повторный H2 снимает без потери текста,
    все H отжаты, Ctrl+Z возвращает H2."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("Текст заголовка")
    editor.select_all_text()
    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_text("Текст заголовка")

    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_count(0)
    expect(editor.area).to_contain_text("Текст заголовка")
    assert _pressed_labels(editor) == []

    page.keyboard.press("Control+Z")
    expect(editor.area.locator("h2")).to_have_text("Текст заголовка")
    assert _pressed_labels(editor) == ["Заголовок 2"]


def test_tc_rich_015_h1_to_h3_single_undo(editor_page, web_base_url):
    """TC-rich-015 (Must): H1 → H3 одной кнопкой; нажата ровно H3; Ctrl+Z
    откатывает замену уровня."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("Строка")
    editor.select_all_text()
    editor.toolbar_button("Заголовок 1").click()
    expect(editor.area.locator("h1")).to_have_count(1)

    editor.toolbar_button("Заголовок 3").click()
    expect(editor.area.locator("h3")).to_have_text("Строка")
    expect(editor.area.locator("h1")).to_have_count(0)
    assert _pressed_labels(editor) == ["Заголовок 3"]

    page.keyboard.press("Control+Z")
    expect(editor.area.locator("h1")).to_have_text("Строка")


def test_tc_rich_016_backspace_empty_heading(editor_page, web_base_url):
    """TC-rich-016 (Must, ОВ-5): Backspace в пустом H2 → пустой абзац с
    курсором; сторожевой текст предыдущего абзаца цел; H-кнопки отжаты."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("Сторожевой абзац")
    page.keyboard.press("Enter")
    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_count(1)

    page.keyboard.press("Backspace")
    expect(editor.area.locator("h2")).to_have_count(0)
    expect(editor.area.locator("p").last).to_have_text("")  # пустой абзац
    expect(editor.area).to_contain_text("Сторожевой абзац")  # сторож цел
    # каретка в пустом абзаце
    caret_p = page.evaluate(
        """() => {
          const n = window.getSelection().anchorNode;
          const e = n && (n.nodeType === 1 ? n : n.parentNode);
          return e && e.closest ? e.closest('p, h1, h2, h3')?.tagName : null;
        }"""
    )
    assert caret_p == "P"
    assert _pressed_labels(editor) == []


def test_tc_rich_017_h_buttons_follow_caret(editor_page, web_base_url):
    """TC-rich-017 (Should): aria-pressed отражает блок под курсором (H1 →
    только H1; H2 → только H2; абзац → никого)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("Первый")
    editor.toolbar_button("Заголовок 1").click()
    page.keyboard.press("End")
    page.keyboard.press("Enter")
    page.keyboard.type("Второй")
    page.keyboard.press("Enter")
    page.keyboard.type("Обычный")

    # H2 на второй блок (Enter после заголовка создает div)
    blocks0 = editor.area.locator("h1, h2, h3, p, div:not([data-editor])")
    blocks0.nth(1).click()
    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_count(1)

    blocks = editor.area.locator("h1, h2, h3, p, div:not([data-editor])")
    blocks.nth(0).click()
    expect_pressed(editor, ["Заголовок 1"])
    blocks.nth(1).click()
    expect_pressed(editor, ["Заголовок 2"])
    blocks.nth(2).click()
    expect_pressed(editor, [])


# ---------------------------------------------------------------------------
# Таблицы (FR-122): TC-rich-018..021
# ---------------------------------------------------------------------------


def test_tc_rich_018_table_add_remove_relative_to_cell(editor_page, qa, web_base_url):
    """TC-rich-018 (Must): +строка ниже / +столбец правее целевой ячейки,
    целевой столбец подсвечен; − удаляет добавленные; GET 3×3 исходный."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Таблица").click()
    panel = editor.area.locator(".tbl-panel")

    # заполнить 3×3 маркерами rNcM
    for r in range(3):
        row = editor.area.locator("tr").nth(r)
        for c in range(3):
            cell = row.locator("th, td").nth(c)
            _fill_cell(page, cell, f"r{r}c{c}")

    target = editor.area.locator("tbody tr").nth(0).locator("td").nth(1)  # [2,2]
    target.click()
    panel.get_by_role("button", name="Добавить строку ниже").click()
    expect(editor.area.locator("tr")).to_have_count(4)
    # целевой столбец подсвечен (кластер столбцовых операций у левой границы)
    target = editor.area.locator("tbody tr").nth(0).locator("td").nth(1)
    target.click()
    col_pos = page.evaluate(
        """() => {
          const area = document.querySelector('.editor-area');
          const cell = area.querySelectorAll('tbody td')[1];
          const col = area.querySelector('.tbl-col-ops');
          return { dx: cell.getBoundingClientRect().left - col.getBoundingClientRect().left,
                   above: cell.getBoundingClientRect().top - col.getBoundingClientRect().bottom };
        }"""
    )
    assert abs(col_pos["dx"] - 26) < 20, col_pos
    assert col_pos["above"] > 0, col_pos
    panel.get_by_role("button", name="Добавить столбец справа").click()
    expect(editor.area.locator("thead th")).to_have_count(4)

    # добавленные строка/столбец: пустые (по факту вставки) → находим по
    # пустоте и заполняем маркерами
    shape = page.evaluate(
        """() => {
          const t = document.querySelector('.editor-area table');
          const rows = [...t.querySelectorAll('tbody tr')];
          let addedRow = -1;
          rows.forEach((tr, i) => {
            const cells = [...tr.querySelectorAll('td')];
            if (cells.length && cells.every(c => !c.textContent.trim())) addedRow = i;
          });
          const heads = [...t.querySelectorAll('thead th')];
          let addedCol = -1;
          heads.forEach((th, i) => { if (!th.textContent.trim()) addedCol = i; });
          return { addedRow, addedCol };
        }"""
    )
    assert shape["addedRow"] >= 0 and shape["addedCol"] >= 0, shape
    for c in range(4):
        _fill_cell(
            page,
            editor.area.locator("tbody tr").nth(shape["addedRow"]).locator("td").nth(c),
            f"n3c{c}",
        )
    for r in range(3):
        _fill_cell(
            page,
            editor.area.locator("tbody tr").nth(r).locator("td").nth(shape["addedCol"]),
            f"nr{r}4",
        )

    # удалить ДОБАВЛЕННЫЕ строку и столбец (факт пробы: «−» удаляет строку/
    # столбец каретки) — каретка в добавленных
    editor.area.locator("tbody tr").nth(shape["addedRow"]).locator("td").nth(0).click()
    panel.get_by_role("button", name="Удалить строку").click()
    expect(editor.area.locator("tr")).to_have_count(3)
    editor.area.locator("thead th").nth(shape["addedCol"]).click()
    expect(panel).to_be_visible()
    panel.get_by_role("button", name="Удалить столбец").click()
    expect(editor.area.locator("thead th")).to_have_count(3)

    editor.title_input.fill("QA-018 таблица")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved = qa.get(pid)
    assert saved.count("<tr>") == 3 and saved.count("<th>") == 3
    for r in range(3):
        for c in range(3):
            assert f"r{r}c{c}" in saved
    assert "n3c" not in saved and "nr" not in saved


def test_tc_rich_019_last_row_col_not_deletable(editor_page, qa, web_base_url):
    """TC-rich-019 (Must): в 1×1 кнопки «−» disabled с подсказкой, таблица
    не исчезает; после сохранения ячейка на месте."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Таблица").click()
    panel = editor.area.locator(".tbl-panel")
    for _ in range(10):
        rows = editor.area.locator("tr").count()
        cols = editor.area.locator("tr").first.locator("th,td").count()
        if rows > 1:
            editor.area.locator("tbody tr").nth(0).locator("td").nth(0).click()
            panel.get_by_role("button", name="Удалить строку").click()
        elif cols > 1:
            editor.area.locator("thead th").first.click()
            panel.get_by_role("button", name="Удалить столбец").click()
        else:
            break
    expect(editor.area.locator("tr")).to_have_count(1)
    editor.area.locator("thead th").first.click()
    expect(panel).to_be_visible()

    del_row = panel.get_by_role("button", name="Последнюю строку удалить нельзя")
    del_col = panel.get_by_role("button", name="Последний столбец удалить нельзя")
    expect(del_row).to_be_disabled()
    expect(del_col).to_be_disabled()
    del_row.click(force=True)
    del_col.click(force=True)
    expect(editor.area.locator("table")).to_have_count(1)
    expect(editor.area.locator("tr")).to_have_count(1)

    _fill_cell(page, editor.area.locator("thead th").first, "Единственная ячейка")
    editor.title_input.fill("QA-019 один на один")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved = qa.get(pid)
    assert "Единственная ячейка" in saved and "<table>" in saved
    expect(page.locator(".article-body table")).to_have_count(1)


def test_tc_rich_020_delete_table_whole_button(editor_page, qa, web_base_url):
    """TC-rich-020 (Must, ОВ-4): «Удалить таблицу» снимает таблицу целиком,
    сторожа целы; «−» таблицу целиком не удаляют."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("Сторож ДО")
    editor.toolbar_button("Таблица").click()
    panel = editor.area.locator(".tbl-panel")
    for r in range(2):
        for c in range(2):
            cell = editor.area.locator("tr").nth(r).locator("th, td").nth(c)
            _fill_cell(page, cell, f"x{r}{c}")
    _caret_to_end(page)
    page.keyboard.type("Сторож ПОСЛЕ")

    editor.area.locator("tbody tr").nth(0).locator("td").nth(0).click()
    panel.get_by_role("button", name="Удалить таблицу целиком").click()
    expect(editor.area.locator("table")).to_have_count(0)
    expect(editor.area).to_contain_text("Сторож ДО")
    expect(editor.area).to_contain_text("Сторож ПОСЛЕ")

    editor.title_input.fill("QA-020 удалить таблицу")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved = qa.get(pid)
    assert "<table" not in saved and "Сторож ДО" in saved and "Сторож ПОСЛЕ" in saved
    expect(page.locator(".article-body table")).to_have_count(0)

    # шаг 4: «−» не удаляют таблицу целиком (свежая страница — повтор шага 1)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("Сторож ДО")
    editor.toolbar_button("Таблица").click()
    panel = editor.area.locator(".tbl-panel")
    _fill_cell(page, editor.area.locator("tr").nth(0).locator("th, td").nth(0), "y00")
    for _ in range(12):
        rows = editor.area.locator("tr").count()
        cols = editor.area.locator("tr").first.locator("th,td").count()
        if rows == 1 and cols == 1:
            break
        if rows > 1:
            editor.area.locator("tbody tr").nth(0).locator("td").nth(0).click()
            expect(panel).to_be_visible(timeout=5000)
            panel.get_by_role("button", name="Удалить строку").click()
        else:
            editor.area.locator("thead th").first.click()
            expect(panel).to_be_visible(timeout=5000)
            panel.get_by_role("button", name="Удалить столбец").click()
    expect(editor.area.locator("table")).to_have_count(1)  # 1×1 жива


def test_tc_rich_021_enter_br_in_cell_tab_navigation(editor_page, qa, web_base_url):
    """TC-rich-021 (Must): Enter — перенос ВНУТРИ ячейки (ровно «один<br>два»),
    Tab — следующая ячейка; tr/td не меняются; дискриминатор в БД."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Таблица").click()
    cell = editor.area.locator("tbody tr").nth(0).locator("td").nth(0)
    cell.click()
    page.keyboard.type("один")
    page.keyboard.press("Enter")
    page.keyboard.type("два")

    cells = editor.area.locator("tbody tr").nth(0).locator("td")
    expect(cells).to_have_count(3)  # новой строки нет
    assert cells.nth(0).evaluate("el => el.innerHTML") == "один<br>два"

    page.keyboard.press("Tab")
    page.keyboard.type("следующая")
    caret_cell = page.evaluate(
        """() => {
          const n = window.getSelection().anchorNode;
          const e = n && (n.nodeType === 1 ? n : n.parentNode);
          return e && e.closest ? e.closest('td,th')?.textContent : '';
        }"""
    )
    assert "следующая" in caret_cell

    editor.title_input.fill("QA-021 enter в ячейке")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved = qa.get(pid)
    assert "один<br>два" in saved
    assert "одиндва" not in saved and "один<br><br>два" not in saved
    assert saved.count("<tr>") == 3  # 1 thead + 2 tbody — не изменилось
    article_cell = page.locator(".article-body tbody tr").nth(0).locator("td").nth(0)
    expect(article_cell.locator("br")).to_have_count(1)


# ---------------------------------------------------------------------------
# Безопасность/деградация (NFR-39): TC-rich-022..025
# ---------------------------------------------------------------------------


def test_tc_rich_022_xss_in_spoiler_neutralized(editor_page, qa, page_errors, web_base_url):
    """TC-rich-022 (Must): script с содержимым и onclick вырезаны ДО рендера,
    спойлер жив, toggle без исполнения (GET-часть — в api-сьюте)."""
    pid = qa.make(
        "QA-022 xss спойлер",
        '<div data-block="spoiler" data-title="X" onclick="alert(2)">'
        '<div data-block-part="body"><script>window.__xss=1</script>'
        "<p>тело</p></div></div>",
    )
    saved = qa.get(pid)
    assert "script" not in saved and "alert" not in saved and "onclick" not in saved

    page = editor_page
    page.goto(f"{web_base_url}/wiki/{pid}")
    spoiler = page.locator(".article-body .spoiler")
    expect(spoiler.locator(".spoiler-body")).to_contain_text("тело")
    spoiler.locator(".spoiler-head").click()
    expect(spoiler).to_have_class(re.compile("closed"))
    assert page.evaluate("window.__xss === undefined")
    assert page_errors == []


def test_tc_rich_023_forged_data_attrs_degrade(editor_page, qa, page_errors, web_base_url):
    """TC-rich-023 (Must): data-block="evil"/data-lang="javascript" сняты,
    текст — обычный контент, исполнения нет."""
    pid = qa.make(
        "QA-023 подмена", '<div data-block="evil" data-lang="javascript">текст</div>'
    )
    saved = qa.get(pid)
    assert 'data-block="evil"' not in saved and 'data-lang="javascript"' not in saved

    page = editor_page
    page.goto(f"{web_base_url}/wiki/{pid}")
    expect(page.locator(".article-body")).to_contain_text("текст")
    assert page.locator(".article-body .spoiler, .article-body .codeblock").count() == 0
    assert page_errors == []


def _chain(n: int) -> str:
    inner = ""
    for i in range(n, 0, -1):
        inner = SPOILER.format(t=f"У{i}", b=f"<p>У{i}</p>{inner}")
    return inner


def test_tc_rich_024_depth_7_unwrap_vs_depth_5(editor_page, qa, page_errors, web_base_url):
    """TC-rich-024 (Must): цепочка 7 — первые 5 спойлеры, 6-7 unwrap без
    потери текста; цепочка 5 — все спойлеры."""
    pid7 = qa.make("QA-024 глубина 7", _chain(7))
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{pid7}")
    body = page.locator(".article-body")
    expect(body.locator(".spoiler")).to_have_count(5)
    for i in range(1, 8):
        expect(body).to_contain_text(f"У{i}")
    # уровня 6-7 — без виджета
    assert body.locator('[data-title="У6"], [data-title="У7"]').count() == 0
    # верхние уровни toggle'ятся
    body.locator(".spoiler").first.locator("> .spoiler-head").click()
    expect(body.locator(".spoiler").first).to_have_class(re.compile("closed"))
    assert page_errors == []

    pid5 = qa.make("QA-024 глубина 5", _chain(5))
    page.goto(f"{web_base_url}/wiki/{pid5}")
    expect(page.locator(".article-body .spoiler")).to_have_count(5)
    assert page_errors == []


def test_tc_rich_025_unknown_block_degrades_neighbor_alive(editor_page, qa, page_errors, web_base_url):
    """TC-rich-025 (Should): неизвестный блок — контент виден без виджета и
    ошибок; соседний спойлер работает."""
    pid = qa.make(
        "QA-025 future-widget",
        SPOILER.format(t="Рабочий", b="<p>сосед</p>")
        + '<div data-block="future-widget">Будущее содержимое</div>',
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{pid}")
    body = page.locator(".article-body")
    expect(body).to_contain_text("Будущее содержимое")
    assert body.locator('[data-block="future-widget"] .spoiler-head').count() == 0
    spoiler = body.locator(".spoiler")
    spoiler.locator(".spoiler-head").click()
    expect(spoiler).to_have_class(re.compile("closed"))
    assert page_errors == []


# ---------------------------------------------------------------------------
# Рендер (NFR-40): TC-rich-026..028
# ---------------------------------------------------------------------------


def test_tc_rich_026_no_external_requests_on_article(editor_page, qa, page_errors, web_base_url):
    """TC-rich-026 (Must): статья с блоками — все запросы только к своему
    origin, интерактив работает (ОГР-8)."""
    content = (
        SPOILER.format(t="Сп", b="<p>тело</p>")
        + '<div data-block="code" data-lang="python"><pre><code>print(1)</code></pre></div>'
        + _tabs_content([("В1", "один"), ("В2", "два")])
    )
    pid = qa.make("QA-026 без CDN", content)
    page = editor_page
    external: list[str] = []
    page.on(
        "request",
        lambda req: external.append(req.url)
        if not req.url.startswith(web_base_url)
        else None,
    )
    page.goto(f"{web_base_url}/wiki/{pid}")
    body = page.locator(".article-body")
    expect(body.locator(".tok-kw").first).to_be_visible()
    body.locator(".spoiler-head").click()
    body.locator(".tab").nth(1).click()
    page.evaluate(
        "navigator.clipboard.writeText = (t) => Promise.resolve();"
    )
    body.locator(".copy-btn").click()
    expect(body.locator(".copy-btn")).to_have_text("✓ Скопировано")
    assert external == []
    assert page_errors == []


def test_tc_rich_027_activation_20_blocks_under_150ms(editor_page, qa, page_errors, web_base_url):
    """TC-rich-027 (Should): 20 блоков с листингом 1000+ строк — активация
    ≤150 мс (максимум из 3 прогонов). Замер JS-метками: t(первый tok-span) −
    t(начало парсинга body) — включает загрузку локальных модулей, т.е.
    оценка сверху. Прокрутка сразу после загрузки отвечает."""
    listing = "\n".join(f"if x{i} > {i}:  # строка {i}" for i in range(1200))
    parts = []
    for i in range(19):
        parts.append(SPOILER.format(t=f"С{i}", b=f"<p>блок {i}</p>"))
    parts.append(
        f'<div data-block="code" data-lang="python"><pre><code>{listing}</code></pre></div>'
    )
    pid = qa.make("QA-027 перф", "".join(parts))

    page = editor_page
    page.add_init_script(
        """() => {
          window.__tBody = null; window.__tAct = null;
          const mo = new MutationObserver(() => {
            if (window.__tBody === null && document.body) {
              window.__tBody = performance.now();
            }
            if (window.__tAct === null && document.querySelector('.tok-kw')) {
              window.__tAct = performance.now();
              mo.disconnect();
            }
          });
          mo.observe(document.documentElement, {childList: true, subtree: true});
        }"""
    )
    worst = 0.0
    for _ in range(3):
        page.goto(f"{web_base_url}/wiki/{pid}", wait_until="load")
        expect(page.locator(".article-body .tok-kw").first).to_be_visible(
            timeout=30_000
        )
        measures = page.evaluate(
            "({act: window.__tAct - window.__tBody, body: window.__tBody})"
        )
        assert measures["act"] is not None
        worst = max(worst, measures["act"])
        # прокрутка сразу после активации отвечает (не заморожена)
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(50)
        scroll_y = page.evaluate("window.scrollY")
        assert scroll_y > 0
    assert worst <= 150, f"активация {worst:.0f} мс > 150 мс"
    assert page_errors == []


def test_tc_rich_028_plain_article_unchanged(editor_page, qa, page_errors, web_base_url):
    """TC-rich-028 (Should): статья без rich-блоков — контент байт-в-байт,
    активаций нет, консоль чистая (фикстура контента — из БД стенда через
    API, не рукописный HTML в странице)."""
    plain = (
        "<h2>Регресс-статья</h2><p>Обычный абзац со <b>жирным</b> и "
        "<a href=\"/wiki\">ссылкой</a>.</p><ul><li>пункт 1</li><li>пункт 2</li></ul>"
    )
    pid = qa.make("QA-028 регресс", plain)
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{pid}")
    article_body = page.locator(".article-body")
    expect(article_body).to_have_count(1)  # рендер клиентский (page.js)
    rendered = article_body.evaluate("el => el.innerHTML")
    assert rendered == qa.get(pid) == plain  # байт-в-байт
    assert page.locator(".article-body .spoiler, .article-body .codeblock, "
                        ".article-body .tabswidget").count() == 0
    assert page_errors == []


# ---------------------------------------------------------------------------
# WYSIWYG-редактор: TC-rich-029..033
# ---------------------------------------------------------------------------


def _select_substring(page, needle: str) -> None:
    """Выделить точный фрагмент текста в редакторе (первое вхождение)."""
    found = page.evaluate(
        """(needle) => {
          const area = document.querySelector('.editor-area');
          const walker = document.createTreeWalker(area, NodeFilter.SHOW_TEXT);
          let n;
          while ((n = walker.nextNode())) {
            const i = n.data.indexOf(needle);
            if (i >= 0) {
              const r = document.createRange();
              r.setStart(n, i);
              r.setEnd(n, i + needle.length);
              const s = window.getSelection();
              s.removeAllRanges();
              s.addRange(r);
              return true;
            }
          }
          return false;
        }""",
        needle,
    )
    assert found, f"фрагмент {needle!r} не найден в редакторе"


def _fresh_block(page, editor) -> None:
    """Выйти на свежий верхнеуровневый блок (не li/цитата/таблица):
    факты пробы — Enter внутри li создает li (не выходит); поэтому каретку
    ставим за верхнеуровневым предком и жмем Enter до пустого блока."""
    for _ in range(4):
        state = page.evaluate(
            """() => {
              const n = window.getSelection().anchorNode;
              const e = n && (n.nodeType === 1 ? n : n.parentNode);
              let b = e && e.closest
                ? e.closest('li, blockquote, td, th, table, h1, h2, h3, p, div')
                : null;
              const area = document.querySelector('.editor-area');
              if (!b) return 'nowhere';
              while (b.parentElement && b.parentElement !== area) b = b.parentElement;
              const isTextBlock = b.tagName === 'DIV' || b.tagName === 'P';
              const r = document.createRange();
              if (isTextBlock && !b.textContent.trim()) {
                r.selectNodeContents(b);
                r.collapse(false);
                const s = window.getSelection();
                s.removeAllRanges();
                s.addRange(r);
                return 'fresh';
              }
              if (isTextBlock) {
                r.selectNodeContents(b);
              } else {
                r.setStartAfter(b);
              }
              r.collapse(false);
              const s = window.getSelection();
              s.removeAllRanges();
              s.addRange(r);
              return 'enter';
            }"""
        )
        if state == "fresh":
            return
        page.keyboard.press("Enter")
    # фолбэк: прямой append пустого верхнеуровневого блока + каретка в него
    # (факт пробы: после цитаты Enter из-за блока нестабилен)
    page.evaluate(
        """() => {
          const a = document.querySelector('.editor-area');
          const d = document.createElement('div');
          d.appendChild(document.createElement('br'));
          a.appendChild(d);
          const r = document.createRange();
          r.selectNodeContents(d);
          r.collapse(false);
          const s = window.getSelection();
          s.removeAllRanges();
          s.addRange(r);
        }"""
    )


def test_tc_rich_029_toolbar_roundtrip_wysiwyg(editor_page, qa, web_base_url):
    """TC-rich-029 (Must): тулбар применяет форматирование; статья повторяет
    редактор (структура + тексты; round-trip без артефактов)."""
    from PIL import Image
    import io

    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    area = editor.area
    area.click()

    page.keyboard.type("Заголовок второй")
    editor.select_all_text()
    editor.toolbar_button("Заголовок 2").click()
    page.keyboard.press("End")
    page.keyboard.press("Enter")
    page.keyboard.type("слово жирное и слово кривое в строке")
    _select_substring(page, "жирное")
    editor.toolbar_button("Полужирный").click()
    _select_substring(page, "кривое")
    editor.toolbar_button("Курсив").click()

    # списки и цитата — каждый в своем верхнеуровневом блоке
    _fresh_block(page, editor)
    page.keyboard.type("пункт маркированный")
    editor.toolbar_button("Маркированный список").click()
    _fresh_block(page, editor)
    page.keyboard.type("пункт нумерованный")
    editor.toolbar_button("Нумерованный список").click()
    _fresh_block(page, editor)
    page.keyboard.type("строка цитаты")
    editor.toolbar_button("Цитата").click()
    _fresh_block(page, editor)

    # изображение с диска (PIL-минипнг) — в свежем блоке, до таблицы
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 60, 60)).save(buf, format="PNG")
    editor.toolbar_button("Изображение").click()
    dialog = editor.img_dialog
    expect(dialog).to_be_visible()
    dialog.get_by_text("Загрузить с диска").check()
    editor.img_file_input().set_input_files(
        [{"name": "qa029.png", "mimeType": "image/png", "buffer": buf.getvalue()}]
    )
    expect(area.locator("img")).to_have_count(1)

    # таблица после изображения
    _caret_to_end(page)
    page.keyboard.press("Enter")
    editor.toolbar_button("Таблица").click()
    _fill_cell(page, area.locator("tbody tr").nth(0).locator("td").nth(0), "табличная")

    editor.title_input.fill("QA-029 roundtrip")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])

    body = page.locator(".article-body")
    expect(body.locator("h2").filter(has_text="Заголовок второй")).to_have_text(
        "Заголовок второй"
    )
    expect(body.locator("b").filter(has_text="жирное")).to_contain_text("жирное")
    expect(body.locator("i").filter(has_text="кривое")).to_contain_text("кривое")
    expect(body.locator("ul li").filter(has_text="пункт маркированный")).to_be_visible()
    expect(body.locator("ol li").filter(has_text="пункт нумерованный")).to_be_visible()
    expect(
        body.locator("blockquote").filter(has_text="строка цитаты")
    ).to_contain_text("строка цитаты")
    expect(body.locator("td").filter(has_text="табличная")).to_be_visible()
    expect(body.locator("img")).to_have_count(1)
    expect(body.locator("h2")).to_have_count(1)  # заголовок единственный (нет «залипания»)
    saved = qa.get(pid)
    assert "data-editor" not in saved  # артефактов редактора нет
    for tag in ("<h2>", "<b>", "<i>", "<ul>", "<ol>", "<blockquote>", "<table>", "<img"):
        assert tag in saved, tag


def test_tc_rich_030_toolbar_single_rich_tools_insert(editor_page, web_base_url):
    """TC-rich-030 (Must): тулбар один; Спойлер/Блок кода/Табуляция вставляют
    в позицию курсора с фокусом в содержимом; панель таблицы inline."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("первый абзац")
    page.keyboard.press("Enter")

    editor.toolbar_button("Спойлер").click()
    expect(editor.area.locator(".spoiler")).to_have_count(1)
    # фокус в зоне содержимого — печать сразу попадает в блок
    page.keyboard.type("тело")
    expect(editor.area.locator(".spoiler-body")).to_contain_text("тело")

    page.keyboard.press("Escape")  # выйти из спойлера
    _caret_to_end(page)
    editor.toolbar_button("Блок кода").click()
    expect(editor.area.locator(".codeblock")).to_have_count(1)
    page.keyboard.type("x = 1")
    expect(editor.area.locator(".codeblock code")).to_contain_text("x = 1")

    _caret_to_end(page)
    editor.toolbar_button("Табуляция").click()
    expect(editor.area.locator(".tabswidget")).to_have_count(1)

    _caret_to_end(page)
    editor.toolbar_button("Таблица").click()
    expect(editor.area.locator("table")).to_have_count(1)
    # inline-панель появляется при курсоре в ячейке
    editor.area.locator("tbody tr").nth(0).locator("td").nth(0).click()
    expect(editor.area.locator(".tbl-panel")).to_be_visible()

    # тулбар один, плавающих панелей/вторых рядов нет
    assert page.locator(".toolbar[role=toolbar]").count() == 1
    assert page.locator(".editor-area .toolbar").count() == 0


def test_tc_rich_031_h_buttons_never_double_pressed(editor_page, web_base_url):
    """TC-rich-031 (Must): снятие/замена/быстрые клики в разных абзацах —
    нажата максимум одна H-кнопка (регресс «залипания»)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("Абзац один")
    editor.select_all_text()
    editor.toolbar_button("Заголовок 1").click()
    expect(editor.area.locator("h1")).to_have_count(1)
    page.keyboard.press("End")
    page.keyboard.press("Enter")  # после H1 создает div (факт пробы)
    page.keyboard.type("Абзац два")
    blocks = editor.area.locator("h1, h2, h3, p, div:not([data-editor])")

    blocks.nth(0).click()
    expect_pressed(editor, ["Заголовок 1"])
    editor.toolbar_button("Заголовок 1").click()  # снятие
    expect_pressed(editor, [])
    editor.toolbar_button("Заголовок 2").click()
    expect_pressed(editor, ["Заголовок 2"])
    editor.toolbar_button("Заголовок 3").click()
    expect_pressed(editor, ["Заголовок 3"])

    # быстрые смены: H1 в первом, сразу H2 во втором
    blocks = editor.area.locator("h1, h2, h3, p, div:not([data-editor])")
    blocks.nth(0).click()
    editor.toolbar_button("Заголовок 1").click()
    blocks.nth(1).click()
    editor.toolbar_button("Заголовок 2").click()
    expect_pressed(editor, ["Заголовок 2"])  # ровно одна
    blocks.nth(0).click()
    expect_pressed(editor, ["Заголовок 1"])  # следует за курсором
    blocks.nth(1).click()
    expect_pressed(editor, ["Заголовок 2"])


def test_tc_rich_032_undo_redo_three_ops(editor_page, web_base_url):
    """TC-rich-032 (Must): undo/redo последовательности правок разных типов,
    включая снятие заголовка повторным кликом и замену H1→H3 (F4); текст не
    теряется и не дублируется. H-клики дают по несколько шагов нативного
    undo-стека — цикл undo до исходного состояния, redo обратно."""

    def snapshot():
        html = editor.area.evaluate("el => el.innerHTML")
        text = editor.area.evaluate("el => el.textContent")
        return {
            "spoiler": html.count("data-block=\"spoiler\""),
            "headings": editor.area.locator("h1, h2, h3").count(),
            "text": text.count("Опорный текст"),
        }

    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("Опорный текст")
    initial = snapshot()

    # правка 1: спойлер
    _caret_to_end(page)
    editor.toolbar_button("Спойлер").click()
    expect(editor.area.locator(".spoiler")).to_have_count(1)
    # правка 2: H2 на абзаце, затем снять повторным кликом
    editor.area.locator("p, div:not([data-editor])").first.click()
    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_count(1)
    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_count(0)
    # правка 3: H1→H3
    editor.toolbar_button("Заголовок 1").click()
    editor.toolbar_button("Заголовок 3").click()
    expect(editor.area.locator("h3")).to_have_count(1)
    assert snapshot()["text"] == 1  # правки текст не задублировали

    # undo по шагу за раз — фиксируем состояние после каждого (H-шаги дают
    # промежуточные состояния с тем же счетчиком заголовков: не сравниваем
    # на равенство, крутим до initial или исчерпания стека)
    steps = [snapshot()]
    for _ in range(12):
        page.keyboard.press("Control+Z")
        state = snapshot()
        steps.append(state)
        if state == initial:
            break
    assert steps[-1] == initial, steps  # откат до исходного: без заголовков/спойлера
    h_states = [s["headings"] for s in steps]
    assert h_states[-1] == 0 and h_states[0] > 0  # H-toggle отменился (F4)
    assert all(s["text"] == 1 for s in steps)  # текст цел на каждом шаге

    # redo обратно
    for _ in range(10):
        page.keyboard.press("Control+Shift+Z")
        state = snapshot()
        if state["spoiler"] and state["headings"]:
            break
    final = snapshot()
    assert final["spoiler"] == 1 and final["headings"] > 0 and final["text"] == 1, final


def test_tc_rich_033_editor_no_external_dependencies(editor_page, web_base_url):
    """TC-rich-033 (Must): редактор — все запросы к своему origin, модули
    rich/* локальны (ОГР-8)."""
    page = editor_page
    requests_log: list[str] = []
    page.on("request", lambda req: requests_log.append(req.url))
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()

    editor.toolbar_button("Спойлер").click()
    _caret_to_end(page)
    editor.toolbar_button("Блок кода").click()
    _caret_to_end(page)
    editor.toolbar_button("Табуляция").click()
    _caret_to_end(page)
    editor.toolbar_button("Таблица").click()

    external = [u for u in requests_log if not u.startswith(web_base_url)]
    assert external == []
    rich_modules = [u for u in requests_log if "/rich/" in u]
    assert rich_modules, "модули rich/* не загружались"
    assert all(u.startswith(web_base_url) for u in rich_modules)


# ---------------------------------------------------------------------------
# Санитизация (view): TC-rich-034, 036
# ---------------------------------------------------------------------------


def test_tc_rich_034_script_onerror_not_executed(editor_page, qa, page_errors, web_base_url):
    """TC-rich-034 (Must): script/onerror вне блоков вырезаны до рендера,
    alert не исполняется."""
    pid = qa.make(
        "QA-034 санитизация",
        '<p>до</p><script>window.__xss=1</script>'
        '<img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" '
        'onerror="window.__xss=2" alt="x"><p>после</p>',
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{pid}")
    expect(page.locator(".article-body")).to_contain_text("до")
    expect(page.locator(".article-body")).to_contain_text("после")
    assert page.evaluate("window.__xss === undefined")
    assert page_errors == []


def test_tc_rich_036_valid_blocks_activate_evil_degrades(editor_page, qa, page_errors, web_base_url):
    """TC-rich-036 (Must): 3 валидных блока активируются, «evil» деградирует
    в текст (GET-часть — в api-сьюте)."""
    pid = qa.make(
        "QA-036 активация",
        SPOILER.format(t="Сп", b="<p>тело спойлера</p>")
        + '<div data-block="code" data-lang="python"><pre><code>print(1)</code></pre></div>'
        + _tabs_content([("В1", "первая"), ("В2", "вторая")])
        + '<div data-block="evil">Подмена</div>',
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{pid}")
    body = page.locator(".article-body")
    spoiler = body.locator(".spoiler")
    spoiler.locator(".spoiler-head").click()
    expect(spoiler).to_have_class(re.compile("closed"))
    expect(body.locator(".tok-kw").first).to_be_visible()
    body.locator(".tab").nth(1).click()
    expect(body.locator(".tab-pane").nth(1)).to_contain_text("вторая")
    expect(body).to_contain_text("Подмена")
    assert body.locator('[data-block="evil"] .spoiler-head').count() == 0
    assert page_errors == []


# ---------------------------------------------------------------------------
# Фикс-раунд review-001: TC-rich-037..041
# ---------------------------------------------------------------------------


def test_tc_rich_037_code_enter_roundtrip_no_br_garbage(editor_page, qa, page_errors, web_base_url):
    """TC-rich-037 (Must, F-1): Enter в коде → \\\\n в БД, br нет; второй
    round-trip не задваивает; пустой блок без мусора."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Блок кода").click()
    page.keyboard.type("line1")
    page.keyboard.press("Enter")
    page.keyboard.type("line2 = 'значение'")
    page.keyboard.press("Enter")
    page.keyboard.type("line3")

    code_html = editor.area.locator(".codeblock code").evaluate("el => el.innerHTML")
    assert "<br" not in code_html

    editor.title_input.fill("QA-037 enter в коде")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved1 = qa.get(pid)
    assert "line1\nline2 = 'значение'\nline3" in saved1
    assert "<br" not in saved1.split("<code>")[1].split("</code>")[0]

    # второй round-trip: переоткрыть в редакторе и сохранить
    editor.open_edit(web_base_url, pid)
    expect(editor.area.locator(".codeblock")).to_have_count(1)  # асинхронная загрузка
    dom_text = editor.area.locator(".codeblock code").evaluate("el => el.textContent")
    assert dom_text == "line1\nline2 = 'значение'\nline3"
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    saved2 = qa.get(pid)
    assert saved2 == saved1  # идемпотентно, переносы не задвоены
    code2 = saved2.split("<code>")[1].split("</code>")[0]
    assert "\n\n" not in code2  # нет двойных переносов на месте одного Enter

    # пустой код-блок (каретка ПОСЛЕ последнего блока — иначе гейт кода
    # заблокирует вставку в код-блок)
    editor.open_edit(web_base_url, pid)
    expect(editor.area.locator(".codeblock")).to_have_count(1)
    page.evaluate(
        """() => {
          const a = document.querySelector('.editor-area');
          const r = document.createRange();
          r.setStartAfter(a.lastElementChild);
          r.collapse(true);
          const s = window.getSelection();
          s.removeAllRanges();
          s.addRange(r);
        }"""
    )
    editor.toolbar_button("Блок кода").click()
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved3 = qa.get(pid)
    empty_code = saved3.rsplit('data-block="code"', 1)[1]
    code_inner = empty_code.split("<code>")[1].split("</code>")[0]
    assert code_inner in ("", "\n"), repr(code_inner)  # без мусорных br/переносов
    # построчный вид статьи
    expect(page.locator(".article-body .codeblock").first.locator("code")).to_contain_text("line1")


def test_tc_rich_038_insert_gate_inside_codeblock(editor_page, qa, page_errors, web_base_url):
    """TC-rich-038 (Must): кнопки НЕ вставляют блоки в код-блок (гейт);
    paste-путь: вложенное в код unwrap, в редакторе код плоский
    (paste-GET-часть — в api-сьюте)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Блок кода").click()
    page.keyboard.type("x = 1")

    editor.toolbar_button("Спойлер").click()
    editor.toolbar_button("Блок кода").click()
    editor.toolbar_button("Табуляция").click()
    editor.toolbar_button("Таблица").click()

    expect(editor.area.locator('[data-block="spoiler"]')).to_have_count(0)
    expect(editor.area.locator(".tabswidget")).to_have_count(0)
    expect(editor.area.locator("table")).to_have_count(0)
    expect(editor.area.locator(".codeblock")).to_have_count(1)

    editor.title_input.fill("QA-038 гейт кода")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))

    # paste-путь: вложенный спойлер в код → в редакторе код плоский
    pid = qa.make(
        "QA-038 paste",
        '<div data-block="code" data-lang="python"><pre><code>x = 1</code></pre>'
        + SPOILER.format(t="Вл", b="<p>секрет</p>") + "</div>",
    )
    editor.open_edit(web_base_url, pid)
    block = editor.area.locator(".codeblock")
    expect(block).to_have_count(1)
    assert block.locator("[data-block]").count() == 0  # внутри кода блоков нет
    block_text = block.evaluate("el => el.textContent")
    assert "x = 1" in block_text and "секрет" in block_text  # текст сохранен
    assert page_errors == []


def test_tc_rich_039_gutter_matches_lines_scroll_sync(editor_page, qa, page_errors, web_base_url):
    """TC-rich-039 (Should, F-2): гуттер 1..N по строкам (пустые нумеруются),
    вертикальной прокрутки внутри pre нет (гуттер синхронен по построению),
    в БД гуттера нет (data-editor)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Блок кода").click()
    for i in range(1, 11):
        if i % 3 == 0:
            pass  # пустая строка
        else:
            page.keyboard.type(f"line {i}")
        if i < 10:
            page.keyboard.press("Enter")

    block = editor.area.locator(".codeblock")
    nums = block.locator(".codeblock-nums").evaluate("el => el.textContent")
    assert nums == "\n".join(str(i) for i in range(1, 11)), nums

    # внутренняя вертикальная прокрутка pre отсутствует → гуттер всегда
    # выровнен (абсолютный сиблинг, скроллится вместе со страницей)
    scroll = block.locator("pre").evaluate(
        "el => ({sy: el.scrollHeight, cy: el.clientHeight})"
    )
    assert scroll["sy"] <= scroll["cy"] + 2, scroll  # нет внутреннего скролла

    editor.title_input.fill("QA-039 гуттер")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved = qa.get(pid)
    assert "codeblock-nums" not in saved and "data-editor" not in saved
    expect(page.locator(".article-body .codeblock-nums")).to_have_text(
        "\n".join(str(i) for i in range(1, 11))
    )
    assert page_errors == []


def test_tc_rich_040_spoiler_rename_gate_editor_only(editor_page, qa, page_errors, web_base_url):
    """TC-rich-040 (Must, F-3): Escape отменяет, blur коммитит, гонка
    Escape+blur детерминирована; в статье rename не открывается."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Спойлер").click()
    spoiler = editor.area.locator(".spoiler")

    # Escape — отмена (спека ОВ; факт см. assert в конце — дискриминатор F-3)
    spoiler.locator(".spoiler-title").click()
    inp = spoiler.locator(".spoiler-title-input")
    expect(inp).to_be_visible()
    inp.fill("Черновик")
    inp.press("Escape")
    page.wait_for_timeout(200)
    escape_result = spoiler.locator(".spoiler-title").evaluate("el => el.textContent")
    escape_input_gone = inp.count() == 0
    # спека: после Escape название «Спойлер» (отмена). Факт фиксируем и
    # продолжаем сбор фактов — вердикт в конце.
    if escape_result != "Спойлер":
        # вернуть детерминированное состояние для дальнейших шагов
        spoiler.locator(".spoiler-title").click()
        inp = spoiler.locator(".spoiler-title-input")
        expect(inp).to_be_visible()
        inp.fill("Спойлер")
        inp.press("Enter")
        expect(spoiler.locator(".spoiler-title")).to_have_text("Спойлер")

    # blur — коммит
    spoiler.locator(".spoiler-title").click()
    expect(inp).to_be_visible()
    inp.fill("Финал")
    editor.area.locator(".spoiler-body").click()
    expect(spoiler.locator(".spoiler-title")).to_have_text("Финал")

    # смоук: коммит по Enter не сломан фикс-раундом (rename «Финал-Enter»)
    spoiler.locator(".spoiler-title").click()
    expect(inp).to_be_visible()
    inp.fill("Финал-Enter")
    inp.press("Enter")
    expect(spoiler.locator(".spoiler-title")).to_have_text("Финал-Enter")
    assert spoiler.locator(".spoiler-title-input").count() == 0
    # вернуть «Финал» для дальнейших шагов
    spoiler.locator(".spoiler-title").click()
    expect(inp).to_be_visible()
    inp.fill("Финал")
    inp.press("Enter")
    expect(spoiler.locator(".spoiler-title")).to_have_text("Финал")

    # гонка Escape → сразу blur: значение до правки («Финал») сохранено
    spoiler.locator(".spoiler-title").click()
    expect(inp).to_be_visible()
    inp.fill("Гонка")
    inp.press("Escape")
    page.wait_for_timeout(100)
    if spoiler.locator(".spoiler-title-input").count():
        spoiler.locator(".spoiler-title-input").dispatch_event("blur")
    page.wait_for_timeout(200)
    race_result = spoiler.locator(".spoiler-title").evaluate("el => el.textContent")
    race_inputs = spoiler.locator(".spoiler-title-input").count()
    if race_result != "Финал":
        # восстановить для сохранения детерминированное значение
        spoiler.locator(".spoiler-title").click()
        inp = spoiler.locator(".spoiler-title-input")
        expect(inp).to_be_visible()
        inp.fill("Финал")
        inp.press("Enter")
        expect(spoiler.locator(".spoiler-title")).to_have_text("Финал")

    editor.title_input.fill("QA-040 rename гейт")
    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid = int(page.url.rstrip("/").rsplit("/", 1)[1])
    saved = qa.get(pid)
    assert saved.count("data-title") == 1 and 'data-title="Финал"' in saved

    # в статье клик по названию = toggle, инлайн-input не открывается
    article = page.locator(".article-body .spoiler")
    article.locator(".spoiler-title").click()
    expect(article).to_have_class(re.compile("closed"))
    assert article.locator(".spoiler-title-input").count() == 0
    expect(article.locator(".spoiler-title")).to_have_text("Финал")
    # ВЕРДИКТ по спеке (дискриминатор F-3): Escape отменяет правку, гонка
    # Escape+blur детерминирована, ошибок JS нет
    problems = []
    if escape_result != "Спойлер":
        problems.append(
            f"Escape НЕ отменил rename: title после Escape = {escape_result!r} "
            f"(репро: редактор, rename «Черновик», Escape — коммитит вместо отмены)"
        )
    if race_result != "Финал" or race_inputs != 0:
        problems.append(
            f"гонка Escape+blur недетерминирована: title = {race_result!r}, inputs = {race_inputs}"
        )
    if page_errors:
        problems.append(f"ошибки JS в консоли: {page_errors[:3]}")
    assert not problems, "; ".join(problems)


def test_tc_rich_041_table_in_table_gated_and_unwrapped(editor_page, qa, page_errors, web_base_url):
    """TC-rich-041 (Must): кнопка не вставляет таблицу в ячейку; paste —
    unwrap целиком с «A1<br>B1»; повторное сохранение идемпотентно."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Таблица").click()
    expect(editor.area.locator("table")).to_have_count(1)
    table_btn = editor.toolbar_button("Таблица")
    cell = editor.area.locator("tbody tr").nth(0).locator("td").nth(0)
    cell.click()
    # Фикс D2: кнопка DISABLED с подсказкой — click по disabled упал бы по
    # таймауту Playwright, поэтому проверяем состояние, а не действие.
    expect(table_btn).to_be_disabled()
    assert table_btn.get_attribute("title") == "В ячейке таблица запрещена"
    page.wait_for_timeout(200)
    gate_inserted = editor.area.locator("td table").count()  # спека: 0 (гейт)
    expect(editor.area.locator("td table")).to_have_count(0)

    # смоук: каретка вне таблицы — кнопка снова доступна, вставка РАБОТАЕТ
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
    expect(table_btn).to_be_enabled()
    expect(table_btn).to_have_attribute("title", "Таблица")
    table_btn.click()
    expect(editor.area.locator("table")).to_have_count(2)
    # убрать смоук-таблицу — дальше paste-путь на чистом черновике
    for _ in range(5):
        page.keyboard.press("Control+Z")
        if editor.area.locator("table").count() == 1:
            break
    expect(editor.area.locator("table")).to_have_count(1)
    expect(editor.area.locator("td table")).to_have_count(0)

    # paste-путь
    pid = qa.make(
        "QA-041 таблица в таблице",
        "<table><tbody><tr><td>"
        "<table><tbody><tr><td>A1</td><td>B1</td></tr></tbody></table>"
        "</td></tr></tbody></table>",
    )
    editor.open_edit(web_base_url, pid)
    expect(editor.area.locator("table")).to_have_count(1)  # контент грузится асинхронно
    assert editor.area.locator("table table").count() == 0

    editor.save_button().click()
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    pid2 = int(page.url.rstrip("/").rsplit("/", 1)[1])
    assert pid2 == pid
    saved = qa.get(pid)
    assert "table-in-table" not in saved
    assert saved.count("<table>") == 1
    assert "<td>A1<br>B1</td>" in saved  # текст обеих ячеек с <br>

    article = page.locator(".article-body")
    expect(article.locator("table")).to_have_count(1)
    expect(article.locator("td").first).to_contain_text("A1")
    expect(article.locator("td").first).to_contain_text("B1")
    assert page_errors == []
    # ВЕРДИКТ по спеке (матрица design §6: ячейка×таблица = НЕТ)
    assert gate_inserted == 0, (
        f"гейт вставки таблицы в ячейку ОТСУТСТВУЕТ: кнопка «Таблица» вставила "
        f"вложенную таблицу в td (count={gate_inserted}); paste-путь при этом "
        f"unwrap'ит на санитайзере — расхождение «редактор показал ≠ сохранилось»"
    )
