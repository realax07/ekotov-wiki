"""UI-тесты конвертации на странице «Видео» (tasks.md 3.1/3.2 фронт,
video-hosting, кусок B).

TC-vid-107 — convert-note «сервер сконвертирует в mp4» в форме загрузки
(мокап video-upload.html .convert-note; ревью-001 куска A, п.2);
TC-vid-108 — бейджи статусов по мокапу video-list.html: «загружено» /
«конвертируется» (пульсирующий индикатор, aria-busy) / «готово» /
«ошибка» (подсказка «оригинал сохранен»); не готовое видео не
открывает плеер (Scenario «Не готовое видео не проигрывается»);
TC-vid-109 — автообновление списка polling'ом: статус «конвертируется»
сменяется «готово» без перезагрузки страницы (design §3, сценарий
приемки 3.3 «статусы в UI без перезагрузки»).

Стенд — session-фикстуры tests/web/conftest.py; API video-сервиса на
стенде не поднят (контракт — юнит-сьют services/video/tests), поэтому
ответы /api/videos* подменяются Playwright-маршрутизацией (роль nginx)
на фикстурные JSON — проверяется ТОЛЬКО фронтенд-слой (video.js).
"""

import json
import re

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def _mock_api(page, videos_payload):
    """API video-сервиса не на стенде: /api/videos* и /api/auth/* —
    фикстурные JSON (роль nginx играется маршрутизацией Playwright)."""

    def list_route(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(videos_payload() if callable(videos_payload) else videos_payload),
        )

    me = {"id": 1, "login": "owner", "display_name": "Owner"}
    page.route(re.compile(r"/api/auth/me$"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(me)))
    page.route(re.compile(r"/api/videos/categories$"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps({"categories": []})))
    page.route(re.compile(r"/api/videos$"), list_route)
    page.route(re.compile(r"/api/videos\?.*"), list_route)


def _sample_items():
    return {
        "videos": [
            {
                "id": "a" * 32, "filename": "обзор.mkv", "status": "uploaded",
                "size_bytes": 428 * 1024 * 1024, "created_at": "2026-10-18T10:00:00+00:00",
                "preview_url": "/api/videos/" + "a" * 32 + "/preview",
                "file_url": "/videos/" + "a" * 32 + "/original.mkv",
                "category_id": None, "category_name": None,
                "likes": 0, "dislikes": 0, "my_reaction": None,
            },
            {
                "id": "b" * 32, "filename": "ремонт.mkv", "status": "converting",
                "size_bytes": 512 * 1024 * 1024, "created_at": "2026-10-18T10:01:00+00:00",
                "preview_url": "/api/videos/" + "b" * 32 + "/preview",
                "file_url": "/videos/" + "b" * 32 + "/original.mkv",
                "category_id": None, "category_name": None,
                "likes": 0, "dislikes": 0, "my_reaction": None,
            },
            {
                "id": "c" * 32, "filename": "дрон.mp4", "status": "ready",
                "size_bytes": 96 * 1024 * 1024, "created_at": "2026-10-18T10:02:00+00:00",
                "preview_url": "/api/videos/" + "c" * 32 + "/preview",
                "file_url": "/videos/" + "c" * 32 + "/video.mp4",
                "category_id": None, "category_name": None,
                "likes": 0, "dislikes": 0, "my_reaction": None,
            },
            {
                "id": "d" * 32, "filename": "битый.mkv", "status": "error",
                "size_bytes": 210 * 1024 * 1024, "created_at": "2026-10-18T10:03:00+00:00",
                "preview_url": "/api/videos/" + "d" * 32 + "/preview",
                "file_url": "/videos/" + "d" * 32 + "/original.mkv",
                "category_id": None, "category_name": None,
                "likes": 0, "dislikes": 0, "my_reaction": None,
            },
        ]
    }


