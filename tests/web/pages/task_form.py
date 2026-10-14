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
        self.tag_hints = page.locator("#task-tag-hints")
        self.sheet = page.locator("#task-form-overlay .task-form-sheet")
        self.category_error = page.locator("#task-category-error")

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

    def delete_button(self):
        return self.page.get_by_role("button", name="Удалить")

    def title_by_id(self):
        """id-локатор (fallback кейсов: поля скрытой формы без роли)."""
        return self.page.locator("#task-title")

    def description_by_id(self):
        return self.page.locator("#task-description")

    def priority_by_id(self):
        """id-локатор select приоритета (fallback кейсов formv3)."""
        return self.page.locator("#task-priority")

    def tags_by_id(self):
        """id-локатор поля тегов (fallback кейсов formv3)."""
        return self.page.locator("#task-tags")

    def heading_by_id(self):
        """Заголовок формы (#task-form-heading, текст «Создание/Редактирование»)."""
        return self.page.locator("#task-form-heading")

    def tag_chips(self):
        """Чипы выбранных тегов (.chip в #task-tags-chips)."""
        return self.page.locator("#task-tags-chips .chip")

    def priority_pill_icon(self):
        """Бокс inline-SVG-иконки пилюли приоритета."""
        return self.page.locator("#task-priority-pill-icon")

    def fast_row(self):
        """Ряд fast-задачи формы (.fast-row; hidden в старых версиях)."""
        return self.page.locator(".fast-row")

    def is_fast_checkbox(self):
        """Чекбокс is_fast формы (#task-is-fast)."""
        return self.page.locator("#task-is-fast")

    def close_cross(self):
        """Крестик «Закрыть форму без сохранения» (aria-label, текст в svg)."""
        return self.overlay.get_by_role(
            "button", name="Закрыть форму без сохранения"
        )

    def priority_pill(self):
        """Пилюля поля приоритета (цвет следует выбранному значению)."""
        return self.page.locator(".priority-field-pill")

    def priority_pill_in_overlay(self):
        """Пилюля приоритета, скоуп оверлея (для expect-автожидания)."""
        return self.page.locator("#task-form-overlay .priority-field-pill")

    def wait_category_options(self, min_names: int) -> None:
        """Автожидание загрузки именованных опций select «Категория»
        (select заполняется асинхронно): wait_for_function — непустых
        (value != "") опций >= min_names, таймаут 10 c, без sleep."""
        self.page.wait_for_function(
            """([sel, minNames]) => {
              const el = document.querySelector(sel);
              if (!el) return false;
              const named = Array.from(el.querySelectorAll('option'))
                .filter((o) => o.getAttribute('value')).length;
              return named >= minNames;
            }""",
            arg=["#task-category", min_names],
            timeout=10_000,
        )

    def named_category_options(self, min_names: int = 1) -> list[str]:
        """Опции select «Категория» без пустой опции-плейсхолдера (пустое
        значение «—» = «категория не задана», Д-2, не элемент справочника).
        Опции загружаются асинхронно — ожидание >= min_names. На общей
        сессионной странице несколько select «Категория» быть не может
        (одна форма); locator.first — защита от множественного label-матча."""
        self.wait_category_options(min_names)
        options = self.page.locator("#task-category option")
        return [
            options.nth(i).text_content().strip()
            for i in range(options.count())
            if options.nth(i).get_attribute("value")
        ]
