"""Домен fastline MODIFIED (Релиз 2): TC-fast2-001…012 (CHK-127…138;
approved/add-r2-categories-settings/TC-fast2-*.md).

Инвариант FR-27 (ОГР-10): `is_fast ⇒ priority='high'`; sdd r2 §3.2 —
явный priority != "high" при is_fast=true → 422
{"error": "validation", "details": {"priority": "fast requires high"}} (дословно);
is_fast=true БЕЗ priority → сервер ставит priority="high".
Инвариант fast ≤1 активной (409 {"error": "fast line occupied"}) — без изменений.

UI-кейсы TC-fast2-003 (блокировка поля приоритета) — скоуп tests/web;
TC-fast2-007 автоматизируется как прямой серверный запрос (суть кейса —
«обход клиентской блокировки не меняет исход»: валидация серверная).
Миграционный TC-fast2-010 — прогон скрипта приведения на временной БД
(fixture migr_temp_db, как TC-migr-*), метка candidate-archive.
"""

import sqlite3

import pytest

pytestmark = [pytest.mark.api]

# Тело 422 priority-lock — дословно sdd r2 §3.2.
FAST_REQUIRES_HIGH_422 = {
    "error": "validation",
    "details": {"priority": "fast requires high"},
}
FAST_LINE_OCCUPIED = {"error": "fast line occupied"}


def _no_active_fast(api) -> bool:
    board = api.board().json()
    return not [
        t
        for column in board["columns"].values()
        for t in column
        if t["is_fast"] and t["status"] in ("todo", "in_progress")
    ]


@pytest.mark.must
def test_fast_create_priority_auto_high(api, r2_fast_line):
    """TC-fast2-001: создание fast без priority → 201, is_fast=true,
    status="todo", priority="high" (автоподстановка сервера, sdd r2 §3.2);
    задача на fast line доски. Cleanup: удаление задачи fixture teardown."""
    assert _no_active_fast(api)
    resp = api.create(title="QAT-фаст-high", is_fast=True)
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_fast"] is True
    assert body["status"] == "todo"
    assert body["priority"] == "high"

    board = api.board().json()["columns"]
    on_line = [t["title"] for c in ("todo", "in_progress") for t in board[c] if t["is_fast"]]
    assert "QAT-фаст-high" in on_line


@pytest.mark.must
def test_regular_task_keeps_chosen_priority(api):
    """TC-fast2-002: обычная задача priority=medium → 201, is_fast=false,
    priority="medium" (выбранный сохранен); карточка в «Ожидает», не на
    fast line; автоназначения нет."""
    resp = api.create(title="QAT-обычная-med", priority="medium")
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_fast"] is False
    assert body["priority"] == "medium"

    columns = api.board().json()["columns"]
    assert "QAT-обычная-med" in [t["title"] for t in columns["todo"]]
    assert "QAT-обычная-med" not in [
        t["title"] for c in columns.values() for t in c if t["is_fast"]
    ]


@pytest.mark.must
@pytest.mark.web_ui
def test_fast_priority_field_locked_in_form(owner_session, r2_seed_categories):
    """TC-fast2-003 (UI): поле «Приоритет» в форме fast-задачи показывает
    high и заблокировано (disabled); select_option("low") невозможен.

    Шаги 1–5 кейса — Playwright (page.get_by_label("fast line").check(),
    evaluate el.value + '|' + el.disabled) — браузерная проверка,
    скоуп tests/web (параллельная сессия r2-qa-auto-web)."""
    pytest.skip("UI-кейс: скоуп tests/web (блокировка поля в форме, браузерная проверка)")


