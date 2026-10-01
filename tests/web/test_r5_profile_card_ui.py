"""Единая карточка профиля V3 (change add-r5-avatar-crop-compact-profile,
tasks.md 3.1; FR-55/FR-56, ОВ-СА-6; дельта settings — Requirement
«Единая карточка профиля V3», Scenario «Единая карточка V3», «Все функции
Релиза 4 сохранены», «Адаптив одной колонкой»).

Кейсы dev-фикстуры (трассировка — docstring каждого теста; TC-ID
продолжают нумерацию Р5: TC-r5card-301…305; сверка стиля — живой макет
design/avatar-crop-v3.html, макет 1.1, эталон):

- «Единая карточка V3»      → TC-r5card-301 test_profile_card_v3_structure
  (одна карточка .profile-card: аватар-зона + данные профиля + смена
  пароля внутри; подзаголовки секций; токены карточки/полей/кнопок по
  макету J25);
- ОВ-СА-6                   → TC-r5card-302 test_password_confirmed_by_button_only
  (подтверждение пароля ТОЛЬКО кнопкой «Сменить пароль»: blur/смена фокуса
  запрос к POST /api/profile/password не отправляют; клик — отправляет);
- «Все функции Релиза 4 сохранены» → TC-r5card-303 test_r4_field_set_preserved +
  TC-r5card-304 test_three_save_operations_independent (состав Р4:
  display_name, роль-select из 2 значений ОВ-21, bio, пароль, аватар;
  три независимые операции сохранения — сабмит одной формы не отправляет
  чужих запросов);
- «Адаптив одной колонкой»  → TC-r5card-305 test_mobile_375_single_column_no_hscroll
  (375px: одна колонка, без горизонтальной прокрутки, FR-56).

Дельта фикса design_validator 4.2 Р5 (находка 1 major + находка 2 minor):

- DEF-004                   → TC-r5card-306 test_avatar_file_input_hidden_choose_button
  (нативный file input визуально скрыт по макету J25 — bbox 1×1/opacity 0;
  кнопка #avatar-choose «Выбрать файл…» видима и стилизована токенами V3
  .btn-secondary; клик по кнопке открывает нативный filechooser; клавиатура:
  Tab фокусирует кнопку, Enter открывает диалог — механика Р4 change на
  #avatar-file не тронута);
- FR-56                     → TC-r5card-307 test_mobile_375_open_crop_no_hscroll
  (375px при ОТКРЫТОМ кроп-виджете: маска сжалась в колонку, горизонтальной
  прокрутки страницы нет — scrollWidth ≤ clientWidth + 1; canvas = маске).

Гигиена стенда: тест правит профиль owner — восстановление в teardown
(как tests/web/test_settings_profile_r4.py).
"""

import sqlite3

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.web, pytest.mark.must]

OWNER_LOGIN = "owner"
OWNER_PASSWORD = "QaOwner_Pass_1!"
OWNER_DEFAULT_ROLE = "Product manager"  # ОВ-21

# Токены/значения макета design/avatar-crop-v3.html (1:1 с app.css :root).
CARD_SURFACE = "rgb(255, 253, 249)"        # --color-bg-surface
CARD_RADIUS = "10px"                       # --radius-card
CARD_SHADOW = "rgba(61, 54, 48, 0.08) 0px 1px 3px 0px"  # --shadow-soft
ACCENT = "rgb(168, 67, 44)"                # --color-accent (терракота)
FIELD_LINE = "2px"                         # нижняя линия поля (прием V3)


@pytest.fixture
def profile_hygiene(web_db_path):
    """Teardown-гигиена: профиль owner восстанавливается после теста
    (роль/поля — к состоянию после миграции 1.1, ОВ-21)."""
    yield
    conn = sqlite3.connect(web_db_path)
    try:
        conn.execute(
            "UPDATE users SET display_name = NULL, bio = NULL, role = ?"
            " WHERE login = ?",
            (OWNER_DEFAULT_ROLE, OWNER_LOGIN),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def owner_password_guard(web_db_path):
    """Гарантия seed-пароля owner после теста (прямым bcrypt-хешем в БД,
    как tests/web/test_settings_profile_r4.owner_password_guard) — регресс
    не зависит от исхода теста."""
    yield
    import bcrypt

    new_hash = bcrypt.hashpw(
        OWNER_PASSWORD.encode("utf-8"), bcrypt.gensalt()
    ).decode("ascii")
    conn = sqlite3.connect(web_db_path)
    try:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE login = ?",
            (new_hash, OWNER_LOGIN),
        )
        conn.commit()
    finally:
        conn.close()


