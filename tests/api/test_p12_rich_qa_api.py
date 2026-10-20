"""QA-сьют p12-rich-tools — API-часть (sanitize/round-trip через живой стенд).

Прогон по чек-листу test-model/cases/p12-rich-tools/ (TC-rich-001..041).
Здесь — sanitize-кейсы и paste-пути через PUT/GET /api/wiki/pages/<id>
(README чек-листа: «вставка paste-подобного контента — прямым PUT HTML»).
UI/e2e-часть тех же кейсов — tests/web/test_p12_rich_qa.py.

Требует поднятый стенд (scripts/qa_stand_up.sh): EKOTOV_WIKI_BASE_URL.
"""

import pytest

pytestmark = [pytest.mark.api, pytest.mark.must]

SPOILER = (
    '<div data-block="spoiler" data-title="{t}">'
    '<div data-block-part="body"><p>{b}</p></div></div>'
)


@pytest.fixture
def qa_page(owner_session, base_url):
    """Создать/удалить wiki-страницу; возвращает (id, put, get)."""
    created = []

    def make(title, content=""):
        resp = owner_session.post(
            f"{base_url}/api/wiki/pages",
            json={"title": title, "content": content},
        )
        assert resp.status_code == 201, resp.text
        pid = resp.json()["id"]
        created.append(pid)
        return pid

    def put(pid, content):
        resp = owner_session.put(
            f"{base_url}/api/wiki/pages/{pid}", json={"content": content}
        )
        assert resp.status_code == 200, resp.text
        return resp

    def get(pid):
        resp = owner_session.get(f"{base_url}/api/wiki/pages/{pid}")
        assert resp.status_code == 200, resp.text
        return resp.json()["content"]

    yield SimpleNamespace_(make, put, get)
    for pid in created:
        owner_session.delete(f"{base_url}/api/wiki/pages/{pid}")


def SimpleNamespace_(make, put, get):  # noqa: N802 — локальный хелпер
    from types import SimpleNamespace

    return SimpleNamespace(make=make, put=put, get=get)


# ---------------------------------------------------------------------------
# TC-rich-009 — нераспознанный язык: data-lang снят, текст цел
# ---------------------------------------------------------------------------


def test_tc_rich_009_unknown_lang_stripped_text_kept(qa_page):
    """S9 (Should): data-lang="cobol" вне словаря — атрибут снят на записи,
    текст кода посимвольно цел."""
    pid = qa_page.make("QA-09 код cobol")
    qa_page.put(
        pid,
        '<div data-block="code" data-lang="cobol"><pre><code>'
        "MOVE A TO B.\nDISPLAY A.</code></pre></div>",
    )
    saved = qa_page.get(pid)
    assert 'data-lang="cobol"' not in saved
    assert "MOVE A TO B.\nDISPLAY A." in saved
    assert 'data-block="code"' in saved  # блок жив, деградировал в plain


# ---------------------------------------------------------------------------
# TC-rich-022 — script/onclick внутри блока вырезаются
# ---------------------------------------------------------------------------


def test_tc_rich_022_script_onclick_inside_block_removed(qa_page):
    """S22 (Must): <script> вырезан С СОДЕРЖИМЫМ, onclick снят, спойлер цел."""
    pid = qa_page.make("QA-22 xss в спойлере")
    qa_page.put(
        pid,
        '<div data-block="spoiler" data-title="X" onclick="alert(2)">'
        '<div data-block-part="body"><script>alert(1)</script>'
        "<p>тело</p></div></div>",
    )
    saved = qa_page.get(pid)
    assert "<script" not in saved and "alert(1)" not in saved
    assert "onclick" not in saved
    assert SPOILER.format(t="X", b="тело") == saved


# ---------------------------------------------------------------------------
# TC-rich-023 — подмена data-атрибутов: снятие, деградация в контент
# ---------------------------------------------------------------------------


