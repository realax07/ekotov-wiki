"""Page Object страницы Wiki (/wiki) и WYSIWYG-редактора (add-wiki, FR-110/111)."""

from playwright.sync_api import expect


class WikiPage:
    """Page Object /wiki: заголовок, дерево страниц, редактор."""

    def __init__(self, page):
        self.page = page
        # exact=True (TC-UI-016, regress-final): на ПУСТОЙ wiki-БД tree.js
        # рендерит пустое состояние с h2 «В Wiki пока нет страниц» —
        # не-exact матчинг по подстроке ловит и его (strict violation
        # «resolved to 2 elements»); h1 раздела — ровно «Wiki».
        self.heading = page.get_by_role("heading", name="Wiki", exact=True)
        self.main = page.locator("main")

    # --- wait-обертки ---

    def open(self, base_url: str) -> None:
        self.page.goto(f"{base_url}/wiki")
        expect(self.heading).to_be_visible()


class WikiEditor:
    """Компонент-PO: WYSIWYG-редактор Wiki (тулбар, диалоги, сохранение).

    Выделение текста (Selection API) и innerHTML-чтение — прямой
    evaluate в тестах/PO-методах (правило «PO — не догма»)."""

    def __init__(self, page):
        self.page = page
        self.area = page.locator(".editor-area")
        self.title_input = page.get_by_label("Заголовок страницы")
        self.link_dialog = page.locator(".editor-link-dialog")
        self.img_dialog = page.locator(".editor-img-dialog")
        self.img_scale_dialog = page.locator(".editor-img-scale-dialog")
        self.error_banner = page.locator("#wiki-editor .error-banner")

    # --- wait-обертки (открытие редактора — якорь .editor-area) ---

    def open_create(self, base_url: str, parent_id=None) -> None:
        url = f"{base_url}/wiki?create=1"
        if parent_id:
            url += f"&parent={parent_id}"
        self.page.goto(url)
        expect(self.area).to_be_visible()

    def open_edit(self, base_url: str, page_id) -> None:
        self.page.goto(f"{base_url}/wiki/{page_id}?edit=1")
        expect(self.area).to_be_visible()

    # --- локаторы-возвратники ---

    def toolbar_button(self, name: str):
        """Кнопка тулбара по имени (B/I/U, H2/H3, списки, таблица…)."""
        return self.page.get_by_role("button", name=name)

    def save_button(self):
        return self.page.get_by_role("button", name="Сохранить")

    def link_address_input(self):
        """Поле «Адрес ссылки» в диалоге ссылки."""
        return self.page.get_by_label("Адрес ссылки")

    def img_pick_item(self, name: str):
        """Элемент грида выбора изображения из галереи."""
        return self.img_dialog.locator(".img-pick-item").filter(has_text=name)

    def img_file_input(self):
        """File input диалога изображения («Загрузить с диска»)."""
        return self.img_dialog.locator("input[type=file]")

    def select_all_text(self) -> None:
        """Выделить весь текст первой строки contenteditable (для B/I/U/H)."""
        self.area.click()
        self.area.evaluate(
            """(node) => {
              const range = document.createRange();
              range.selectNodeContents(node);
              const sel = window.getSelection();
              sel.removeAllRanges();
              sel.addRange(range);
            }"""
        )

    def area_html(self) -> str:
        """innerHTML редактируемой области (для негативных проверок)."""
        return self.area.evaluate("node => node.innerHTML")
