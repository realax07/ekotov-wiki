"""Rich-редактор wiki: рендер блоков, XSS-безопасность, парсер-идентичность
(change add-rich-editor, tasks.md 1.4–1.7, 2.1–2.5; FR-117…FR-124, FR-127;
NFR-35/36/38) — playwright-тесты по паттерну tests/web (стенд conftest:
uvicorn app + search + http.server static, tmp-БД + seed owner/wife).

Кейсы:
  TC-rich-101 → test_parser_matches_backend_on_grammar_fixtures (1.4а:
                фронтовый парсер = зеркалу бэкенда на grammar-фикстурах)
  TC-rich-102 → test_roundtrip_in_browser (1.4а: roundtrip текст→дерево→текст)
  TC-rich-103 → test_renderer_xss_vectors_no_executable_elements (1.4:
                renderer не создает исполняемых элементов, векторы 1.2)
  TC-rich-104 → test_view_table_3x2_and_two_columns (FR-117, FR-118)
  TC-rich-105 → test_view_callout_types_aside_spoiler_code_image (FR-119…FR-123)
  TC-rich-106 → test_spoiler_hidden_reveal_reload (FR-121)
  TC-rich-107 → test_table_inside_column_view (FR-127, рендер)
  TC-rich-108 → test_editor_opens_rich_page_and_preserves_content (1.6, FR-124)
  TC-rich-109 → test_editor_legacy_page_save_unchanged (1.6, FR-125/NFR-38)
  TC-rich-110 → test_editor_blocks_save_on_structural_error (1.6б: ошибка до
                отправки, запрос не уходит)
  TC-rich-111 → test_editor_insert_into_column_roundtrip (2.5, FR-127)
  TC-rich-112 → test_mixed_page_legacy_part_renders_as_before (1.7в)
  TC-RICH-201…213 → фиксы review-001-4.1 (MAX_DEPTH бэк/фронт, URL со
                скобками — инвариант зеркала и синхрон URL-групп, &amp;
                roundtrip, шов 500→fallback в test_wiki_api/test_sanitize_rich)

Изоляция: страницы создаются API от owner-сессии, удаляются в teardown.
"""

import os
import subprocess as sp
import sys
from pathlib import Path

import pytest
from playwright.sync_api import expect

_REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_BACKEND_DIR = _REPO_ROOT / "backend"

# backend/app для сверки с серверным парсером (1.4а)
sys.path.insert(0, str(REPO_BACKEND_DIR))

from app.rich_blocks import serialize as py_serialize  # noqa: E402
from app.rich_blocks import parse as py_parse  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

BASE_URL_ENV = "EKOTOV_WIKI_BASE_URL"
BASE_URL = os.environ.get(BASE_URL_ENV, "http://127.0.0.1:8080")

# Grammar-фикстуры (общие с tests/api/test_rich_blocks.py; патологические
# lookalike — ревью A-2). Канонические ожидания считает СЕРВЕРНЫЙ парсер
# прямо в тесте — расхождение фронтового зеркала = красный тест.
GRAMMAR_FIXTURES = [
    "<p>Старая страница</p>\nОбычный текст.",
    "| Колонка 1 | Колонка 2 |\n| :--- | ---: |\n| a | 2 |\n| строка | 3 |",
    ":::columns\nПервая колонка.\n<<<\nВторая колонка.\n:::",
    ":::callout type=warn\nВнимание: **важно** и [ссылка](/wiki/1)\n:::",
    ":::aside\nВрезка с текстом.\n:::",
    ':::spoiler title="Секрет \\"скрытый\\""\nТайна.\n:::',
    "```python\ndef f():\n    return 42\n```",
    "![Скрин](/images/abc.png){width=50}",
    "Текст с ::: в начале\n:::\nтекст\n:::",
    "| a | b |\n| --- |\n| 1 | 2 |",
    "```незакрытый\nкод",
    # URL со скобками (review-001-4.1 #2/#3, зеркалят FIX_* в
    # tests/api/test_rich_blocks.py дословно): кандидат блока-изображения
    # со скобками в URL — НЕ блок (текст); ссылка с ≥2 группами скобок —
    # инлайн-разметка, URL-группы бэка и фронта синхронны.
    "![a](javascript:alert(1))",
    "[ссылка](http://x/a(b)c(d))",
]

