"""Домен sel — селект-поля и подсказки из фактических данных
(QA-этап 5, change add-r3-visual-foundation, FR-35, DEF-001).

Кейсы_TC (approved test-model/approved/add-r3-visual-foundation/):
- TC-sel-101: категория в форме задачи = справочник («—» + Дом/Работа/Личное).
- TC-sel-102: РУЧНОЙ кейс на прод-сессии Заказчика — НЕ автоматизируется
  (ЗАПРЕЩЕНА автоматизация: прод + сессия Заказчика). Носитель — manual-
  тест с процедурой в docstring (skip).
- TC-sel-103: 401 подсказок → немой пустой datalist (урок DEF-001) —
  кейс документирует молчаливый отказ.
- TC-sel-104: категория в фильтре-конструкторе = справочник («любая» + seed).
- TC-sel-105: появление/удаление категории отражается в обоих селектах
  (прогон в одиночной сессии; маркер serial).
- TC-sel-106: подсказки (datalist формы и поиска) показывают значения
  из БД (тег + категория задачи-маркера).
- TC-sel-107: единый механизм — все 4 источника из 2 эндпоинтов
  (categories/suggestions), в DOM нет значений вне ответов API.
- TC-sel-108 (негатив): пустые и статические списки не допускаются.
"""

import json

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.web, pytest.mark.must]

# Порядок опций/ответа — сортировка по имени (GET /api/categories по name).
SEED = ("Дом", "Личное", "Работа")


def _option_texts(locator) -> list[str]:
    return [
        locator.nth(i).text_content().strip() for i in range(locator.count())
    ]


def _search_page(logged_in_page, web_base_url):
    logged_in_page.goto(f"{web_base_url}/search")
    expect(
        logged_in_page.get_by_role("button", name="Конструктор")
    ).to_be_visible()
    return logged_in_page


# --------------------------------------------------------------------------
# TC-sel-101 — «категория в форме задачи из справочника» (Must)
# --------------------------------------------------------------------------
def test_task_form_category_options_from_directory(board_page):
    """TC-sel-101 (CHK-174): #task-category = пустое «—» (nullable, Д-2) +
    ровно «Дом», «Работа», «Личное» — фактический справочник, без иных
    значений."""
    page = board_page
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.get_by_role("heading", name="Создание задачи")).to_be_visible()

    select = page.locator("#task-category")
    expect(select.locator("option")).to_have_count(4)
    options = _option_texts(select.locator("option"))
    assert options == ["—", *SEED], options


# --------------------------------------------------------------------------
# TC-sel-102 — РУЧНАЯ (прод-сессия Заказчика) — НЕ автоматизируется
# --------------------------------------------------------------------------
@pytest.mark.manual
def test_sel_102_manual_customer_production_session():
    """TC-sel-102 (CHK-180) — РУЧНАЯ процедура, автоматизация ЗАПРЕЩЕНА
    (прод + сессия Заказчика; носитель протокола ручной процедуры).

    Предусловия: задачи 5.1/5.2; подтверждение у Заказчика фактического
    URL входа (def001-diagnosis §6.1). Шаги будущей сессии:
    1. Подтвердить URL входа (адресная строка: http или https).
    2. https: воспроизвести вместе с Заказчиком — вход → /search → фокус
       на полях подсказок; значения видны → DEF-001 закрыт, скриншот.
    3. http: применить фикс §3 диагностики (редирект 80→https / контрольное
       сообщение login.js), повторить шаг 2.
    4. Результат (скриншот/протокол) — в test-model/ и tasks.md 5.3.
    Ожидаемый результат: в реальной сессии подсказки и селект-поля
    отображают фактические значения БД в UI; протокол зафиксирован.
    """
    pytest.skip("ручная процедура на проде (сессия Заказчика) — не автоматизируется")


