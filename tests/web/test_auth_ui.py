"""Домен auth: TC-UI-001…005 (CHK-E-1…5; approved/e2e-critical-path/ui-01.md).

Селекторы — дословно из кейсов (рольные/семантические); автожидания expect,
sleep 0; изоляция: пустая БД стенда на сессию, тесты auth задач не создают.
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def test_unauthenticated_redirects_to_login(page, web_base_url):
    """TC-UI-001: неавторизованный доступ к /board, /search, /wiki —
    серверный редирект на /login, содержимое защищенных страниц не
    отрисовывается (NFR-7)."""
    for path in ("/board", "/search", "/wiki"):
        page.goto(f"{web_base_url}{path}")
        expect(page.get_by_role("heading", name="Вход")).to_be_visible()
        assert page.url.endswith("/login"), f"{path}: URL {page.url} не /login"
        expect(page.get_by_label("Логин")).to_be_visible()
        expect(page.get_by_label("Пароль")).to_be_visible()
        expect(page.get_by_role("button", name="Войти")).to_be_visible()
    # На итоговой (/login) контента доски нет.
    expect(page.get_by_role("heading", name="Доска", exact=True)).to_have_count(0)


def test_owner_login_success_board_and_sidebar(page, web_base_url):
    """TC-UI-002: успешный вход owner → редирект /board, заголовок «Доска»,
    сайдбар (Доска/Поиск/Wiki), три столбца с заголовками."""
    page.goto(f"{web_base_url}/login")
    page.get_by_label("Логин").fill("owner")
    page.get_by_label("Пароль").fill("QaOwner_Pass_1!")
    page.get_by_role("button", name="Войти").click()
    expect(page.get_by_role("heading", name="Доска", exact=True)).to_be_visible()
    assert page.url.endswith("/board")

    for name in ("Доска", "Поиск", "Wiki"):
        expect(page.get_by_role("link", name=name)).to_be_visible()

    for status, heading in (
        ("todo", "Ожидает"),
        ("in_progress", "В работе"),
        ("done", "Выполнено"),
    ):
        column = page.locator(f'[data-status="{status}"]')
        expect(column).to_be_visible()
        expect(column.get_by_role("heading", name=heading)).to_be_visible()


def test_wrong_password_and_unknown_login_same_error(page, web_base_url):
    """TC-UI-003: неверный пароль и несуществующий логин — один и тот же
    текст ошибки «Неверный логин или пароль» (посимвольно), URL /login."""
    page.goto(f"{web_base_url}/login")

    page.get_by_label("Логин").fill("owner")
    page.get_by_label("Пароль").fill("Wrong_Pass_9!")
    page.get_by_role("button", name="Войти").click()
    alert = page.get_by_role("alert")
    expect(alert).to_be_visible()
    text1 = alert.inner_text()
    assert page.url.endswith("/login")

    page.get_by_label("Логин").fill("ghost_user")
    page.get_by_label("Пароль").fill("Any_Pass_1!")
    page.get_by_role("button", name="Войти").click()
    expect(alert).to_be_visible()
    text2 = alert.inner_text()
    assert page.url.endswith("/login")

    assert text1 == text2, "тексты отказов различаются — раскрытие существования логина"
    assert text1 == "Неверный логин или пароль"


def test_session_survives_reload(page, web_base_url):
    """TC-UI-004: перезагрузка и переходы в действующей сессии — без
    повторного входа (форма входа не показывается, доска отрисована)."""
    page.goto(f"{web_base_url}/login")
    page.get_by_label("Логин").fill("owner")
    page.get_by_label("Пароль").fill("QaOwner_Pass_1!")
    page.get_by_role("button", name="Войти").click()
    expect(page.get_by_role("heading", name="Доска", exact=True)).to_be_visible()

    page.reload()
    expect(page.get_by_role("heading", name="Доска", exact=True)).to_be_visible()
    assert page.url.endswith("/board")

    page.goto(f"{web_base_url}/search")
    assert page.url.endswith("/search")
    expect(page.get_by_role("heading", name="Поиск", exact=True)).to_be_visible()

    page.goto(f"{web_base_url}/board")
    assert page.url.endswith("/board")
    expect(page.get_by_role("button", name="Войти")).to_have_count(0)
    expect(page.locator('[data-status="todo"]')).to_be_visible()


def test_logout_invalidates_session(page, web_base_url):
    """TC-UI-005: «Выйти» → /login; прямое открытие /board и reload
    возвращают на /login — сессия закрыта на сервере."""
    page.goto(f"{web_base_url}/login")
    page.get_by_label("Логин").fill("owner")
    page.get_by_label("Пароль").fill("QaOwner_Pass_1!")
    page.get_by_role("button", name="Войти").click()
    expect(page.get_by_role("heading", name="Доска", exact=True)).to_be_visible()

    page.get_by_role("button", name="Выйти").click()
    expect(page.get_by_role("heading", name="Вход")).to_be_visible()
    assert page.url.endswith("/login")
    expect(page.get_by_label("Логин")).to_be_visible()

    page.goto(f"{web_base_url}/board")
    assert page.url.endswith("/login")
    page.reload()
    assert page.url.endswith("/login")
