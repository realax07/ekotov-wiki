"""Домен archive: TC-arch-001…009 (CHK-57…65; approved/add-kanban-core/archive-01.md).

Ленивая автоархивация (sdd §3.3): GET /api/board перед ответом выполняет
UPDATE tasks SET archived_at = now WHERE status='done' AND archived_at IS NULL
AND done_at < начало текущего МСК-дня. Граница — фиксированный UTC+3.
Смещение done_at для эмуляции прошедшего дня — прямым UPDATE в SQLite
(требует env EKOTOV_WIKI_DB_PATH; иначе тест skip — см. README).
"""

import pytest

pytestmark = [pytest.mark.api]

BOARD_KEYS = ("todo", "in_progress", "done")


def _all_board_titles(board_json: dict) -> list[str]:
    columns = board_json.get("columns", board_json)
    return [t["title"] for tasks in columns.values() for t in tasks]


@pytest.mark.must
def test_done_today_stays_until_msk_midnight(api, cleanup_task, msk_dates):
    """TC-arch-001: done-задача остается в «Выполнено» до конца МСК-дня:
    status=done, done_at в день D, archived_at=NULL; при повторных чтениях
    доски в течение дня задача в «Выполнено» (автоархивации сразу после done нет)."""
    today, _ = msk_dates
    task = cleanup_task("QAT-Арх-сегодня")
    resp_move = api.move(task["id"], "done")
    assert resp_move.status_code == 200

    resp = api.get_task(task["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["done_at"] is not None and body["done_at"].startswith(today)
    assert body["archived_at"] is None

    # несколько чтений доски подряд в тот же день — задача остается
    for _ in range(3):
        resp_board = api.board()
        assert resp_board.status_code == 200
        titles = [
            t["title"] for t in resp_board.json()["columns"]["done"]
        ]
        assert "QAT-Арх-сегодня" in titles


@pytest.mark.must
def test_done_yesterday_autoarchives_on_first_board_read(
    api, cleanup_task, shift_done_at_yesterday
):
    """TC-arch-002: в новый МСК-день done-задача архивируется автоматически
    (лениво при первом GET /api/board): archived_at проставлен, done_at
    сохранен неизменным; задачи нет в столбцах; из поиска archived=true доступна."""
    task = cleanup_task("QAT-Арх-переход")
    assert api.move(task["id"], "done").status_code == 200
    done_at_before = api.get_task(task["id"]).json()["done_at"]
    shifted = shift_done_at_yesterday(task["id"], "18:00")
    assert done_at_before != shifted  # смещение применено

    # первое чтение доски после смены дня — ленивая автоархивация срабатывает здесь
    resp_board = api.board()
    assert resp_board.status_code == 200
    assert "QAT-Арх-переход" not in _all_board_titles(resp_board.json())

    resp = api.get_task(task["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["archived_at"] is not None
    assert body["done_at"] == shifted  # done_at сохранен неизменным

    archived = api.search(archived="true").json()["results"]
    assert "QAT-Арх-переход" in [t["title"] for t in archived]


@pytest.mark.must
def test_msk_midnight_boundary_done_2358_archives_next_day(
    api, cleanup_task, shift_done_at_yesterday, msk_dates
):
    """TC-arch-003 (вариант Б, эмуляция — допустимая замена варианта А):
    done_at 23:58 МСК дня D; при первом чтении доски задача архивируется,
    archived_at не NULL (граница — МСК, инвариант sdd §3.3: фиксированный UTC+3).

    Вариант А (живое ожидание полуночи) — ручная процедура (см. README):
    ожидание 10 минут в тесте нарушило бы детерминизм/скорость прогона."""
    task = cleanup_task("QAT-Арх-граница")
    assert api.move(task["id"], "done").status_code == 200
    # эмуляция: done_at сегодня 23:58 МСК — до границы текущего дня не попадает
    today, _ = msk_dates
    from conftest import db_update
    import os

    db_path = os.environ["EKOTOV_WIKI_DB_PATH"]  # skip выше гарантирует наличие
    db_update(
        db_path,
        "UPDATE tasks SET done_at = ? WHERE id = ?",
        (f"{today}T23:58:00+03:00", task["id"]),
    )
    # done_at СЕГОДНЯ 23:58 — задача еще на доске (граница не прошла):
    resp_board = api.board()
    assert "QAT-Арх-граница" in [
        t["title"] for t in resp_board.json()["columns"]["done"]
    ]

    # смещаем на вчера (D-1 23:58 МСК) — в новый день архивируется лениво
    shift_done_at_yesterday(task["id"], "23:58")
    resp_board = api.board()
    assert "QAT-Арх-граница" not in _all_board_titles(resp_board.json())

    body = api.get_task(task["id"]).json()
    assert body["archived_at"] is not None
    assert body["done_at"].endswith("T23:58:00+03:00")


@pytest.mark.must
def test_archived_task_never_returns_to_board(
    api, cleanup_task, shift_done_at_yesterday
):
    """TC-arch-004: архивная задача не возвращается на доску: при повторных
    чтениях доски задачи нет ни в одном столбце; задача не исчезла из системы —
    в поиске присутствует с archived_at не NULL."""
    task = cleanup_task("QAT-Арх-переход-004")
    assert api.move(task["id"], "done").status_code == 200
    shift_done_at_yesterday(task["id"], "15:00")

    for _ in range(4):  # повторные (третий-четвертый раз) чтения
        resp_board = api.board()
        assert resp_board.status_code == 200
        assert "QAT-Арх-переход-004" not in _all_board_titles(resp_board.json())

    found = api.search(archived="all").json()["results"]
    match = [t for t in found if t["title"] == "QAT-Арх-переход-004"]
    assert len(match) == 1
    assert match[0]["archived_at"] is not None


@pytest.mark.must
def test_move_to_done_fixes_done_at_no_archive(api, cleanup_task, msk_dates):
    """TC-arch-005: перевод в done фиксирует done_at (день D по МСК, ISO-datetime
    со смещением +03:00); archived_at NULL — не архивная, в столбце «Выполнено»."""
    today, _ = msk_dates
    task = cleanup_task("QAT-Фиксация")
    resp_move = api.move(task["id"], "done")
    assert resp_move.status_code == 200

    body = api.get_task(task["id"]).json()
    assert body["done_at"] is not None
    assert body["done_at"].startswith(today)  # день D по МСК
    assert body["done_at"].endswith("+03:00")  # ISO-datetime, фиксированный UTC+3
    assert body["archived_at"] is None
    done_titles = [t["title"] for t in api.board().json()["columns"]["done"]]
    assert "QAT-Фиксация" in done_titles


@pytest.mark.must
def test_move_back_from_done_clears_done_at_and_archived_at(api, cleanup_task):
    """TC-arch-006: обратный перевод из done снимает фиксацию: status=in_progress,
    done_at=NULL, archived_at=NULL (оба сняты); задача в столбце «В работе»."""
    task = cleanup_task("QAT-Фиксация-006")
    assert api.move(task["id"], "done").status_code == 200

    resp = api.move(task["id"], "in_progress")
    assert resp.status_code == 200

    body = api.get_task(task["id"]).json()
    assert body["status"] == "in_progress"
    assert body["done_at"] is None
    assert body["archived_at"] is None
    wip_titles = [t["title"] for t in api.board().json()["columns"]["in_progress"]]
    assert "QAT-Фиксация-006" in wip_titles


@pytest.mark.must
def test_second_done_cycle_counts_from_last_move(
    api, cleanup_task, shift_done_at_yesterday
):
    """TC-arch-007: повторный цикл done → В работе → done: отсчет от последнего
    перевода. done_at: DA1 → NULL → DA2 (свежий, DA2≠DA1); после смещения DA2
    на вчера ленивая автоархивация срабатывает по смещенному DA2, done_at
    сохранен (не DA1) — признак отсчитывается от последнего перевода."""
    task = cleanup_task("QAT-Цикл")

    # 1. move → done: DA1
    assert api.move(task["id"], "done").status_code == 200
    da1 = api.get_task(task["id"]).json()["done_at"]
    assert da1 is not None

    # 2. move → in_progress: done_at NULL
    assert api.move(task["id"], "in_progress").status_code == 200
    assert api.get_task(task["id"]).json()["done_at"] is None

    # 3. move → done заново: свежий DA2 (момент повторного перевода)
    assert api.move(task["id"], "done").status_code == 200
    body = api.get_task(task["id"]).json()
    da2 = body["done_at"]
    assert da2 is not None and da2 != da1
    assert body["archived_at"] is None
    done_titles = [t["title"] for t in api.board().json()["columns"]["done"]]
    assert "QAT-Цикл" in done_titles

    # 4. сместить DA2 на вчера (формат +03:00) — смещение наблюдаемо
    shifted = shift_done_at_yesterday(task["id"], "18:00")
    body = api.get_task(task["id"]).json()
    assert body["done_at"] == shifted  # move его еще не перезаписал

    # 5. GET /api/board: ленивая автоархивация по смещенному DA2 (вчера)
    resp_board = api.board()
    assert resp_board.status_code == 200
    assert "QAT-Цикл" not in _all_board_titles(resp_board.json())

    body = api.get_task(task["id"]).json()
    assert body["archived_at"] is not None  # момент — время шага 5
    assert body["done_at"] == shifted  # DA2 (вчера) сохранен неизменным


@pytest.mark.must
def test_archived_task_found_by_search_card_opens(api, cleanup_task, shift_done_at_yesterday):
    """TC-arch-008 (API-часть): архивная задача находится поиском, карточка
    (GET /api/tasks/{id}) открывается: 200 с полным объектом — название,
    признаки (high, Дом, архив2026), комментарий видны, archived_at не NULL.
    UI-часть (вкладка поиска, бейдж) — tests/web."""
    task = cleanup_task(
        "QAT-Арх-просмотр",
        priority="high",
        category="Дом",
        tags=["архив2026"],
    )
    api.add_comment(task["id"], "Коммент в архиве")
    assert api.move(task["id"], "done").status_code == 200
    shift_done_at_yesterday(task["id"], "15:00")
    api.board()  # ленивая автоархивация

    resp = api.get_task(task["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "QAT-Арх-просмотр"
    assert body["priority"] == "high"
    assert body["category"] == "Дом"
    assert body["tags"] == ["архив2026"]
    assert body["archived_at"] is not None

    comments = api.comments(task["id"]).json()["comments"]
    assert "Коммент в архиве" in [c["body"] for c in comments]

    archived = api.search(archived="true").json()["results"]
    assert "QAT-Арх-просмотр" in [t["title"] for t in archived]


@pytest.mark.must
def test_active_and_archived_distinguishable_in_search(api, cleanup_task, shift_done_at_yesterday):
    """TC-arch-009 (API-часть): активные и архивные задачи в поиске различимы:
    обе в выдаче archived=all; активная archived_at=NULL, архивная — не NULL
    (различимый признак архивности в данных выдачи). UI-бейджи — tests/web."""
    active = cleanup_task("QAT-Актив-микс", tags=["микс"])
    archived_task = cleanup_task("QAT-Арх-микс", tags=["микс"])
    assert api.move(archived_task["id"], "done").status_code == 200
    shift_done_at_yesterday(archived_task["id"], "15:00")
    api.board()

    found = api.search(archived="all").json()["results"]
    by_title = {t["title"]: t for t in found}
    assert "QAT-Актив-микс" in by_title
    assert "QAT-Арх-микс" in by_title
    assert by_title["QAT-Актив-микс"]["archived_at"] is None
    assert by_title["QAT-Арх-микс"]["archived_at"] is not None
