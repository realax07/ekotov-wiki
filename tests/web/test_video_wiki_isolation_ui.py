"""UI-изоляция сервиса «Видео» от wiki-редактора (approved TC-vid-003).

ОВ-3: видео НЕ встраивается в статьи wiki — в инструментах вставки
редактора нет пункта «Видео», элемент <video> в редакторе не появляется,
содержимое статьи не меняется от открытия меню вставки.

Стенд — session-фикстуры tests/web/conftest.py; Page Object
tests/web/pages/wiki.py (WikiEditor).
"""

import pytest
from playwright.sync_api import expect

from tests.web.pages.wiki import WikiEditor

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def test_wiki_editor_has_no_video_insert(logged_in_page, web_base_url):
    """TC-vid-003 (ОВ-3, Scenario «Видео не встраивается в статьи»):
    в тулбаре редактора нет кнопки «Видео» (эталонный состав вставок —
    ссылка/таблица/изображение), элемента <video> нет, открытие диалога
    вставки не меняет содержимое статьи (diff пуст)."""
    page = logged_in_page
    editor = WikiEditor(page)
    editor.open_create(web_base_url)
    area = editor.area
    area.click()

    # Шаг 2: осмотреть ВСЕ пункты меню вставки (тулбар редактора).
    labels = page.evaluate(
        "[...document.querySelectorAll('#wiki-editor .toolbar .tb-btn')]"
        ".map((b) => (b.getAttribute('aria-label') || b.textContent).trim())"
    )
    assert labels, "тулбар редактора пуст"
    video_labels = [l for l in labels if "видео" in l.lower()]
    assert video_labels == [], video_labels
    # Эталонные вставки на месте (пункт «Изображение» — медиа-вставка).
    assert "Изображение" in labels and "Ссылка" in labels

    # <video> в редакторе отсутствует; диалог изображения не предлагает видео.
    expect(page.locator("#wiki-editor video")).to_have_count(0)
    before = editor.area_html()
    editor.toolbar_button("Изображение").click()
    expect(editor.img_dialog).to_be_visible()
    assert "видео" not in editor.img_dialog.inner_text().lower()
    editor.img_dialog.get_by_role("button", name="Отмена").click()
    expect(editor.img_dialog).to_be_hidden()

    # Шаг 3: содержимое статьи не изменилось.
    assert editor.area_html() == before
    expect(page.locator("#wiki-editor video")).to_have_count(0)
