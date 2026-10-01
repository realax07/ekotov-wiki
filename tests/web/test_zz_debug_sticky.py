import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web]


def test_debug_sticky_dropdown(logged_in_page, web_base_url, web_owner_session, web_cleanup_created):
    """Полная реплика порядка UPALШЕГО прогона: excludes → escape → pick_existing
    (тесты подряд, ОДИН page-стенд). После escape-теста «Создать» кликается?"""
    created = web_owner_session.post(
        f"{web_base_url}/api/tasks",
        json={"title": "QATdbg-seq", "tags": ["QATescтег"]},
    )
    assert created.status_code == 201
    web_cleanup_created(created.json()["id"])

    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # --- фаза 1 (как excludes): fill('QATdup, ') и ассерты
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    tags = page.get_by_label("Теги (через запятую)")
    tags.fill("QATescтег, ")
    expect(page.locator("#task-tags-chips .chip")).to_have_count(1)
    page.get_by_role("button", name="Отмена").click()

    # --- фаза 2 (как escape): Enter-выбор, fill, Escape, submit
    page.get_by_role("button", name="Создать задачу").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    tags.fill("QATesc")
    expect(page.locator("#task-tag-combobox")).to_be_visible()
    page.keyboard.press("Enter")
    tags.fill(" QATescтег, QATesc2")
    expect(page.locator("#task-tag-combobox")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#task-tag-combobox")).to_be_hidden()
    page.get_by_label("Название").fill("QATdbg-seq-задача")
    page.get_by_role("button", name="Создать", exact=True).click()
    expect(page.locator("#task-form-overlay")).to_be_hidden()
    print("SEQ-OK")
