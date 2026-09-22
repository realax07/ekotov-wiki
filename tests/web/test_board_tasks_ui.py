"""Домен board/tasks (создание, признаки, комментарии): TC-UI-006…009, 012…015.

Regression TC-UI-006/013/015 — продовые дефекты 2026-09-19 (фикс 79ceb7b):
модалки скрыты при загрузке, запросы на /api/tasks/null/* не уходят.
ID-локаторы #task-form-overlay / #task-detail-overlay — разрешены кейсом
(соглашение п.3): скрытые hidden-модалки не имеют ARIA-роли.
"""

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui, move_via_card_select

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def test_modals_hidden_on_board_load(page, web_base_url, board_page, web_cleanup_created):
    """TC-UI-006: REGRESSION 2026-09-19(a) — модалки скрыты при загрузке
    доски (hidden-атрибут у обеих оберток), ничто не перекрывает карточку,
    форма создания открывается только по кнопке."""
    # Предусловие: одна задача в «Ожидает» (создана через UI, TC-UI-007).
    create_task_via_ui(board_page, "Модалки-фон")
    card = board_page.get_by_role("article").filter(has_text="Модалки-фон")
    expect(card).to_be_visible()

    # Шаг 1: чистая загрузка доски без единого клика по модалкам.
    board_page.get_by_role("button", name="Выйти").click()
    board_page.get_by_role("heading", name="Вход").wait_for()
    board_page.goto(f"{web_base_url}/login")
    board_page.get_by_label("Логин").fill("owner")
    board_page.get_by_label("Пароль").fill("QaOwner_Pass_1!")
    board_page.get_by_role("button", name="Войти").click()
    expect(board_page.get_by_role("heading", name="Доска", exact=True)).to_be_visible()
    expect(board_page.locator("#board")).to_have_attribute("data-loaded", "true")

    # Шаг 2: обе обертки скрыты сразу после загрузки.
    expect(board_page.locator("#task-form-overlay")).to_be_hidden()
    expect(board_page.locator("#task-detail-overlay")).to_be_hidden()

    # Шаг 3: hidden-атрибут присутствует в DOM (не только display).
    assert board_page.locator("#task-form-overlay").get_attribute("hidden") is not None
    assert board_page.locator("#task-detail-overlay").get_attribute("hidden") is not None

    # Шаги 4–5: клик по карточке доходит до карточки (не перекрыта).
    card = board_page.get_by_role("article").filter(has_text="Модалки-фон")
    detail_id = _card_task_id(card)
    web_cleanup_created(detail_id)
    card.click()
    expect(board_page.get_by_role("heading", name="Модалки-фон")).to_be_visible()
    board_page.get_by_role("button", name="Закрыть").click()
    expect(board_page.locator("#task-detail-overlay")).to_be_hidden()

    # Шаг 6: форма создания открывается по кнопке, не «сама».
    board_page.get_by_role("button", name="Создать задачу").click()
    expect(board_page.get_by_role("heading", name="Создание задачи")).to_be_visible()
    board_page.get_by_role("button", name="Отмена").click()
    expect(board_page.locator("#task-form-overlay")).to_be_hidden()


def test_create_task_title_only(page, web_base_url, board_page, web_cleanup_created):
    """TC-UI-007: создание задачи только с названием — модалка закрылась,
    карточка в «Ожидает» (todo), признаки не заполнены."""
    create_task_via_ui(board_page, "Только-название")

    column = board_page.locator('[data-status="todo"]')
    card = column.get_by_role("article").filter(has_text="Только-название")
    expect(card).to_be_visible()
    web_cleanup_created(_card_task_id(card))

    # Открыть карточку кликом → признаки пусты.
    card.click()
    expect(board_page.locator("#task-detail-overlay")).to_be_visible()
    for term in ("Описание", "Приоритет", "Категория", "Срок", "Теги"):
        expect(
            board_page.locator("#task-detail-attrs").get_by_text(term)
        ).to_have_count(0)
    board_page.get_by_role("button", name="Закрыть").click()


def _card_task_id(card) -> int:
    """id задачи из data-task-id карточки (renderCard, board.js)."""
    value = card.get_attribute("data-task-id")
    assert value is not None, "у карточки нет data-task-id"
    return int(value)


