"""QA 2.1 (a)+(г): web-проверки сайдбара «Мониторинг» на локальном стенде.

Запуск:  EKOTOV_WIKI_BASE_URL=http://127.0.0.1:18443 \
         EKOTOV_WIKI_DB_PATH=<стендовая БД> \
         pytest tests/web/test_qa21_netdata_sidebar_ui.py -q

Артефакт QA-задачи (tests/**): проверки роли-видимости ссылки «Мониторинг»
(1.4, FR-78; design §2/§3), регресс блока профиля/разделов, design_validator-
сверка фактического пункта против утвержденного мокапа 1.1а
(design/netdata-sidebar-mockup.html) на живом DOM: структура, href/target/rel,
токены computed-style (не хардкод), состояния hover/focus-visible/active,
позиция в sidebar-footer.
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.web, pytest.mark.must]

MONITORING_LABEL = "Мониторинг"
ALLOWED_ROLE = "Product manager"


def _login(page, base_url, login, password):
    page.goto(f"{base_url}/login")
    page.get_by_label("Логин").fill(login)
    page.get_by_label("Пароль").fill(password)
    page.get_by_role("button", name="Войти").click()
    page.get_by_role("heading", name="Доска", exact=True).wait_for()
    return page


def _monitoring_item(page):
    return page.locator(".sidebar-footer .nav-item-monitoring")


# --------------------------------------------------------------------------
# (а) Роль-видимость: owner (Product manager) — видна; wife (Product
#     engineer) — скрыта; аноним — скрыта (редирект на /login).
# --------------------------------------------------------------------------
def test_monitoring_link_visible_for_owner(logged_in_page, web_base_url):
    """owner: после /api/auth/me (role=Product manager) пункт есть в
    sidebar-footer, href=/netdata/, target=_blank, rel=noopener."""
    page = logged_in_page
    expect(_monitoring_item(page)).to_be_visible(timeout=10_000)
    expect(_monitoring_item(page)).to_have_attribute("href", "/netdata/")
    expect(_monitoring_item(page)).to_have_attribute("target", "_blank")
    expect(_monitoring_item(page)).to_have_attribute("rel", "noopener")
    expect(_monitoring_item(page)).to_contain_text(MONITORING_LABEL)


def test_monitoring_link_hidden_for_product_engineer(page, web_base_url):
    """wife (Product engineer): пункт НЕ создается (design §2: скрытие —
    удобство; граница — basic auth на nginx)."""
    _login(page, web_base_url, "wife", "QaWife_Pass_2!")
    expect(page.locator("#sidebar-profile")).to_contain_class(
        "profile-filled", timeout=10_000
    )
    expect(_monitoring_item(page)).to_have_count(0)


def test_monitoring_link_hidden_for_anonymous(page, web_base_url):
    """Аноним: /board перенаправлен на /login — сайдбар-футер не существует,
    пункта нет."""
    page.goto(f"{web_base_url}/board")
    page.wait_for_url("**/login**")
    expect(page.locator(".sidebar-footer")).to_have_count(0)
    expect(_monitoring_item(page)).to_have_count(0)


# --------------------------------------------------------------------------
# (а) Регресс: блок профиля и разделы сайдбара не сломаны (паритет
#     TC-nav-101/105/106 на внешнем стенде).
# --------------------------------------------------------------------------
def test_profile_block_and_sections_regression(logged_in_page, web_base_url):
    """Регресс сайдбара при появлении пункта мониторинга: профиль заполнен,
    четыре раздела на месте, tooltip-блок не задвоен, порядок footer
    «Мониторинг» → «Настройки» → «Выйти» → профиль."""
    page = logged_in_page
    # профиль
    expect(page.locator("#sidebar-profile")).to_contain_class(
        "profile-filled", timeout=10_000
    )
    expect(page.locator("#sidebar-profile .profile-badge")).to_have_text("O")
    expect(page.locator("#sidebar-profile .profile-name")).to_have_text("owner")
    # разделы (Настройки — в sidebar-footer, мокап/шаблон base.html)
    for name in ("Доска", "Поиск", "Wiki"):
        expect(
            page.locator(".sidebar-nav").get_by_role("link", name=name)
        ).to_be_visible()
    # ровно один пункт мониторинга, перед «Настройки»
    expect(_monitoring_item(page)).to_have_count(1)
    footer = page.locator(".sidebar-footer")
    children = footer.locator(":scope > *")
    classes = [
        children.nth(i).get_attribute("class") or ""
        for i in range(children.count())
    ]
    assert any("nav-item-monitoring" in c for c in classes), classes
    mon_idx = next(
        i for i, c in enumerate(classes) if "nav-item-monitoring" in c
    )
    settings_idx = next(
        i for i, c in enumerate(classes) if "nav-item-settings" in c
    )
    assert mon_idx == settings_idx - 1, (classes, mon_idx, settings_idx)
    # «Выйти» и профиль после «Настройки»
    expect(footer.get_by_role("button", name="Выйти")).to_be_visible()
    expect(page.locator("#sidebar-profile")).to_be_visible()


def test_monitoring_link_present_on_all_functional_pages(logged_in_page, web_base_url):
    """Пункт есть на всех страницах функционала (profile.js — модуль
    base.html), как блок профиля (TC-nav-101-паритет)."""
    page = logged_in_page
    for path in ("/board", "/search", "/wiki", "/settings"):
        page.goto(f"{web_base_url}{path}")
        expect(_monitoring_item(page)).to_be_visible(timeout=10_000)


# --------------------------------------------------------------------------
# (г) design_validator: фактический вид против мокапа 1.1а.
# --------------------------------------------------------------------------
def test_design_validator_markup_and_tokens(logged_in_page, web_base_url):
    """Сверка с design/netdata-sidebar-mockup.html (утвержден, мокапы eac40de;
    решение Заказчика 2026-10-05: без промпт-карточки, без маркера внешней
    ссылки): структура a.nav-item.nav-item-monitoring > svg.nav-icon(polyline,
    stroke=currentColor) + span.nav-label; токены (не хардкод): color =
    --p-paper-050 (#faf7f2), hover-фон = вуаль rgba(255,253,249,0.08),
    focus-visible = inset focus-ring, active = var(--color-accent) (#a8432c);
    иконка 16px."""
    page = logged_in_page
    item = _monitoring_item(page)
    expect(item).to_be_visible(timeout=10_000)

    # Структура: классы и дети — 1:1 мокап (без ext-hint — решение Заказчика).
    expect(item).to_have_class("nav-item nav-item-monitoring")
    icon = item.locator("svg.nav-icon")
    expect(icon).to_have_count(1)
    expect(item.locator("svg.ext-hint")).to_have_count(0)  # маркер НЕ нужен
    expect(icon.locator("polyline")).to_have_attribute("stroke", "currentColor")
    expect(item.locator("span.nav-label")).to_have_text(MONITORING_LABEL)

    # Геометрия иконки: 16px (мокап .nav-icon 16px).
    box = icon.bounding_box()
    assert box is not None and abs(box["width"] - 16) <= 1, box
    assert abs(box["height"] - 16) <= 1, box

    eval_res = item.evaluate(
        """(el) => {
          const cs = getComputedStyle(el);
          const root = getComputedStyle(document.documentElement);
          const read = (n) => root.getPropertyValue(n).trim();
          return {
            color: cs.color,
            paper: read('--p-paper-050'),
            accent: read('--color-accent'),
            clay: read('--p-clay-600'),
            focusRing: read('--focus-ring'),
            radius: cs.borderRadius,
          };
        }"""
    )
    # Цвет текста пункта = токен --p-paper-050 (#faf7f2), не хардкод вне токена.
    assert eval_res["color"] == "rgb(250, 247, 242)", eval_res
    assert eval_res["paper"].lower() == "#faf7f2", eval_res
    # Акцент = clay-600 (#a8432c) — токен V3 «Бумага».
    assert eval_res["accent"].lower() == "#a8432c", eval_res
    assert eval_res["clay"].lower() == "#a8432c", eval_res
    assert "168, 67, 44" in eval_res["focusRing"], eval_res

    # hover: вуаль rgba(255,253,249,0.08), opacity → 1.
    item.hover()
    hover_bg = item.evaluate("(el) => getComputedStyle(el).backgroundColor")
    assert hover_bg == "rgba(255, 253, 249, 0.08)", hover_bg
    assert item.evaluate("(el) => getComputedStyle(el).opacity") == "1"

    # focus-visible: keyboard-фокус → inset focus-ring (box-shadow).
    page.keyboard.press("Tab")
    # фокус может уйти не на пункт — форсируем и проверяем именно правило.
    focus_style = page.evaluate(
        """() => {
          const el = document.querySelector('.nav-item-monitoring');
          el.focus();
          // :focus-visible недоступен из JS напрямую; проверяем примененное
          // правило через matches + box-shadow при键盘ном фокусе из Tab:
          const cs = getComputedStyle(el);
          return {matches: el.matches(':focus-visible'), shadow: cs.boxShadow};
        }"""
    )
    assert "rgba(168, 67, 44, 0.35)" in focus_style["shadow"], focus_style

    # active: зажатие ЛКМ — акцентная заливка var(--color-accent).
    box = item.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    active_bg = item.evaluate("(el) => getComputedStyle(el).backgroundColor")
    page.mouse.up()
    # #a8432c = rgb(168, 67, 44)
    assert active_bg == "rgb(168, 67, 44)", active_bg
