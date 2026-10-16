"""Юнит-тесты sanitize_rich (change add-rich-editor, tasks.md 1.2; design §3;
FR-126, NFR-35) — XSS по КАЖДОМУ вектору NFR-35 из specs/wiki-sanitize.

Набор (tasks.md 1.2д):
- script/iframe/object в содержимом блоков — хранятся/отдаются как текст;
- onerror в таблице, onclick в заголовке спойлера;
- javascript: в callout-ссылке и в ссылке таблицы;
- скрипт в таблице внутри колонки (вложенность);
- <script> в код-блоке — буквальный текст;
- инвариант passthrough legacy-части (ревью M-4):
  sanitize_rich(legacy) == sanitize_html(legacy) на фикстурах старых страниц.

Существующий sanitize-сьют wiki (test_sanitize.py) проходит без правок —
sanitize.py не тронут (директива Заказчика, design §3).

Запуск (из корня репозитория):
  python3 -m pytest tests/api/test_sanitize_rich.py -v

Реестр тест→TC (rule 6): векторы NFR-35 — TC-richs-101…115;
whitelist атрибутов — TC-richs-116…118; идемпотентность/структура — TC-richs-119/120;
инвариант M-4 — TC-richs-121/122.
Sweep-кейсы approved-матрицы (этап 3.3): script — TC-sec-304; iframe — TC-sec-306;
object/embed — TC-sec-307; обработчики on* — TC-sec-309; javascript:/data: —
TC-sec-311 (спойлер, регистр, data:-ссылка); опасные атрибуты — TC-sec-312;
обходы санитайзера — TC-sec-315.
"""

import os
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
)

from app.rich_blocks import parse, serialize  # noqa: E402
from app.sanitize import sanitize_html  # noqa: E402
from app.sanitize_rich import sanitize  # noqa: E402

# --------------------------------------------------------------------------
# Нейтрализация тегов script/iframe/object во всех типах блоков (NFR-35)
# --------------------------------------------------------------------------


def _no_executable_markup(text: str) -> bool:
    """В sanitized-тексте нет живых тегов: `<` встречается только в маркере
    колонок ``<<<`` (грамматика диалекта), но не в разметке."""
    stripped = "\n".join(
        line for line in text.split("\n") if line.strip() != "<<<"
    )
    return "<" not in stripped


def test_script_in_callout_neutralized():
    """TC-richs-101."""
    out = sanitize(":::callout type=info\nдо <script>alert(1)</script> после\n:::")
    assert _no_executable_markup(out)
    assert "alert(1)" in out  # как ТЕКСТ (хранится/отдается текстом)
    # и дерево парсера тоже не содержит сырых тегов
    assert _no_executable_markup(serialize(parse(out)))


def test_iframe_in_table_neutralized():
    """TC-richs-102."""
    out = sanitize("| a | b |\n| --- | --- |\n| <iframe src=\"x\"></iframe> | 2 |")
    assert _no_executable_markup(out)
    assert "&lt;iframe" in out


def test_object_in_aside_neutralized():
    """TC-richs-103."""
    out = sanitize(":::aside\n<object data=\"x\"></object>\n:::")
    assert _no_executable_markup(out)
    assert "data=\"x\"" in out  # содержимое осталось текстом


def test_onerror_in_table_cell_neutralized():
    """TC-richs-104."""
    out = sanitize("| a | b |\n| --- | --- |\n| <img src=\"/images/1\" onerror=\"evil()\"> | 2 |")
    assert _no_executable_markup(out)
    assert "onerror" in out  # как текст, не как атрибут


def test_onclick_in_spoiler_title_neutralized():
    """TC-richs-105."""
    out = sanitize(':::spoiler title="Клик <b onclick=\\"evil()\\">"\nТайна\n:::')
    assert _no_executable_markup(out)
    assert "onclick" in out


def test_onclick_in_callout_text_neutralized():
    """TC-richs-106."""
    out = sanitize(":::callout type=warn\n<b onclick=\"evil()\">жирный</b>\n:::")
    assert _no_executable_markup(out)


# --------------------------------------------------------------------------
# javascript:/data: URL в ссылках (NFR-35)
# --------------------------------------------------------------------------


