"""Регресс-тест обратной совместимости rich-редактора (change add-rich-editor,
tasks.md 1.7; design §1; NFR-36, NFR-38, FR-125).

- (а) Эталонные рендеры фиксированного набора существующих страниц сняты
  ДО волны 2 скриптом snapshot_reference.py (tests/api/fixtures/rich_compat/
  *.render.txt): plain text, HTML тулбара FR-110, изображение FR-111.
- (б) Рендер каждой страницы набора идентичен эталону: «рендер» rich-
  архитектуры = sanitize_rich(content) на записи (design §6: sanitize НА
  ЗАПИСИ + структурная безопасность рендера; GET отдает как сохранено).
- (в) Смешанный контент (legacy + один rich-блок): legacy-часть рендерится
  по-старому (passthrough sanitize_html, инвариант M-4).
- (г) Патологические страницы (ревью A-2): legacy-текст, похожий на диалект
  (``:::`` в начале строки, GFM-шапка, ```) — рендер идентичен эталону;
  re-save через API проходит БЕЗ 422 и без изменения контента
  (fallback-политика design §1).

Запуск (из корня репозитория, стенд поднят — tests/README.md):
  EKOTOV_WIKI_DB_PATH=... python3 -m pytest tests/api/test_render_compat.py -v
"""

import os
import sys
import uuid

import pytest
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(HERE, "..", "..", "backend")
sys.path.insert(0, BACKEND)

from app.rich_blocks import content_has_blocks, parse  # noqa: E402
from app.sanitize import sanitize_html  # noqa: E402
from app.sanitize_rich import sanitize  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "rich_compat")

# Legacy-кейсы набора (case7_mixed — отдельный тест смешанного контента)
LEGACY_CASES = [
    "case1_plain",
    "case2_toolbar_html",
    "case3_image",
    # патологические (ревью A-2): «legacy-текст, похожий на диалект»
    "case4_lookalike_colons",
    "case5_lookalike_gfm",
    "case6_lookalike_fence",
]


def _read(name: str, suffix: str) -> str:
    with open(os.path.join(FIXTURES, name + suffix), encoding="utf-8") as fh:
        return fh.read()


def _reference(name: str) -> str:
    return _read(name, ".render.txt")


# --------------------------------------------------------------------------
# (а)+(б) Рендер каждой страницы набора идентичен эталону (NFR-36)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", LEGACY_CASES)
def test_render_matches_pre_wave_reference(name):
    """Рендер (sanitize_rich на записи) идентичен эталону, снятому до
    внедрения rich-редактора."""
    content = _read(name, ".content.txt")
    assert sanitize(content) == _reference(name)


@pytest.mark.parametrize("name", LEGACY_CASES)
def test_legacy_render_path_unchanged_m4(name):
    """Инвариант M-4: legacy-рендер = существующий sanitize_html без правок;
    re-save старой страницы не меняет контент (NFR-38)."""
    content = _read(name, ".content.txt")
    assert sanitize(content) == sanitize_html(content)


@pytest.mark.parametrize("name", LEGACY_CASES)
def test_lookalike_re_save_content_unchanged(name):
    """Патологические страницы (1.7г): parse не превращает кандидатов в блоки
    и не теряет контент — serialize∘parse = идентичность (re-save safe)."""
    content = _read(name, ".content.txt")
    nodes = parse(content)
    assert not content_has_blocks(nodes)
    from app.rich_blocks import serialize

    assert serialize(nodes) == content


# --------------------------------------------------------------------------
# (в) Смешанный контент: legacy-часть — по-старому
# --------------------------------------------------------------------------


def test_mixed_content_legacy_part_rendered_as_before():
    content = _read("case7_mixed", ".content.txt")
    reference = _reference("case7_mixed")
    out = sanitize(content)
    assert out == reference
    # legacy-сегменты «Старый HTML …» прошли без изменения
    assert "Старый HTML перед блоком." in out
    assert "Старый HTML после блока." in out
    # rich-блок распознан и сохранен блоком
    blocks = [node for node in parse(out) if node["type"] != "text"]
    assert [node["type"] for node in blocks] == ["callout"]


# --------------------------------------------------------------------------
# (г) Re-save патологических страниц через API: 200, БЕЗ 422, контент цел
# --------------------------------------------------------------------------


def _create_page(base_url: str, session: requests.Session, content: str) -> int:
    resp = session.post(
        f"{base_url}/api/wiki/pages",
        json={"title": "QAT-rich-compat-" + uuid.uuid4().hex[:8], "content": content},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.parametrize("name", LEGACY_CASES)
def test_re_save_pathological_page_no_422_content_identical(name, base_url, owner_session):
    """Fallback-политика design §1 (ревью A-2): старую страницу с текстом,
    похожим на диалект, можно отредактировать и сохранить — 200, НЕ 422,
    контент сохранен без изменения."""
    content = _read(name, ".content.txt")
    page_id = _create_page(base_url, owner_session, content)
    try:
        # хранилище: контент прошел legacy-путь без изменения
        stored = owner_session.get(f"{base_url}/api/wiki/pages/{page_id}").json()
        assert stored["content"] == content
        # re-save (PUT правки)
        resp = owner_session.put(
            f"{base_url}/api/wiki/pages/{page_id}",
            json={"title": stored["title"], "content": content},
        )
        assert resp.status_code == 200, resp.text
        reread = owner_session.get(f"{base_url}/api/wiki/pages/{page_id}").json()
        assert reread["content"] == content  # без изменения контента
    finally:
        owner_session.delete(f"{base_url}/api/wiki/pages/{page_id}")


def test_re_save_valid_rich_page_200(base_url, owner_session):
    """Сохранение страницы с валидным диалектом — 200 (шов 1.3, позитив)."""
    content = (
        "Вступление.\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\n"
        ":::callout type=warn\nТекст\n:::"
    )
    page_id = _create_page(base_url, owner_session, content)
    try:
        resp = owner_session.put(
            f"{base_url}/api/wiki/pages/{page_id}",
            json={"title": "QAT-rich-valid", "content": content},
        )
        assert resp.status_code == 200
    finally:
        owner_session.delete(f"{base_url}/api/wiki/pages/{page_id}")
