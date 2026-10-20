"""Домен зоны FASTLINE (p23-fastline; спека specs/p23-fastline/spec.md,
tasks 4.1 — полный чек-лист дельты; волны 2–4).

TC-p23-101: зона над канбаном; пустая — полностью, без подсказок; шапка
  без счетчика (ОВ-1/ОВ-2/ОВ-3).
TC-p23-102: fast только в зоне, обычные только в канбане; кнопка зоны
  открывает форму с предотмеченным fast (2.1).
TC-p23-103: занятая зона — кнопка disabled + чип; выполнение освобождает
  слот, выполненная остается в «Выполнено» зоны (Э1).
TC-p23-104: гейт чекбокса fast в edit-форме (2.5, F1 ревью №1).
TC-p23-105: DnD fast между этапами зоны — РОВНО один POST move на drop
  (3.1, O1 ревью №1).
TC-p23-106: DnD обычной в зону запрещен — красный пунктир + запрет,
  запроса нет (3.3, Э2; пустая зона тоже не-приемник).
TC-p23-107: DnD fast на канбан запрещен — канбан не-приемник.
TC-p23-108: гонка вкладок — кнопка активна на устаревшем GET, сабмит →
  409 «fast line occupied», чип + перерисовка из сервера (2.3, O2).
  Негатив «возврат выполненной fast при новой активной → 409» —
  TC-dnd-103 (test_r3_dnd_ui.py, наследник по tasks 4.4).

Механика DnD — dispatchEvent с общим DataTransfer (dnd_helpers; нативный
HTML5 DnD Playwright не эмулирует).
"""

import pytest
from playwright.sync_api import expect

from tests.web.dnd_helpers import dnd_dispatch

pytestmark = [pytest.mark.web, pytest.mark.must]

FASTLINE_BUSY_TEXT = "В фастлайне уже есть задача — выполните текущую"


def _fast_column(page, status: str):
    return page.locator(
        f'#fastline .fastline-column[data-fastline-stage="{status}"]'
    )


def _column(page, status: str):
    return page.locator(f'#board .board-column[data-status="{status}"]')


def _card(page, title: str):
    return page.get_by_role("article").filter(has_text=title)


def _wait_board(page) -> None:
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")


def _create_fast_via_api(
    page, web_base_url, web_owner_session, web_cleanup_created, title, *, reload=True
):
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": title, "is_fast": True}
    )
    assert created.status_code == 201, created.text
    web_cleanup_created(created.json()["id"])
    if reload:
        page.reload()
        _wait_board(page)
    return created.json()["id"]


# --------------------------------------------------------------------------
# TC-p23-101 — «зона над канбаном, пустая — без подсказок и счетчика» (Must)
# --------------------------------------------------------------------------
def test_fastline_zone_empty_no_hints(board_page):
    """Зона отображается НАД канбаном: подложка/рамка/заголовок FASTLINE,
    3 столбца-этапа; пустая зона — столбцы видны, подсказок нет (класс
    board-column-empty в зоне не ставится), счетчика нет; кнопка активна,
    чип скрыт (мокап v2-empty)."""
    page = board_page
    zone = page.locator("#fastline")
    expect(zone).to_be_visible()
    # Зона ПЕРЕД канбаном в DOM (над ним).
    assert page.evaluate(
        "document.querySelector('#fastline').compareDocumentPosition("
        "document.querySelector('#board')) & Node.DOCUMENT_POSITION_FOLLOWING"
    ), "зона FASTLINE должна предшествовать канбану"

    # Вариант A: подложка + рамка (вычисленный стиль).
    styles = page.evaluate(
        """() => {
          const zone = document.querySelector('#fastline');
          const cs = getComputedStyle(zone);
          return { bg: cs.backgroundColor, border: cs.borderTopStyle };
        }"""
    )
    assert styles["bg"] == "rgb(238, 242, 246)", styles  # --p-blue-050
    assert styles["border"] == "solid", styles

    expect(zone.get_by_role("heading", name="FASTLINE")).to_be_visible()
    # Счетчика НЕТ (ОВ-2).
    assert page.locator(".fastline-count").count() == 0

    # 3 столбца-этапа с заголовками мокапа.
    for status, title in (
        ("todo", "Ожидает"),
        ("in_progress", "В работе"),
        ("done", "Выполнено"),
    ):
        column = _fast_column(page, status)
        expect(column).to_be_visible()
        expect(column.get_by_role("heading", name=title)).to_be_visible()

    # Пустое состояние: без подсказок (ОВ-3).
    assert page.locator("#fastline .board-column-empty").count() == 0
    hints = page.evaluate(
        """() => Array.from(
          document.querySelectorAll('#fastline .fastline-column')
        ).every((col) => getComputedStyle(col, '::before').content === 'none')"""
    )
    assert hints, "в пустых столбцах зоны есть подсказка (::before)"

    expect(page.locator("#fastline-add-button")).to_be_enabled()
    expect(page.locator("#fastline-blocked-hint")).to_be_hidden()