RICH_PAGE_CONTENT = """Вступление обычным абзацем.

| Колонка 1 | Колонка 2 |
| :--- | ---: |
| a | 2 |
| строка | 3 |

:::columns
Первая колонка.
<<<
Вторая колонка.
:::

:::callout type=warn
Предупреждение в callout.
:::

:::aside
Текст врезки.
:::

:::spoiler title="Секрет"
Скрытый текст спойлера.
:::

```python
def f(x):
    return x + 42  # комментарий
```

![Скрин](/images/abc123.png){width=50}
"""


# ---------------------------------------------------------------------------
# стенд: схема wiki (паттерн test_p15_wiki_editor.wiki_stand_schema)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def rich_stand_schema(web_server):
    db_path = web_server.get("db_path") if isinstance(web_server, dict) else None
    if not db_path:
        return
    mig_env = dict(os.environ, DB_PATH=db_path, SECRET_KEY="web-tests-secret-key")
    mig_env.pop("PYTHONPATH", None)
    mig = sp.run(
        [sys.executable, "-m", "app.migrate_wiki"],
        cwd=str(REPO_BACKEND_DIR), env=mig_env, capture_output=True, text=True,
    )
    assert mig.returncode == 0, f"migrate_wiki: {mig.stderr}"


@pytest.fixture
def rich_page_factory(web_base_url, web_owner_session):
    """Создание wiki-страницы с контентом; удаление в teardown."""
    created = []

    def _create(content: str, title: str = "QAT-rich") -> int:
        resp = web_owner_session.post(
            f"{web_base_url}/api/wiki/pages",
            json={"title": title + "-" + os.urandom(4).hex(), "content": content},
        )
        assert resp.status_code == 201, resp.text
        page_id = resp.json()["id"]
        created.append(page_id)
        return page_id

    yield _create
    for page_id in created:
        web_owner_session.delete(f"{web_base_url}/api/wiki/pages/{page_id}")


def _open_view(page, web_base_url, page_id):
    page.goto(f"{web_base_url}/wiki/{page_id}")
    expect(page.locator(".article-body")).to_be_visible()


def _open_editor(page, web_base_url, page_id):
    page.goto(f"{web_base_url}/wiki/{page_id}?edit=1")
    expect(page.locator(".editor-area")).to_be_visible()


# ---------------------------------------------------------------------------
# 1.4а/1.4б: парсер-идентичность и roundtrip (в браузере, на стенде)
# ---------------------------------------------------------------------------


def _js_parser(page):
    """Динамический импорт фронтового парсера на странице стенда (/static)."""

    def run(expression):
        return page.evaluate(
            "async (expr) => {"
            " const m = await import('/static/js/wiki/rich/block-parser.js');"
            " const fn = new Function('m', 'return ' + expr);"
            " return fn(m);"
            "}",
            expression,
        )

    return run


def test_parser_matches_backend_on_grammar_fixtures(logged_in_page):
    """TC-rich-101 (1.4а): фронтовый serialize∘parse идентичен серверному
    парсеру на grammar-фикстурах (включая lookalike — ревью A-2)."""
    js = _js_parser(logged_in_page)
    for fixture in GRAMMAR_FIXTURES:
        expected = py_serialize(py_parse(fixture))
        actual = js(f"m.serialize(m.parse({fixture!r}))")
        assert actual == expected, f"расхождение зеркала на: {fixture!r}"


