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
        self.search_link = page.get_by_role("link", name="Поиск")
        self.wiki_link = page.get_by_role("link", name="Wiki")
        self.logout_button = page.get_by_role("button", name="Выйти")

    # --- локаторы-возвратники ---

    def name_label(self):
        """Подпись имени в блоке профиля (.profile-name)."""
        return self.profile.locator(".profile-name")

    def avatar_image(self):
        """Аватар в блоке профиля (img.profile-avatar вместо кружка)."""
        return self.profile.locator("img.profile-avatar")

    def badge(self):
        """Кружок-заглушка с бейджем (пока аватара нет)."""
        return self.profile.locator(".profile-badge")

    def wait_filled(self, name: str, timeout: int = 10_000) -> None:
        """Автожидание заполненного профиля: класс profile-filled +
        подпись display_name (GET /api/auth/me после ответа /me —
        асинхронно, автожидание текста, а не мгновенный ассерт)."""
        expect(self.profile).to_contain_class("profile-filled", timeout=timeout)
        expect(self.name_label()).to_have_text(name, timeout=timeout)
