"""UI-тесты переименования видео (tasks.md 7.2, video-hosting волна 7).

Кейсы по сценариям спеки «Переименование видео» (фронт-часть):
TC-vid-120 — «Успешное переименование»: edit-иконка у имени на странице
просмотра, инлайн-правка, PATCH {title}, имя в DOM (просмотр + карточка
списка) обновляется БЕЗ перезагрузки, новое имя переживает перезагрузку;
Esc — отмена без запроса.
TC-vid-121 — 422 показывается пользователю, имя не изменено.
TC-vid-122 — 404 показывается пользователю, имя не изменено.

Стенд — session-фикстуры tests/web/conftest.py (uvicorn app + static,
Playwright-маршрутизация). API video-сервиса на стенде не поднят
(конвенция сьюта: контракт — юнит-сьют services/video/tests, здесь
TC-vid-090…099), поэтому /api/videos* перехватывается page.route
состоящим в состоянии теста моком (stateful): GET-список отдает текущие
имена, PATCH меняет имя мока — сквозной сценарий «переименовал →
перезагрузил → имя новое» проверяется честно, включая данные GET.
"""

import json

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

VIDEO_ID = "vid0000000000000000000000000001a"


def _video_item(filename):
    return {
        "id": VIDEO_ID,
        "filename": filename,
        "status": "ready",
        "size_bytes": 2048,
        "created_at": "2026-10-18T10:00:00+00:00",
        "preview_url": f"/api/videos/{VIDEO_ID}/preview",
        "file_url": f"/videos/{VIDEO_ID}/video.mp4",
        "category_id": None,
        "category_name": None,
        "likes": 0,
        "dislikes": 0,
        "my_reaction": None,
    }


def _install_video_api(page, web_base_url, state):
    """Stateful-мок /api/videos* (nginx-маршрутизация стенда не знает
    video-сервиса): состояние state['videos'] меняет PATCH, читают GET'ы
    (список при загрузке/возврате/перезагрузке страницы)."""

    def handler(route):
        request = route.request
        path = request.url.partition(web_base_url)[2].split("?")[0]
        if request.method == "GET" and path == "/api/videos":
            route.fulfill(json={"videos": list(state["videos"])})
        elif request.method == "GET" and path == "/api/videos/categories":
            route.fulfill(json={"categories": []})
        elif request.method == "PATCH" and path == f"/api/videos/{VIDEO_ID}":
            body = json.loads(request.post_data or "{}")
            state["patch_bodies"].append(body)
            behavior = state.get("patch_behavior")
            if behavior == "422":
                route.fulfill(
                    status=422,
                    json={"error": "validation error", "details": []},
                )
            elif behavior == "404":
                route.fulfill(status=404, json={"detail": "video not found"})
            else:
                title = body.get("title", "")
                for item in state["videos"]:
                    if item["id"] == VIDEO_ID:
                        item["filename"] = title
                route.fulfill(json={"id": VIDEO_ID, "title": title})
        elif request.method == "GET" and path == (
            f"/api/videos/{VIDEO_ID}/comments"
        ):
            route.fulfill(json={"comments": []})
        else:
            route.fallback()

    page.route(f"{web_base_url}/api/videos**", handler)


def _open_player(page, web_base_url):
    page.goto(f"{web_base_url}/video")
    card = page.locator(f'.v-card[data-video-id="{VIDEO_ID}"]')
    expect(card).to_be_visible()
    card.click()
    expect(page.locator("#video-player-view")).to_be_visible()