def test_create_task_without_title_rejected(page, web_base_url, board_page, web_cleanup_created):
    """TC-UI-008: создание без названия отклонено ДО отправки — сообщение
    (нативная required-валидация ИЛИ #task-form-error), POST /api/tasks
    не уходит, форма открыта, задача не создана."""
    requests_made = []
    board_page.on(
        "request",
        lambda r: requests_made.append(r.url)
        if "/api/tasks" in r.url and r.method == "POST"
        else None,
    )

    board_page.get_by_role("button", name="Создать задачу").click()
    board_page.get_by_label("Описание").fill("без названия")
    board_page.get_by_role("button", name="Создать", exact=True).click()

    # Фактический механизм (любой из двух допустимых кейсом).
    native_message = board_page.get_by_label("Название").evaluate("el => el.validationMessage")
    js_error_visible = board_page.locator("#task-form-error").is_visible()
    assert native_message or js_error_visible, (
        f"ни нативной required-подсказки ({native_message!r}), ни #task-form-error"
    )
    if native_message:
        print(f"[TC-UI-008] механизм: нативная валидация required: {native_message!r}")
    else:
        print(
            "[TC-UI-008] механизм: JS #task-form-error:",
            board_page.locator("#task-form-error").inner_text(),
        )

    # Форма осталась открыта, POST /api/tasks не ушел.
    expect(board_page.locator("#task-form-overlay")).to_be_visible()
    assert requests_made == [], f"POST /api/tasks ушел: {requests_made}"

    board_page.get_by_role("button", name="Отмена").click()
    expect(board_page.get_by_role("article").filter(has_text="без названия")).to_have_count(0)


def test_all_attributes_create_view_edit(page, web_base_url, board_page, web_cleanup_created):
    """TC-UI-009: все признаки задачи — создание → карточка → редактирование;
    новые значения видны в карточке и на доске, старые исчезли."""
    create_task_via_ui(
        board_page,
        "Полная",
        description="Проверка признаков e2e",
        priority="high",
        category="Дом",
        due_date="2026-09-30",
        tags="дом, срочно",
    )
    card = board_page.get_by_role("article").filter(has_text="Полная")
    expect(card).to_be_visible()
    web_cleanup_created(_card_task_id(card))

    # Шаг 2–3: все 5 признаков в карточке ровно введенными значениями.
    # (attrs показывает сырые значения задачи — контракт утвержденного
    # e2e TC-UI-009; бейджи «Высокий/Средний» — карточка доски, FR-29.)
    card.click()
    attrs = board_page.locator("#task-detail-attrs")
    expect(attrs).to_be_visible()
    for value in ("Проверка признаков e2e", "high", "Дом", "2026-09-30", "дом, срочно"):
        expect(attrs.get_by_text(value, exact=True)).to_be_visible()
    # Бейдж приоритета на карточке доски — локализованный (FR-29, CHK-144).
    expect(card.get_by_text("Высокий", exact=True)).to_be_visible()

    # Шаг 4: редактирование.
    board_page.get_by_role("button", name="Редактировать").click()
    expect(board_page.get_by_role("heading", name="Редактирование задачи")).to_be_visible()
    board_page.get_by_label("Приоритет").select_option("medium")
    # Категория — select из справочника (FR-19/FR-30; select_option вместо
    # fill — CHK-144/TC-UI-009-update; «Работа» гарантирована seed, CHK-139).
    board_page.get_by_label("Категория").select_option("Работа")
    board_page.get_by_label("Теги (через запятую)").fill("дом")
    board_page.get_by_role("button", name="Сохранить").click()
    expect(board_page.locator("#task-form-overlay")).to_be_hidden()

    # Шаг 5: рефреш доски, переоткрытие карточки.
    expect(board_page.locator("#board")).to_have_attribute("data-loaded", "true")
    board_page.get_by_role("article").filter(has_text="Полная").click()
    attrs = board_page.locator("#task-detail-attrs")
    for value in ("medium", "Работа", "дом"):
        expect(attrs.get_by_text(value, exact=True)).to_be_visible()
    expect(attrs.get_by_text("high", exact=True)).to_have_count(0)
    expect(attrs.get_by_text("срочно")).to_have_count(0)
    board_page.get_by_role("button", name="Закрыть").click()

    # Шаг 7: бейдж приоритета на карточке доски — локализованный «Средний»
    # (CHK-144/TC-UI-009-update; «medium» на карточке больше не выводится).
    board_card = board_page.get_by_role("article").filter(has_text="Полная")
    expect(board_card.get_by_text("Средний", exact=True)).to_be_visible()
    expect(board_card.get_by_text("Высокий", exact=True)).to_have_count(0)