# --------------------------------------------------------------------------
# TC-p23-102 — «fast только в зоне, обычные только в канбане» (Must)
# --------------------------------------------------------------------------
def test_fast_only_in_zone_normal_only_in_kanban(
    board_page, web_cleanup_created
):
    """Создание fast кнопкой зоны (форма с предотмеченным fast, приоритет
    заблокирован high) → карточка в «Ожидает» зоны; обычная задача →
    только в канбане; в зоне обычных нет (мокап v2-busy)."""
    page = board_page

    # Кнопка зоны: форма создания с предотмеченным fast (2.1).
    page.locator("#fastline-add-button").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    fast_cb = page.get_by_label("fast line")
    assert fast_cb.is_checked()
    assert page.get_by_label("Приоритет").input_value() == "high"
    assert page.get_by_label("Приоритет").is_disabled()
    page.get_by_label("Название").fill("QAT-p23-fast")
    page.get_by_role("button", name="Создать", exact=True).click()
    expect(_fast_column(page, "todo").get_by_role("article").filter(
        has_text="QAT-p23-fast"
    )).to_be_visible()
    web_cleanup_created(
        int(_card(page, "QAT-p23-fast").get_attribute("data-task-id"))
    )

    # Обычная задача — через «Создать задачу».
    page.get_by_role("button", name="Создать задачу").click()
    page.get_by_label("Название").fill("QAT-p23-обычная")
    page.get_by_role("button", name="Создать", exact=True).click()
    expect(_column(page, "todo").get_by_role("article").filter(
        has_text="QAT-p23-обычная"
    )).to_be_visible()
    web_cleanup_created(
        int(_card(page, "QAT-p23-обычная").get_attribute("data-task-id"))
    )

    # Разделение: fast НЕ в канбане, обычная НЕ в зоне (data-fast="false"
    # у обычной карточки — атрибут рендера, в зоне статей ровно одна — fast).
    expect(page.locator("#board article[data-fast='true']")).to_have_count(0)
    zone_articles = page.locator("#fastline article")
    expect(zone_articles).to_have_count(1)
    assert "QAT-p23-обычная" not in (zone_articles.first.get_attribute("class") or "")


