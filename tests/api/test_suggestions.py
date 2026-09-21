"""Подсказки фильтра: GET /api/suggestions (Релиз 1, задача 1.3 / P4).

Контракт (уточнение Заказчика): {"suggestions": [...]} — множество (set:
без дублей, отсортировано) из ОБЪЕДИНЕНИЯ тегов и категорий существующих
задач (tags ∪ categories); только уже заведенные значения. Авторизация —
middleware: без сессии 401 {"error": "unauthorized"} (кейс
TC-API-SUGG-002, требование middleware-401, sdd §3).

TC-ID: TC-API-SUGG-001, TC-API-SUGG-002, TC-API-SUGG-003, TC-API-SUGG-004,
TC-API-SUGG-005. Формат: 1 кейс = 1 тест (contract 6);
трассировка — ТЗ Релиза 1 задача 1.3 (PRODUCT_BACKLOG.md, план релиза),
домен search (FR-10/FR-11); самостоятельных CHK от qa-контура на R1.3
еще нет (QA-цикл 1.5 впереди по плану релиза) — тесты написаны по ТЗ
задачи и сценарию продукта, не по test-model/approved (в отчете ПМ).
"""

import pytest

pytestmark = [pytest.mark.api]


@pytest.fixture
def sugg_fixtures(api):
    """Фикстура данных: задача с тегом и категорией (уникальный префикс —
    изоляция от чужих данных на общей БД стенда)."""
    task = api.create_ok(
        "QAT-SUGG-источник", category="QAT-Категория-1", tags=["QAT-Тег-1"]
    )
    return task


@pytest.mark.must
def test_suggestions_200_and_format(base_url, owner_session, sugg_fixtures):
    """TC-API-SUGG-001: GET /api/suggestions с сессией — 200, JSON-объект
    с единственным ключом "suggestions", значение — список строк; созданные
    в фикстуре категория и тег в списке присутствуют."""
    resp = owner_session.get(f"{base_url}/api/suggestions")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"suggestions"}
    assert isinstance(body["suggestions"], list)
    assert all(isinstance(s, str) for s in body["suggestions"])
    assert "QAT-Категория-1" in body["suggestions"]
    assert "QAT-Тег-1" in body["suggestions"]


@pytest.mark.must
def test_suggestions_unauthorized(base_url):
    """TC-API-SUGG-002 (негативный): GET /api/suggestions без сессии — 401
    {"error": "unauthorized"} (единый текст middleware, sdd §3)."""
    import requests

    resp = requests.get(f"{base_url}/api/suggestions")
    assert resp.status_code == 401
    assert resp.json() == {"error": "unauthorized"}


@pytest.mark.must
def test_suggestions_unique(api, base_url, owner_session):
    """TC-API-SUGG-003 (set-семантика): пересечение тега и категории —
    значение входит в ответ ОДИН раз; дублей в списке нет."""
    api.create_ok(
        "QAT-SUGG-пересечение",
        category="QAT-Общее",  # категория = тегу: пересечение
        tags=["QAT-Общее"],
    )
    resp = owner_session.get(f"{base_url}/api/suggestions")
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert len(suggestions) == len(set(suggestions)), "есть дубли"
    assert suggestions.count("QAT-Общее") == 1


@pytest.mark.must
def test_suggestions_sorted(api, base_url, owner_session):
    """TC-API-SUGG-004 (сортировка): ответ отсортирован по возрастанию."""
    api.create_ok(
        "QAT-SUGG-сортировка",
        category="QAT-якорь",  # буква «я» — конец сортировки
        tags=["QAT-Альфа"],
    )
    resp = owner_session.get(f"{base_url}/api/suggestions")
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert suggestions == sorted(suggestions)
    idx_alpha = suggestions.index("QAT-Альфа")
    idx_yakor = suggestions.index("QAT-якорь")
    assert idx_alpha < idx_yakor


@pytest.mark.must
def test_suggestions_union_of_tags_and_categories(api, base_url, owner_session):
    """TC-API-SUGG-005 (объединение): suggestion-list содержит И теги,
    И категории существующих задач; значения другой задачи не теряются."""
    api.create_ok("QAT-SUGG-А", category="QAT-Кат-А", tags=["QAT-Тег-А"])
    api.create_ok("QAT-SUGG-Б", category="QAT-Кат-Б", tags=["QAT-Тег-Б"])
    resp = owner_session.get(f"{base_url}/api/suggestions")
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    for value in ("QAT-Кат-А", "QAT-Тег-А", "QAT-Кат-Б", "QAT-Тег-Б"):
        assert value in suggestions, f"{value} отсутствует в множестве"