def test_roundtrip_in_browser(logged_in_page):
    """TC-rich-102 (1.4а): roundtrip текст→дерево→текст стабилен
    (двойной прогон не меняет каноническую форму)."""
    js = _js_parser(logged_in_page)
    for fixture in GRAMMAR_FIXTURES:
        once = js(f"m.serialize(m.parse({fixture!r}))")
        twice = js(f"m.serialize(m.parse({once!r}))")
        assert once == twice


def test_renderer_xss_vectors_no_executable_elements(logged_in_page, web_base_url):
    """TC-rich-103 (1.4/1.2): renderer не создает исполняемых элементов ни
    на одном XSS-векторе NFR-35 (script/iframe/object/on*/javascript:)."""
    logged_in_page.goto(f"{web_base_url}/wiki")
    vectors = [
        {"type": "callout", "callout_type": "info",
         "children": [{"type": "text", "text": "<script>alert(1)</script>"}]},
        {"type": "table", "header": ["a"], "align": ["default"],
         "rows": [["<iframe src=\"x\"></iframe>"]]},
        {"type": "aside", "children": [{"type": "text", "text": "<object data=\"x\"></object>"}]},
        {"type": "spoiler", "title": "<b onclick=\"evil()\">титул</b>",
         "children": [{"type": "text", "text": "ok"}]},
        {"type": "callout", "callout_type": "warn",
         "children": [{"type": "text", "text": "[тыкни](javascript:alert(1))"}]},
        {"type": "columns",
         "columns": [[{"type": "table", "header": ["a"], "align": ["default"],
                       "rows": [["<script>alert(1)</script>"]]}],
                     [{"type": "text", "text": "ok"}]]},
        {"type": "code", "lang": "python", "code": "<script>alert(1)</script>"},
        {"type": "image", "alt": "x", "src": "javascript:alert(1)", "width": 50},
    ]
    result = logged_in_page.evaluate(
        """async (nodes) => {
          const renderer = await import('/static/js/wiki/rich/renderer.js');
          await import('/static/js/wiki/rich/blocks/tables.js');
          await import('/static/js/wiki/rich/blocks/columns.js');
          await import('/static/js/wiki/rich/blocks/callout.js');
          await import('/static/js/wiki/rich/blocks/aside.js');
          await import('/static/js/wiki/rich/blocks/spoiler.js');
          await import('/static/js/wiki/rich/blocks/code.js');
          const host = document.createElement('div');
          host.appendChild(renderer.renderMixed(nodes, { editing: false }));
          document.body.appendChild(host);
          const bad = [];
          host.querySelectorAll('script, iframe, object, embed').forEach((n) => bad.push(n.tagName));
          host.querySelectorAll('*').forEach((n) => {
            for (const attr of n.attributes) {
              if (attr.name.toLowerCase().startsWith('on')) bad.push(attr.name);
              if ((attr.name === 'href' || attr.name === 'src') &&
                  attr.value.toLowerCase().trim().startsWith('javascript:')) {
                bad.push(attr.name + '=javascript:');
              }
            }
          });
          return { bad, html: host.innerHTML };
        }""",
        vectors,
    )
    assert result["bad"] == [], result["bad"]
    # вектор в код-блоке — буквальный текст
    assert "&lt;script&gt;" in result["html"]
    # javascript:-src изображения не вставлен (src нейтрализован рендером)
    assert "javascript:" not in result["html"]


# ---------------------------------------------------------------------------
# Просмотр блоков (FR-117…FR-123, FR-127)
# ---------------------------------------------------------------------------


