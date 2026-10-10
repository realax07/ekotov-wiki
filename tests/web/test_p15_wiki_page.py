"""Страница статьи /wiki/{id}: breadcrumb + действия + удаление (tasks.md
3.2 add-wiki; FR-108, FR-109, FR-116; design §6–§7) — web-кейсы playwright
по паттерну tests/web (стенд conftest: uvicorn app + http.server static,
tmp-БД + seed owner/wife). Эталон — утвержденный мокап design/wiki-page.html.

TC-ID (реестр тест→кейс, 1 кейс = 1 тест):
  TC-wiki-101 → test_breadcrumb_four_levels_links_and_current (FR-109, breadcrumb 4 уровня, 3.2а)
  TC-wiki-102 → test_breadcrumb_root_single_item (FR-109, корень = 1 элемент, 3.2а)
  TC-wiki-103 → test_actions_visible_and_delete_gated_by_can_delete (FR-108/FR-116, действия + can_delete, 3.2б)
  TC-wiki-104 → test_delete_confirm_dialog_and_redirect (FR-116, удаление листа, 3.2б)
  TC-wiki-105 → test_delete_conflict_409_banner_page_stays (FR-116, 409 без удаления, 3.2б)
  TC-wiki-106 → test_missing_page_shows_not_found_in_content (FR-108, 404 в контенте, 3.2а)
Кейсы этапа C (QA) не утверждены (test-model/approved/add-wiki нет); ID
заведены по формату TC-wiki-NNN, привязка будет уточнена в QA-цикле 6.1.

Проверяется:
  1) breadcrumb 4 уровней: все элементы кликабельны (/wiki/{id}), текущая —
     без ссылки (aria-current="page", FR-109); корневая страница — 1 элемент;
  2) действия по мокапу: «Редактировать» → /wiki/{id}?edit=1 (редактор 3.3
     подхватит), «История» → /wiki/{id}/history; «Удалить» видна ТОЛЬКО при
     can_delete (лист) и скрыта у родителя;
  3) удаление листа: диалог подтверждения (мокап: «Удалить страницу?»,
     фокус на «Отмена», Esc — отмена) → DELETE → redirect /wiki;
  4) 409 (у страницы появились дочерние с момента рендера): баннер ошибки
     по мокапу (.error-banner, role=alert), страница остается;
  5) 404 от API → «Страница не найдена» в контентной области (#wiki-article).

Страницы создаются API (POST /api/wiki/pages) от owner-сессии и удаляются
в teardown (DELETE, снизу вверх — FK RESTRICT на parent_id).
"""

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


def _open_article(logged_in_page, web_base_url, page_id):
    """Открытая статья /wiki/{id}: шапка отрендерена (page.js отработал)."""
    logged_in_page.goto(f"{web_base_url}/wiki/{page_id}")
    head = logged_in_page.locator(".article-head")
    expect(head).to_be_visible()
    return head


# ---------------------------------------------------------------------
# 1. Breadcrumb: 4 уровня кликабельны, текущая — без ссылки
# ---------------------------------------------------------------------


def test_breadcrumb_four_levels_links_and_current(
    logged_in_page, web_base_url, wiki_pages_created
):
    """TC-wiki-101 (FR-109): breadcrumb из ответа API — все элементы кликабельны,
    текущая страница без ссылки (aria-current); корень — 1 элемент без
    ссылки. Разделитель «/» (мокап)."""
    level1 = wiki_pages_created("Быт: уровень 1", "тело L1")
    level2 = wiki_pages_created("Быт: уровень 2", "тело L2", parent_id=level1)
    level3 = wiki_pages_created("Быт: уровень 3", "тело L3", parent_id=level2)
    level4 = wiki_pages_created("Быт: уровень 4", "тело L4", parent_id=level3)

    page = logged_in_page
    _open_article(page, web_base_url, level4)

    crumbs = page.locator("nav.wiki-breadcrumb ol.breadcrumb > li")
    # 4 страницы + 3 разделителя «/» = 7 li
    expect(crumbs).to_have_count(7)

    links = page.locator("nav.wiki-breadcrumb ol.breadcrumb a")
    expect(links).to_have_count(3)  # все, кроме текущей

    expect(links.nth(0)).to_have_text("Быт: уровень 1")
    expect(links.nth(0)).to_have_attribute("href", f"/wiki/{level1}")
    expect(links.nth(1)).to_have_attribute("href", f"/wiki/{level2}")
    expect(links.nth(2)).to_have_attribute("href", f"/wiki/{level3}")

    # текущая — без ссылки, aria-current="page" (мокап)
    current = page.locator('nav.wiki-breadcrumb [aria-current="page"]')
    expect(current).to_have_text("Быт: уровень 4")
    expect(current.locator("a")).to_have_count(0)

    # разделители по мокапу
    seps = page.locator("nav.wiki-breadcrumb .crumb-sep")
    expect(seps).to_have_count(3)
    for i in range(3):
        expect(seps.nth(i)).to_have_text("/")

    # переход по ссылке-предку ведет на статью предка
    links.nth(1).click()
    expect(page.locator(".article-head h1")).to_have_text("Быт: уровень 2")
    expect(page).to_have_url(f"{web_base_url}/wiki/{level2}")


