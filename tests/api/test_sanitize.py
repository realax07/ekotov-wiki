"""Юнит-тесты sanitizer (change add-wiki, tasks.md 2.2; design.md §4;
NFR-31, ОГР-8).

Обязательный негативный набор design.md §4 — дословно: <script> (с
содержимым), onclick, javascript:-ссылка, iframe, вложенная мутация
(<scr<script>ipt>); позитивный — вся разметка тулбара проходит без
искажений (FR-110: H1–H3, B/I/U, ul/ol, цитата, код-блок, ссылка,
таблица, изображение).

Запуск (из корня репозитория):
  python3 -m pytest tests/api/test_sanitize.py -v
(чистые юниты: импорт app.sanitize, без TestClient и БД.)
"""

import os
import sys

import pytest

# Плагин pytest-base-url тянет conftest-овский base_url (поллинг живого
# стенда) — санитайзеру стенд не нужен: перекрываем no-op'ом
# (паттерн test_wiki_api.py / test_comments_author_r8.py).
@pytest.fixture(scope="session", autouse=True)
def _verify_url():
    yield

# backend/app в sys.path (из корня репозитория — тесты api живут там;
# env-заглушки не нужны: app.sanitize ничего из конфига не читает).
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
)

from app.sanitize import (  # noqa: E402
    DATA_BLOCK_VALUES,
    DATA_BLOCK_PART_VALUES,
    DATA_LANG_VALUES,
    MAX_BLOCK_DEPTH,
    sanitize_html,
)


# --------------------------------------------------------------------------
# Негатив (design.md §4 — обязательный набор)
# --------------------------------------------------------------------------


def test_script_tag_removed_with_content():
    """TC-san-001: <script> вырезается С СОДЕРЖИМЫМ (design.md §4)."""
    out = sanitize_html("<p>ok</p><script>alert(1)</script><p>после</p>")
    assert "<script" not in out
    assert "alert(1)" not in out
    assert "<p>ok</p>" in out and "<p>после</p>" in out


def test_style_tag_removed_with_content():
    """TC-san-002: <style> вырезается с содержимым (design.md §4)."""
    out = sanitize_html("<style>body{display:none}</style><p>x</p>")
    assert "<style" not in out and "display:none" not in out
    assert "<p>x</p>" in out


def test_onclick_attribute_stripped():
    """TC-san-003: обработчики on* снимаются; прочие атрибуты (style, class,
    id) — тоже (design.md §4: whitelist)."""
    out = sanitize_html('<p onclick="evil()" style="x" class="c" id="i">текст</p>')
    assert "onclick" not in out and "evil" not in out
    assert "style" not in out and 'class="c"' not in out and 'id="i"' not in out
    assert "текст" in out


def test_javascript_href_removed_with_attribute():
    """TC-san-004: javascript:-ссылка — атрибут href вырезан целиком,
    текст ссылки остается."""
    out = sanitize_html('<a href="javascript:alert(1)">тыкни</a>')
    assert "javascript" not in out and "alert" not in out
    assert "<a>тыкни</a>" == out


def test_data_href_removed():
    """TC-san-005: data:-URL в href запрещен (разрешен только data:image/
    в img src — по ТЗ 2.2)."""
    out = sanitize_html('<a href="data:text/html,<b>x</b>">ссылка</a>')
    assert "data:" not in out and "ссылка" in out


def test_data_image_src_allowed_for_img():
    """TC-san-006: data:image/ в img src проходит (исключение по ТЗ 2.2)."""
    out = sanitize_html('<img src="data:image/png;base64,AAAA" alt="к">')
    assert 'src="data:image/png;base64,AAAA"' in out


def test_iframe_unwrapped_content_kept():
    """TC-san-007: запрещенный тег без содержимого-скрипта (iframe)
    разворачивается: содержимое остается, тег нет (design.md §4)."""
    out = sanitize_html("<p>до</p><iframe>внутри</iframe><p>после</p>")
    assert "iframe" not in out
    assert "внутри" in out and "до" in out and "после" in out


