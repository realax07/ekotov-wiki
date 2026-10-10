"""История версий + откат (change add-wiki, tasks.md 3.4; design §6–§7;
FR-112, FR-113) — СТРОГО по утвержденному мокапу design/wiki-history.html.

Набор web-desktop, ссьют истории: роут /wiki/{id}/history (3.4а) +
frontend/static/js/wiki/history.js (3.4б) + секция wiki.css (3.4в).

TC-ID (реестр тест→кейс, 1 кейс = 1 тест):
  TC-wiki-201 → test_history_page_requires_session (FR-112, редирект без сессии, 3.4а)
  TC-wiki-202 → test_history_list_newest_first_with_author_and_datetime (FR-112, список версий, 3.4а)
  TC-wiki-203 → test_current_pill_on_latest_no_revert_button (FR-113, «текущая» без отката, 3.4в)
  TC-wiki-204 → test_version_view_readonly (FR-112, read-only просмотр версии, 3.4б)
  TC-wiki-205 → test_revert_confirm_dialog_cancel (FR-113, диалог отката/отмена, 3.4в)
  TC-wiki-206 → test_revert_creates_new_version_updates_list (FR-113, откат = новая версия, 3.4в)
  TC-wiki-207 → test_history_layout_collapses_narrow (NFR-33, layout ≤880px, 3.4в)
Кейсы этапа C (QA) не утверждены (test-model/approved/add-wiki нет); ID
заведены по формату TC-wiki-NNN, привязка будет уточнена в QA-цикле 6.1.

Сценарии (по ТЗ задачи 3.4 [tests] + мокап):
- роут /wiki/{id}/history без сессии → редирект /login (middleware)  → test_history_page_requires_session;
- список версий от новых к старым (автор, дата-время; последовательность
  правок двух учеток)                                     → test_history_list_newest_first_with_author_and_datetime;
- пилюля «текущая» на последней версии, кнопки «Откатить» у нее НЕТ;
  у прочих — есть                                          → test_current_pill_on_latest_no_revert_button;
- просмотр версии read-only (клик «Смотреть» → плашка «только чтение»,
  контент версии, элементов правки нет)                    → test_version_view_readonly;
- диалог подтверждения отката с формулировкой мокапа («новая версия —
  история не переписывается»), Отмена/Esc закрывают без POST → test_revert_confirm_dialog_cancel;
- «Откатить» в диалоге → POST revert → success-баннер + в списке
  появляется НОВАЯ версия (наверху, «текущая»); проверка по API:
  версий +1, ранние не переписаны, контент новой = контент V1
  (откат к V1 при V1–V3 → V4 = контент V1, V1–V3 неизменны)  → test_revert_creates_new_version_updates_list;
- layout ≤880px складывается в одну колонку (мокап, media 880) → test_history_layout_collapses_narrow.

Подготовка данных — через API стенда от owner-сессии (web_owner_session);
правка второй учетки (wife) — в тесте авторов через ее сессию
(LocalhostSession, Secure-куки по http localhost — см. conftest).

Изоляция: все страницы, созданные _make_page_with_versions, регистрируются
в tracked-списке и удаляются в teardown (DELETE /api/wiki/pages, обратный
порядок) — паттерн F-2/wiki_api (test_p15_wiki_editor.py), иначе
session-tmp-БД грязнится и порядок файлов в прогоне ломает пустое
состояние tree-сьюта (DV-F1 review-004-wave3).
"""

import pytest
from playwright.sync_api import expect

from tests.web.conftest import WIFE_LOGIN, WIFE_PASSWORD

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


