"""Домены set/nav/form/sel пакета add-r2-categories-settings (24 кейса).

set  — страница /settings и общность настроек: TC-set-001…006 (CHK-103…108).
nav  — раздел «Настройки» сайдбара: TC-nav-006…008 (CHK-109…111).
form — подсказки/крестик/визуал формы задачи: TC-form-001…011 (CHK-112…122).
sel  — селект-поля из фактических данных: TC-sel-001…004 (CHK-123…126).

Правила сьюта: 1 кейс = 1 тест, TC-ID в docstring, метка `# regression: keep`
на устойчивых проверках, селекторы/ожидания — дословно из кейсов,
автожидания Playwright (time.sleep = 0). Seed справочника «Дом/Работа/Личное»
— session-scope фикстура conftest (CHK-139/TC-env-001); QAT-категории тесты
создают сами и удаляют в teardown (impact §4.1).

Среда (решение по кейсам-исключениям): reduced-motion не тестируется
(@media prefers-reduced-motion — средовое поведение, кейс ТС-form-011 не
содержит этого шага; обязательный минимум Д-5 — заявленный transition/
animation оверлея/модалки) — проверяется наблюдаемым CSS-состоянием.
"""

import pytest
from playwright.sync_api import expect

from tests.web.conftest import SEED_CATEGORIES

pytestmark = [pytest.mark.web, pytest.mark.must]


# --- Общие помощники (setup/teardown категорий, form API-сессия) ---


def _create_category(http, base_url: str, name: str) -> int:
    """POST /api/categories → id (шаги кейсов; FR-21-precondition)."""
    resp = http.post(f"{base_url}/api/categories", json={"name": name})
    assert resp.status_code == 201, f"создание категории {name!r}: {resp.text}"
    return resp.json()["id"]


def _delete_category(http, base_url: str, category_id: int) -> int:
    """DELETE /api/categories/{id} — cleanup кейсов (CHK-140).

    Возвращает код ответа: 200 — удалена; 409 «category in use» —
    задача-носитель еще жива (кейсы form-домена удаляют задачу до
    категории, Д-1: удаление используемой блокируется)."""
    resp = http.delete(f"{base_url}/api/categories/{category_id}")
    return resp.status_code


def _categories_names(http, base_url: str) -> list[str]:
    """GET /api/categories → список имен (sdd r2 §3.1)."""
    resp = http.get(f"{base_url}/api/categories")
    assert resp.status_code == 200
    return [item["name"] for item in resp.json()["categories"]]


def _wait_options_at_least(page, selector: str, min_names: int) -> None:
    """Автожидание загрузки опций (select заполняется асинхронно):
    wait_for_function — количество непустых (value != "") опций >= min_names,
    таймаут 10 c, без sleep."""
    page.wait_for_function(
        """([sel, minNames]) => {
          const el = document.querySelector(sel);
          if (!el) return false;
          const named = Array.from(el.querySelectorAll('option'))
            .filter((o) => o.getAttribute('value')).length;
          return named >= minNames;
        }""",
        arg=[selector, min_names],
        timeout=10_000,
    )


def _open_category_select_options(page, min_names: int = 1) -> list[str]:
    """Опции select «Категория» формы задачи без пустой опции-плейсхолдера
    (пустое значение «—» = «категория не задана», Д-2, не элемент
    справочника). Опции загружаются асинхронно — ожидание >= min_names.
    На общей сессионной странице несколько select «Категория» быть не может
    (одна форма); locator.first — защита от множественного label-матча."""
    _wait_options_at_least(page, "#task-category", min_names)
    options = page.locator("#task-category option")
    return [
        options.nth(i).text_content().strip()
        for i in range(options.count())
        if options.nth(i).get_attribute("value")
    ]


def _open_filter_select_options(page, min_names: int = 1) -> list[str]:
    """Опции select «Категория» фильтра-конструктора без пустой опции
    («любая» = «фильтр не задан», не элемент справочника). Опции загружаются
    асинхронно — ожидание >= min_names."""
    _wait_options_at_least(page, "#search-category", min_names)
    options = page.locator("#search-category option")
    return [
        options.nth(i).text_content().strip()
        for i in range(options.count())
        if options.nth(i).get_attribute("value")
    ]


def _open_form(page):
    """Открытая форма создания задачи (шаг кейсов form/sel)."""
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    return page


def _route_static(page, web_server) -> None:
    """Маршрутизация /static/* страницы нового контекста на static-сервер
    стенда (роль nginx, design §8) — как в фикстуре page conftest."""
    static_url = web_server["static_url"]
    if not static_url:
        return

    def _to_static(route):
        new_url = static_url + route.request.url.partition("/static")[2]
        route.fulfill(response=route.fetch(url=new_url))

    page.route(f"{web_server['base_url']}/static/**", _to_static)


def _card_task_id(card) -> int:
    value = card.get_attribute("data-task-id")
    assert value is not None, "у карточки нет data-task-id"
    return int(value)


# ==========================================================================
# Домен set: страница настроек (TC-set-001…006)
# ==========================================================================


def test_settings_page_opens_direct_and_via_content(
    logged_in_page, web_base_url, web_owner_session
):
    """TC-set-001 (CHK-103): авторизованный пользователь открывает
    настройки — прямым GET /settings и через сайдбар; заголовок «Настройки»
    виден, справочник seed (Дом/Работа/Личное) отображается (sdd §3.3)."""
    page = logged_in_page

    # Шаг 1: прямой GET → 200, HTML страницы настроек.
    resp = web_owner_session.get(f"{web_base_url}/settings")
    assert resp.status_code == 200
    assert "Настройки" in resp.text

    # Шаг 2: UI — прямая навигация: заголовок и URL.
    page.goto(f"{web_base_url}/settings")
    expect(page.get_by_role("heading", name="Настройки")).to_be_visible()
    assert page.url == f"{web_base_url}/settings"

    # Шаг 3: блок управления справочником; список содержит seed.
    for name in SEED_CATEGORIES:
        expect(
            page.locator("#category-list").get_by_text(name, exact=True)
        ).to_be_visible()

    # Дополнительный путь «через сайдбар» (GIVEN/WHEN кейса).
    page.goto(f"{web_base_url}/board")
    page.get_by_role("link", name="Настройки").click()
    expect(page.get_by_role("heading", name="Настройки")).to_be_visible()
    assert page.url == f"{web_base_url}/settings"


