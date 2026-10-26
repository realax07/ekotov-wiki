"""coverage-backfill-1; TC-p23-109: Вставка fast через редактирование обычной
задачи (FR-89, третий путь); TC-p23-110: Чекбокс fast в edit-форме заблокирован
при занятой зоне, идемпотентность на самой fast; TC-p23-111: Paste/селект-путь
не назначает fast; TC-p23-112: Негатив — вторая fast-задача через API
отклонена 409/422; TC-p23-113: DnD fast между этапами зоны — ровно один POST
move на drop; TC-p23-114: Перемещение fast в «Выполнено» зоны = выполнение;
TC-p23-115: Негатив — возврат выполненной fast в этап при новой активной — 409;
TC-p23-116: Приемники DnD подсвечены цветом направления (ОВ-4); TC-p23-117:
Негатив — обычная задача не вставляется в занятую зону DnD; TC-p23-118:
Негатив — обычная задача не вставляется и в ПУСТУЮ зону DnD (Э2); TC-p23-119:
Негатив — fast-карта не перетаскивается на канбан; TC-p23-120: Гонка двух
вкладок — сабмит при занятом слоте закрывается серверным 409; TC-p23-121:
XSS через названия задач не исполняется в зоне и канбане.

Группа B change coverage-backfill-1 (fast line, p23). Кейсы:
test-model/approved/p23-fastline/TC-p23-109…121.md. Стенд и хелперы —
tests/web/conftest.py (автостенд, tmp-БД, seed owner); DnD — синтетические
события с общим DataTransfer (tests/web/dnd_helpers.py, урок regress №7).
Запуск: pytest tests/web/test_coverage_fastline.py -q

Факты расхождений с кейсами (зафиксированы в docstring'ах тестов):
- TC-p23-116: мокап v2-dnd-move «голубой пунктир» в коде заменен сигнальным
  янтарным зоны (--fastline) и ступенями bg3/border-2 канбана (волна
  «Пульта», board.css) — ассерты по фактической цветовой кодировке,
  направления не спутать (дух ОВ-4 соблюден).
- TC-p23-111 шаг 4: многострочный paste НЕ разбивается на задачи (продукт
  не реализует split) — ассерт: что бы ни создал paste-путь, все созданные
  задачи обычные (is_fast=false), зона не задействована.
"""

import json

import pytest
from playwright.sync_api import expect

from tests.web.dnd_helpers import dnd_dispatch

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def _zone_column(page, stage: str):
    """Столбец зоны FASTLINE по этапу (data-fastline-stage = status)."""
    return page.locator(
        f'#fastline .fastline-column[data-fastline-stage="{stage}"]'
    )


def _kanban_column(page, status: str):
    """Столбец канбана (data-status) — только канбан, зона не матчится."""
    return page.locator(f'[data-status="{status}"]')


def _card(page, title: str):
    return page.get_by_role("article").filter(has_text=title)


def _track_posts(page, store: list, pattern: str = "/api/tasks"):
    """Собирать POST-запросы с URL, содержащим pattern (журнал кейсов:
    счетчик запросов на drop/гонки). Возвращает функцию-отписку."""

    def _on_request(request):
        if request.method == "POST" and pattern in request.url:
            store.append(request)

    page.on("request", _on_request)
    return lambda: page.remove_listener("request", _on_request)


# ---------------------------------------------------------------------------
# TC-p23-109 — Вставка fast через редактирование обычной задачи (FR-89)
# ---------------------------------------------------------------------------
def test_tc_p23_109_edit_form_fast_insert(board_page, web_owner_session,
                                          web_base_url, web_cleanup_created):
    """TC-p23-109: чекбокс fast в режиме редактирования доступен; включение
    ставит priority=high и блокирует поле (priority-lock); PATCH несет
    is_fast:true (полное переключение) + priority:high → 200; задача
    переезжает в «Ожидает» ЗОНЫ, слот занят: кнопка disabled + чип."""
    page = board_page
    plain = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "CB-стать-fast"}
    )
    assert plain.status_code == 201, plain.text
    task_id = plain.json()["id"]
    web_cleanup_created(task_id)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    card = _card(page, "CB-стать-fast")
    expect(_kanban_column(page, "todo").get_by_role("article")).to_have_count(1)
    card.click()
    page.get_by_role("button", name="Редактировать").click()
    form = page.locator("#task-form-overlay")
    expect(form).to_be_visible()

    checkbox = page.locator("#task-is-fast")
    expect(checkbox).to_be_enabled()
    expect(checkbox).not_to_be_checked()

    with page.expect_response(
        lambda r: r.request.method == "PATCH" and f"/api/tasks/{task_id}" in r.url
    ) as resp_info:
        checkbox.check()
        # priority-lock: приоритет поднят до «высокий», поле заблокировано.
        expect(page.locator("#task-priority")).to_have_value("high")
        expect(page.locator("#task-priority")).to_be_disabled()
        page.locator("#task-form-submit").click()

    response = resp_info.value
    assert response.status == 200, response.text
    payload = json.loads(response.request.post_data)
    assert payload["is_fast"] is True, payload
    assert payload["priority"] == "high", payload

    expect(_zone_column(page, "todo").get_by_role("article").filter(
        has_text="CB-стать-fast")).to_be_visible()
    expect(_kanban_column(page, "todo").get_by_role("article")).to_have_count(0)
    expect(page.locator("#fastline-add-button")).to_be_disabled()
    expect(page.locator("#fastline-blocked-hint")).to_be_visible()