def _goto(page, web_base_url):
    page.goto(f"{web_base_url}/settings/profile")
    # Автожидание предзаполнения (конвенция data-loaded, profile-settings.js).
    expect(page.locator("#profile-form")).to_have_attribute(
        "data-loaded", "true", timeout=10_000
    )


def _computed(page, selector: str, prop: str) -> str:
    return page.evaluate(
        "([sel, prop]) => getComputedStyle(document.querySelector(sel))[prop]",
        [selector, prop],
    )


# ==========================================================================
# Scenario «Единая карточка V3»: структура и токены по макету J25
# ==========================================================================


def test_profile_card_v3_structure(logged_in_page, web_base_url):
    """Scenario «Единая карточка V3» (FR-55): аватар-зона, данные профиля и
    смена пароля — в ОДНОЙ карточке .profile-card (токены V3: bg-surface,
    radius-card, shadow-soft); подзаголовки секций; пароль — внутри карточки
    ниже профиля (ОВ-СА-6), с кнопкой «Сменить пароль». Сверка с макетом
    design/avatar-crop-v3.html: классы/токены 1:1."""
    page = logged_in_page
    _goto(page, web_base_url)

    # Одна карточка, все три секции — внутри нее.
    cards = page.locator(".profile-card")
    expect(cards).to_have_count(1)
    card = cards.first
    expect(card.locator(".avatar-col #avatar-form")).to_be_visible()
    expect(card.locator(".fields-col #profile-form")).to_be_visible()
    expect(card.locator(".password-section #password-form")).to_be_visible()

    # Токены карточки — по макету (токены V3 из app.css :root).
    assert _computed(page, ".profile-card", "backgroundColor") == CARD_SURFACE
    assert _computed(page, ".profile-card", "borderRadius") == CARD_RADIUS
    assert _computed(page, ".profile-card", "boxShadow") == CARD_SHADOW

    # Подзаголовки секций (uppercase-метки по макету).
    titles = [
        t.strip().lower()
        for t in card.locator(".section-title").all_inner_texts()
    ]
    assert titles == ["аватар", "данные профиля", "смена пароля"], titles

    # Секция пароля — визуально отделена внутри той же карточки (border-top
    # по макету), НЕ отдельной карточкой/секцией страницы.
    assert (
        _computed(page, ".password-section", "borderTopWidth") == "1px"
    )

    # ОВ-СА-6: подтверждение пароля — кнопка «Сменить пароль» type=submit
    # в форме пароля (не обработчик blur).
    btn = page.locator("#password-save")
    expect(btn).to_have_attribute("type", "submit")
    expect(page.locator("#password-form")).to_contain_text("Сменить пароль")

    # Поля — прием V3 «нижняя линия»: нижняя граница 2px, радиус 0.
    assert _computed(page, "#profile-display-name", "borderBottomWidth") == FIELD_LINE
    assert _computed(page, "#profile-display-name", "borderRadius") == "0px"

    # Кнопки — пилюли V3 (radius 999px), основная — терракота-акцент.
    assert _computed(page, "#profile-save", "borderRadius") == "999px"
    assert _computed(page, "#profile-save", "backgroundColor") == ACCENT


# ==========================================================================
# ОВ-СА-6: подтверждение пароля кнопкой, не по blur
# ==========================================================================