def test_settings_unauthenticated_redirect_and_api_401(page, web_base_url):
    """TC-set-002 (CHK-104, негативный): без сессии /settings — редирект на
    /login (содержимого настроек нет); /api/categories и мутирующий PATCH —
    401 {\"error\": \"unauthorized\"} (NFR-7: exempt-список не расширяется)."""
    # Шаг 1: новый контекст БЕЗ куки session (page — чистый контекст теста).
    page.goto(f"{web_base_url}/settings")
    assert page.url.endswith("/login"), f"URL после перехода: {page.url}"
    expect(page.get_by_role("heading", name="Вход")).to_be_visible()

    # Шаг 2: контента настроек нет.
    expect(
        page.get_by_role("heading", name="Настройки", exact=True)
    ).to_have_count(0)

    # Шаг 3: GET /api/categories без кук → 401.
    import requests

    anon = requests.Session()
    try:
        resp_get = anon.get(f"{web_base_url}/api/categories")
        assert resp_get.status_code == 401
        assert resp_get.json() == {"error": "unauthorized"}

        # Шаг 4: representative-мутирующий метод (PATCH) без кук → 401.
        resp_patch = anon.patch(
            f"{web_base_url}/api/categories/999999",
            json={"name": "QAT-никогда"},
        )
        assert resp_patch.status_code == 401
        assert resp_patch.json() == {"error": "unauthorized"}
    finally:
        anon.close()


def test_settings_change_visible_to_second_user(
    logged_in_page, web_base_url, http, web_owner_session, web_server
):
    """TC-set-003 (CHK-105): категория, созданная owner, видна wife и в API,
    и на странице настроек — настройки общие (FR-24), нет пер-пользовательской
    изоляции."""
    # Шаг 1: вход wife (seed-пользователь, пароль conftest).
    wife = http
    resp_login = wife.post(
        f"{web_base_url}/api/auth/login",
        json={"login": "wife", "password": "QaWife_Pass_2!"},
    )
    assert resp_login.status_code == 200, resp_login.text

    # Шаг 2: owner создает категорию.
    category_id = _create_category(web_owner_session, web_base_url, "QAT-общ-work")

    try:
        # Шаг 3: wife видит категорию в API.
        resp_list = wife.get(f"{web_base_url}/api/categories")
        assert resp_list.status_code == 200
        assert "QAT-общ-work" in _categories_names(wife, web_base_url)

        # Шаг 4: wife видит категорию на странице настроек (UI, сессия wife
        # — отдельный контекст браузера с собственной куки-банкой).
        context2 = logged_in_page.context.browser.new_context()
        page2 = context2.new_page()
        _route_static(page2, web_server)
        try:
            page2.goto(f"{web_base_url}/login")
            page2.get_by_label("Логин").fill("wife")
            page2.get_by_label("Пароль").fill("QaWife_Pass_2!")
            page2.get_by_role("button", name="Войти").click()
            expect(
                page2.get_by_role("heading", name="Доска", exact=True)
            ).to_be_visible()
            page2.goto(f"{web_base_url}/settings")
            expect(
                page2.locator("#category-list").get_by_text(
                    "QAT-общ-work", exact=True
                )
            ).to_be_visible()
        finally:
            page2.close()
            context2.close()
    finally:
        # Шаг 5: cleanup (CHK-140).
        _delete_category(web_owner_session, web_base_url, category_id)


def test_settings_second_user_can_rename_and_delete(
    logged_in_page, web_base_url, http, web_owner_session
):
    """TC-set-004 (CHK-106): второй пользователь (wife, не владелец)
    переименовывает и удаляет категорию — 200 (не 403, ОГР-11 «права на
    настройки не проектируются»); изменения общесистемные (видны owner)."""
    # Шаг 1: owner создает категорию.
    category_id = _create_category(web_owner_session, web_base_url, "QAT-меняемая")

    # Шаг 1b: вход wife в отдельной сессии.
    wife = http
    resp_login = wife.post(
        f"{web_base_url}/api/auth/login",
        json={"login": "wife", "password": "QaWife_Pass_2!"},
    )
    assert resp_login.status_code == 200, resp_login.text

    try:
        # Шаг 2: wife переименовывает → 200.
        resp_patch = wife.patch(
            f"{web_base_url}/api/categories/{category_id}",
            json={"name": "QAT-переименованная"},
        )
        assert resp_patch.status_code == 200, resp_patch.text
        assert resp_patch.json()["name"] == "QAT-переименованная"

        # Шаг 3: owner (контроль) видит переименованную.
        assert "QAT-переименованная" in _categories_names(
            web_owner_session, web_base_url
        )
        assert "QAT-меняемая" not in _categories_names(
            web_owner_session, web_base_url
        )

        # Шаг 4: wife удаляет → 200.
        resp_delete = wife.delete(f"{web_base_url}/api/categories/{category_id}")
        assert resp_delete.status_code == 200

        # Шаг 5: owner (контроль) — категории больше нет.
        assert "QAT-переименованная" not in _categories_names(
            web_owner_session, web_base_url
        )
    finally:
        # Изоляция: если шаг 4 не дошел — удаляем owner-сессией.
        wife.cookies.clear()
        web_owner_session.delete(f"{web_base_url}/api/categories/{category_id}")