# ---------------------------------------------------------------------------
# TC-p23-110 — Гейт чекбокса в edit-форме; идемпотентность на самой fast
# ---------------------------------------------------------------------------
def test_tc_p23_110_edit_gate_and_idempotent_toggle(board_page,
                                                    web_owner_session,
                                                    web_base_url,
                                                    web_cleanup_created):
    """TC-p23-110: при занятой зоне чекбокс fast у ОБЫЧНОЙ задачи disabled
    с причиной-чипом (гейт 2.5, как у кнопки); на самой fast-задаче чекбокс
    доступен всегда; выключение освобождает слот (задача в канбан, кнопка
    активна, чип исчез), повторное включение — 200 (идемпотентно,
    exclude_task_id), не 409."""
    page = board_page
    fast = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "FL-редактор", "is_fast": True, "priority": "high"},
    )
    assert fast.status_code == 201, fast.text
    plain = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "CB-редактор"}
    )
    assert plain.status_code == 201, plain.text
    web_cleanup_created(fast.json()["id"])
    web_cleanup_created(plain.json()["id"])
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # Шаг 2: у обычной задачи чекбокс заблокирован, причина показана.
    _card(page, "CB-редактор").click()
    page.get_by_role("button", name="Редактировать").click()
    checkbox = page.locator("#task-is-fast")
    expect(checkbox).to_be_disabled()
    expect(page.locator("#task-is-fast-gate")).to_be_visible()
    page.locator("#task-form-cancel").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()

    # Шаг 3: на самой fast-задаче чекбокс доступен.
    _card(page, "FL-редактор").click()
    page.get_by_role("button", name="Редактировать").click()
    expect(checkbox).to_be_enabled()
    expect(checkbox).to_be_checked()

    # Шаг 4: выключение освобождает слот; задача вернулась в канбан.
    with page.expect_response(
        lambda r: r.request.method == "PATCH"
        and f"/api/tasks/{fast.json()['id']}" in r.url
    ) as resp_info:
        checkbox.uncheck()
        page.locator("#task-form-submit").click()
    assert resp_info.value.status == 200, resp_info.value.text
    expect(_kanban_column(page, "todo").get_by_role("article").filter(
        has_text="FL-редактор")).to_be_visible()
    expect(_zone_column(page, "todo").locator("article")).to_have_count(0)
    expect(page.locator("#fastline-add-button")).to_be_enabled()
    expect(page.locator("#fastline-blocked-hint")).to_be_hidden()

    # Шаг 5: повторное включение — 200 (идемпотентность), задача снова в зоне.
    _card(page, "FL-редактор").click()
    page.get_by_role("button", name="Редактировать").click()
    with page.expect_response(
        lambda r: r.request.method == "PATCH"
        and f"/api/tasks/{fast.json()['id']}" in r.url
    ) as resp_info2:
        checkbox.check()
        page.locator("#task-form-submit").click()
    assert resp_info2.value.status == 200, resp_info2.value.text
    expect(_zone_column(page, "todo").get_by_role("article").filter(
        has_text="FL-редактор")).to_be_visible()
    expect(page.locator("#fastline-add-button")).to_be_disabled()