def test_password_confirmed_by_button_only(
    logged_in_page, web_base_url, owner_password_guard
):
    """ОВ-СА-6: заполнение полей пароля и уход фокуса (blur) НЕ отправляют
    POST /api/profile/password; запрос уходит только по клику «Сменить
    пароль» (механика Р4/Д-11 — форма submit)."""
    page = logged_in_page
    _goto(page, web_base_url)

    hits = []
    page.on(
        "request",
        lambda req: hits.append(req.url) if req.url.endswith("/api/profile/password") else None,
    )

    page.locator("#password-current").fill(OWNER_PASSWORD)
    page.locator("#password-new").fill("QaWhatever_9!")
    # Увод фокуса (blur) и ожидание — запроса быть не должно.
    page.locator("h1").click()
    page.wait_for_timeout(700)
    assert hits == [], f"blur отправил запрос смены пароля: {hits}"

    # Подтверждение кнопкой — запрос уходит; успех: JS после 200 делает
    # form.reset() — автожидание пустых полей гарантирует обработку запроса
    # (success-сообщение от предыдущей операции НЕ сбрасывается, expect
    # visible от него — ложный).
    page.locator("#password-save").click()
    expect(page.locator("#password-current")).to_have_value("", timeout=10_000)
    assert len(hits) == 1, hits

    # Восстановление seed-пароля — не инлайн (падение между сменой и
    # обратной сменой каскадно ломает следующие тесты), а guard-фикстурой
    # (bcrypt-хеш в teardown, конвенция tests/web/test_settings_profile_r4.py:
    # owner_password_guard) — выполняется при любом исходе теста.


# ==========================================================================
# Scenario «Все функции Релиза 4 сохранены»: состав полей + независимость
# ==========================================================================


def test_r4_field_set_preserved(logged_in_page, web_base_url):
    """Состав полей Р4 без потерь (FR-40/41/42, ОВ-21): display_name,
    роль — select ровно с 2 значениями, bio (textarea), текущий+новый
    пароль, файловый input аватара png/jpg."""
    page = logged_in_page
    _goto(page, web_base_url)

    assert page.locator("#profile-display-name").evaluate(
        "el => el.tagName.toLowerCase()"
    ) == "input"
    role = page.locator("#profile-role")
    assert role.evaluate("el => el.tagName.toLowerCase()") == "select"
    assert role.evaluate("el => [ ...el.options ].map(o => o.value)") == [
        "Product manager",
        "Product engineer",
    ]
    assert page.locator("#profile-bio").evaluate(
        "el => el.tagName.toLowerCase()"
    ) == "textarea"
    expect(page.locator("#password-current")).to_have_attribute(
        "type", "password"
    )
    expect(page.locator("#password-new")).to_have_attribute("type", "password")
    file_input = page.locator("#avatar-file")
    expect(file_input).to_have_attribute("type", "file")
    expect(file_input).to_have_attribute(
        "accept", ".png,.jpg,.jpeg,image/png,image/jpeg"
    )


def test_three_save_operations_independent(
    logged_in_page, web_base_url, web_db_path, profile_hygiene
):
    """Три независимые операции сохранения (design §3): сабмит формы профиля
    уходит PUT /api/profile и НЕ отправляет ни password-, ни avatar-запрос;
    success-сообщения — по блокам."""
    page = logged_in_page
    _goto(page, web_base_url)

    hits = {"profile": 0, "password": 0, "avatar": 0}

    def _track(req):
        if req.url.endswith("/api/profile"):
            if req.method == "PUT":
                hits["profile"] += 1
        elif req.url.endswith("/api/profile/password"):
            hits["password"] += 1
        elif req.url.endswith("/api/profile/avatar"):
            hits["avatar"] += 1

    page.on("request", _track)

    page.locator("#profile-display-name").fill("QAT Владелец")
    page.locator("#profile-bio").fill("QAT био карточки V3")
    page.locator("#profile-save").click()
    expect(page.locator("#profile-success")).to_be_visible()

    assert hits == {"profile": 1, "password": 0, "avatar": 0}, hits

    # Факт на сервере: профиль сохранен (единая карточка — те же API Р4).
    conn = sqlite3.connect(web_db_path)
    try:
        row = conn.execute(
            "SELECT display_name, bio FROM users WHERE login = ?",
            (OWNER_LOGIN,),
        ).fetchone()
    finally:
        conn.close()
    assert row == ("QAT Владелец", "QAT био карточки V3"), row