# --------------------------------------------------------------------------
# TC-p23-103 — «занято: кнопка disabled + чип; выполнение освобождает» (Must)
# --------------------------------------------------------------------------
def test_busy_zone_gates_and_done_frees_slot(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """Занятая зона: кнопка disabled (not-allowed) + чип точно из мокапа
    v2-blocked. Перевод fast в «Выполнено» зоны: слот свободен (кнопка
    активна, чип скрыт), выполненная карточка ОСТАЕТСЯ в «Выполнено»
    зоны до автоархивации (Э1 design §2)."""
    page = board_page
    task_id = _create_fast_via_api(
        page, web_base_url, web_owner_session, web_cleanup_created, "QAT-p23-busy"
    )

    expect(page.locator("#fastline-add-button")).to_be_disabled()
    chip = page.locator("#fastline-blocked-hint")
    expect(chip).to_be_visible()
    assert chip.inner_text().strip() == FASTLINE_BUSY_TEXT, chip.inner_text()

    # Выполнение: drop-эквивалент — move в done (селект-путь тестируется
    # в TC-UI-012/017); здесь суть инварианта слота.
    moved = web_owner_session.post(
        f"{web_base_url}/api/tasks/{task_id}/move", json={"status": "done"}
    )
    assert moved.status_code == 200, moved.text
    page.reload()
    _wait_board(page)

    expect(page.locator("#fastline-add-button")).to_be_enabled()
    expect(chip).to_be_hidden()
    # Выполненная покидает АКТИВНУЮ часть зоны, но остается видимой в
    # «Выполнено» зоны до автоархивации (Э1).
    expect(_fast_column(page, "done").get_by_role("article").filter(
        has_text="QAT-p23-busy"
    )).to_be_visible()


# --------------------------------------------------------------------------
# TC-p23-104 — «гейт чекбокса fast в edit-форме» (Must; 2.5, F1)
# --------------------------------------------------------------------------
def test_edit_form_fast_checkbox_gate(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """Занятая зона: чекбокс fast в edit-форме ОБЫЧНОЙ задачи disabled +
    причина чипом; на самой fast-задаче чекбокс доступен всегда."""
    page = board_page
    _create_fast_via_api(
        page, web_base_url, web_owner_session, web_cleanup_created, "QAT-p23-gate-fast"
    )
    regular = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "QAT-p23-gate-regular"}
    )
    assert regular.status_code == 201, regular.text
    web_cleanup_created(regular.json()["id"])
    page.reload()
    _wait_board(page)

    detail = page.locator("#task-detail-overlay")

    # Обычная задача при занятой зоне: чекбокс disabled + чип-причина.
    _card(page, "QAT-p23-gate-regular").click()
    page.get_by_role("button", name="Редактировать").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    expect(page.get_by_label("fast line")).to_be_disabled()
    gate = page.locator("#task-is-fast-gate")
    expect(gate).to_be_visible()
    assert gate.inner_text().strip() == FASTLINE_BUSY_TEXT
    page.get_by_role("button", name="Отмена").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()

    # Сама fast-задача: чекбокс доступен (выключение освобождает слот,
    # включение идемпотентно — серверный exclude_task_id).
    _card(page, "QAT-p23-gate-fast").click()
    page.get_by_role("button", name="Редактировать").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    expect(page.get_by_label("fast line")).to_be_enabled()
    assert page.get_by_label("fast line").is_checked()
    expect(gate).to_be_hidden()
    page.get_by_role("button", name="Отмена").click()

    # Пустая зона: гейта нет (проверка после освобождения слота).
    delete = web_owner_session.delete(
        f"{web_base_url}/api/tasks/{regular.json()['id']}"
    )
    assert delete.status_code in (200, 204)
    page.reload()
    _wait_board(page)
    _card(page, "QAT-p23-gate-fast").click()
    page.get_by_role("button", name="Редактировать").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    expect(page.get_by_label("fast line")).to_be_enabled()
    expect(page.locator("#task-is-fast-gate")).to_be_hidden()


