"""Page Object страницы Wiki (/wiki)."""

from playwright.sync_api import expect


class WikiPage:
    """Page Object /wiki: заголовок, дерево страниц, редактор."""

    def __init__(self, page):
        self.page = page
        self.heading = page.get_by_role("heading", name="Wiki")
        self.main = page.locator("main")

    # --- wait-обертки ---

    def open(self, base_url: str) -> None:
        self.page.goto(f"{base_url}/wiki")
        expect(self.heading).to_be_visible()