@pytest.fixture
def wiki_schema_ready(web_db_path):
    """Схема wiki (pages/page_versions) на tmp-БД автостенда: накат
    app.migrate_wiki (идемпотентно) — автостенд conftest поднимает только
    app.db + seed, wiki-DDL (design §1) в init_db не входит (паттерн
    test_p15_wiki_tree.py::wiki_pages_created)."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parents[2] / "backend"
    subprocess.run(
        [sys.executable, "-m", "app.migrate_wiki"],
        cwd=backend_dir,
        env={
            **os.environ,
            "DB_PATH": web_db_path,
            "SECRET_KEY": "web-tests-secret-key",
        },
        check=True,
        capture_output=True,
    )


# Tracked-список страниц, созданных _make_page_with_versions в рамках
# текущего теста (заполняет фикстура wiki_created_pages, None вне ее
# контекста) — teardown удаляет страницы через API, обратный порядок
# (DV-F1 review-004-wave3; паттерн F-2: wiki_api в test_p15_wiki_editor.py).
_created_pages_stack: list[int] | None = None


@pytest.fixture
def wiki_created_pages(web_owner_session, web_base_url):
    """Tracked cleanup созданных через API wiki-страниц (паттерн F-2,
    эталон wiki_api в test_p15_wiki_editor.py): _make_page_with_versions
    регистрирует каждый созданный id; teardown удаляет их обратным
    порядком через DELETE /api/wiki/pages/{id} от owner-сессии — FK/CASCADE
    сносит версии страниц. Без этого session-tmp-БД грязнится, и при
    прогоне history-сьюта ПЕРВЫМ tree-кейсы пустого состояния видят
    непустое дерево (DV-F1 review-004-wave3)."""
    global _created_pages_stack
    _created_pages_stack = []
    yield
    created, _created_pages_stack = _created_pages_stack, None
    for page_id in reversed(created):
        try:
            web_owner_session.delete(f"{web_base_url}/api/wiki/pages/{page_id}")
        except Exception:
            pass


@pytest.fixture
def wiki_ready(wiki_schema_ready, web_owner_session, wiki_created_pages):
    """Стенд с wiki-схемой + залогиненная owner-сессия (precondition всех
    кейсов, кроме проверки редиректа без сессии) + teardown-очистка
    созданных страниц (tracked cleanup, DV-F1)."""


def _make_page_with_versions(owner_session, base_url, versions, *, title):
    """Создание страницы + правок через API (каждое сохранение = версия,
    FR-112). versions — список контентов; первый — исходный контент.
    Возвращает id страницы (сессия уже залогинена владельцем).
    Страница регистрируется в tracked-списке фикстуры wiki_created_pages
    — teardown удаляет ее через API (DV-F1 review-004-wave3)."""
    if _created_pages_stack is None:
        raise RuntimeError(
            "_make_page_with_versions вне фикстуры wiki_created_pages: "
            "страница не попадет в teardown-очистку (см. DV-F1)"
        )
    resp = owner_session.post(
        f"{base_url}/api/wiki/pages",
        json={"title": title, "content": versions[0]},
    )
    assert resp.status_code == 201, resp.text
    page_id = resp.json()["id"]
    _created_pages_stack.append(page_id)
    for content in versions[1:]:
        resp = owner_session.put(
            f"{base_url}/api/wiki/pages/{page_id}", json={"content": content}
        )
        assert resp.status_code == 200, resp.text
    return page_id


def _versions_via_api(owner_session, base_url, page_id):
    resp = owner_session.get(f"{base_url}/api/wiki/pages/{page_id}/versions")
    assert resp.status_code == 200, resp.text
    return resp.json()["versions"]


def _history_page(logged_in_page, web_base_url, page_id):
    """Открытие /wiki/{id}/history и ожидание отрисовки списка (ul.versions
    появился — history.js отработал)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/wiki/{page_id}/history")
    expect(page.locator("#wiki-history h1")).to_have_text("История версий")
    expect(
        page.locator("#wiki-history .versions .version-item").first
    ).to_be_visible()
    return page


def test_history_page_requires_session(page, web_base_url):
    """TC-wiki-201 (FR-112): роут /wiki/{id}/history без сессии — редирект на /login
    (middleware, как у /wiki и /wiki/{id}; задача 3.4а)."""
    page.goto(f"{web_base_url}/wiki/1/history")
    page.wait_for_url("**/login")
    assert "/login" in page.url


def test_history_list_newest_first_with_author_and_datetime(
    logged_in_page, web_base_url, wiki_ready, web_owner_session
):
    """TC-wiki-202 (FR-112): список версий от НОВЫХ к старым; в каждой строке — автор и
    дата-время (мокап: «ekotov · 02.10.2026 14:32»). Последовательность
    правок двух учеток: owner → wife → owner; верхняя строка = последняя
    правка owner."""
    page = logged_in_page

    page_id = _make_page_with_versions(
        web_owner_session,
        web_base_url,
        ["<p>v1 owner</p>"],
        title="История: авторы",
    )
    # Правка wife — отдельная сессия (второй автор в истории).
    import requests

    from tests.web.conftest import LocalhostSession

    wife = LocalhostSession()
    try:
        resp = wife.post(
            f"{web_base_url}/api/auth/login",
            json={"login": WIFE_LOGIN, "password": WIFE_PASSWORD},
        )
        assert resp.status_code == 200, resp.text
        resp = wife.put(
            f"{web_base_url}/api/wiki/pages/{page_id}",
            json={"content": "<p>v2 wife</p>"},
        )
        assert resp.status_code == 200, resp.text
    finally:
        wife.close()

    resp = web_owner_session.put(
        f"{web_base_url}/api/wiki/pages/{page_id}",
        json={"content": "<p>v3 owner</p>"},
    )
    assert resp.status_code == 200

    _history_page(page, web_base_url, page_id)

    items = page.locator("#wiki-history .versions .version-item")

    # От новых к старым: номера V3/V2/V1 сверху вниз.
    expect(items.nth(0).locator(".version-num")).to_have_text("V3")
    expect(items.nth(1).locator(".version-num")).to_have_text("V2")
    expect(items.nth(2).locator(".version-num")).to_have_text("V1")

    # Авторы: верхняя — owner (последняя правка), вторая — wife.
    expect(items.nth(0).locator(".version-meta")).to_contain_text("owner")
    expect(items.nth(1).locator(".version-meta")).to_contain_text("wife")

    # Дата-время: формат дд.мм.гггг чч:мм в каждой строке (мокап).
    for i in range(3):
        meta = items.nth(i).locator(".version-meta").inner_text()
        assert "·" in meta
        date_part = meta.split("·")[1].strip()
        assert len(date_part) >= 16, meta  # «02.10.2026 14:32» минимум
        assert date_part[2] == "." and date_part[10] == " ", meta


