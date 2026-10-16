"""Юнит-тесты парсера/валидатора диалекта rich-редактора (change
add-rich-editor, tasks.md 1.1; design.md §1; FR-117, FR-118, FR-127).

Покрытие по задаче 1.1:
- (д) позитив каждого типа блока, негативы структуры, круговая
  преобразуемость, вложенность 2 уровней;
- (е) негативные тесты толерантности (ревью A-2): «legacy-текст, похожий
  на диалект» — ``:::`` в начале строки, GFM-шапка ``|…|``+``|---|``,
  ``` в тексте — валидатор не бросает необработанного исключения на
  re-save, кандидат не становится блоком (fallback-политика design §1:
  plain text + лог, БЕЗ 422).

Запуск (из корня репозитория):
  python3 -m pytest tests/api/test_rich_blocks.py -v
(чистые юниты: импорт app.rich_blocks, без TestClient и БД.)

Реестр тест→TC (rule 6): 1.1д позитивы/негативы — TC-richb-101…113;
круговая преобразуемость — TC-richb-114…116; строгие негативы — TC-richb-117…126;
толерантность (ревью A-2) — TC-richb-123…127.
Approved-матрица 3.3: границы содержимого ячеек — TC-blocks-103;
границы числа колонок — TC-blocks-105/106.
"""

import os
import sys

import pytest

# backend/app в sys.path (паттерн test_sanitize.py)
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
)

from app.rich_blocks import (  # noqa: E402
    RichSyntaxError,
    content_has_blocks,
    parse,
    parse_strict,
    serialize,
    serialize_nodes,
    validate,
)
from app.sanitize_rich import sanitize  # noqa: E402

# --------------------------------------------------------------------------
# Фикстуры-примеры (используются также тестом идентичности фронтового
# парсера, tests/web — grammar-фикстуры зеркалируются дословно)
# --------------------------------------------------------------------------

FIX_PLAIN_LEGACY = "<p>Старая страница</p>\nОбычный текст и <b>HTML</b> тулбара."

FIX_TABLE = """| Колонка 1 | Колонка 2 |
| :--- | ---: |
| a | 2 |
| строка | 3 |"""

FIX_COLUMNS = """:::columns
Первая колонка.
<<<
Вторая колонка.
:::"""

FIX_CALLOUT = """:::callout type=warn
Внимание: **важно** и [ссылка](/wiki/1)
:::"""

FIX_ASIDE = """:::aside
Врезка с текстом.
:::"""

FIX_SPOILER = """:::spoiler title="Секрет \\"скрытый\\""
Тайна.
:::"""

FIX_CODE = """```python
def f():
    return 42
```"""

FIX_IMAGE = "![Скрин](/images/abc.png){width=50}"

# URL со скобками (review-001-4.1 #2/#3): кандидат блока-изображения и
# инлайн-ссылка с ≥2 группами скобок в URL. ЗЕРКАЛИРУЮТСЯ дословно в
# GRAMMAR_FIXTURES tests/web/test_rich_editor.py — дифтест бэк/фронт.
FIX_IMAGE_PAREN_URL = "![a](javascript:alert(1))"
FIX_LINK_TWO_PAREN_GROUPS = "[ссылка](http://x/a(b)c(d))"

FIX_NESTED = """:::columns
:::aside
Врезка в колонке.
:::
<<<
:::callout type=info
Таблица в колонке:

| Т | Т |
| --- | --- |
| 1 | 2 |
:::
:::"""


# --------------------------------------------------------------------------
# Лимит глубины вложенности (review-001-4.1 #1, major)
# --------------------------------------------------------------------------


def _nested_callouts(n: int) -> str:
    """n вложенных :::callout (по одному на строку) + контент + n закрытий."""
    return ":::callout type=info\n" * n + "глубоко\n" + ":::\n" * n


def _tree_depth(nodes: list[dict]) -> int:
    """Максимальная вложенность контейнеров в дереве (text/code/image = 0)."""
    max_depth = 0
    for node in nodes:
        if node["type"] in ("text", "code", "image", "table"):
            continue
        children = node.get("children") or (
            [child for column in node.get("columns", []) for child in column]
        )
        max_depth = max(max_depth, 1 + _tree_depth(children))
    return max_depth


def test_max_depth_strict_is_structural_error():
    """TC-RICH-201 (review-001-4.1 #1): превышение MAX_DEPTH в строгом разборе
    — структурная ошибка RichSyntaxError (ValueError), попадает под
    толерантный fallback шва wiki.py, а НЕ RecursionError/500."""
    from app.rich_blocks import MAX_DEPTH

    with pytest.raises(RichSyntaxError) as excinfo:
        validate(_nested_callouts(MAX_DEPTH + 50))
    assert "глубина вложенности" in str(excinfo.value)