def test_move_between_columns_and_quick_done(page, web_base_url, board_page, web_cleanup_created):
    """TC-UI-012: перемещение по цепочке todo → in_progress → done →
    in_progress → todo → done → todo; на каждом шаге карточка ровно в одном
    столбце; быстрые переходы (Ожидает → Выполнено) работают."""
    create_task_via_ui(board_page, "Перемещаемая")
    card = board_page.locator('[data-status="todo"]').get_by_role("article").filter(
        has_text="Перемещаемая"
    )
    expect(card).to_be_visible()
    web_cleanup_created(_card_task_id(card))

    chain = ["in_progress", "done", "in_progress", "todo", "done", "todo"]
    for status in chain:
        move_via_card_select(board_page, "Перемещаемая", status)
        column = board_page.locator(f'[data-status="{status}"]')
        expect(
            column.get_by_role("article").filter(has_text="Перемещаемая")
        ).to_be_visible()
        # Карточка ровно в одном столбце.
        for other in ("todo", "in_progress", "done"):
            if other != status:
                expect(
                    board_page.locator(f'[data-status="{other}"]').get_by_role(
                        "article"
                    ).filter(has_text="Перемещаемая")
                ).to_have_count(0)

    # Финальный статус — todo (предусловие TC-UI-013/015).
    expect(
        board_page.locator('[data-status="todo"]')
        .get_by_role("article")
        .filter(has_text="Перемещаемая")
    ).to_be_visible()


def test_move_without_selected_card_no_request(page, web_base_url, board_page, web_cleanup_created):
    """TC-UI-013: REGRESSION 2026-09-19(c) — перенос без выбранной карточки:
    запрос /api/tasks/null/move НЕ уходит (guard), 422 нет, доска не сломана,
    обычное перемещение после «пустого» события работает."""
    # Предусловие: задача «Перемещаемая» в «Ожидает».
    create_task_via_ui(board_page, "Перемещаемая")
    card = board_page.locator('[data-status="todo"]').get_by_role("article").filter(
        has_text="Перемещаемая"
    )
    expect(card).to_be_visible()
    web_cleanup_created(_card_task_id(card))

    null_moves = []
    responses_422 = []
    board_page.on(
        "request",
        lambda r: null_moves.append(r.url) if "/api/tasks/null/move" in r.url else None,
    )
    board_page.on(
        "response",
        lambda r: responses_422.append(r.url)
        if r.status == 422 and "/api/tasks/" in r.url
        else None,
    )

    # Шаг 1: продовый путь currentTaskId=null — программное событие change
    # на скрытом контроле «Столбец» (кейс, шаг 1 дословно).
    board_page.evaluate("document.getElementById('task-move-select').value = 'done'")
    board_page.evaluate(
        "document.getElementById('task-move-select')"
        ".dispatchEvent(new Event('change'))"
    )

    # Шаг 2: автожидание окна на ушедший запрос.
    expect(board_page.locator("#board")).to_have_attribute("data-loaded", "true")
    expect(
        board_page.get_by_role("article").filter(has_text="Перемещаемая")
    ).to_be_visible()
    assert null_moves == [], f"запрос /api/tasks/null/move ушел: {null_moves}"
    assert responses_422 == [], f"422 на /api/tasks/*: {responses_422}"

    # Шаг 3: доска не сломана.
    assert board_page.locator("#board").get_attribute("data-loaded") == "true"
    expect(board_page.locator("#board-error")).to_be_hidden()
    expect(
        board_page.locator('[data-status="todo"]')
        .get_by_role("article")
        .filter(has_text="Перемещаемая")
    ).to_be_visible()

    # Шаг 4: контроль живости — обычное перемещение работает.
    move_via_card_select(board_page, "Перемещаемая", "in_progress")
    expect(
        board_page.locator('[data-status="in_progress"]')
        .get_by_role("article")
        .filter(has_text="Перемещаемая")
    ).to_be_visible()


