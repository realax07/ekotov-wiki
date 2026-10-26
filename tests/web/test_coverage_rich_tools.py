"""coverage-backfill-1, группа A: автотесты TC-rich-001…021 (p12-rich-tools).

Source of truth: test-model/approved/p12-rich-tools/TC-rich-001..021.md.
Каждый тест — ровно один утвержденный кейс; маркер трассировки в docstring
(«coverage-backfill-1; TC-rich-NNN: <название кейса>»). Стиль и FIXTURES —
по tests/web/test_rich_tools.py / test_p12n004* (богатый локаторный опыт —
test_redesign_console.py). Ассерты — по духу кейса, не слабее.

Отклонение от буквы кейса (задокументировано в docstring конкретного теста):
p12-rich-2 (багфикс с прода) сделал вставленный/открытый спойлер ВСЕГДА
свернутым, а каретку после вставки — в абзаце ЗА блоком; кейсы 001/005
писались до этого фикса, дух кейса (контент цел, состояние в контенте не
хранится, раскрытие кликом) проверяется, устаревшая буква — нет.

Вторая часть группы (TC-rich-022…039) — tests/web/test_coverage_rich_tools_security.py.
"""

import re
from types import SimpleNamespace

import pytest
from playwright.sync_api import expect

from tests.web.pages.wiki import WikiEditor

pytestmark = [pytest.mark.e2e, pytest.mark.web]

BASE_URL_ENV = "EKOTOV_WIKI_BASE_URL"


# ---------------------------------------------------------------------------
# fixtures (паттерн test_rich_tools.py / test_p15_wiki_editor.py)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def wiki_stand_schema(web_server):
    """Схема wiki в tmp-БД стенда (идемпотентно; паттерн test_rich_tools)."""
    import os
    import subprocess as sp
    import sys

    db_path = web_server.get("db_path") if isinstance(web_server, dict) else None
    if not db_path:
        return
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    mig_env = dict(os.environ, DB_PATH=db_path, SECRET_KEY="web-tests-secret-key")
    mig_env.pop("PYTHONPATH", None)
    mig = sp.run(
        [sys.executable, "-m", "app.migrate_wiki"],
        cwd=repo_root + "/backend", env=mig_env, capture_output=True, text=True,
    )
    assert mig.returncode == 0, mig.stderr


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
# общие хелперы
# ---------------------------------------------------------------------------


def _saved_page_id(page) -> int:
    """id страницы после save-редиректа /wiki/{id}."""
    page.wait_for_url(re.compile(r"/wiki/\d+$"))
    return int(page.url.rstrip("/").rsplit("/", 1)[1])


def _caret_to_area_end(page) -> None:
    """Каретка в конец области редактирования (паттерн QA-сьюта)."""
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


def _caret_cell_text(page) -> str:
    """textContents ячейки, в которой стоит каретка."""
    return page.evaluate(
        """() => {
          const n = window.getSelection().anchorNode;
          const e = n && (n.nodeType === 1 ? n : n.parentNode);
          const cell = e && (e.closest ? e.closest('td,th') : null);
          return cell ? cell.textContent : '';
        }"""
    )


def _expect_heading_pressed(editor, label, value) -> None:
    """aria-pressed обновляется по selectionchange (асинхронно) — только
    expect c авто-ожиданием, немедленное чтение атрибута гоночно."""
    expect(editor.toolbar_button(label)).to_have_attribute("aria-pressed", value)


def _no_heading_pressed(editor) -> None:
    for label in ("Заголовок 1", "Заголовок 2", "Заголовок 3"):
        expect(editor.toolbar_button(label)).to_have_attribute("aria-pressed", "false")


# ---------------------------------------------------------------------------
# Спойлер (FR-118): TC-rich-001…005
# ---------------------------------------------------------------------------


def test_tc_rich_001_spoiler_insert_inline_rename(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-001: Вставка спойлера и инлайн-переименование.

    Шаг 2 (буква кейса «фокус в зоне содержимого») скорректирован багфиксом
    p12-rich-2: вставленный спойлер СВЕРНУТ, каретка — в абзаце за блоком
    (в скрытое тело каретка невозможна). Дух кейса проверяется целиком:
    шапка (шеврон+название) + зона содержимого вставлены; инлайн-rename;
    сохранение; в контенте data-block=spoiler + data-title, служебных
    data-editor узлов нет."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Спойлер").click()

    spoiler = editor.area.locator(".spoiler")
    expect(spoiler).to_have_count(1)
    # шаг 2: вставлены шапка (шеврон + название) и зона содержимого
    expect(spoiler.locator(".spoiler-caret")).to_have_count(1)
    expect(spoiler.locator(".spoiler-title")).to_have_text("Спойлер")
    expect(spoiler.locator(".spoiler-body")).to_have_count(1)

    # шаг 3: инлайн-переименование названия
    spoiler.locator(".spoiler-caret").click()  # раскрыть (p12-rich-2: закрыт)
    expect(spoiler).to_have_class(re.compile("open"))
    spoiler.locator(".spoiler-title").click()
    name_input = spoiler.locator(".spoiler-title-input")
    expect(name_input).to_be_visible()
    name_input.fill("Скрытые детали")
    name_input.press("Enter")
    expect(spoiler.locator(".spoiler-title")).to_have_text("Скрытые детали")

    # зона содержимого: каретка внутрь тела, ввод текста
    spoiler.locator(".spoiler-body").click()
    page.keyboard.type("Тело спойлера")
    expect(spoiler.locator(".spoiler-body")).to_contain_text("Тело спойлера")

    # шаг 4: сохранить, открыть статью
    editor.title_input.fill("Спойлер insert-rename")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    wiki_api.register(page_id)

    body = page.locator(".article-body")
    article_spoiler = body.locator(".spoiler")
    expect(article_spoiler).to_have_count(1)
    expect(article_spoiler.locator(".spoiler-title")).to_have_text("Скрытые детали")
    article_spoiler.locator(".spoiler-head").click()
    expect(article_spoiler.locator(".spoiler-body")).to_contain_text("Тело спойлера")

    # шаг 5: контент — data-block=spoiler + data-title, служебных узлов нет
    saved = wiki_api.content_of(page_id)
    assert 'data-block="spoiler"' in saved
    assert 'data-title="Скрытые детали"' in saved
    assert "data-editor" not in saved
    assert page_errors == []