def test_javascript_link_in_callout_neutralized():
    """TC-richs-107."""
    out = sanitize(
        ":::callout type=info\n[тыкни](javascript:alert(1))\n:::"
    )
    assert "javascript" not in out
    assert "[тыкни]()" in out  # URL вырезан, текст ссылки остался


def test_javascript_link_in_table_cell_neutralized():
    """TC-richs-108."""
    out = sanitize("| a | b |\n| --- | --- |\n| [x](javascript:alert(1)) | 2 |")
    assert "javascript" not in out
    assert "[x]()" in out


def test_javascript_image_src_neutralized():
    """TC-richs-109: Блок-изображение с javascript:-src: URL нейтрализован (блок остается)."""
    out = sanitize("![alt](javascript:x)")
    assert "javascript" not in out
    assert "![alt]()" in out


def test_javascript_image_inline_in_callout_neutralized():
    """TC-richs-110."""
    out = sanitize(":::callout type=info\n![alt](javascript:alert(1))\n:::")
    assert "javascript" not in out
    assert "![alt]()" in out


def test_data_url_in_image_neutralized():
    """TC-richs-111: data: в rich-изображении запрещен целиком (whitelist только
    http/https/относительные; data:image/-исключение legacy-sanitize на
    rich-путь не переносится — атрибуты диалекта, задача 1.2а)."""
    out = sanitize("![a](data:image/png;base64,AAAA)")
    assert "data:" not in out
    out = sanitize(":::aside\n![a](data:image/png;base64,AAAA)\n:::")
    assert "data:" not in out


def test_relative_and_https_urls_pass():
    """TC-richs-112."""
    content = "[внутр](/wiki/1) и [внешн](https://example.com) и ![к](/images/1.png){width=50}"
    out = sanitize(content)
    assert "[внутр](/wiki/1)" in out
    assert "[внешн](https://example.com)" in out
    assert "![к](/images/1.png){width=50}" in out


# --------------------------------------------------------------------------
# Вложенные блоки (NFR-35, FR-127)
# --------------------------------------------------------------------------


def test_script_in_table_inside_column_neutralized():
    """TC-richs-113."""
    content = """:::columns
Первая.
<<<
| a | b |
| --- | --- |
| <script>alert(1)</script> | 2 |
:::"""
    out = sanitize(content)
    assert _no_executable_markup(out)
    assert "alert(1)" in out  # текст сохранен


def test_vector_inside_nested_callout_in_column():
    """TC-richs-114."""
    content = """:::columns
:::callout type=success
[bad](javascript:x)
:::
<<<
ok
:::"""
    out = sanitize(content)
    assert "javascript" not in out


# --------------------------------------------------------------------------
# Код-блок: вектор — буквальный текст (NFR-35)
# --------------------------------------------------------------------------


def test_script_in_code_block_is_literal_text():
    """TC-richs-115."""
    content = "```\n<script>alert(1)</script>\n```"
    out = sanitize(content)
    assert _no_executable_markup(out)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out
    # код-блок остался код-блоком
    assert parse(out)[0]["type"] == "code"


# --------------------------------------------------------------------------
# Whitelist атрибутов диалекта (tasks.md 1.2б)
# --------------------------------------------------------------------------


def test_callout_type_whitelist():
    """TC-richs-116: Три типа проходят блоком; неизвестный тип — ТОЛЕРАНТНЫЙ fallback
    (ревью A-2): кандидат не блок, контент остается plain text (строгая
    валидация нового rich-контента — в редакторе до отправки, 1.6)."""
    for known in ("info", "warn", "success"):
        assert f"type={known}" in sanitize(f":::callout type={known}\nx\n:::")
    out = sanitize(":::callout type=danger\nx\n:::")
    assert not parse(out) or not any(
        node["type"] == "callout" for node in parse(out)
    )
    # belt-and-suspenders: нормализация и на уровне узла (sanitize_block)
    from app.sanitize_rich import sanitize_block

    assert sanitize_block(
        {"type": "callout", "callout_type": "danger", "children": []}
    )["callout_type"] == "info"