def test_nested_mutation_scr_script_ipt():
    """TC-san-008: вложенная мутация <scr<script>ipt> не восстанавливается
    в работающий <script> после фильтрации (обязательный кейс design.md §4)."""
    out = sanitize_html("<scr<script>ipt>alert(1)</script>")
    lowered = out.lower()
    # Ни один фрагмент не должен склеиться в работающий <script>.
    assert "<script" not in lowered
    assert "</script" not in lowered
    # Исполняемый код не должен остаться в форме, исполняемой браузером
    # как тег:alert при «доигрывании» мутации.
    assert "ipt>alert(1)" not in lowered.replace("&lt;", "<")


def test_event_handler_img_onerror():
    """TC-san-009: img c onerror — атрибут снимается, сам img остается."""
    out = sanitize_html('<img src="/images/1" onerror="evil()" alt="а">')
    assert "onerror" not in out and "evil" not in out
    assert 'src="/images/1"' in out and 'alt="а"' in out


def test_mixed_case_and_obfuscated_scheme():
    """TC-san-010: обход через регистр/управляющие символы в схеме —
    фильтр нормализует (JaVaScRiPt:, java\\tscript:)."""
    for url in ("JaVaScRiPt:alert(1)", "java\tscript:alert(1)", " javascript:x"):
        out = sanitize_html(f'<a href="{url}">x</a>')
        assert "script" not in out.lower() or "alert" not in out


def test_unknown_tag_unwrapped_text_kept():
    """TC-san-011: прочие запрещенные теги разворачиваются (текст остается)."""
    out = sanitize_html("<form><p>контент</p></form>")
    assert "form" not in out and "<p>контент</p>" in out


def test_plain_text_passthrough_and_escaping():
    """TC-san-012: чистый текст проходит; сырой < в тексте экранируется."""
    assert sanitize_html("просто текст") == "просто текст"
    out = sanitize_html("a < b и > c")
    assert "<script" not in out
    assert "&lt;" in out


# --------------------------------------------------------------------------
# Позитив: вся разметка тулбара (FR-110) проходит без искажений
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fragment",
    [
        "<h1>Заголовок</h1>",
        "<h2>Раздел</h2>",
        "<h3>Подраздел</h3>",
        "<p>Абзац</p>",
        "строка<br>разрыва",
        "<b>жирный</b>",
        "<strong>strong</strong>",
        "<i>курсив</i>",
        "<em>em</em>",
        "<u>подчеркнутый</u>",
        "<ul><li>пункт</li></ul>",
        "<ol><li>номер</li></ol>",
        "<blockquote>цитата</blockquote>",
        "<pre><code>код</code></pre>",
        '<a href="https://example.com" title="сайт">ссылка</a>',
        '<a href="/wiki/2">внутренняя</a>',
        '<img src="/images/5" alt="схема">',
        "<table><thead><tr><th colspan=\"2\">Шапка</th></tr></thead>"
        "<tbody><tr><td rowspan=\"1\">ячейка</td><td>еще</td></tr></tbody></table>",
        "<div>блок</div>",
        "<span>фрагмент</span>",
    ],
)
def test_toolbar_markup_passes(fragment):
    """TC-san-013: каждый элемент тулбара редактора (FR-110) проходит
    без искажений."""
    assert sanitize_html(fragment) == fragment