# --------------------------------------------------------------------------
# TC-sel-103 — «негатив: 401 подсказок — немой пустой datalist» (Must)
# --------------------------------------------------------------------------
def test_suggestions_401_silent_empty_datalist(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-sel-103 (CHK-181): /search с непустым datalist → route-перехват
    /api/suggestions → 401 → перезагрузка: datalist пуст/прежний без
    сообщения (молчаливый отказ — текущий дизайн), ошибок в консоли нет."""
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-sel-401-носитель", "tags": ["QAT-sel-401"]},
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])

    page = _search_page(logged_in_page, web_base_url)
    options = page.locator("#tag-hints option")
    expect(options.filter(has_text="QAT-sel-401")).to_have_count(1, timeout=10_000)

    # Нештатные JS-ошибки страницы (uncaught); сетевые записи браузера о
    # самом 401 («Failed to load resource») — шум браузера, не ошибка JS.
    page_errors: list[str] = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    def _unauthorized(route):
        route.fulfill(
            status=401,
            body='{"error": "unauthorized"}',
            content_type="application/json",
        )

    page.route("**/api/suggestions", _unauthorized)
    page.reload()
    expect(
        page.get_by_role("button", name="Конструктор")
    ).to_be_visible()

    # Прямой fetch из страницы подтверждает 401 перехвата.
    status = page.evaluate(
        "async () => (await fetch('/api/suggestions')).status"
    )
    assert status == 401, status

    # Datalist пуст/прежний: опции QAT-sel-401 нет (полная перезагрузка).
    expect(options.filter(has_text="QAT-sel-401")).to_have_count(0)
    # Нештатных JS-ошибок нет (молчаливый отказ — дизайн search.js).
    assert page_errors == [], page_errors


# --------------------------------------------------------------------------
# TC-sel-104 — «категория в фильтре-конструкторе из справочника» (Must)
# --------------------------------------------------------------------------
def test_search_filter_category_options_from_directory(logged_in_page, web_base_url):
    """TC-sel-104 (CHK-175): #search-category = «любая» (пустое значение,
    вне справочника) + ровно Дом/Работа/Личное."""
    page = _search_page(logged_in_page, web_base_url)

    select = page.locator("#search-category")
    expect(select.locator("option")).to_have_count(4)
    texts = _option_texts(select.locator("option"))
    assert texts == ["любая", *SEED], texts
    assert select.locator("option").nth(0).get_attribute("value") == ""


# --------------------------------------------------------------------------
# TC-sel-105 — «изменение справочника отражается в обоих селектах» (Must)
# --------------------------------------------------------------------------
@pytest.mark.serial
def test_category_directory_changes_reflected_in_both_selects(
    logged_in_page, web_base_url, web_owner_session
):
    """TC-sel-105 (CHK-176; одиночная сессия — маркер serial): создание
    `QAT-sel-новая` (без задачи на ней) появляется в #task-category и
    #search-category; удаление (дополнение автора кейса) — исчезает из
    обоих. Задачи на категории кейс не создает."""
    created = web_owner_session.post(
        f"{web_base_url}/api/categories", json={"name": "QAT-sel-новая"}
    )
    assert created.status_code == 201, created.text
    category_id = created.json()["id"]
    try:
        # Форма задачи: опции перезагружаются при каждом открытии.
        page = logged_in_page
        page.goto(f"{web_base_url}/board")
        expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
        page.get_by_role("button", name="Создать задачу").click()
        form_options = page.locator("#task-category option")
        expect(form_options.filter(has_text="QAT-sel-новая")).to_have_count(
            1, timeout=10_000
        )
        page.get_by_role("button", name="Отмена").click()

        # Фильтр-конструктор.
        _search_page(page, web_base_url)
        search_options = page.locator("#search-category option")
        expect(search_options.filter(has_text="QAT-sel-новая")).to_have_count(
            1, timeout=10_000
        )
    finally:
        assert web_owner_session.delete(
            f"{web_base_url}/api/categories/{category_id}"
        ).status_code == 200

    # После удаления категория исчезла из обоих (дополнение автора кейса).
    page = logged_in_page
    _search_page(page, web_base_url)
    search_options = page.locator("#search-category option")
    expect(search_options.filter(has_text="QAT-sel-новая")).to_have_count(0)

    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    page.get_by_role("button", name="Создать задачу").click()
    form_options = page.locator("#task-category option")
    expect(form_options.filter(has_text="QAT-sel-новая")).to_have_count(0)


# --------------------------------------------------------------------------
# TC-sel-106 — «подсказки показывают значения из БД» (Must)
# --------------------------------------------------------------------------
def test_datalists_show_task_tag_and_category_values(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-sel-106 (CHK-177): задача-маркер (тег `QAT-sel-тег`, категория
    «Дом») видна в datalist'ах. r6 (ОВ-1/Д-14, FR-57): форма запрашивает
    GET /api/suggestions?kind=tags — в #task-tag-hints только теги
    (категории больше нет, это осознанное поведение ОВ-1); поиск
    (#tag-hints) ходит без параметра — прежний UNION (ОГР-26), там видны
    и тег, и категория; значения из БД видны пользователю."""
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-sel-маркер", "tags": ["QAT-sel-тег"], "category": "Дом"},
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])

    # Форма задачи: datalist перезагружается при каждом открытии.
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    page.get_by_role("button", name="Создать задачу").click()
    form_hints = page.locator("#task-tag-hints option")
    expect(form_hints.filter(has_text="QAT-sel-тег")).to_have_count(1, timeout=10_000)
    # ОВ-1/Д-14: форма — только теги, категории в подсказках формы нет.
    expect(form_hints.filter(has_text="Дом")).to_have_count(0)
    # Дублей нет (set-семантика).
    texts = _option_texts(form_hints)
    assert len(texts) == len(set(texts)), texts
    page.get_by_role("button", name="Отмена").click()

    # Поиск.
    _search_page(page, web_base_url)
    search_hints = page.locator("#tag-hints option")
    expect(search_hints.filter(has_text="QAT-sel-тег")).to_have_count(1, timeout=10_000)
    expect(search_hints.filter(has_text="Дом")).to_have_count(1)


