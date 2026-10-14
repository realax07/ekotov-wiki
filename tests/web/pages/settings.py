"""Page Object страницы настроек (/settings): справочник категорий."""

from playwright.sync_api import expect


class SettingsPage:
    """Page Object /settings: создание/переименование/удаление категорий
    (set-домен add-r2-categories-settings)."""

    def __init__(self, page):
        self.page = page
        self.heading = page.get_by_role("heading", name="Настройки")
        self.category_list = page.locator("#category-list")
        self.new_name_input = page.locator("#category-new-name")
        self.create_submit = page.locator("#category-create-submit")

    # --- wait-обертки ---

    def open(self, base_url: str) -> None:
        self.page.goto(f"{base_url}/settings")
        expect(self.heading).to_be_visible()

    # --- локаторы-возвратники ---

    def heading_exact(self):
        """Заголовок «Настройки» с exact-матчем (негативные проверки)."""
        return self.page.get_by_role("heading", name="Настройки", exact=True)

    def category_text(self, name: str):
        """Запись справочника по точному тексту."""
        return self.category_list.get_by_text(name, exact=True)

    def category_item(self, name: str):
        """Элемент списка категорий (.category-item) с текстом name."""
        return self.category_list.locator(".category-item").filter(has_text=name)

    def rename_button(self, name: str):
        """Кнопка «Переименовать» у записи name."""
        return self.category_item(name).get_by_role("button", name="Переименовать")

    def delete_button(self, name: str):
        """Кнопка «Удалить» у записи name."""
        return self.category_item(name).get_by_role("button", name="Удалить")
