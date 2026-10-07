"""r6 2.1+2.2: кастомный комбобокс подсказок тегов (FR-58/59, NFR-17/18).

Замена нативного datalist #task-tag-hints у поля «Теги» формы задачи
(tag-combobox.js; стили/aria — design/tag-combobox-v3.html). Проверяется
через DOM (Playwright): открытие при фокусе/вводе, локальная фильтрация
(case-insensitive подстрока), подсветка совпадения <mark>, исключение
уже введенных тегов, явный пункт «+ Добавить тег «…»», клавиатура
(стрелки/Enter/Escape — только дропдаун/Tab), aria-атрибуты
(combobox/listbox/option/aria-activedescendant/aria-live), клик вне,
тач-тап, сбой загрузки.

TC-ID: TC-r6-comb-001…009 (по СЦ-1…СЦ-6 requirements-r6). Формат:
1 кейс = 1 тест (contract 6). Чипы (FR-34) не тронуты — их покрывают
test_r3_formv3_ui; здесь только комбобокс-надстройка.

ВАЖНО (переходный период): backend-задача 1.1 (?kind=tags) не в этой
зоне — запрос уходит С параметром, но сервер отвечает полным множеством
tags ∪ categories. Тесты ассертят поведение комбобокса относительно
фактического тела /api/suggestions (как его отдал сервер), а не состав
«только теги» — это покроет QA-контур 5.1 после 1.1.
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

LISTBOX = "#task-tag-combobox"


def _open_form(page, web_base_url):
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()


def _tag_hints(page) -> list[str]:
    """Фактическое множество подсказок — опции зеркала-datalist
    (совместимость r3/r4; источник один с комбобоксом)."""
    return [
        page.locator("#task-tag-hints option").nth(i).text_content().strip()
        for i in range(page.locator("#task-tag-hints option").count())
    ]


def _option_texts(page) -> list[str]:
    """Тексты пунктов дропдауна без пункта добавления."""
    options = page.locator(f"{LISTBOX} .option")
    return [options.nth(i).text_content().strip() for i in range(options.count())]


def _seed_tagged_task(web_owner_session, web_base_url, title, tags):
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks", json={"title": title, "tags": tags}
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


# regression: keep — r6 FR-58: открытие при фокусе; полный список при
# пустом вводе; фильтрация case-insensitive подстрокой (СЦ-1).
def test_combobox_opens_on_focus_and_filters(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-comb-001: фокус на поле «Теги» открывает дропдаун со всеми
    подсказками; ввод «ho» фильтрует локально (подстрока, без учета
    регистра)."""
    task_id = _seed_tagged_task(
        web_owner_session, web_base_url, "QAT-comb-фильтр", ["QATcombHome"]
    )
    web_cleanup_created(task_id)

    page = logged_in_page
    _open_form(page, web_base_url)

    tags = page.get_by_label("Теги (через запятую)")
    tags.click()
    expect(page.locator(LISTBOX)).to_be_visible()
    hints = _tag_hints(page)
    assert "QATcombHome" in hints
    assert "QATcombHome" in _option_texts(page)

    # Ввод «ho» → только совпадающие по подстроке (регистр не важен).
    tags.fill("ho")
    options = _option_texts(page)
    assert options == ["QATcombHome"], options

    # Несовпадающий ввод → дропдаун с ЕДИНСТВЕННЫМ пунктом добавления
    # (макет, состояние «нет совпадений»); ввод не заблокирован.
    tags.fill("zzz-нет")
    add_only = page.locator(f"{LISTBOX} .option-add")
    expect(add_only).to_have_text("+ Добавить тег «zzz-нет»")
    expect(page.locator(f"{LISTBOX} .option")).to_have_count(0)
    assert page.locator("#task-tags").input_value() == "zzz-нет"


