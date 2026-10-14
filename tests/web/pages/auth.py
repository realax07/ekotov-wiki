"""Page Object страницы входа (/login) и навигации-сайдбара."""

from playwright.sync_api import expect


class AuthPage:
    """Page Object /login: поля логина/пароля, кнопка «Войти»."""

    def __init__(self, page):
        self.page = page
        self.login_input = page.get_by_label("Логин")
        self.password_input = page.get_by_label("Пароль")
        self.submit_button = page.get_by_role("button", name="Войти")
        self.heading = page.get_by_role("heading", name="Вход")

    # --- wait-обертки ---

    def open(self, base_url: str) -> None:
        self.page.goto(f"{base_url}/login")
        expect(self.heading).to_be_visible()

    def login_as(self, login: str, password: str) -> None:
        """Заполнение и сабмит формы входа (шаги TC-UI-002)."""
        self.login_input.fill(login)
        self.password_input.fill(password)
        self.submit_button.click()


class Sidebar:
    """Компонент-PO: сайдбар (профиль, разделы навигации)."""

    def __init__(self, page):
        self.page = page
        self.profile = page.locator("#sidebar-profile")
        self.settings_link = page.get_by_role("link", name="Настройки")
        self.board_link = page.get_by_role("link", name="Доска")
        self.logout_button = page.get_by_role("button", name="Выйти")
