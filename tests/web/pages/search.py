"""Page Object страницы поиска (/search): конструктор, advanced, результаты."""

from playwright.sync_api import expect


class SearchPage:
    """Page Object /search: свободный поиск + фильтр-конструктор."""

    def __init__(self, page):
        self.page = page
        self.constructor_button = page.get_by_role("button", name="Конструктор")
        self.advanced_button = page.get_by_role("button", name="Advanced")
        self.advanced = page.locator("#search-advanced")
        self.advanced_query = page.locator("#search-advanced-query")
        self.results = page.locator("#search-results")
        self.category_select = page.locator("#search-category")
        self.category_options = page.locator("#search-category option")
        self.tag_hints_options = page.locator("#tag-hints option")

    # --- wait-обертки ---

    def open(self, base_url: str) -> None:
        """Переход на поиск; якорь загрузки — кнопка «Конструктор»."""
        self.page.goto(f"{base_url}/search")
        expect(self.constructor_button).to_be_visible()

    # --- локаторы-возвратники ---

    def result_card(self, title: str):
        """Карточка результата поиска (role=article + текст)."""
        return self.results.get_by_role("article").filter(has_text=title)

    def find_button(self):
        return self.advanced.get_by_role("button", name="Найти")