def test_current_pill_on_latest_no_revert_button(
    logged_in_page, web_base_url, wiki_ready, web_owner_session
):
    """TC-wiki-203 (FR-113): пилюля «текущая» на первой (последней) версии; у нее НЕТ кнопки
    «Откатить»; у остальных — есть (мокап wiki-history)."""
    page_id = _make_page_with_versions(
        web_owner_session,
        web_base_url,
        ["<p>v1</p>", "<p>v2</p>"],
        title="История: пилюля",
    )
    page = _history_page(logged_in_page, web_base_url, page_id)

    items = page.locator("#wiki-history .versions .version-item")
    expect(items).to_have_count(2)

    # Пилюля только у первой.
    expect(items.nth(0).locator(".pill-current")).to_have_text("текущая")
    expect(items.nth(1).locator(".pill-current")).to_have_count(0)

    # «Откатить»: у первой нет, у второй есть.
    expect(items.nth(0).get_by_role("button", name="Откатить")).to_have_count(0)
    expect(items.nth(1).get_by_role("button", name="Откатить")).to_have_count(1)

    # «Смотреть» есть у обеих.
    expect(items.nth(0).get_by_role("button", name="Смотреть")).to_have_count(1)
    expect(items.nth(1).get_by_role("button", name="Смотреть")).to_have_count(1)


def test_version_view_readonly(
    logged_in_page, web_base_url, wiki_ready, web_owner_session
):
    """TC-wiki-204 (FR-112): клик «Смотреть» → read-only просмотр: плашка «только чтение»,
    контент выбранной версии (НЕ текущего), элементов правки нет."""
    page_id = _make_page_with_versions(
        web_owner_session,
        web_base_url,
        ["<h2>Версия один</h2><p>содержимое v1</p>", "<p>v2 новое</p>"],
        title="История: просмотр",
    )
    page = _history_page(logged_in_page, web_base_url, page_id)

    items = page.locator("#wiki-history .versions .version-item")

    # По умолчанию выбрана последняя (текущая) — правая панель показывает v2.
    view = page.locator("#wiki-history .version-view")
    expect(view).to_be_visible()
    expect(view.locator(".readonly-banner")).to_contain_text("только чтение")
    expect(view.locator(".version-body")).to_contain_text("v2 новое")

    # Клик «Смотреть» у V1 → контент версии v1.
    items.nth(1).get_by_role("button", name="Смотреть").click()
    expect(view.locator(".version-body")).to_contain_text("содержимое v1")
    expect(view.locator(".readonly-banner")).to_contain_text("V1")

    # Read-only: никаких кнопок правки/сохранения/редактора в правой панели.
    expect(view.get_by_role("button")).to_have_count(0)
    expect(view.locator("[contenteditable='true']")).to_have_count(0)
    expect(view.locator("textarea, input")).to_have_count(0)