def test_tc_rich_002_spoiler_head_click_anywhere_toggles(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-002: Сворачивание/разворачивание кликом
    по всей шапке (ОВ-1). Любая точка шапки (правый край, название, пустое
    место у шеврона) toggle'ит; клик по телу — НЕ сворачивает; контент без
    потерь."""
    page_id = wiki_api.create(
        "Спойлер ОВ-1",
        '<div data-block="spoiler" data-title="Секреты">'
        '<div data-block-part="body"><p>уникальное содержимое ОВ-1</p></div></div>',
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    spoiler = page.locator(".article-body .spoiler")
    expect(spoiler).to_have_class(re.compile("closed"))  # дефолт p12-rich-2

    head = spoiler.locator(".spoiler-head")
    expect(head).to_be_visible()
    # шаг 2: правый край шапки (не шеврон и не название)
    box = head.bounding_box()
    page.mouse.click(box["x"] + box["width"] - 3, box["y"] + box["height"] / 2)
    expect(spoiler).to_have_class(re.compile("open"))
    # шаг 3: клик по названию, затем по пустому месту рядом с шевроном
    spoiler.locator(".spoiler-title").click()
    expect(spoiler).to_have_class(re.compile("closed"))
    box = head.bounding_box()
    page.mouse.click(box["x"] + 20, box["y"] + box["height"] / 2)
    expect(spoiler).to_have_class(re.compile("open"))
    # шаг 4: клик по зоне содержимого спойлер НЕ сворачивает
    spoiler.locator(".spoiler-body p").click()
    expect(spoiler).to_have_class(re.compile("open"))
    # содержимое без потерь после серии toggle
    expect(spoiler.locator(".spoiler-body")).to_have_text(
        "уникальное содержимое ОВ-1"
    )
    assert page_errors == []


def test_tc_rich_003_spoiler_in_table_cell_compact(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-003: Спойлер в ячейке таблицы —
    компактный вариант. rich-compact в редакторе/статье; toggle работает,
    раскладка таблицы не сломана; компактность в контенте НЕ хранится."""
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
    expect(spoiler).to_have_class(re.compile("closed"))  # дефолт p12-rich-2
    spoiler.locator(".spoiler-caret").click()
    expect(spoiler).to_have_class(re.compile("open"))
    spoiler.locator(".spoiler-body").click()
    page.keyboard.type("В ячейке")

    editor.title_input.fill("Спойлер в ячейке")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    wiki_api.register(page_id)

    body = page.locator(".article-body")
    cell_spoiler = body.locator("td .spoiler")
    expect(cell_spoiler).to_have_count(1)
    expect(cell_spoiler).to_have_class(re.compile("rich-compact"))
    # шаг 3: toggle работает, таблица не сломана
    expect(cell_spoiler).to_have_class(re.compile("closed"))
    expect(body.locator("table")).to_have_count(1)
    expect(body.locator("td")).to_have_count(6)  # 2x3 раскладка цела
    cell_spoiler.locator(".spoiler-head").click()
    expect(cell_spoiler.locator(".spoiler-body")).to_contain_text("В ячейке")
    expect(body.locator("td")).to_have_count(6)

    # шаг 4: компактности в контенте НЕТ (класс появляется только по
    # closest('td,th') при активации)
    saved = wiki_api.content_of(page_id)
    assert "rich-compact" not in saved, saved
    assert 'data-block="spoiler"' in saved
    assert page_errors == []


def test_tc_rich_004_spoiler_in_spoiler_independent(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-004: Спойлер в спойлере — независимая
    работа, без потери контента. Урок rich-v1 «потеря при вложении» не
    воспроизводится: вложенный div[data-block=spoiler] внутри
    data-block-part=body."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Спойлер").click()
    outer = editor.area.locator(".spoiler").nth(0)
    outer_caret = outer.locator("> .spoiler-head > .spoiler-caret")
    outer_caret.click()  # раскрыть внешний
    expect(outer).to_have_class(re.compile("open"))
    outer.locator(".spoiler-body").click()
    page.keyboard.type("Текст внешний")
    editor.toolbar_button("Спойлер").click()  # каретка в теле внешнего
    inner = outer.locator(".spoiler")
    expect(inner).to_have_count(1)
    inner.locator(".spoiler-caret").click()  # раскрыть внутренний
    expect(inner).to_have_class(re.compile("open"))
    inner.locator(".spoiler-body").click()
    page.keyboard.type("Текст внутренний")

    # шаг 3: свернуть внутренний, затем внешний
    inner.locator("> .spoiler-head > .spoiler-caret").click()
    expect(inner).to_have_class(re.compile("closed"))
    outer_caret.click()
    expect(outer).to_have_class(re.compile("closed"))

    editor.title_input.fill("Спойлер в спойлере")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    wiki_api.register(page_id)

    # шаг 4: развернуть внешний — внутренний остался свернутым
    body = page.locator(".article-body")
    outer_view = body.locator(".spoiler").first
    outer_view.locator("> .spoiler-head").click()
    expect(outer_view).to_have_class(re.compile("open"))
    inner_view = body.locator(".spoiler .spoiler")
    expect(inner_view).to_have_count(1)
    expect(inner_view).to_have_class(re.compile("closed"))
    expect(inner_view.locator(".spoiler-body")).to_contain_text("Текст внутренний")
    expect(outer_view.locator("> .spoiler-body")).to_contain_text("Текст внешний")
    inner_view.locator("> .spoiler-head").click()
    expect(inner_view.locator(".spoiler-body")).to_contain_text("Текст внутренний")

    # шаг 5: вложенный data-block=spoiler внутри data-block-part=body,
    # оба текста сохранены
    saved = wiki_api.content_of(page_id)
    assert saved.count('data-block="spoiler"') == 2
    body_part = saved.split('data-block-part="body"', 1)[1]
    assert 'data-block="spoiler"' in body_part
    assert "Текст внешний" in saved and "Текст внутренний" in saved
    assert page_errors == []


def test_tc_rich_005_collapsed_spoiler_keeps_content_state_not_saved(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-005: Свернутый спойлер сохраняет
    содержимое, состояние не хранится. Буква кейса «при открытии развернут»
    скорректирована багфиксом p12-rich-2 (спойлер при открытии СВЕРНУТ —
    раскрытие только кликом пользователя); дух кейса: содержимое цело
    в статье и в редакторе, в HTML нет атрибутов свернутости."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Спойлер").click()
    spoiler = editor.area.locator(".spoiler")
    spoiler.locator(".spoiler-caret").click()  # раскрыть
    expect(spoiler).to_have_class(re.compile("open"))
    spoiler.locator(".spoiler-body").click()
    page.keyboard.type("Секретный текст")
    spoiler.locator(".spoiler-caret").click()  # шаг 1: свернуть в редакторе
    expect(spoiler).to_have_class(re.compile("closed"))

    editor.title_input.fill("Свернутый сохраняет")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    wiki_api.register(page_id)

    # шаг 2: содержимое присутствует в статье… (раскрыл пользователь)
    expect(page.locator(".article-body .spoiler")).to_have_class(re.compile("closed"))
    page.locator(".article-body .spoiler .spoiler-head").click()
    expect(page.locator(".article-body .spoiler .spoiler-body")).to_contain_text(
        "Секретный текст"
    )
    # …и в редакторе
    editor.open_edit(web_base_url, page_id)
    editor.area.locator(".spoiler .spoiler-caret").click()
    expect(editor.area.locator(".spoiler .spoiler-body")).to_contain_text(
        "Секретный текст"
    )

    # шаг 3: текст в data-block-part="body" цел; атрибутов свернутости нет
    saved = wiki_api.content_of(page_id)
    assert 'data-block-part="body"' in saved
    assert "Секретный текст" in saved
    assert "data-collapsed" not in saved and "data-open" not in saved
    assert "open" not in saved and "closed" not in saved
    assert page_errors == []


# ---------------------------------------------------------------------------
# Блок кода (FR-119): TC-rich-006…009
# ---------------------------------------------------------------------------

_PY_CODE = (
    "def greet(name):",
    "    # приветствие",
    '    msg = "Привет, " + name',
    "    print(msg, 42)",
    "    return msg",
)


def test_tc_rich_006_codeblock_python_highlight_numbering(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-006: Код-блок: выбор языка python,
    подсветка и нумерация. Нумерация по строкам; ключевые слова/строки/
    числа/комментарии различимы (tok-*); в контенте data-lang=python,
    внутри pre/code чистый текст — спанов подсветки в БД нет."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Блок кода").click()
    block = editor.area.locator(".codeblock")
    expect(block).to_have_count(1)

    # шаг 2: выбор языка «python» в шапке блока
    block.locator(".codeblock-lang").click()
    block.locator(".lang-menu .lang-opt").filter(has_text="python").click()
    expect(block.locator(".codeblock-lang")).to_contain_text("python")

    # шаг 3: код с def, строкой в кавычках, числом и комментарием
    page.keyboard.type(_PY_CODE[0])
    for line in _PY_CODE[1:]:
        page.keyboard.press("Enter")
        page.keyboard.type(line)
    # нумерация: 5 строк → «1..5»
    assert (
        block.locator(".codeblock-nums").evaluate("el => el.textContent")
        == "1\n2\n3\n4\n5"
    )

    editor.title_input.fill("Код python")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    wiki_api.register(page_id)

    # шаг 4: в статье тот же вид — подсветка и нумерация
    article_block = page.locator(".article-body .codeblock")
    expect(article_block.locator(".codeblock-lang")).to_have_text("python")
    expect(article_block.locator(".tok-kw").first).to_be_visible()  # def
    expect(article_block.locator(".tok-str").first).to_be_visible()  # строка
    expect(article_block.locator(".tok-com").first).to_be_visible()  # комментарий
    expect(article_block.locator(".tok-num").first).to_be_visible()  # число 42
    expect(article_block.locator(".codeblock-nums")).to_have_text("1\n2\n3\n4\n5")

    # в контенте: data-lang=python, чистый экранированный текст, без tok-*
    saved = wiki_api.content_of(page_id)
    assert 'data-lang="python"' in saved
    code_in_db = saved.split("<code>")[1].split("</code>")[0]
    assert "\n".join(_PY_CODE) in code_in_db.replace("&#x27;", "'").replace(
        "&quot;", '"'
    ), code_in_db
    assert "tok-" not in saved
    assert page_errors == []


def test_tc_rich_007_copy_button_clean_text(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-007: Кнопка «Копировать» — чистый текст
    без нумерации и спанов, «✓ Скопировано» ~1,5 с и возврат надписи.
    Буфер читается через перехват Clipboard API (стаб writeText, паттерн
    test_rich_tools: сам Clipboard браузера не тестируем)."""
    code = "\n".join(_PY_CODE)
    page_id = wiki_api.create(
        "Копировать код",
        '<div data-block="code" data-lang="python"><pre><code>'
        + code.replace("&", "&amp;").replace("<", "&lt;")
        + "</code></pre></div>",
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    article_block = page.locator(".article-body .codeblock")
    expect(article_block.locator(".codeblock-nums")).to_have_text(
        "1\n2\n3\n4\n5"
    )

    page.evaluate(
        "navigator.clipboard.writeText = (t) => "
        "{ window.__copiedText = t; return Promise.resolve(); };"
    )
    article_block.locator(".copy-btn").click()
    # в буфере чистый текст: равен textContent кода, без номеров и спанов
    expected = article_block.locator("code").evaluate("el => el.textContent")
    assert page.evaluate("window.__copiedText") == expected
    assert page.evaluate("window.__copiedText") == code
    # кнопка показывает «✓ Скопировано»…
    expect(article_block.locator(".copy-btn")).to_have_text("✓ Скопировано")
    # …затем возвращает исходную надпись (~1,5 с)
    page.wait_for_timeout(1700)
    expect(article_block.locator(".copy-btn")).to_have_text("Копировать")
    assert page_errors == []


def test_tc_rich_008_codeblock_inside_spoiler(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-008: Код-блок внутри спойлера —
    подсветка и копирование работают, toggle спойлера не теряет ни символа
    кода; в контенте data-block=code внутри data-block-part=body."""
    code = "\n".join(_PY_CODE)
    page_id = wiki_api.create(
        "Код в спойлере copy",
        '<div data-block="spoiler" data-title="Скрипт">'
        '<div data-block-part="body">'
        '<div data-block="code" data-lang="python"><pre><code>'
        + code.replace("&", "&amp;").replace("<", "&lt;")
        + "</code></pre></div></div></div>",
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    spoiler = page.locator(".article-body .spoiler")
    expect(spoiler).to_have_class(re.compile("closed"))  # дефолт p12-rich-2

    # подсветка работает внутри спойлера
    spoiler.locator(".spoiler-head").click()
    code_block = spoiler.locator(".codeblock")
    expect(code_block.locator(".tok-kw").first).to_be_visible()
    before = code_block.locator("code").evaluate("el => el.textContent")

    # копирование внутри спойлера
    page.evaluate(
        "navigator.clipboard.writeText = (t) => "
        "{ window.__copiedText = t; return Promise.resolve(); };"
    )
    code_block.locator(".copy-btn").click()
    assert page.evaluate("window.__copiedText") == code

    # toggle без потерь: textContent до/после идентичен
    spoiler.locator(".spoiler-head").click()
    expect(code_block).to_be_hidden()
    spoiler.locator(".spoiler-head").click()
    expect(code_block.locator("code")).to_be_visible()
    after = code_block.locator("code").evaluate("el => el.textContent")
    assert before == after == code

    # в контенте код-блок вложен в тело спойлера
    saved = wiki_api.content_of(page_id)
    body_part = saved.split('data-block-part="body"', 1)[1]
    assert 'data-block="code"' in body_part
    assert page_errors == []


def test_tc_rich_009_unknown_lang_plain_no_errors(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-009: Нераспознанный язык деградирует в
    plain без потери текста. Санитайзер снимает data-lang вне словаря ОВ-2
    (имитация внешней порчи) — код моноширинным без подсветки, текст
    посимвольно цел, ошибок JS нет (NFR-39)."""
    source = "MOVE A TO B.\nDISPLAY 'HELLO'.\nSTOP RUN."
    page_id = wiki_api.create(
        "Код cobol",
        '<div data-block="code" data-lang="cobol"><pre><code>'
        + source
        + "</code></pre></div>",
    )
    saved = wiki_api.content_of(page_id)
    assert "data-lang" not in saved  # невалидное значение снято (_safe_block_attr)

    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    block = page.locator(".article-body .codeblock")
    expect(block).to_have_count(1)
    expect(block.locator(".tok-kw")).to_have_count(0)  # подсветки нет — plain
    # текст полностью сохранен (посимвольно)
    assert block.locator("code").evaluate("el => el.textContent") == source
    assert page_errors == []  # ошибок JS в консоли нет (NFR-39)


# ---------------------------------------------------------------------------
# Табуляция (FR-120): TC-rich-010…013
# ---------------------------------------------------------------------------


def test_tc_rich_010_tabs_switching_in_article(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-010: Переключение вкладок в статье.
    Активная черта (active) перемещается, в зоне содержимого — контент
    именно выбранной вкладки; активная вкладка в контент не сохраняется."""
    page_id = wiki_api.create(
        "Табы три",
        '<div data-block="tabs">'
        '<div data-block-part="tab" data-title="Обзор"><p>МОК-ОБЗОР</p></div>'
        '<div data-block-part="tab" data-title="Детали"><p>МОК-ДЕТАЛИ</p></div>'
        '<div data-block-part="tab" data-title="Пример"><p>МОК-ПРИМЕР</p></div>'
        "</div>",
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    widget = page.locator(".article-body .tabswidget")
    expect(widget.locator(".tab")).to_have_count(3)
    expect(widget.locator(".tab").first).to_have_class(re.compile("active"))

    # шаг 2: вторая вкладка активна, показан её контент
    widget.locator(".tab").nth(1).click()
    expect(widget.locator(".tab").nth(1)).to_have_class(re.compile("active"))
    expect(widget.locator(".tab-pane").nth(1)).to_contain_text("МОК-ДЕТАЛИ")
    expect(widget.locator(".tab-pane").nth(0)).to_be_hidden()

    # шаг 3: третья, затем первая — каждая показывает свой контент
    widget.locator(".tab").nth(2).click()
    expect(widget.locator(".tab-pane").nth(2)).to_contain_text("МОК-ПРИМЕР")
    widget.locator(".tab").nth(0).click()
    expect(widget.locator(".tab-pane").nth(0)).to_contain_text("МОК-ОБЗОР")

    # активная вкладка в контент не сохраняется: после перезагрузки первая
    page.reload()
    widget = page.locator(".article-body .tabswidget")
    expect(widget.locator(".tab").first).to_have_class(re.compile("active"))
    expect(widget.locator(".tab-pane").first).to_contain_text("МОК-ОБЗОР")
    assert page_errors == []


def test_tc_rich_011_tabs_add_rename_last_protected(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-011: Добавление, dblclick-переименование
    и запрет удаления последней вкладки. Удаление единственной заблокировано
    (крестик неактивен/скрыт), виджет не исчезает; в статье «Детали» есть,
    «Обзор» нет."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Табуляция").click()
    widget = editor.area.locator(".tabswidget")
    expect(widget.locator(".tab")).to_have_count(2)

    # сводим к одной вкладке «Обзор» (предусловие кейса)
    widget.locator(".tab").nth(1).locator(".tab-close").dispatch_event("click")
    expect(widget.locator(".tab")).to_have_count(1)
    first = widget.locator(".tab").first
    first.dblclick()
    rename = widget.locator(".tab-rename")
    expect(rename).to_be_visible()
    rename.fill("Обзор")
    rename.press("Enter")
    expect(first).to_contain_text("Обзор")

    # шаги 2–3: «+» создает вкладку, dblclick переименовывает в «Детали»
    widget.locator(".tab-add").click()
    expect(widget.locator(".tab")).to_have_count(2)
    second = widget.locator(".tab").nth(1)
    second.dblclick()
    rename = widget.locator(".tab-rename")
    expect(rename).to_be_visible()
    rename.fill("Детали")
    rename.press("Enter")
    expect(second).to_contain_text("Детали")

    # шаг 4: удаление «Обзор» возможно (стало 1)
    second.click()  # делаем «Детали» активной — «×» удаляет неактивную
    expect(second).to_have_class(re.compile("active"))
    first.locator(".tab-close").dispatch_event("click")
    expect(widget.locator(".tab")).to_have_count(1)

    # шаг 5: единственную вкладку удалить нельзя, виджет не исчезает
    widget.locator(".tab").first.hover()
    widget.locator(".tab").first.locator(".tab-close").dispatch_event("click")
    expect(widget.locator(".tab")).to_have_count(1)
    assert not widget.locator(".tab .tab-close").first.is_visible()
    expect(widget).to_be_visible()

    # шаг 6: в статье «Обзор» нет, «Детали» на месте
    widget.locator(".tab-pane").nth(0).click()
    page.keyboard.type("Контент деталей")
    editor.title_input.fill("Табы последняя")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    wiki_api.register(page_id)
    article = page.locator(".article-body .tabswidget")
    expect(article.locator(".tab")).to_have_count(1)
    expect(article.locator(".tab").first).to_contain_text("Детали")
    assert "Обзор" not in wiki_api.content_of(page_id)
    assert page_errors == []


def test_tc_rich_012_tabs_limit8_overflow_scroll(editor_page, wiki_api, page_errors, web_base_url):
    """coverage-backfill-1; TC-rich-012: Лимит 8 вкладок и горизонтальный
    скролл переполнения (ОВ-3). Девятая не создается (в DOM и в контенте
    ровно 8 data-block-part=tab); переполненный таб-бар прокручивается
    горизонтально без переноса строк."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Табуляция").click()
    widget = editor.area.locator(".tabswidget")
    expect(widget.locator(".tab")).to_have_count(2)

    # шаг 1: «+» до восьми вкладок
    for _ in range(6):
        widget.locator(".tab-add").click()
    expect(widget.locator(".tab")).to_have_count(8)
    # длинные названия (30+ символов) — JS-переименование (паттерн сьюта)
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
    # шаг 2: девятое нажатие «+» не создает вкладку
    expect(widget.locator(".tab-add")).to_be_disabled()
    widget.locator(".tab-add").dispatch_event("click")
    expect(widget.locator(".tab")).to_have_count(8)

    # шаг 3: viewport 1024 — переполнение прокручивается горизонтально
    page.set_viewport_size({"width": 1024, "height": 800})
    overflow = page.evaluate(
        """() => {
          const bar = document.querySelector('.editor-area .tabbar');
          const tab = bar.querySelector('.tab');
          return {
            overflow: getComputedStyle(bar).overflowX,
            scrolls: bar.scrollWidth > bar.clientWidth,
            nowrap: getComputedStyle(tab).whiteSpace,
          };
        }"""
    )
    assert overflow["overflow"] == "auto"
    assert overflow["scrolls"]
    assert overflow["nowrap"] in ("nowrap", "pre")

    # шаг 4: в контенте ровно 8 data-block-part="tab"
    editor.title_input.fill("Табы лимит")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    wiki_api.register(page_id)
    saved = wiki_api.content_of(page_id)
    assert saved.count('data-block-part="tab"') == 8
    assert page_errors == []


def test_tc_rich_013_tabs_inside_tab_nested(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-013: Табы внутри вкладки — независимые
    виджеты. Переключение внешнего не сбрасывает внутренний и наоборот; все
    четыре таб-части в контенте без потерь (design §6)."""
    page_id = wiki_api.create(
        "Табы в табе cov",
        '<div data-block="tabs">'
        '<div data-block-part="tab" data-title="Снаружи1"><p>В1.1</p>'
        '<div data-block="tabs">'
        '<div data-block-part="tab" data-title="Внутри1"><p>В2.1</p></div>'
        '<div data-block-part="tab" data-title="Внутри2"><p>В2.2</p></div>'
        "</div></div>"
        '<div data-block-part="tab" data-title="Снаружи2"><p>В1.2</p></div>'
        "</div>",
    )
    page = editor_page
    page.goto(f"{web_base_url}/wiki/{page_id}")
    widget = page.locator(".article-body .tabswidget").first
    nested = widget.locator(".tabswidget")
    expect(nested).to_have_count(1)
    expect(nested.locator(".tab")).to_have_count(2)
    # вкладки внешнего виджета — только прямые дети его таб-бара
    expect(widget.locator("> .tabbar > .tab")).to_have_count(2)

    # переключаем внутренний, затем внешний
    nested.locator(".tab").nth(1).click()
    expect(nested.locator(".tab-pane").nth(1)).to_contain_text("В2.2")
    widget.locator("> .tabbar > .tab").nth(1).click()
    expect(widget.locator("> .tab-pane").nth(1)).to_contain_text("В1.2")
    # внутренний НЕ сбросился внешним: остался на второй вкладке
    widget.locator("> .tabbar > .tab").nth(0).click()
    expect(widget.locator("> .tab-pane").nth(0)).to_contain_text("В1.1")
    expect(nested.locator(".tab").nth(1)).to_have_class(re.compile("active"))
    expect(nested.locator(".tab-pane").nth(1)).to_contain_text("В2.2")
    nested.locator(".tab").nth(0).click()
    expect(nested.locator(".tab-pane").nth(0)).to_contain_text("В2.1")
    # внешний при этом не сбросился
    expect(widget.locator("> .tab-pane").nth(0)).to_contain_text("В1.1")

    # 4 таб-части в контенте, все тексты целы
    saved = wiki_api.content_of(page_id)
    assert saved.count('data-block-part="tab"') == 4
    for marker in ("В1.1", "В1.2", "В2.1", "В2.2"):
        assert marker in saved
    assert page_errors == []


# ---------------------------------------------------------------------------
# H-заголовки (FR-121): TC-rich-014…017
# ---------------------------------------------------------------------------


def test_tc_rich_014_heading_toggle_off_undo_alive(editor_page, page_errors, web_base_url):
    """coverage-backfill-1; TC-rich-014: Повторный клик H2 снимает заголовок
    без потери текста, undo жив (F4). CLEAR-состояние: ни одна H-кнопка не
    нажата; Ctrl+Z откатывает снятие (execCommand('formatBlock') держит
    нативный undo-стек)."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("Текст заголовка")
    editor.select_all_text()

    # шаг 1: абзац → H2
    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_text("Текст заголовка")
    expect(editor.toolbar_button("Заголовок 2")).to_have_attribute(
        "aria-pressed", "true"
    )
    # шаг 2: повторный клик H2 — снятие, текст без изменения символов
    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_count(0)
    expect(editor.area.locator("p")).to_have_text("Текст заголовка")
    # шаг 3: CLEAR — ни одна H-кнопка не нажата
    _no_heading_pressed(editor)
    # шаг 4: Ctrl+Z — текст снова H2 (undo-стек жив, находка F4)
    page.keyboard.press("Control+Z")
    expect(editor.area.locator("h2")).to_have_text("Текст заголовка")
    _expect_heading_pressed(editor, "Заголовок 2", "true")
    assert page_errors == []


def test_tc_rich_015_heading_replace_h1_h3(editor_page, page_errors, web_base_url):
    """coverage-backfill-1; TC-rich-015: Замена уровня заголовка H1 → H3 без
    двойного нажатия. Тег h3 в DOM, нажата ровно кнопка H3, текст не
    изменен; Ctrl+Z откатывает замену уровня."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    page.keyboard.type("Строка уровня")
    editor.select_all_text()
    editor.toolbar_button("Заголовок 1").click()
    expect(editor.area.locator("h1")).to_have_text("Строка уровня")

    # шаг 2: H3 без двойного нажатия
    editor.toolbar_button("Заголовок 3").click()
    # шаг 3: тег h3 в DOM; нажата ровно H3 (DON'T-состояние недостижимо)
    expect(editor.area.locator("h3")).to_have_text("Строка уровня")
    expect(editor.area.locator("h1")).to_have_count(0)
    _expect_heading_pressed(editor, "Заголовок 3", "true")
    _expect_heading_pressed(editor, "Заголовок 1", "false")
    _expect_heading_pressed(editor, "Заголовок 2", "false")
    expect(editor.area.locator("h3")).to_have_text("Строка уровня")  # текст цел
    # шаг 4: Ctrl+Z откатывает замену уровня
    page.keyboard.press("Control+Z")
    expect(editor.area.locator("h1")).to_have_text("Строка уровня")
    expect(editor.area.locator("h3")).to_have_count(0)
    assert page_errors == []


def test_tc_rich_016_backspace_empty_heading_unformats(
    editor_page, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-016: Backspace в пустом заголовке снимает
    формат (ОВ-5). Пустая строка после Enter → H2 → Backspace = пустой абзац
    с курсором; сторожевой текст предыдущего абзаца цел; H-кнопки отжаты."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    # шаг 1: курсор в конец абзаца, Enter — новая пустая строка
    page.keyboard.type("Сторожевой абзац")
    page.keyboard.press("Enter")
    # шаг 2: пустая строка → H2 (не вводя текст)
    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_count(1)
    expect(editor.area.locator("h2")).to_have_text("")
    # шаг 3: Backspace
    page.keyboard.press("Backspace")
    # шаг 4: формат снят — пустой абзац p с курсором; сторожевой текст цел;
    # H-кнопки отжаты (ОВ-5, перехват keydown вместо слияния)
    expect(editor.area.locator("h2")).to_have_count(0)
    expect(editor.area.locator("p")).to_have_count(1)
    expect(editor.area.locator("p")).to_have_text("")
    expect(editor.area).to_contain_text("Сторожевой абзац")
    _no_heading_pressed(editor)
    # каретка в новом пустом абзаце
    anchor_p = page.evaluate(
        """() => {
          const n = window.getSelection().anchorNode;
          const e = n && (n.nodeType === 1 ? n : n.parentNode);
          const p = e && (e.closest ? e.closest('p') : null);
          return p ? p.textContent : null;
        }"""
    )
    assert anchor_p == "", anchor_p
    assert page_errors == []


def test_tc_rich_017_heading_buttons_follow_cursor(
    editor_page, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-017: Состояние H-кнопок отражает блок под
    курсором. H1 → ровно H1; H2 → ровно H2; обычный абзац — ни одной;
    синхронизация следует за курсором без клика по кнопкам."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()

    # шаг 1: три блока подряд H1, H2, обычный абзац (Enter из заголовка
    # создает обычный блок-абзац — абзац уже «обычный», без клика)
    page.keyboard.type("Блок аш-один")
    editor.select_all_text()
    editor.toolbar_button("Заголовок 1").click()
    expect(editor.area.locator("h1")).to_have_text("Блок аш-один")

    page.keyboard.press("End")
    page.keyboard.press("Enter")
    page.keyboard.type("Блок аш-два")
    page.keyboard.press("Home")
    page.keyboard.press("Shift+End")
    editor.toolbar_button("Заголовок 2").click()
    expect(editor.area.locator("h2")).to_have_text("Блок аш-два")

    page.keyboard.press("End")
    page.keyboard.press("Enter")
    page.keyboard.type("Блок абзац")
    blocks = page.evaluate(
        """() => Array.from(
          document.querySelectorAll('.editor-area > h1, .editor-area > h2, .editor-area > h3, .editor-area > p, .editor-area > div:not(.tbl-panel)')
        ).map((b) => [b.nodeName.toLowerCase(), b.textContent])"""
    )
    assert blocks == [
        ["h1", "Блок аш-один"],
        ["h2", "Блок аш-два"],
        ["div", "Блок абзац"],
    ], blocks

    # шаг 2: курсор в H1 — нажата ровно кнопка H1
    editor.area.locator("h1").click()
    _expect_heading_pressed(editor, "Заголовок 1", "true")
    _expect_heading_pressed(editor, "Заголовок 2", "false")
    _expect_heading_pressed(editor, "Заголовок 3", "false")
    # шаг 3: курсор в H2 — ровно H2
    editor.area.locator("h2").click()
    _expect_heading_pressed(editor, "Заголовок 2", "true")
    _expect_heading_pressed(editor, "Заголовок 1", "false")
    # курсор в обычном абзаце — не нажата ни одна
    editor.area.locator("> div:not(.tbl-panel)").last.click()
    _no_heading_pressed(editor)
    assert page_errors == []


# ---------------------------------------------------------------------------
# Таблицы (FR-122): TC-rich-018…021
# ---------------------------------------------------------------------------


def test_tc_rich_018_table_add_remove_row_col_target_cell(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-018: Добавление/удаление строк и столбцов
    относительно целевой ячейки. «+» — ниже и правее [2,2]; «−» удаляет
    именно добавленные; итог 3×3 с посимвольно исходными маркерами rNcM."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Таблица").click()  # шапка 3 + 2 строки × 3 = 3×3

    def cell_at(row: int, col: int):
        if row == 0:
            return editor.area.locator("thead th").nth(col)
        return editor.area.locator("tbody tr").nth(row - 1).locator("td").nth(col)

    # шаг 1: маркеры rNcM во все 9 ячеек (дефолтные «Колонка N» затираем)
    for row in range(3):
        for col in range(3):
            cell_at(row, col).click()
            page.keyboard.press("Home")
            page.keyboard.press("Shift+End")
            page.keyboard.type(f"r{row + 1}c{col + 1}")

    # шаг 2: курсор в [2,2]; «+» строка ниже, «+» столбец правее
    cell_at(1, 1).click()
    panel = editor.area.locator(".tbl-panel")
    expect(panel).to_be_visible()
    panel.get_by_role("button", name="Добавить строку ниже").click()
    expect(editor.area.locator("tr")).to_have_count(4)  # thead + 2 + новая
    cell_at(1, 1).click()
    expect(panel).to_be_visible()
    panel.get_by_role("button", name="Добавить столбец справа").click()
    expect(editor.area.locator("thead th")).to_have_count(4)

    # новая строка — НИЖЕ [2,2] (третья строка таблицы), новый столбец —
    # ПРАВЕЕ [2,2] (третий столбец), бывший третий сместился четвертым
    assert cell_at(2, 1).text_content() == ""
    assert cell_at(0, 2).text_content() == ""
    assert cell_at(0, 3).text_content() == "r1c3"

    # шаг 3: заполняем новые ячейки маркерами (новая строка, новый столбец)
    for col in range(4):
        cell_at(2, col).click()
        page.keyboard.type(f"r4c{col + 1}")
    for row in range(1, 4):
        cell_at(row, 2).click()
        page.keyboard.type(f"r{row + 1}c4")

    # шаг 4: «−» удаляет именно добавленные строку и столбец
    cell_at(2, 0).click()
    panel.get_by_role("button", name="Удалить строку").click()
    expect(editor.area.locator("tr")).to_have_count(3)
    cell_at(1, 2).click()
    expect(panel).to_be_visible()
    panel.get_by_role("button", name="Удалить столбец").click()
    expect(editor.area.locator("thead th")).to_have_count(3)

    # шаг 5: таблица 3×3, содержимое посимвольно исходное
    editor.title_input.fill("Таблица rNcM")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    wiki_api.register(page_id)
    body = page.locator(".article-body")
    expect(body.locator("tr")).to_have_count(3)
    expect(body.locator("thead th")).to_have_count(3)
    for row in range(3):
        for col in range(3):
            if row == 0:
                got = body.locator("thead th").nth(col).text_content()
            else:
                got = (
                    body.locator("tbody tr")
                    .nth(row - 1)
                    .locator("td")
                    .nth(col)
                    .text_content()
                )
            assert got == f"r{row + 1}c{col + 1}", (row, col, got)
    saved = wiki_api.content_of(page_id)
    assert "r4c" not in saved and "c4" not in saved
    assert page_errors == []


def test_tc_rich_019_table_last_row_col_not_deletable(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-019: Последняя строка и столбец не
    удаляются (таблица 1×1). Кнопки «−» disabled с title-подсказкой; клики
    ничего не меняют; после сохранения ячейка с текстом в статье."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Таблица").click()

    # сводим к 1×1 (каретка в таблице показывает панель; после каждого
    # удаления каретка переносится в соседнюю ячейку — панель не гаснет;
    # паттерн test_rich_tools)
    editor.area.locator("thead th").first.click()
    panel = editor.area.locator(".tbl-panel")
    expect(panel).to_be_visible()
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
    # единственная ячейка (td или th — доживает любая строка)
    last_cell = editor.area.locator("tr").first.locator("th,td").first
    last_cell.click()

    # шаги 2–3: «−» неактивны с подсказкой; клики ничего не меняют
    del_row = panel.get_by_role("button", name="Последнюю строку удалить нельзя")
    del_col = panel.get_by_role("button", name="Последний столбец удалить нельзя")
    expect(del_row).to_be_disabled()
    expect(del_col).to_be_disabled()
    del_row.dispatch_event("click")
    del_col.dispatch_event("click")
    expect(editor.area.locator("table")).to_have_count(1)  # таблица не исчезла
    expect(editor.area.locator("tr")).to_have_count(1)

    # ячейка с текстом (затираем дефолт «Колонка 1»); шаг 4: сохранение
    last_cell.click()
    page.keyboard.press("Home")
    page.keyboard.press("Shift+End")
    page.keyboard.type("Последняя ячейка")
    editor.title_input.fill("Таблица 1х1")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    wiki_api.register(page_id)
    body = page.locator(".article-body")
    expect(body.locator("table")).to_have_count(1)
    expect(body.locator("table")).to_contain_text("Последняя ячейка")
    assert "Последняя ячейка" in wiki_api.content_of(page_id)
    assert page_errors == []


def test_tc_rich_020_table_delete_whole_button(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-020: Удаление таблицы отдельной кнопкой
    (ОВ-4). Одно действие удаляет таблицу целиком, сторожа-абзацы целы;
    «−» строк/столбцов таблицу целиком не удаляют."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()

    # шаг 1: сторож до, таблица 2×2 с заполненными ячейками
    page.keyboard.type("Сторожа до таблицы")
    editor.toolbar_button("Таблица").click()
    # вставленная таблица: thead 3 колонки + tbody 2×3; сводим к 2×2
    # (панель видна при каретке в ячейке)
    panel = editor.area.locator(".tbl-panel")
    editor.area.locator("tbody tr").nth(0).locator("td").nth(2).click()
    expect(panel).to_be_visible()
    cell = editor.area.locator("tbody tr").nth(0).locator("td").nth(2)
    cell.click()
    panel.get_by_role("button", name="Удалить столбец").click()
    cell = editor.area.locator("tbody tr").nth(1).locator("td").nth(0)
    cell.click()
    panel.get_by_role("button", name="Удалить строку").click()
    expect(editor.area.locator("tr")).to_have_count(2)  # thead + 1 строка

    # заполняем 2×2 (затирая дефолтные «Колонка N») и ставим сторож после
    for row, locator_rows in ((0, "thead th"), (1, "tbody tr")):
        cols = editor.area.locator(locator_rows).first.locator("th,td")
        for col in range(cols.count()):
            if row == 0:
                editor.area.locator("thead th").nth(col).click()
            else:
                editor.area.locator("tbody tr").nth(0).locator("td").nth(col).click()
            page.keyboard.press("Home")
            page.keyboard.press("Shift+End")
            page.keyboard.type(f"Я{row}{col}")
    _caret_to_area_end(page)
    page.keyboard.type("Сторожа после таблицы")

    # шаг 2: отдельная кнопка «Удалить таблицу целиком»
    editor.area.locator("tbody td").first.click()
    panel.get_by_role("button", name="Удалить таблицу целиком").click()
    expect(editor.area.locator("table")).to_have_count(0)
    expect(editor.area).to_contain_text("Сторожа до таблицы")
    expect(editor.area).to_contain_text("Сторожа после таблицы")

    # шаг 3: в статье таблицы нет, оба сторожа не затронуты
    editor.title_input.fill("Таблица удалена кнопкой")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    wiki_api.register(page_id)
    body = page.locator(".article-body")
    expect(body.locator("table")).to_have_count(0)
    expect(body).to_contain_text("Сторожа до таблицы")
    expect(body).to_contain_text("Сторожа после таблицы")
    assert "<table" not in wiki_api.content_of(page_id)

    # шаг 4: «−» строк/столбцов таблицу ЦЕЛИКОМ не удаляют (минимум 1×1).
    # Замечание: шаг кейса выполняется в свежем редакторе — при редактировании
    # СОХРАНЕННОЙ страницы контекстная панель таблицы недоступна (загрузка
    # контента затирает panel; дефект продукта — BUG-022, см. test-model/bugs).
    page.goto(f"{web_base_url}/wiki?create=1")
    expect(editor.area).to_be_visible()
    editor.area.click()
    editor.toolbar_button("Таблица").click()
    expect(editor.area.locator("table")).to_have_count(1)
    editor.area.locator("thead th").first.click()  # каретка в таблице → панель
    panel = editor.area.locator(".tbl-panel")
    expect(panel).to_be_visible()
    for _ in range(10):
        rows = editor.area.locator("tr").count()
        cols = editor.area.locator("tr").first.locator("th,td").count()
        if rows > 1:
            panel.get_by_role("button", name="Удалить строку").click()
        elif cols > 1:
            panel.get_by_role("button", name="Удалить столбец").click()
        else:
            break
    expect(editor.area.locator("table")).to_have_count(1)  # ОВ-4: не исчезла
    expect(editor.area.locator("tr")).to_have_count(1)
    assert page_errors == []


def test_tc_rich_021_table_tab_enter_br_discriminator(
    editor_page, wiki_api, page_errors, web_base_url
):
    """coverage-backfill-1; TC-rich-021: Tab — следующая ячейка, Enter —
    перенос внутри ячейки. Дискриминатор: в контенте ячейка содержит ровно
    «один<br>два» (один <br>, без дублирования/слияния); tr/td не менялись."""
    page = editor_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    editor.area.click()
    editor.toolbar_button("Таблица").click()
    rows_before = editor.area.locator("tr").count()
    cells_before = editor.area.locator("td, th").count()

    # шаг 1: «один» + Enter + «два» в первой ячейке
    first_cell = editor.area.locator("tbody tr").nth(0).locator("td").nth(0)
    first_cell.click()
    page.keyboard.type("один")
    page.keyboard.press("Enter")
    page.keyboard.type("два")

    # шаг 2: Enter дал перенос ВНУТРИ ячейки — новой строки/ячейки нет
    expect(editor.area.locator("tr")).to_have_count(rows_before)
    cell_html = first_cell.evaluate("el => el.innerHTML")
    assert cell_html == "один<br>два", cell_html

    # шаг 3: Tab — курсор в следующую ячейку
    page.keyboard.press("Tab")
    assert _caret_cell_text(page) == ""  # следующая (пустая) ячейка
    page.keyboard.type("вторая ячейка")
    assert "вторая ячейка" in _caret_cell_text(page)

    # шаг 4: в сохраненном контенте ровно «один<br>два»; tr/td не изменились
    editor.title_input.fill("Таблица один-два")
    editor.save_button().click()
    page_id = _saved_page_id(page)
    wiki_api.register(page_id)
    saved = wiki_api.content_of(page_id)
    assert "один<br>два" in saved
    assert "один<br><br>два" not in saved and "одиндва" not in saved
    assert saved.count("<tr>") == rows_before
    assert saved.count("<td>") + saved.count("<th>") == cells_before
    # в статье перенос отображается
    article_cell = page.locator(".article-body tbody tr").nth(0).locator("td").nth(0)
    expect(article_cell.locator("br")).to_have_count(1)
    expect(article_cell).to_contain_text("один")
    expect(article_cell).to_contain_text("два")
    assert page_errors == []