def test_image_width_whitelist_10_100():
    """TC-richs-117."""
    assert "{width=50}" in sanitize("![a](/images/1.png){width=50}")
    assert "{width=10}" in sanitize("![a](/images/1.png){width=10}")
    assert "{width=100}" in sanitize("![a](/images/1.png){width=100}")
    assert "width=9" not in sanitize("![a](/images/1.png){width=9}")
    assert "width=101" not in sanitize("![a](/images/1.png){width=101}")


def test_spoiler_title_kept_as_text():
    """TC-richs-118."""
    out = sanitize(':::spoiler title="Заголовок <i>x</i>"\nТайна\n:::')
    assert _no_executable_markup(out)
    assert "&lt;i&gt;x&lt;/i&gt;" in out  # разметка заголовка — как текст
    assert parse(out)[0]["type"] == "spoiler"  # структура спойлера цела


# --------------------------------------------------------------------------
# Идемпотентность (re-save не меняет контент)
# --------------------------------------------------------------------------


def test_sanitize_is_idempotent():
    """TC-richs-119."""
    content = """Вступление <b>с разметкой</b>.

| a | b |
| --- | --- |
| [x](javascript:alert(1)) | <script>2</script> |

:::callout type=warn
Текст ![к](/images/1.png){width=30}
:::"""
    once = sanitize(content)
    assert sanitize(once) == once


def test_structure_preserved_through_sanitize():
    """TC-richs-120: Санитизация не разрушает структуру диалекта (блоки остаются блоками)."""
    content = """:::columns
:::aside
<iframe></iframe>
:::
<<<
:::spoiler title="Т"
<script>x</script>
:::
:::"""
    nodes = parse(sanitize(content))
    (columns,) = nodes
    assert columns["type"] == "columns"
    assert columns["columns"][0][0]["type"] == "aside"
    assert columns["columns"][1][0]["type"] == "spoiler"


# --------------------------------------------------------------------------
# Инвариант legacy-passthrough (ревью M-4, tasks.md 1.2е):
# sanitize_rich(legacy) == sanitize_html(legacy)
# --------------------------------------------------------------------------


LEGACY_FIXTURES = [
    # plain text страница
    "Просто текст страницы.\nВторая строка.",
    # HTML тулбара FR-110
    "<h1>Заголовок</h1><p>Абзац с <b>жирным</b> и <a href=\"/wiki/1\">ссылкой</a>.</p>",
    # изображение FR-111
    "<p>Скрин</p><img src=\"/images/abc.png\" alt=\"скрин\" width=\"480\">",
    # пустой контент
    "",
    # смешанный HTML
    "<ul><li>пункт</li></ul><table><tr><td>1</td></tr></table>",
    # legacy-текст, похожий на диалект (ревью A-2) — fallback на legacy-путь
    "Строка с ::: в начале\n:::\nтекст\n:::",
    "| a | b |\n| --- |\n| 1 | 2 |",
    "```незакрытый код\nстрока",
]


def test_m4_invariant_legacy_passthrough():
    """TC-richs-121: На фикстурах старых страниц sanitize_rich работает идентично
    sanitize_html — re-save старой страницы не меняет контент (NFR-36/38)."""
    for legacy in LEGACY_FIXTURES:
        assert sanitize(legacy) == sanitize_html(legacy), legacy


def test_mixed_content_legacy_segment_passthrough():
    """TC-richs-122: В смешанном контенте legacy-сегмент проходит тот же sanitize_html,
    блоки — sanitize_rich (структурная нейтрализация на записи)."""
    legacy_part = "<p>Старый HTML</p>"
    content = legacy_part + "\n\n:::callout type=info\n[bad](javascript:x)\n:::"
    out = sanitize(content)
    assert out.startswith(sanitize_html(legacy_part) + "\n\n")
    assert "javascript" not in out


# --------------------------------------------------------------------------
# URL со скобками (review-001-4.1 #2 minor — security-инвариант зеркала;
# #3 minor — рассинхрон инлайн-URL-групп бэк/фронт)
# --------------------------------------------------------------------------