# --------------------------------------------------------------------------
# TC-p23-105 — «DnD fast между этапами зоны, ровно один POST» (Must; 3.1, O1)
# --------------------------------------------------------------------------
def test_dnd_fast_within_zone_single_move_post(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """Drag fast-карты todo→in_progress внутри зоны (мокап v2-dnd-move):
    столбец-приемник подсвечен (drop-target), статус изменен, карточка в
    «В работе» зоны; РОВНО один POST /move на один drop (квирк двойного
    fire HTML5 DnD, O1)."""
    page = board_page
    _create_fast_via_api(
        page, web_base_url, web_owner_session, web_cleanup_created, "QAT-p23-dnd"
    )
    card = _card(page, "QAT-p23-dnd")
    expect(_fast_column(page, "todo").get_by_role("article").filter(
        has_text="QAT-p23-dnd"
    )).to_be_visible()

    move_requests = []
    page.on(
        "request",
        lambda r: move_requests.append(r.url)
        if "/api/tasks/" in r.url and r.url.endswith("/move") and r.method == "POST"
        else None,
    )

    result = dnd_dispatch(page, card, _fast_column(page, "in_progress"))
    assert "drop-target" in result["targetClass"], result

    expect(_fast_column(page, "in_progress").get_by_role("article").filter(
        has_text="QAT-p23-dnd"
    )).to_be_visible()
    assert len(move_requests) == 1, f"POST move не ровно один: {move_requests}"

    # Сервер: статус действительно in_progress.
    task_id = int(card.get_attribute("data-task-id"))
    body = web_owner_session.get(f"{web_base_url}/api/tasks/{task_id}").json()
    assert body["status"] == "in_progress", body


# --------------------------------------------------------------------------
# TC-p23-106 — «обычная задача не вставляется в зону DnD» (Must; 3.3, Э2)
# Две ветки: занятая зона (F-2 review-001, исходный кейс) и ПУСТАЯ зона —
# запрет по зоне независимо от занятости (dropAllowed не читает busy).
# --------------------------------------------------------------------------
def test_dnd_normal_card_to_fastline_forbidden(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """Drag обычной карты на столбец ЗАНЯТОЙ зоны (мокап v2-dnd-blocked):
    красный пунктир + знак запрета (drop-forbidden), drop-target нет,
    POST move НЕ отправляется, карточка остается в канбане."""
    page = board_page
    _create_fast_via_api(
        page, web_base_url, web_owner_session, web_cleanup_created, "QAT-p23-занято"
    )
    regular = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "QAT-p23-обычная-dnd"}
    )
    assert regular.status_code == 201, regular.text
    regular_id = regular.json()["id"]
    web_cleanup_created(regular_id)
    page.reload()
    _wait_board(page)

    move_requests = []
    page.on(
        "request",
        lambda r: move_requests.append(r.url)
        if "/api/tasks/" in r.url and r.url.endswith("/move") and r.method == "POST"
        else None,
    )

    card = _card(page, "QAT-p23-обычная-dnd")
    result = dnd_dispatch(page, card, _fast_column(page, "todo"))
    assert "drop-forbidden" in result["targetClass"], result
    assert "drop-target" not in result["targetClass"], result
    assert move_requests == [], f"POST move ушел в запрещенную зону: {move_requests}"
    expect(_column(page, "todo").get_by_role("article").filter(
        has_text="QAT-p23-обычная-dnd"
    )).to_be_visible()
    assert web_owner_session.get(
        f"{web_base_url}/api/tasks/{regular_id}"
    ).json()["status"] == "todo"


def test_dnd_normal_card_to_empty_fastline_forbidden(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """Ветка ПУСТОЙ зоны TC-p23-106 (Э2): без fast-precondition — drag
    обычной карты на столбец пустой зоны тоже не-приемник: красный
    пунктир (drop-forbidden), drop-target нет, POST move НЕ отправляется,
    карточка остается в канбане (запрет по ЗОНЕ, не по занятости)."""
    page = board_page
    regular = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": "QAT-p23-обычная-пусто"}
    )
    assert regular.status_code == 201, regular.text
    regular_id = regular.json()["id"]
    web_cleanup_created(regular_id)
    page.reload()
    _wait_board(page)

    # Зона пуста: карточек в столбцах зоны нет, кнопка активна
    # (занятости нет — запрет все равно действует).
    assert page.locator("#fastline .fastline-column article").count() == 0
    expect(page.locator("#fastline-add-button")).to_be_enabled()

    move_requests = []
    page.on(
        "request",
        lambda r: move_requests.append(r.url)
        if "/api/tasks/" in r.url and r.url.endswith("/move") and r.method == "POST"
        else None,
    )

    card = _card(page, "QAT-p23-обычная-пусто")
    result = dnd_dispatch(page, card, _fast_column(page, "todo"))
    assert "drop-forbidden" in result["targetClass"], result
    assert "drop-target" not in result["targetClass"], result
    assert move_requests == [], f"POST move ушел в пустую зону: {move_requests}"
    expect(_column(page, "todo").get_by_role("article").filter(
        has_text="QAT-p23-обычная-пусто"
    )).to_be_visible()
    assert web_owner_session.get(
        f"{web_base_url}/api/tasks/{regular_id}"
    ).json()["status"] == "todo"


