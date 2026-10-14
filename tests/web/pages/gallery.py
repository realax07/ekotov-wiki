"""Page Object страницы Галереи (/gallery) и лайтбокса (add-gallery-service).

Локаторы дословно из кейсов TC-GAL-115…119; ассерты — в тестах. Вход
(/login) и BUG-008-guard фикстуры — в тест-файле (стенд :18443).
"""


class GalleryPage:
    """Page Object /gallery: грид карточек, фильтры, лайтбокс, upload-форма."""

    def __init__(self, page):
        self.page = page
        self.grid = page.locator("#gallery-grid")
        self.toolbar = page.locator(".gallery-toolbar")
        self.filter_category = page.locator("#filter-category")
        self.filter_tag = page.locator("#filter-tag")
        self.filter_reset = page.locator("#filter-reset")

        # Лайтбокс.
        self.lightbox = page.locator("#lightbox-overlay")
        self.lb_title = page.locator("#lb-title")
        self.lb_prev = page.locator("#lb-prev")
        self.lb_next = page.locator("#lb-next")
        self.lb_like = page.locator("#lb-like")
        self.lb_like_count = page.locator("#lb-like-count")
        self.lb_dislike = page.locator("#lb-dislike")
        self.lb_dislike_count = page.locator("#lb-dislike-count")
        self.lb_comments_list = page.locator("#lb-comments-list")
        self.lb_comment_input = page.locator("#comment-input")
        self.lb_comment_send = page.locator("#comment-send")
        self.lb_download = page.locator("#lb-download")
        self.lb_close = page.locator("#lb-close")
        self.lb_error = page.locator("#lb-error")

        # Upload-форма.
        self.upload_button = page.locator("#upload-button")
        self.upload_form = page.locator("#upload-form")
        self.upload_file = page.locator("#upload-file")
        self.upload_category = page.locator("#up-category")
        self.upload_category_new = page.locator("#up-category-new")
        self.upload_tags = page.locator("#up-tags")
        self.upload_submit = page.locator("#upload-submit")
        self.upload_error = page.locator("#upload-error")
        self.upload_close = page.locator("#upload-close")
        self.upload_dropzone = page.locator("#upload-dropzone")

        # Сайдбар.
        self.nav_items = page.locator(".sidebar-nav a.nav-item")
        self.gallery_nav_item = page.locator("a.nav-item-gallery")

    # --- локаторы-возвратники ---

    def cards(self):
        """Карточки грида (.g-card)."""
        return self.page.locator(".g-card")

    def card(self, name: str):
        """Карточка по имени файла (has_text)."""
        return self.page.locator(".g-card", has_text=name)

    def card_title(self, name: str):
        """Заголовок карточки (.g-card-title) с текстом name."""
        return self.page.locator(".g-card-title", has_text=name)