# ---------------------------------------------------------------------------
# TC-p23-111 — Paste/селект-путь не назначает fast
# ---------------------------------------------------------------------------
def test_tc_p23_111_paste_and_select_paths_never_fast(board_page,
                                                      web_owner_session,
                                                      web_base_url,
                                                      web_cleanup_created):
    """TC-p23-111: перевод столбца селектом edit-формы не меняет is_fast
    (payload несет ТОЛЬКО status — факт: селект стреляет сразу POST /move,
    без «Сохранить»), в зоне задача не появляется ни на одном шаге; paste
    многострочного списка в форму создания дает ТОЛЬКО обычные задачи
    (is_fast=false). Факт: split многострочного title продуктом не
    реализован (строка с \\n обрезается input'ом) — ассерт по духу кейса:
    все, что создал paste-путь, — обычные задачи в канбане."""
    page = board_page
    plain = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "CB-селект"}
    )
    assert plain.status_code == 201, plain.text
    task_id = plain.json()["id"]
    web_cleanup_created(task_id)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    moves = []

    def _open_edit():
        _card(page, "CB-селект").click()
        page.get_by_role("button", name="Редактировать").click()
        expect(page.locator("#task-form-overlay")).to_be_visible()

    def _move_and_capture(status: str):
        # Факт: селект «Столбец» выполняет перевод СРАЗУ на change —
        # POST /api/tasks/{id}/move (task-form.js), «Сохранить» не нужен
        # (механика move_via_card_select в conftest). Перехват payload.
        with page.expect_request(
            lambda r: r.method == "POST"
            and f"/api/tasks/{task_id}/move" in r.url
        ) as req_info:
            page.get_by_label("Столбец").select_option(status)
        moves.append(req_info.value)
        expect(_kanban_column(page, status).get_by_role("article").filter(
            has_text="CB-селект")).to_be_visible()

    for status in ("in_progress", "done", "todo"):
        _open_edit()
        _move_and_capture(status)
        expect(_zone_column(page, status).locator("article")).to_have_count(0)

    for request in moves:
        payload = json.loads(request.post_data)
        assert set(payload) == {"status"}, payload  # is_fast не меняется
        assert payload["status"] in ("in_progress", "done", "todo"), payload

    # Шаг 4: paste-путь — вставка многострочного списка в форму создания.
    page.get_by_role("button", name="Создать задачу").click()
    page.get_by_label("Название").click()
    page.keyboard.insert_text("Первая задача\nВторая задача")
    page.locator("#task-form-submit").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()

    board = web_owner_session.get(f"{web_base_url}/api/board").json()
    all_tasks = [t for tasks in board["columns"].values() for t in tasks]
    pasted = [
        t for t in all_tasks
        if "Первая задача" in t["title"] or "Вторая задача" in t["title"]
    ]
    assert pasted, board
    for t in pasted:
        assert t["is_fast"] is False, t
        assert t["status"] in ("todo", "in_progress", "done"), t
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    for stage in ("todo", "in_progress", "done"):
        expect(_zone_column(page, stage).locator("article")).to_have_count(0)


# ---------------------------------------------------------------------------
# TC-p23-112 — Негатив: вторая fast через API отклонена 409/422
# ---------------------------------------------------------------------------
def test_tc_p23_112_api_second_fast_409_and_priority_lock(web_owner_session,
                                                          web_base_url,
                                                          web_cleanup_created):
    """TC-p23-112: POST is_fast при занятой линии — 409 «fast line occupied»,
    задача не создана; PATCH обычной is_fast:true — тот же 409; после
    освобождения слота POST is_fast с priority=medium — 422 «fast requires
    high» (priority-lock); в доске ровно одна fast, «FL-вторая» отсутствует."""
    base = web_base_url
    first = web_owner_session.post(
        f"{base}/api/tasks",
        json={"title": "FL-первая", "is_fast": True, "priority": "high"},
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]
    web_cleanup_created(first_id)
    plain = web_owner_session.post(
        f"{base}/api/tasks", json={"title": "FL-обычная"}
    )
    assert plain.status_code == 201, plain.text
    web_cleanup_created(plain.json()["id"])

    # Шаг 2: второй POST — 409, инвариант ≤1.
    second = web_owner_session.post(
        f"{base}/api/tasks",
        json={"title": "FL-вторая", "is_fast": True, "priority": "high"},
    )
    assert second.status_code == 409, second.text
    assert second.json() == {"error": "fast line occupied"}, second.text

    # Шаг 3: PATCH-путь под тем же инвариантом.
    patched = web_owner_session.patch(
        f"{base}/api/tasks/{plain.json()['id']}", json={"is_fast": True}
    )
    assert patched.status_code == 409, patched.text
    assert patched.json() == {"error": "fast line occupied"}, patched.text

    # Шаг 5 (до освобождения): ровно одна fast, FL-вторая не создана.
    board = web_owner_session.get(f"{base}/api/board").json()
    fasts = [
        t for tasks in board["columns"].values() for t in tasks if t["is_fast"]
    ]
    assert [t["title"] for t in fasts] == ["FL-первая"], board

    # Шаг 4: слот освобожден → POST с priority=medium — 422 priority-lock.
    freed = web_owner_session.patch(
        f"{base}/api/tasks/{first_id}", json={"is_fast": False}
    )
    assert freed.status_code == 200, freed.text
    wrong = web_owner_session.post(
        f"{base}/api/tasks",
        json={"title": "FL-вторая", "is_fast": True, "priority": "medium"},
    )
    assert wrong.status_code == 422, wrong.text
    # Валидационный обработчик: тело {"error","details"} (паритет ядру).
    assert wrong.json()["error"] == "validation", wrong.text
    assert wrong.json()["details"] == {"priority": "fast requires high"}
    # Возврат первой в зону — 200 (идемпотентный путь TC-p23-110).
    back = web_owner_session.patch(
        f"{base}/api/tasks/{first_id}",
        json={"is_fast": True, "priority": "high"},
    )
    assert back.status_code == 200, back.text

    board = web_owner_session.get(f"{base}/api/board").json()
    fasts = [
        t for tasks in board["columns"].values() for t in tasks if t["is_fast"]
    ]
    assert [t["title"] for t in fasts] == ["FL-первая"], board