# --------------------------------------------------------------------------
# TC-p23-107 — «fast-карта не перетаскивается на канбан» (Must; 3.3)
# --------------------------------------------------------------------------
def test_dnd_fast_card_to_kanban_forbidden(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """Drag fast-карты на столбец канбана: канбан не-приемник (подсветки
    нет, drop невозможен), POST move не отправляется, карточка остается
    в зоне (fast-задача не покидает фастлайн)."""
    page = board_page
    _create_fast_via_api(
        page, web_base_url, web_owner_session, web_cleanup_created, "QAT-p23-fast-канбан"
    )
    card = _card(page, "QAT-p23-fast-канбан")

    move_requests = []
    page.on(
        "request",
        lambda r: move_requests.append(r.url)
        if "/api/tasks/" in r.url and r.url.endswith("/move") and r.method == "POST"
        else None,
    )

    result = dnd_dispatch(page, card, _column(page, "in_progress"))
    assert "drop-target" not in result["targetClass"], result
    assert "drop-forbidden" not in result["targetClass"], result
    assert move_requests == [], f"POST move ушел на канбан: {move_requests}"
    expect(_fast_column(page, "todo").get_by_role("article").filter(
        has_text="QAT-p23-fast-канбан"
    )).to_be_visible()


# --------------------------------------------------------------------------
# TC-p23-108 — «гонка вкладок: 409 закрывает чипом и перерисовкой» (Must; 2.3, O2)
# --------------------------------------------------------------------------
def test_tab_race_create_fast_409_chip_and_refresh(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """Кнопка/чекбокс могли быть активны на устаревшем GET /api/board
    (соперник занял слот через API, наша вкладка не перерисовалась):
    сабмит формы зоны → 409 «fast line occupied»; сообщение чипа у формы;
    после перерисовки чип зоны виден, кнопка disabled, задача соперника в
    зоне; форма открыта, введенное название сохранено."""
    page = board_page
    # Зона пуста: кнопка активна на ЭТОМ снимке доски.
    expect(page.locator("#fastline-add-button")).to_be_enabled()

    # «Вторая вкладка» занимает слот напрямую через API — БЕЗ перезагрузки
    # нашей вкладки: ее доска отрисована пустой (кнопка активна), снимок
    # устарел — как в реальной гонке двух вкладок.
    _create_fast_via_api(
        page, web_base_url, web_owner_session, web_cleanup_created,
        "QAT-p23-гонка", reload=False,
    )

    page.locator("#fastline-add-button").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    page.get_by_label("Название").fill("QAT-p23-гонка-вторая")
    page.get_by_role("button", name="Создать", exact=True).click()

    # 409: сообщение чипа у формы (бокс ошибки формы), форма открыта,
    # данные сохранены.
    form_error = page.locator("#task-form-error")
    expect(form_error).to_be_visible()
    assert form_error.inner_text().strip() == FASTLINE_BUSY_TEXT, form_error.inner_text()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    assert (
        page.get_by_label("Название").input_value() == "QAT-p23-гонка-вторая"
    )
    assert page.get_by_label("fast line").is_checked()

    # Доска перерисована из серверного состояния (handleSubmitError →
    # refreshBoard): чип виден, кнопка disabled, соперник в зоне.
    expect(page.locator("#fastline-blocked-hint")).to_be_visible()
    expect(page.locator("#fastline-add-button")).to_be_disabled()
    expect(_fast_column(page, "todo").get_by_role("article").filter(
        has_text="QAT-p23-гонка"
    )).to_be_visible()
    expect(_card(page, "QAT-p23-гонка-вторая")).to_have_count(0)

    page.get_by_role("button", name="Отмена").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