def test_convert_note_in_upload_form(logged_in_page, web_base_url):
    """TC-vid-107 (мокап video-upload.html; ревью-001 п.2): в форме
    загрузки — convert-note «сервер сконвертирует видео в mp4» (формат
    любой, конвертация в фоне, статус в списке)."""
    page = logged_in_page
    _mock_api(page, {"videos": []})
    page.goto(f"{web_base_url}/video")
    page.locator("#open-upload-button").click()

    note = page.locator("#convert-note")
    expect(note).to_be_visible()
    expect(note).to_contain_text("Сервер сконвертирует видео в")
    expect(note.locator("b")).to_have_text("mp4")
    expect(note).to_contain_text("в любом формате")
    expect(note).to_contain_text("статус виден в списке")


def test_status_badges_by_mockup(logged_in_page, web_base_url):
    """TC-vid-108 (мокап video-list.html): четыре бейджа статусов с
    токенными классами; «конвертируется» — aria-busy (пульсирующая
    точка); «ошибка» — подсказка «оригинал сохранен»; не готовое видео
    в просмотре — плейсхолдер БЕЗ <video> (плеер только для «готово»)."""
    page = logged_in_page
    _mock_api(page, _sample_items())
    page.goto(f"{web_base_url}/video")
    expect(page.locator(".v-card")).to_have_count(4)

    uploaded = page.locator(".status-badge.status-uploaded")
    expect(uploaded.first).to_have_text(re.compile("загружено"))
    converting = page.locator(".status-badge.status-converting")
    expect(converting.first).to_have_text(re.compile("конвертируется"))
    expect(converting.first).to_have_attribute("aria-busy", "true")
    expect(page.locator(".status-badge.status-ready").first).to_have_text(
        re.compile("готово")
    )
    error_badge = page.locator(".status-badge.status-error").first
    expect(error_badge).to_have_text(re.compile("ошибка"))
    expect(page.locator(".v-card .error-hint").first).to_contain_text(
        "оригинал сохранен"
    )

    # Плеер только для «готово»: карточка «конвертируется» — плейсхолдер.
    page.locator('.v-card[data-video-id="' + "b" * 32 + '"]').click()
    expect(page.locator("#player-card .player-pending")).to_be_visible()
    expect(page.locator("#player-card video")).to_have_count(0)
    expect(page.locator("#player-status .status-converting")).to_be_visible()

    # У «готово» — плеер <video> с nginx-отдачей из тома.
    page.locator("#player-back-link").click()
    expect(page.get_by_role("heading", name="Видео")).to_be_visible()
    page.locator('.v-card[data-video-id="' + "c" * 32 + '"]').click()
    expect(page.locator("#player-card video")).to_have_count(1)
    page.wait_for_load_state("networkidle")


def test_list_auto_refresh_polling(logged_in_page, web_base_url):
    """TC-vid-109 (сценарий приемки 3.3): статус «конвертируется» →
    «готово» в списке БЕЗ перезагрузки страницы — автообновление
    (polling); после готовности опрос останавливается."""
    page = logged_in_page
    calls = {"n": 0}

    def payload():
        calls["n"] += 1
        if calls["n"] <= 2:  # первый список + тик опроса: еще конвертируется
            return _sample_items()
        items = _sample_items()
        for item in items["videos"]:
            if item["status"] in ("uploaded", "converting"):
                item["status"] = "ready"
                item["file_url"] = "/videos/" + item["id"] + "/video.mp4"
        return items

    _mock_api(page, payload)
    page.goto(f"{web_base_url}/video")
    converting = page.locator(".status-badge.status-converting")
    expect(converting).to_have_count(1)

    # Опрос (3 c) доводит статус до «готово» без перезагрузки.
    ready = page.locator('.v-card[data-video-id="' + "b" * 32 + '"] .status-ready')
    expect(ready).to_have_text(re.compile("готово"), timeout=15000)
    assert calls["n"] >= 3  # список перечитан, а не взят из кэша страницы
    # Проверка остановки опроса: все финальные — запросы прекращаются.
    before = calls["n"]
    page.wait_for_timeout(4000)
    assert calls["n"] == before
    page.wait_for_load_state("networkidle")
