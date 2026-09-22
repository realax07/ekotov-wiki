"""UI подсказок фильтра: datalist #tag-hints на /search (Релиз 1, 1.3 / P4).

Сценарий (уточнение Заказчика): поля «Категория» и «Теги» конструктора
поиска получают подсказку — один datalist, заполненный множеством
(tags ∪ categories) из GET /api/suggestions; только уже заведенные
значения. Проверяется через DOM (Playwright): привязка list=,
содержимое option'ов, set-семантика/сортировка.

TC-ID: TC-UI-SUGG-001, TC-UI-SUGG-002, TC-sugg-007. Формат: 1 кейс = 1 тест
(contract 6);
трассировка — ТЗ Релиза 1 задача 1.3 (PRODUCT_BACKLOG.md, план релиза),
домен search (FR-10/FR-11); CHK от qa-контура на R1.3 еще нет (QA-цикл
1.5 впереди) — тесты написаны по ТЗ задачи (в отчете ПМ).

REVALIDATE (CHK-141/142/143, impact §2.1, add-r2-categories-settings):
- поле «Категория» конструктора — SELECT из GET /api/categories (FR-19/
  FR-30, DEF-001): без атрибута list, свободный ввод невозможен;
- «Теги» — input с datalist #tag-hints из GET /api/suggestions (без
  изменений); источник категорий в подсказках — ПО ТЕКУЩЕЙ РЕАЛИЗАЦИИ
  (значения задач: теги + категории задач, sdd r2 §3.2 «без изменений»);
  если реализация переведет категории подсказок на справочник —
  пересмотреть ожидания (эскалация б, CHK-142).
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def _search_page(logged_in_page, web_base_url):
    """Открытая вкладка поиска (вход owner уже выполнен фикстурой)."""
    logged_in_page.goto(f"{web_base_url}/search")
    expect(
        logged_in_page.get_by_role("button", name="Конструктор")
    ).to_be_visible()
    return logged_in_page


def _category_directory(web_owner_session, web_base_url) -> set[str]:
    """Фактический справочник категорий из GET /api/categories (источник
    select-полей, FR-30; sdd r2 §3.1)."""
    resp = web_owner_session.get(f"{web_base_url}/api/categories")
    assert resp.status_code == 200
    return {item["name"] for item in resp.json()["categories"]}


def _select_option_names(select) -> list[str]:
    """Имена опций select без пустой опции-плейсхолдера («любая»/«—»)."""
    return [
        select.nth(i).text_content().strip()
        for i in range(select.count())
        if select.nth(i).get_attribute("value")
    ]


# regression: keep — FR-15: datalist тегов + заполнение option из живого
# ответа API; REVALIDATE CHK-141: поле категории — select из справочника
# (impact-001 п.1, TC-UI-SUGG-001-update таблица шаг 2).
def test_tag_hints_datalist_bound_and_filled(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-UI-SUGG-001 (revalidate CHK-141): привязка подсказок ПОЛЯМ
    РАЗДЕЛЕНА — поле «Категория» конструктора — select, опции сверены с
    GET /api/categories (set-равенство, без пустой опции-плейсхолдера),
    атрибута list нет; поле «Теги» — input с list="tag-hints"; после
    создания задачи с уникальной категорией и тегом — datalist #tag-hints
    заполнен из GET /api/suggestions (только существующие значения)."""
    # Подготовка: категория-носитель — в справочник (FR-21: задача с
    # категорией вне справочника — 422; impact §4.1: QAT-категории —
    # через автосоздание, cleanup возвращает справочник к seed).
    cat_created = web_owner_session.post(
        f"{web_base_url}/api/categories",
        json={"name": "QAT-UI-Категория"},
    )
    assert cat_created.status_code == 201, f"seed категории: {cat_created.text}"
    category_id = cat_created.json()["id"]

    # Подготовка: задача с уникальными категорией и тегом (через API —
    # источник данных кейса; UI-часть кейса — подсказки на /search).
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": "QAT-UI-SUGG-источник",
            "category": "QAT-UI-Категория",
            "tags": ["QAT-UI-Тег"],
        },
    )
    assert created.status_code == 201
    web_cleanup_created(created.json()["id"])

    try:
        page = _search_page(logged_in_page, web_base_url)

        # Шаг 2 (обновленный): «Категория» — select из справочника (FR-19/
        # FR-30): тег SELECT, атрибута list нет, опции == GET /api/categories.
        category_select = page.locator("#search-category")
        assert category_select.evaluate(
            "el => el.tagName.toLowerCase()"
        ) == "select", "поле категории не select"
        expect(category_select).not_to_have_attribute("list", "tag-hints")
        category_options = category_select.locator("option")
        expected_categories = _category_directory(web_owner_session, web_base_url)
        actual_categories = set(_select_option_names(category_options))
        assert actual_categories == expected_categories, (
            f"опции select категории {actual_categories} != справочнику "
            f"{expected_categories}"
        )

        # Шаг 3 (без изменений): «Теги» — input с list="tag-hints".
        datalist = page.locator("#tag-hints")
        expect(datalist).to_be_attached()
        expect(page.locator("#search-tags")).to_have_attribute(
            "list", "tag-hints"
        )

        # Шаг 4 (без изменений): datalist заполнен из /api/suggestions:
        # option'ы = значения множества (для поля тегов).
        resp = web_owner_session.get(f"{web_base_url}/api/suggestions")
        assert resp.status_code == 200
        expected = set(resp.json()["suggestions"])
        assert {"QAT-UI-Категория", "QAT-UI-Тег"} <= expected  # фикстура дошла

        options = datalist.locator("option")
        expect(options).to_have_count(len(expected), timeout=10_000)
        actual = {
            options.nth(i).text_content().strip() for i in range(options.count())
        }
        assert actual == expected
        assert "QAT-UI-Категория" in actual
        assert "QAT-UI-Тег" in actual
    finally:
        # Cleanup категории (impact §4.1 п.2: тесты, создающие категории,
        # восстанавливают справочник; задачи удалены web_cleanup_created,
        # поэтому DELETE не упрется в 409 «in use»).
        web_owner_session.delete(f"{web_base_url}/api/categories/{category_id}")