def test_view_table_3x2_and_two_columns(logged_in_page, rich_page_factory, web_base_url):
    """TC-rich-104 (FR-117, FR-118): таблица 3×2 и две колонки рядом,
    слева направо, содержимое целиком."""
    content = (
        "| Колонка 1 | Колонка 2 |\n| :--- | ---: |\n| a | 2 |\n| строка | 3 |\n\n"
        ":::columns\nПервая колонка.\n<<<\nВторая колонка.\n:::"
    )
    page_id = rich_page_factory(content)
    page = logged_in_page
    _open_view(page, web_base_url, page_id)

    table = page.locator(".article-body .rich-table")
    expect(table).to_be_visible()
    assert table.locator("thead th").count() == 2
    assert table.locator("tbody tr").count() == 2  # 3×2: шапка + 2 строки
    assert table.locator("tbody tr").nth(1).locator("td").nth(1).inner_text() == "3"

    columns = page.locator(".article-body .rich-columns .rich-column")
    assert columns.count() == 2
    assert "Первая" in columns.nth(0).inner_text()
    assert "Вторая" in columns.nth(1).inner_text()
    # колонки рядом (grid): левая граница второй правее правой границы первой
    box0 = columns.nth(0).bounding_box()
    box1 = columns.nth(1).bounding_box()
    assert box1["x"] > box0["x"] + box0["width"] - 5


def test_view_callout_types_aside_spoiler_code_image(
    logged_in_page, rich_page_factory, web_base_url
):
    """TC-rich-105 (FR-119…FR-123): warn-оформление отличимо от info/success
    (фоны), врезка ≠ callout ≠ абзац, код подсвечен, изображение в масштабе."""
    content = (
        ":::callout type=info\nИнфо.\n:::\n\n"
        ":::callout type=warn\nПредупреждение.\n:::\n\n"
        ":::callout type=success\nУспех.\n:::\n\n"
        ":::aside\nТекст врезки.\n:::\n\n"
        "```python\ndef f(x):\n    return x  # комментарий\n```\n\n"
        "![Скрин](/images/abc123.png){width=50}"
    )
    page_id = rich_page_factory(content)
    page = logged_in_page
    _open_view(page, web_base_url, page_id)

    def bg(selector):
        return page.locator(selector).evaluate(
            "el => getComputedStyle(el).backgroundColor"
        )

    info_bg = bg(".rich-callout-info")
    warn_bg = bg(".rich-callout-warn")
    success_bg = bg(".rich-callout-success")
    assert info_bg != warn_bg != success_bg, (info_bg, warn_bg, success_bg)

    # врезка: курсив и левая линия — отличие от callout (без заливки типов)
    aside = page.locator(".rich-aside")
    assert aside.evaluate("el => getComputedStyle(el).fontStyle") == "italic"
    assert aside.evaluate("el => getComputedStyle(el).borderLeftWidth") not in ("0px", "")
    assert bg(".rich-aside") not in (info_bg, warn_bg, success_bg)

    # код: моноширинный + подсветка (ключевые слова/комментарии — спаны)
    code = page.locator(".rich-code-code")
    expect(code).to_be_visible()
    mono = code.evaluate("el => getComputedStyle(el).fontFamily")
    assert "monospace" in mono
    assert code.locator(".rich-tok-kw").count() >= 1
    assert code.locator(".rich-tok-com").count() == 1
    # переносы/отступы буквальны: 4 пробела перед return
    assert "    return x" in code.inner_text()

    # изображение: width=50 → половина доступной ширины (style width 50%)
    img = page.locator(".article-body img")
    expect(img).to_be_attached()
    assert img.evaluate("el => el.style.width") == "50%"


def test_spoiler_hidden_reveal_reload(logged_in_page, rich_page_factory, web_base_url):
    """TC-rich-106 (FR-121): скрыт на свежей загрузке; раскрытие показывает
    содержимое без reload; перезагрузка — снова скрыт."""
    page_id = rich_page_factory(':::spoiler title="Секрет"\nТайное содержимое.\n:::')
    page = logged_in_page
    _open_view(page, web_base_url, page_id)

    spoiler = page.locator(".rich-spoiler")
    body = spoiler.locator(".rich-spoiler-body")
    assert spoiler.locator(".rich-spoiler-title").inner_text() == "Секрет"
    expect(body).to_be_hidden()  # скрыт на свежей загрузке

    spoiler.locator(".rich-spoiler-toggle").click()
    expect(body).to_be_visible()  # раскрытие без перезагрузки
    assert "Тайное содержимое" in body.inner_text()
    assert page.url.endswith(f"/wiki/{page_id}")  # reload не случился

    page.reload()
    expect(page.locator(".rich-spoiler-body")).to_be_hidden()  # снова скрыт