# ==========================================================================
# Scenario «Адаптив одной колонкой»: 375px, без гориз. прокрутки (FR-56)
# ==========================================================================


def test_mobile_375_single_column_no_hscroll(logged_in_page, web_base_url):
    """Scenario «Адаптив одной колонкой» (FR-56): при ширине 375px карточка
    перестроена в одну колонку (grid-template-columns), горизонтальной
    прокрутки страницы нет; на десктопной ширине (1280px) — 2 колонки по
    макету (перестроение, а не постоянная одна колонка)."""
    page = logged_in_page
    page.set_viewport_size({"width": 375, "height": 720})
    _goto(page, web_base_url)

    expect(page.locator(".profile-card")).to_be_visible()

    # Одна колонка: аватар-зона и поля друг под другом.
    grid_cols = _computed(page, ".card-grid", "gridTemplateColumns")
    assert len(grid_cols.split()) == 1, grid_cols
    pw_cols = _computed(page, ".password-grid", "gridTemplateColumns")
    assert len(pw_cols.split()) == 1, pw_cols

    # Нет горизонтальной прокрутки (ни у документа, ни у карточки).
    metrics = page.evaluate(
        """() => ({
      doc: document.scrollingElement.scrollWidth,
      win: window.innerWidth,
      card: document.querySelector('.profile-card').scrollWidth,
      cardClient: document.querySelector('.profile-card').clientWidth,
      cardOverflow: (() => {
        const card = document.querySelector('.profile-card');
        const cr = card.getBoundingClientRect();
        let worst = null;
        card.querySelectorAll('*').forEach((el) => {
          const r = el.getBoundingClientRect();
          const over = Math.round(r.right - cr.right);
          if (over > 0 && (!worst || over > worst.over)) {
            worst = { tag: el.tagName, id: el.id, cls: String(el.className).slice(0, 40), over };
          }
        });
        return worst;
      })(),
      widest: (() => {
        let worst = null;
        document.querySelectorAll('body *').forEach((el) => {
          const r = el.getBoundingClientRect();
          if (!worst || r.right > worst.right) {
            worst = { tag: el.tagName, id: el.id, cls: String(el.className).slice(0, 40), right: Math.round(r.right) };
          }
        });
        return worst;
      })(),
    })"""
    )
    assert metrics["doc"] <= metrics["win"] + 1, metrics  # допуск 1px на субпиксель
    assert metrics["card"] <= metrics["cardClient"] + 1, metrics

    # Аватар-зона и парольный блок помещаются в вьюпорт по ширине.
    for selector in (".avatar-col", ".password-section", "#avatar-file"):
        box = page.locator(selector).bounding_box()
        assert box is not None and box["x"] >= 0 and (
            box["x"] + box["width"] <= metrics["win"] + 1
        ), (selector, box)

    # Перестроение, а не постоянная одна колонка: на десктопной ширине
    # (≥769px) card-grid — 2 колонки по макету design/avatar-crop-v3.html
    # (240px аватар-зона | поля).
    page.set_viewport_size({"width": 1280, "height": 800})
    expect(page.locator(".profile-card")).to_be_visible()
    desktop_cols = _computed(page, ".card-grid", "gridTemplateColumns")
    assert len(desktop_cols.split()) == 2, desktop_cols


# ==========================================================================
# Дельта design_validator 4.2 Р5: DEF-004 (скрытый file input + кнопка)
# ==========================================================================