# ---------------------------------------------------------------------------
# TC-p23-113 — DnD fast между этапами зоны: ровно один POST move на drop
# ---------------------------------------------------------------------------
def test_tc_p23_113_dnd_move_single_post(board_page, web_owner_session,
                                         web_base_url, web_cleanup_created):
    """TC-p23-113: drop fast-карты в столбец зоны «В работе» отправляет РОВНО
    ОДИН POST /api/tasks/{id}/move {status: in_progress} (двойной dragend не
    задваивает запрос, O1); карточка в «В работе» зоны; ошибок в
    #board-error нет."""
    page = board_page
    fast = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "FL-dnd-move", "is_fast": True, "priority": "high"},
    )
    assert fast.status_code == 201, fast.text
    fast_id = fast.json()["id"]
    web_cleanup_created(fast_id)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    posts: list = []
    stop = _track_posts(page, posts, "/api/tasks")
    result = dnd_dispatch(
        page, _card(page, "FL-dnd-move"), _zone_column(page, "in_progress")
    )
    assert "drop-target" in result["targetClass"], result

    expect(_zone_column(page, "in_progress").get_by_role("article").filter(
        has_text="FL-dnd-move")).to_be_visible()
    moves = [r for r in posts if r.url.endswith(f"/api/tasks/{fast_id}/move")]
    assert len(moves) == 1, [r.url for r in posts]
    assert json.loads(moves[0].post_data) == {"status": "in_progress"}
    expect(page.locator("#board-error")).to_be_hidden()
    stop()


# ---------------------------------------------------------------------------
# TC-p23-114 — Перемещение fast в «Выполнено» зоны = выполнение задачи
# ---------------------------------------------------------------------------
def test_tc_p23_114_zone_done_completes_fast(board_page, web_owner_session,
                                             web_base_url,
                                             web_cleanup_created):
    """TC-p23-114: drop в столбец зоны done — обычный POST /move
    {status: done} (нового эндпоинта нет); карточка в «Выполнено» ЗОНЫ,
    done_at проставлен; слот освобожден — «+ Fast-задача» активна."""
    page = board_page
    fast = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "FL-dnd-done", "is_fast": True, "priority": "high"},
    )
    assert fast.status_code == 201, fast.text
    fast_id = fast.json()["id"]
    web_cleanup_created(fast_id)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    posts: list = []
    stop = _track_posts(page, posts, "/api/tasks")
    dnd_dispatch(
        page, _card(page, "FL-dnd-done"), _zone_column(page, "in_progress")
    )
    expect(_zone_column(page, "in_progress").get_by_role("article")).to_have_count(1)
    dnd_dispatch(page, _card(page, "FL-dnd-done"), _zone_column(page, "done"))

    expect(_zone_column(page, "done").get_by_role("article").filter(
        has_text="FL-dnd-done")).to_be_visible()
    moves = [r for r in posts if r.url.endswith(f"/api/tasks/{fast_id}/move")]
    assert len(moves) == 2, [r.url for r in posts]
    assert json.loads(moves[1].post_data) == {"status": "done"}
    stop()

    task = web_owner_session.get(f"{web_base_url}/api/tasks/{fast_id}").json()
    assert task["status"] == "done", task
    assert task["done_at"], task
    expect(page.locator("#fastline-add-button")).to_be_enabled()