def test_table_inside_column_view(logged_in_page, rich_page_factory, web_base_url):
    """TC-rich-107 (FR-127): таблица внутри колонки рендерится корректно."""
    content = (
        ":::columns\n"
        "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
        "<<<\nТекст второй колонки.\n:::"
    )
    page_id = rich_page_factory(content)
    page = logged_in_page
    _open_view(page, web_base_url, page_id)
    nested = page.locator(".rich-columns .rich-column .rich-table")
    expect(nested).to_be_visible()
    assert nested.locator("tbody td").count() == 2


def test_mixed_page_legacy_part_renders_as_before(
    logged_in_page, rich_page_factory, web_base_url
):
    """TC-rich-112 (1.7в): смешанный контент — legacy-часть рендерится
    по-старому (HTML тулбара), rich-блок — рядом."""
    content = (
        "<h2>Старый заголовок</h2><p>Старый <b>HTML</b> тулбара.</p>\n\n"
        ":::callout type=info\nБлок диалекта.\n:::"
    )
    page_id = rich_page_factory(content)
    page = logged_in_page
    _open_view(page, web_base_url, page_id)
    assert page.locator(".article-body h2").inner_text() == "Старый заголовок"
    assert page.locator(".article-body b").inner_text() == "HTML"
    expect(page.locator(".article-body .rich-callout-info")).to_be_visible()


# ---------------------------------------------------------------------------
# Редактор (1.6, 2.5)
# ---------------------------------------------------------------------------


def test_editor_opens_rich_page_and_preserves_content(
    logged_in_page, rich_page_factory, web_base_url
):
    """TC-rich-108 (1.6, FR-124): страница с таблицей и колонками в редакторе
    рендерится тем же renderer; сохранение — roundtrip без потерь; вид в
    редакторе = вид на просмотре."""
    page_id = rich_page_factory(RICH_PAGE_CONTENT)
    page = logged_in_page
    _open_editor(page, web_base_url, page_id)

    area = page.locator(".editor-area")
    # WYSIWYG: блоки в редакторе рендерит тот же renderer (структуры те же)
    expect(area.locator(".rich-table")).to_be_visible()
    expect(area.locator(".rich-columns .rich-column")).to_have_count(2)
    expect(area.locator(".rich-callout-warn")).to_be_visible()
    expect(area.locator(".rich-aside")).to_be_visible()
    expect(area.locator(".rich-code-code")).to_be_visible()

    # правка ячейки таблицы → сохранение → содержимое на просмотре обновлено
    # (клик ставит каретку в ячейку; Ctrl+A выбрал бы весь editing host
    # канвы — не ячейку)
    cell = area.locator(".rich-table tbody td").first
    cell.click()
    page.keyboard.press("End")
    page.keyboard.type("-правка")
    page.get_by_role("button", name="Сохранить").click()
    page.wait_for_url(f"{web_base_url}/wiki/{page_id}")
    expect(page.locator(".article-body .rich-table")).to_be_visible()
    assert "a-правка" in page.locator(".article-body .rich-table").inner_text()
    # остальные блоки не потерялись (масштаб/структура кругом, FR-123в)
    expect(page.locator(".article-body .rich-columns .rich-column")).to_have_count(2)
    assert page.locator(".article-body img").evaluate("el => el.style.width") == "50%"


