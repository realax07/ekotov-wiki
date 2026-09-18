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
def test_wiki_stub_with_todo_badge(base_url, owner_session):
    """TC-nav-004 (API-часть): раздел Wiki — заглушка с todo: страница /wiki —
    HTTP 200, текст-заглушка с упоминанием todo, wiki-статей нет. Пометка todo
    в сайдбаре — в разметке всех страниц. UI-часть — tests/web."""
    resp = owner_session.get(f"{base_url}/wiki")
    assert resp.status_code == 200
    assert "todo" in resp.text  # пометка todo/текст-заглушка
    assert "Раздел-заглушка" in resp.text
    # сайдбар: раздел Wiki с пометкой todo
    assert "todo-badge" in resp.text
    # содержимого wiki-статей нет
    assert 'class="wiki-article"' not in resp.text


@pytest.mark.must
def test_wiki_gives_no_wiki_functions(base_url, owner_session):
    """TC-nav-005 (API-часть): Wiki не дает wiki-функций: API-пути wiki
    отсутствуют — GET/POST /api/wiki не 2xx (ожидание кейса: отсутствие
    wiki-функций проверяется отсутствием 2xx-успеха; фактические коды
    зафиксировать — контракт wiki API в спеке не определен), не 5xx.
    UI-часть (отсутствие элементов) — tests/web."""
    resp_get = owner_session.get(f"{base_url}/api/wiki")
    resp_post = owner_session.post(
        f"{base_url}/api/wiki", json={"title": "QAT-Тест-wiki"}
    )
    for resp in (resp_get, resp_post):
        assert resp.status_code // 100 != 2, (
            f"wiki-функция не должна существовать: {resp.request.method} → {resp.status_code}"
        )
        assert resp.status_code < 500, (
            f"зафиксировано: {resp.request.method} /api/wiki → {resp.status_code}"
        )