# ---------------------------------------------------------------------------
# TC-p23-115 — Негатив: возврат выполненной fast при новой активной — 409
# ---------------------------------------------------------------------------
def test_tc_p23_115_return_done_fast_409(board_page, web_owner_session,
                                         web_base_url, web_cleanup_created):
    """TC-p23-115: возврат выполненной fast в «Ожидает» зоны при новой
    активной fast — 409 «fast line occupied» (единственное DnD-ребро с 409:
    инвариант ≤1 считает только todo/in_progress); сообщение в
    #board-error; refreshBoard из серверного состояния — карточки на местах,
    полузависимых состояний нет."""
    page = board_page
    first = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "FL-первая", "is_fast": True, "priority": "high"},
    )
    assert first.status_code == 201, first.text
    web_cleanup_created(first.json()["id"])
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # Выполнить первую: drop в «Выполнено» зоны — слот свободен.
    dnd_dispatch(page, _card(page, "FL-первая"), _zone_column(page, "done"))
    expect(_zone_column(page, "done").get_by_role("article").filter(
        has_text="FL-первая")).to_be_visible()
    expect(page.locator("#fastline-add-button")).to_be_enabled()

    second = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "FL-вторая", "is_fast": True, "priority": "high"},
    )
    assert second.status_code == 201, second.text
    web_cleanup_created(second.json()["id"])
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    with page.expect_response(
        lambda r: r.request.method == "POST"
        and r.url.endswith(f"/api/tasks/{first.json()['id']}/move")
    ) as resp_info:
        dnd_dispatch(page, _card(page, "FL-первая"), _zone_column(page, "todo"))
    assert resp_info.value.status == 409, resp_info.value.text

    # Сообщение об ошибке показано; refreshBoard из серверного состояния:
    # первая осталась в done, вторая на своем этапе (полузависимых состояний
    # нет — карточка не «висит» в «Ожидает»).
    expect(page.locator("#board-error")).to_be_visible()
    error_text = page.locator("#board-error").inner_text()
    # Текст 409 переформулирован под зону (api.js): «В фастлайне уже есть
    # задача — выполните текущую».
    assert "уже есть задача" in error_text.lower(), error_text
    expect(_zone_column(page, "done").get_by_role("article").filter(
        has_text="FL-первая")).to_be_visible()
    expect(_zone_column(page, "todo").get_by_role("article").filter(
        has_text="FL-вторая")).to_be_visible()
    expect(_zone_column(page, "todo").get_by_role("article")).to_have_count(1)


# ---------------------------------------------------------------------------
# TC-p23-116 — Приемники DnD подсвечены цветом направления (ОВ-4)
# ---------------------------------------------------------------------------
def test_tc_p23_116_dnd_direction_colors(board_page, web_owner_session,
                                         web_base_url, web_cleanup_created):
    """TC-p23-116: направления не спутать (дух ОВ-4). Факт (см. докстринг
    модуля): зона-приемник — янтарный пунктир --fastline (не голубой мокапа
    v2-dnd-move), канбан-приемник — ступень bg3 + пунктир border-2, запрет в
    зоне — красный пунктир --status-error. Ассерты по классам + computed
    outline-цвету в момент dragover."""
    page = board_page
    fast = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "FL-цвет", "is_fast": True, "priority": "high"},
    )
    assert fast.status_code == 201, fast.text
    plain = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "CB-цвет"}
    )
    assert plain.status_code == 201, plain.text
    web_cleanup_created(fast.json()["id"])
    web_cleanup_created(plain.json()["id"])
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # fast → столбец зоны: приемник (drop-target, янтарный пунктир).
    result = dnd_dispatch(
        page, _card(page, "FL-цвет"), _zone_column(page, "in_progress"),
        drop=False,
    )
    assert "drop-target" in result["targetClass"], result

    # Цвет пунктира в момент dragover — единый JS-таск (урок regress №7).
    probe = page.evaluate(
        """(taskId) => new Promise((resolve) => {
          const card = document.querySelector(
            'article[data-task-id="' + taskId + '"]');
          const target = document.querySelector(
            '.fastline-column[data-fastline-stage="in_progress"]');
          const dt = new DataTransfer();
          const fire = (el, type) => {
            const ev = new DragEvent(type, {bubbles: true, cancelable: true});
            Object.defineProperty(ev, "dataTransfer", {value: dt});
            el.dispatchEvent(ev);
          };
          fire(card, "dragstart");
          requestAnimationFrame(() => {
            fire(target, "dragover");
            const cs = getComputedStyle(target);
            resolve({outline: cs.outlineColor, cls: target.className,
                     token: getComputedStyle(target)
                       .getPropertyValue("--fastline").trim()});
            fire(card, "dragend");
          });
        })""",
        fast.json()["id"],
    )
    assert "drop-target" in probe["cls"], probe
    # Токен задан hex (#f0b45c), computed — rgb(): сверяем числовые базы.
    hex_rgb = [int(probe["token"].lstrip("#")[i:i + 2], 16)
               for i in (0, 2, 4)]
    computed_rgb = [int(n) for n in
                    probe["outline"].removeprefix("rgb(").removesuffix(")")
                    .split(", ")]
    assert hex_rgb == computed_rgb, probe

    # обычная → столбец канбана: приемник со ступенями «Пульта» (bg3/border-2).
    result = dnd_dispatch(
        page, _card(page, "CB-цвет"), _kanban_column(page, "in_progress"),
        drop=False,
    )
    assert "drop-target" in result["targetClass"], result


