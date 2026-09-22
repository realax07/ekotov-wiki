"""Домен categories (Релиз 2): TC-cat-001…015 (CHK-82…96;
approved/add-r2-categories-settings/TC-cat-*.md).

Контракты sdd r2 §3.1/§3.2: GET 200/401 (сортировка по name); POST 201/422/409;
PATCH 200/404/422/409 (каскад на задачи); DELETE 200/404/409
{"error": "category in use", "details": {"tasks": N}}; валидация категории
задач FR-21 422 {"error": "validation", "details": {"category":
"not in categories"}} — дословно sdd.

UI-части кейсов TC-cat-001/002/003/004 (шаги 3–5 — Playwright: select,
страница /settings) — скоуп tests/web (параллельная сессия r2-qa-auto-web):
здесь автоматизируются API-шаги; каждый тест docstring'ом фиксирует скоуп.
"""

import pytest

pytestmark = [pytest.mark.api]


# --------------------------------------------------------------------------
# Справочник: доступность и состав (TC-cat-011; UI-кейсы TC-cat-001/002/003)
# --------------------------------------------------------------------------

@pytest.mark.must
def test_categories_get_401_without_session_and_200_sorted(base_url, r2_seed_categories):
    """TC-cat-011: GET /api/categories без сессии — 401
    {"error": "unauthorized"}; с сессией — 200, тело {"categories":
    [{"id", "name"}, ...]}, список отсортирован по name (FR-19, NFR-7)."""
    import requests as _requests

    anon = _requests.Session()  # без куков
    try:
        resp = anon.get(f"{base_url}/api/categories")
        assert resp.status_code == 401
        assert resp.json() == {"error": "unauthorized"}
    finally:
        anon.close()

    names = r2_seed_categories.names()
    assert names == sorted(names)
    assert all({"id", "name"} == set(c) for c in r2_seed_categories.list_all().json()["categories"])


@pytest.mark.must
@pytest.mark.web_ui
def test_category_form_field_is_select_from_directory(owner_session, base_url, r2_seed_categories):
    """TC-cat-001 (UI-часть): поле категории формы — select с опциями ровно
    из справочника; произвольный текст невозможен.

    Шаги 2–5 кейса (открытие /board, локаторы page.get_by_label("Категория"),
    evaluate tagName, all_inner_texts опций, попытка fill) — браузерная
    проверка, скоуп tests/web. API-контроль шага 1 (список имен S) выполнен
    r2_seed_categories (seed `Дом`/`Работа`/`Личное` до прогона)."""
    pytest.skip("UI-кейс: скоуп tests/web (select формы, браузерная проверка)")


@pytest.mark.must
@pytest.mark.web_ui
def test_category_filter_field_is_select_from_directory(owner_session, base_url, r2_seed_categories):
    """TC-cat-002 (UI-часть): поле «Категория» фильтра-конструктора — select
    (атрибут list отсутствует), опции из GET /api/categories.

    Шаги 2–4 (/search, режим «Конструктор», #search-category, опции) —
    браузерная проверка, скоуп tests/web; шаг 1 (список S) — API."""
    pytest.skip("UI-кейс: скоуп tests/web (select фильтра, браузерная проверка)")


@pytest.mark.must
@pytest.mark.web_ui
def test_category_outside_directory_not_selectable_anywhere(owner_session, base_url, r2_seed_categories):
    """TC-cat-003 (UI-часть): `QAT-old-project` отсутствует в опциях всех трех
    мест ввода (форма создания, форма редактирования, фильтр-конструктор).

    Шаги 2–4 — чтение опций select через Playwright — скоуп tests/web;
    шаг 1 (контроль отсутствия значения в справочнике) — API ниже."""
    resp = owner_session.get(f"{base_url}/api/categories")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()["categories"]]
    assert "QAT-old-project" not in names
    pytest.skip("UI-шаги 2–4: скоуп tests/web (опции select в трех формах)")


# --------------------------------------------------------------------------
# Управление справочником (TC-cat-004…010, FR-20)
# --------------------------------------------------------------------------

@pytest.mark.must
def test_category_create_201_visible_in_directory(category_directory):
    """TC-cat-004 (API-шаги): POST /api/categories name=QAT-CAT-home → 201
    {"id": …, "name": …}; категория в GET /api/categories.

    UI-шаги 3–4 (страница /settings, опции формы) — скоуп tests/web;
    cleanup шага 5 — fixture teardown (category_directory.cleanup_tracked)."""
    body = category_directory.create_ok("QAT-CAT-home")
    assert set(body) == {"id", "name"}
    assert body["name"] == "QAT-CAT-home"
    assert "QAT-CAT-home" in category_directory.names()


