"""Домен navigation: TC-nav-001…005 (CHK-77…81; approved/add-kanban-core/navigation-01.md).

Страницы (sdd §3.6): /login, /board, /search, /wiki. Сайдбар — base.html
(разделы «Доска», «Поиск», «Wiki» с пометкой todo). UI-часть (клики по
сайдбару, матрица переходов 3×3) — браузерная; здесь проверяются
серверные контракты страниц (доступность, редиректы, содержимое шаблонов).
"""

import pytest

pytestmark = [pytest.mark.api]


@pytest.mark.must
def test_board_page_available_authorized(base_url, owner_session):
    """TC-nav-001 (API-часть): страница доски доступна авторизованному:
    GET /board — 200 без редиректа, канбан-доска (три столбца) в разметке.
    UI-часть (переход через сайдбар из /search и /wiki) — tests/web."""
    resp = owner_session.get(f"{base_url}/board")
    assert resp.status_code == 200
    assert "column-todo" in resp.text
    assert "column-in_progress" in resp.text
    assert "column-done" in resp.text


@pytest.mark.must
def test_search_page_available_authorized(base_url, owner_session):
    """TC-nav-002 (API-часть): вкладка поиска доступна с доски-сессии:
    GET /search — 200, фильтр-конструктор и переключатель advanced в разметке.
    UI-часть (клик по сайдбару) — tests/web."""
    resp = owner_session.get(f"{base_url}/search")
    assert resp.status_code == 200
    assert 'id="search-builder-form"' in resp.text
    assert 'id="search-mode-advanced"' in resp.text


@pytest.mark.must
def test_sidebar_on_all_pages(base_url, owner_session):
    """TC-nav-003 (API-часть): сайдбар доступен со всех страниц функционала:
    на /board, /search, /wiki разметка сайдбара идентичного состава — разделы
    «Доска», «Поиск», «Wiki» со ссылками /board, /search, /wiki (все 9 ссылок
    ведут на существующие страницы — каждая отвечает 200 авторизованному).
    UI-часть (клики) — tests/web."""
    for page in ("/board", "/search", "/wiki"):
        resp = owner_session.get(f"{base_url}{page}")
        assert resp.status_code == 200, page
        for href in ("/board", "/search", "/wiki"):
            assert f'href="{href}"' in resp.text, f"{page}: нет ссылки {href}"


@pytest.mark.must
def test_wiki_page_scaffold_no_todo_stub(base_url, owner_session):
    """TC-nav-004 (API-часть), дельта navigation P15 (add-wiki): раздел Wiki —
    полноценный, заглушка снята: страница /wiki — HTTP 200, каркас содержит
    контейнеры wiki-layout/wiki-tree/wiki-content, текста заглушки
    «Раздел-заглушка» НЕТ (todo-badge сайдбара — base.html, вне зоны пакета,
    снимается волной 3/6.x). UI-часть — tests/web."""
    resp = owner_session.get(f"{base_url}/wiki")
    assert resp.status_code == 200
    # каркас: контейнеры волны 3 (tasks.md «Неразделимые зоны»)
    assert 'class="wiki-layout"' in resp.text
    assert 'class="wiki-tree"' in resp.text
    assert 'class="wiki-content"' in resp.text
    # обратный ассерт: прежняя заглушка снята (Won't FR-13 — дельта navigation).
    # todo-badge сайдбара (base.html) вне зоны пакета — снимается волной 3/6.x
    # (review-001: «base.html не тронут, бейдж todo — волна 3/6.x»), здесь НЕ проверяется.
    assert "Раздел-заглушка" not in resp.text


@pytest.mark.must
def test_wiki_api_exists(base_url, owner_session):
    """TC-nav-005 (API-часть), дельта navigation P15 (add-wiki): wiki-функции
    существуют — capability wiki (FR-108…FR-116): GET /api/wiki/pages под
    сессией — 2xx (список страниц для дерева), не 404 и не 5xx. UI-часть
    (создание/редактирование/поиск из раздела) — tests/web."""
    resp = owner_session.get(f"{base_url}/api/wiki/pages")
    assert resp.status_code == 200, (
        f"GET /api/wiki/pages → {resp.status_code}: wiki-API должен существовать "
        "(дельта navigation: Won't «функции отсутствуют» снят)"
    )
