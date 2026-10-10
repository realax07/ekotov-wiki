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

# backend/app в sys.path (из корня репозитория — тесты api живут там;
# env-заглушки не нужны: app.sanitize ничего из конфига не читает).
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
)

from app.sanitize import sanitize_html  # noqa: E402


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


def test_empty_and_none_like_input():
    """TC-san-016: пустая строка — пустой выход."""
    assert sanitize_html("") == ""