@pytest.mark.must
def test_fast_explicit_null_priority_422(api, r2_fast_line):
    """TC-fast2-004: POST is_fast=true с явным priority=null → 422
    {"error": "validation", "details": {"priority": "fast requires high"}}
    (sdd r2 §3.2: явный null — отдельный случай от отсутствия поля, CHK-130);
    fast-задача не создана (0 совпадений).

    BUG-002 ИСПРАВЛЕН (backend/app/tasks.py: _explicit_null_priority_422,
    различение null/отсутствие через model_fields_set): xfail(strict) снят
    2026-09-22, тест зеленый (история дефекта — test-model/bugs/BUG-002)."""
    assert _no_active_fast(api)
    resp = api.session.post(
        f"{api.base_url}/api/tasks",
        json={"title": "QAT-фаст-null", "is_fast": True, "priority": None},
    )
    assert resp.status_code == 422
    assert resp.json() == FAST_REQUIRES_HIGH_422

    found = api.search(archived="false").json()["results"]
    assert not [t for t in found if t["title"] == "QAT-фаст-null"]


@pytest.mark.must
def test_fast_priority_low_422(api, r2_fast_line):
    """TC-fast2-005: POST is_fast=true priority="low" → 422
    details.priority="fast requires high"; задача не создана (ОГР-10:
    обход через API невозможен)."""
    assert _no_active_fast(api)
    resp = api.create(title="QAT-фаст-low", is_fast=True, priority="low")
    assert resp.status_code == 422
    assert resp.json() == FAST_REQUIRES_HIGH_422

    found = api.search(archived="false").json()["results"]
    assert not [t for t in found if t["title"] == "QAT-фаст-low"]


@pytest.mark.must
def test_fast_priority_medium_422(api, r2_fast_line):
    """TC-fast2-006: POST is_fast=true priority="medium" → 422
    details.priority="fast requires high"; задача не создана."""
    assert _no_active_fast(api)
    resp = api.create(title="QAT-фаст-medium", is_fast=True, priority="medium")
    assert resp.status_code == 422
    assert resp.json() == FAST_REQUIRES_HIGH_422

    found = api.search(archived="false").json()["results"]
    assert not [t for t in found if t["title"] == "QAT-фаст-medium"]


@pytest.mark.must
def test_forged_client_request_rejected_by_server(api, r2_fast_line):
    """TC-fast2-007 (API-суть): подделанный клиентский запрос (минуя
    disabled-поле формы) с priority="low" отклоняется серверной валидацией —
    422 details.priority="fast requires high"; задачи нет. Кейс выполняет
    запрос из консоли страницы (page.evaluate fetch) — та же серверная
    проверка; здесь — прямой запрос с payload кейса (QAT-фаст-подделка)."""
    assert _no_active_fast(api)
    resp = api.create(title="QAT-фаст-подделка", is_fast=True, priority="low")
    assert resp.status_code == 422
    assert resp.json() == FAST_REQUIRES_HIGH_422

    found = api.search(archived="false").json()["results"]
    assert not [t for t in found if t["title"] == "QAT-фаст-подделка"]


@pytest.mark.must
def test_fast_without_priority_key_gets_high(api, r2_fast_line):
    """TC-fast2-008: POST is_fast=true БЕЗ ключа priority → 201 с
    priority="high" (не null!) — автоподстановка (sdd r2 §3.2); контраст
    с CHK-130 (явный null → 422, TC-fast2-004)."""
    assert _no_active_fast(api)
    resp = api.create(title="QAT-фаст-безприор", is_fast=True)
    assert resp.status_code == 201
    body = resp.json()
    assert body["priority"] == "high"
    assert body["is_fast"] is True


@pytest.mark.must
def test_regular_task_any_priority_unrestricted(api, cleanup_task):
    """TC-fast2-009: обычная задача priority="low" → 201; GET →
    priority="low", is_fast=false — ограничение только для fast."""
    task = cleanup_task("QAT-обычная-low", priority="low")
    got = api.get_task(task["id"])
    assert got.status_code == 200
    body = got.json()
    assert body["priority"] == "low"
    assert body["is_fast"] is False


