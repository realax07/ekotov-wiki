"""UI-тесты страницы «Погода» (change weather-service, задача 3.4;
дельта specs/weather-service — Requirements «Раздел «Погода» в сайдбаре
и страница сервиса», «Карточка «Сегодня» с 8 метриками», «Прогноз на
7 дней», «Вид интерфейса по утвержденному мокапу A», «Недоступность
провайдера…», «Пустой кэш…»).

TC-weather-web-001 — пункт сайдбара «Погода» СТРОГО после «Видео»
(Scenario «Пункт сайдбара виден авторизованным», мокап A);
TC-weather-web-002 — неавторизованный: /weather → редирект /login
(Scenario «Неавторизованный — редирект на login»);
TC-weather-web-003 — состояние «данные»: карточка «Сегодня» (8 метрик)
и ровно 7 карточек-дней, days[0] с меткой today (мокап A, Scenario
«Полная карточка по мокапу A» / «Семь карточек с полным набором полей»);
TC-weather-web-004 — состояние «устаревшие»: баннер «Данные устарели» с
временем + карточки (Scenario «Отдача устаревшего кэша при отказе
провайдера», UI-часть);
TC-weather-web-005 — состояние «ошибка» и повтор: 503 → честное
сообщение + кнопка «Повторить» (Scenario «Честное сообщение вместо
данных», UI-часть); повтор после восстановления — данные.
Деградация метрики — прочерк «—» покрывается в 003 (давление null).

Стенд — session-фикстуры tests/web/conftest.py (uvicorn app + static,
Playwright-маршрутизация). Сервис weather на стенде не поднят — его
контракт (TTL/деградация/конверсии) покрыт юнит-сьютом
services/weather/tests (TC-weather-001…041); здесь проверяются каркас
страницы/сайдбара и 4 состояния UI — ответы /api/weather СТАБЯТСЯ
playwright-маршрутом (сеть и сервис не нужны).
"""

import json

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

# Стаб ответа /api/weather (контракт design §6): давление null — заодно
# покрывает деградацию метрики в прочерк (Scenario «Деградация при
# отсутствии метрики»).
WEATHER_OK = {
    "fetched_at": "2026-10-19T12:00:00+03:00",
    "stale": False,
    "today": {
        "temperature": 4.3, "description": "Дождь", "code": 63,
        "apparent": 1.2, "temp_max": 5.0, "temp_min": 1.0,
        "precipitation": 80, "wind": {"dir": "ЮЗ", "speed": 5.0},
        "humidity": 87, "pressure_mmhg": None,
    },
    "days": [
        {
            "date": f"2026-10-{19 + i}", "code": 63, "description": "Дождь",
            "temp_max": 5.0 - i, "temp_min": 1.0 - i, "precipitation": 80 - i,
            "wind": {"dir": "ЮЗ", "speed": 5.0},
        }
        for i in range(7)
    ],
}

WEATHER_STALE = {
    "fetched_at": "2026-10-19T11:00:00+03:00",
    "stale": True,
    "today": WEATHER_OK["today"],
    "days": WEATHER_OK["days"],
}


def _stub_route(page, payload, status=200):
    def handler(route):
        route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(payload, ensure_ascii=False),
        )

    page.route("**/api/weather", handler)
    return handler


