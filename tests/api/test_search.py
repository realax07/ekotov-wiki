"""Домен search: TC-search-001…011 (CHK-66…76; approved/add-kanban-core/search-01.md).

GET /api/search — все параметры опциональны, archived по умолчанию all
(sdd §3.5). Повторяемый tag — ИЛИ внутри признака, IN (design §6).
Кейсы с UI-частью (вкладка поиска, конструктор) — API-часть здесь, UI —
tests/web (см. README).
"""

import pytest

pytestmark = [pytest.mark.api]


@pytest.fixture
def search_fixtures(api, cleanup_task, shift_done_at_yesterday):
    """Фикстура данных поиска (предусловия search-01.md): ВЫС, СРЕД, АРХ."""
    high = cleanup_task(
        "QAT-Поиск-ВЫС", priority="high", category="Дом",
        tags=["urgent"], due_date="2026-10-01",
    )
    medium = cleanup_task(
        "QAT-Поиск-СРЕД", priority="medium", category="Работа",
        tags=["home"], due_date="2026-10-10",
    )
    arch = cleanup_task(
        "QAT-Поиск-АРХ", priority="high", category="Дом", tags=["urgent"]
    )
    api.move(arch["id"], "done")
    shift_done_at_yesterday(arch["id"], "15:00")
    api.board()  # ленивая автоархивация
    return {"high": high, "medium": medium, "arch": arch}


@pytest.mark.must
def test_search_page_builder_reachable(base_url, owner_session):
    """TC-search-001 (API-часть): вкладка поиска доступна авторизованному:
    GET /search — 200, страница с элементами поиска (конструктор/advanced).
    UI-часть (переход через сайдбар) — tests/web."""
    resp = owner_session.get(f"{base_url}/search")
    assert resp.status_code == 200
    assert 'id="search-builder-form"' in resp.text
    assert 'id="search-mode-advanced"' in resp.text


@pytest.mark.must
def test_filter_by_single_attribute(api, search_fixtures):
    """TC-search-002 (API-часть): фильтр priority=high — в результатах только
    priority=high: Поиск-ВЫС и Поиск-АРХ; Поиск-СРЕД отсутствует."""
    resp = api.search(priority="high")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()["results"]]
    assert "QAT-Поиск-ВЫС" in titles
    assert "QAT-Поиск-АРХ" in titles
    assert "QAT-Поиск-СРЕД" not in titles
    for t in resp.json()["results"]:
        assert t["priority"] == "high"


@pytest.mark.must
def test_filter_combination_two_attributes(api, search_fixtures):
    """TC-search-003 (API-часть): комбинация priority=high И category=Дом —
    только задачи, удовлетворяющие обоим условиям: ВЫС и АРХ; СРЕД отфильтован."""
    resp = api.search(priority="high", category="Дом")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()["results"]]
    assert "QAT-Поиск-ВЫС" in titles
    assert "QAT-Поиск-АРХ" in titles
    assert "QAT-Поиск-СРЕД" not in titles
    for t in resp.json()["results"]:
        assert t["priority"] == "high" and t["category"] == "Дом"


@pytest.mark.must
def test_empty_filter_returns_all_tasks(api, search_fixtures):
    """TC-search-004 (API-часть): пустой фильтр = все задачи: results содержит
    N задач — и активные, и архивные (по умолчанию archived=all, sdd §3.5);
    N совпадает с контрольным полным подсчетом."""
    n = len(api.search(archived="all").json()["results"])
    resp = api.search()
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == n
    assert {t["title"] for t in results} >= {
        "QAT-Поиск-ВЫС", "QAT-Поиск-СРЕД", "QAT-Поиск-АРХ",
    }


@pytest.mark.must
def test_filter_no_matches_empty_result(api):
    """TC-search-005: фильтр без совпадений: HTTP 200, "results": []
    (корректное пустое состояние, без ошибок)."""
    resp = api.search(category="QAT-Несуществующая-категория")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.must
def test_switch_builder_to_advanced_normalized(api, search_fixtures):
    """TC-search-006 (API-часть): условие конструктора «priority = high»
    эквивалентно advanced-фильтру: normalized_query содержит priority = "high";
    ответ API-эквивалента идентичен выдаче GET."""
    resp = api.advanced('priority = "high"')
    assert resp.status_code == 200
    assert 'priority = "high"' in resp.json()["normalized_query"]

    titles = [t["title"] for t in resp.json()["results"]]
    assert "QAT-Поиск-ВЫС" in titles
    assert "QAT-Поиск-АРХ" in titles
    assert "QAT-Поиск-СРЕД" not in titles