def test_full_toolbar_document_roundtrip():
    """TC-san-014: цельный документ из всей разметки тулбара — все теги и
    атрибуты на месте."""
    doc = (
        "<h1>Рецепт</h1><p>Тесто <b>плотное</b>, <i>вкусное</i> и <u>сытное</u>.</p>"
        "<ul><li>мука</li><li>вода</li></ul>"
        "<ol><li>смешать</li><li>месить</li></ol>"
        "<blockquote>Совет бабушки</blockquote>"
        "<pre><code>mix(a, b)</code></pre>"
        '<p><a href="https://example.com" title="источник">Статья</a> и '
        '<img src="/images/3" alt="фото"></p>'
        '<table><thead><tr><th>Ингр.</th></tr></thead><tbody><tr><td>Мука</td>'
        "</tr></tbody></table>"
    )
    assert sanitize_html(doc) == doc


def test_disallowed_attribute_on_allowed_tag():
    """TC-san-015: colspan на td — проходит; colspan на p — снимается
    (whitelist привязан к тегу)."""
    assert sanitize_html('<td colspan="2">x</td>') == '<td colspan="2">x</td>'
    assert sanitize_html('<p colspan="2">x</p>') == "<p>x</p>"


def test_img_width_integer_kept_and_non_integer_stripped():
    """TC-san-017 (возврат живой приемки 2026-10-11): img width — только целое.
    Целое сохраняется; дробное/мусор/пустое — атрибут снят, src/alt целы."""
    assert sanitize_html('<img src="/images/1" alt="с" width="480">') == (
        '<img src="/images/1" alt="с" width="480">'
    )
    out = sanitize_html('<img src="/images/1" alt="с" width="480.5">')
    assert "width" not in out
    assert 'src="/images/1"' in out and 'alt="с"' in out
    out = sanitize_html('<img src="/images/1" alt="с" width="abc">')
    assert "width" not in out and 'src="/images/1"' in out
    out = sanitize_html('<img src="/images/1" alt="с" width="">')
    assert "width" not in out and 'src="/images/1"' in out


def test_img_width_negative_and_injection_stripped():
    """TC-san-018 (возврат живой приемки 2026-10-11): отрицательное и
    инъекция через width снимаются целиком (атрибута нет)."""
    out = sanitize_html('<img src="/images/1" alt="с" width="-240">')
    assert "width" not in out and 'src="/images/1"' in out
    # onerror снимается, валидный width при этом сохраняется
    out = sanitize_html('<img src="/images/1" alt="с" width="10" onerror="x()">')
    assert "onerror" not in out and 'width="10"' in out
    # width не из whitelist других тегов — снимается
    out = sanitize_html('<p width="480">текст</p>')
    assert "width" not in out and "<p>текст</p>" == out


def test_empty_and_none_like_input():
    """TC-san-016: пустая строка — пустой выход."""
    assert sanitize_html("") == ""


# --------------------------------------------------------------------------
# P12 rich-блоки (design.md §1–§2, tasks.md 1.2; словарь — §1)
# --------------------------------------------------------------------------


SPOILER_HTML = (
    '<div data-block="spoiler" data-title="Скрытые детали">'
    '<div data-block-part="body"><p>тело спойлера</p></div></div>'
)
CODE_HTML = (
    '<div data-block="code" data-lang="python">'
    "<pre><code>def f():\n    return 1 &lt; 2</code></pre></div>"
)
TABS_HTML = (
    '<div data-block="tabs">'
    '<div data-block-part="tab" data-title="Обзор"><p>первая</p></div>'
    '<div data-block-part="tab" data-title="Детали"><p>вторая</p></div>'
    "</div>"
)


@pytest.mark.parametrize("fragment", [SPOILER_HTML, CODE_HTML, TABS_HTML])
def test_rich_valid_blocks_pass_byte_identical(fragment):
    """TC-san-019: валидные блоки (спойлер, код, табы) проходят санитайзер
    байт-в-байт (design.md §1–§2)."""
    assert sanitize_html(fragment) == fragment


def test_rich_invalid_data_block_value_stripped():
    """TC-san-020: data-block вне словаря — атрибут снят, блок деградирует
    в контент, текст сохранен (NFR-39, сценарий «Подмена значений»)."""
    out = sanitize_html('<div data-block="evil" data-lang="javascript">текст</div>')
    assert "data-block" not in out and "data-lang" not in out
    assert out == "<div>текст</div>"


