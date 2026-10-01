"""Параметр kind в GET /api/suggestions (Релиз 6, задача 1.1, add-r6-task-form-ux).

Контракт (Д-14, дельта suggestions «Параметр kind фильтра подсказок»;
трассировка FR-57, ОГР-26, ОВ-1, СЦ-1/СЦ-10):
- БЕЗ параметра — прежний UNION тегов и категорий, дословно прежний
  контракт (обратная совместимость ОГР-26; TC-API-SUGG-001/004 из
  test_suggestions.py покрывают его постоянно и остаются green);
- kind=tags — только уникальные теги существующих задач (sorted, дедуп
  как сейчас; категории не участвуют — СЦ-1);
- kind=categories — только категории существующих задач;
- неизвестный kind — 422, явный отказ, не тихий UNION (ОГР-26, СЦ-10);
- 401 без сессии при любом kind (преемственность FR-18/NFR-7).

TC-ID: TC-sugg-r6-001…005. Формат: 1 кейс = 1 тест (contract 6).
Источники тестов: сценарии дельты openspec/changes/add-r6-task-form-ux/
specs/suggestions/spec.md (approved qa-кейсов на r6 еще нет — QA-цикл 5.1
пакета впереди; в отчете ПМ).
"""

import pytest
import requests

pytestmark = [pytest.mark.api]


@pytest.fixture
def r6_sugg_fixtures(api, r2_seed_categories):
    """Данные СЦ-1: задача с тегом «QAT-R6Тег» и категорией «QAT-R6Кат»
    (справочник R2 — 422 not in categories, cleanup фикстуры r2)."""
    category_id = r2_seed_categories.create_ok("QAT-R6Кат")["id"]
    task = api.create_ok(
        "QAT-SUGG-R6-источник", category="QAT-R6Кат", tags=["QAT-R6Тег"]
    )
    try:
        yield task
    finally:
        api.patch(task["id"], category="Дом")
        api.delete(task["id"])
        r2_seed_categories.untrack(category_id)
        assert r2_seed_categories.delete(category_id).status_code == 200


@pytest.mark.must
# regression: keep — без параметра прежний UNION (ОГР-26, СЦ-10):
# контракт поиска дословно сохранен.
def test_suggestions_r6_no_param_union(api, base_url, owner_session, r6_sugg_fixtures):
    """TC-sugg-r6-001: GET /api/suggestions без параметра — 200, ответ
    содержит И тег, И категорию фикстуры (прежний UNION; формат —
    единственный ключ «suggestions» — как в TC-API-SUGG-001)."""
    resp = owner_session.get(f"{base_url}/api/suggestions")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"suggestions"}
    suggestions = body["suggestions"]
    assert suggestions == sorted(suggestions)
    assert "QAT-R6Тег" in suggestions
    assert "QAT-R6Кат" in suggestions


@pytest.mark.must
# regression: keep — kind=tags, источник комбобокса (FR-57, ОВ-1, СЦ-1).
def test_suggestions_r6_kind_tags_only(api, base_url, owner_session, r6_sugg_fixtures):
    """TC-sugg-r6-002: ?kind=tags — 200, только теги: «QAT-R6Тег» есть,
    категория «QAT-R6Кат» в ответе отсутствует; sorted, без дублей."""
    resp = owner_session.get(f"{base_url}/api/suggestions", params={"kind": "tags"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"suggestions"}
    suggestions = body["suggestions"]
    assert suggestions == sorted(suggestions)
    assert len(suggestions) == len(set(suggestions))
    assert "QAT-R6Тег" in suggestions
    assert "QAT-R6Кат" not in suggestions


@pytest.mark.must
# regression: keep — kind=categories, симметричная ветка фильтра (Д-14).
def test_suggestions_r6_kind_categories_only(api, base_url, owner_session, r6_sugg_fixtures):
    """TC-sugg-r6-003: ?kind=categories — 200, только категории:
    «QAT-R6Кат» есть, тег «QAT-R6Тег» в ответе отсутствует."""
    resp = owner_session.get(
        f"{base_url}/api/suggestions", params={"kind": "categories"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"suggestions"}
    suggestions = body["suggestions"]
    assert suggestions == sorted(suggestions)
    assert "QAT-R6Кат" in suggestions
    assert "QAT-R6Тег" not in suggestions


@pytest.mark.must
# regression: keep — негатив 422 на неизвестный kind (ОГР-26, СЦ-10):
# явный отказ, прежнее множество не возвращается.
def test_suggestions_r6_unknown_kind_422(owner_session, base_url):
    """TC-sugg-r6-004 (негатив): ?kind=users (и иное неизвестное значение)
    — 422; тела с множеством подсказок нет."""
    for bad_kind in ("users", "прочее"):
        resp = owner_session.get(
            f"{base_url}/api/suggestions", params={"kind": bad_kind}
        )
        assert resp.status_code == 422, (bad_kind, resp.status_code, resp.text)


@pytest.mark.must
# regression: keep — 401 без сессии при любом kind (преемственность FR-18).
def test_suggestions_r6_unauthorized_with_and_without_kind(base_url):
    """TC-sugg-r6-005 (негатив): без сессии — 401 {\"error\":
    \"unauthorized\"} и без параметра, и при kind=tags/categories."""
    for params in ({}, {"kind": "tags"}, {"kind": "categories"}):
        resp = requests.get(f"{base_url}/api/suggestions", params=params)
        assert resp.status_code == 401, (params, resp.status_code)
        assert resp.json() == {"error": "unauthorized"}
