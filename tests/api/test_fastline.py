"""Домен fastline: TC-fast-001…012 (CHK-28…40; approved/add-kanban-core/fastline-01.md),
кроме TC-fast-005 (UI-негатив через интерфейс — скоуп tests/web, см. README)
и кейса CHK-35 (отложен: DS-1, кейс не создан).

Инвариант (FR-3, ОГР-5): не более одной fast-задачи в активных статусах
(todo/in_progress); 409 {"error": "fast line occupied"} (sdd §3.2).
"""

import pytest

pytestmark = [pytest.mark.api]


def _titles(board_json: dict, column: str) -> list[str]:
    """Названия задач столбца; принимает как board_json, так и columns."""
    columns = board_json.get("columns", board_json)
    return [t["title"] for t in columns[column]]


def _fast_titles(board_json: dict) -> list[str]:
    """Задачи на fast line (is_fast=true); принимает board_json или columns."""
    columns = board_json.get("columns", board_json)
    out = []
    for tasks in columns.values():
        out.extend(t["title"] for t in tasks if t["is_fast"])
    return out


@pytest.mark.must
def test_second_fast_via_api_409_not_created(api, fast_occupied, unique_title):
    """TC-fast-006: вторая fast-задача через API — HTTP 409, тело точно
    {"error": "fast line occupied"}; задача не создана (0 совпадений в поиске)."""
    title = f"{unique_title}-вторая-API"
    resp = api.create(title=title, is_fast=True)
    assert resp.status_code == 409
    assert resp.json() == {"error": "fast line occupied"}

    found = api.search(archived="all").json()["results"]
    assert title not in [t["title"] for t in found]


@pytest.mark.must
def test_repeated_fast_requests_409_reproducible(api, fast_occupied, unique_title):
    """TC-fast-007: оба повторных запроса создания второй fast — снова 409
    {"error": "fast line occupied"} (отказ воспроизводим); ни одна из задач
    не создана; побочных задач нет."""
    title2 = f"{unique_title}-вторая-API2"
    title3 = f"{unique_title}-вторая-API3"

    resp2 = api.create(title=title2, is_fast=True)
    assert resp2.status_code == 409
    assert resp2.json() == {"error": "fast line occupied"}

    resp3 = api.create(title=title3, is_fast=True)
    assert resp3.status_code == 409
    assert resp3.json() == {"error": "fast line occupied"}

    found = api.search(archived="all").json()["results"]
    titles = [t["title"] for t in found]
    assert title2 not in titles
    assert title3 not in titles
    # побочных fast-задач нет: активная ровно одна — фикстура fast_occupied
    active_fast = [
        t for t in found if t["is_fast"] and t["status"] in ("todo", "in_progress")
    ]
    assert [t["id"] for t in active_fast] == [fast_occupied["id"]]


@pytest.mark.must
def test_regular_create_ok_after_fast_rejection(api, fast_occupied, unique_title):
    """TC-fast-008: после отказа (409) создание обычной задачи — HTTP 201,
    Task с is_fast=false, status="todo"; задача в столбце «Ожидает»."""
    title = f"{unique_title}-После-отказа-обычная"
    resp = api.create(title=title)
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_fast"] is False
    assert body["status"] == "todo"
    assert title in _titles(api.board().json()["columns"], "todo")


@pytest.mark.must
def test_new_fast_after_previous_done(api, cleanup_task, unique_title):
    """TC-fast-009: новая fast после ухода предыдущей в done — HTTP 201,
    is_fast=true; уходящая в тот же день в столбце «Выполнено».

    Ожидание кейса «уходящая (не на линии)»: fast line — todo/in_progress-столбец
    с подсветкой has-fast (board.js, tasks.md 5.2); done-столбец fast-подсветку
    не получает. Проверяем: is_fast=true у уходящей — это признак задачи, линия
    же определяется активными статусами; в активных статусах осталась ровно
    одна fast (новая)."""
    leaving = cleanup_task(f"{unique_title}-уходящая", is_fast=True)
    resp_move = api.move(leaving["id"], "done")
    assert resp_move.status_code == 200

    resp = api.create(title=f"{unique_title}-новая", is_fast=True)
    assert resp.status_code == 201
    assert resp.json()["is_fast"] is True

    board = api.board().json()
    columns = board["columns"]
    # уходящая в столбце «Выполнено»
    assert f"{unique_title}-уходящая" in _titles(columns, "done")
    # fast line (подсветка has-fast ставится todo/in_progress-столбцам):
    # ровно одна fast в активных статусах — новая
    active_fast = [
        t["title"]
        for column in ("todo", "in_progress")
        for t in columns[column]
        if t["is_fast"]
    ]
    assert active_fast == [f"{unique_title}-новая"]