def test_rich_invalid_data_part_and_lang_stripped():
    """TC-san-021: data-block-part/data-lang вне словаря — атрибуты сняты,
    остальное проходит."""
    out = sanitize_html('<div data-block-part="evil" data-lang="cobol">x</div>')
    assert out == "<div>x</div>"
    # валидные значения при этом живут
    ok = sanitize_html('<div data-block="code" data-lang="sql"><pre><code>1</code></pre></div>')
    assert 'data-block="code"' in ok and 'data-lang="sql"' in ok


def test_rich_depth_limit_six_unwrapped():
    """TC-san-022: 6 вложенных спойлеров — первые 5 остаются блоками,
    шестой разворачивается: содержимое сохранено, виджета нет (NFR-39)."""
    inner = '<div data-block="spoiler"><div data-block-part="body">глубина</div></div>'
    src = '<div data-block="spoiler"><div data-block-part="body">' * 5 + inner + "</div></div>" * 5
    out = sanitize_html(src)
    assert out.count('data-block="spoiler"') == 5
    assert "глубина" in out
    # идемпотентность: повторный прогон не меняет
    assert sanitize_html(out) == out


def test_rich_depth_five_passes():
    """TC-san-023: ровно 5 уровней — лимит соблюден, все блоки на месте."""
    inner = '<div data-block="spoiler"><div data-block-part="body">дно</div></div>'
    src = '<div data-block="spoiler"><div data-block-part="body">' * 4 + inner + "</div></div>" * 4
    out = sanitize_html(src)
    assert out.count('data-block="spoiler"') == 5
    assert "дно" in out


def test_rich_script_inside_spoiler_removed_with_content():
    """TC-san-024: script внутри спойлера вырезается С СОДЕРЖИМЫМ; onclick
    на шапке снимается; спойлер остается (NFR-39/NFR-31)."""
    src = (
        '<div data-block="spoiler" data-title="T" onclick="evil()">'
        '<div data-block-part="body"><script>alert(1)</script><p>ok</p>'
        '<img src="/i.png" onerror="x()"></div></div>'
    )
    out = sanitize_html(src)
    assert "script" not in out and "alert" not in out
    assert "onclick" not in out and "onerror" not in out and "evil" not in out
    assert '<div data-block="spoiler" data-title="T">' in out and "<p>ok</p>" in out


def test_rich_javascript_link_inside_block_cut():
    """TC-san-025: URL-фильтр работает внутри блоков (javascript:-ссылка
    в теле спойлера — атрибут вырезан)."""
    src = (
        '<div data-block="spoiler"><div data-block-part="body">'
        '<a href="javascript:alert(1)">тыкни</a></div></div>'
    )
    out = sanitize_html(src)
    assert "javascript" not in out and "alert" not in out
    assert "тыкни" in out


def test_rich_table_in_table_unwrapped_text_kept():
    """TC-san-026: таблица в ячейке разворачивается целиком — структурные
    теги вложенной таблицы не эмитятся, текст ячеек сохранен, ячейки
    разделены <br> (design.md §2, находка F3, paste-путь)."""
    src = (
        "<table><tbody><tr><td>внешняя"
        "<table><tbody><tr><td>a</td><td>b</td></tr>"
        "<tr><td>c</td></tr></tbody></table>"
        "</td><td>y</td></tr></tbody></table>"
    )
    out = sanitize_html(src)
    assert out == "<table><tbody><tr><td>внешняя<br>a<br>b<br>c</td><td>y</td></tr></tbody></table>"
    # идемпотентность
    assert sanitize_html(out) == out


def test_rich_table_in_table_keeps_only_one_table():
    """TC-san-027: вложенных table-тегов в выходе нет вовсе."""
    src = "<table><tr><td><table><tr><td>x</td></tr></table></td></tr></table>"
    out = sanitize_html(src)
    assert out.count("<table>") == 1 and out.count("x") == 1


