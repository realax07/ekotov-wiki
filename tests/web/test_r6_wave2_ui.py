"""r6 волна 2: единая зона действий (3.1, FR-63), Escape-закрытие формы
(4.2, FR-61), адаптив формы ≤480px (4.3, FR-62).

3.1 (FR-63, ОГР-28, эталон design/tag-combobox-v3.html «Единая зона
действий»): в режиме редактирования селект «Столбец», «Сохранить»,
«Отмена», «Удалить» — в ОДНОМ визуальном ряду-блоке внизу формы; порядок
по макету; «Удалить» — destructive, прижата вправо (margin-left:auto) и
отделена разделителем ::before; в создании блок #task-actions (режимная
часть) скрыт — ряд [Создать][Отмена]. id прежние (ОГР-28):
task-move-select, task-delete-button, task-form-submit, task-form-cancel.

4.2 (FR-61): Escape закрывает форму (аналог «Отмены», на сервер ничего
не уходит): чистая — сразу, грязная — после confirm (диалог мокается
page.on("dialog")).

4.3 (FR-62): при 480px форма в одну колонку, поля full-width, без
горизонтальной прокрутки.

TC-ID: TC-r6-wave2-001…004 (по СЦ-8/СЦ-9/СЦ-11 requirements-r6).
"""

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

FORM_OVERLAY = "#task-form-overlay"


def _open_edit_form(page, title: str):
    """Карточка → view → «Редактировать» → открытая форма редактирования."""
    card = page.get_by_role("article").filter(has_text=title)
    card.click()
    page.locator("#task-detail-overlay").wait_for(state="visible")
    page.get_by_role("button", name="Редактировать").click()
    expect(page.locator(FORM_OVERLAY)).to_be_visible()
    expect(
        page.get_by_role("heading", name="Редактирование задачи")
    ).to_be_visible()
    return card


# --------------------------------------------------------------------------
# TC-r6-wave2-001 — 3.1: состав/порядок/один ряд зоны действий (СЦ-11)
# --------------------------------------------------------------------------
# regression: keep — r6 FR-63: единая зона действий; id не менялись.
def test_actions_zone_single_row_order_and_ids(board_page):
    """TC-r6-wave2-001: в редактировании все управление задачей — один
    ряд-блок .task-actions: [Столбец][Сохранить][Отмена][Удалить] —
    bbox-ряд (одна высота, сверху вниз в порядке макета), все элементы —
    внутри одного контейнера; id прежние (ОГР-28)."""
    page = board_page
    create_task_via_ui(page, "QAT-зона-действий")
    _open_edit_form(page, "QAT-зона-действий")

    # Один контейнер: ряд + режимная часть.
    row = page.locator(".task-actions")
    expect(row).to_be_visible()
    task_actions = page.locator("#task-actions")
    expect(task_actions).to_be_visible()

    # id прежние, все — внутри ряда (ОГР-28: подписки/e2e живут).
    move_select = page.locator("#task-move-select")
    submit = page.locator("#task-form-submit")
    cancel = page.locator("#task-form-cancel")
    delete = page.locator("#task-delete-button")
    for locator, desc in (
        (move_select, "task-move-select"),
        (submit, "task-form-submit"),
        (cancel, "task-form-cancel"),
        (delete, "task-delete-button"),
    ):
        expect(locator).to_be_visible()
        assert locator.evaluate(
            "el => !!el.closest('.task-actions')"
        ), f"{desc} вне единой зоны действий"

    # Порядок по макету: Столбец → Сохранить → Отмена → Удалить.
    boxes = [
        locator.bounding_box()
        for locator in (move_select, submit, cancel, delete)
    ]
    assert all(box is not None for box in boxes)
    lefts = [box["x"] for box in boxes]
    assert lefts == sorted(lefts), f"порядок зоны нарушен: {lefts}"

    # Один визуальный ряд: вертикальные центры совпадают (±4px).
    centers = [box["y"] + box["height"] / 2 for box in boxes]
    assert max(centers) - min(centers) <= 4, f"не один ряд: {centers}"

    # Кнопка сабмита в режиме редактирования — «Сохранить» (не «Создать»).
    assert submit.text_content().strip() == "Сохранить"