def test_sidebar_weather_item_after_video(logged_in_page, web_base_url):
    """TC-weather-web-001 (Scenario «Пункт сайдбара виден авторизованным»):
    пункт «Погода» в сайдбаре, СТРОГО после «Видео», с иконкой
    (inline-SVG, .nav-icon); клик ведет на /weather, заголовок — «Погода»."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")

    weather_link = page.locator(".sidebar-nav .nav-item-weather")
    video_link = page.locator(".sidebar-nav .nav-item-video")
    expect(weather_link).to_be_visible()
    expect(video_link).to_be_visible()

    # Порядок — «Погода» сразу после «Видео» (мокап A).
    order = page.evaluate(
        "[...document.querySelectorAll('.sidebar-nav .nav-item')]"
        ".map((a) => a.className)"
    )
    assert order.index("nav-item nav-item-weather") == (
        order.index("nav-item nav-item-video") + 1
    )

    # Иконка в едином стиле эталона (inline-SVG .nav-icon, aria-hidden).
    icon = weather_link.locator("svg.nav-icon")
    expect(icon).to_have_count(1)
    expect(icon).to_have_attribute("aria-hidden", "true")

    # Клик → страница сервиса /weather (рендер ядра, заголовок по мокапу).
    weather_link.click()
    assert page.url.endswith("/weather")
    expect(page.get_by_role("heading", name="Погода")).to_be_visible()
    expect(page.locator("text=Москва · прогноз на 7 дней")).to_be_visible()


def test_weather_page_redirects_anonymous_to_login(page, web_base_url):
    """TC-weather-web-002 (Scenario «Неавторизованный — редирект на
    login»): без сессии /weather → редирект на /login (middleware ядра,
    паритет /video)."""
    page.goto(f"{web_base_url}/weather")
    page.wait_for_load_state()
    assert page.url.endswith("/login")


def test_weather_page_data_state_with_metrics(logged_in_page, web_base_url):
    """TC-weather-web-003 (Scenario «Полная карточка по мокапу A» +
    «Семь карточек с полным набором полей» + «Деградация при отсутствии
    метрики»): состояние «данные» — карточка «Сегодня» с метриками
    (давление null → прочерк «—», остальные целы), ровно 7 карточек-дней,
    первая с меткой today-mark; баннер устаревания скрыт."""
    page = logged_in_page
    _stub_route(page, WEATHER_OK)
    page.goto(f"{web_base_url}/weather")

    expect(page.locator("#weather-data")).to_be_visible()
    expect(page.locator("#weather-loading")).to_be_hidden()

    # Карточка «Сегодня»: температура, описание, ощущается, 6 метрик meta.
    expect(page.locator("#weather-temp")).to_have_text("+4°")
    expect(page.locator("#weather-desc")).to_have_text("Дождь")
    expect(page.locator("#weather-feels")).to_have_text("+1°")
    expect(page.locator("#weather-tmax")).to_have_text("+5°")
    expect(page.locator("#weather-tmin")).to_have_text("+1°")
    expect(page.locator("#weather-pop")).to_have_text("80\u2009%")
    expect(page.locator("#weather-wind")).to_have_text("ЮЗ, 5 м/с")
    expect(page.locator("#weather-humidity")).to_have_text("87\u2009%")
    # Деградация: давление null в API → прочерк «—», карточка цела.
    expect(page.locator("#weather-pressure")).to_have_text("—")

    # Прогноз: ровно 7 карточек, первая — today-mark.
    days = page.locator("#weather-days .day-card")
    expect(days).to_have_count(7)
    expect(days.first).to_have_class("day-card w-card today-mark")
    expect(days.nth(1)).to_have_class("day-card w-card")
    expect(days.first.locator(".dc-name")).to_have_text("Пн, 19.10")

    # Баннер устаревания в состоянии «данные» скрыт.
    expect(page.locator("#weather-stale-banner")).to_be_hidden()


def test_weather_page_stale_state_banner(logged_in_page, web_base_url):
    """TC-weather-web-004 (UI-часть Scenario «Отдача устаревшего кэша
    при отказе провайдера»): stale: true → баннер «Данные устарели» со
    временем последнего обновления (МСК) + карточки остаются."""
    page = logged_in_page
    _stub_route(page, WEATHER_STALE)
    page.goto(f"{web_base_url}/weather")

    expect(page.locator("#weather-data")).to_be_visible()
    banner = page.locator("#weather-stale-banner")
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("Данные устарели")
    # Время — из fetched_at (+03:00), в московском формате (не зависит
    # от таймзоны браузера).
    expect(page.locator("#weather-stale-time")).to_have_text("19.10.2026, 11:00 МСК")


def test_weather_page_error_state_and_retry(logged_in_page, web_base_url):
    """TC-weather-web-005 (UI-часть Scenario «Честное сообщение вместо
    данных»): 503 от API → честное сообщение «Не удалось получить данные
    погоды» + кнопка «Повторить» (без карточек-заглушек); повтор после
    восстановления — состояние «данные»."""
    page = logged_in_page
    _stub_route(page, {"error": "weather_unavailable"}, status=503)
    page.goto(f"{web_base_url}/weather")

    error_box = page.locator("#weather-error")
    expect(error_box).to_be_visible()
    expect(error_box).to_contain_text("Не удалось получить данные погоды")
    retry = page.locator("#weather-retry")
    expect(retry).to_be_visible()
    # Никаких карточек с выдуманными/нулевыми данными.
    expect(page.locator("#weather-data")).to_be_hidden()

    # Повторить после восстановления провайдера → состояние «данные».
    page.unroute("**/api/weather")
    _stub_route(page, WEATHER_OK)
    retry.click()
    expect(page.locator("#weather-data")).to_be_visible()
    expect(error_box).to_be_hidden()