PAREN_URL_FIXTURES = [
    # кандидат блока-изображения с URL в скобках: НЕ матчится блок-regex
    # (_IMAGE_LINE_RE, URL-группа [^)\s]+) → весь контент — legacy-passthrough;
    # литерал javascript: остается как инертный ТЕКСТ (не в атрибуте).
    "![a](javascript:alert(1))",
    # то же с «безопасной» схемой — passthrough тоже литеральный
    "![к](/images/x(1).png)",
]


def test_paren_url_image_candidate_is_legacy_passthrough():
    """TC-RICH-205 (review-001-4.1 #2): строка-кандидат блока-изображения с
    URL, содержащим скобки, уходит в legacy-passthrough — sanitize_rich
    идентичен sanitize_html (инвариант M-4); инвариант «зеркало regex =
    security-граница» задокументирован в ОБОИХ парсерах (sanitize_rich.py,
    block-parser.js), фронт рендерит такой сегмент текстом."""
    for fixture in PAREN_URL_FIXTURES:
        assert sanitize(fixture) == sanitize_html(fixture), fixture
    # вектор javascript: остается литеральным текстом, но НЕ исполняется:
    # он не в атрибуте href/src, а в текстовом узле (textContent).
    out = sanitize("![a](javascript:alert(1))")
    assert "![a](javascript:alert(1))" in out


def test_paren_url_inline_in_block_neutralized():
    """TC-RICH-206 (review-001-4.1 #2): ВНУТРИ блока диалекта инлайн-разметка
    с URL в скобках фильтруется rich-путем — javascript:-URL нейтрализован,
    текст остается."""
    out = sanitize(":::callout type=info\n![a](javascript:alert(1))\n:::")
    assert "javascript" not in out
    assert "![a]()" in out
    out2 = sanitize(":::callout type=info\n[тык](javascript:alert(1))\n:::")
    assert "javascript" not in out2
    assert "[тык]()" in out2


def test_inline_url_two_paren_groups_kept_intact():
    """TC-RICH-207 (review-001-4.1 #3): инлайн-ссылка с URL, содержащим ≥2
    группы скобок, бэкендом сохраняется ЦЕЛИКОМ (та же URL-группа
    _URL_GROUP, что у фронтового токенайзера renderer.js INLINE_TOKEN_RE —
    sync-инвариант FR-124 «что видишь — то сохранишь»)."""
    out = sanitize(":::callout type=info\n[ссылка](http://x/a(b)c(d))\n:::")
    assert "[ссылка](http://x/a(b)c(d))" in out


# --------------------------------------------------------------------------
# Sweep-кейсы approved-матрицы 3.3: вектор × все типы блоков (NFR-35
# «во всех поддерживаемых типах»);-approved TC-sec-304/306/307/309/311/312/315.
# --------------------------------------------------------------------------


def _assert_structure_kept(out: str, *block_types: str) -> None:
    """Структура диалекта не разрушена: блоки перечисленных типов остаются."""
    types = [node["type"] for node in parse(out)]
    for expected in block_types:
        assert expected in types, (expected, types)


@pytest.mark.parametrize(
    "content,kept",
    [
        # ячейка таблицы / колонка / врезка / спойлер (заголовок и содержимое)
        ("| a | b |\n| --- | --- |\n| <script>alert(1)</script> | 2 |", ("table",)),
        (":::columns\n<script>alert(1)</script>\n<<<\nok\n:::", ("columns",)),
        (":::aside\n<script>alert(1)</script>\n:::", ("aside",)),
        (':::spoiler title="С"\n<script>alert(1)</script>\n:::', ("spoiler",)),
        (':::spoiler title="<script>alert(1)</script>"\nТайна\n:::', ("spoiler",)),
        # подпись изображения (alt) — остается блоком, вектор — текстом
        ("![<script>alert(1)</script>](/images/x.png){width=50}", ("image",)),
    ],
)
def test_script_sweep_across_block_types(content, kept):
    """TC-sec-304: вектор script нейтрализован в КАЖДОМ типе блока —
    исполняемой разметки нет, текст сохранен, структура блока цела."""
    out = sanitize(content)
    assert _no_executable_markup(out)
    assert "alert(1)" in out  # как ТЕКСТ
    _assert_structure_kept(out, *kept)


