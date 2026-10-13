"""Page Object формы задачи (overlay #task-form-overlay).

Локаторы дословно перенесены из тест-файлов (TC-UI-*, TC-sel-*, TC-form-*):
ассерты остаются в тестах, PO — действия и возврат локаторов. Скрытые
hidden-модалки не имеют ARIA-роли — id-локаторы разрешены кейсом
(соглашение п.3, tests/web/test_board_tasks_ui.py).
"""

from playwright.sync_api import expect


class TaskForm:
    """Компонент-PO: форма создания/редактирования задачи."""

    def __init__(self, page):
        self.page = page
        self.overlay = page.locator("#task-form-overlay")
        self.heading_create = page.get_by_role("heading", name="Создание задачи")
        self.heading_edit = page.get_by_role("heading", name="Редактирование задачи")
        self.heading_comments = page.get_by_role("heading", name="Комментарии")
        self.title_input = page.get_by_label("Название")
        self.description = page.get_by_label("Описание")
        self.priority = page.get_by_label("Приоритет")
        self.category = page.get_by_label("Категория")
        self.due_date = page.get_by_label("Срок")
        self.tags = page.get_by_label("Теги (через запятую)")
        self.error = page.locator("#task-form-error")
        self.actions = page.locator("#task-actions")
        self.comment_form = page.locator("#comment-form")
        self.comments_list = page.locator("#task-form-comments-list")
        # Опции селекта «Категория» (форма): опции загружаются асинхронно.
        self.category_options = page.locator("#task-category option")
        self.tag_hints_options = page.locator("#task-tag-hints option")

    # --- wait-обертки (единственное исключение из «без ассертов в PO») ---

    def wait_open(self) -> None:
        expect(self.overlay).to_be_visible()

    def wait_hidden(self) -> None:
        expect(self.overlay).to_be_hidden()

    def open_create(self) -> None:
        """Открытие формы создания по кнопке «Создать задачу»."""
        self.page.get_by_role("button", name="Создать задачу").click()
        self.wait_open()

    # --- локаторы-возвратники (кнопки формы; роль-приоритет playwright-pro) ---

    def open_button(self):
        return self.page.get_by_role("button", name="Создать задачу")

    def submit_button(self):
        """Кнопка сабмита формы («Создать»/«Сохранить») — точное имя."""
        return self.page.get_by_role("button", name="Создать", exact=True)

    def save_button(self):
        return self.page.get_by_role("button", name="Сохранить")

    def cancel_button(self):
        return self.page.get_by_role("button", name="Отмена")

    def category_select(self):
        return self.page.locator("#task-category")

    def new_comment_input(self):
        return self.page.get_by_label("Новый комментарий")

    def add_comment_button(self):
        return self.page.get_by_role("button", name="Добавить комментарий")

    def move_select(self):
        return self.page.get_by_label("Столбец")