@pytest.mark.must
def test_edit_advanced_filter_and_apply(api, search_fixtures):
    """TC-search-007 (API-часть): правка фильтра в advanced и применение:
    priority = "medium" AND tag IN ("home") — только Поиск-СРЕД; ВЫС/АРХ не
    в выдаче; API: 200."""
    resp = api.advanced('priority = "medium" AND tag IN ("home")')
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()["results"]]
    assert titles == ["QAT-Поиск-СРЕД"]
    assert "QAT-Поиск-ВЫС" not in titles
    assert "QAT-Поиск-АРХ" not in titles


@pytest.mark.must
def test_invalid_advanced_filter_400_data_untouched(api, search_fixtures):
    """TC-search-008: некорректный фильтр в advanced: HTTP 400, тело
    {"error": "filter syntax: …"}; запрос не выполняется. Данные не изменены:
    повторный корректный поиск возвращает тот же набор (Поиск-СРЕД)."""
    resp_bad = api.advanced('priority === "high" AND ((')
    assert resp_bad.status_code == 400
    assert resp_bad.json()["error"].startswith("filter syntax:")

    # данные не тронуты: контрольный корректный поиск — те же результаты
    resp_ok = api.advanced('priority = "medium" AND tag IN ("home")')
    assert resp_ok.status_code == 200
    titles = [t["title"] for t in resp_ok.json()["results"]]
    assert titles == ["QAT-Поиск-СРЕД"]


@pytest.mark.must
def test_empty_advanced_text_not_5xx(api):
    """TC-search-009: пустой текст фильтра в advanced — поведение не
    специфицировано (DS-4): фиксируем факт. Допустимо: «все задачи» (200 c
    results), ошибка синтаксиса 400, либо 200 c results: []. НЕ допустим
    5xx/зависание. Окончательное ожидание — после решения DS-4 через ПМ."""
    resp = api.advanced("")
    assert resp.status_code < 500, f"DS-4, зафиксировано: {resp.status_code} {resp.text}"
    if resp.status_code == 200:
        assert isinstance(resp.json().get("results"), list)


@pytest.mark.should
def test_api_search_with_filter_and_repeated_tag(api, search_fixtures):
    """TC-search-010: поиск через API с фильтром. Шаг 1: priority=high&archived=false
    — только неархивные priority=high (Поиск-ВЫС; АРХ исключен архивностью).
    Шаг 2: повторяемый tag=urgent&tag=home — семантика И/ИЛИ спекой НЕ определена
    (DS, эскалация ПМ): фиксируем факт — 200, валидный results, у задач поля
    признаков и архивности; фактическая семантика — в протокол (README)."""
    resp1 = api.search(priority="high", archived="false")
    assert resp1.status_code == 200
    titles = [t["title"] for t in resp1.json()["results"]]
    assert "QAT-Поиск-ВЫС" in titles
    assert "QAT-Поиск-АРХ" not in titles

    resp2 = api.search(tag=["urgent", "home"])
    assert resp2.status_code < 500, f"DS: повторяемый tag → {resp2.status_code}"
    assert isinstance(resp2.json().get("results"), list)
    for t in resp2.json()["results"]:
        assert "priority" in t and "archived_at" in t
    # фактическая семантика (design §6: ИЛИ = IN): обе задачи с любым из тегов
    titles2 = [t["title"] for t in resp2.json()["results"]]
    assert "QAT-Поиск-ВЫС" in titles2 and "QAT-Поиск-СРЕД" in titles2


@pytest.mark.must
def test_api_search_without_auth_401(base_url, http):
    """TC-search-011: поиск без авторизации: GET /api/search и POST
    /api/search/advanced — оба HTTP 401, тело {"error": "unauthorized"};
    результатов задач в теле нет (данные не утекают)."""
    resp_get = http.get(f"{base_url}/api/search", params={"priority": "high"})
    resp_post = http.post(
        f"{base_url}/api/search/advanced", json={"query": 'priority = "high"'}
    )
    for resp in (resp_get, resp_post):
        assert resp.status_code == 401
        assert resp.json() == {"error": "unauthorized"}
        assert "results" not in resp.json()
