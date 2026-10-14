"""Page Object страницы настроек пользователя (/settings/profile).

Профиль/пароль/аватар (add-r4-user-profile-ticket-view, FR-39…42,
Д-10/Д-11) + кроп-виджет аватара (add-r5, Д-12). Локаторы дословно из
кейсов TC-setp-201…/TC-passwd-101…/TC-ava-101…; ассерты — в тестах.
"""

from playwright.sync_api import expect


class ProfileSettingsPage:
    """Page Object /settings/profile: форма профиля, смена пароля, аватар."""

    def __init__(self, page):
        self.page = page
        self.profile_form = page.locator("#profile-form")
        self.password_form = page.locator("#password-form")
        self.avatar_form = page.locator("#avatar-form")
        self.display_name = page.locator("#profile-display-name")
        self.bio = page.locator("#profile-bio")
        self.role = page.locator("#profile-role")
        self.role_options = page.locator("#profile-role option")
        self.save_button = page.get_by_role("button", name="Сохранить")
        self.change_password_button = page.get_by_role(
            "button", name="Сменить пароль"
        )
        self.profile_success = page.locator("#profile-success")
        self.profile_error = page.locator("#profile-error")
        self.password_current = page.locator("#password-current")
        self.password_new = page.locator("#password-new")
        self.password_success = page.locator("#password-success")
        self.password_error = page.locator("#password-error")
        self.avatar_file = page.locator("#avatar-file")
        self.avatar_upload = page.locator("#avatar-upload")
        self.avatar_success = page.locator("#avatar-success")
        self.avatar_error = page.locator("#avatar-error")
        self.avatar_preview = page.locator("#avatar-preview")
        self.crop_widget = page.locator("#crop-widget")
        self.crop_apply = page.locator("#crop-apply")
        self.heading = page.locator("h1", has_text="Профиль")

    # --- wait-обертки ---

    def open(self, base_url: str) -> None:
        """Переход на /settings/profile; якорь готовности — data-loaded
        формы профиля (GET /api/profile асинхронен; роль PM — дефолт
        select, поэтому значение роли готовности НЕ сигналит)."""
        self.page.goto(f"{base_url}/settings/profile")
        expect(self.profile_form).to_have_attribute(
            "data-loaded", "true", timeout=10_000
        )

    def wait_loaded(self) -> None:
        """Автожидание предзаполнения после reload (data-loaded=true)."""
        expect(self.profile_form).to_have_attribute(
            "data-loaded", "true", timeout=10_000
        )


class CropWidget:
    """Компонент-PO: кроп-виджет аватара (add-r5, Д-12; avatar-crop.js).

    Локаторы дословно из кейсов TC-r5crop-401…415; drag/pinch/touch-сценарии
    — прямые mouse/evaluate в тестах (правило «PO — не догма»)."""

    def __init__(self, page):
        self.page = page
        self.widget = page.locator("#crop-widget")
        self.mask = page.locator("#crop-mask")
        self.warning = page.locator("#crop-warning")
        self.slider = page.locator("#crop-zoom")
        self.zoom_out = page.locator("#zoom-out")
        self.zoom_in = page.locator("#zoom-in")
        self.apply = page.locator("#crop-apply")
        self.cancel = page.locator("#crop-cancel")

    # --- действия / wait-обертки ---

    def select_photo(self, png: bytes, name: str = "photo.png"):
        """Выбор файла в карточке → виджет открылся (Д-12). Возвращает
        локатор виджета."""
        self.page.locator("#avatar-file").set_input_files(
            files=[{"name": name, "mimeType": "image/png", "buffer": png}]
        )
        expect(self.widget).to_contain_class("is-open", timeout=10_000)
        return self.widget

    def set_slider(self, value: int) -> None:
        """Значение слайдера программно (fill() не работает для range выше
        max; dispatch 'input' — как реальное движение)."""
        self.slider.evaluate(
            "(el, v) => { el.value = String(v); el.dispatchEvent(new Event('input')); }",
            value,
        )

    def state(self) -> dict:
        """dataset-состояние виджета (cropX/cropY/cropZoom) — без ассертов."""
        return self.page.evaluate(
            """() => {
              const w = document.getElementById('crop-widget');
              return {
                x: Number(w.dataset.cropX || 0),
                y: Number(w.dataset.cropY || 0),
                zoom: Number(w.dataset.cropZoom || 0),
              };
            }"""
        )
