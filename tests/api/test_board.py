"""Домен board: TC-board-001…010 (CHK-18…27; approved/add-kanban-core/board-01.md).

GET /api/board → {"columns": {"todo": [Task], "in_progress": [...], "done": [...]}}
— только не-архивные (sdd §3.3); move — POST /api/tasks/{id}/move (sdd §3.2).
"""

import pytest

pytestmark = [pytest.mark.api]

BOARD_KEYS = {"todo", "in_progress", "done"}


def _titles(board_json: dict, column: str) -> list[str]:
    """Названия задач столбца; принимает как board_json, так и columns."""
    columns = board_json.get("columns", board_json)
    return [t["title"] for t in columns[column]]


@pytest.mark.must
def test_board_tasks_in_own_columns(api, cleanup_task, msk_dates):
    """TC-board-001: задачи отображаются в столбцах своего статуса:
    Доска-A (todo), Доска-B (in_progress), Доска-C (done сегодня);
    archived-задач в ответе нет."""
    a = cleanup_task(f"QAT-Доска-A")
    b = cleanup_task(f"QAT-Доска-B")
    c = cleanup_task(f"QAT-Доска-C")
    assert api.move(b["id"], "in_progress").status_code == 200
    assert api.move(c["id"], "done").status_code == 200

    resp = api.board()
    assert resp.status_code == 200
    columns = resp.json()["columns"]
    assert f"QAT-Доска-A" in _titles(columns, "todo")
    assert f"QAT-Доска-B" in _titles(columns, "in_progress")
    assert f"QAT-Доска-C" in _titles(columns, "done")
    # archived-задач в ответе нет: у всех задач columns archived_at NULL
    for column in BOARD_KEYS:
        assert all(t["archived_at"] is None for t in columns[column])


@pytest.mark.must
def test_empty_board_three_empty_columns(api):
    """TC-board-002: пустая доска — 200, ровно {"columns": {"todo": [],
    "in_progress": [], "done": []}} (после удаления всех QAT-задач)."""
    api.cleanup_all()
    resp = api.board()
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"columns": {"todo": [], "in_progress": [], "done": []}}


@pytest.mark.must
def test_board_exactly_three_fixed_columns(api):
    """TC-board-003: columns содержит ровно 3 ключа todo/in_progress/done —
    никаких других (состав столбцов неизменяем, ОГР-3)."""
    resp = api.board()
    assert resp.status_code == 200
    columns = resp.json()["columns"]
    assert set(columns.keys()) == BOARD_KEYS
    assert len(columns) == 3


@pytest.mark.must
def test_done_today_in_done_column(api, cleanup_task, msk_dates):
    """TC-board-004: выполненная сегодня (МСК) задача — в столбце «Выполнено»:
    status=done, done_at в текущий МСК-день, archived_at=NULL."""
    today, _ = msk_dates
    task = cleanup_task("QAT-Сегодня-Done")
    resp_move = api.move(task["id"], "done")
    assert resp_move.status_code == 200

    resp_task = api.get_task(task["id"])
    assert resp_task.status_code == 200
    body = resp_task.json()
    assert body["status"] == "done"
    assert body["done_at"] is not None and body["done_at"].startswith(today)
    assert body["archived_at"] is None

    resp_board = api.board()
    assert "QAT-Сегодня-Done" in _titles(resp_board.json()["columns"], "done")


@pytest.mark.must
def test_done_yesterday_not_on_board(api, cleanup_task, shift_done_at_yesterday):
    """TC-board-005: done-задача прошедшего МСК-дня отсутствует на доске;
    в поиске (archived=all) найдена с archived_at не NULL (архивирована)."""
    task = cleanup_task("QAT-Вчера-Done")
    assert api.move(task["id"], "done").status_code == 200
    shift_done_at_yesterday(task["id"], "15:00")

    resp_board = api.board()
    assert resp_board.status_code == 200
    for column in BOARD_KEYS:
        assert "QAT-Вчера-Done" not in _titles(resp_board.json()["columns"], column)

    found = api.search(archived="all").json()["results"]
    match = [t for t in found if t["title"] == "QAT-Вчера-Done"]
    assert len(match) == 1
    assert match[0]["archived_at"] is not None