def test_max_depth_tolerant_parse_no_recursionerror():
    """TC-RICH-202 (review-001-4.1 #1): толерантный parse на 500 вложенных
    callout не бросает (раньше — RecursionError ≈ с n=500); результат —
    стабильная каноническая форма (текст/блоки, без падения рекурсии)."""
    deep = _nested_callouts(500)
    once = serialize(parse(deep))  # не бросает
    assert serialize(parse(once)) == once  # roundtrip стабилен


def test_max_depth_boundary_exact_max_depth_allowed():
    """TC-RICH-203 (review-001-4.1 #1): ровно MAX_DEPTH уровней вложенности —
    валидный диалект (дерево строится, блоки не деградируют в текст)."""
    from app.rich_blocks import MAX_DEPTH

    nodes = parse_strict(_nested_callouts(MAX_DEPTH))
    assert _tree_depth(nodes) == MAX_DEPTH
    assert serialize(parse_strict(_nested_callouts(MAX_DEPTH))) == _nested_callouts(
        MAX_DEPTH
    )


def test_max_depth_boundary_over_max_depth_rejected():
    """TC-RICH-204 (review-001-4.1 #1): MAX_DEPTH+1 уровней — структурная
    ошибка в strict и текст (без исключений) в толерантном разборе."""
    from app.rich_blocks import MAX_DEPTH, parse as tolerant_parse

    over = _nested_callouts(MAX_DEPTH + 1)
    with pytest.raises(RichSyntaxError):
        parse_strict(over)
    nodes = tolerant_parse(over)  # толерантно: не бросает, часть — текст
    assert nodes  # разбор непуст


def test_paren_url_grammar_fixtures_roundtrip():
    """TC-RICH-208 (review-001-4.1 #2/#3): URL-со-скобками фикстуры lossless —
    кандидат блока-изображения со скобками в URL не становится блоком, инлайн-
    ссылка с ≥2 группами скобок сохраняется дословно (каноническая форма =
    исходная строка; зеркало fixtures — tests/web GRAMMAR_FIXTURES)."""
    for fixture in (FIX_IMAGE_PAREN_URL, FIX_LINK_TWO_PAREN_GROUPS):
        assert serialize(parse(fixture)) == fixture, fixture
        assert not content_has_blocks(parse(fixture)), fixture


# --------------------------------------------------------------------------
# Позитив каждого типа (tasks.md 1.1д)
# --------------------------------------------------------------------------


def test_legacy_text_is_single_text_node():
    """TC-richb-101: Legacy-страница без диалекта: parse → 0 блоков (legacy passthrough)."""
    nodes = parse(FIX_PLAIN_LEGACY)
    assert [node["type"] for node in nodes] == ["text"]
    assert nodes[0]["text"] == FIX_PLAIN_LEGACY
    assert not content_has_blocks(nodes)


def test_parse_gfm_table():
    """TC-richb-102."""
    nodes = parse(FIX_TABLE)
    assert [node["type"] for node in nodes] == ["table"]
    table = nodes[0]
    assert table["header"] == ["Колонка 1", "Колонка 2"]
    assert table["align"] == ["left", "right"]
    assert table["rows"] == [["a", "2"], ["строка", "3"]]


def test_parse_columns():
    """TC-richb-103."""
    (node,) = parse(FIX_COLUMNS)
    assert node["type"] == "columns"
    assert len(node["columns"]) == 2  # минимум две колонки (FR-118)
    assert node["columns"][0][0]["text"] == "Первая колонка."
    assert node["columns"][1][0]["text"] == "Вторая колонка."


def test_parse_callout_type():
    """TC-richb-104."""
    (node,) = parse(FIX_CALLOUT)
    assert node == {
        "type": "callout",
        "callout_type": "warn",
        "children": [{"type": "text", "text": "Внимание: **важно** и [ссылка](/wiki/1)"}],
    }


def test_parse_aside_and_spoiler():
    """TC-richb-105."""
    (aside,) = parse(FIX_ASIDE)
    assert aside["type"] == "aside"
    (spoiler,) = parse(FIX_SPOILER)
    assert spoiler["type"] == "spoiler"
    assert spoiler["title"] == 'Секрет "скрытый"'  # \\" развернулось