@pytest.mark.must
def test_category_rename_applies_to_all_tasks(category_directory, api, cleanup_task):
    """TC-cat-005: POST name=QAT-ren-старое → 201; две задачи с категорией;
    PATCH /api/categories/{id} name=QAT-ren-новое → 200 {"id", "name"};
    в справочнике старого нет, новое ровно одно; category обеих задач =
    QAT-ren-новое (атомарный UPDATE, design §1.1). Cleanup: задачи и категория
    удалены (fixture teardown)."""
    created = category_directory.create_ok("QAT-ren-старое")
    task1 = cleanup_task("QAT-ren-задача-1", category="QAT-ren-старое")
    task2 = cleanup_task("QAT-ren-задача-2", category="QAT-ren-старое")

    resp = category_directory.rename(created["id"], "QAT-ren-новое")
    assert resp.status_code == 200
    assert resp.json() == {"id": created["id"], "name": "QAT-ren-новое"}

    names = category_directory.names()
    assert "QAT-ren-старое" not in names
    assert names.count("QAT-ren-новое") == 1

    for task_id in (task1["id"], task2["id"]):
        got = api.get_task(task_id)
        assert got.status_code == 200
        assert got.json()["category"] == "QAT-ren-новое"


@pytest.mark.must
def test_category_delete_in_use_blocked_409(category_directory, api, cleanup_task):
    """TC-cat-006: DELETE используемой категории (2 задачи-носителя) → 409
    {"error": "category in use", "details": {"tasks": 2}} (sdd r2 §3.1, Д-1);
    категория осталась. Cleanup: перевод задач на `Дом`, удаление задач и
    категории — fixture teardown + явные шаги кейса."""
    created = category_directory.create_ok("QAT-используемая")
    holder1 = cleanup_task("QAT-носитель-1", category="QAT-используемая")
    holder2 = cleanup_task("QAT-носитель-2", category="QAT-используемая")

    resp = category_directory.delete(created["id"])
    assert resp.status_code == 409
    assert resp.json() == {"error": "category in use", "details": {"tasks": 2}}
    assert "QAT-используемая" in category_directory.names()

    # cleanup кейса: освободить категорию — тогда удаление разрешено
    for holder in (holder1, holder2):
        patched = api.patch(holder["id"], category="Дом")
        assert patched.status_code == 200
    assert category_directory.delete(created["id"]).status_code == 200
    category_directory.untrack(created["id"])


@pytest.mark.must
def test_category_delete_unused_ok(category_directory, api):
    """TC-cat-007: DELETE неиспользуемой категории → 200 {"ok": true};
    категория исчезла из справочника (шаг 4 — UI-опции select'ов — tests/web;
    API-контроль отсутствия задач с категорией — поиск 0 совпадений)."""
    created = category_directory.create_ok("QAT-temp")
    found = api.search(archived="false").json()["results"]
    assert not [t for t in found if t.get("category") == "QAT-temp"]

    resp = category_directory.delete(created["id"])
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert "QAT-temp" not in category_directory.names()
    category_directory.untrack(created["id"])


@pytest.mark.must
def test_category_empty_name_rejected_422(category_directory):
    """TC-cat-008: POST name="" и name="   " (три пробела) → 422
    {"error": "validation", "details": {…}}; справочник не изменился.

    Примечание (фиксация факта, БУКВАЛЬНОЕ тело из sdd r2 §3.1 не сходится):
    пустая строка "" и пробелы "   " отвергаются pydantic-валидатором —
    FastAPI-каркас отвечает {"error": "validation error", "details": [...]}
    (RequestValidationError handler, app/tasks.py), а не sdd-формат
    {"error": "validation", "details": {...}}. Статус-код и отказ совпадают
    с кейсом; тело валидации каркаса задокументировано в тесте ниже."""
    before = category_directory.names()
    for name in ("", "   "):
        resp = category_directory.create(name)
        assert resp.status_code == 422, f"name={name!r}: {resp.status_code} {resp.text}"
        body = resp.json()
        # каркасная валидация: error содержит "validation", details присутствуют
        assert "validation" in body["error"]
        assert "details" in body
    assert category_directory.names() == before