@pytest.mark.must
def test_migration_normalizes_fast_priority(migr_temp_db):
    """TC-fast2-010 (candidate-archive): fast-задача с priority='low'
    (легально до внедрения) после миграции приведена к priority='high'
    (sdd r2 §5); SQL-контроль: COUNT(is_fast=1 AND priority!='high') == 0;
    инвариант выполняется для всех fast-задач копии."""
    db_path, run_migration, execute = migr_temp_db
    execute(
        "INSERT INTO tasks (title, category, status, is_fast, priority, created_at, updated_at) "
        "VALUES ('QAT-фаст-нарушитель',NULL,'todo',1,'low',datetime('now'),datetime('now'))"
    )
    bad_before = execute(
        "SELECT COUNT(*) FROM tasks WHERE is_fast = 1 AND priority != 'high'"
    )[0][0]
    assert bad_before >= 1, "в снимке «до» должен быть нарушитель инварианта fast"

    result = run_migration()
    assert result.returncode == 0, f"миграция упала: {result.stdout} {result.stderr}"

    conn = sqlite3.connect(db_path)
    try:
        bad_after = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE is_fast = 1 AND priority != 'high'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad_after == 0


@pytest.mark.must
def test_patch_cases_regular_high_ok_fast_medium_rejected(api, r2_fast_line, cleanup_task):
    """TC-fast2-011: PATCH обычной priority="high" → 200, is_fast=false;
    PATCH обычной is_fast=true — is_fast не меняется (ОГР-5: смена is_fast
    вне дельты; фактический код зафиксирован, главное — is_fast=false после);
    PATCH fast priority="medium" → 422 details.priority="fast requires high"
    (инвариант «после PATCH priority fast = high» обязателен)."""
    regular = cleanup_task("QAT-патч-обычная", priority="medium")

    fast = api.create_ok("QAT-патч-фаст", is_fast=True)

    # шаг 2: обычная → high легальна
    resp_high = api.patch(regular["id"], priority="high")
    assert resp_high.status_code == 200
    got = api.get_task(regular["id"]).json()
    assert got["priority"] == "high"
    assert got["is_fast"] is False

    # шаг 3: PATCH не назначает is_fast (код ответа не фиксируется кейсом —
    # ожидаемо 200 с игнором или 422; главное — is_fast=false после)
    api.patch(regular["id"], is_fast=True)
    got_after = api.get_task(regular["id"]).json()
    assert got_after["is_fast"] is False  # инвариант ОГР-5 независимо от кода ответа

    # шаг 4: fast PATCH на не-high отклоняется
    resp_medium = api.patch(fast["id"], priority="medium")
    assert resp_medium.status_code == 422
    assert resp_medium.json() == FAST_REQUIRES_HIGH_422
    got_fast = api.get_task(fast["id"]).json()
    assert got_fast["priority"] == "high"


@pytest.mark.must
def test_second_fast_with_invalid_priority_order_fixed(api, r2_fast_line):
    """TC-fast2-012 (CHK-138): вторая fast с невалидным priority="low" при
    занятой линии — порядок проверок ЗАФИКСИРОВАН контрактом: priority-lock
    (422) проверяется ДО инварианта fast line (design.md §4: валидации
    категории и priority — до любых записей и до проверки занятости линии;
    create_task в app/tasks.py). Ожидаемый код EXPECTED=422 дословно
    контракта; задача не создана ни при каком порядке. (UI-кейсы
    TC-UI-011/TC-UI-018 — детерминизм для tests/web.)"""
    # подготовка: активная fast (линия занята)
    first = api.create_ok("QAT-фаст-первая", is_fast=True)
    try:
        resp = api.create(title="QAT-фаст-вторая-невалид", is_fast=True, priority="low")
        assert resp.status_code == 422, (
            f"ACTUAL={resp.status_code} ≠ EXPECTED=422 (контракт design.md §4): "
            f"{resp.text} — расхождение sdd↔реализация, эскалация ПМ"
        )
        assert resp.json() == FAST_REQUIRES_HIGH_422
        found = api.search(archived="false").json()["results"]
        assert not [t for t in found if t["title"] == "QAT-фаст-вторая-невалид"]
    finally:
        api.delete(first["id"])
