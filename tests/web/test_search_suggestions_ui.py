"""UI подсказок фильтра: datalist #tag-hints на /search (Релиз 1, 1.3 / P4).

Сценарий (уточнение Заказчика): поля «Категория» и «Теги» конструктора
поиска получают подсказку — один datalist, заполненный множеством
(tags ∪ categories) из GET /api/suggestions; только уже заведенные
значения. Проверяется через DOM (Playwright): привязка list=,
содержимое option'ов, set-семантика/сортировка.

TC-ID: TC-UI-SUGG-001, TC-UI-SUGG-002. Формат: 1 кейс = 1 тест
(contract 6);
трассировка — ТЗ Релиза 1 задача 1.3 (PRODUCT_BACKLOG.md, план релиза),
домен search (FR-10/FR-11); CHK от qa-контура на R1.3 еще нет (QA-цикл
1.5 впереди) — тесты написаны по ТЗ задачи (в отчете ПМ).
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


# regression: keep — FR-15/СЦ-8: привязка datalist к обоим полям + заполнение
# option из живого ответа API; захардкоженных ожиданий нет (impact-001 п.1).
def test_tag_hints_datalist_bound_and_filled(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-UI-SUGG-001: datalist #tag-hints существует и привязан к ОБОИМ
    полям (категория list="tag-hints", теги list="tag-hints"); после
    создания задачи с уникальными категорией и тегом — GET /api/suggestions
    отдает их, search.js заполняет datalist option'ами (только существующие
    значения)."""
    # Подготовка: задача с уникальными категорией и тегом (через API —
    # источник данных кейса; UI-часть кейса — datalist на /search).
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

    page = _search_page(logged_in_page, web_base_url)

    datalist = page.locator("#tag-hints")
    expect(datalist).to_be_attached()
    expect(page.locator("#search-category")).to_have_attribute(
        "list", "tag-hints"
    )
    expect(page.locator("#search-tags")).to_have_attribute("list", "tag-hints")

    # Даталист заполнен из /api/suggestions: option'ы = значения множества.
    resp = web_owner_session.get(f"{web_base_url}/api/suggestions")
    assert resp.status_code == 200
    expected = set(resp.json()["suggestions"])
    assert {"QAT-UI-Категория", "QAT-UI-Тег"} <= expected  # фикстура дошла

    options = datalist.locator("option")
    expect(options).to_have_count(len(expected), timeout=10_000)
    actual = {options.nth(i).text_content().strip() for i in range(options.count())}
    assert actual == expected
    assert "QAT-UI-Категория" in actual
    assert "QAT-UI-Тег" in actual


# regression: keep — FR-16 в UI: дубль пересечения + порядок option;
# источник истины — живой ответ API, QAT-значения изолированы (impact-001 п.1).
def test_tag_hints_set_semantics_and_order(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-UI-SUGG-002 (set-семантика + сортировка в UI): значение, входящее
    и в теги, и в категории, встречается в datalist ОДИН раз; option'ы идут
    в отсортированном порядке (как вернул API)."""
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
    assert actual_order == expected_sorted, "option'ы не в отсортированном порядке"


# regression: keep — устойчивое поведение FR-17 (Scenario 7 спеки:
# свободный ввод легитимен, источник подсказок не меняется).
def test_free_input_does_not_change_suggestions_source(
    logged_in_page, web_base_url, web_owner_session
):
    """TC-sugg-007 (CHK-S-7, негативный): свободный ввод вне datalist не
    меняет источник подсказок — снимок S0 до == после (Scenario 7 спеки
    add-suggestions)."""
    # Предусловие: снимок S0 подсказок (HTTP 200).
    snapshot = web_owner_session.get(f"{web_base_url}/api/suggestions")
    assert snapshot.status_code == 200
    s0 = snapshot.json()["suggestions"]

    page = _search_page(logged_in_page, web_base_url)

    # Шаг 1: поле «Теги» (доступное имя дословно «Теги (через запятую)» —
    # minor №2 ревью-001; атрибут list="tag-hints", id #search-tags):
    # ввод значения, которого нет в datalist. ARIA-роль input'а с атрибутом
    # list — combobox (не textbox, как в тексте кейса).
    tags_input = page.get_by_role("combobox", name="Теги (через запятую)")
    expect(tags_input).to_have_attribute("list", "tag-hints")
    tags_input.fill("QAT-SUGG-Новый-Свободный")
    assert tags_input.input_value() == "QAT-SUGG-Новый-Свободный", (
        "свободный ввод в поле «Теги» не принят (ввод не должен блокироваться)"
    )

    # Шаг 2: поле «Категория» (доступное имя «Категория», list="tag-hints",
    # id #search-category) — аналогичный свободный ввод (ARIA-роль combobox).
    category_input = page.get_by_role("combobox", name="Категория")
    expect(category_input).to_have_attribute("list", "tag-hints")
    category_input.fill("QAT-SUGG-Новая-Кат-Свободная")
    assert category_input.input_value() == "QAT-SUGG-Новая-Кат-Свободная", (
        "свободный ввод в поле «Категория» не принят"
    )

    # Шаг 3: перезагрузить страницу — loadSuggestions() выполнится повторно;
    # в datalist нет опций со свободными значениями шагов 1–2.
    page.reload()
    expect(
        page.get_by_role("button", name="Конструктор")
    ).to_be_visible()
    options = page.locator("#tag-hints option")
    expect(options.filter(has_text="QAT-SUGG-Новый-Свободный")).to_have_count(0)
    expect(options.filter(has_text="QAT-SUGG-Новая-Кат-Свободная")).to_have_count(0)

    # Шаг 4: API-контроль — снимок идентичен S0 (подвыборка QAT-SUGG:
    # ничего не появилось и не исчезло; префиксное сравнение — minor №3
    # ревью-001, полный список на общем стенде может меняться посторонне).
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