# ---------------------------------------------------------------------------
# TC-p23-117 — Негатив: обычная задача не вставляется в занятую зону DnD
# ---------------------------------------------------------------------------
def test_tc_p23_117_plain_blocked_by_occupied_zone(board_page,
                                                   web_owner_session,
                                                   web_base_url,
                                                   web_cleanup_created):
    """TC-p23-117: dragover обычной карты над столбцом ЗААНЯТОЙ зоны —
    drop-forbidden с бейджем запрета и cursor not-allowed; drop НЕ отправляет
    ни одного POST (preventDefault нет, fetch не вызван); CB-тащу осталась
    в канбане со своим статусом."""
    page = board_page
    fast = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "FL-занята", "is_fast": True, "priority": "high"},
    )
    assert fast.status_code == 201, fast.text
    plain = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "CB-тащу"}
    )
    assert plain.status_code == 201, plain.text
    web_cleanup_created(fast.json()["id"])
    web_cleanup_created(plain.json()["id"])
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    posts: list = []
    stop = _track_posts(page, posts)
    result = dnd_dispatch(
        page, _card(page, "CB-тащу"), _zone_column(page, "todo"),
        drop=True,
    )
    assert "drop-forbidden" in result["targetClass"], result
    assert result["dragoverPrevented"] is False, result  # drop не дается
    assert posts == [], [r.url for r in posts]  # счетчик запросов = 0
    expect(_kanban_column(page, "todo").get_by_role("article").filter(
        has_text="CB-тащу")).to_be_visible()

    # cursor not-allowed и бейдж запрета — в момент dragover.
    probe = page.evaluate(
        """(taskId) => new Promise((resolve) => {
          const card = document.querySelector(
            'article[data-task-id="' + taskId + '"]');
          const target = document.querySelector(
            '.fastline-column[data-fastline-stage="todo"]');
          const dt = new DataTransfer();
          const fire = (el, type) => {
            const ev = new DragEvent(type, {bubbles: true, cancelable: true});
            Object.defineProperty(ev, "dataTransfer", {value: dt});
            el.dispatchEvent(ev);
          };
          fire(card, "dragstart");
          requestAnimationFrame(() => {
            fire(target, "dragover");
            const cs = getComputedStyle(target);
            const badge = target.querySelector(".drop-forbidden-badge");
            resolve({cursor: cs.cursor,
                     badge: getComputedStyle(badge).display,
                     badgeCount: target.querySelectorAll(
                       ".drop-forbidden-badge-circle, " +
                       ".drop-forbidden-badge-slash").length});
            fire(card, "dragend");
          });
        })""",
        plain.json()["id"],
    )
    assert probe == {"cursor": "not-allowed", "badge": "flex",
                     "badgeCount": 2}, probe
    stop()


# ---------------------------------------------------------------------------
# TC-p23-118 — Негатив: обычная задача не вставляется и в ПУСТУЮ зону (Э2)
# ---------------------------------------------------------------------------
def test_tc_p23_118_plain_blocked_by_empty_zone(board_page, web_owner_session,
                                                web_base_url,
                                                web_cleanup_created):
    """TC-p23-118 (Э2): ПУСТОЙ столбец зоны — тоже не-приемник: красный
    пунктир без fast-precondition; drop не отправляет запрос; вставка fast —
    только кнопка или edit-форма (move не меняет is_fast)."""
    page = board_page
    plain = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "CB-в-пустую"}
    )
    assert plain.status_code == 201, plain.text
    web_cleanup_created(plain.json()["id"])
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    expect(_zone_column(page, "todo").locator("article")).to_have_count(0)

    posts: list = []
    stop = _track_posts(page, posts)
    result = dnd_dispatch(
        page, _card(page, "CB-в-пустую"), _zone_column(page, "todo")
    )
    assert "drop-forbidden" in result["targetClass"], result
    assert result["dragoverPrevented"] is False, result
    assert posts == [], [r.url for r in posts]
    expect(_kanban_column(page, "todo").get_by_role("article").filter(
        has_text="CB-в-пустую")).to_be_visible()
    expect(_zone_column(page, "todo").locator("article")).to_have_count(0)
    stop()