def test_avatar_file_input_hidden_choose_button(
    logged_in_page, web_base_url, web_db_path
):
    """DEF-004 (design_validator 4.2 Р5, находка 1 major): file input
    визуально скрыт по макету J25 (.avatar-file-input: bbox 1×1, opacity 0,
    за пределами потока), «Choose File» браузерных дефолтов на странице нет;
    выбор — стилизованная кнопка #avatar-choose «Выбрать файл…» (токены V3:
    .btn-secondary — border-strong/радиус-пилюля). Клик по кнопке открывает
    нативный filechooser (input.click()); с клавиатуры кнопка фокусируется
    (Enter — тоже диалог, обработчик click). Механика Р4 сохранена: change на
    #avatar-file жив — set_input_files открывает виджет (Д-12)."""
    from tests.web.test_r5_crop_ui import _make_png, _select_photo

    page = logged_in_page
    _goto(page, web_base_url)

    chooser = page.locator("#avatar-choose")
    expect(chooser).to_be_visible()
    expect(chooser).to_have_text("Выбрать файл…")

    # Кнопка — стилизованная пилюля V3 (btn-secondary), не браузерный дефолт.
    assert "btn-secondary" in (chooser.get_attribute("class") or "")
    assert _computed(page, "#avatar-choose", "borderRadius") == "999px"
    assert _computed(page, "#avatar-choose", "borderColor") != "rgba(0, 0, 0, 0)" or \
        _computed(page, "#avatar-choose", "borderTopStyle") == "solid"
    assert _computed(page, "#avatar-choose", "cursor") == "pointer"

    # Input скрыт по макету: bbox ≤ 1×1 и opacity 0 (визуально отсутствует).
    box = page.locator("#avatar-file").bounding_box()
    assert box is not None and box["width"] <= 1 and box["height"] <= 1, box
    assert _computed(page, "#avatar-file", "opacity") == "0"
    assert _computed(page, "#avatar-file", "position") == "absolute"

    # Клавиатура: кнопка в tab-порядке (у скрытого input tabindex=-1 — из
    # tab-цепочки исключен), фокусируется Tab'ом, Enter открывает filechooser.
    focused = page.evaluate(
        "() => { document.getElementById('avatar-choose').focus();"
        " return document.activeElement && document.activeElement.id; }"
    )
    assert focused == "avatar-choose", focused
    with page.expect_file_chooser() as fc_info:
        chooser.focus()
        chooser.press("Enter")
    assert fc_info.value.page is page
    assert fc_info.value.element.evaluate(
        "el => el.id"
    ) == "avatar-file", "диалог открыт для #avatar-file"

    # И клик мышью — тоже filechooser нативного input.
    with page.expect_file_chooser():
        chooser.click()

    # Механика Р4 не тронута: change на #avatar-file по-прежнему работает
    # (валидный png → кроп-виджет открылся, Д-12).
    _select_photo(page, _make_png(800, 600))
    expect(page.locator("#crop-widget")).to_contain_class("is-open")


def test_mobile_375_open_crop_no_hscroll(
    logged_in_page, web_base_url, web_db_path
):
    """FR-56 (design_validator 4.2 Р5, находка 2 minor): 375px при ОТКРЫТОМ
    кроп-виджете горизонтальной прокрутки страницы нет — маска сжимается
    в доступную ширину колонки (min(192px, 100%), круг aspect-ratio:1),
    scrollWidth ≤ clientWidth + 1; canvas повторяет фактический размер маски
    (avatar-crop.js берет mask.clientWidth)."""
    from tests.web.test_r5_crop_ui import _make_png, _select_photo

    page = logged_in_page
    page.set_viewport_size({"width": 375, "height": 720})
    _goto(page, web_base_url)

    _select_photo(page, _make_png(800, 600))  # виджет открыт (Д-12)
    expect(page.locator("#crop-widget")).to_be_visible()

    mask_box = page.locator("#crop-mask").bounding_box()
    assert mask_box is not None, "маска видима"
    # Маска круглые пропорции сохранила и не шире доступной колонки.
    assert abs(mask_box["width"] - mask_box["height"]) <= 1, mask_box
    assert mask_box["width"] <= 192, mask_box

    metrics = page.evaluate(
        "() => ({"
        " doc: document.scrollingElement.scrollWidth,"
        " win: window.innerWidth,"
        " mask: document.getElementById('crop-mask').clientWidth,"
        " canvas: document.getElementById('crop-canvas').clientWidth })"
    )
    assert metrics["doc"] <= metrics["win"] + 1, metrics
    assert metrics["mask"] <= metrics["win"], metrics
    assert metrics["canvas"] == metrics["mask"], metrics