def test_breadcrumb_root_single_item(logged_in_page, web_base_url, wiki_pages_created):
    """TC-wiki-102 (FR-109): breadcrumb корневой страницы — 1 элемент, без ссылок
    (проверка tasks.md 3.2: «breadcrumb корневой — 1 элемент»)."""
    root_id = wiki_pages_created("Корень без предков", "тело корня")

    page = logged_in_page
    _open_article(page, web_base_url, root_id)

    links = page.locator("nav.wiki-breadcrumb ol.breadcrumb a")
    expect(links).to_have_count(0)
    current = page.locator('nav.wiki-breadcrumb [aria-current="page"]')
    expect(current).to_have_text("Корень без предков")


# ---------------------------------------------------------------------
# 2. Действия: видимы/скрыты по can_delete; навигация
# ---------------------------------------------------------------------


def test_actions_visible_and_delete_gated_by_can_delete(
    logged_in_page, web_base_url, wiki_pages_created
):
    """TC-wiki-103 (FR-108/FR-116): «Редактировать» → /wiki/{id}?edit=1 (3.3), «История» →
    /wiki/{id}/history (3.4); «Удалить» видна только при can_delete —
    у листа есть, у родителя скрыта (мокап: can_delete=true — лист)."""
    parent_id = wiki_pages_created("Родитель с ребенком", "тело родителя")
    leaf_id = wiki_pages_created("Лист для действий", "тело листа", parent_id=parent_id)

    page = logged_in_page

    # лист: все три действия
    _open_article(page, web_base_url, leaf_id)
    actions = page.locator(".article-actions")
    expect(actions.get_by_role("button", name="Редактировать")).to_be_visible()
    expect(actions.get_by_role("button", name="История")).to_be_visible()
    delete_leaf = actions.get_by_role("button", name="Удалить")
    expect(delete_leaf).to_be_visible()

    # «Редактировать» → /wiki/{id}?edit=1 (подхватит редактор 3.3)
    actions.get_by_role("button", name="Редактировать").click()
    expect(page).to_have_url(f"{web_base_url}/wiki/{leaf_id}?edit=1")

    # «История» → роут каркаса /wiki/{id}/history (history.js 3.4)
    _open_article(page, web_base_url, leaf_id)
    page.locator(".article-actions").get_by_role("button", name="История").click()
    expect(page).to_have_url(f"{web_base_url}/wiki/{leaf_id}/history")

    # родитель (есть дочерние → can_delete=false): «Удалить» скрыта
    _open_article(page, web_base_url, parent_id)
    actions = page.locator(".article-actions")
    expect(actions.get_by_role("button", name="Редактировать")).to_be_visible()
    expect(actions.get_by_role("button", name="История")).to_be_visible()
    expect(actions.get_by_role("button", name="Удалить")).to_be_hidden()


# ---------------------------------------------------------------------
# 3. Удаление: диалог подтверждения → DELETE → redirect /wiki
# ---------------------------------------------------------------------