def test_parse_code_block_literal():
    """TC-richb-106."""
    (node,) = parse(FIX_CODE)
    assert node == {"type": "code", "lang": "python", "code": "def f():\n    return 42"}


def test_parse_image_with_width():
    """TC-richb-107."""
    (node,) = parse(FIX_IMAGE)
    assert node == {"type": "image", "alt": "Скрин", "src": "/images/abc.png", "width": 50}


def test_parse_image_width_outside_whitelist_dropped():
    """TC-richb-108."""
    (node,) = parse("![a](/images/x.png){width=5}")
    assert node["width"] is None  # вне 10..100 — атрибут отброшен
    (node,) = parse("![a](/images/x.png){width=101}")
    assert node["width"] is None
    (node,) = parse("![a](/images/x.png)")
    assert node["width"] is None


def test_parse_mixed_legacy_and_blocks():
    """TC-richb-109."""
    content = "Вступление.\n\n" + FIX_TABLE + "\n\nЗаключение."
    assert [node["type"] for node in parse(content)] == [
        "text",
        "table",
        "text",
    ]


def test_parse_nested_two_levels():
    """TC-richb-110: Вложенность блоков 2 уровней (FR-127): врезка в колонке, таблица в
    callout в колонке."""
    nodes = parse(FIX_NESTED)
    (columns,) = nodes
    assert columns["type"] == "columns"
    first, second = columns["columns"]
    assert first[0]["type"] == "aside"
    assert second[0]["type"] == "callout"
    table = second[0]["children"][1]
    assert table["type"] == "table"
    assert table["rows"] == [["1", "2"]]


# --------------------------------------------------------------------------
# Круговая преобразуемость (tasks.md 1.1б)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        FIX_PLAIN_LEGACY,
        FIX_TABLE,
        FIX_COLUMNS,
        FIX_CALLOUT,
        FIX_ASIDE,
        FIX_SPOILER,
        FIX_CODE,
        FIX_IMAGE,
        FIX_NESTED,
        "Текст.\n\n" + FIX_TABLE + "\n\n" + FIX_CODE + "\n\nЕще текст.",
        "",
    ],
)
def test_roundtrip_parse_serialize_identity(content):
    """TC-richb-111: parse∘serialize = идентичность: serialize(parse(t)) каноничен и
    стабилен (двойной прогон не меняет текст)."""
    once = serialize(parse(content))
    twice = serialize(parse(once))
    assert twice == once


def test_roundtrip_tree_level():
    """TC-richb-112: parse(serialize(nodes)) == nodes — дерево восстанавливается точно."""
    nodes = parse(FIX_NESTED)
    assert parse(serialize_nodes(nodes)) == nodes


def test_serialize_canonicalizes_table_spacing():
    """TC-richb-113: Каноническая форма: ячейки с одной подбивкой пробелами (значения те же)."""
    nodes = parse("|a |b|\n|---|---|\n|1|2|")
    assert nodes[0]["type"] == "table"
    assert serialize_nodes(nodes) == "| a | b |\n| --- | --- |\n| 1 | 2 |"


# --------------------------------------------------------------------------
# Негативы структуры — строгий validate (tasks.md 1.1в)
# --------------------------------------------------------------------------


def test_validate_unclosed_container_raises_with_position():
    """TC-richb-114."""
    with pytest.raises(ValueError) as excinfo:
        validate("Текст.\n\n:::aside\nВрезка без закрытия")
    assert isinstance(excinfo.value, RichSyntaxError)
    assert excinfo.value.line == 3


def test_validate_unknown_container_type_raises():
    """TC-richb-115."""
    with pytest.raises(ValueError):
        validate(":::widget\nx\n:::")


def test_validate_callout_bad_type_raises():
    """TC-richb-116."""
    with pytest.raises(ValueError):
        validate(":::callout type=danger\nx\n:::")


def test_validate_callout_without_type_raises():
    """TC-richb-117."""
    with pytest.raises(ValueError):
        validate(":::callout\nx\n:::")


def test_validate_spoiler_without_title_raises():
    """TC-richb-118."""
    with pytest.raises(ValueError):
        validate(":::spoiler\nx\n:::")


def test_validate_single_column_raises():
    """TC-richb-119."""
    with pytest.raises(ValueError):
        validate(":::columns\nТолько одна.\n:::")


def test_validate_empty_column_raises():
    """TC-richb-120."""
    with pytest.raises(ValueError):
        validate(":::columns\n<<<\nВторая полная.\n:::")


def test_validate_unclosed_code_fence_raises():
    """TC-richb-121."""
    with pytest.raises(ValueError):
        validate("```python\nx = 1")