def test_revert_confirm_dialog_cancel(
    logged_in_page, web_base_url, wiki_ready, web_owner_session
):
    """TC-wiki-205 (FR-113): «Откатить» → диалог подтверждения с формулировкой мокапа
    («новая версия — история не переписывается»); «Отмена»/Esc закрывают
    без POST (версии через API не меняются)."""
    page_id = _make_page_with_versions(
        web_owner_session,
        web_base_url,
        ["<p>v1 контент</p>", "<p>v2 контент</p>"],
        title="История: диалог",
    )
    before = _versions_via_api(web_owner_session, web_base_url, page_id)

    page = _history_page(logged_in_page, web_base_url, page_id)
    items = page.locator("#wiki-history .versions .version-item")

    items.nth(1).get_by_role("button", name="Откатить").click()
    dialog = page.locator(".confirm[role='dialog']")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Откатить к версии V1?")
    # Формулировка мокапа — дословно в диалоге.
    expect(dialog).to_contain_text("новая версия")
    expect(dialog).to_contain_text("история не переписывается")

    # Отмена — диалог закрыт, POST не было: версии через API те же.
    dialog.get_by_role("button", name="Отмена").click()
    expect(dialog).to_have_count(0)
    assert _versions_via_api(web_owner_session, web_base_url, page_id) == before

    # Повтор с Esc — тот же эффект.
    items.nth(1).get_by_role("button", name="Откатить").click()
    expect(dialog).to_be_visible()
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    assert _versions_via_api(web_owner_session, web_base_url, page_id) == before


def test_revert_creates_new_version_updates_list(
    logged_in_page, web_base_url, wiki_ready, web_owner_session
):
    """TC-wiki-206 (FR-113): откат: подтверждение → POST revert → success-баннер + обновление
    списка (сверху НОВАЯ версия «текущая»); проверка по API: количество
    версий +1, ранние не переписаны (те же id), контент новой версии =
    контент V1 (откат к V1 при V1–V2 → V3 = контент V1, FR-113)."""
    page_id = _make_page_with_versions(
        web_owner_session,
        web_base_url,
        ["<p>v1 особый контент</p>", "<p>v2 промежуточный</p>"],
        title="История: откат",
    )
    before = _versions_via_api(web_owner_session, web_base_url, page_id)
    assert len(before) == 2

    page = _history_page(logged_in_page, web_base_url, page_id)
    items = page.locator("#wiki-history .versions .version-item")

    # Откат к V1.
    items.nth(1).get_by_role("button", name="Откатить").click()
    dialog = page.locator(".confirm[role='dialog']")
    dialog.get_by_role("button", name="Откатить").click()

    # Success-баннер (мокап: «Откат выполнен: создана версия…»).
    banner = page.locator("#wiki-history-banner.success-banner")
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("Откат выполнен")

    # Список обновился: сверху НОВАЯ версия V3 = «текущая», без «Откатить».
    expect(items.nth(0).locator(".version-num")).to_have_text("V3")
    expect(items.nth(0).locator(".pill-current")).to_have_text("текущая")
    expect(items.nth(0).get_by_role("button", name="Откатить")).to_have_count(0)
    expect(items).to_have_count(3)

    # Правая панель — откаченный контент (V3 = содержимое V1).
    view = page.locator("#wiki-history .version-view")
    expect(view.locator(".version-body")).to_contain_text("v1 особый контент")

    # API-проверка: история не переписана — все прежние версии на месте
    # (после новой сверху), +1 новая сверху.
    after = _versions_via_api(web_owner_session, web_base_url, page_id)
    assert len(after) == 3
    before_ids = [v["id"] for v in before]
    after_ids = [v["id"] for v in after]
    assert sorted(after_ids[1:]) == sorted(before_ids), (
        "ранние версии обязаны остаться (история не переписывается)"
    )
    new_top = after[0]
    assert new_top["id"] not in before_ids

    # Контент новой версии = контент V1.
    resp = web_owner_session.get(
        f"{web_base_url}/api/wiki/pages/{page_id}/versions/{new_top['id']}"
    )
    assert resp.status_code == 200
    assert "v1 особый контент" in resp.json()["content"]


def test_history_layout_collapses_narrow(
    logged_in_page, web_base_url, wiki_ready, web_owner_session
):
    """TC-wiki-207 (NFR-33): ≤880px layout складывается в одну колонку; десктоп — две (мокап,
    media 880)."""
    page_id = _make_page_with_versions(
        web_owner_session,
        web_base_url,
        ["<p>v1</p>", "<p>v2</p>"],
        title="История: узкий",
    )
    page = _history_page(logged_in_page, web_base_url, page_id)

    layout = page.locator("#wiki-history .history-layout")
    expect(layout).to_be_visible()

    page.set_viewport_size({"width": 375, "height": 812})
    columns = layout.evaluate(
        "node => getComputedStyle(node).gridTemplateColumns.split(' ').length"
    )
    assert columns == 1, f"на 375px ожидалась одна колонка, got {columns}"

    page.set_viewport_size({"width": 1280, "height": 800})
    columns = layout.evaluate(
        "node => getComputedStyle(node).gridTemplateColumns.split(' ').length"
    )
    assert columns == 2, f"на 1280px ожидались две колонки, got {columns}"