def test_delete_confirm_dialog_and_redirect(
    logged_in_page, web_base_url, wiki_pages_created
):
    """TC-wiki-104 (FR-116): клик «Удалить» → диалог по мокапу («Удалить страницу?»,
    «Отмена»/«Удалить», фокус на «Отмена», Esc — отмена); подтверждение →
    DELETE → redirect /wiki; в дереве страница исчезла."""
    page = logged_in_page
    parent_id = wiki_pages_created("Удаляемый лист", "тело")

    head = _open_article(page, web_base_url, parent_id)
    title = head.locator("h1").inner_text()

    head.locator(".article-actions").get_by_role("button", name="Удалить").click()

    dialog = page.locator(".confirm[role='dialog']")
    expect(dialog).to_be_visible()
    expect(dialog.locator("h2")).to_have_text("Удалить страницу?")
    expect(dialog).to_contain_text(f"«{title}» будет удалена безвозвратно")

    # мокап: фокс в диалоге — на кнопке «Отмена»; danger-solid подтверждает
    expect(page.locator(".confirm-actions .btn-secondary")).to_be_focused()
    expect(
        page.locator(".confirm-actions .btn-danger-solid")
    ).to_have_text("Удалить")

    # Esc — отмена: диалог закрыт, страница на месте
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    expect(page.locator(".article-head h1")).to_have_text(title)

    # кнопка «Отмена» тоже закрывает без удаления
    head.locator(".article-actions").get_by_role("button", name="Удалить").click()
    page.locator(".confirm-actions .btn-secondary").click()
    expect(dialog).to_have_count(0)
    expect(page.locator(".article-head h1")).to_have_text(title)

    # подтверждение → DELETE → redirect /wiki
    head.locator(".article-actions").get_by_role("button", name="Удалить").click()
    page.locator(".confirm-actions .btn-danger-solid").click()
    expect(page).to_have_url(f"{web_base_url}/wiki")
    expect(page.locator(f"a.tree-link[href='/wiki/{parent_id}']")).to_have_count(0)


# ---------------------------------------------------------------------
# 4. 409: баннер ошибки, страница остается
# ---------------------------------------------------------------------


def test_delete_conflict_409_banner_page_stays(
    logged_in_page, web_base_url, wiki_pages_created
):
    """TC-wiki-105 (FR-116): у листа с момента рендера появились дочерние → DELETE 409 →
    баннер ошибки по мокапу (.error-banner, role=alert), страница остается
    на месте, удаления нет (FR-116, ОВ-2)."""
    parent_id = wiki_pages_created("Родитель 409", "тело родителя")
    page = logged_in_page
    head = _open_article(page, web_base_url, parent_id)
    title = head.locator("h1").inner_text()

    # дочерние появились ПОСЛЕ рендера страницы — can_delete протух
    wiki_pages_created("Новый ребенок", "тело ребенка", parent_id=parent_id)

    head.locator(".article-actions").get_by_role("button", name="Удалить").click()
    page.locator(".confirm-actions .btn-danger-solid").click()

    banner = page.locator("#wiki-delete-error")
    expect(banner).to_be_visible()
    expect(banner).to_have_attribute("role", "alert")
    expect(banner).to_contain_text("Страницу удалить нельзя")
    expect(banner).to_contain_text("есть дочерние страницы")

    # страница остается: шапка, контент, URL без изменений
    expect(page).to_have_url(f"{web_base_url}/wiki/{parent_id}")
    expect(page.locator(".article-head h1")).to_have_text(title)
    expect(page.locator("article.article")).to_be_visible()


# ---------------------------------------------------------------------
# 5. 404: «Страница не найдена» в контентной области
# ---------------------------------------------------------------------


def test_missing_page_shows_not_found_in_content(
    logged_in_page, web_base_url, wiki_pages_created, web_owner_session
):
    """TC-wiki-106 (FR-108): 404 от API (несуществующий id) → «Страница не найдена» в
    контентной области (#wiki-article), без шапки/действий; после удаления
    страницы через API та же картина."""
    ghost_id = wiki_pages_created("Одноразовая страница", "тело")
    # удаление через API от owner-сессии (куки playwright-request не несут
    # сессию — Secure-кука по http не отправляется, паттерн conftest)
    resp = web_owner_session.delete(f"{web_base_url}/api/wiki/pages/{ghost_id}")
    assert resp.ok, "предусловие: страница удалена через API"

    page = logged_in_page
    page.goto(f"{web_base_url}/wiki/{ghost_id}")

    not_found = page.locator("#wiki-article .wiki-notfound")
    expect(not_found).to_be_visible()
    expect(not_found.locator("h2")).to_have_text("Страница не найдена")
    # действий и breadcrumb у несуществующей страницы нет
    expect(page.locator(".article-head")).to_have_count(0)
    expect(page.locator("nav.wiki-breadcrumb ol")).to_have_count(0)

    # ссылка возврата в раздел
    not_found.get_by_text("Вернуться в Wiki").click()
    expect(page).to_have_url(f"{web_base_url}/wiki")
