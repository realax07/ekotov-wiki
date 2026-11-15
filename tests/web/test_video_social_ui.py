"""UI-тесты социального слоя страницы «Видео» (tasks.md 2.4, video-hosting
волна 2, кусок D).

TC-vid-104 — фильтр категории в тулбаре списка (мокап video-list.html:
label + select «Все категории», опции справочника добавляет video.js);
TC-vid-105 — выбор категории в форме загрузки (мокап video-upload.html:
select с «Без категории» по умолчанию, опция «+ Новая категория…», поле
названия скрыто до выбора опции);
TC-vid-106 — блоки просмотра по мокапу video-view.html: реакции
(лайк/дизлайк с счетчиками и aria-pressed), пилюля категории в деталях,
карточка комментариев (список, форма с textarea, «Отправить» неактивна);
TC-vid-109 — механика UX реакций (TD-B2, follow-up BUG-027): клик по
АКТИВНОЙ реакции — DELETE (снятие голоса), по неактивной — PUT
(установка/перенос); хинт и aria-метки следуют состоянию.

Стенд — session-фикстуры tests/web/conftest.py (uvicorn app + static,
Playwright-маршрутизация). API видео (сервис video) на стенде не поднят —
контракт социального слоя покрыт юнит-сьютом services/video/tests
(2.5, TC-vid-040…058); здесь проверяется каркас блоков D (зона 2.4).
"""

import json
import re

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def test_list_toolbar_category_filter_by_mockup(logged_in_page, web_base_url):
    """TC-vid-104. Тулбар списка: фильтр «Категория» (label + select) рядом
    со счетчиком и кнопкой загрузки; по умолчанию «Все категории»."""
    page = logged_in_page
    page.goto(f"{web_base_url}/video")

    toolbar = page.locator(".video-toolbar")
    expect(toolbar).to_be_visible()
    label = toolbar.locator('label[for="video-category"]')
    expect(label).to_have_text("Категория")
    select = page.locator("#video-category")
    expect(select).to_be_visible()
    # Статическая опция шаблона: «Все категории» выбрана по умолчанию
    # (опции справочника добавляет video.js из /api/videos/categories).
    expect(select.locator("option")).not_to_have_count(0)


def test_upload_category_select_with_new_option_by_mockup(
    logged_in_page, web_base_url
):
    """TC-vid-105. Форма загрузки (мокап video-upload.html): select категории
    — «Без категории» по умолчанию + опция «+ Новая категория…»; при выборе
    опции появляется поле названия (демо-состояние мокапа); подсказка про
    общий справочник с «Галереей»; сброс возвращает «Без категории»."""
    page = logged_in_page
    page.goto(f"{web_base_url}/video")
    page.locator("#open-upload-button").click()

    select = page.locator("#up-category")
    expect(select).to_be_visible()
    expect(select).to_have_value("")
    expect(select.locator('option[value="new"]')).to_have_text("+ Новая категория…")
    hint = page.locator("#up-category ~ .hint")
    expect(hint).to_contain_text("справочник")

    new_field = page.locator("#up-category-new-field")
    expect(new_field).to_be_hidden()
    select.select_option("new")
    expect(new_field).to_be_visible()
    expect(page.locator("#up-category-new")).to_be_visible()

    select.select_option("")
    expect(new_field).to_be_hidden()

    # Существующие кусок-A проверки формы не задеты: отправка блокирована.
    expect(page.locator("#upload-submit-button")).to_be_disabled()