def test_rich_spoiler_in_cell_survives():
    """TC-san-028: спойлер в ячейке таблицы (разрешено матрицей §6) —
    проходит целиком."""
    src = (
        "<table><tbody><tr><td>"
        '<div data-block="spoiler" data-title="Список">'
        '<div data-block-part="body">текст</div></div>'
        "</td></tr></tbody></table>"
    )
    assert sanitize_html(src) == src


def test_rich_tags_inside_code_block_unwrapped():
    """TC-san-029: внутри код-блока разрешены только pre/code и текст —
    прочие теги разворачиваются, текст сохранен (design.md §2)."""
    src = (
        '<div data-block="code" data-lang="plain"><pre><code>'
        "<b>жирный</b><span>спан</span>простой</code></pre></div>"
    )
    out = sanitize_html(src)
    assert "<b>" not in out and "<span>" not in out
    assert "жирныйспанпростой" in out
    assert '<div data-block="code" data-lang="plain"><pre><code>' in out


def test_rich_block_inside_code_block_unwrapped():
    """TC-san-030: любой блок внутри код-блока невозможен (матрица §6):
    div[data-block] внутри кода разворачивается, текст остается."""
    src = (
        '<div data-block="code" data-lang="plain"><pre><code>'
        '<div data-block="spoiler"><div data-block-part="body">x</div></div>'
        "</code></pre></div>"
    )
    out = sanitize_html(src)
    assert out == (
        '<div data-block="code" data-lang="plain"><pre><code>x</code></pre></div>'
    )


def test_rich_code_br_becomes_newline_not_merged():
    """F-1 (review-001, blocker): Enter в код-блоке редактора дает <br>
    внутри <code>; санитайзер эмитит текстовый \\n — строки кода НЕ
    сливаются в «line1line2» (инвариант design §1 «текст кода
    сохраняется», FR-119). Дискриминатор: до фикса тест падал."""
    src = (
        '<div data-block="code" data-lang="python"><pre><code>'
        "line1<br>line2</code></pre></div>"
    )
    out = sanitize_html(src)
    assert out == (
        '<div data-block="code" data-lang="python">'
        "<pre><code>line1\nline2</code></pre></div>"
    )
    assert "line1line2" not in out


def test_rich_code_multiline_br_roundtrip_idempotent():
    """F-1: уже-санитизированный многострочный код (с \\n) проходит
    байт-в-байт (идемпотентность санитайзера на сохранении)."""
    doc = (
        '<div data-block="code" data-lang="python">'
        "<pre><code>def f():\n    return 1\n\n\nx = 2</code></pre></div>"
    )
    assert sanitize_html(doc) == doc


def test_rich_code_trailing_br_keeps_trailing_newline():
    """F-1: br в КОНЦЕ непустого кода (Enter в конце строки) — хвостовой
    \\n сохраняется; гуттер статьи считает строки корректно."""
    src = (
        '<div data-block="code" data-lang="plain"><pre><code>'
        "line1<br></code></pre></div>"
    )
    assert sanitize_html(src) == (
        '<div data-block="code" data-lang="plain">'
        "<pre><code>line1\n</code></pre></div>"
    )


def test_rich_code_empty_block_br_anchor_stays_empty():
    """F-1, обратная сторона: ПУСТОЙ код-блок с br-якорем каретки
    (newCodeblockHtml) сохраняется пустым — якорные br не превращаются в
    мусорные \\n в БД (прежнее поведение до F-1 не деградировало)."""
    src = (
        '<div data-block="code" data-lang="python"><pre><code>'
        "<br></code></pre></div>"
    )
    assert sanitize_html(src) == (
        '<div data-block="code" data-lang="python"><pre><code></code></pre></div>'
    )