@pytest.mark.parametrize(
    "content,kept",
    [
        (":::callout type=info\n<iframe src=\"https://evil.example\"></iframe>\n:::", ("callout",)),
        (":::aside\n<iframe src=\"https://evil.example\"></iframe>\n:::", ("aside",)),
        (":::columns\n<iframe src=\"https://evil.example\"></iframe>\n<<<\nok\n:::", ("columns",)),
        (':::spoiler title="<iframe src=x></iframe>"\n<iframe src=x></iframe>\n:::', ("spoiler",)),
        ("![<iframe src=x></iframe>](/images/x.png)", ("image",)),
    ],
)
def test_iframe_sweep_across_block_types(content, kept):
    """TC-sec-306: iframe нейтрализован в каждом типе блока (embed не
    соберется ни в одном типе — тег экранирован на записи)."""
    out = sanitize(content)
    assert _no_executable_markup(out)
    assert "&lt;iframe" in out
    _assert_structure_kept(out, *kept)


@pytest.mark.parametrize(
    "content,kept",
    [
        # врезка (основной сценарий) + вариант <embed>
        (":::aside\n<object data=\"https://evil.example/x.swf\"></object>\n:::", ("aside",)),
        (":::aside\n<embed src=\"https://evil.example/x.swf\">\n:::", ("aside",)),
        # sweep по остальным типам: callout / колонка / ячейка таблицы /
        # спойлер (заголовок и содержимое) / подпись изображения
        (":::callout type=info\n<object data=\"https://evil.example/x.swf\"></object>\n:::", ("callout",)),
        (":::columns\n<object data=\"https://evil.example/x.swf\"></object>\n<<<\nok\n:::", ("columns",)),
        ("| a | b |\n| --- | --- |\n| <object data=\"https://evil.example/x.swf\"></object> | 2 |", ("table",)),
        (':::spoiler title="<object data=x></object>"\n<object data="x"></object>\n:::', ("spoiler",)),
        ("![<object data=x></object>](/images/x.png)", ("image",)),
        # код-блок: вектор — литеральный текст, код-блок остается код-блоком
        ("```html\n<object data=\"x\"></object>\n```", ("code",)),
    ],
)
def test_object_embed_sweep_across_block_types(content, kept):
    """TC-sec-307: object/embed отсутствуют как элементы во ВСЕХ типах блоков
    (врезка + callout + колонка + таблица + спойлер + подпись + код-блок);
    встроенный объект не собирается ни в одном типе (экранирование на записи)."""
    out = sanitize(content)
    assert _no_executable_markup(out)
    assert "&lt;object" in out or "&lt;embed" in out
    _assert_structure_kept(out, *kept)


@pytest.mark.parametrize(
    "content",
    [
        ':::callout type=info\n<span onmouseover="evil()">x</span>\n:::',
        ":::aside\n<div onfocus=\"evil()>y</div>\n:::",
        "| a | b |\n| --- | --- |\n| <td onclick=\"evil()\">x</td> | 2 |",
        "![<img src=x onload=\"evil()\">](/images/x.png)",
        ':::spoiler title="<b onerror=\"evil()\">С</b>"\nТайна\n:::',
    ],
)
def test_event_handler_sweep_across_block_types(content):
    """TC-sec-309: обработчики on* (onmouseover/onfocus/onclick/onload/
    onerror) не попадают в DOM ни в одном типе блока — разметка экранируется
    целиком, обработчик остается инертным текстом."""
    out = sanitize(content)
    assert _no_executable_markup(out)