def test_validate_stray_column_separator_raises():
    """TC-richb-122."""
    with pytest.raises(ValueError):
        validate("Текст\n<<<\nПродолжение")


def test_validate_gfm_header_without_separator_is_not_block():
    """TC-richb-123: GFM-шапка без валидного разделителя — НЕ структурная ошибка:
    это legacy-текст (строковые кандидаты не блок)."""
    nodes = validate("| a | b |\n| --- |\n| 1 | 2 |")
    assert not content_has_blocks(nodes)


# --------------------------------------------------------------------------
# Негативные тесты толерантности (tasks.md 1.1е, ревью A-2):
# «legacy-текст, похожий на диалект» — parse не бросает, кандидат → текст
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lookalike",
    [
        "Строка с ::: в начале\n:::\nпросто текст\n:::",
        "| a | b |\n| --- |\n| 1 | 2 |",  # GFM-шапка без --- под каждой
        "```в тексте без закрытия\nкод",
        ":::widget неизвестный контейнер\n:::",
        "Текст\n<<<\nсепаратор вне колонок",
    ],
)
def test_tolerant_parse_lookalike_stays_text(lookalike):
    """TC-richb-124: Кандидат в блок, не прошедший разбор → текст; parse НЕ бросает."""
    nodes = parse(lookalike)  # не бросает
    assert not content_has_blocks(nodes)
    # Контент проходит через толерантный разбор без потерь (re-save
    # не меняет контент — fallback-политика design §1)
    assert serialize(nodes) == lookalike


def test_tolerant_parse_unclosed_container_keeps_raw_text():
    """TC-richb-125."""
    content = ":::aside\nНезакрытая врезка"
    nodes = parse(content)
    assert not content_has_blocks(nodes)
    assert serialize(nodes) == content  # re-save без изменения


def test_validate_never_unhandled_on_re_save_of_lookalikes():
    """TC-richb-126: Валидатор на re-save lookalike-контента бросает ValueError (ловится
    швом → fallback), но никогда — необработанного исключения иного типа."""
    for lookalike in (
        ":::aside\nбез закрытия",
        ":::columns\nодна колонка\n:::",
        ":::callout type=nope\nx\n:::",
    ):
        try:
            validate(lookalike)
            raise AssertionError("ожидался RichSyntaxError: " + lookalike)
        except RichSyntaxError:
            pass  # контрактный ValueError с позицией


def test_stray_close_marker_line_is_text():
    """TC-richb-127: Одиночный ::: без открывателя — не блок, проходит как текст."""
    nodes = parse("Первая строка\n:::\nВторая строка")
    assert not content_has_blocks(nodes)
    assert serialize(nodes) == "Первая строка\n:::\nВторая строка"


# --------------------------------------------------------------------------
# Approved-матрица 3.3: границы (TC-blocks-103, TC-blocks-105/106)
# --------------------------------------------------------------------------


def test_table_cell_content_boundaries():
    """TC-blocks-103 (FR-117): границы размера и содержимого ячеек —
    спецсимволы не ломают разбор строки/столбца, содержимое ячеек 1:1."""
    # 10×10: все 100 ячеек адресно, шапка + 9 строк
    header = [f"R1C{c}" for c in range(1, 11)]
    rows = [[f"R{r}C{c}" for c in range(1, 11)] for r in range(2, 11)]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * 10) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    (node,) = parse("\n".join(lines))
    assert node["type"] == "table"
    assert node["header"] == header
    assert node["rows"] == rows
    # 1×1 (одна колонка) — минимум класса: блок-таблица, шапка сохранена 1:1
    (node,) = parse("| x |\n| --- |")
    assert node == {
        "type": "table",
        "header": ["x"],
        "rows": [],
        "align": ["default"],
    }
    # пустая ячейка сохраняет позицию
    (node,) = parse("| a | b |\n| --- | --- |\n| | 2 |")
    assert node["rows"] == [["", "2"]]
    # экранированная черта, бэктики, юникод — содержимое ячейки 1:1
    (node,) = parse("| a \\| b | `x` |\n| --- | --- |\n| эмодзи 🎉 кириллица | 2 |")
    assert node["header"] == ["a | b", "`x`"]
    assert node["rows"] == [["эмодзи 🎉 кириллица", "2"]]
    # псевдо-GFM (шапка+разделитель) внутри ОДНОЙ ячейки — текст ячейки,
    # не вложенная таблица
    (node,) = parse(
        "| a | b |\n| --- | --- |\n| \\| c \\| d \\| --- \\| --- \\| | 2 |"
    )
    assert node["type"] == "table"
    assert node["rows"] == [["| c | d | --- | --- |", "2"]]