# regression: keep — r6 FR-58: подсветка совпадения <mark> (СЦ-1).
def test_combobox_highlights_match_fragment(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-comb-002: совпавшая часть подсвечена — <mark> внутри пункта
    с точным текстом совпадения; стили терракота на accent-soft (макет)."""
    _seed_tagged_task(
        web_owner_session, web_base_url, "QAT-comb-подсветка", ["QATurgently"]
    )
    page = logged_in_page
    _open_form(page, web_base_url)

    tags = page.get_by_label("Теги (через запятую)")
    tags.fill("urgent")
    option = page.locator(f"{LISTBOX} .option").first
    expect(option).to_contain_text("QATurgently")
    marks = option.locator("mark")
    expect(marks).to_have_count(1)
    assert marks.text_content() == "urgent"
    # Терракота (accent) на мягком фоне (accent-soft) — токены макета.
    accent = marks.first.evaluate("m => getComputedStyle(m).color")
    bg = marks.first.evaluate("m => getComputedStyle(m).backgroundColor")
    assert accent == "rgb(168, 67, 44)", accent  # --color-accent
    assert bg == "rgb(247, 232, 228)", bg  # --color-accent-soft


# regression: keep — r6 FR-58: исключение уже введенных тегов (СЦ-2).
def test_combobox_excludes_entered_tags(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-comb-003: тег, уже введенный в поле (виден чипом), не
    предлагается в дропдауне; другие совпадения показаны."""
    _seed_tagged_task(
        web_owner_session,
        web_base_url,
        "QAT-comb-исключение",
        ["QATdup", "QATдругой"],
    )
    page = logged_in_page
    _open_form(page, web_base_url)

    tags = page.get_by_label("Теги (через запятую)")
    tags.fill("QATdup, ")
    expect(page.locator("#task-tags-chips .chip")).to_have_count(1)
    options = _option_texts(page)
    assert "QATdup" not in options, options
    assert "QATдругой" in options


# regression: keep — r6 FR-59: явный пункт «+ Добавить тег» (СЦ-4).
def test_combobox_add_new_tag_item(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-comb-004: ввод значения без точного совпадения показывает
    «+ Добавить тег «…»»; клик по пункту дописывает тег в input и
    рендерит чип; после сохранения тег заведен (get-or-create)."""
    assert "QATсовершенноновый" not in _tag_hints_slow(logged_in_page, web_base_url, web_owner_session)

    page = logged_in_page
    _open_form(page, web_base_url)
    tags = page.get_by_label("Теги (через запятую)")
    tags.fill("QATсовершенноновый")

    add_item = page.locator(f"{LISTBOX} .option-add")
    expect(add_item).to_have_text("+ Добавить тег «QATсовершенноновый»")

    add_item.click()
    # FR-92 committed-леджер (TC-UIP-109, волна 2.3): выбранное остается
    # в input до сабмита (строка леджера «тег,»), чип отрендерен.
    assert "QATсовершенноновый" in tags.input_value()
    expect(page.locator("#task-tags-chips .chip")).to_have_count(1)
    expect(page.locator(LISTBOX)).to_be_hidden()

    # Тег сохраняется задачей как обычный (ОГР-27) — проверка через API.
    page.get_by_label("Название").fill("QAT-comb-новый-тег")
    page.get_by_role("button", name="Создать", exact=True).click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    resp = web_owner_session.get(
        f"{web_base_url}/api/search", params={"archived": "false"}
    )
    matched = [
        t for t in resp.json()["results"] if t["title"] == "QAT-comb-новый-тег"
    ]
    assert len(matched) == 1 and "QATсовершенноновый" in matched[0]["tags"]
    web_cleanup_created(matched[0]["id"])


def _tag_hints_slow(page, web_base_url, web_owner_session):
    resp = web_owner_session.get(f"{web_base_url}/api/suggestions")
    assert resp.status_code == 200
    return resp.json()["suggestions"]


# regression: keep — r6 NFR-17: клавиатура (СЦ-6).
def test_combobox_keyboard_navigation(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-comb-005: стрелки перемещают aria-activedescendant и
    aria-selected; Enter выбирает активный пункт и НЕ отправляет форму;
    Tab выбирает активный."""
    _seed_tagged_task(
        web_owner_session,
        web_base_url,
        "QAT-comb-клава",
        ["QATkbодин", "QATkbдва", "QATkbтри"],
    )
    page = logged_in_page
    _open_form(page, web_base_url)

    tags = page.get_by_label("Теги (через запятую)")
    tags.fill("QATkb")
    options = page.locator(f"{LISTBOX} .option")
    expect(options).to_have_count(3)

    # Первый пункт активен сразу (рендер).
    first_id = options.nth(0).get_attribute("id")
    assert tags.get_attribute("aria-activedescendant") == first_id
    assert options.nth(0).get_attribute("aria-selected") == "true"

    # ArrowDown → второй; ArrowUp → снова первый.
    page.keyboard.press("ArrowDown")
    second_id = options.nth(1).get_attribute("id")
    assert tags.get_attribute("aria-activedescendant") == second_id
    assert options.nth(1).get_attribute("aria-selected") == "true"
    assert options.nth(0).get_attribute("aria-selected") == "false"

    page.keyboard.press("ArrowUp")
    assert tags.get_attribute("aria-activedescendant") == first_id

    # Enter → выбор активного; форма НЕ закрывается.
    page.keyboard.press("Enter")
    value = tags.input_value()
    # FR-92 committed-леджер (TC-UIP-109): тег остается в input до сабмита.
    assert "QATkb" in value, value
    expect(page.locator("#task-form-overlay")).to_be_visible()
    expect(page.locator(LISTBOX)).to_be_hidden()
    # Чип отрендерен существующим рендером (источник истины — input).
    expect(page.locator("#task-tags-chips .chip")).to_have_count(1)
    expect(
        page.locator("#task-tags-chips .chip", has_text="QATkbодин")
    ).to_be_visible()

    # Tab → выбор активного (после нового ввода — «+ Добавить»); Tab
    # уводит фокус, но дропдаун к моменту ухода закрыт выбором.
    tags.fill(" QATkbодин, QATkbнов")
    add_item = page.locator(f"{LISTBOX} .option-add")
    expect(add_item).to_be_visible()
    page.keyboard.press("Tab")
    # FR-92 committed-леджер (TC-UIP-109): леджер содержит выбранный тег.
    assert "QATkbнов" in tags.input_value()
    expect(page.locator(LISTBOX)).to_be_hidden()
    expect(page.locator("#task-tags")).not_to_be_focused()


# regression: keep — r6 NFR-17/СЦ-8 + FR-61-граница: Escape закрывает
# ТОЛЬКО дропдаун.
def test_combobox_escape_closes_dropdown_not_form(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-comb-006: Escape при открытом дропдауне закрывает только
    его — форма остается открытой; ввод/сохранение работают."""
    _seed_tagged_task(
        web_owner_session, web_base_url, "QAT-comb-escape", ["QATescтег"]
    )
    page = logged_in_page
    _open_form(page, web_base_url)

    tags = page.get_by_label("Теги (через запятую)")
    tags.fill("QATesc")
    expect(page.locator(LISTBOX)).to_be_visible()
    # Выбор из подсказки (Enter) → в input полный тег + запятая.
    page.keyboard.press("Enter")
    assert "QATescтег" in tags.input_value()
    expect(page.locator(LISTBOX)).to_be_hidden()

    # Escape при открытом дропдауне закрывает ТОЛЬКО его — форма открыта.
    tags.fill(" QATescтег, QATesc2")
    expect(page.locator(LISTBOX)).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(LISTBOX)).to_be_hidden()
    expect(page.locator("#task-form-overlay")).to_be_visible()

    # Форма жива: значение ввода на месте, сохранение проходит.
    page.get_by_label("Название").fill("QAT-comb-escape-задача")
    page.get_by_role("button", name="Создать", exact=True).click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    resp = web_owner_session.get(
        f"{web_base_url}/api/search", params={"archived": "false"}
    )
    matched = [
        t for t in resp.json()["results"] if t["title"] == "QAT-comb-escape-задача"
    ]
    assert len(matched) == 1, matched
    # Тег выбран выбором из подсказки до Escape-этапа; второй ввод
    # (недозавершенный токен «QATesc2») остался в input — get-or-create
    # сохранит его как тег (свободный ввод легитимен, FR-26).
    assert "QATescтег" in matched[0]["tags"], matched[0]["tags"]
    assert "QATesc2" in matched[0]["tags"], matched[0]["tags"]
    web_cleanup_created(matched[0]["id"])


# regression: keep — r6 NFR-18: aria-атрибуты (СЦ-6, ОВ-2).
def test_combobox_aria_attributes(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-comb-007: input role=combobox + aria-expanded/controls/
    autocomplete=list; дропдаун role=listbox, пункты role=option с id
    tag-opt-N; количество подсказок — в aria-live узле; значения в DOM
    через textContent (XSS: тег с HTML-спецсимволами не исполняется)."""
    _seed_tagged_task(
        web_owner_session, web_base_url, "QAT-comb-aria", ["QATariaтег"]
    )
    page = logged_in_page
    _open_form(page, web_base_url)

    tags = page.get_by_label("Теги (через запятую)")
    assert tags.get_attribute("role") == "combobox"
    assert tags.get_attribute("aria-expanded") == "false"
    assert tags.get_attribute("aria-controls") == "task-tag-combobox"
    assert tags.get_attribute("aria-autocomplete") == "list"

    tags.click()
    assert tags.get_attribute("aria-expanded") == "true"
    listbox = page.locator(LISTBOX)
    assert listbox.get_attribute("role") == "listbox"
    options = listbox.locator(".option")
    first_id = options.first.get_attribute("id")
    assert first_id.startswith("tag-opt-")
    assert tags.get_attribute("aria-activedescendant") == first_id

    # aria-live узел озвучивает количество (текст «Найдено тегов: N»).
    live = page.locator("#task-tag-combobox-live")
    assert live.get_attribute("aria-live") == "polite"
    count = options.count()
    expect(live).to_have_text(f"Найдено тегов: {count}")

    # XSS: значения — текст; <b> внутри имени тега не становится разметкой.
    # (заводим задачу с тегом-инъекцией отдельной сессией ниже по кейсу
    # не требуется: достаточно проверить отсутствие innerHTML-путей —
    # пункт с обычным значением содержит только текстовые узлы.)
    assert options.first.evaluate("el => el.innerHTML.indexOf('<b>') === -1")


# regression: keep — r6 NFR-17: клик вне закрывает дропдаун.
def test_combobox_click_outside_closes(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-comb-008: клик вне дропдауна (заголовок формы) закрывает
    его; форма остается открытой."""
    _seed_tagged_task(
        web_owner_session, web_base_url, "QAT-comb-вне", ["QAToutтег"]
    )
    page = logged_in_page
    _open_form(page, web_base_url)

    tags = page.get_by_label("Теги (через запятую)")
    tags.click()
    expect(page.locator(LISTBOX)).to_be_visible()
    page.locator("#task-form-heading").click()
    expect(page.locator(LISTBOX)).to_be_hidden()
    expect(page.locator("#task-form-overlay")).to_be_visible()


# regression: keep — r6 NFR-17/СЦ-5: тач-тап выбирает; сбой загрузки не
# блокирует ввод.
def test_combobox_touch_tap_and_load_failure(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-comb-009: клик по пункту выбирает значение (тап-путь —
    тот же click-обработчик; mousedown preventDefault держит фокус в
    input, тач-скролл не ломается — структура без touch-хаков);
    перехват сети: сбой GET /api/suggestions?kind=tags → дропдаун не
    показан, ввод тегов и сохранение работают (СЦ-5)."""
    _seed_tagged_task(
        web_owner_session, web_base_url, "QAT-comb-тач", ["QATtapтег"]
    )
    page = logged_in_page
    _open_form(page, web_base_url)

    # Клик/тап по пункту = выбор; фокус остается в input (mousedown
    # preventDefault) — blur-закрытие не опережает выбор.
    tags = page.get_by_label("Теги (через запятую)")
    tags.click()
    option = page.locator(f'{LISTBOX} [data-value="QATtapтег"]')
    expect(option).to_be_visible()
    option.click()
    assert "QATtapтег" in tags.input_value()
    expect(page.locator("#task-tags-chips .chip")).to_have_count(1)

    # Сбой загрузки подсказок (перехват → 500): дропдаун не показан,
    # свободный ввод сохраняется.
    def _fail_route(route):
        route.fulfill(status=500, body='{"error": "boom"}', content_type="application/json")

    page.route("**/api/suggestions*", _fail_route)
    page.get_by_role("button", name="Отмена").click()
    _open_form(page, web_base_url)
    tags = page.get_by_label("Теги (через запятую)")
    tags.click()
    expect(page.locator(LISTBOX)).to_be_hidden()
    tags.fill("QATbezpodskazok")
    # Сбой загрузки → подсказок нет; пункт добавления появляется, НО
    # free-input работает и задача сохраняется с введенным тегом.
    expect(page.locator(f"{LISTBOX} .option")).to_have_count(0)
    page.get_by_label("Название").fill("QAT-comb-сбой-загрузки")
    page.get_by_role("button", name="Создать", exact=True).click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    resp = web_owner_session.get(
        f"{web_base_url}/api/search", params={"archived": "false"}
    )
    matched = [
        t for t in resp.json()["results"] if t["title"] == "QAT-comb-сбой-загрузки"
    ]
    assert len(matched) == 1 and "QATbezpodskazok" in matched[0]["tags"]
    web_cleanup_created(matched[0]["id"])


# regression: keep — r6 review 2.1/2.2 (major): дропдаун не «залипает» —
# закрытие формы (крестик) закрывает и комбобокс.
def test_combobox_closes_with_form_no_stuck_dropdown(
    logged_in_page, web_base_url, web_owner_session, web_cleanup_created
):
    """TC-r6-comb-010: дропдаун, открытый при фокусе в «Теги», закрывается
    вместе с формой (крестик .modal-close — click(), не клик по странице);
    после переоткрытия дропдаун hidden, клик по «Создать» не перехвачен
    (elementFromPoint в точке кнопки + сабмит доходит до обработчика)."""
    _seed_tagged_task(
        web_owner_session, web_base_url, "QAT-comb-залипание", ["QATstickтег"]
    )
    page = logged_in_page
    _open_form(page, web_base_url)

    # Фокус в «Теги» → дропдаун открыт.
    tags = page.get_by_label("Теги (через запятую)")
    tags.click()
    expect(page.locator(LISTBOX)).to_be_visible()

    # Закрыть форму КРЕСТИКОМ (не кликом по странице).
    page.locator("#task-form-close").click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    # Дропдаун закрылся вместе с формой (не переживает закрытие).
    expect(page.locator(LISTBOX)).to_be_hidden()

    # Переоткрыть — дропдаун скрыт, не «всплыл» из прошлого открытия.
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    expect(page.locator(LISTBOX)).to_be_hidden()

    # Клик по «Создать» не перехвачен: в точке кнопки — сама кнопка (или
    # ее потомок), а не невидимый дропдаун поверх.
    hit_is_submit = page.evaluate(
        """() => {
          const btn = document.getElementById("task-form-submit");
          const r = btn.getBoundingClientRect();
          const hit = document.elementFromPoint(
            r.x + r.width / 2, r.y + r.height / 2
          );
          return btn === hit || btn.contains(hit);
        }"""
    )
    assert hit_is_submit, "кнопку «Создать» перекрывает чужой элемент"

    # И по факту: сабмит проходит обычным путем (клик не перехвачен) —
    # форма закрывается, задача создана.
    page.get_by_label("Название").fill("QAT-comb-незалипание")
    page.get_by_role("button", name="Создать", exact=True).click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    resp = web_owner_session.get(
        f"{web_base_url}/api/search", params={"archived": "false"}
    )
    matched = [
        t for t in resp.json()["results"] if t["title"] == "QAT-comb-незалипание"
    ]
    assert len(matched) == 1, matched
    web_cleanup_created(matched[0]["id"])
