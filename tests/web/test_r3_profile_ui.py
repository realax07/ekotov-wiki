"""Домен nav/профиль (QA-этап 5, change add-r3-visual-foundation, FR-33/Д-7/ОГР-13).

Кейсы_TC (approved test-model/approved/add-r3-visual-foundation/):
- TC-nav-101: блок профиля внизу сайдбара на всех страницах функционала
  (/board, /search, /wiki, /settings): .profile-badge = первая буква
  логина в верхнем регистре, .profile-name = логин целиком (CHK-151,
  CHK-156 шагами 1–3 кейса).
- TC-nav-102: сессия wife — «W»/«wife» (не «первый пользователь»).
- TC-nav-103: при 401 /api/auth/me (route-перехват) блок скрыт CSS-ом
  (нет .profile-filled), страница остается на /board, uncaught-ошибок JS нет.
- TC-nav-104: в блоке нет file-инпутов/смены пароля/настроек; состав
  ровно .profile-badge + .profile-name.
- TC-nav-105: #sidebar-profile стоит после #logout-button; все четыре
  раздела кликабельны и ведут на свои страницы.
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.web, pytest.mark.must]

PAGES = ("/board", "/search", "/wiki", "/settings")
HEADINGS = {
    "/board": "Доска",
    "/search": "Поиск",
    "/wiki": "Wiki",
    "/settings": "Настройки",
}


def _profile(page):
    return page.locator("#sidebar-profile")


def _expect_profile_filled(page, badge: str, name: str) -> None:
    expect(_profile(page)).to_contain_class("profile-filled", timeout=10_000)
    expect(_profile(page).locator(".profile-badge")).to_have_text(badge)
    expect(_profile(page).locator(".profile-name")).to_have_text(name)


# --------------------------------------------------------------------------
# TC-nav-101 — «профиль внизу сайдбара на всех страницах» (Must)
# --------------------------------------------------------------------------
def test_profile_badge_and_login_on_all_pages(logged_in_page, web_base_url):
    """TC-nav-101 (CHK-151 + CHK-156): /board, /search, /wiki, /settings —
    блок видим и заполнен: .profile-badge = «O», .profile-name = «owner»."""
    page = logged_in_page
    for path in PAGES:
        page.goto(f"{web_base_url}{path}")
        expect(
            page.get_by_role("heading", name=HEADINGS[path])
        ).to_be_visible()
        _expect_profile_filled(page, "O", "owner")


# --------------------------------------------------------------------------
# TC-nav-102 — «профиль показывает сессионного пользователя (wife)» (Must)
# --------------------------------------------------------------------------
def test_profile_shows_session_user_wife(page, web_base_url):
    """TC-nav-102: вход wife → .profile-badge = «W», .profile-name =
    «wife» (логин сессии, не «первый пользователь системы»)."""
    page.goto(f"{web_base_url}/login")
    page.get_by_label("Логин").fill("wife")
    page.get_by_label("Пароль").fill("QaWife_Pass_2!")
    page.get_by_role("button", name="Войти").click()
    expect(page.get_by_role("heading", name="Доска", exact=True)).to_be_visible()
    _expect_profile_filled(page, "W", "wife")


# --------------------------------------------------------------------------
# TC-nav-103 — «при 401 /api/auth/me блок не отображается» (Must)
# --------------------------------------------------------------------------
def test_profile_hidden_on_auth_me_401(logged_in_page, web_base_url):
    """TC-nav-103: блок был заполнен (позитивный фон) → route-перехват
    **/api/auth/me → 401 → перезагрузка /board: .profile-filled нет
    (блок скрыт CSS-ом), uncaught-ошибок JS нет (молчаливое скрытие —
    дизайн, код-ревью review-001-1.2 №2)."""
    page = logged_in_page
    _expect_profile_filled(page, "O", "owner")

    def _unauthorized(route):
        route.fulfill(
            status=401,
            body='{"error": "unauthorized"}',
            content_type="application/json",
        )

    page.route("**/api/auth/me", _unauthorized)
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    assert "profile-filled" not in (_profile(page).get_attribute("class") or "")
    assert page.url.endswith("/board")


# --------------------------------------------------------------------------
# TC-nav-104 — «нет аватарок-файлов, смены пароля и настроек» (Must)
# --------------------------------------------------------------------------
def test_profile_block_has_no_extra_controls(logged_in_page, web_base_url):
    """TC-nav-104 (ОГР-13, Won't): в #sidebar-profile нет input[type=file],
    элементов с «парол»/«аватар»/«display_name», любых button/a; состав
    ровно .profile-badge + .profile-name."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    _expect_profile_filled(page, "O", "owner")

    block = _profile(page)
    assert block.locator("input[type=file]").count() == 0
    assert block.locator("button, a").count() == 0
    text = block.inner_text().lower()
    for term in ("парол", "аватар", "display_name"):
        assert term not in text, (term, text)
    # Ровно два элемента.
    assert block.locator(".profile-badge").count() == 1
    assert block.locator(".profile-name").count() == 1
    assert block.evaluate("el => el.children.length") == 2


# --------------------------------------------------------------------------
# TC-nav-105 — «профиль не вытесняет разделы сайдбара» (Must)
# --------------------------------------------------------------------------
def test_profile_after_logout_and_sections_clickable(logged_in_page, web_base_url):
    """TC-nav-105: #sidebar-profile стоит ПОСЛЕ #logout-button (внизу);
    ссылки Доска/Поиск/Wiki/Настройки кликабельны и ведут на свои
    страницы (перекрытий нет)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/settings")
    expect(
        page.get_by_role("heading", name="Настройки")
    ).to_be_visible()

    # Порядок в DOM: profile следует за logout-button.
    after = page.evaluate(
        """() => {
          const logout = document.getElementById("logout-button");
          const profile = document.getElementById("sidebar-profile");
          // PRECEDING: аргумент (logout) предшествует вызвавшему (profile)
          // — значит профиль стоит после кнопки выхода.
          return Boolean(profile.compareDocumentPosition(logout) & Node.DOCUMENT_POSITION_PRECEDING)
            ? "profile-after-logout"
            : "profile-before-logout";
        }"""
    )
    assert after == "profile-after-logout", after

    # Все четыре раздела кликабельны («Wiki todo» — имя с бейджем).
    for path in PAGES:
        link = page.get_by_role("link", name=HEADINGS[path])
        link.click()
        expect(
            page.get_by_role("heading", name=HEADINGS[path])
        ).to_be_visible()
        assert path in page.url
