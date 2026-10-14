"""Page Object доски задач (/board): столбцы, карточки, загрузка."""

from playwright.sync_api import expect


def expect_board_loaded(page) -> None:
    """Автожидание готовности доски (без sleep): #board data-loaded=true."""
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")


class BoardPage:
    """Page Object /board: колонки-статусы и карточки задач."""

    def __init__(self, page):
        self.page = page
        self.board = page.locator("#board")
        self.board_error = page.locator("#board-error")

    # --- wait-обертки ---

    def open(self, base_url: str) -> None:
        self.page.goto(f"{base_url}/board")
        expect_board_loaded(self.page)

    def wait_loaded(self) -> None:
        expect_board_loaded(self.page)

    # --- локаторы-возвратники ---

    def column(self, status: str):
        """Столбец по статусу (todo / in_progress / done)."""
        return self.page.locator(f'[data-status="{status}"]')

    def card(self, title: str):
        """Карточка задачи по названию (role=article + текст)."""
        return self.page.get_by_role("article").filter(has_text=title)

    def card_in_column(self, status: str, title: str):
        return self.column(status).get_by_role("article").filter(has_text=title)

    def heading(self):
        return self.page.get_by_role("heading", name="Доска", exact=True)

    def create_task_button(self):
        return self.page.get_by_role("button", name="Создать задачу")