@pytest.mark.must
def test_new_fast_after_previous_deleted(api, cleanup_task, unique_title):
    """TC-fast-010: удаление активной fast освобождает линию: DELETE — 2xx,
    затем создание новой fast — HTTP 201, задача на fast line."""
    leaving = cleanup_task(f"{unique_title}-удаляемая", is_fast=True)
    resp_del = api.delete(leaving["id"])
    assert resp_del.status_code // 100 == 2

    resp = api.create(title=f"{unique_title}-после-удаления", is_fast=True)
    assert resp.status_code == 201
    assert f"{unique_title}-после-удаления" in _fast_titles(api.board().json())


@pytest.mark.must
def test_regular_tasks_do_not_block_fast_line(api, cleanup_task, unique_title):
    """TC-fast-011: обычные активные задачи (todo и in_progress) не блокируют
    fast line: создание fast среди них — HTTP 201, на fast line."""
    cleanup_task(f"{unique_title}-Обыч-1")
    t2 = api.create_ok(f"{unique_title}-Обыч-2")
    api.move(t2["id"], "in_progress")

    resp = api.create(title=f"{unique_title}-Фаст-среди-обычных", is_fast=True)
    assert resp.status_code == 201
    board = api.board().json()
    assert f"{unique_title}-Фаст-среди-обычных" in _fast_titles(board)
    # обычные на месте в столбцах
    assert f"{unique_title}-Обыч-1" in _titles(board, "todo")
    assert f"{unique_title}-Обыч-2" in _titles(board, "in_progress")


@pytest.mark.must
def test_fast_line_no_autoassign_on_move_or_patch(api, cleanup_task):
    """TC-fast-004: автоназначения на fast line нет: move → in_progress,
    move → todo, PATCH priority=high — после всех операций is_fast=false."""
    task = cleanup_task("QAT-Не-фаст")

    resp = api.move(task["id"], "in_progress")
    assert resp.status_code == 200
    assert resp.json()["is_fast"] is False

    resp = api.move(task["id"], "todo")
    assert resp.status_code == 200
    assert resp.json()["is_fast"] is False

    resp = api.patch(task["id"], priority="high")
    assert resp.status_code == 200
    assert resp.json()["is_fast"] is False


@pytest.mark.must
def test_regular_task_without_fast_flag(api, cleanup_task):
    """TC-fast-003: обычная задача без отметки fast: is_fast=false (не NULL,
    не true); карточка в столбце «Ожидает», не на fast line."""
    task = cleanup_task("QAT-Обычная-без-фаста")

    resp = api.get_task(task["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_fast"] is False

    board = api.board().json()
    assert "QAT-Обычная-без-фаста" in _titles(board, "todo")
    assert "QAT-Обычная-без-фаста" not in _fast_titles(board)


@pytest.mark.must
def test_fast_create_is_fast_true_todo(api, unique_title):
    """TC-fast-002 (API-часть): создание задачи с is_fast=true — созданная
    задача is_fast=true, status="todo"; присутствует в fast-линии доски.

    UI-часть кейса (чекбокс в форме) — tests/web (см. README).
    """
    task = api.create_ok(f"{unique_title}-Фаст-ручная", is_fast=True)
    assert task["is_fast"] is True
    assert task["status"] == "todo"
    assert f"{unique_title}-Фаст-ручная" in _fast_titles(api.board().json())


# --------------------------------------------------------------------------
# UI-кейсы fastline: визуальная линия (DOM/CSS) — вне API-набора.
# --------------------------------------------------------------------------


@pytest.mark.must
@pytest.mark.web_ui
def test_fast_line_visual_highlight():
    """TC-fast-001 (UI): выделенная линия с fast-задачей; подсветка —
    светло-синий прозрачный rgba; линия не четвертый столбец.

    Проверка требует браузера (DOM/CSS board.js: классы has-fast /
    task-card-fast) — скоуп tests/web, не API (см. README, матрица).
    """
    pytest.skip("UI-кейс: скоуп tests/web (браузерная проверка DOM/CSS)")


@pytest.mark.must
@pytest.mark.web_ui
def test_fast_task_visual_priority():
    """TC-fast-012 (UI): fast-карточка однозначно выделена как первоочередная
    независимо от priority обычных задач.

    Визуальная/DOM-проверка — tests/web (см. README). Серверная часть
    (fast первым в сортировке столбца) покрывается test_fast_create_is_fast_true_todo.
    """
    pytest.skip("UI-кейс: скоуп tests/web (визуальное сравнение карточек)")