@pytest.mark.must
def test_move_forward_chain_todo_wip_done(api, cleanup_task):
    """TC-board-006: прямое перемещение по цепочке todo → in_progress → done:
    после каждого шага ответ move — 200 с Task, status равен целевому;
    GET /api/board показывает задачу в целевом столбце."""
    task = cleanup_task("QAT-Цепочка")

    resp = api.move(task["id"], "in_progress")
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"
    assert "QAT-Цепочка" in _titles(api.board().json()["columns"], "in_progress")

    resp = api.move(task["id"], "done")
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
    assert "QAT-Цепочка" in _titles(api.board().json()["columns"], "done")


@pytest.mark.must
def test_move_backward_wip_to_todo(api, cleanup_task):
    """TC-board-007: обратное перемещение В работе → Ожидает:
    после move status="todo", карточка в столбце «Ожидает»."""
    task = cleanup_task("QAT-Назад")
    assert api.move(task["id"], "in_progress").status_code == 200

    resp = api.move(task["id"], "todo")
    assert resp.status_code == 200

    resp_task = api.get_task(task["id"])
    assert resp_task.json()["status"] == "todo"
    assert "QAT-Назад" in _titles(api.board().json()["columns"], "todo")


@pytest.mark.must
def test_repeated_move_to_same_column_no_duplicates(api, cleanup_task):
    """TC-board-008: повторный move в тот же столбец — 200 (не 4xx/5xx),
    Task со status="todo"; задача существует в единственном экземпляре."""
    task = cleanup_task("QAT-Тот же")

    resp = api.move(task["id"], "todo")
    assert resp.status_code == 200
    assert resp.json()["status"] == "todo"

    # единственный экземпляр: в columns.todo ровно одна карточка
    resp_task = api.get_task(task["id"])
    assert resp_task.status_code == 200
    todo_titles = _titles(api.board().json()["columns"], "todo")
    assert todo_titles.count("QAT-Тот же") == 1


@pytest.mark.must
def test_quick_done_from_any_column(api, cleanup_task, msk_dates):
    """TC-board-009: быстрое «Выполнено» из любого столбца: Быстро-1 (todo),
    Быстро-2 (in_progress), Быстро-3 (done → done): каждая сразу status=done,
    done_at в день D, archived_at=NULL; на доске в столбце «Выполнено»."""
    today, _ = msk_dates
    t1 = cleanup_task("QAT-Быстро-1")
    t2 = cleanup_task("QAT-Быстро-2")
    t3 = cleanup_task("QAT-Быстро-3")
    assert api.move(t2["id"], "in_progress").status_code == 200
    assert api.move(t3["id"], "done").status_code == 200

    for t in (t1, t2, t3):
        resp = api.move(t["id"], "done")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "done"
        assert body["done_at"] is not None and body["done_at"].startswith(today)
        assert body["archived_at"] is None
        done_titles = _titles(api.board().json()["columns"], "done")
        assert body["title"] in done_titles


@pytest.mark.must
def test_move_patch_delete_missing_id_404_not_5xx(api):
    """TC-board-010: move/PATCH/DELETE несуществующего id=999999 — каждый ответ
    HTTP 404 (не 5xx/502), тело содержит error о ненайденной задаче (DS-3)."""
    missing = 999999
    resp_move = api.move(missing, "done")
    resp_patch = api.patch(missing, priority="high")
    resp_delete = api.delete(missing)

    for resp in (resp_move, resp_patch, resp_delete):
        assert resp.status_code == 404, f"{resp.request.method}: {resp.status_code}"
        assert "error" in resp.json()