def test_settings_single_directory_no_per_user_lists(
    logged_in_page, web_base_url, http, web_owner_session, web_db_path, web_server
):
    """TC-set-005 (CHK-107, граничный): справочник един — wife видит тот же
    список (S_wife == S, включая Дом/Работа/Личное) в API, на /settings и в
    select формы задачи; отдельного «личного» списка нет (ОГР-7)."""
    page = logged_in_page

    # Шаг 1: owner — список S и его отображение на /settings.
    s_owner = _categories_names(web_owner_session, web_base_url)
    page.goto(f"{web_base_url}/settings")
    for name in s_owner:
        expect(
            page.locator("#category-list").get_by_text(name, exact=True)
        ).to_be_visible()

    # Шаг 2: вход wife (отдельная сессия/контекст куки).
    wife = http
    resp_login = wife.post(
        f"{web_base_url}/api/auth/login",
        json={"login": "wife", "password": "QaWife_Pass_2!"},
    )
    assert resp_login.status_code == 200, resp_login.text

    # Шаг 3: wife — API-список S_wife идентичен S.
    s_wife = _categories_names(wife, web_base_url)
    assert s_wife == s_owner

    # Шаг 4: wife (UI) — тот же список на /settings; select формы задачи
    # содержит S. Отдельный контекст браузера (чистые куки — сессия wife,
    # не owner-контекст logged_in_page).
    context2 = logged_in_page.context.browser.new_context()
    page2 = context2.new_page()
    _route_static(page2, web_server)
    try:
        page2.goto(f"{web_base_url}/login")
        page2.get_by_label("Логин").fill("wife")
        page2.get_by_label("Пароль").fill("QaWife_Pass_2!")
        page2.get_by_role("button", name="Войти").click()
        expect(
            page2.get_by_role("heading", name="Доска", exact=True)
        ).to_be_visible()

        page2.goto(f"{web_base_url}/settings")
        for name in s_owner:
            expect(
                page2.locator("#category-list").get_by_text(name, exact=True)
            ).to_be_visible()

        page2.goto(f"{web_base_url}/board")
        expect(page2.locator("#board")).to_have_attribute("data-loaded", "true")
        _open_form(page2)
        assert set(_open_category_select_options(page2, min_names=len(s_owner))) == set(s_owner)
        page2.get_by_role("button", name="Отмена").click()
    finally:
        page2.close()
        context2.close()

    # Шаг 5: контроль модели (обоснование, не ассерт кейса): таблица
    # categories без столбца user_id — PRAGMA table_info (в протокол).
    import sqlite3

    conn = sqlite3.connect(web_db_path)
    try:
        columns = [
            row[1]
            for row in conn.execute("PRAGMA table_info(categories)").fetchall()
        ]
    finally:
        conn.close()
    assert "user_id" not in columns, (
        f"categories содержит user_id — пер-пользовательские списки: {columns}"
    )


def test_settings_contains_only_category_management(logged_in_page, web_base_url):
    """TC-set-006 (CHK-108, негативный — проверка отсутствия): на /settings
    только создание/переименование/удаление категорий; профиля, смены
    пароля, справочника тегов нет (FR-25, Won't релиза)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/settings")

    # Шаг 2: функции категорий присутствуют (поле+кнопка создания,
    # действия у записей — проверка на seed-записи).
    expect(page.locator("#category-new-name")).to_be_visible()
    expect(page.locator("#category-create-submit")).to_be_visible()
    seed_item = page.locator("#category-list .category-item").filter(
        has_text=SEED_CATEGORIES[0]
    )
    expect(seed_item).to_be_visible()
    expect(
        seed_item.get_by_role("button", name="Переименовать")
    ).to_be_visible()
    expect(seed_item.get_by_role("button", name="Удалить")).to_be_visible()

    # Шаг 3: отсутствующие функции — и по доступному имени, и по тексту
    # страницы, to_have_count(0) каждое.
    for term in ("Профиль", "Сменить пароль", "Справочник тегов"):
        expect(page.get_by_text(term)).to_have_count(0)
        expect(page.get_by_role("button", name=term)).to_have_count(0)
    expect(page.get_by_text("Пароль", exact=True)).to_have_count(0)
    expect(page.get_by_text("Теги", exact=True)).to_have_count(0)

    # Шаг 4: инспекция HTML на строки password/profile/тег (допустимы
    # служебные совпадения; input[type=password] на /settings быть не должно).
    html = page.content().lower()
    assert 'type="password"' not in html, "на /settings есть поле пароля"
    for banned in ("profile", "справочник тегов"):
        assert banned not in html, f"на /settings найдено {banned!r}"


# ==========================================================================
# Домен nav: раздел «Настройки» сайдбара (TC-nav-006…008)
# ==========================================================================


def test_settings_link_position_bottom_left_near_logout(logged_in_page, web_base_url):
    """TC-nav-006 (CHK-109): «Настройки» присутствует в сайдбаре, внизу
    слева, рядом с кнопкой выхода (|Y_настройки − Y_выход| < высота +
    отступ; одна колонка X); ниже остальных пунктов навигации."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")

    # Шаг 2: ссылка «Настройки» видна (роль link — разметка base.html:
    # <a href="/settings" class="nav-item nav-item-settings">).
    link = page.get_by_role("link", name="Настройки")
    expect(link).to_be_visible()

    # Шаг 3: геометрия — близость к «Выйти» (одна колонка, соседство по Y).
    bb_link = link.bounding_box()
    bb_logout = page.get_by_role("button", name="Выйти").bounding_box()
    assert bb_link is not None and bb_logout is not None
    assert abs(bb_link["y"] - bb_logout["y"]) < bb_link["height"] + 32, (
        f"«Настройки» {bb_link} не рядом с «Выйти» {bb_logout}"
    )
    assert abs(bb_link["x"] - bb_logout["x"]) < bb_link["width"], (
        f"«Настройки» и «Выйти» в разных колонках: {bb_link} vs {bb_logout}"
    )

    # Шаг 4: ниже остальных пунктов навигации (Y нижней границы ≥ Y низа «Доска»).
    bb_board = page.get_by_role("link", name="Доска").bounding_box()
    assert bb_board is not None
    assert bb_link["y"] + bb_link["height"] >= bb_board["y"] + bb_board["height"], (
        f"«Настройки» ({bb_link}) выше «Доска» ({bb_board})"
    )