# --------------------------------------------------------------------------
# TC-r6-wave2-002 — 3.1: destructive «Удалить» прижат вправо и отделен;
# в создании режимная часть скрыта (ряд [Создать][Отмена])
# --------------------------------------------------------------------------
# regression: keep — r6 FR-63: destructive отдельно; создание без зоны.
def test_actions_zone_delete_separated_and_create_mode(board_page):
    """TC-r6-wave2-002: «Удалить» прижата к правому краю ряда
    (margin-left:auto — зазор слева больше межэлементного) и несет
    destructive-цвет токена --status-error; в режиме создания #task-actions
    скрыт, виден только ряд [Создать][Отмена]."""
    page = board_page

    # Режим создания: режимная часть скрыта.
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator(FORM_OVERLAY)).to_be_visible()
    expect(page.locator("#task-actions")).to_be_hidden()
    expect(page.locator("#task-form-submit")).to_be_visible()
    assert (
        page.locator("#task-form-submit").text_content().strip() == "Создать"
    )
    page.get_by_role("button", name="Отмена").click()
    expect(page.locator(FORM_OVERLAY)).to_be_hidden()

    # Режим редактирования: «Удалить» — destructive и прижата вправо.
    create_task_via_ui(page, "QAT-зона-удалить")
    _open_edit_form(page, "QAT-зона-удалить")

    delete = page.locator("#task-delete-button")
    cancel = page.locator("#task-form-cancel")
    row_box = page.locator(".task-actions").bounding_box()
    delete_box = delete.bounding_box()
    cancel_box = cancel.bounding_box()
    assert row_box and delete_box and cancel_box

    # Прижата к правому краю ряда (±8px — padding контейнера);
    # двусторонний ассерт (review-001 №1): переполнение ряда (отрицательный
    # зазор) раньше проходило одностороннюю проверку.
    row_right = row_box["x"] + row_box["width"]
    delete_right = delete_box["x"] + delete_box["width"]
    assert abs(row_right - delete_right) <= 8, (row_right, delete_right)

    # Зазор слева больше межкнопочного gap (8px): разделитель/отступ.
    gap = delete_box["x"] - (cancel_box["x"] + cancel_box["width"])
    assert gap >= 16, f"«Удалить» не отделена отступом: gap={gap}"

    # Разделитель ::before существует и отрисован.
    divider = delete.evaluate(
        """el => {
          const s = getComputedStyle(el, '::before');
          return {content: s.content, width: s.width, bg: s.backgroundColor};
        }"""
    )
    assert divider["content"] not in ("none", "normal"), divider
    assert divider["width"] == "1px", divider
    assert divider["bg"] != "rgba(0, 0, 0, 0)", divider

    # Destructive-цвет: контур кнопки = токен --status-error.
    colors = page.evaluate(
        """() => ({
          border: getComputedStyle(document.getElementById('task-delete-button')).borderColor,
          token: getComputedStyle(document.documentElement).getPropertyValue('--status-error').trim(),
        })"""
    )
    token_rgb = page.evaluate(
        """(token) => {
          const probe = document.createElement('span');
          probe.style.color = token;
          document.body.appendChild(probe);
          const rgb = getComputedStyle(probe).color;
          probe.remove();
          return rgb;
        }""",
        colors["token"],
    )
    assert colors["border"] == token_rgb, colors

    # Подтверждение удаления сохранено: отмена dialog → форма жива.
    page.once(
        "dialog", lambda dialog: dialog.dismiss()
    )
    delete.click()
    expect(page.locator(FORM_OVERLAY)).to_be_visible()


