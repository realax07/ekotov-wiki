"""Домен DnD (QA-этап 5, change add-r3-visual-foundation, FR-31/Д-6/ОВ-19).

Кейсы_TC (approved test-model/approved/add-r3-visual-foundation/):
- TC-dnd-101: перенос карточки в другой столбец — drag-ghost/drop-target,
  серверный статус меняется (равнозначно переводу селектом, ОГР-14).
- TC-dnd-102: отпускание ВНЕ столбца — POST move не отправлялся,
  карточка возвращена, drag-ghost снят.
- TC-dnd-103: 409 «fast line occupied» — ошибка в #board-error, плитка
  возвращена, инвариант ≤1 активной fast-задачи сохранен.
- TC-dnd-104: перенос в «Выполнено» — done_at проставлен (момент МСК),
  archived_at пуст (ленивая автоархивация, ОГР-14).
- TC-dnd-105: touch-контекст — тап не открывает drag-сессию; перенос
  прежним способом (селект «Столбец») работает (ОВ-19).
- TC-dnd-106: после 409 следующий успешный DnD скрывает #board-error.

Механика (урок architect-ревью): нативные mouse-события HTML5 DnD не
порождают — события dispatchEvent с общим DataTransfer (dnd_helpers).
"""

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui
from tests.web.dnd_helpers import dnd_dispatch

pytestmark = [pytest.mark.web, pytest.mark.must]

BOARD_JS = "frontend/static/js/board/board-init.js"


def _card(page, title: str):
    return page.get_by_role("article").filter(has_text=title)


def _column(page, status: str):
    return page.locator(f'.board-column[data-status="{status}"]')


def _wait_board(page) -> None:
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")


def _login(page, web_base_url) -> None:
    """Вход owner на произвольной странице (своя страница контекста)."""
    page.goto(f"{web_base_url}/login")
    page.get_by_label("Логин").fill("owner")
    page.get_by_label("Пароль").fill("QaOwner_Pass_1!")
    page.get_by_role("button", name="Войти").click()
    page.get_by_role("heading", name="Доска", exact=True).wait_for()


def _make_fast_occupied(page, web_base_url, web_owner_session, web_cleanup_created, busy_title: str) -> None:
    """Активная fast-задача (is_fast=true, статус todo) — fast line занята."""
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": busy_title, "is_fast": True}
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])
    _wait_board(page)