def test_settings_link_navigates_to_settings_page(logged_in_page, web_base_url):
    """TC-nav-007 (CHK-110): клик по «Настройки» в сайдбаре → URL /settings,
    заголовок «Настройки», список seed-категорий виден — переход на
    страницу настроек, не заглушку."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")

    # Шаг 2–3: клик → URL и заголовок.
    page.get_by_role("link", name="Настройки").click()
    assert page.url == f"{web_base_url}/settings"
    expect(page.get_by_role("heading", name="Настройки")).to_be_visible()

    # Шаг 4: блок управления справочником с seed-категориями.
    for name in SEED_CATEGORIES:
        expect(
            page.locator("#category-list").get_by_text(name, exact=True)
        ).to_be_visible()


def test_settings_link_available_from_all_pages(logged_in_page, web_base_url):
    """TC-nav-008 (CHK-111): «Настройки» видна на /board, /search, /settings;
    переход работает с доски и из поиска; на самой странице настроек раздел
    тоже присутствует (активная разметка .active — факт в протоколе)."""
    page = logged_in_page

    # Шаг 1: ссылка видна на всех трех страницах.
    for path in ("/board", "/search", "/settings"):
        page.goto(f"{web_base_url}{path}")
        expect(page.get_by_role("link", name="Настройки")).to_be_visible()

    # Шаг 2: с /board клик → /settings.
    page.goto(f"{web_base_url}/board")
    page.get_by_role("link", name="Настройки").click()
    assert page.url == f"{web_base_url}/settings"
    expect(page.get_by_role("heading", name="Настройки")).to_be_visible()

    # Шаг 3: с /search снова клик → /settings.
    page.goto(f"{web_base_url}/search")
    page.get_by_role("link", name="Настройки").click()
    assert page.url == f"{web_base_url}/settings"
    expect(page.get_by_role("heading", name="Настройки")).to_be_visible()

    # Шаг 4: на /settings раздел присутствует; фактическая разметка —
    # активная ссылка (класс active, base.html: active_page == 'settings').
    active = page.get_by_role("link", name="Настройки")
    expect(active).to_be_visible()
    assert "active" in (active.get_attribute("class") or ""), (
        "активная разметка ссылки «Настройки» на /settings отсутствует"
    )


# ==========================================================================
# Домен form: подсказки, крестик, визуал (TC-form-001…011)
# ==========================================================================


def test_task_form_tag_hints_show_known_values(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-form-001 (CHK-112): подсказки поля «Теги» формы содержат теги
    QAT-тег-home, QAT-тег-urgent и категорию QAT-кат-work (объединение,
    Д-3); набор совпадает с GET /api/suggestions — механизм един с поиском
    (sdd §3.2)."""
    page = logged_in_page

    # Шаг 1: категория в справочник (FR-21) + задача-носитель через API;
    # контроль GET /api/suggestions.
    category_id = _create_category(web_owner_session, web_base_url, "QAT-кат-work")
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": "QAT-носитель-хинтов",
            "category": "QAT-кат-work",
            "tags": ["QAT-тег-home", "QAT-тег-urgent"],
        },
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])

    try:
        resp = web_owner_session.get(f"{web_base_url}/api/suggestions")
        assert resp.status_code == 200
        api_values = set(resp.json()["suggestions"])
        assert {"QAT-тег-home", "QAT-тег-urgent", "QAT-кат-work"} <= api_values

        # Шаг 2: форма задачи; поле «Теги» — атрибут list (datalist) и его id.
        _open_form(page)
        tags_field = page.get_by_label("Теги (через запятую)")
        datalist_id = tags_field.get_attribute("list")
        assert datalist_id, "у поля «Теги» формы нет атрибута list"
        datalist = page.locator(f"#{datalist_id}")

        # Шаг 3: опции datalist (автожидание наполнения — по числу из API).
        # Пустая опция-плейсхолдер «—» (value="") в справочник не входит.
        options = datalist.locator("option")
        expect(options).to_have_count(len(api_values), timeout=10_000)
        hint_values = [
            options.nth(i).text_content().strip() for i in range(options.count())
        ]
        for value in ("QAT-тег-home", "QAT-тег-urgent", "QAT-кат-work"):
            assert value in hint_values, f"{value!r} нет в подсказках формы"

        # Шаг 4: набор совпадает с телом GET /api/suggestions (единый
        # механизм с поиском).
        assert set(hint_values) == api_values
    finally:
        # Шаг 5: cleanup — сначала задача-носитель (Д-1: иначе DELETE
        # категории — 409 «in use»), затем категория.
        resp = web_owner_session.get(
            f"{web_base_url}/api/search", params={"archived": "false"}
        )
        for t in resp.json().get("results", []):
            if t["title"] == "QAT-носитель-хинтов":
                web_owner_session.delete(f"{web_base_url}/api/tasks/{t['id']}")
        _delete_category(web_owner_session, web_base_url, category_id)