# --------------------------------------------------------------------------
# TC-r6-wave2-003 — 4.2: Escape — чистая сразу, грязная после confirm
# --------------------------------------------------------------------------
# regression: keep — r6 FR-61: Escape-закрытие (СЦ-8).
def test_escape_closes_form_clean_immediately_dirty_with_confirm(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-wave2-003: чистая форма закрывается первым Escape без
    диалога; грязная (правка названия) — диалог «Закрыть без сохранения?»,
    dismiss → форма осталась со значениями, accept → закрыта; задача на
    сервере не изменилась (закрытие — путь «Отмены»)."""
    page = board_page
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-escape-исходное"},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    web_cleanup_created(task_id)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # 1) Чистая форма (создание): Escape — сразу, без диалога.
    # Именованный auto-handler (dismiss): снимаем на шаге 4, чтобы
    # последний confirm ПРИНЯТЬ (dismiss навсегда оставил бы форму
    # открытой — путь «accept» остался бы непроверенным).
    dialogs = []

    def _auto_dismiss(dialog):
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", _auto_dismiss)
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator(FORM_OVERLAY)).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(FORM_OVERLAY)).to_be_hidden()
    assert dialogs == [], f"чистая форма запросила подтверждение: {dialogs}"

    # 2) Грязная форма (редактирование): Escape → confirm.
    _open_edit_form(page, "QAT-escape-исходное")
    title = page.locator("#task-title")
    assert title.input_value() == "QAT-escape-исходное"
    title.fill("QAT-escape-измененное")
    page.keyboard.press("Escape")
    expect(page.locator(FORM_OVERLAY)).to_be_visible()  # еще открыт
    expect(page.get_by_text("Закрыть без сохранения?")).not_to_be_visible()
    assert dialogs == ["Закрыть без сохранения?"], dialogs

    # 3) Отмена подтверждения → форма осталась со значениями.
    page.keyboard.press("Escape")
    # Подсчет диалогов (review-001 №4): повторный Escape обязан открыть
    # НОВЫЙ confirm — без него форма закрылась бы молча (диалогов 2, не 1).
    assert len(dialogs) == 2, dialogs
    assert dialogs[-1] == "Закрыть без сохранения?"
    # диалог уже отклонён auto-handler'ом (dismiss в page.on); текущий
    # Escape — тот же диалог: форма осталась, повторное dismiss не нужно.
    expect(page.locator(FORM_OVERLAY)).to_be_visible()
    assert title.input_value() == "QAT-escape-измененное"

    # 4) Подтверждение → форма закрыта без сохранения.
    # Снимаем dismiss-автохендлер и вешаем accept (с подсчетом — диалог
    # MUST открыться и здесь, review-001 №4): третий Escape открыл
    # НОВЫЙ confirm (диалог модален — открытие возможно только из
    # обработчика, dismissed-диалог уже завершен). Ждем его появление,
    # затем принимаем.
    page.remove_listener("dialog", _auto_dismiss)

    def _accept_and_count(dialog):
        dialogs.append(dialog.message)
        dialog.accept()

    page.on("dialog", _accept_and_count)

    def _wait_for_third_dialog():
        page.keyboard.press("Escape")

    expect(page.locator(FORM_OVERLAY)).to_be_visible()
    _wait_for_third_dialog()
    expect(page.locator(FORM_OVERLAY)).to_be_hidden()
    assert len(dialogs) == 3, dialogs

    # 5) Данные на сервере не изменились (СЦ-8, негативный путь).
    resp = web_owner_session.get(f"{web_base_url}/api/tasks/{task_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "QAT-escape-исходное", resp.json()


# --------------------------------------------------------------------------
# TC-r6-wave2-004 — 4.2/СЦ-8 + 4.3: Escape при открытом дропдауне не
# закрывает форму; 480px — без горизонтальной прокрутки
# --------------------------------------------------------------------------
# regression: keep — r6 FR-61 (дропдаун глотает Escape) + FR-62 (адаптив).
def test_escape_with_dropdown_and_mobile_480(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-wave2-004: (1) открытый дропдаун комбобокса + Escape →
    закрыт только дропдаун, форма жива (stopPropagation не сломан);
    (2) вьюпорт 480×800: форма в одну колонку, поля full-width, ряд
    действий и форма без горизонтальной прокрутки."""
    # Подсказки комбобокса = теги СУЩЕСТВУЮЩИХ задач (GET
    # /api/suggestions?kind=tags): сеем тегированную задачу через API —
    # иначе множество пусто, дропдаун закономерно не открывается
    # (renderDropdown(0) → closeDropdown), и сценарий не про то.
    seeded = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-адаптив-тег-источник", "tags": ["QATадаптивтег"]},
    )
    assert seeded.status_code == 201, seeded.text
    web_cleanup_created(seeded.json()["id"])

    page = board_page
    page.set_viewport_size({"width": 480, "height": 800})
    create_task_via_ui(page, "QAT-адаптив-480")
    _open_edit_form(page, "QAT-адаптив-480")

    # 1) Дропдаун: фокус в «Теги» открывает список; Escape не закрывает форму.
    tags = page.get_by_label("Теги (через запятую)")
    tags.focus()
    expect(page.locator("#task-tag-combobox")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#task-tag-combobox")).to_be_hidden()
    expect(page.locator(FORM_OVERLAY)).to_be_visible()

    # 2) Адаптив: без горизонтальной прокрутки, поля full-width.
    # Дропдаун закрыт и очищен (Escape выше) — меряем форму без него.
    metrics = page.evaluate(
        """() => {
          const doc = document.documentElement;
          const form = document.getElementById('task-form');
          const row = document.querySelector('.task-actions');
          const formRect = form.getBoundingClientRect();
          const fields = [...form.querySelectorAll('input[type="text"], input[type="date"], textarea, select')]
            .filter(el => el.offsetParent !== null && el.type !== 'checkbox'
                          && !el.closest('.task-actions'))
            .map(el => {
              const r = el.getBoundingClientRect();
              return {right: r.right, formRight: formRect.right,
                      formWidth: formRect.width,
                      width: r.width, x: r.x, formX: formRect.x};
            });
          const rowRect = row.getBoundingClientRect();
          // Кнопки зоны (review-001 №5): та же метрика «на всю ширину
          // формы» — в сумме ряд занимает ширину формы (wrap допустим).
          const buttons = [...row.querySelectorAll('button')]
            .filter(el => el.offsetParent !== null)
            .map(el => {
              const r = el.getBoundingClientRect();
              return {right: r.right, formRight: formRect.right, width: r.width};
            });
          const offenders = [...document.querySelectorAll('body *')]
            .filter(el => el.getBoundingClientRect().right > doc.clientWidth + 1)
            .sort((a, b) => b.getBoundingClientRect().right - a.getBoundingClientRect().right)
            .slice(0, 12)
            .map(el => ({cls: String(el.className).slice(0, 40), id: el.id, tag: el.tagName,
                         right: Math.round(el.getBoundingClientRect().right),
                         w: Math.round(el.getBoundingClientRect().width),
                         disp: getComputedStyle(el).display}));
          const branchInfo = ['.content', 'main']
            .map(sel => {
              const el = document.querySelector(sel);
              return el ? {sel, scrollW: el.scrollWidth, clientW: el.clientWidth} : {sel, none: true};
            });
          return {
            scrollW: doc.scrollWidth, clientW: doc.clientWidth,
            formRight: formRect.right, winW: window.innerWidth,
            fields, buttons, rowWrap: rowRect.height > 80, offenders, branchInfo,
          };
        }"""
    )
    assert metrics["scrollW"] <= metrics["clientW"], (
        f"горизонтальная прокрутка: {metrics['scrollW']} > "
        f"{metrics['clientW']}; offenders={metrics['offenders']}; "
        f"branches={metrics['branchInfo']}"
    )
    for index, field in enumerate(metrics["fields"]):
        assert field["right"] <= metrics["formRight"] + 1, (index, field)
        # Full-width (review-001 №5): поле тянется от левого до правого
        # края формы (±1px), а не «шире label» — сравнение с формой.
        assert field["width"] >= 0.9 * field["formWidth"], (
            f"поле {index} не full-width: {field}"
        )
        assert field["x"] <= field["formX"] + 1, (index, field)
    # Кнопки зоны: каждая — до правого края формы (review-001 №5).
    for index, button in enumerate(metrics["buttons"]):
        assert button["right"] <= metrics["formRight"] + 1, (index, button)
    # Кнопки зоны переносятся (wrap) — ряд стал выше одной строки кнопок.
    assert metrics["rowWrap"], "кнопки зоны не переносятся на 480px"
