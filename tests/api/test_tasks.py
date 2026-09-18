"""Домен tasks: TC-tasks-001…016 (CHK-41…56; approved/add-kanban-core/tasks-01.md).

Контракты sdd §3.2: POST 201/422/409; GET 200/404; PATCH 200/404/422;
DELETE 204/404; move 200/404/422. Комментарии: POST 201 (sdd §3.2).
"""

import pytest

pytestmark = [pytest.mark.api]


# --------------------------------------------------------------------------
# Создание задачи (CHK-41…44)
# --------------------------------------------------------------------------

@pytest.mark.must
def test_create_task_title_only_defaults(api, cleanup_task):
    """TC-tasks-001: создание только с названием: title сохранен; status="todo",
    description=NULL, priority=NULL, category=NULL, due_date=NULL, tags=[],
    is_fast=false; карточка в столбце «Ожидает»."""
    task = cleanup_task("QAT-Только-название")
    resp = api.get_task(task["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "QAT-Только-название"
    assert body["status"] == "todo"
    assert body["description"] is None
    assert body["priority"] is None
    assert body["category"] is None
    assert body["due_date"] is None
    assert body["tags"] == []
    assert body["is_fast"] is False
    columns = api.board().json()["columns"]
    assert "QAT-Только-название" in [t["title"] for t in columns["todo"]]


@pytest.mark.must
def test_create_task_with_all_attributes(api, cleanup_task):
    """TC-tasks-002: все признаки сохранены и равны введенным: description,
    priority=high, category=Дом, due_date=2026-09-30, tags содержит дом и
    срочно (без дублей), title."""
    task = cleanup_task(
        "QAT-Полная",
        description="Проверка признаков r1",
        priority="high",
        category="Дом",
        due_date="2026-09-30",
        tags=["дом", "срочно"],
    )
    resp = api.get_task(task["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "QAT-Полная"
    assert body["description"] == "Проверка признаков r1"
    assert body["priority"] == "high"
    assert body["category"] == "Дом"
    assert body["due_date"] == "2026-09-30"
    assert body["tags"] == ["дом", "срочно"]


@pytest.mark.must
def test_create_task_without_title_422(api):
    """TC-tasks-003 (API-часть): создание без названия — HTTP 422, тело
    {"error": …, "details": {…}} (валидация); задача не создана (0 совпадений)."""
    resp = api.create(description="без названия")
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert "details" in body

    found = api.search(archived="all").json()["results"]
    assert not [t for t in found if t.get("description") == "без названия"]


@pytest.mark.must
def test_title_boundaries_one_char_ok_spaces_documented(api):
    """TC-tasks-004: границы названия: 1 символ «Я» — 201, задача создана;
    название из 3 пробелов — поведение НЕ предопределено спекой (DS-2):
    фиксируем фактический код; любое поведение, кроме 5xx, не дефект кейса."""
    resp_one = api.create(title="Я")
    assert resp_one.status_code == 201
    api.delete(resp_one.json()["id"])

    resp_spaces = api.create(title="   ")
    assert resp_spaces.status_code < 500, (
        f"DS-2, зафиксировано: пробельный title → {resp_spaces.status_code} {resp_spaces.text}"
    )
    if resp_spaces.status_code // 100 == 2:
        created = resp_spaces.json()
        api.delete(created["id"])  # факт зафиксирован, хвост убран


# --------------------------------------------------------------------------
# Признаки задачи (CHK-45…48)
# --------------------------------------------------------------------------

@pytest.mark.must
def test_attributes_stored_and_readable(api, cleanup_task):
    """TC-tasks-005 (API-часть): признаки задачи видны в карточке: все
    заполненные признаки читаются из GET /api/tasks/{id} с введенными
    значениями. UI-часть (отображение карточки) — tests/web."""
    task = cleanup_task(
        "QAT-Полная-005",
        description="Проверка признаков r1",
        priority="high",
        category="Дом",
        due_date="2026-09-30",
        tags=["дом", "срочно"],
    )
    resp = api.get_task(task["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "Проверка признаков r1"
    assert body["priority"] == "high"
    assert body["category"] == "Дом"
    assert body["due_date"] == "2026-09-30"
    assert set(body["tags"]) == {"дом", "срочно"}
    # комментарии — раздел присутствует (список читается отдельно, sdd §3.2)
    comments = api.comments(task["id"])
    assert comments.status_code == 200
    assert comments.json() == {"comments": []}


@pytest.mark.must
def test_edit_attributes_saved(api, cleanup_task):
    """TC-tasks-006: редактирование признаков с сохранением: priority low→medium,
    category Работа→Личное, срок →2026-10-05, тег работа→дом; старые значения
    не вернулись."""
    task = cleanup_task(
        "QAT-Признаки-до", priority="low", category="Работа", tags=["работа"]
    )
    resp = api.patch(
        task["id"],
        priority="medium",
        category="Личное",
        due_date="2026-10-05",
        tags=["дом"],
    )
    assert resp.status_code == 200

    after = api.get_task(task["id"]).json()
    assert after["priority"] == "medium"
    assert after["category"] == "Личное"
    assert after["due_date"] == "2026-10-05"
    assert after["tags"] == ["дом"]  # без «работа»


@pytest.mark.must
def test_comment_persists(api, cleanup_task):
    """TC-tasks-007: комментарий сохраняется: в API присутствует с телом без
    искажений и заполненными author_id, created_at (повторное чтение)."""
    task = cleanup_task("QAT-С-комментарием")
    resp_add = api.add_comment(task["id"], "Первый комментарий к задаче")
    assert resp_add.status_code == 201

    resp = api.comments(task["id"])
    assert resp.status_code == 200
    comments = resp.json()["comments"]
    assert len(comments) == 1
    comment = comments[0]
    assert comment["body"] == "Первый комментарий к задаче"
    assert comment["author_id"] is not None
    assert comment["created_at"]


@pytest.mark.must
def test_bare_task_card_empty_fields(api, cleanup_task):
    """TC-tasks-008 (API-часть): карточка без признаков и комментариев:
    description=NULL, priority=NULL, category=NULL, due_date=NULL, tags=[],
    comments=[]; HTTP 200. UI-часть — tests/web."""
    task = cleanup_task("QAT-Голая")
    resp = api.get_task(task["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] is None
    assert body["priority"] is None
    assert body["category"] is None
    assert body["due_date"] is None
    assert body["tags"] == []

    comments = api.comments(task["id"])
    assert comments.status_code == 200
    assert comments.json() == {"comments": []}


# --------------------------------------------------------------------------
# Редактирование / удаление (CHK-49…52)
# --------------------------------------------------------------------------

@pytest.mark.must
def test_rename_task(api, cleanup_task):
    """TC-tasks-009: переименование: title="Новое-имя", updated_at обновился;
    задачи «Старое-имя» нет.

    updated_at в Task-схему API не входит (sdd §3.2 — ровно 11 полей), поэтому
    момент обновления проверяется прямым чтением БД; без EKOTOV_WIKI_DB_PATH —
    проверка updated_at пропускается (title-часть ассертов выполняется всегда)."""
    import os

    task = cleanup_task("QAT-Старое-имя")
    resp = api.patch(task["id"], title="QAT-Новое-имя")
    assert resp.status_code == 200
    after = api.get_task(task["id"]).json()
    assert after["title"] == "QAT-Новое-имя"

    db_path = os.environ.get("EKOTOV_WIKI_DB_PATH")
    if db_path:
        from conftest import db_select_one

        row = db_select_one(
            db_path, "SELECT updated_at, created_at FROM tasks WHERE id = ?",
            (task["id"],),
        )
        assert row[0] > row[1]  # updated_at обновился относительно создания

    found = api.search(archived="all").json()["results"]
    assert "QAT-Старое-имя" not in [t["title"] for t in found]


@pytest.mark.must
def test_patch_delete_missing_and_double_delete(api, unique_title):
    """TC-tasks-010: PATCH несуществующего id — 404 (не 5xx), тело с error;
    повторное DELETE — 404 либо идемпотентный 2xx (DS-3), но НЕ 5xx и задача
    «не воскресла» (в поиске archived=all ее нет)."""
    resp_patch = api.patch(999999, title="x")
    assert resp_patch.status_code == 404
    assert "error" in resp_patch.json()

    task = api.create_ok(f"{unique_title}-Удаляема-дважды")
    first = api.delete(task["id"])
    assert first.status_code // 100 == 2  # 204

    second = api.delete(task["id"])
    assert second.status_code == 404 or second.status_code // 100 == 2, (
        f"DS-3, зафиксировано: повторный DELETE → {second.status_code}"
    )
    found = api.search(archived="all").json()["results"]
    assert f"{unique_title}-Удаляема-дважды" not in [t["title"] for t in found]


@pytest.mark.must
def test_delete_existing_task(api, cleanup_task, unique_title):
    """TC-tasks-011 (API-часть): удаление существующей задачи: исчезла с доски,
    в результатах поиска отсутствует, GET /api/tasks/{id} — 404. Контрольная
    задача с тегом findme не затронута. UI-часть (диалог подтверждения) — tests/web."""
    task = cleanup_task("QAT-К-удалению")
    marker = cleanup_task("QAT-Маркер-поиска", tags=["findme"])

    resp_del = api.delete(task["id"])
    assert resp_del.status_code == 204

    columns = api.board().json()["columns"]
    assert "QAT-К-удалению" not in [
        t["title"] for tasks in columns.values() for t in tasks
    ]
    found = api.search(archived="all").json()["results"]
    assert "QAT-К-удалению" not in [t["title"] for t in found]

    resp_get = api.get_task(task["id"])
    assert resp_get.status_code == 404

    # контрольная не затронута
    resp_marker = api.get_task(marker["id"])
    assert resp_marker.status_code == 200
    assert resp_marker.json()["tags"] == ["findme"]

    # кейс оставляет DELETED_ID для TC-tasks-012 — тот создает свою пару
    del task  # изоляция: TC-tasks-012 самодостаточен


@pytest.mark.must
def test_deleted_task_inaccessible_everywhere(api, cleanup_task, unique_title):
    """TC-tasks-012: после удаления: GET по id — 404 (не 5xx, DS-3), тело
    с error; в поиске и архиве 0 совпадений (задача не появилась в архиве)."""
    task = cleanup_task("QAT-К-удалению-012")
    deleted_id = task["id"]
    assert api.delete(deleted_id).status_code == 204

    resp_get = api.get_task(deleted_id)
    assert resp_get.status_code == 404
    assert "error" in resp_get.json()

    for archived_mode in ("all", "true"):
        found = api.search(archived=archived_mode).json()["results"]
        assert "QAT-К-удалению-012" not in [t["title"] for t in found]


# --------------------------------------------------------------------------
# API-создание (CHK-53, CHK-54 — Should)
# --------------------------------------------------------------------------

@pytest.mark.should
def test_create_task_via_api_authorized(api, cleanup_task):
    """TC-tasks-013: создание через API (авторизованно): HTTP 201, Task c
    title, priority=medium, tags=["api"], status="todo", числовым id; видна
    в «Ожидает» на доске."""
    task = cleanup_task("QAT-АПИ-создана", priority="medium", tags=["api"])
    assert isinstance(task["id"], int)
    assert task["title"] == "QAT-АПИ-создана"
    assert task["priority"] == "medium"
    assert task["tags"] == ["api"]
    assert task["status"] == "todo"

    columns = api.board().json()["columns"]
    assert "QAT-АПИ-создана" in [t["title"] for t in columns["todo"]]


@pytest.mark.should
def test_create_via_api_missing_title_422(api):
    """TC-tasks-014: создание без обязательного поля: body={} и {"title": null}
    — оба HTTP 422 (4xx-валидация), тело {"error", "details"}; не 5xx; задач
    не создано."""
    resp_empty = api.create()
    assert resp_empty.status_code == 422
    body = resp_empty.json()
    assert "error" in body and "details" in body

    resp_null = api.create(title=None)
    assert resp_null.status_code == 422
    body = resp_null.json()
    assert "error" in body and "details" in body

    found = api.search(archived="all").json()["results"]
    assert not [t for t in found if t["title"] in (None, "")]


# --------------------------------------------------------------------------
# НФТ: рестарт (CHK-55, CHK-56) — процедуры, автоматизация ограничена
# --------------------------------------------------------------------------

@pytest.mark.manual
@pytest.mark.must
def test_data_survives_service_restart():
    """TC-tasks-015 (НФТ, CHK-55): 0 потерь после штатного рестарта: состав
    задач, статусы, все признаки, комментарии совпадают до/после (сессии могут
    инвалидироваться — не потеря данных).

    Процедура (ручная, требует управления процессом сервиса — systemctl
    restart / перезапуск uvicorn; из автоматизации исключена: тест не может
    безопасно перезапускать прод-процесс из pytest-сессии):
      1. Снимок до: GET /api/board и GET "/api/search?archived=all" → before_restart.json
      2. Штатный рестарт: sudo systemctl restart ekotov-wiki (локально —
         эквивалентный перезапуск uvicorn из deploy/README.md)
      3. Готовность: poll GET /api/health → 200, не более 60 с (без sleep-циклов
         в тесте — poll с таймаутом; в ручной процедуре интервал 2 с)
      4. Войти заново, снять after_restart.json
      5. diff <(jq -S '.columns' before) <(jq -S '.columns' after) → пуст

    Порог: health ≤ 60 с; diff пуст; расхождение ≥1 поля — дефект NFR-3.
    """
    pytest.skip("НФТ-процедура: рестарт сервиса (см. docstring и README)")


@pytest.mark.manual
@pytest.mark.must
def test_archive_survives_service_restart():
    """TC-tasks-016 (НФТ, CHK-56): число архивных задач и их поля до/после
    рестарта совпадают (0 потерь).

    Процедура (ручная, рестарт — как в TC-tasks-015):
      1. До: GET "/api/search?archived=true" → before_arch.json; посчитать length
      2. Рестарт + готовность (шаги 2–3 TC-tasks-015)
      3. После: after_arch.json
      4. diff снимков → пуст; UI вкладки поиска — архив отображается полностью

    Порог: количество до = после; diff пуст; без пустого списка/ошибки в UI.
    """
    pytest.skip("НФТ-процедура: рестарт сервиса (см. docstring и README)")