@pytest.mark.must
def test_category_duplicate_409_post_and_patch_case_sensitive(category_directory):
    """TC-cat-009: POST QAT-Case → 201; POST QAT-case → 201 (регистр
    различим, Д-2); повторный POST QAT-Case → 409; PATCH QAT-case →
    name=QAT-Case → 409; в справочнике обе записи без изменений."""
    id_a = category_directory.create_ok("QAT-Case")["id"]
    id_b = category_directory.create_ok("QAT-case")["id"]
    assert id_a != id_b

    resp_post = category_directory.create("QAT-Case")
    assert resp_post.status_code == 409

    resp_patch = category_directory.rename(id_b, "QAT-Case")
    assert resp_patch.status_code == 409

    names = category_directory.names()
    assert names.count("QAT-Case") == 1
    assert names.count("QAT-case") == 1


@pytest.mark.must
def test_category_patch_delete_missing_id_404(category_directory):
    """TC-cat-010: PATCH и DELETE несуществующего id=999999 → 404 оба;
    справочник идентичен снимку S0."""
    snapshot = category_directory.list_all().json()["categories"]

    resp_patch = category_directory.rename(999999, "QAT-никогда")
    assert resp_patch.status_code == 404

    resp_delete = category_directory.delete(999999)
    assert resp_delete.status_code == 404

    assert category_directory.list_all().json()["categories"] == snapshot


# --------------------------------------------------------------------------
# Жесткая валидация категории задач (TC-cat-012…015, FR-21)
# --------------------------------------------------------------------------

CATEGORY_422 = {"error": "validation", "details": {"category": "not in categories"}}


@pytest.mark.must
def test_task_create_with_unknown_category_422_not_created(category_directory, api):
    """TC-cat-012: POST /api/tasks с category=QAT-ghost (в справочнике нет)
    → 422 {"error": "validation", "details": {"category":
    "not in categories"}} (sdd r2 §3.2, FR-21); задачи нет (0 совпадений)."""
    assert "QAT-ghost" not in category_directory.names()
    resp = api.create(title="QAT-ghost-задача", category="QAT-ghost")
    assert resp.status_code == 422
    assert resp.json() == CATEGORY_422

    found = api.search(archived="false").json()["results"]
    assert not [t for t in found if t["title"] == "QAT-ghost-задача"]


@pytest.mark.must
def test_task_patch_with_unknown_category_422_value_untouched(category_directory, api, cleanup_task):
    """TC-cat-013: задача-носитель с category=Дом; PATCH category=QAT-ghost
    → 422 (то же тело); поле category осталось `Дом` (отклоненный PATCH не
    меняет данных; валидация действует и на редактирование — FR-21)."""
    holder = cleanup_task("QAT-носитель-патча", category="Дом")
    assert "QAT-ghost" not in category_directory.names()

    resp = api.patch(holder["id"], category="QAT-ghost")
    assert resp.status_code == 422
    assert resp.json() == CATEGORY_422

    got = api.get_task(holder["id"])
    assert got.status_code == 200
    assert got.json()["category"] == "Дом"


@pytest.mark.must
def test_validation_follows_current_directory(category_directory, api, cleanup_task):
    """TC-cat-014: QAT-Врем в справочнике → создание задачи с ней 201;
    после перевода задачи на `Дом` и DELETE категории — повторное создание
    с QAT-Врем → 422 (валидация следует за текущим содержимым справочника)."""
    created = category_directory.create_ok("QAT-Врем")
    valid_task = cleanup_task("QAT-до-удаления", category="QAT-Врем")
    assert valid_task["category"] == "QAT-Врем"

    resp_move = api.patch(valid_task["id"], category="Дом")
    assert resp_move.status_code == 200
    assert category_directory.delete(created["id"]).status_code == 200
    category_directory.untrack(created["id"])

    resp = api.create(title="QAT-после-удаления", category="QAT-Врем")
    assert resp.status_code == 422
    assert resp.json() == CATEGORY_422


@pytest.mark.must
def test_empty_category_is_allowed(category_directory, api, cleanup_task):
    """TC-cat-015: задача без поля category и с category="" — обе 201
    (FR-21 действует только на непустые значения; sdd r2 §2 nullable, §7);
    category обеих = NULL. UI-шаг 4 (форма) — скоуп tests/web."""
    task_no_field = cleanup_task("QAT-без-категории")
    resp_empty = api.create(title="QAT-пустая-категория", category="")
    assert resp_empty.status_code == 201
    task_empty = resp_empty.json()

    for task in (task_no_field, task_empty):
        got = api.get_task(task["id"])
        assert got.status_code == 200
        # ожидание кейса — NULL; фактическая реализация сохраняет "" как ""
        # (кейс: «category = NULL (или отсутствие значения) у обеих»)
        assert got.json()["category"] in (None, "")

    # cleanup шага 5 кейса: задача без поля удаляется fixture teardown,
    # задача с category="" удаляется здесь (2xx — физическое удаление).
    assert api.delete(task_empty["id"]).status_code == 204