def test_editor_legacy_page_save_unchanged(
    logged_in_page, rich_page_factory, web_base_url, web_owner_session
):
    """TC-rich-109 (1.6, FR-125/NFR-38): старая страница открывается на правку
    и сохраняется без изменения контента (legacy-путь не тронут)."""
    legacy = "<p>Старая страница</p><p>Просто <b>HTML</b>.</p>"
    page_id = rich_page_factory(legacy)
    page = logged_in_page
    _open_editor(page, web_base_url, page_id)
    # rich-канва НЕ активирована: legacy-режим как до пакета
    assert page.locator(".editor-area .rich-block").count() == 0
    page.get_by_role("button", name="Сохранить").click()
    page.wait_for_url(f"{web_base_url}/wiki/{page_id}")
    stored = web_owner_session.get(f"{web_base_url}/api/wiki/pages/{page_id}").json()
    assert stored["content"] == legacy  # контент сохранен без изменения


def test_editor_blocks_save_on_structural_error(
    logged_in_page, rich_page_factory, web_base_url, web_owner_session
):
    """TC-rich-110 (1.6б): блок с незакрытым контейнером — сохранение
    блокируется с показом ошибки ДО запроса (строгая валидация нового
    rich-контента; на сервер 422 не уходит — design §1)."""
    page_id = rich_page_factory("Обычный текст до правки.")
    page = logged_in_page
    _open_editor(page, web_base_url, page_id)

    # Вставляем блоки и ломаем структуру через serialize-модель: колонки с
    # одной колонкой невозможны из UI (+ колонка), поэтому сценарий незакрытого
    # контейнера воспроизводим подменой сериализации в канве (ошибка должна
    # перехватиться в редакторе до отправки).
    # Вход в rich-режим кнопкой тулбара (вставка таблицы), затем порча
    # дерева: колонки с одной колонкой = структурная ошибка валидатора.
    page.locator(".tb-btn-block", has_text="Таблица").click()
    expect(page.locator(".editor-area .rich-table")).to_be_visible()
    page.evaluate(
        """async () => {
          const area = document.querySelector('.editor-area');
          area.__richCanvas.nodes.push({type: 'columns', columns: [[{type:'text',text:'x'}]]});
        }"""
    )
    request_sent = []
    page.on("request", lambda req: request_sent.append(req.url)
            if "/api/wiki/pages" in req.url else None)
    page.get_by_role("button", name="Сохранить").click()
    banner = page.locator("#wiki-editor .error-banner")
    expect(banner).to_be_visible()
    assert "Структурная ошибка" in banner.inner_text()
    assert request_sent == [], "запрос сохранения не должен был уйти"


def test_editor_insert_into_column_roundtrip(
    logged_in_page, rich_page_factory, web_base_url
):
    """TC-rich-111 (2.5, FR-127): таблица вставляется внутрь колонки,
    сохраняется, повторно редактируется без потерь; вложенность проходит
    sanitize_rich (XSS во вложенном — нейтрализован, серверная часть 1.2)."""
    page_id = rich_page_factory(
        ":::columns\nПервая колонка.\n<<<\nВторая колонка.\n:::"
    )
    page = logged_in_page
    _open_editor(page, web_base_url, page_id)

    # фокус в канву ПЕРВОЙ колонки → вставка таблицы внутрь (активная канва)
    column = page.locator(".editor-area .rich-columns .rich-column").first
    column.click()
    column.locator(".rich-textline").first.click()
    page.locator(".tb-btn-block", has_text="Таблица").click()
    nested = page.locator(".editor-area .rich-columns .rich-column").first
    expect(nested.locator(".rich-table")).to_be_visible()

    cell = nested.locator(".rich-table tbody td").first
    cell.click()
    page.keyboard.type("вложенная ячейка")
    page.get_by_role("button", name="Сохранить").click()
    page.wait_for_url(f"{web_base_url}/wiki/{page_id}")

    # повторное редактирование без потерь
    _open_editor(page, web_base_url, page_id)
    nested_edit = page.locator(".editor-area .rich-columns .rich-column").first
    expect(nested_edit.locator(".rich-table")).to_be_visible()
    assert "вложенная ячейка" in nested_edit.locator(".rich-table").inner_text()
    assert "Вторая колонка." in page.locator(".editor-area").inner_text()


# ---------------------------------------------------------------------------
# Фиксы review-001-4.1 (MAX_DEPTH + minor'ы #2…#4)
# ---------------------------------------------------------------------------


