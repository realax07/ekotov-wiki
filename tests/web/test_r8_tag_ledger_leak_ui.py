"""review add-ui-polish-r8 #49 (blocker): мини-тест утечки committed-леджера
комбобокса тегов (тег-combobox.js ↔ task-form.js).

Сценарий из ревью (node-симуляция tag-ledger-leak-sim.js — тот же флоу
в реальном браузере): редактирование задачи A (теги X,Y + выбор Z из
дропдауна) → «Сохранить» → редактирование задачи B (тег P) →
«Сохранить» БЕЗ правок. Утечка = PATCH B содержит «Z» (тихий перенос
тега в чужую задачу через committed-леджер, переживший закрытие формы:
resetCommittedFromInput срабатывает только в closeTagHints и падает на
непустом после сабмита input; фикс — безусловный resetTagLedger() в
fillTaskForm/openCreateForm/openEditForm/closeTaskForm).

Перехват сети (прием TC-r6-comb-009): GET /api/suggestions?kind=tags
мокается детерминированным множеством — на снапшоте ветки эндпоинт
подсказок отвечает 404 (backend-задача 1.1 не смержена; деградация
СЦ-5 не дает открыть дропдаун вовсе, что честно, но к проверяемому
дефекту не относится). PATCH /api/tasks/{id_b} ловится БЕЗ порчи
данных: continue_ — запрос уходит на сервер с реальным ответом,
задача B не меняется (контроль чтением после сабмита).
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

LEAK_TAG = "QATlkgZ"
BASE_TAGS = ["QATlkgX", "QATlkgY"]
B_TAG = "QATlkgP"
SUGGESTIONS = [LEAK_TAG, B_TAG]


def _seed_task(web_owner_session, web_base_url, title, tags):
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": title, "tags": tags}
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _open_edit(page, web_base_url, title, first_load=False):
    """Карточка → view-модалка (r4 Д-9) → «Редактировать» → task-form.

    first_load=False (переоткрытие): БЕЗ page.goto — committed-леджер
    живет в ES-модуле, переживает закрытие формы только в рамках одной
    жизни страницы; перезагрузка страницы обнуляла бы его сама и
    обесценивала проверку межформенной утечки (#49)."""
    if first_load:
        page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    card = page.get_by_role("article").filter(has_text=title).first
    card.click()
    expect(page.locator("#task-detail-overlay")).to_be_visible()
    page.get_by_role("button", name="Редактировать").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()


# regression: keep — review add-ui-polish-r8 #49: открытие/закрытие формы
# сбрасывает committed-леджер комбобокса — тег, выбранный в задаче A, не
# дописывается в PATCH задачи B (межформенная утечка).
def test_combobox_ledger_does_not_leak_between_tasks(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """A (теги X,Y + выбор Z) → сохранить → B (тег P) → сохранить:
    PATCH B не содержит Z."""
    page = logged_in_page

    id_a = _seed_task(
        web_owner_session, web_base_url, "QAT-ledger-A", BASE_TAGS
    )
    id_b = _seed_task(
        web_owner_session, web_base_url, "QAT-ledger-B", [B_TAG]
    )
    web_cleanup_created(id_a)
    web_cleanup_created(id_b)

    # Детерминированные подсказки (см. докстринг модуля).
    def _mock_suggestions(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body='{"suggestions": [%s]}'
            % ", ".join(f'"{tag}"' for tag in SUGGESTIONS),
        )

    page.route("**/api/suggestions*", _mock_suggestions)

    captured: dict = {}

    def _catch_patch_b(route):
        """Только PATCH (GET задачи B — служебные чтения view/формы —
        идут мимо перехвата): тело логируется, запрос продолжается
        реальным обработчиком — данные задачи B не меняются."""
        if route.request.method == "PATCH":
            captured["patch_b"] = route.request.post_data_json
        route.continue_()

    def _arm_capture():
        page.route(f"**/api/tasks/{id_b}", _catch_patch_b)

    # Перехват ставится ПЕРЕД каждым «Сохранить» и снимается после:
    # route, зарегистрированный на всё время теста, перебивает
    # service-worker-независимые GET той же задачи (в т.ч. «Сетевая
    # ошибка» наблюдалась при гонке route/continue с невинным GET).
    _arm_capture()

    # --- Задача A: теги X,Y в форме, выбираем Z из дропдауна. ---
    _open_edit(page, web_base_url, "QAT-ledger-A", first_load=True)
    tags = page.get_by_label("Теги (через запятую)")
    assert BASE_TAGS[0] in tags.input_value()
    # Токен ввода — текст после последней запятой («QATlkgY»), поэтому
    # дропдаун при простом клике отфильтрован до нуля. Замыкающая
    # запятая опустошает токен (обычный жест пользователя) — список
    # подсказок полный, минус уже введенные.
    tags.fill(", ".join(BASE_TAGS) + ",")
    tags.click()
    option_z = page.locator(f'#task-tag-combobox [data-value="{LEAK_TAG}"]')
    expect(option_z).to_be_visible()
    option_z.click()
    # FR-92: committed-выбор — чип Z есть, токен из поля убран.
    expect(page.locator("#task-tags-chips .chip")).to_have_count(3)

    page.get_by_role("button", name="Сохранить").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    page.unroute(f"**/api/tasks/{id_b}")

    # --- Задача B: открыть и сохранить БЕЗ правок (та же страница —
    # леджер задачи A обязан умереть на закрытии/переоткрытии формы). ---
    _open_edit(page, web_base_url, "QAT-ledger-B")
    tags_b = page.get_by_label("Теги (через запятую)")
    assert B_TAG in tags_b.input_value()
    assert LEAK_TAG not in tags_b.input_value(), (
        "тег Z из задачи A утек в input задачи B"
    )
    _arm_capture()
    page.get_by_role("button", name="Сохранить").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    page.unroute(f"**/api/tasks/{id_b}")

    # --- ГЛАВНАЯ проверка: PATCH B не несет тег задачи A. ---
    assert "patch_b" in captured, "PATCH задачи B не перехвачен"
    patch_b_tags = captured["patch_b"].get("tags")
    assert patch_b_tags == [B_TAG], (
        f"утечка committed-леджера: PATCH B несет {patch_b_tags!r}, "
        f"ожидалось {[B_TAG]}"
    )

    # Контроль факта на сервере (перехват не портил данные).
    resp = web_owner_session.get(f"{web_base_url}/api/tasks/{id_b}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["tags"] == [B_TAG], resp.json()["tags"]