# regression: keep — FR-16 в UI: дубль пересечения + порядок option;
# источник истины — живой ответ API, QAT-значения изолированы (impact-001 п.1).
# REVALIDATE CHK-142: категория пересечения предварительно заводится в
# справочник (иначе 422 на setup по FR-21); источник категорий подсказок —
# по текущей реализации (значения задач, sdd r2 §3.2) — уточнить в sdd.
def test_tag_hints_set_semantics_and_order(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-UI-SUGG-002 (revalidate CHK-142; set-семантика + сортировка в UI):
    значение, входящее и в теги, и в категорию, встречается в datalist
    ОДИН раз; option'ы идут в отсортированном порядке (как вернул API).
    Категория `QAT-UI-Общее` заведена в справочник ДО создания задачи
    (FR-21: без этого — 422 на setup)."""
    # Шаг 1 (обновленный, среда): категория пересечения — в справочник.
    cat_created = web_owner_session.post(
        f"{web_base_url}/api/categories",
        json={"name": "QAT-UI-Общее"},
    )
    assert cat_created.status_code == 201, f"seed категории: {cat_created.text}"
    category_id = cat_created.json()["id"]

    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": "QAT-UI-SUGG-пересечение",
            "category": "QAT-UI-Общее",  # категория = тегу: пересечение
            "tags": ["QAT-UI-Общее", "QAT-UI-Альфа"],
        },
    )
    assert created.status_code == 201
    web_cleanup_created(created.json()["id"])

    try:
        page = _search_page(logged_in_page, web_base_url)

        options = page.locator("#tag-hints option")
        expect(options.filter(has_text="QAT-UI-Общее")).to_have_count(
            1, timeout=10_000
        ), "пересечение тега и категории задублировано"

        # Ожидаемое множество и его сортировка — из API (источник истины).
        resp = web_owner_session.get(f"{web_base_url}/api/suggestions")
        assert resp.status_code == 200
        expected_sorted = sorted(set(resp.json()["suggestions"]))

        expect(options).to_have_count(len(expected_sorted), timeout=10_000)
        actual_order = [
            options.nth(i).text_content().strip() for i in range(options.count())
        ]
        assert actual_order == expected_sorted, (
            "option'ы не в отсортированном порядке"
        )
    finally:
        # Cleanup (TC-UI-SUGG-002-update шаг 1): категория удаляется после
        # теста (справочник возвращается к seed-составу).
        web_owner_session.delete(f"{web_base_url}/api/categories/{category_id}")


# regression: keep — устойчивое поведение FR-17 (Scenario 7 спеки:
# свободный ввод легитимен, источник подсказок не меняется).
# REVALIDATE CHK-143 (TC-sugg-007-update, расщепление по доменам):
# «Теги» — keep-семантика (свободный ввод легитимен, FR-11); «Категория»
# — select из справочника (FR-19): свободный ввод НЕВОЗМОЖЕН, значение
# можно только выбрать. Ссылка на конфликт спек (сценарий 7 спеки
# add-suggestions vs FR-19): решение о сужении сценария 7 — за ПМ/
# Заказчиком (эскалация в), кейс написан по доменам.
def test_free_input_does_not_change_suggestions_source(
    logged_in_page, web_base_url, web_owner_session
):
    """TC-sugg-007 (revalidate CHK-143, негативный, по доменам): «Теги» —
    свободный ввод вне datalist принят и не меняет источник подсказок
    (снимок S0 до == после); «Категория» фильтра — select: свободный ввод
    невозможен (тег SELECT, fill() отклоняется, значение вне справочника
    выбрать нельзя, FR-19)."""
    # Предусловие: снимок S0 подсказок (HTTP 200).
    snapshot = web_owner_session.get(f"{web_base_url}/api/suggestions")
    assert snapshot.status_code == 200
    s0 = snapshot.json()["suggestions"]

    page = _search_page(logged_in_page, web_base_url)

    # Шаг 1 (без изменений, домен «Теги»): поле «Теги» (доступное имя
    # дословно «Теги (через запятую)» — minor №2 ревью-001; атрибут
    # list="tag-hints", id #search-tags): ввод значения, которого нет в
    # datalist. ARIA-роль input'а с атрибутом list — combobox (не textbox,
    # как в тексте кейса).
    tags_input = page.get_by_role("combobox", name="Теги (через запятую)")
    expect(tags_input).to_have_attribute("list", "tag-hints")
    tags_input.fill("QAT-SUGG-Новый-Свободный")
    assert tags_input.input_value() == "QAT-SUGG-Новый-Свободный", (
        "свободный ввод в поле «Теги» не принят (ввод не должен блокироваться)"
    )

    # Шаг 2 (ЗАМЕНЕН, домен «Категория», FR-19): поле категории — select
    # из справочника. (а) тег SELECT — fill() на нем невозможен; (б)
    # попытка fill() → исключение Playwright / ввод не принят; (в) выбрать
    # можно только значение из справочника — произвольного текста в опциях
    # нет (DEF-001: опции == GET /api/categories).
    category_select = page.locator("#search-category")
    assert category_select.evaluate("el => el.tagName.toLowerCase()") == "select", (
        "поле категории не select (FR-19)"
    )
    try:
        category_select.fill("QAT-SUGG-Новая-Кат-Свободная")
        raise AssertionError(
            "fill() на select категории не отклонен — свободный ввод "
            "в поле категории возможен (нарушение FR-19)"
        )
    except Exception:
        pass  # ожидаемо: select не принимает fill() (FR-19)
    category_options = category_select.locator("option")
    directory = _category_directory(web_owner_session, web_base_url)
    assert set(_select_option_names(category_options)) == directory
    assert "QAT-SUGG-Новая-Кат-Свободная" not in directory

    # Шаг 3 (обновленный): перезагрузить /search — loadSuggestions()
    # выполнится повторно; в datalist нет опции свободного тега; опций
    # QAT-SUGG-Новая-Кат-Свободная в select категории нет по построению
    # (select не содержит значений вне справочника).
    page.reload()
    expect(
        page.get_by_role("button", name="Конструктор")
    ).to_be_visible()
    options = page.locator("#tag-hints option")
    expect(options.filter(has_text="QAT-SUGG-Новый-Свободный")).to_have_count(0)
    page.locator("#search-category option").filter(
        has_text="QAT-SUGG-Новая-Кат-Свободная"
    ).first.wait_for(state="detached")

    # Шаг 4 (без изменений): API-контроль — снимок идентичен S0 (подвыборка
    # QAT-SUGG: ничего не появилось и не исчезло; префиксное сравнение —
    # minor №3 ревью-001, полный список на общем стенде может меняться
    # посторонне).
    after = web_owner_session.get(f"{web_base_url}/api/suggestions")
    assert after.status_code == 200
    s_after = after.json()["suggestions"]
    assert sorted(s_after) == s_after

    def subset(items):
        return [s for s in items if s.startswith("QAT-SUGG")]

    free_values = {"QAT-SUGG-Новый-Свободный", "QAT-SUGG-Новая-Кат-Свободная"}
    assert not (set(subset(s_after)) - set(subset(s0))), (
        "свободный ввод создал новые значения в источнике подсказок"
    )
    assert not (set(subset(s0)) - set(subset(s_after))), (
        "значения подсказок исчезли после свободного ввода"
    )
    assert free_values.isdisjoint(s_after), (
        "свободные значения шагов 1–2 попали в подсказки"
    )