def test_editor_rejects_over_max_depth(logged_in_page):
    """TC-RICH-211 (review-001-4.1 #1, major): parseStrict на MAX_DEPTH+1
    вложенных :::callout бросает RichSyntaxError «глубина вложенности» —
    редактор отклоняет структурную ошибку ДО отправки; толерантный parse не
    бросает; MAX_DEPTH фронта = MAX_DEPTH бэкенда."""
    from app.rich_blocks import MAX_DEPTH as PY_MAX_DEPTH

    deep = ":::callout type=info\n" * (PY_MAX_DEPTH + 1) + "x\n" + ":::\n" * (
        PY_MAX_DEPTH + 1
    )
    result = _js_parser(logged_in_page)(
        f"""(() => {{
          let strictError = null;
          try {{ m.parseStrict({deep!r}); }} catch (e) {{
            strictError = {{ name: e.name, message: String(e.message) }};
          }}
          let tolerantThrew = false;
          try {{ m.parse({deep!r}); }} catch (e) {{ tolerantThrew = true; }}
          return {{ strictError, tolerantThrew, maxDepth: m.MAX_DEPTH }};
        }})()"""
    )
    assert result["maxDepth"] == PY_MAX_DEPTH  # зеркало лимита
    assert result["strictError"] is not None
    assert result["strictError"]["name"] == "RichSyntaxError"
    assert "глубина вложенности" in result["strictError"]["message"]
    assert result["tolerantThrew"] is False


def test_editor_roundtrip_amp_not_decoded(logged_in_page):
    """TC-RICH-213 (review-001-4.1 #4): литерал «&amp;» в тексте блока НЕ
    декодируется в редакторе (&lt;/&gt; — разворачиваются): открытие-правка-
    сохранение сохраняет AT&amp;T без мутации — roundtrip-сохранность."""
    result = logged_in_page.evaluate(
        """async () => {
          const renderer = await import('/static/js/wiki/rich/renderer.js');
          const node = { type: 'text', text: 'AT&amp;T 5&lt;6' };
          const element = document.createElement('div');
          renderer.renderCanvas(
            { nodes: [node], element },
            { editing: true, onChange() {} }
          );
          const shown = element.querySelector('.rich-textline').textContent;
          // правка DOM → write-back (observeWriteBack → folded(innerText))
          element.querySelector('.rich-textline').appendChild(
            document.createTextNode('!')
          );
          await new Promise((resolve) => setTimeout(resolve, 80));
          return { shown, stored: node.text };
        }"""
    )
    assert result["shown"] == "AT&amp;T 5<6"  # &lt; развернут, &amp; — НЕТ
    assert result["stored"] == "AT&amp;T 5&lt;6!"  # &amp; не мутировал


def test_render_inline_url_two_paren_groups_not_literal(logged_in_page):
    """TC-RICH-212 (review-001-4.1 #3): URL с ≥2 группами скобок фронтовый
    токенайзер рендерит ССЫЛКОЙ с полным URL (INLINE_TOKEN_RE = зеркало
    _URL_GROUP бэкенда), а не литеральным текстом (FR-124)."""
    result = logged_in_page.evaluate(
        """async () => {
          const renderer = await import('/static/js/wiki/rich/renderer.js');
          const target = document.createElement('div');
          renderer.renderInline(target, 'до [ссылка](http://x/a(b)c(d)) после');
          const a = target.querySelector('a');
          return { href: a ? a.getAttribute('href') : null,
                   text: a ? a.textContent : null };
        }"""
    )
    assert result["href"] == "http://x/a(b)c(d)"
    assert result["text"] == "ссылка"
    # бэкенд сохраняет ссылку дословно — URL-группы синхронны
    from app.sanitize_rich import sanitize_inline

    out = sanitize_inline("до [ссылка](http://x/a(b)c(d)) после")
    assert "[ссылка](http://x/a(b)c(d))" in out
