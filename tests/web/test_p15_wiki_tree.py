"""Wiki-дерево + поиск на /wiki (tasks.md 3.1 add-wiki; FR-107, FR-114;
design §6–§7) — web-кейсы playwright по паттерну tests/web (стенд conftest:
uvicorn app + http.server static, tmp-БД + seed owner/wife).

TC-ID (реестр тест→кейс, 1 кейс = 1 тест):
  TC-wiki-001 → test_wiki_tree_three_levels_build_and_collapse (FR-107, дерево 3+ уровней, 3.1а)
  TC-wiki-002 → test_wiki_search_title_and_snippet_mark (FR-114, поиск заголовок/текст + mark, 3.1в)
  TC-wiki-003 → test_wiki_search_no_results (FR-114, пустой результат, 3.1в)
  TC-wiki-004 → test_wiki_empty_state_create_first_page (FR-107, пустое состояние, 3.1б)
  TC-wiki-005 → test_wiki_empty_state_button_opens_editor (FR-107, кнопка → редактор, 3.1б)
  TC-wiki-006 → test_wiki_toolbar_create_button_opens_editor (FR-107, тулбар → редактор, 3.1б)
  TC-wiki-007 → test_wiki_layout_desktop_280_and_mobile_one_column (NFR-33, раскладка, 3.1г)
Кейсы этапа C (QA) не утверждены (test-model/approved/add-wiki нет); ID
заведены по формату TC-wiki-NNN, привязка будет уточнена в QA-цикле 6.1.

Проверяется (мокап design/wiki-tree.html — эталон):
  1) дерево с вложенностью 3+ уровней строится из GET /api/wiki/pages
     (плоский список → вложенность по parent_id) и сворачивается
     (шеврон aria-expanded + hidden на поддереве);
  2) поиск: по заголовку и по тексту с <mark> (инверсная подсветка
     amber-700); пустой результат — «ничего не найдено»;
  3) пустое состояние — кнопка «Создать первую страницу»;
  4) раскладка 280px/контент, на 480px — одна колонка.

Страницы для кейсов создаются API (POST /api/wiki/pages) от owner-сессии
и удаляются в teardown (DELETE) — чистота стенда, как web_cleanup_created.
"""

import re

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