# --------------------------------------------------------------------------
# TC-sel-107 — «единый механизм: два общих эндпоинта» (Must)
# --------------------------------------------------------------------------
def test_single_mechanism_two_endpoints(
    logged_in_page, web_base_url, web_owner_session
):
    """TC-sel-107 (CHK-178): перехват сети: категории (форма и фильтр) —
    из GET /api/categories; подсказки (оба datalist) — из GET
    /api/suggestions; значения в DOM не выходят за ответы API."""
    page = logged_in_page

    api_responses: dict[str, object] = {}
    urls_seen: list[str] = []

    def _on_response(response):
        url = response.url
        if url.endswith("/api/categories"):
            urls_seen.append(url)
            try:
                api_responses["categories"] = response.json()
            except json.JSONDecodeError:
                pass
        elif url.endswith("/api/suggestions"):
            urls_seen.append(url)
            try:
                api_responses["suggestions"] = response.json()
            except json.JSONDecodeError:
                pass

    page.on("response", _on_response)

    # Форма задачи (категории + подсказки).
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-category option")).to_have_count(4)
    page.get_by_role("button", name="Отмена").click()

    # Поиск (категории + подсказки).
    _search_page(page, web_base_url)
    expect(page.locator("#search-category option")).to_have_count(4)

    assert "categories" in api_responses and "suggestions" in api_responses, (
        urls_seen
    )
    directory = {item["name"] for item in api_responses["categories"]["categories"]}
    suggestions = set(api_responses["suggestions"]["suggestions"])

    # Значения в DOM не выходят за ответы двух эндпоинтов.
    for selector in ("#task-category option", "#search-category option"):
        values = set(
            page.locator(selector).nth(i).text_content().strip()
            for i in range(page.locator(selector).count())
        ) - {"—", "любая"}
        assert values <= directory, (selector, values - directory)

    for selector in ("#task-tag-hints option", "#tag-hints option"):
        texts = set(
            page.locator(selector).nth(i).text_content().strip()
            for i in range(page.locator(selector).count())
        )
        assert texts <= suggestions, (selector, texts - suggestions)


# --------------------------------------------------------------------------
# TC-sel-108 — «негатив: пустые и статические списки не допускаются» (Must)
# --------------------------------------------------------------------------
def test_selects_not_empty_not_static(logged_in_page, web_base_url):
    """TC-sel-108 (CHK-179): оба поля — ≥2 опции (служебное пустое +
    справочник), состав равен справочнику, лишних/захардкоженных нет."""
    page = logged_in_page

    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    page.get_by_role("button", name="Создать задачу").click()
    form_select = page.locator("#task-category")
    expect(form_select.locator("option")).to_have_count(4)
    page.get_by_role("button", name="Отмена").click()

    _search_page(page, web_base_url)
    search_select = page.locator("#search-category")
    expect(search_select.locator("option")).to_have_count(4)

    expected_search = ["любая", *SEED]
    assert _option_texts(search_select.locator("option")) == expected_search

    # Форма задачи — сверка при открытой форме (страница /board).
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    page.get_by_role("button", name="Создать задачу").click()
    expect(form_select.locator("option")).to_have_count(4)
    expected_form = ["—", *SEED]
    assert _option_texts(form_select.locator("option")) == expected_form
