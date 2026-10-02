"""r6 QA-контур 5.1: закрытие гэпов покрытия (add-r6-task-form-ux).

Гэпы выявлены сверкой СЦ-1…СЦ-11 / CHK-R6-1…CHK-R6-30 с существующими
сьютами (test-model/impact/add-r6-task-form-ux.md §2–3):

1. **СЦ-9: дропдаун комбобокса на 375px** — test_r6_wave2_ui.py::TC-004
   гоняет адаптив ровно на 480px (граница media-блока); recovery-ревью
   отметило, что задача 4.3 предписывает проверку на ~375px. Здесь:
   375px — одна колонка, поля full-width, БЕЗ горизонтальной прокрутки,
   дропдаун подсказок позиционируется корректно (100% ширины поля,
   не шире вьюпорта) при ОТКРЫТОМ дропдауне.
   → TC-r6-gaps-001 (CHK-R6-17b).

2. **СЦ-8: Escape при открытой view-модалке** — guard «форма открыта,
   view не открыта» (FR-61): форма не открывается и не закрывается,
   view закрывается своей прежней логикой. Существующие тесты покрывают
   чистую/грязную форму и дропдаун, но не ветку view-модалки.
   → TC-r6-gaps-002 (CHK-R6-14).

3. **СЦ-1/СЦ-9: множество ?kind=tags не содержит категорий ПРИ АКТИВНОЙ
   категории** — TC-sugg-r6-002 создает задачу с тегом И категорией
   одновременно, но не фиксирует отсутствие ДРУГОЙ категории справочника
   (seed Дом/Работа/Личное) в kind=tags и не проверяет сценарий формы
   «работает в обоих режимах» на 375px (дропдаун не шире вьюпорта).
   Здесь API-часть: kind=tags исключает ВСЕ категории справочника при
   их активном использовании задачей; kind=categories симметрично.
   → TC-r6-gaps-003 (CHK-R6-1b, дополнение).

Существующие сьюты (покрытие — см. чеклист):
- tests/api/test_suggestions_r6.py   TC-sugg-r6-001…005 (СЦ-1/СЦ-10);
- tests/web/test_r6_tag_combobox_ui.py TC-r6-comb-001…010 (СЦ-1…СЦ-6);
- tests/web/test_r6_wave2_ui.py      TC-r6-wave2-001…004 (СЦ-8/9/11).

TC-ID: TC-r6-gaps-001…002 (web, этот файл) + TC-r6-gaps-003 (API, в
tests/api/test_suggestions_r6.py — фикстуры API-контура там).
Формат: 1 кейс = 1 тест (contract 6).
Маркеры и фикстуры — tests/web/pytest.ini, tests/web/conftest.py.
"""

import pytest
from playwright.sync_api import expect

from tests.web.conftest import create_task_via_ui

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

FORM_OVERLAY = "#task-form-overlay"
LISTBOX = "#task-tag-combobox"
VIEW_OVERLAY = "#task-detail-overlay"