def test_columns_count_boundaries():
    """TC-blocks-105/106 (FR-118): порядок 3 колонок слева направо; границы
    числа колонок — минимум (1 колонка без <<< → толерантный fallback-текст,
    факт реализации), пустая колонка сохраняет позицию, представители 6 и 8
    колонок — все рядом в заданном порядке, содержимое целиком (верхняя
    граница НЕ заявляется)."""
    # 3 колонки, порядок слева направо
    three = ":::columns\nПервая\n<<<\nВторая\n<<<\nТретья\n:::"
    (node,) = parse(three)
    assert node["type"] == "columns"
    assert [col[0]["text"] for col in node["columns"]] == [
        "Первая",
        "Вторая",
        "Третья",
    ]
    # минимум: 1 колонка (без <<<) — не разбирается как колонки; ТОЛЕРАНТНЫЙ
    # fallback: диалектоподобный текст сохранен ЦЕЛИКОМ (A-2, факт реализации)
    single = ":::columns\nодна\n:::"
    (node,) = parse(single)
    assert node["type"] == "text"
    assert node["text"] == single
    # пустая колонка: ТОЛЕРАНТНЫЙ парсер сохраняет позицию (пустой text-узел
    # посередине); СТРОГИЙ валидатор при этом отвергает «колонку без
    # содержимого» (см. test_validate_empty_column_raises) — на сохранении
    # такой контент уходит в fallback-plain-text (A-2); расхождение с шагом 2
    # TC-blocks-106 («пустая колонка сохраняет позицию» на просмотре)
    # зафиксировано в матрице 3.3 как дивергенция кейса и design §1
    empty = ":::columns\nКол-1\n<<<\n\n<<<\nКол-3\n:::"
    (node,) = parse(empty)
    assert [col[0]["text"] for col in node["columns"]] == ["Кол-1", "", "Кол-3"]
    # представители большого класса: 6 и 8 колонок, порядок и содержимое
    for n in (6, 8):
        content = (
            ":::columns\n"
            + "\n<<<\n".join(f"Кол-{i}" for i in range(1, n + 1))
            + "\n:::"
        )
        (node,) = parse(content)
        assert node["type"] == "columns"
        cols = node["columns"]
        assert len(cols) == n
        assert [col[0]["text"] for col in cols] == [f"Кол-{i}" for i in range(1, n + 1)]
        # круговая преобразуемость на границе класса
        assert serialize(parse(serialize(parse(content)))) == serialize(parse(content))


# --------------------------------------------------------------------------
# BUG-018/019/020 (живая приемка p15-wiki-8): шов сохранения
# --------------------------------------------------------------------------


def test_bug019_image_width_roundtrip_through_sanitize_seam():
    """TC-RICH-218 (BUG-019): масштаб rich-изображения ({width=N}) переживает
    save→reload→re-save на шве sanitize_rich: width не теряется, whitelist
    NFR-34 (10..100) соблюден, re-save идемпотентен (контент не мутирует)."""
    content = "Вступление.\n\n![Скрин](/images/abc123.png){width=50}"
    once = sanitize(content)
    assert "{width=50}" in once  # width пережил санитизацию записи
    twice = sanitize(once)  # re-save после перечитывания
    assert twice == once  # идемпотентно — масштаб не теряется на re-save
    # граница whitelist: NFR-34 не расширен
    assert "{width=100}" in sanitize("![a](/images/x.png){width=100}")
    out_over = sanitize("![a](/images/x.png){width=101}")
    assert "{width" not in out_over and "![a](/images/x.png)" in out_over
    out_under = sanitize("![a](/images/x.png){width=9}")
    assert "{width" not in out_under and "![a](/images/x.png)" in out_under


def test_bug020_code_block_roundtrip_through_sanitize_seam():
    """TC-RICH-218 (BUG-020): код-блок переживает save→reload→re-save 1:1
    (FR-122): переносы/пробелы буквально, HTML-векторы — каноническое
    экранирование диалекта, re-save идемпотентен (подсветка/фон — фронт)."""
    content = "```python\ndef f(x):\n    return x + 42 <b>text</b>\n```"
    once = sanitize(content)
    assert "```python\ndef f(x):\n    return x + 42 &lt;b&gt;text&lt;/b&gt;\n```" == once
    assert sanitize(once) == once  # re-save без мутаций