def test_javascript_url_sweep_spoiler_case_and_data_links():
    """TC-sec-311: javascript:-URL (в любом регистре) и data:-ссылка с html
    нейтрализованы в содержимом спойлера, колонке, таблице (caps-регистр) и
    врезке; текст ссылки остается, URL вырезан ([текст]())."""
    # содержимое спойлера — представитель sweep по типам блоков
    out = sanitize(':::spoiler title="С"\n[w](javascript:alert(\'spoiler\'))\n:::')
    assert "javascript" not in out.lower()
    assert "[w]()" in out
    assert parse(out)[0]["type"] == "spoiler"
    # регистр — граница: JAVASCRIPT: в колонке
    out = sanitize(":::columns\n[z](JAVASCRIPT:alert('col'))\n<<<\nok\n:::")
    assert "javascript" not in out.lower()
    assert "[z]()" in out
    # caps в ячейке таблицы
    out = sanitize("| a | b |\n| --- | --- |\n| [x](JavaScript:alert(1)) | 2 |")
    assert "javascript" not in out.lower()
    assert "[x]()" in out
    # data:-ссылка с html во врезке
    out = sanitize(":::aside\n[y](data:text/html,<script>alert(1)</script>)\n:::")
    assert "data:" not in out
    assert "<script>" not in out
    assert "[y]()" in out


@pytest.mark.parametrize(
    "content,kept",
    [
        (':::callout type=info\n<span style="background:url(javascript:alert(1))">x</span>\n:::', ("callout",)),
        ('| a | b |\n| --- | --- |\n| <a href="#" formaction="javascript:alert(2)">y</a> | 2 |', ("table",)),
        (':::aside\n<img srcset="javascript:alert(3)">\n:::', ("aside",)),
        (':::columns\n<form action="javascript:alert(4)"><input></form>\n<<<\nok\n:::', ("columns",)),
        (':::spoiler title="m"\n<meta http-equiv="refresh" content="0;url=javascript:alert(5)">\n:::', ("spoiler",)),
    ],
)
def test_dangerous_attributes_sweep_across_block_types(content, kept):
    """TC-sec-312: опасные атрибуты (style с javascript:-url, formaction,
    srcset, form action, meta refresh) не попадают в DOM ни в одном типе
    блока — тег экранирован на записи целиком; whitelist диалекта при этом
    жив (позитив-контроль ниже, TC-blocks-114)."""
    out = sanitize(content)
    assert _no_executable_markup(out)
    _assert_structure_kept(out, *kept)
    # позитив-контроль: валидный атрибут диалекта не задет
    assert "{width=50}" in sanitize("![a](/images/1.png){width=50}")


@pytest.mark.parametrize(
    "content",
    [
        # смешанный регистр тега
        ":::callout type=info\n<ScRiPt>alert(1)</sCrIpT>\n:::",
        # вложенная мутация (прецедент BUG-AF-RECHECK-004)
        ":::callout type=info\n<scr<script>ipt>alert(1)</script>\n:::",
        # незакрытый тег
        ":::callout type=info\n<script src=https://evil.example/x.js\n:::",
        # caps-атрибуты
        ":::callout type=info\n<IMG SRC=x ONERROR=alert(1)>\n:::",
        # худший класс — повтор в ячейке таблицы
        "| a | b |\n| --- | --- |\n| <ScRiPt>alert(1)</sCrIpT> | 2 |",
    ],
)
def test_sanitizer_bypass_classes_neutralized(content):
    """TC-sec-315: классы обходов (регистр, вложенная мутация, незакрытый
    тег, caps-атрибуты) нейтрализованы — исполняемой разметки в
    sanitized-контенте нет ни в одном случае."""
    out = sanitize(content)
    assert _no_executable_markup(out)
    assert sanitize(out) == out  # идемпотентность на обходах


def test_sanitizer_encoded_and_control_char_urls_inert():
    """TC-sec-315 (энкодинги/управляющие символы в схеме): HTML-энкодинг
    &#106;avascript: и таб внутри схемы НЕ образуют исполняемого href —
    URL-фильтр диалекта вырезает literal-схемы javascript:/data:, остаток —
    инертный текст ссылки; структура блока цела."""
    out = sanitize(":::callout type=info\n[a](&#106;avascript:alert(1))\n:::")
    assert _no_executable_markup(out)
    assert parse(out)[0]["type"] == "callout"  # блок цел
    # таб в схеме: java\tscript: не матчится ни как валидный URL, ни как
    # javascript: — рендер не создает href с исполняемой схемой (инертный
    # текст; DOM-граница — структурно безопасный renderer, TC-rich-103)
    out = sanitize(":::callout type=info\n[j](java\tscript:alert(1))\n:::")
    assert _no_executable_markup(out)
    assert parse(out)[0]["type"] == "callout"