def test_tc_rich_023_forged_data_attrs_stripped(qa_page):
    """S23 (Must): data-block="evil" и data-lang="javascript" сняты (_safe_block_attr),
    текст деградировал в обычный контент."""
    pid = qa_page.make("QA-23 подмена attrs")
    qa_page.put(pid, '<div data-block="evil" data-lang="javascript">текст</div>')
    saved = qa_page.get(pid)
    assert 'data-block="evil"' not in saved
    assert 'data-lang="javascript"' not in saved
    assert "текст" in saved


# ---------------------------------------------------------------------------
# TC-rich-024 — глубина: 5 работают, 6+ разворачиваются без потери
# ---------------------------------------------------------------------------


def _chain(n: int) -> str:
    """Цепочка из n спойлеров; у КАЖДОГО уровня свой текст в теле («Уi»)."""
    inner = ""
    for i in range(n, 0, -1):
        inner = SPOILER.format(t=f"У{i}", b=f"У{i}{inner}")
    return inner


def test_tc_rich_024_depth_limit_seven_vs_five(qa_page):
    """S24 (Must): цепочка 7 — уровней-блоков ровно 5, тексты У1..У7 целы;
    цепочка 5 (граница) — все 5 блоки."""
    pid = qa_page.make("QA-24 глубина 7")
    qa_page.put(pid, _chain(7))
    saved = qa_page.get(pid)
    assert saved.count('data-block="spoiler"') == 5
    for i in range(1, 8):
        assert f"У{i}" in saved, f"потерян текст уровня {i}"

    pid5 = qa_page.make("QA-24 глубина 5")
    qa_page.put(pid5, _chain(5))
    saved5 = qa_page.get(pid5)
    assert saved5.count('data-block="spoiler"') == 5
    assert saved5.count('data-block-part="body"') == 5


# ---------------------------------------------------------------------------
# TC-rich-025 — неизвестный блок: attr снят, контент цел
# ---------------------------------------------------------------------------


def test_tc_rich_025_unknown_block_degrades_content_kept(qa_page):
    """S25 (Should): data-block="future-widget" снят, «Будущее содержимое» цело,
    соседний спойлер не тронут."""
    pid = qa_page.make("QA-25 неизвестный блок")
    qa_page.put(
        pid,
        SPOILER.format(t="Рабочий", b="сосед")
        + '<div data-block="future-widget">Будущее содержимое</div>',
    )
    saved = qa_page.get(pid)
    assert 'data-block="future-widget"' not in saved
    assert "Будущее содержимое" in saved
    assert SPOILER.format(t="Рабочий", b="сосед") in saved


# ---------------------------------------------------------------------------
# TC-rich-034 — базовая санитизация: script/onerror до рендера
# ---------------------------------------------------------------------------


def test_tc_rich_034_script_onerror_removed(qa_page):
    """S34 (Must): script вырезан с содержимым, onerror снят, img остается."""
    pid = qa_page.make("QA-34 базовая санитизация")
    qa_page.put(
        pid,
        '<p>до</p><script>alert(1)</script>'
        '<img src="/static/img/logo.svg" onerror="alert(2)" alt="x"><p>после</p>',
    )
    saved = qa_page.get(pid)
    assert "<script" not in saved and "alert" not in saved
    assert "onerror" not in saved
    assert "до" in saved and "после" in saved


# ---------------------------------------------------------------------------
# TC-rich-035 — whitelist-теги проходят без искажений
# ---------------------------------------------------------------------------