def test_add_comment_persists(page, web_base_url, board_page, web_cleanup_created):
    """TC-UI-014: комментарий к задаче — добавление, очистка поля,
    сохранение после переоткрытия карточки."""
    # Предусловие: задача «Полная» с признаками (TC-UI-009).
    create_task_via_ui(
        board_page, "Полная", description="Проверка признаков e2e", priority="high"
    )
    card = board_page.get_by_role("article").filter(has_text="Полная")
    expect(card).to_be_visible()
    web_cleanup_created(_card_task_id(card))

    card.click()
    expect(board_page.get_by_role("heading", name="Комментарии")).to_be_visible()
    board_page.get_by_label("Новый комментарий").fill("Коммент первый")
    board_page.get_by_role("button", name="Добавить комментарий").click()
    expect(
        board_page.locator("#task-comments-list").get_by_text("Коммент первый")
    ).to_be_visible()
    assert board_page.get_by_label("Новый комментарий").input_value() == ""

    board_page.get_by_role("button", name="Закрыть").click()
    expect(board_page.locator("#task-detail-overlay")).to_be_hidden()
    board_page.get_by_role("article").filter(has_text="Полная").click()
    expect(
        board_page.locator("#task-comments-list").get_by_text("Коммент первый")
    ).to_be_visible()
    board_page.get_by_role("button", name="Закрыть").click()


def test_comment_submit_without_card_no_request(page, web_base_url, board_page, web_cleanup_created):
    """TC-UI-015: REGRESSION 2026-09-19(b) — submit комментария без карточки:
    запрос /api/tasks/null/comments НЕ уходит (guard), понятное сообщение
    «Карточка задачи не открыта…», доска работает, ложного комментария нет."""
    # Предусловие: задача «Перемещаемая» на доске.
    create_task_via_ui(board_page, "Перемещаемая")
    card = board_page.locator('[data-status="todo"]').get_by_role("article").filter(
        has_text="Перемещаемая"
    )
    expect(card).to_be_visible()
    web_cleanup_created(_card_task_id(card))

    null_comments = []
    responses_422 = []
    board_page.on(
        "request",
        lambda r: null_comments.append(r.url)
        if "/api/tasks/null/comments" in r.url
        else None,
    )
    board_page.on(
        "response",
        lambda r: responses_422.append(r.url)
        if r.status == 422 and "/api/tasks/" in r.url
        else None,
    )

    # Шаг 1: продовый путь — requestSubmit формы комментария при
    # currentTaskId=null (кейс, шаг 1 дословно).
    board_page.evaluate("document.getElementById('comment-body').value = 'регресс-коммент'")
    board_page.evaluate("document.getElementById('comment-form').requestSubmit()")

    # Шаг 2: автожидание окна на ушедший запрос.
    expect(
        board_page.get_by_role("article").filter(has_text="Перемещаемая")
    ).to_be_visible()
    assert null_comments == [], f"запрос /api/tasks/null/comments ушел: {null_comments}"
    assert responses_422 == [], f"422 на /api/tasks/*: {responses_422}"

    # Шаг 3: понятное сообщение guard'а (DOM #comment-error).
    comment_error = board_page.evaluate(
        "document.getElementById('comment-error').textContent"
    )
    assert "Карточка задачи не открыта" in comment_error, f"текст: {comment_error!r}"

    # Шаг 4: целостность — карточка открывается, комментария «регресс-коммент» нет.
    board_page.get_by_role("article").filter(has_text="Перемещаемая").click()
    expect(board_page.locator("#task-detail-overlay")).to_be_visible()
    expect(
        board_page.locator("#task-comments-list").get_by_text("регресс-коммент")
    ).to_have_count(0)
    board_page.get_by_role("button", name="Закрыть").click()
