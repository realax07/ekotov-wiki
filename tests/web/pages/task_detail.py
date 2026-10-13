"""Page Object view-модалки карточки задачи (overlay #task-detail-overlay).

Read-only просмотр (add-r4-user-profile-ticket-view, FR-47/Д-9): id-локаторы
перенесены дословно из тест-файлов; ассерты остаются в тестах.
"""

from playwright.sync_api import expect


class TaskDetailView:
    """Компонент-PO: view-модалка карточки (клик по карточке на доске)."""

    def __init__(self, page):
        self.page = page
        self.overlay = page.locator("#task-detail-overlay")
        self.title = page.locator("#task-detail-title")
        self.attrs = page.locator("#task-detail-attrs")
        self.comments = page.locator("#task-comments-list")
        self.close_cross = page.locator("#task-view-close")
        self.unassigned_em = self.attrs.locator("em.task-view-unassigned")

    # --- wait-обертки ---

    def wait_open(self) -> None:
        expect(self.overlay).to_be_visible()

    def wait_hidden(self) -> None:
        expect(self.overlay).to_be_hidden()

    # --- локаторы-возвратники ---

    def card(self, title: str):
        """Карточка задачи на доске (role=article + текст названия)."""
        return self.page.get_by_role("article").filter(has_text=title)

    def edit_button(self):
        return self.page.get_by_role("button", name="Редактировать")

    def close_button(self):
        return self.page.get_by_role("button", name="Закрыть", exact=True)

    def inputs(self):
        """Все поля ввода view-модалки (негатив: их быть не должно)."""
        return self.page.locator(
            f"{self._OVERLAY_SEL} input, {self._OVERLAY_SEL} textarea, "
            f"{self._OVERLAY_SEL} select"
        )

    _OVERLAY_SEL = "#task-detail-overlay"