def test_tc_rich_035_whitelist_roundtrip_identical(qa_page):
    """S35 (Must): разметка всего тулбара (H1-H3, B/I/U, списки, цитата,
    код, ссылка, таблица, img) — round-trip байт-в-байт."""
    pid = qa_page.make("QA-35 whitelist roundtrip")
    html = (
        "<h1>З1</h1><h2>З2</h2><h3>З3</h3>"
        "<p><b>ж</b><i>к</i><u>ч</u><code>x=1</code></p>"
        "<ol><li>н1</li><li>н2</li></ol>"
        "<ul><li>м1</li><li>м2</li></ul>"
        "<blockquote><p>цитата</p></blockquote>"
        "<p><a href=\"https://example.com/a?b=1\">ссылка</a></p>"
        "<table><thead><tr><th>H</th></tr></thead>"
        "<tbody><tr><td>D</td></tr></tbody></table>"
        '<p><img src="/static/img/logo.svg" alt="л"></p>'
    )
    pid = qa_page.make("QA-35 whitelist roundtrip")
    qa_page.put(pid, html)
    assert qa_page.get(pid) == html


# ---------------------------------------------------------------------------
# TC-rich-036 — валидные блоки проходят, подмена снимается (GET-часть)
# ---------------------------------------------------------------------------


def test_tc_rich_036_valid_blocks_pass_evil_stripped(qa_page):
    """S36 (Must): спойлер+код+табы сохранены как есть, data-block="evil" снят."""
    pid = qa_page.make("QA-36 блоки и подмена")
    qa_page.put(
        pid,
        SPOILER.format(t="Сп", b="тело спойлера")
        + '<div data-block="code" data-lang="python"><pre><code>print(1)'
        "</code></pre></div>"
        + '<div data-block="tabs"><div data-block-part="tab" data-title="В1">'
        "<p>первая</p></div></div>"
        + '<div data-block="evil">Подмена</div>',
    )
    saved = qa_page.get(pid)
    assert SPOILER.format(t="Сп", b="тело спойлера") in saved
    assert '<div data-block="code" data-lang="python"><pre><code>print(1)</code></pre></div>' in saved
    assert 'data-block="evil"' not in saved
    assert "Подмена" in saved


# ---------------------------------------------------------------------------
# TC-rich-038 — paste-путь: вложенный блок в код unwrap'нут
# ---------------------------------------------------------------------------


def test_tc_rich_038_paste_nested_spoiler_in_code_unwrapped(qa_page):
    """S38-paste (Must): spoiler внутри code — теги unwrap, текст сохранен
    как текст, внутри кода только pre/code; повторный PUT идемпотентен."""
    pid = qa_page.make("QA-38 paste в код")
    dirty = (
        '<div data-block="code" data-lang="python"><pre><code>x = 1</code></pre>'
        + SPOILER.format(t="Вл", b="секрет") + "</div>"
    )
    qa_page.put(pid, dirty)
    saved = qa_page.get(pid)
    assert saved.count("data-block") == 1  # только сам код
    assert 'data-block="code"' in saved and "<pre><code>x = 1</code></pre>" in saved
    assert "секрет" in saved  # текст вложенного блока сохранен
    assert "data-title" not in saved and "data-block-part" not in saved
    # идемпотентность
    qa_page.put(pid, saved)
    assert qa_page.get(pid) == saved


# ---------------------------------------------------------------------------
# TC-rich-041 — paste-путь: таблица в таблице unwrap целиком, текст с <br>
# ---------------------------------------------------------------------------


def test_tc_rich_041_paste_table_in_table_unwrapped(qa_page):
    """S41-paste (Must): вложенная table unwrap целиком, «A1» и «B1» в td
    с разделителем <br>; повторное сохранение идемпотентно (урок rich-v1)."""
    pid = qa_page.make("QA-41 paste таблица в таблице")
    dirty = (
        "<table><tbody><tr><td>"
        "<table><tbody><tr><td>A1</td><td>B1</td></tr></tbody></table>"
        "</td></tr></tbody></table>"
    )
    qa_page.put(pid, dirty)
    saved = qa_page.get(pid)
    assert saved == "<table><tbody><tr><td>A1<br>B1</td></tr></tbody></table>", saved
    # идемпотентность (повторный round-trip из редактора)
    qa_page.put(pid, saved)
    assert qa_page.get(pid) == saved