def test_task_form_tag_hints_set_semantics(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-form-002 (CHK-113, граничный): значение QAT-дубль, заведенное и
    тегом, и категорией, встречается в опциях datalist формы ровно 1 раз и
    ровно 1 раз в теле GET /api/suggestions (set/UNION, Д-3)."""
    page = logged_in_page

    # Шаги 1–2: категория в справочник + задача с пересечением.
    category_id = _create_category(web_owner_session, web_base_url, "QAT-дубль")
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": "QAT-носитель-дубля",
            "category": "QAT-дубль",
            "tags": ["QAT-дубль"],
        },
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])

    try:
        # Шаг 3: форма, опции datalist.
        _open_form(page)
        datalist = page.locator("#task-tag-hints")
        options = datalist.locator("option")

        resp = web_owner_session.get(f"{web_base_url}/api/suggestions")
        assert resp.status_code == 200
        api_values = resp.json()["suggestions"]
        expect(options).to_have_count(len(set(api_values)), timeout=10_000)

        # Шаг 4: подсчет вхождений — ровно 1 в опциях и 1 в теле API.
        option_texts = [
            options.nth(i).text_content().strip() for i in range(options.count())
        ]
        assert option_texts.count("QAT-дубль") == 1, (
            f"дубль в datalist формы: {option_texts.count('QAT-дубль')} раза"
        )
        assert api_values.count("QAT-дубль") == 1, (
            f"дубль в теле /api/suggestions: {api_values.count('QAT-дубль')} раза"
        )
    finally:
        # Шаг 5: cleanup — сначала задача-носителя (Д-1: 409 «in use»),
        # затем категория.
        resp = web_owner_session.get(
            f"{web_base_url}/api/search", params={"archived": "false"}
        )
        for t in resp.json().get("results", []):
            if t["title"] == "QAT-носитель-дубля":
                web_owner_session.delete(f"{web_base_url}/api/tasks/{t['id']}")
        _delete_category(web_owner_session, web_base_url, category_id)


def test_task_form_pick_existing_hint_value(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-form-003 (CHK-114): выбор QAT-выбор из подсказок формы (клавиатура
    стрелка вниз + Enter) → значение сохраняется как тег создаваемой задачи
    (FR-26; проверка через GET /api/search?archived=false)."""
    page = logged_in_page

    # Шаг 1: задача-источник с тегом QAT-выбор.
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-источник-хинта", "tags": ["QAT-выбор"]},
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])

    # Шаги 2–3: форма → ввод значения → выбор из подсказки (клавиатура:
    # ArrowDown + Enter — фактический механизм datalist) → сохранить.
    _open_form(page)
    tags_field = page.get_by_label("Теги (через запятую)")
    tags_field.fill("QAT-выбор")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    assert "QAT-выбор" in tags_field.input_value(), (
        "выбор из подсказки не подставил значение в поле"
    )
    page.get_by_label("Название").fill("QAT-задача-с-выбором")
    page.get_by_role("button", name="Создать", exact=True).click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()

    created_id = None
    try:
        # Шаг 4: задача найдена, tags содержит QAT-выбор.
        resp = web_owner_session.get(
            f"{web_base_url}/api/search",
            params={"archived": "false"},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        matched = [t for t in results if t["title"] == "QAT-задача-с-выбором"]
        assert len(matched) == 1, f"задача не найдена: {len(matched)}"
        created_id = matched[0]["id"]
        assert "QAT-выбор" in matched[0]["tags"], matched[0]["tags"]
    finally:
        # Шаг 5: cleanup обеих задач.
        if created_id is not None:
            web_owner_session.delete(f"{web_base_url}/api/tasks/{created_id}")


def test_task_form_new_tag_value_allowed(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-form-004 (CHK-115): новое значение QAT-newtag в поле «Теги» формы
    принято (свободный ввод легитимен, в отличие от поиска FR-17); задача
    сохранена с этим тегом."""
    page = logged_in_page

    # Шаг 1: контроль — QAT-newtag отсутствует в подсказках.
    resp = web_owner_session.get(f"{web_base_url}/api/suggestions")
    assert resp.status_code == 200
    assert "QAT-newtag" not in resp.json()["suggestions"]

    # Шаг 2: форма — ввод QAT-newtag без выбора из подсказок → сохранить;
    # форма закрывается без ошибки ввода.
    _open_form(page)
    page.get_by_label("Название").fill("QAT-новый-тег")
    page.get_by_label("Теги (через запятую)").fill("QAT-newtag")
    page.get_by_role("button", name="Создать", exact=True).click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    expect(page.locator("#task-form-error")).to_be_hidden()

    created_id = None
    try:
        # Шаг 3: задача создана с тегом QAT-newtag.
        resp = web_owner_session.get(
            f"{web_base_url}/api/search", params={"archived": "false"}
        )
        assert resp.status_code == 200
        matched = [
            t for t in resp.json()["results"] if t["title"] == "QAT-новый-тег"
        ]
        assert len(matched) == 1, f"задача не найдена: {len(matched)}"
        created_id = matched[0]["id"]
        assert "QAT-newtag" in matched[0]["tags"], matched[0]["tags"]
    finally:
        # Шаг 4: cleanup.
        if created_id is not None:
            web_owner_session.delete(f"{web_base_url}/api/tasks/{created_id}")


def test_task_form_suggestions_require_auth(web_base_url):
    """TC-form-005 (CHK-116, негативный): GET /api/suggestions без сессии →
    401 {\"error\": \"unauthorized\"}, списка значений в теле нет (sdd §3.2,
    NFR-7)."""
    import requests

    anon = requests.Session()
    try:
        resp = anon.get(f"{web_base_url}/api/suggestions")
        assert resp.status_code == 401
        assert resp.json() == {"error": "unauthorized"}
        assert "suggestions" not in resp.json()
    finally:
        anon.close()


def test_task_form_close_button_top_right(logged_in_page, web_base_url):
    """TC-form-006 (CHK-117): крестик закрытия формы виден; позиция —
    правый верхний угол модалки (зазоры до краев < ~48px; фактические
    значения — в комментарии/выводе теста)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")

    # Шаг 1: открыть форму.
    _open_form(page)

    # Шаг 2: крестик — кнопка #task-form-close (aria-label «Закрыть форму
    # без сохранения», текстового «×» нет — текст в svg path; локатор
    # зафиксирован как семантический якорь кейса).
    overlay = page.locator("#task-form-overlay")
    close = overlay.get_by_role("button", name="Закрыть форму без сохранения")
    expect(close).to_be_visible()

    # Шаги 3–4: геометрия — правый верхний угор ОКНА ФОРМЫ (модалки
    # .modal; bbox оверлея — весь вьюпорт, .modal-overlay fixed inset:0,
    # поэтому зазоры считаются от формы): right = зазор до правого края
    # модалки, top = отступ от верха модалки; порог кейса ~48px.
    bb_close = close.bounding_box()
    bb_modal = page.locator("#task-form-overlay .modal").bounding_box()
    assert bb_close is not None and bb_modal is not None
    right_gap = (bb_modal["x"] + bb_modal["width"]) - (
        bb_close["x"] + bb_close["width"]
    )
    top_gap = bb_close["y"] - bb_modal["y"]
    print(
        f"[TC-form-006] зазоры крестика: right={right_gap:.0f}px, "
        f"top={top_gap:.0f}px"
    )
    assert 0 <= right_gap < 48, f"крестик не у правого края: {right_gap:.0f}px"
    assert 0 <= top_gap < 48, f"крестик не у верхнего края: {top_gap:.0f}px"


def test_task_form_close_discards_input(
    logged_in_page, web_base_url, web_owner_session
):
    """TC-form-007 (CHK-118): крестик закрывает окно без сохранения — POST
    /api/tasks не уходил, задача QAT-крестик-не-создана не создана."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")

    # Шаг 1: сетевой журнал POST /api/tasks.
    posts: list[str] = []
    page.on(
        "request",
        lambda r: posts.append(r.url)
        if "/api/tasks" in r.url and r.method == "POST"
        else None,
    )

    # Шаг 2: форма с заполненными полями.
    _open_form(page)
    page.get_by_label("Название").fill("QAT-крестик-не-создана")
    page.get_by_label("Описание").fill("заполнено до закрытия")

    # Шаг 3–4: крестик → окно скрыто.
    page.locator("#task-form-overlay").get_by_role(
        "button", name="Закрыть форму без сохранения"
    ).click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()

    # Шаг 5: POST не уходил; задача не создана (GET /api/search).
    assert posts == [], f"POST /api/tasks ушел: {posts}"
    resp = web_owner_session.get(
        f"{web_base_url}/api/search", params={"archived": "false"}
    )
    assert resp.status_code == 200
    created = [
        t for t in resp.json()["results"] if t["title"] == "QAT-крестик-не-создана"
    ]
    assert len(created) == 0, f"задача создана вопреки кейсу: {created}"


def test_task_form_priorities_distinguished_color_and_icon(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-form-008 (CHK-119): приоритеты low/medium/high различимы и цветом
    (computed style бейджей попарно различен), и иконкой (svg у каждого
    бейджа); в форме выбор приоритета сопровождается цветом пилюли
    (.priority-field-pill :has(:checked)) и текстом опций «Низкий/Средний/
    Высокий» (CHK-144: фактическая реализация в протоколе)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")

    # Шаг 1: три задачи с разными приоритетами.
    ids = []
    for title, priority in (
        ("QAT-приор-low", "low"),
        ("QAT-приор-med", "medium"),
        ("QAT-приор-high", "high"),
    ):
        resp = web_owner_session.post(
            f"{web_base_url}/api/tasks",
            json={"title": title, "priority": priority},
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])
    for task_id in ids:
        web_cleanup_created(task_id)

    # Шаг 2: карточки — svg-иконка в бейдже + computed style (задачи созданы
    # через API — доску перечитываем перезагрузкой страницы).
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    styles = {}
    for title in ("QAT-приор-low", "QAT-приор-med", "QAT-приор-high"):
        card = page.get_by_role("article").filter(has_text=title)
        expect(card).to_be_visible()
        badge = card.locator(".task-priority-badge")
        expect(badge).to_be_visible()
        assert badge.locator("svg").count() == 1, (
            f"у бейджа {title!r} нет svg-иконки"
        )
        styles[title] = badge.evaluate(
            "el => getComputedStyle(el).backgroundColor + ' / ' + getComputedStyle(el).color"
        )
        # Текст бейджа — локализованная подпись (FR-29, различимость без цвета).
        labels = ("Низкий", "Средний", "Высокий")
        assert any(label in badge.inner_text() for label in labels), (
            f"бейдж {title!r} без текстовой подписи: {badge.inner_text()!r}"
        )

    # Шаг 3: стили попарно различны (цвет различает приоритеты).
    pairs = [
        ("QAT-приор-low", "QAT-приор-med"),
        ("QAT-приор-low", "QAT-приор-high"),
        ("QAT-приор-med", "QAT-приор-high"),
    ]
    for a, b in pairs:
        assert styles[a] != styles[b], f"стили {a!r} и {b!r} совпадают"

    # Шаг 4: форма — select «Приоритет» (нативный select, контракт
    # task-form.js 4.5/e2e); иконку внутри нативного select реализация не
    # отрисовывает — различимость в форме дают цвет пилюли + текст опций.
    _open_form(page)
    pill = page.locator(".priority-field-pill")
    select = page.get_by_label("Приоритет")
    for value, label in (("low", "Низкий"), ("medium", "Средний"), ("high", "Высокий")):
        select.select_option(value)
        expect(page.locator("#task-form-overlay .priority-field-pill")).to_be_visible()
    # Цвет пилюли следует выбранному значению (computed style меняется).
    select.select_option("low")
    style_low = pill.evaluate("el => getComputedStyle(el).backgroundColor")
    select.select_option("high")
    style_high = pill.evaluate("el => getComputedStyle(el).backgroundColor")
    assert style_low != style_high, (
        f"цвет пилюли формы не меняется: {style_low!r} vs {style_high!r}"
    )
    # Скриншот формы (шаг 5 — приложить к протоколу).
    page.screenshot(path="tests/web/artifacts/tc-form-008-form.png")
    page.get_by_role("button", name="Отмена").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()

    # Шаг 5: скриншоты трех карточек — в артефакты прогонов.
    for title in ("QAT-приор-low", "QAT-приор-med", "QAT-приор-high"):
        card = page.get_by_role("article").filter(has_text=title)
        expect(card).to_be_visible()
    page.screenshot(path="tests/web/artifacts/tc-form-008-cards.png")


def test_task_form_priority_icons_inline_svg_no_external(
    logged_in_page, web_base_url
):
    """TC-form-009 (CHK-120, НФТ): иконки приоритетов — inline <svg> в HTML;
    внешние ресурсы (иконки/шрифты/CDN) не подключаются — external == []
    (ОГР-8)."""
    page = logged_in_page

    # Шаг 1: сетевой журнал внешних запросов; открыть /board.
    external: list[str] = []
    page.on(
        "request",
        lambda r: external.append(r.url)
        if not r.url.startswith((web_base_url, "data:"))
        else None,
    )
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # Шаг 2: открыть форму — все ресурсы загрузились.
    _open_form(page)

    # Шаг 3: иконки приоритетов — инлайновые <svg> (в разметке формы
    # и в JS-шаблоне карточек; на доске — svg внутри бейджей, см. TC-form-008).
    assert page.locator("#task-form-overlay svg").count() >= 1, (
        "в форме нет inline svg (крестик — svg, priority-icons.js)"
    )

    # Шаг 4: внешних хостов нет; иконочные CDN отсутствуют.
    cdn_markers = ("googleapis", "fontawesome", "jsdelivr", "unpkg", "cdnjs")
    for url in external:
        assert not any(marker in url for marker in cdn_markers), (
            f"внешний иконочный/шрифтовой CDN: {url}"
        )
    assert external == [], f"внешние ресурсы: {external}"

    page.get_by_role("button", name="Отмена").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()


def test_task_form_invalid_category_highlighted(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-form-010 (CHK-121, негативный): категория удалена из справочника
    ПОСЛЕ выбора в открытой форме → сохранение отклоняется 422 details.
    category («not in categories»), поле подсвечено (aria-invalid/класс +
    сообщение), задача не создана (FR-21/FR-29)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")

    # Шаг 1: категория → форма → выбор QAT-Врем-подсветка в select.
    category_id = _create_category(
        web_owner_session, web_base_url, "QAT-Врем-подсветка"
    )
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    _open_form(page)
    page.get_by_label("Категория").select_option("QAT-Врем-подсветка")
    page.get_by_label("Название").fill("QAT-подсветка-422")

    # Шаг 2: удалить категорию через API при открытой форме.
    _delete_category(web_owner_session, web_base_url, category_id)

    # Шаг 3: «Создать» → 422 details.category; форма осталась открыта.
    page.get_by_role("button", name="Создать", exact=True).click()
    expect(page.locator("#task-form-overlay")).to_be_visible()

    # Шаг 4: поле категории подсвечено: класс field-invalid +
    # aria-invalid=true + сообщение об ошибке (#task-category-error).
    category_select = page.get_by_label("Категория")
    state = category_select.evaluate(
        "el => el.className + '|' + el.getAttribute('aria-invalid')"
    )
    assert "field-invalid" in state and "true" in state, (
        f"поле категории не подсвечено: {state!r}"
    )
    error = page.locator("#task-category-error")
    expect(error).to_be_visible()
    assert error.inner_text().strip(), "сообщение об ошибке категории пустое"

    # Шаг 5: задача не создана.
    resp = web_owner_session.get(
        f"{web_base_url}/api/search", params={"archived": "false"}
    )
    assert resp.status_code == 200
    created = [
        t for t in resp.json()["results"] if t["title"] == "QAT-подсветка-422"
    ]
    assert len(created) == 0, f"задача создана вопреки 422: {created}"

    # Cleanup: закрыть форму (задача не создавалась — удалять нечего).
    page.get_by_role("button", name="Отмена").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()


def test_task_form_open_close_animation(logged_in_page, web_base_url):
    """TC-form-011 (CHK-122): у оверлея/модалки заявлен непустой
    transition/animation (минимальный порог — длительность > 0; конкретный
    стиль — Д-5, на усмотрение реализации); механизм открытия и закрытия
    единый (модалка .modal, animation modal-in)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")

    # Шаг 1: computed style скрытого оверлея (transition | animation).
    overlay = page.locator("#task-form-overlay")
    style_hidden = overlay.evaluate(
        "el => getComputedStyle(el).transition + ' | ' + getComputedStyle(el).animation"
    )
    print(f"[TC-form-011] скрытый оверлей: {style_hidden!r}")

    # Шаг 2: открыть форму — у видимой модалки заявлена анимация
    # (непустые значения, не «all 0s»/«none»).
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    modal = page.locator("#task-form-overlay .modal")
    anim_name = modal.evaluate("el => getComputedStyle(el).animationName")
    anim_duration = modal.evaluate("el => getComputedStyle(el).animationDuration")
    print(
        f"[TC-form-011] модалка: animationName={anim_name!r}, "
        f"duration={anim_duration!r}"
    )
    assert anim_name not in ("", "none"), "анимация модалки не заявлена"
    duration_s = float(str(anim_duration).rstrip("s") or 0)
    assert duration_s > 0, f"длительность анимации = 0: {anim_duration!r}"

    # Шаг 3: наблюдаемость промежуточного состояния (скриншот ~100 мс
    # после клика — промежуточный кадр открытия; фактический кадр
    # прикладывается к протоколу, артефакты вне git).
    page.get_by_role("button", name="Отмена").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    page.get_by_role("button", name="Создать задачу").click()
    page.wait_for_timeout(100)
    page.screenshot(path="tests/web/artifacts/tc-form-011-open-mid.png")
    expect(page.locator("#task-form-overlay")).to_be_visible()

    # Шаг 4: закрытие («Отмена») — тот же механизм модалки; скриншот
    # промежуточного кадра закрытия.
    page.get_by_role("button", name="Отмена").click()
    page.wait_for_timeout(40)
    page.screenshot(path="tests/web/artifacts/tc-form-011-close-mid.png")
    expect(page.locator("#task-form-overlay")).to_be_hidden()


# ==========================================================================
# Домен sel: селект-поля из фактических данных (TC-sel-001…004)
# ==========================================================================


def test_task_form_category_select_from_directory(
    logged_in_page, web_base_url, web_owner_session
):
    """TC-sel-001 (CHK-123): select «Категория» формы содержит ровно
    фактический справочник (Дом/Работа/Личное + QAT-sel-finance) — источник
    GET /api/categories, не статический список (DEF-001/FR-30)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # Шаг 1: заведомо известная 4-я категория.
    category_id = _create_category(
        web_owner_session, web_base_url, "QAT-sel-finance"
    )

    try:
        # Шаг 2: фактический справочник S (seed + заведенная категория;
        # справочник общий на сессию — категории других тестов удаляются их
        # teardown'ом, поэтому проверяется подмножество, а состав select
        # сверяется с фактическим S целиком ниже).
        names = _categories_names(web_owner_session, web_base_url)
        assert set(SEED_CATEGORIES) | {"QAT-sel-finance"} <= set(names), names

        # Шаги 3–4: опции select формы (без пустой опции-плейсхолдера) == S;
        # свежесозданная QAT-sel-finance присутствует — источник данных.
        _open_form(page)
        options = _open_category_select_options(page, min_names=len(names))
        assert set(options) == set(names), (
            f"опции формы {sorted(options)} != справочнику {sorted(names)}"
        )
        assert "QAT-sel-finance" in options
        page.get_by_role("button", name="Отмена").click()
    finally:
        # Шаг 5: cleanup.
        _delete_category(web_owner_session, web_base_url, category_id)


def test_search_filter_category_select_from_directory(
    logged_in_page, web_base_url, web_owner_session
):
    """TC-sel-002 (CHK-124): select «Категория» фильтра-конструктора
    содержит ровно фактический справочник (seed + QAT-sel-filtr) — FR-30."""
    page = logged_in_page

    # Шаг 1: категория.
    category_id = _create_category(web_owner_session, web_base_url, "QAT-sel-filtr")

    try:
        # Шаг 2: справочник S (seed + заведенная категория; состав общий на
        # сессию — сверяется с фактическим S целиком ниже).
        names = _categories_names(web_owner_session, web_base_url)
        assert set(SEED_CATEGORIES) | {"QAT-sel-filtr"} <= set(names), names

        # Шаги 3–4: /search (режим «Конструктор») — опции select (без
        # пустой опции «любая») == S; свежая категория присутствует.
        page.goto(f"{web_base_url}/search")
        expect(
            page.get_by_role("button", name="Конструктор")
        ).to_be_visible()
        options = _open_filter_select_options(page, min_names=len(names))
        assert set(options) == set(names), (
            f"опции фильтра {sorted(options)} != справочнику {sorted(names)}"
        )
        assert "QAT-sel-filtr" in options
    finally:
        # Шаг 5: cleanup.
        _delete_category(web_owner_session, web_base_url, category_id)


def test_select_fields_follow_directory_changes(
    logged_in_page, web_base_url, web_owner_session
):
    """TC-sel-003 (CHK-125): добавление QAT-sel-new-project и последующее
    удаление отражаются в ОБОИХ селект-полях (форма + фильтр) после
    перезагрузки страниц — без перезапуска сервера (FR-30, данные ведущие)."""
    page = logged_in_page

    # Шаг 1: опции «до» — без QAT-sel-new-project.
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    _open_form(page)
    assert "QAT-sel-new-project" not in _open_category_select_options(page, min_names=3)
    page.get_by_role("button", name="Отмена").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    page.goto(f"{web_base_url}/search")
    expect(page.get_by_role("button", name="Конструктор")).to_be_visible()
    assert "QAT-sel-new-project" not in _open_filter_select_options(page, min_names=3)

    # Шаг 2: категория добавлена.
    category_id = _create_category(
        web_owner_session, web_base_url, "QAT-sel-new-project"
    )

    # Шаги 3–5: перезагрузка страниц (без перезапуска приложения) —
    # категория в обоих списках.
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    _open_form(page)
    assert "QAT-sel-new-project" in _open_category_select_options(page, min_names=4)
    page.get_by_role("button", name="Отмена").click()
    page.goto(f"{web_base_url}/search")
    expect(page.get_by_role("button", name="Конструктор")).to_be_visible()
    assert "QAT-sel-new-project" in _open_filter_select_options(page, min_names=4)

    # Шаг 6: cleanup + исчезновение из обоих списков после обновления.
    _delete_category(web_owner_session, web_base_url, category_id)
    page.reload()
    expect(page.get_by_role("button", name="Конструктор")).to_be_visible()
    assert "QAT-sel-new-project" not in _open_filter_select_options(page, min_names=3)
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    _open_form(page)
    assert "QAT-sel-new-project" not in _open_category_select_options(page, min_names=3)
    page.get_by_role("button", name="Отмена").click()


def test_select_fields_not_static_not_empty(
    logged_in_page, web_base_url, web_owner_session
):
    """TC-sel-004 (CHK-126, негативный): оба селект-поля непусты и точно
    равны справочнику; посторонних (захардкоженных) значений нет —
    DEF-001 закрыт."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # Шаг 1: справочник S (непустой, ≥3 — seed).
    names = _categories_names(web_owner_session, web_base_url)
    assert len(names) >= 3, names

    # Шаги 2–3: форма и фильтр — (а) непусты, (б) равны S.
    _open_form(page)
    o_form = _open_category_select_options(page, min_names=len(names))
    assert len(o_form) >= 1, "select категории формы пуст"
    assert set(o_form) == set(names), (
        f"опции формы {sorted(o_form)} != справочнику {sorted(names)}"
    )
    page.get_by_role("button", name="Отмена").click()

    page.goto(f"{web_base_url}/search")
    expect(page.get_by_role("button", name="Конструктор")).to_be_visible()
    o_filter = _open_filter_select_options(page, min_names=len(names))
    assert len(o_filter) >= 1, "select категории фильтра пуст"
    assert set(o_filter) == set(names), (
        f"опции фильтра {sorted(o_filter)} != справочнику {sorted(names)}"
    )

    # Шаг 4: посторонних значений нет (захардкоженные дефолты отсутствуют).
    assert set(o_form) - set(names) == set()
    assert set(o_filter) - set(names) == set()
