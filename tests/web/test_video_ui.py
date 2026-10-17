"""UI-тесты страницы «Видео» (tasks.md 1.5 video-hosting, кусок A).

TC-vid-101 — пункт сайдбара «Видео» после «Галерея» (Scenario
«Пункт сайдбара виден авторизованным», утвержденный мокап 0.2,
design/video-hosting/video-list.html);
TC-vid-102 — неавторизованный: /video → редирект /login (Scenario
«Неавторизованный — редирект на login», sdd §3.6);
TC-vid-103 — форма загрузки по мокапу video-upload.html: dropzone,
лимит «до 500 МБ» в подписи (ОВ-1), блокировка отправки без файла.

Стенд — session-фикстуры tests/web/conftest.py (uvicorn app + static,
Playwright-маршрутизация). API видео (сервис video) на стенде не поднят —
его контракт покрыт юнит-сьютом services/video/tests (1.6, TC-vid-001…);
здесь проверяется ТОЛЬКО каркас страницы/сайдбара (зона 1.5).
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def test_sidebar_video_item_after_gallery(logged_in_page, web_base_url):
    """Scenario «Пункт сайдбара виден авторизованным»: пункт «Видео» в
    сайдбаре, СТРОГО после «Галерея», с иконкой (inline-SVG, .nav-icon);
    клик ведет на /video, заголовок страницы — «Видео»."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")

    video_link = page.locator(".sidebar-nav .nav-item-video")
    gallery_link = page.locator(".sidebar-nav .nav-item-gallery")
    expect(video_link).to_be_visible()
    expect(gallery_link).to_be_visible()

    # Порядок — «Видео» сразу после «Галерея» (финал мокапа 0.3).
    order = page.evaluate(
        "[...document.querySelectorAll('.sidebar-nav .nav-item')]"
        ".map((a) => a.className)"
    )
    assert order.index("nav-item nav-item-video") == (
        order.index("nav-item nav-item-gallery") + 1
    )

    # Иконка в едином стиле эталона (inline-SVG .nav-icon, aria-hidden).
    icon = video_link.locator("svg.nav-icon")
    expect(icon).to_have_count(1)
    expect(icon).to_have_attribute("aria-hidden", "true")

    # Клик → страница сервиса /video (заголовок и кнопка загрузки по мокапу).
    video_link.click()
    assert page.url.endswith("/video")
    expect(page.get_by_role("heading", name="Видео")).to_be_visible()
    expect(page.locator("#open-upload-button")).to_be_visible()
    expect(page.locator("#video-grid")).to_be_visible()


def test_video_page_redirects_anonymous_to_login(page, web_base_url):
    """Scenario «Неавторизованный — редирект на login»: открытие /video
    без сессии — редирект на страницу входа (middleware ядра, sdd §3.6)."""
    page.goto(f"{web_base_url}/video")
    page.wait_for_url("**/login")
    assert page.url.endswith("/login")


def test_video_upload_form_by_mockup(logged_in_page, web_base_url):
    """Вид формы загрузки по утвержденному мокапу video-upload.html:
    dropzone с подписью лимита «любой видеоформат · до 500 МБ» (ОВ-1),
    кнопки «Отмена»/«Загрузить», отмена возвращает к списку."""
    page = logged_in_page
    page.goto(f"{web_base_url}/video")
    page.locator("#open-upload-button").click()

    dropzone = page.locator("#dropzone")
    expect(dropzone).to_be_visible()
    expect(page.locator("#dz-hint")).to_have_text("любой видеоформат · до 500 МБ")
    submit = page.locator("#upload-submit-button")
    expect(submit).to_be_disabled()  # файл не выбран — отправка заблокирована
    expect(page.locator("#upload-cancel-button")).to_be_visible()

    page.locator("#upload-cancel-button").click()
    expect(page.get_by_role("heading", name="Видео")).to_be_visible()
    expect(page.locator("#video-upload-view")).to_be_hidden()
