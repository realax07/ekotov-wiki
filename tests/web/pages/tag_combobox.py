"""Component-PO кастомного комбобокса подсказок тегов (r6, FR-58/59).

Дропдаун #task-tag-combobox у поля «Теги» формы задачи (tag-combobox.js);
ассерты — в тестах, PO возвращает локаторы.
"""


class TagCombobox:
    """Компонент-PO: дропдаун комбобокса тегов формы задачи."""

    def __init__(self, page):
        self.page = page
        self.listbox = page.locator("#task-tag-combobox")
        self.live = page.locator("#task-tag-combobox-live")

    # --- локаторы-возвратники ---

    def options(self):
        """Пункты дропдауна (role=option, класс .option)."""
        return self.listbox.locator(".option")

    def add_item(self):
        """Явный пункт «+ Добавить тег «…»»."""
        return self.listbox.locator(".option-add")

    def option_by_value(self, value: str):
        """Пункт дропдауна по data-value."""
        return self.listbox.locator(f'[data-value="{value}"]')