def test_rename_inline_without_reload_survives_reload(
    logged_in_page, web_base_url
):
    """TC-vid-120 (Scenario «Успешное переименование», фронт-часть).
    Edit-иконка у имени → инлайн-поле → PATCH → имя обновлено в просмотре
    и карточке списка БЕЗ перезагрузки (маркер окна жив); после
    перезагрузки страницы имя новое (сервер хранит); Esc — отмена."""
    state = {
        "videos": [_video_item("clip_001.mp4")],
        "patch_bodies": [],
        "patch_behavior": None,
    }
    page = logged_in_page
    _install_video_api(page, web_base_url, state)
    _open_player(page, web_base_url)

    title = page.locator("#player-title")
    expect(title).to_have_text("clip_001.mp4")

    # Маркер «без перезагрузки»: попадет в DOM до правки, должен пережить ее.
    page.evaluate("window.__w7noReload = 'alive'")

    # Иконка переименования + инлайн-поле (образец FR-97: maxlength 255,
    # «Сохранить» заблокирована, пока нет значения после trim).
    expect(page.locator("#player-rename")).to_be_visible()
    page.locator("#player-rename").click()
    field = page.locator("#player-rename-field")
    expect(field).to_be_visible()
    expect(title).to_be_hidden()
    rename_input = page.locator("#player-rename-input")
    expect(rename_input).to_have_value("clip_001.mp4")
    expect(rename_input).to_have_attribute("maxlength", "255")
    expect(page.locator("#player-rename-confirm")).to_be_disabled()

    # Esc до изменений — отмена, запроса нет.
    rename_input.press("Escape")
    expect(field).to_be_hidden()
    expect(title).to_be_visible()
    assert state["patch_bodies"] == []

    page.locator("#player-rename").click()
    expect(field).to_be_visible()
    rename_input.fill("Отпуск 2026")
    expect(page.locator("#player-rename-confirm")).to_be_enabled()
    rename_input.press("Enter")

    # Имя обновлено в просмотре, редактор закрыт, перезагрузки НЕ было.
    expect(title).to_have_text("Отпуск 2026")
    expect(field).to_be_hidden()
    expect(title).to_be_visible()
    assert page.evaluate("window.__w7noReload") == "alive"
    assert state["patch_bodies"] == [{"title": "Отпуск 2026"}]

    # Карточка списка (скрытый вид) обновлена на месте, без перезагрузки.
    card_title = page.locator(
        f'.v-card[data-video-id="{VIDEO_ID}"] .v-card-title'
    )
    expect(card_title).to_have_text("Отпуск 2026")

    # Возврат к списку: GET сервера отдает новое имя — карточка с ним же.
    page.locator("#player-back-link").click()
    expect(page.locator("#video-list-view")).to_be_visible()
    expect(card_title).to_have_text("Отпуск 2026")

    # Перезагрузка страницы: имя переживает (обновлена запись на сервере).
    page.reload()
    reloaded_card = page.locator(
        f'.v-card[data-video-id="{VIDEO_ID}"] .v-card-title'
    )
    expect(reloaded_card).to_have_text("Отпуск 2026")


def test_rename_error_422_shown_and_name_unchanged(logged_in_page, web_base_url):
    """TC-vid-121 (Scenario «Негативный: недопустимые символы», фронт-часть).
    422 от API — сообщение показано пользователю, имя видео не изменено,
    редактор остается открыт с работающей кнопкой (правку можно исправить)."""
    state = {
        "videos": [_video_item("clip_001.mp4")],
        "patch_bodies": [],
        "patch_behavior": "422",
    }
    page = logged_in_page
    _install_video_api(page, web_base_url, state)
    _open_player(page, web_base_url)

    title = page.locator("#player-title")
    expect(title).to_have_text("clip_001.mp4")

    page.locator("#player-rename").click()
    rename_input = page.locator("#player-rename-input")
    rename_input.fill("плохое/имя")
    page.locator("#player-rename-confirm").click()

    error = page.locator("#player-rename-error")
    expect(error).to_be_visible()
    expect(error).to_contain_text("Имя не сохранено")
    # Имя видео не изменено — ни в просмотре, ни в моке сервера.
    expect(title).to_be_hidden()  # редактор еще открыт
    expect(rename_input).to_have_value("плохое/имя")
    expect(page.locator("#player-rename-confirm")).to_be_enabled()
    assert state["videos"][0]["filename"] == "clip_001.mp4"

    # Esc после ошибки — отмена, имя прежнее, сообщение скрыто.
    rename_input.press("Escape")
    expect(title).to_have_text("clip_001.mp4")
    expect(error).to_be_hidden()


def test_rename_error_404_shown_and_name_unchanged(logged_in_page, web_base_url):
    """TC-vid-122 (Scenario «Негативный: несуществующее видео», фронт-часть).
    404 от API — сообщение показано, имя не изменено."""
    state = {
        "videos": [_video_item("clip_001.mp4")],
        "patch_bodies": [],
        "patch_behavior": "404",
    }
    page = logged_in_page
    _install_video_api(page, web_base_url, state)
    _open_player(page, web_base_url)

    title = page.locator("#player-title")
    expect(title).to_have_text("clip_001.mp4")

    page.locator("#player-rename").click()
    rename_input = page.locator("#player-rename-input")
    rename_input.fill("Новое имя")
    page.locator("#player-rename-confirm").click()

    error = page.locator("#player-rename-error")
    expect(error).to_be_visible()
    expect(error).to_contain_text("не найдено")
    assert state["videos"][0]["filename"] == "clip_001.mp4"

    rename_input.press("Escape")
    expect(title).to_have_text("clip_001.mp4")
    expect(error).to_be_hidden()