# --------------------------------------------------------------------------
# TC-dnd-101 — «перетаскивание карточки в другой столбец» (Must)
# --------------------------------------------------------------------------
def test_dnd_move_card_to_another_column(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-dnd-101: dragstart → drag-ghost на карточке; dragover →
    drop-target на столбце «В работе»; drop → карточка в новом столбце,
    GET /api/board показывает in_progress (тот же результат, что перевод
    существующим способом, ОГР-14)."""
    page = board_page
    create_task_via_ui(page, "QAT-dnd-перенос")
    card = _card(page, "QAT-dnd-перенос")
    expect(card).to_be_visible()
    web_cleanup_created(int(card.get_attribute("data-task-id")))

    result = dnd_dispatch(page, card, _column(page, "in_progress"))

    # Шаг 2: карточка получила drag-ghost; после dragend класс снят.
    assert "drag-ghost" in result["cardClass"], result
    assert "drag-ghost" not in result["cardClassAfterDragEnd"], result
    # Шаг 3: столбец-приемник получил drop-target.
    assert "drop-target" in result["targetClass"], result

    # Шаг 5: карточка в «В работе»; сервер — in_progress.
    expect(_column(page, "in_progress").get_by_role("article").filter(
        has_text="QAT-dnd-перенос"
    )).to_be_visible()
    board = web_owner_session.get(f"{web_base_url}/api/board")
    assert board.status_code == 200
    tasks = board.json()["columns"]["in_progress"]
    moved = [t for t in tasks if t["title"] == "QAT-dnd-перенос"]
    assert len(moved) == 1, tasks
    assert moved[0]["status"] == "in_progress"


# --------------------------------------------------------------------------
# TC-dnd-102 — «отпускание вне зоны столбца возвращает карточку» (Must)
# --------------------------------------------------------------------------
def test_dnd_drop_outside_column_returns_card(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-dnd-102: dragover/drop вне .board-column (заголовок h1.page-title):
    POST /api/tasks/*/move не отправлялся (счетчик 0); вне столбца
    drop-target не ставится; после dragend карточка на месте, серверный
    статус todo не изменился."""
    page = board_page
    create_task_via_ui(page, "QAT-dnd-вне-зоны")
    card = _card(page, "QAT-dnd-вне-зоны")
    expect(card).to_be_visible()
    task_id = int(card.get_attribute("data-task-id"))
    web_cleanup_created(task_id)

    move_requests = []
    page.on(
        "request",
        lambda r: move_requests.append(r.url)
        if "/api/tasks/" in r.url and r.url.endswith("/move") and r.method == "POST"
        else None,
    )

    result = dnd_dispatch(page, card, page.locator("h1.page-title"))

    # Вне столбца: drop-target не ставился, drag-ghost снят dragend'ом.
    assert "drop-target" not in result.get("targetClass", ""), result
    assert "drag-ghost" not in result["cardClassAfterDragEnd"], result
    assert move_requests == [], f"POST move ушел: {move_requests}"

    # Карточка на исходном месте; сервер: статус todo.
    expect(_column(page, "todo").get_by_role("article").filter(
        has_text="QAT-dnd-вне-зоны"
    )).to_be_visible()
    task = web_owner_session.get(f"{web_base_url}/api/tasks/{task_id}")
    assert task.status_code == 200
    assert task.json()["status"] == "todo"


# --------------------------------------------------------------------------
# TC-dnd-103 — «409 fast line занята — ошибка в UI, плитка возвращена» (Must)
# --------------------------------------------------------------------------
def test_dnd_fast_line_occupied_409_error_and_return(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-dnd-103: drop fast-карточки из «Выполнено» в «Ожидает» при занятой
    fast line: ответ 409 {"error": "fast line occupied"}; #board-error
    видим; плитка возвращена в done; активная fast-задача ровно одна (Д-6)."""
    page = board_page
    # Порядок учета инварианта ≤1 (Д-6): пока линия свободна создаем
    # «QAT-fast-возврат», переводим в done (линия снова свободна) —
    # только затем создаем активную «QAT-fast-занято» (обе 201).
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "QAT-fast-возврат", "is_fast": True}
    )
    assert created.status_code == 201, created.text
    return_id = created.json()["id"]
    web_cleanup_created(return_id)
    assert web_owner_session.post(
        f"{web_base_url}/api/tasks/{return_id}/move", json={"status": "done"}
    ).status_code == 200

    _make_fast_occupied(
        page, web_base_url, web_owner_session, web_cleanup_created, "QAT-fast-занято"
    )
    # Задачи, созданные/переведенные через API, появляются в DOM доски
    # после перезагрузки (UI перерисовывается только своими действиями).
    page.reload()
    _wait_board(page)

    # Перехват ответа POST /api/tasks/*/move (шаг 2).
    responses = []
    page.on(
        "response",
        lambda r: responses.append((r.status, r.url))
        if "/api/tasks/" in r.url and r.url.endswith("/move") and r.request.method == "POST"
        else None,
    )

    card = _card(page, "QAT-fast-возврат")
    expect(_column(page, "done").get_by_role("article").filter(
        has_text="QAT-fast-возврат"
    )).to_be_visible()
    result = dnd_dispatch(page, card, _column(page, "todo"))
    assert "drop-target" in result["targetClass"], result

    # Шаг 4: ошибка видима; шаг 2: ответ 409 с телом из кейса.
    error = page.locator("#board-error")
    expect(error).to_be_visible()
    assert error.inner_text().strip() == "fast line занята", error.inner_text()

    # Шаг 5: плитка возвращена в «Выполнено» (перерисовка из сервера).
    expect(_column(page, "done").get_by_role("article").filter(
        has_text="QAT-fast-возврат"
    )).to_be_visible()
    assert responses and responses[0][0] == 409, responses

    # Шаг 6: в активных статусах ровно одна fast-задача (инвариант Д-6).
    body = web_owner_session.get(f"{web_base_url}/api/board").json()
    active_fast = [
        t
        for status in ("todo", "in_progress")
        for t in body["columns"][status]
        if t["is_fast"]
    ]
    assert [t["title"] for t in active_fast] == ["QAT-fast-занято"], body


# --------------------------------------------------------------------------
# TC-dnd-104 — «DnD в Выполнено: done_at проставлен, архивации нет» (Must)
# --------------------------------------------------------------------------
def test_dnd_to_done_sets_done_at_no_archive(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-dnd-104: drop в «Выполнено»: status=done; done_at непустое и
    парсится как момент перевода (МСК ±0 с допустимым Z-эквивалентом);
    archived_at пустое (null) — ленивая автоархивация, ОГР-14."""
    from datetime import datetime, timedelta, timezone

    page = board_page
    create_task_via_ui(page, "QAT-dnd-done")
    card = _card(page, "QAT-dnd-done")
    expect(card).to_be_visible()
    task_id = int(card.get_attribute("data-task-id"))
    web_cleanup_created(task_id)

    before = datetime.now(timezone.utc) - timedelta(seconds=5)
    result = dnd_dispatch(page, card, _column(page, "done"))
    assert "drop-target" in result["targetClass"], result

    expect(_column(page, "done").get_by_role("article").filter(
        has_text="QAT-dnd-done"
    )).to_be_visible()

    # Шаг 3: GET /api/tasks/{id} — статус/моменты.
    task = web_owner_session.get(f"{web_base_url}/api/tasks/{task_id}")
    assert task.status_code == 200
    body = task.json()
    assert body["status"] == "done"
    assert body["done_at"], body
    done_at = body["done_at"].replace("Z", "+00:00")
    moment = datetime.fromisoformat(done_at)
    after = datetime.now(timezone.utc) + timedelta(seconds=5)
    assert before <= moment <= after, (before, moment, after)
    # Ассерт по моменту, не по суффиксу: МСК = UTC+03:00 (или Z-эквивалент).
    msk = moment.astimezone(timezone(timedelta(hours=3)))
    assert msk.utcoffset() == timedelta(hours=3)
    assert body.get("archived_at") in (None, ""), body


# --------------------------------------------------------------------------
# TC-dnd-105 — «Touch: drag не срабатывает, прежний перенос работает» (Must)
# --------------------------------------------------------------------------
def test_touch_tap_starts_no_drag_select_move_works(
    browser, web_server, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-dnd-105: touch-контекст (has_touch=True): одиночный тап по
    карточке НЕ открывает drag-сессию (нет drag-ghost, счетчик POST move
    = 0 — HTML5 DnD на touch не срабатывает, ОВ-19); перенос прежним
    способом (карточка → селект «Столбец» → in_progress) работает."""
    context = browser.new_context(has_touch=True)
    page = context.new_page()
    # Статика /static/* — с http.server-стенда (роль nginx, как в conftest).
    static_url = web_server["static_url"]
    if static_url:
        page.route(
            f"{web_base_url}/static/**",
            lambda route: route.fulfill(
                response=route.fetch(
                    url=static_url + route.request.url.partition("/static")[2]
                )
            ),
        )
    try:
        _login(page, web_base_url)
        _wait_board(page)

        created = web_owner_session.post(
            f"{web_base_url}/api/tasks", json={"title": "QAT-dnd-touch"}
        )
        assert created.status_code == 201, created.text
        task_id = created.json()["id"]
        web_cleanup_created(task_id)
        # Задачи, созданные через API, попадают в DOM доски после перезагрузки
        # (UI перерисовывается только своими действиями).
        page.reload()
        _wait_board(page)

        card = _card(page, "QAT-dnd-touch")
        expect(card).to_be_visible()

        move_requests = []
        page.on(
            "request",
            lambda r: move_requests.append(r.url)
            if "/api/tasks/" in r.url and r.url.endswith("/move") and r.method == "POST"
            else None,
        )

        # Шаг 2: одиночный тап (никаких синтетических drag-событий).
        box = card.bounding_box()
        page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

        # Шаг 3: drag-сессии нет.
        assert "drag-ghost" not in (card.get_attribute("class") or "")
        assert move_requests == [], f"POST move ушел: {move_requests}"

        # Шаги 4–5: перенос прежним способом — селект «Столбец»
        # (после перезагрузки страницы, т.к. тап уже использован).
        page.reload()
        _wait_board(page)
        card = _card(page, "QAT-dnd-touch")
        expect(card).to_be_visible()
        # 4.1 (FR-47, Д-9): клик открывает view-модалку read-only;
        # селект «Столбец» — в форме редактирования («Редактировать»).
        card.click()
        page.get_by_role("button", name="Редактировать").click()
        expect(page.locator("#task-form-overlay")).to_be_visible()
        page.get_by_label("Столбец").select_option("in_progress")
        expect(_column(page, "in_progress").get_by_role("article").filter(
            has_text="QAT-dnd-touch"
        )).to_be_visible()
    finally:
        context.close()


# --------------------------------------------------------------------------
# TC-dnd-106 — «после 409 успешный DnD не оставляет старую ошибку» (Must)
# --------------------------------------------------------------------------
def test_dnd_success_after_409_hides_board_error(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-dnd-106: воспроизведен 409 (шаг 1, расстановка TC-dnd-103);
    затем успешный DnD обычной задачи в «В работе» — #board-error скрыт,
    старое сообщение не висит, перевод выполнен."""
    page = board_page
    # Порядок учета инварианта ≤1 (Д-6): «QAT-fast-возврат» создается и
    # переводится в done ПЕРВОЙ (линия снова свободна), затем создается
    # активная «QAT-fast-занято» (обе 201).
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "QAT-fast-возврат", "is_fast": True}
    )
    assert created.status_code == 201, created.text
    return_id = created.json()["id"]
    web_cleanup_created(return_id)
    assert web_owner_session.post(
        f"{web_base_url}/api/tasks/{return_id}/move", json={"status": "done"}
    ).status_code == 200

    _make_fast_occupied(
        page, web_base_url, web_owner_session, web_cleanup_created, "QAT-fast-занято"
    )
    # API-созданные задачи появляются в DOM после перезагрузки доски.
    page.reload()
    _wait_board(page)

    create_task_via_ui(page, "QAT-dnd-очистка")
    cleanup_card = _card(page, "QAT-dnd-очистка")
    expect(cleanup_card).to_be_visible()
    web_cleanup_created(int(cleanup_card.get_attribute("data-task-id")))
    _wait_board(page)

    # Шаг 1: 409 по шагам TC-dnd-103.
    fast_card = _card(page, "QAT-fast-возврат")
    expect(_column(page, "done").get_by_role("article").filter(
        has_text="QAT-fast-возврат"
    )).to_be_visible()
    dnd_dispatch(page, fast_card, _column(page, "todo"))
    expect(page.locator("#board-error")).to_be_visible()

    # Шаг 2: успешный DnD «QAT-dnd-очистка» → «В работе».
    result = dnd_dispatch(page, cleanup_card, _column(page, "in_progress"))
    assert "drop-target" in result["targetClass"], result

    # Шаг 3: карточка в новом столбце; #board-error скрыт.
    expect(_column(page, "in_progress").get_by_role("article").filter(
        has_text="QAT-dnd-очистка"
    )).to_be_visible()
    error = page.locator("#board-error")
    assert not error.is_visible(), error.inner_text()