# --------------------------------------------------------------------------
# TC-r6-gaps-001 — СЦ-9/CHK-R6-17b: адаптив 375px (строже границы 480px):
# одна колонка, поля full-width, без h-скролла; ОТКРЫТЫЙ дропдаун
# комбобокса умещается в вьюпорт и не шире поля
# --------------------------------------------------------------------------
# regression: keep — r6 FR-62: проверка на ~375px предписана задачей 4.3;
# существующий TC-r6-wave2-004 гоняет только границу 480px.
def test_form_adaptive_375_with_open_dropdown(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-gaps-001: вьюпорт 375×720 (мобильный, строже границы media
    480px): форма в одну колонку (grid-template-columns: 1fr от media-
    блока; контролы стеком), поля full-width (±1px до края формы),
    документа/оверлея без горизонтальной прокрутки; при ОТКРЫТОМ дропдауне
    подсказок он не шире вьюпорта и не шире поля «Теги» (позиционирование
    корректно — СЦ-9 «дропдаун позиционируется корректно»)."""
    # Подсказки комбобокса = теги существующих задач (?kind=tags) — сеем
    # тегированную задачу, иначе дропдаун закономерно не открывается.
    seeded = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-гэп375-тег-источник", "tags": ["QATгэп375тег"]},
    )
    assert seeded.status_code == 201, seeded.text
    web_cleanup_created(seeded.json()["id"])

    page = board_page
    page.set_viewport_size({"width": 375, "height": 720})
    create_task_via_ui(page, "QAT-гэп375-форма")
    # Карточка → view: на 375px колонки доски живут в h-прокручиваемом
    # ряду (board flex-row вне формы), карточка сжата до ~25px — клик по
    # заголовку вне вьюпорта/нестабилен. Открываем view кликом по самой
    # карточке через DOM (тот же click-обработчик onClickCard).
    page.evaluate(
        """() => {
          const card = [...document.querySelectorAll('article')]
            .find(a => a.textContent.includes('QAT-гэп375-форма'));
          card.click();
        }"""
    )
    expect(page.locator(VIEW_OVERLAY)).to_be_visible()
    page.get_by_role("button", name="Редактировать").click()
    expect(page.locator(FORM_OVERLAY)).to_be_visible()

    # 1) Без горизонтальной прокрутки: документ и оверлей.
    metrics = page.evaluate(
        """() => {
          const doc = document.documentElement;
          const overlay = document.getElementById('task-form-overlay');
          const form = document.getElementById('task-form');
          const formRect = form.getBoundingClientRect();
          const fields = [...form.querySelectorAll(
              'input[type="text"], input[type="date"], textarea, select')]
            .filter(el => el.offsetParent !== null && el.type !== 'checkbox'
                          && !el.closest('.task-actions'))
            .map(el => {
              const r = el.getBoundingClientRect();
              return {right: r.right, x: r.x, width: r.width,
                      formRight: formRect.right, formX: formRect.x,
                      formWidth: formRect.width};
            });
          return {
            scrollW: doc.scrollWidth, clientW: doc.clientWidth,
            overlayScrollW: overlay.scrollWidth,
            overlayClientW: overlay.clientWidth,
            winW: window.innerWidth, fields,
          };
        }"""
    )
    assert metrics["scrollW"] <= metrics["clientW"] + 1, (
        f"горизонтальная прокрутка документа на 375px: {metrics}"
    )
    assert metrics["overlayScrollW"] <= metrics["overlayClientW"] + 1, (
        f"горизонтальная прокрутка оверлея формы на 375px: {metrics}"
    )
    # Поля: full-width — от левого до правого края формы (±1px).
    for index, field in enumerate(metrics["fields"]):
        assert field["right"] <= field["formRight"] + 1, (index, field)
        assert field["x"] <= field["formX"] + 1, (index, field)
        assert field["width"] >= 0.9 * field["formWidth"], (
            f"поле {index} не full-width на 375px: {field}"
        )

    # 2) ОТКРЫТЫЙ дропдаун комбобокса: в вьюпорте, не шире поля «Теги».
    tags = page.get_by_label("Теги (через запятую)")
    tags.click()
    expect(page.locator(LISTBOX)).to_be_visible()
    dropdown = page.evaluate(
        """() => {
          const dd = document.getElementById('task-tag-combobox');
          const input = document.getElementById('task-tags');
          const d = dd.getBoundingClientRect();
          const i = input.getBoundingClientRect();
          return {ddLeft: d.x, ddRight: d.right, ddWidth: d.width,
                  inputLeft: i.x, inputRight: i.right, winW: innerWidth};
        }"""
    )
    assert dropdown["ddLeft"] >= 0, dropdown
    assert dropdown["ddRight"] <= dropdown["winW"] + 1, (
        f"дропдаун шире вьюпорта 375px: {dropdown}"
    )
    assert dropdown["ddWidth"] <= dropdown["inputRight"] - dropdown["inputLeft"] + 1, (
        f"дропдаун шире поля «Теги» на 375px: {dropdown}"
    )

    # 3) Дропдаун живой на 375px: тап по пункту выбирает значение.
    option = page.locator(f'{LISTBOX} [data-value="QATгэп375тег"]')
    expect(option).to_be_visible()
    option.click()
    assert "QATгэп375тег" in tags.input_value()

    # 4) После Escape (закрыт дропдаун) форма по-прежнему без h-скролла —
    # скрытый дропдаун не оставляет переполнения (риск position:absolute).
    page.keyboard.press("Escape")
    expect(page.locator(LISTBOX)).to_be_hidden()
    scroll_after = page.evaluate(
        "() => ({s: document.documentElement.scrollWidth,"
        " c: document.documentElement.clientWidth})"
    )
    assert scroll_after["s"] <= scroll_after["c"] + 1, scroll_after


# --------------------------------------------------------------------------
# TC-r6-gaps-002 — СЦ-8/CHK-R6-14: Escape при открытой view-модалке —
# guard «форма открыта, view не открыта»: view закрывается, форма нет
# --------------------------------------------------------------------------
# regression: keep — r6 FR-61: Escape нормирован и для формы (guard не
# ломает прежнее закрытие view, task-detail.js).
def test_escape_with_open_view_modal_closes_view_not_form(
    board_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-gaps-002: открыта view-модалка карточки (read-only), форма
    задачи закрыта → Escape закрывает view по прежней логике
    (task-detail.js); форма задачи не открывается и не закрывается
    (guard «форма открыта, view не открыта» — r6-обработчик молчит).
    Форма из view: view закрыт, форма открыта — Escape грязной формы
    идет по СВОЕМУ пути (confirm «Закрыть без сохранения?», dismiss →
    форма осталась); данные на сервере не изменились (СЦ-8, FR-61).
    Примечание: в UI модалки взаимоисключающи (openEditForm скрывает
    view) — сценарий «обе открыты» недостижим; guard проверен через
    взаимоисключающие состояния + целостность Escape-поведения."""
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QAT-гэп-view-escape", "priority": "low"},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    web_cleanup_created(task_id)
    page = board_page
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # 1) View-модалка одна (форма закрыта): Escape закрывает view.
    card = page.get_by_role("article").filter(has_text="QAT-гэп-view-escape")
    card.locator("h3").first.click(force=True)
    expect(page.locator(VIEW_OVERLAY)).to_be_visible()
    expect(page.locator(FORM_OVERLAY)).to_be_hidden()
    page.keyboard.press("Escape")
    expect(page.locator(VIEW_OVERLAY)).to_be_hidden()
    expect(page.locator(FORM_OVERLAY)).to_be_hidden()

    # 2) Открыть форму ИЗ view: view закрывается, форма открыта —
    # guard «форма открыта, view не открыта» означает: Escape формы
    # обрабатывается ЕЁ обработчиком (r6), а view-обработчик (task-
    # detail.js) молчит; состояние модалок не «расходится».
    # (После закрытия view кнопка «Редактировать» вне a11y-дерева —
    # view переоткрывается кликом по карточке.)
    card.locator("h3").first.click(force=True)
    expect(page.locator(VIEW_OVERLAY)).to_be_visible()
    page.get_by_role("button", name="Редактировать").click()
    expect(page.locator(FORM_OVERLAY)).to_be_visible()
    expect(page.locator(VIEW_OVERLAY)).to_be_hidden()
    # Escape при грязной форме из view-потока: confirm появляется
    # (диалог автоснимается), форма остается с введенными значениями.
    page.get_by_label("Название").fill("QAT-гэп-view-escape-2")
    dialogs: list[str] = []

    def _auto_dismiss(dialog):
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", _auto_dismiss)
    page.keyboard.press("Escape")
    expect(page.locator(FORM_OVERLAY)).to_be_visible()
    assert dialogs == ["Закрыть без сохранения?"], dialogs
    page.remove_listener("dialog", _auto_dismiss)

    # 3) Данные на сервере не изменились (закрытие — путь «Отмены»;
    # view-модалка не «подхватила» форму и не сохранила ничего).
    resp = web_owner_session.get(f"{web_base_url}/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "QAT-гэп-view-escape"