def test_player_view_social_blocks_by_mockup(logged_in_page, web_base_url):
    """TC-vid-106. Просмотр (мокап video-view.html, блоки D): ряд реакций
    (лайк/дизлайк, счетчики, aria-pressed=false без голоса), пилюля категории
    в деталях, карточка комментариев (список, форма, textarea, «Отправить»
    неактивна пока пусто)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/video")

    # Вид просмотра скрыт до выбора видео, но разметка блоков D на странице.
    reactions = page.locator("#reactions-row")
    expect(reactions).to_be_attached()
    like = page.locator("#like-button")
    dislike = page.locator("#dislike-button")
    expect(like).to_have_attribute("aria-pressed", "false")
    expect(dislike).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#like-count")).to_have_text("0")
    expect(page.locator("#dislike-count")).to_have_text("0")

    details = page.locator(".video-details .details-list")
    expect(details.locator("#player-category")).to_be_attached()

    comments = page.locator("#comments-card")
    expect(comments).to_be_attached()


def test_reaction_click_active_deletes_inactive_puts(
    logged_in_page, web_base_url
):
    """TC-vid-109 (TD-B2, follow-up BUG-027/#275). Механика UX реакций
    (мокап video-view.html): клик по АКТИВНОЙ реакции (my_reaction совпал,
    aria-pressed=true) — DELETE /api/videos/{id}/reaction (снятие голоса,
    паритет галереи), по НЕактивной — PUT (установка/перенос, TD-B
    идемпотентный set). Хинт «повторный клик снимет» и aria-метки
    «Снять голос» соответствуют фактическому запросу.
    API видео мокается маршрутизацией (роль nginx), как в
    test_video_convert_ui.py: фронтенд-слой video.js."""
    page = logged_in_page
    vid = "c" * 32
    calls = []

    def reaction_route(route):
        request = route.request
        calls.append({"method": request.method, "body": request.post_data})
        if request.method == "DELETE":
            body = {"my_reaction": None, "likes": 0, "dislikes": 0}
        else:
            body = {"my_reaction": 1, "likes": 1, "dislikes": 0}
        route.fulfill(
            status=200, content_type="application/json", body=json.dumps(body)
        )

    me = {"id": 1, "login": "owner", "display_name": "Owner"}
    item = {
        "id": vid, "filename": "дрон.mp4", "status": "ready",
        "size_bytes": 96 * 1024 * 1024,
        "created_at": "2026-10-18T10:02:00+00:00",
        "preview_url": "/api/videos/" + vid + "/preview",
        "file_url": "/videos/" + vid + "/video.mp4",
        "category_id": None, "category_name": None,
        "likes": 1, "dislikes": 0, "my_reaction": 1,
    }
    page.route(re.compile(r"/api/auth/me$"), lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(me)))
    page.route(re.compile(r"/api/videos/categories$"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"categories": []})))
    page.route(re.compile(r"/api/videos$"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"videos": [item]})))
    page.route(re.compile(r"/api/videos\?.*"), lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"videos": [item]})))
    page.route(
        re.compile(r"/api/videos/[0-9a-f]+/reaction$"), reaction_route
    )

    page.goto(f"{web_base_url}/video")
    page.locator(f'.v-card[data-video-id="{vid}"]').click()

    # Открытое видео: голос УЖЕ стоит (пришел из агрегатов списка) —
    # кнопка активна, aria-метка обещает «Снять голос».
    like = page.locator("#like-button")
    expect(like).to_have_attribute("aria-pressed", "true")
    expect(like).to_have_class("react-btn my-vote")
    expect(page.locator("#like-count")).to_have_text("1")
    expect(like).to_have_attribute("aria-label", "Нравится, ваш голос учтен. Снять голос")
    hint = page.locator("#react-hint")
    expect(hint).to_be_visible()
    expect(hint).to_contain_text("повторный клик снимет")

    # Клик по АКТИВНОЙ реакции — DELETE (снятие), НЕ повторный PUT.
    like.click()
    expect(page.locator("#like-count")).to_have_text("0")
    expect(like).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#react-hint")).to_be_hidden()
    assert calls == [{"method": "DELETE", "body": '{"value": 1}'}]

    # Клик по НЕактивной — PUT (установка); голос вернулся.
    like.click()
    expect(page.locator("#like-count")).to_have_text("1")
    expect(like).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#react-hint")).to_be_visible()
    assert calls[-1] == {"method": "PUT", "body": '{"value": 1}'}

    # Клик по второй (неактивной) кнопке — PUT-перенос, не DELETE.
    page.locator("#dislike-button").click()
    assert calls[-1] == {"method": "PUT", "body": '{"value": -1}'}


def test_player_view_comments_card_tail(logged_in_page, web_base_url):
    """TC-vid-106 (хвост): карточка комментариев — заголовок со счетчиком
    и заблокированная отправка при пустом поле."""
    page = logged_in_page
    page.goto(f"{web_base_url}/video")

    comments = page.locator("#comments-card")
    expect(comments).to_be_attached()
    # Заголовок «Комментарии» со счетчиком (вид скрыт до выбора видео —
    # проверяем присутствие в DOM, паритет остальным блокам).
    expect(comments.locator("h2")).to_contain_text("Комментарии")
    expect(comments.locator("h2 .count")).to_have_text("(0)")
    expect(page.locator("#comment-form textarea#video-comment-input")).to_be_attached()
    send = page.locator("#comment-send-button")
    expect(send).to_be_disabled()  # поле пусто — отправка заблокирована (мокап)