# ---------------------------------------------------------------------------
# TC-p23-119 — Негатив: fast-карта не перетаскивается на канбан
# ---------------------------------------------------------------------------
def test_tc_p23_119_fast_not_to_kanban(board_page, web_owner_session,
                                       web_base_url, web_cleanup_created):
    """TC-p23-119: канбан — не-приемник для fast-карты (подсветки приемника
    нет ни на одном столбце); drop не отправляет POST /move; fast-карта
    осталась в своем столбце зоны."""
    page = board_page
    fast = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "FL-на-канбан", "is_fast": True, "priority": "high"},
    )
    assert fast.status_code == 201, fast.text
    web_cleanup_created(fast.json()["id"])
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    posts: list = []
    stop = _track_posts(page, posts)
    for status in ("todo", "in_progress", "done"):
        result = dnd_dispatch(
            page, _card(page, "FL-на-канбан"), _kanban_column(page, status),
            drop=True,
        )
        # Канбан для fast-карты — вообще не-приемник: ни подсветки приемника
        # (drop-target), ни красного запрета зоны — классов подсветки нет.
        assert "drop-target" not in result["targetClass"], (status, result)
        assert "drop-forbidden" not in result["targetClass"], (status, result)
        assert result["dragoverPrevented"] is False, (status, result)
    assert posts == [], [r.url for r in posts]
    expect(_zone_column(page, "todo").get_by_role("article").filter(
        has_text="FL-на-канбан")).to_be_visible()
    stop()


# ---------------------------------------------------------------------------
# TC-p23-120 — Гонка двух вкладок: серверный 409 закрывает устаревший гейт
# ---------------------------------------------------------------------------
def test_tc_p23_120_two_tabs_race_409(board_page, page, web_owner_session,
                                      web_base_url, web_cleanup_created):
    """TC-p23-120: при пустой зоне открыты три вкладки одного контекста
    (общая сессия). Вкладка B создает fast; вкладки A (кнопка) и A2
    (edit-форма, чекбокс включен ДО занятия слота) держат устаревший
    клиентский гейт — их сабмиты уходят и получают 409 «fast line occupied»;
    человекочитаемое сообщение показано, доска перерисована из серверного
    состояния (кнопка disabled, чип, FL-гонка в зоне, дублей нет); PATCH-путь
    edit-формы закрывается тем же 409 (не 500, не тихий провал)."""
    page_a = board_page  # вкладка A (путь кнопки) — загружена при пустой зоне
    plain = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "CB-гонка"}
    )
    assert plain.status_code == 201, plain.text
    web_cleanup_created(plain.json()["id"])
    page_a.reload()
    expect(page_a.locator("#board")).to_have_attribute("data-loaded", "true")

    page_a2 = page.context.new_page()  # вкладка A2 (PATCH-путь edit-формы)
    page_b = page.context.new_page()
    try:
        for stale in (page_a2, page_b):
            stale.goto(f"{web_base_url}/board")
            expect(stale.locator("#board")).to_have_attribute(
                "data-loaded", "true")

        # A2 заранее готовит PATCH-путь: edit-форма обычной задачи, чекбокс
        # fast включен при еще пустой зоне (гейт пропускает).
        _card(page_a2, "CB-гонка").click()
        page_a2.get_by_role("button", name="Редактировать").click()
        page_a2.locator("#task-is-fast").check()

        # Вкладка B: кнопка активна, создание fast — слот занят.
        expect(page_b.locator("#fastline-add-button")).to_be_enabled()
        page_b.locator("#fastline-add-button").click()
        page_b.get_by_label("Название").fill("FL-гонка")
        page_b.locator("#task-form-submit").click()
        expect(page_b.locator("#task-form-overlay")).to_be_hidden()
        expect(_zone_column(page_b, "todo").get_by_role("article").filter(
            has_text="FL-гонка")).to_be_visible()
        # Fast создана UI-ом вкладки B — берем id из API на cleanup
        # (иначе занятый слот отравляет следующие тесты сессии).
        board = web_owner_session.get(f"{web_base_url}/api/board").json()
        race_fast = [t for tasks in board["columns"].values() for t in tasks
                     if t["is_fast"]]
        assert [t["title"] for t in race_fast] == ["FL-гонка"], board
        web_cleanup_created(race_fast[0]["id"])

        # Вкладка A (путь кнопки, устаревшее состояние): сабмит → 409.
        expect(page_a.locator("#fastline-add-button")).to_be_enabled()
        page_a.locator("#fastline-add-button").click()
        page_a.get_by_label("Название").fill("FL-гонка-А")
        with page_a.expect_response(
            lambda r: r.request.method == "POST" and r.url.endswith("/api/tasks")
        ) as resp_info:
            page_a.locator("#task-form-submit").click()
        assert resp_info.value.status == 409, resp_info.value.text
        expect(page_a.locator("#task-form-error")).to_be_visible()
        # Человекочитаемое сообщение переформулировано под зону (api.js).
        assert "уже есть задача" in (
            page_a.locator("#task-form-error").inner_text().lower())
        page_a.locator("#task-form-cancel").click()
        expect(page_a.locator("#task-form-overlay")).to_be_hidden()

        # Доска A перерисована из серверного состояния: гейт закрыт, дублей нет.
        expect(page_a.locator("#fastline-add-button")).to_be_disabled()
        expect(page_a.locator("#fastline-blocked-hint")).to_be_visible()
        expect(page_a.locator("#fastline-blocked-hint")).to_contain_text(
            "уже есть задача")
        expect(_zone_column(page_a, "todo").get_by_role("article").filter(
            has_text="FL-гонка")).to_have_count(1)

        # Вкладка A2 (PATCH-путь edit-формы, чекбокс с устаревшего гейта).
        with page_a2.expect_response(
            lambda r: r.request.method == "PATCH"
            and f"/api/tasks/{plain.json()['id']}" in r.url
        ) as patch_info:
            page_a2.locator("#task-form-submit").click()
        assert patch_info.value.status == 409, patch_info.value.text
        expect(page_a2.locator("#task-form-error")).to_be_visible()
        assert "уже есть задача" in (
            page_a2.locator("#task-form-error").inner_text().lower())
    finally:
        page_a2.close()
        page_b.close()