def test_rich_br_outside_code_context_untouched():
    """F-1, изоляция: br ВНЕ код-блока (абзац, ячейка таблицы, тело
    спойлера) проходит как <br> — \\n-подстановка только в code-контексте."""
    assert sanitize_html("<p>a<br>b</p>") == "<p>a<br>b</p>"
    assert (
        sanitize_html("<table><tbody><tr><td>один<br>два</td></tr></tbody></table>")
        == "<table><tbody><tr><td>один<br>два</td></tr></tbody></table>"
    )
    src = (
        '<div data-block="spoiler" data-title="t">'
        '<div data-block-part="body"><p>ok<br>fine</p></div></div>'
    )
    assert sanitize_html(src) == src


def test_sanitize_unclosed_tag_closed_cleanly():
    """Регресс санитайзера (попутно F-раунду): разрешенный тег, не
    закрытый до конца входа, дозакрывается ЧИСТЫМ закрывающим тегом —
    repr кортежа стека («</('p', None)>») в выходе невозможен."""
    assert sanitize_html("<p>hello") == "<p>hello</p>"
    assert sanitize_html("<b>x") == "<b>x</b>"


def test_rich_data_title_escaped():
    """TC-san-031: data-title с разметкой/кавычками экранируется при эмите
    (design.md §1: «произвольный текст, экранируется»)."""
    src = '<div data-block="spoiler" data-title="a&quot;b <i>c</i>"><div data-block-part="body">t</div></div>'
    out = sanitize_html(src)
    assert "<i>" not in out and 'data-title="a&quot;b &lt;i&gt;c&lt;/i&gt;"' in out


def test_rich_page_without_blocks_byte_identical():
    """TC-san-032: страница без блоков проходит байт-в-байт (design.md §2).
    Фикстура — уже-санитизированный документ из разметки тулбара
    (свойство идемпотентности санитайзера; O3 ревью №1: рукописный HTML
    «старого контента» не есть сохраненная страница)."""
    doc = (
        "<h1>Регламент</h1><p>Тесто <b>плотное</b>.</p>"
        "<ul><li>мука</li></ul>"
        "<blockquote>Совет</blockquote>"
        "<pre><code>mix(a)</code></pre>"
        '<p><a href="https://example.com" title="источник">Ссылка</a> и '
        '<img src="/images/3" alt="фото" width="480"></p>'
        '<table><thead><tr><th colspan="2">Шапка</th></tr></thead>'
        "<tbody><tr><td>Мука</td><td>1 кг</td></tr></tbody></table>"
        "<div>блок</div><span>фрагмент</span>"
    )
    assert sanitize_html(doc) == doc


def test_rich_dictionary_matches_js_model():
    """TC-san-033: словарь sanitize.py согласован с frontend/static/js/wiki/
    rich/model.js (design.md §1 — «константа продублирована в JS-модулях
    с тестом согласования»)."""
    import re

    model_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "frontend", "static", "js", "wiki", "rich", "model.js",
    )
    with open(model_path, encoding="utf-8") as fh:
        source = fh.read()

    def js_strings(array_name: str) -> set[str]:
        match = re.search(
            r"var " + array_name + r"\s*=\s*\[([^;\]]*)\]", source
        )
        assert match, f"массив {array_name} не найден в model.js"
        return set(re.findall(r"'([^']+)'", match.group(1)))

    assert js_strings("BLOCK_VALUES") == set(DATA_BLOCK_VALUES)
    assert js_strings("BLOCK_PART_VALUES") == set(DATA_BLOCK_PART_VALUES)
    assert js_strings("LANG_VALUES") == set(DATA_LANG_VALUES)
    # лимиты глубины и вкладок — те же числа
    assert f"var MAX_BLOCK_DEPTH = {MAX_BLOCK_DEPTH};" in source
    assert re.search(r"var TAB_LIMIT\s*=\s*8;", source)