@pytest.fixture
def wiki_pages_created(web_base_url, web_owner_session, web_db_path):
    """Фабрика wiki-страниц с гарантированным удалением в teardown.

    Схему wiki (pages/page_versions) автостенд conftest не создает —
    накат app.migrate_wiki на tmp-БД стенда (идемпотентно, tasks.md:
    стенд = app.db + migrate_wiki + seed_user). Удаление — снизу вверх
    (FK RESTRICT на parent_id): сначала листья.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parents[2] / "backend"
    subprocess.run(
        [sys.executable, "-m", "app.migrate_wiki"],
        cwd=backend_dir,
        env={**os.environ, "DB_PATH": web_db_path, "SECRET_KEY": "web-tests-secret-key"},
        check=True,
        capture_output=True,
    )

    created: list[int] = []

    def _create(title: str, content: str = "", parent_id: int | None = None) -> int:
        resp = web_owner_session.post(
            f"{web_base_url}/api/wiki/pages",
            json={"title": title, "content": content, "parent_id": parent_id},
        )
        assert resp.status_code == 201, f"создание wiki-страницы: {resp.status_code} {resp.text}"
        page_id = resp.json()["id"]
        created.append(page_id)
        return page_id

    yield _create

    for page_id in reversed(created):
        try:
            web_owner_session.delete(f"{web_base_url}/api/wiki/pages/{page_id}")
        except Exception:
            pass


def _open_wiki(logged_in_page, web_base_url):
    """Открыть /wiki и дождаться рендера ДЕРЕВА (не пустого состояния).

    Внимание: страницы создает та же сессия-владелец, но вкладка
    logged_in_page могла открыть /wiki ДО создания страниц (fixture
    порядок) — перезагружаем, пока API не отдаст непустой список.
    """
    logged_in_page.goto(f"{web_base_url}/wiki")
    tree = logged_in_page.locator("ul.wiki-tree")
    for _ in range(10):
        if tree.count() > 0:
            break
        logged_in_page.reload()
    expect(tree).to_be_visible()
    return tree


# ---------------------------------------------------------------------
# 1. Дерево: вложенность 3+, раскрытие/сворачивание, ссылки
# ---------------------------------------------------------------------


def test_wiki_tree_three_levels_build_and_collapse(
    logged_in_page, web_base_url, wiki_pages_created
):
    """TC-wiki-001 (FR-107): дерево 3+ уровней строится и сворачивается.

    Корень → ребенок → внук; шеврон корня переключает aria-expanded и
    hidden поддерева; ссылки узлов ведут на /wiki/{id}.
    """
    root_id = wiki_pages_created("Корневой раздел", "тело корня")
    child_id = wiki_pages_created("Дочерний раздел", "тело ребенка", parent_id=root_id)
    grandchild_id = wiki_pages_created(
        "Внук: смета", "итоговая смета на материалы", parent_id=child_id
    )

    page = logged_in_page
    tree = _open_wiki(page, web_base_url)

    # 3 уровня: корень → ребенок → внук
    root_node = tree.locator("li.tree-node").filter(has_text="Корневой раздел").first
    child_node = root_node.locator("li.tree-node").filter(has_text="Дочерний раздел").first
    grandchild_link = child_node.locator("a.tree-link", has_text="Внук: смета")
    expect(grandchild_link).to_be_visible()

    # ссылки на /wiki/{id}
    expect(root_node.locator("a.tree-link").first).to_have_attribute(
        "href", f"/wiki/{root_id}"
    )
    expect(grandchild_link).to_have_attribute("href", f"/wiki/{grandchild_id}")

    # счетчик meta у корня: «N страниц · обновлено {дата}» (мокап, DV-3)
    root_meta = root_node.locator(".tree-meta").first
    meta_text = root_meta.inner_text()
    assert meta_text.startswith("2 страницы"), meta_text
    assert "· обновлено " in meta_text, meta_text

    # свернуть корень: aria-expanded=false, поддерево скрыто
    root_toggle = root_node.locator("> .tree-row .tree-toggle")
    expect(root_toggle).to_have_attribute("aria-expanded", "true")
    root_toggle.click()
    expect(root_toggle).to_have_attribute("aria-expanded", "false")
    root_children = root_node.locator("> ul.tree-children")
    expect(root_children).to_be_hidden()

    # развернуть обратно
    root_toggle.click()
    expect(root_toggle).to_have_attribute("aria-expanded", "true")
    expect(root_children).to_be_visible()

    # лист (внук): спейсер вместо шеврона
    grandchild_row = child_node.locator("li.tree-node").filter(has_text="Внук: смета").first
    expect(grandchild_row.locator(".tree-spacer")).to_have_count(1)
    expect(grandchild_row.locator(".tree-toggle")).to_have_count(0)


# ---------------------------------------------------------------------
# 2. Поиск: заголовок, текст с <mark>, пустой результат
# ---------------------------------------------------------------------


def test_wiki_search_title_and_snippet_mark(
    logged_in_page, web_base_url, wiki_pages_created
):
    """TC-wiki-002 (FR-114): поиск по заголовку и по тексту, <mark> по оффсету.

    Подсветка — DOM-разметка из match_offset/match_length: текст ответа
    вставляется textNode'ами, HTML из ответа не исполняется.
    """
    page = logged_in_page
    # сначала данные, потом открытие страницы: дерево рендерится при загрузке
    wiki_pages_created(
        "Кварцит: свойства породы",
        "Обзор: кварцит — прочная порода, применяемая в отделке.",
    )
    _open_wiki(page, web_base_url)

    search = page.locator("#wiki-search")
    search.fill("кварцит")

    results = page.locator("ul.wiki-results")
    expect(results).to_be_visible()
    expect(results.locator(".result-title").first).to_contain_text("Кварцит")

    # путь в иерархии (корень → пустая строка path) — сниппет с <mark>
    mark = results.locator(".result-snippet mark").first
    expect(mark).to_have_text("кварцит")

    # инверсная подсветка: фон amber-700 (решение дизайнера, review мокапов)
    bg = mark.evaluate("node => getComputedStyle(node).backgroundColor")
    assert bg == "rgb(138, 90, 30)", f"фон <mark>: {bg}"

    # совпадение по тексту (в контенте, не в заголовке)
    search.fill("отделке")
    expect(results.locator(".result-item").first).to_be_visible()
    expect(results.locator(".result-snippet mark").first).to_have_text("отделке")

    # счетчик найденного
    expect(page.locator(".filter-count")).to_have_text("Найдено: 1")


def test_wiki_search_no_results(logged_in_page, web_base_url, wiki_pages_created):
    """TC-wiki-003 (FR-114): пустой результат поиска — «ничего не найдено» (мокап)."""
    page = logged_in_page
    wiki_pages_created("Рецепт борща", "классический рецепт")
    _open_wiki(page, web_base_url)

    search = page.locator("#wiki-search")
    search.fill("qqqqничего")
    empty = page.locator("#wiki-search-results")
    expect(empty).to_contain_text("Ничего не найдено")
    expect(page.locator(".filter-count")).to_have_text("Найдено: 0")


# ---------------------------------------------------------------------
# 3. Пустое состояние
# ---------------------------------------------------------------------


def test_wiki_empty_state_create_first_page(logged_in_page, web_base_url):
    """TC-wiki-004 (FR-107): пустой список страниц — dashed-плашка + «Создать первую
    страницу» (мокап wiki-tree, демо-зона → продуктовое поведение).

    На чистом стенде (tmp-БД) wiki пуста — состояние видно сразу.
    """
    page = logged_in_page
    page.goto(f"{web_base_url}/wiki")

    empty = page.locator(".wiki-empty")
    expect(empty).to_be_visible()
    expect(empty.locator("h2")).to_have_text("В Wiki пока нет страниц")
    button = empty.get_by_role("button", name="Создать первую страницу")
    expect(button).to_be_visible()
    # дерева и выдачи при пустом списке нет
    expect(page.locator("ul.wiki-tree")).to_have_count(0)


def test_wiki_empty_state_button_opens_editor(
    logged_in_page, web_base_url
):
    """TC-wiki-005 (FR-107, F-1 review-004, спека 3.1б): клик «Создать первую страницу» →
    /wiki?create=1 → редактор 3.3 открыт (.editor-area видима).

    Паттерн _open_editor_create из test_p15_wiki_editor.py.
    """
    page = logged_in_page
    page.goto(f"{web_base_url}/wiki")

    empty = page.locator(".wiki-empty")
    expect(empty).to_be_visible()
    empty.get_by_role("button", name="Создать первую страницу").click()

    expect(page).to_have_url(re.compile(r"/wiki\?create=1$"))
    expect(page.locator(".editor-area")).to_be_visible()
    # долить фоновые /static-запросы страницы-редактора до teardown —
    # иначе гонка 'Route.fulfill: Fetch response has been disposed'
    # (обход из save-кейсов test_p15_wiki_editor.py, F-4 review-004)
    page.wait_for_load_state("networkidle")


def test_wiki_toolbar_create_button_opens_editor(
    logged_in_page, web_base_url, wiki_pages_created
):
    """TC-wiki-006 (FR-107, F-1 review-004): тулбарная «Создать страницу» — тот же
    переход в редактор (?create=1), .editor-area видима."""
    wiki_pages_created("Раздел для тулбара", "тело")
    page = logged_in_page
    _open_wiki(page, web_base_url)

    page.locator(".wiki-toolbar .wiki-create").click()

    expect(page).to_have_url(re.compile(r"/wiki\?create=1$"))
    expect(page.locator(".editor-area")).to_be_visible()
    # долить фоновые /static-запросы страницы-редактора до teardown —
    # иначе гонка 'Route.fulfill: Fetch response has been disposed'
    # (обход из save-кейсов test_p15_wiki_editor.py, F-4 review-004)
    page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------
# 4. Раскладка: 280px/контент, ≤480px — одна колонка
# ---------------------------------------------------------------------


def test_wiki_layout_desktop_280_and_mobile_one_column(
    logged_in_page, web_base_url, wiki_pages_created
):
    """TC-wiki-007 (NFR-33): grid 280px + контент до 1200px на десктопе;
    ≤480px — одна колонка (дерево в потоке сверху, order:-1).

    Значения — решение Заказчика decisions/2026-10-11-wiki-layout-tree-left.md:
    дерево слева 280px, .wiki-content max-1200px, поиск min(320px, 100%)
    (отклонение от мокапов 980px зафиксировано решением).
    """
    wiki_pages_created("Раздел раскладки", "тело")
    page = logged_in_page
    tree = _open_wiki(page, web_base_url)

    page.set_viewport_size({"width": 1280, "height": 800})
    columns = page.locator(".wiki-layout").evaluate(
        "node => getComputedStyle(node).gridTemplateColumns"
    )
    first_col = columns.split()[0]
    assert first_col == "280px", f"колонка дерева: {columns}"

    # контентная колонка расширена до 1200px (решение Заказчика, дерево слева)
    content_max = page.locator(".wiki-content").evaluate(
        "node => getComputedStyle(node).maxWidth"
    )
    assert content_max == "1200px", f"max-width контента: {content_max}"

    # инпут поиска — гибкий: min(320px, 100%), не выезжает за плитку тулбара
    search_width = page.locator(".wiki-search").evaluate(
        "node => getComputedStyle(node).width"
    )
    assert search_width == "320px", f"ширина поиска на 1280px: {search_width}"
    toolbar_box = page.locator(".wiki-toolbar").bounding_box()
    search_box = page.locator(".wiki-search").bounding_box()
    assert search_box["x"] >= toolbar_box["x"], "поиск левее плитки тулбара"
    assert search_box["x"] + search_box["width"] <= toolbar_box["x"] + toolbar_box["width"], (
        "инпут поиска выезжает за плитку тулбара"
    )

    page.set_viewport_size({"width": 480, "height": 800})
    columns = page.locator(".wiki-layout").evaluate(
        "node => getComputedStyle(node).gridTemplateColumns"
    )
    assert len(columns.split()) == 1, f"мобильная раскладка: {columns}"
    expect(tree).to_be_visible()
    # долить фоновые запросы страницы до teardown (Browser.close) — иначе
    # гонка 'Route.fulfill: Fetch response has been disposed' (см. F-4
    # review-004: известная pw-гонка disposeAPIResponse с невыполненным
    # fulfill; тот же обход, что в save-кейсах test_p15_wiki_editor.py)
    page.wait_for_load_state("networkidle")