# ---------------------------------------------------------------------------
# TC-p23-121 — XSS через названия задач не исполняется
# ---------------------------------------------------------------------------
def test_tc_p23_121_xss_titles_rendered_as_text(board_page, web_owner_session,
                                                web_base_url,
                                                web_cleanup_created):
    """TC-p23-121: названия с векторами XSS рендерятся ТЕКСТОМ (текстовые
    узлы renderCard/el): ни один alert не исполняется, ошибок в консоли нет,
    атрибутов onerror/onload/onmouseover в DOM нет; разметка зоны (шапка
    FASTLINE, чип) не инъектируется содержимым title; <b> из UI-создания
    показан как текст."""
    page = board_page
    xss_fast = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={
            "title": "<script>alert(1)</script><img src=x onerror=alert(2)>",
            "is_fast": True,
            "priority": "high",
        },
    )
    assert xss_fast.status_code == 201, xss_fast.text
    xss_plain = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": '<svg onload=alert(3)>"onmouseover=alert(4)'},
    )
    assert xss_plain.status_code == 201, xss_plain.text
    web_cleanup_created(xss_fast.json()["id"])
    web_cleanup_created(xss_plain.json()["id"])

    dialogs: list[str] = []
    console_errors: list[str] = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.on("console", lambda m: console_errors.append(m.text)
            if m.type == "error" else None)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    page.wait_for_timeout(500)

    assert dialogs == [], dialogs
    assert console_errors == [], console_errors

    titles = page.evaluate(
        """() => [...document.querySelectorAll('article .task-card-title')]
             .map(el => el.textContent)"""
    )
    assert "<script>alert(1)</script><img src=x onerror=alert(2)>" in titles, titles
    assert '<svg onload=alert(3)>"onmouseover=alert(4)' in titles, titles
    injected = page.evaluate(
        """() => ({
             handlers: document.querySelectorAll(
               "[onerror], [onload], [onmouseover], [onclick]").length,
             scripts: document.querySelectorAll("#fastline script").length,
             imgs: document.querySelectorAll("#fastline img[src='x']").length,
             svgs: document.querySelectorAll("svg[onload]").length,
           })"""
    )
    assert injected == {"handlers": 0, "scripts": 0, "imgs": 0,
                        "svgs": 0}, injected

    # Шаг 4: <b>жирный</b> через UI-форму — текст, не разметка.
    page.get_by_role("button", name="Создать задачу").click()
    page.get_by_label("Название").fill("<b>жирный</b>")
    page.locator("#task-form-submit").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    bold = _card(page, "<b>жирный</b>").locator(".task-card-title")
    expect(bold).to_have_text("<b>жирный</b>")
    assert bold.locator("b").count() == 0
