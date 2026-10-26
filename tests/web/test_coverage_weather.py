"""coverage-backfill-1; бэкфилл автотестов Must-кейсов weather-service
(test-model/approved/weather-service/, группа C) — 11 из 12 кейсов,
TC-weather-019 — skip (нужен docker-стенд):

TC-weather-001: Пункт сайдбара «Погода» виден авторизованным и ведет на /weather
TC-weather-005: Деградация: отсутствующая метрика — прочерк, карточка не ломается
TC-weather-006: Прогноз на неделю: ровно 7 карточек с полным набором полей по датам
TC-weather-007: Граница: «сегодня» — первая карточка прогноза, согласована с карточкой «Сегодня»
TC-weather-008: Запрос к провайдеру: зафиксированные координаты, tz, 7 дней, м/с и полный набор полей
TC-weather-015: Битый JSON провайдера не затирает кэш — паритет отказу провайдера
TC-weather-016: Пустой кэш + недоступный провайдер: 503 JSON, честный UI без заглушек, кэш не создан
TC-weather-017: Таймаут 5 с считается ошибкой провайдера; воркер не блокируется
TC-weather-018: Граница: ровно один автоматический повтор при ошибке провайдера
TC-weather-019: Деградация: остановка контейнера weather — быстрый 503 nginx, стек работает (SKIP — docker-стенд)
TC-weather-023: Вид по утвержденному мокапу A; без внешних библиотек/CDN; B/C не реализованы
TC-weather-025: NFR: отзывчивость при отказе провайдера — /api/weather ≤ ~11 с, стек не деградирует

Стиль — существующие weather-тесты: API/юнит-часть — TestClient над
app.main сервиса (services/weather) с изолированными env (временная
sqlite users/sessions + временный кэш-файл), провайдер — СТАБ/МокТранспорт,
сеть не трогаем; UI-часть — стенд tests/web/conftest.py (uvicorn + static),
ответы /api/weather стабятся playwright-маршрутом. Фикстуры стенда —
второй пользователь стенда wife (роль pe из кейсов; seed QaWife_Pass_2!).

Прогон: pytest tests/web/test_coverage_weather.py (venv wiki; без сети —
исключение: hang-транспорты TC-weather-017/025 дают реальное течение
таймаутов провайдера, ~25 с на файл).
"""

import asyncio
import hashlib
import json
import re
import socket
import sys
import threading
import time
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Пакет app сервиса weather — в process только здесь (tests/web больше
# никого не импортирует in-process, монолит поднимается subprocess'ами).
WEATHER_DIR = REPO_ROOT / "services" / "weather"
if str(WEATHER_DIR) not in sys.path:
    sys.path.insert(0, str(WEATHER_DIR))

import httpx  # noqa: E402
from playwright.sync_api import expect  # noqa: E402

from app import provider as provider_mod  # noqa: E402
from app import cache as wcache  # noqa: E402
from app.middleware import SESSION_COOKIE_NAME  # noqa: E402
from app.provider import ProviderError, fetch, normalize  # noqa: E402

pytestmark = pytest.mark.must

MSK = timezone(timedelta(hours=3))
SESSION_TOKEN = "cov-weather-session-token"
# Python weekday(): Пн=0 (в weather.html JS-массив идет от Вс=0 — getUTCDay).
WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _run(coro):
    """asyncio.run в отдельном потоке: после sync-Playwright тестов в
    главном потоке сессии остается активный loop-диспетчер — прямой
    asyncio.run в тесте падает («cannot be called from a running event
    loop»). Корутина выполняется в чистом потоке, исключение — наверх."""

    def target(box):
        try:
            box["result"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001 — пробрасываем в тест
            box["error"] = exc

    box: dict = {}
    thread = threading.Thread(target=target, args=(box,), daemon=True)
    thread.start()
    thread.join(timeout=60)
    assert not thread.is_alive(), "async-сценарий не завершился за 60 с"
    if "error" in box:
        raise box["error"]
    return box["result"]


class _LocalProvider:
    """Локальный stand-in провайдера Open-Meteo (в тесте PROVIDER_URL
    патчится на него — внешней сети нет):
    - hang=True: соединение принял — ответа нет (реальный read-таймаут 5 с);
    - fail_first=N: первые N соединений обрываются без ответа
      (ReadError у клиента), дальше — валидный ответ Open-Meteo.
    connections — моменты подключений (счетчик попыток провайдера)."""

    def __init__(self, *, hang: bool = False, fail_first: int = 0):
        self.hang = hang
        self.fail_first = fail_first
        self._srv = socket.socket()
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(8)
        self.port = self._srv.getsockname()[1]
        self.connections: list[float] = []
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        served = 0
        while True:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            self.connections.append(time.monotonic())
            try:
                conn.recv(65536)  # заголовки запроса клиента
                if self.hang:
                    pass  # молчим: клиент висит до read-таймаута
                elif served < self.fail_first:
                    conn.close()  # обрыв соединения — ReadError
                else:
                    body = json.dumps(provider_raw()).encode()
                    head = (
                        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
                    )
                    conn.sendall(head.encode() + body)
                    conn.close()
            except OSError:
                pass
            served += 1

    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1/forecast"

    def close(self):
        self._srv.close()


# ------------------------------------------------------------ окружение

@pytest.fixture()
def wenv(tmp_path, monkeypatch):
    """Изолированные env weather-сервиса: временная БД + временный кэш."""
    db_path = tmp_path / "wiki.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE users (
              id INTEGER PRIMARY KEY,
              login TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL,
              display_name TEXT, role TEXT, bio TEXT,
              avatar_path TEXT, avatar_updated_at TEXT
            );
            CREATE TABLE sessions (
              token TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id),
              created_at TEXT NOT NULL,
              expires_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO users (id, login, password_hash, display_name)"
            " VALUES (1, 'owner', 'x', 'Owner')"
        )
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at)"
            " VALUES (?, 1, ?, ?)",
            (
                SESSION_TOKEN,
                datetime.now(timezone.utc).isoformat(),
                (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("EKOTOV_WIKI_DB_PATH", str(db_path))
    monkeypatch.setenv(
        "EKOTOV_WEATHER_CACHE_PATH", str(tmp_path / "weather-cache" / "weather.json")
    )
    monkeypatch.setenv("EKOTOV_WEATHER_USER_AGENT", "ekotov-wiki-weather-tests/1.0")
    return tmp_path / "weather-cache" / "weather.json"


@pytest.fixture()
def wclient(wenv):
    """TestClient над app.main weather-сервиса (изолированные env)."""
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _cookies():
    return {SESSION_COOKIE_NAME: SESSION_TOKEN}


# ------------------------------------------------------- фикстуры данных

def moscow_today():
    """Текущая дата в Europe/Moscow (фиксированный UTC+3, design §3)."""
    return datetime.now(MSK).date()


def provider_raw(start=None, payload_id: int = 1) -> dict:
    """Валидный ответ провайдера Open-Meteo (схема design §3) — 7 дней
    от заданной даты (дефолт — сегодня по Москве; паритет
    services/weather/tests/helpers.py, но даты привязаны к «сегодня»).
    daily[0] заведомо отличается от остальных дней (TC-weather-007)."""
    start = start or moscow_today()
    dates = [(start + timedelta(days=i)).isoformat() for i in range(7)]
    return {
        "latitude": 55.7539,
        "longitude": 37.6208,
        "timezone": "Europe/Moscow",
        "generationtime_ms": float(payload_id),
        "current": {
            "time": f"{dates[0]}T12:00",
            "interval": 900,
            "temperature_2m": 4.3,
            "apparent_temperature": 1.2,
            "weather_code": 63,
            "relative_humidity_2m": 87,
            "surface_pressure": 984.0,
            "wind_speed_10m": 5.0,
            "wind_direction_10m": 225,
        },
        "daily": {
            "time": dates,
            "weather_code": [63, 3, 2, 61, 3, 2, 71],
            "temperature_2m_max": [12.3, 5.1, 7.0, 6.0, 4.0, 2.0, 1.0],
            "temperature_2m_min": [1.0, 2.0, 3.0, 2.0, 0.0, -1.0, -2.0],
            "precipitation_probability_max": [80, 30, 15, 55, 40, 20, 65],
            "wind_speed_10m_max": [5.0, 4.0, 3.0, 6.0, 5.0, 3.0, 4.0],
            "wind_direction_10m_dominant": [225, 270, 225, 180, 315, 0, 45],
        },
    }


def payload(start=None, *, fetched_at=None, payload_id: int = 1) -> dict:
    """Полезная нагрузка контракта §6 через provider.normalize (БЕЗ
    stale — его ставит routes/ playwright-стаб)."""
    data = normalize(provider_raw(start, payload_id))
    if fetched_at is not None:
        data["fetched_at"] = (
            fetched_at.isoformat(timespec="seconds")
            if isinstance(fetched_at, datetime)
            else fetched_at
        )
    return data


def _stub_fetch(calls, *, result=None, fail_times=0, error=None):
    """Async-стаб app.provider.fetch (стиль services/weather/tests):
    считает вызовы, первые fail_times попыток кидает ProviderError."""

    async def _fetch(user_agent_str=None, transport=None):
        calls.append(user_agent_str)
        if len(calls) <= fail_times:
            raise error or ProviderError("provider down (stub)")
        return result if result is not None else payload(payload_id=len(calls))

    return _fetch


def _stub_route(page, payload_body, status=200):
    """Playwright-стаб /api/weather (сервис на стенде не поднят — стиль
    tests/web/test_weather_ui.py)."""

    def handler(route):
        route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(payload_body, ensure_ascii=False),
        )

    page.route("**/api/weather", handler)
    return handler


def _expected_day_name(date) -> str:
    """Формат dc-name карточки прогноза (weather.html: «Пн, 19.10»)."""
    return f"{WEEKDAYS_SHORT[date.weekday()]}, {date.day}.{date.month:02d}"


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------- кейсы UI

@pytest.mark.e2e
@pytest.mark.web
def test_tc_weather_001_sidebar_item_visible_and_navigates(
    logged_in_page, web_base_url
):
    """TC-weather-001 (Scenario «Пункт сайдбара виден авторизованным»):
    у авторизованного (owner, затем второй пользователь wife/pe) в
    сайдбаре есть пункт «Погода» сразу после «Видео» с иконкой в едином
    стиле; клик ведет на /weather (рендер ядра, active_page=weather);
    виджетов «Погода» в других разделах нет."""
    page = logged_in_page

    for user in ("owner", "wife"):
        page.goto(f"{web_base_url}/board")
        weather_link = page.locator(".sidebar-nav .nav-item-weather")
        video_link = page.locator(".sidebar-nav .nav-item-video")
        expect(weather_link).to_be_visible()
        expect(video_link).to_be_visible()

        # «Погода» присутствует непосредственно после «Видео».
        order = page.evaluate(
            "[...document.querySelectorAll('.sidebar-nav .nav-item')]"
            ".map((a) => a.className)"
        )
        assert order.index("nav-item nav-item-weather") == (
            order.index("nav-item nav-item-video") + 1
        )
        # Иконка в едином стиле эталона (inline-SVG, как «Видео»/«Галерея»).
        expect(weather_link.locator("svg.nav-icon")).to_have_count(1)

        # Клик → страница сервиса /weather (рендер ядра, заголовок мокапа).
        weather_link.click()
        assert page.url == f"{web_base_url}/weather"
        expect(page.get_by_role("heading", name="Погода")).to_be_visible()
        expect(page.locator("text=Москва · прогноз на 7 дней")).to_be_visible()

        if user == "owner":
            # Виджетов «Погода» в других разделах нет.
            for section in ("/board", "/video"):
                page.goto(f"{web_base_url}{section}")
                expect(page.locator(".weather-page")).to_have_count(0)
            # Перелогин под вторым пользователем (wife — роль pe из кейса):
            # logout в контексте браузера (куки сессии owner), затем вход wife.
            page.request.post(f"{web_base_url}/api/auth/logout")
            page.goto(f"{web_base_url}/login")
            page.get_by_label("Логин").fill("wife")
            page.get_by_label("Пароль").fill("QaWife_Pass_2!")
            page.get_by_role("button", name="Войти").click()
            page.get_by_role("heading", name="Доска", exact=True).wait_for()


@pytest.mark.e2e
@pytest.mark.web
def test_tc_weather_005_missing_metric_dash_ui(logged_in_page, web_base_url):
    """TC-weather-005, UI-часть (Scenario «Деградация при отсутствии
    метрики»): давление и влажность null → прочерк «—» в карточке
    «Сегодня», остальные метрики на месте, карточка не схлопывается."""
    page = logged_in_page
    body = payload()
    body["today"]["pressure_mmhg"] = None
    body["today"]["humidity"] = None
    _stub_route(page, body)
    page.goto(f"{web_base_url}/weather")

    expect(page.locator("#weather-data")).to_be_visible()
    expect(page.locator("#weather-pressure")).to_have_text("—")
    expect(page.locator("#weather-humidity")).to_have_text("—")
    # Остальные метрики не задеты, карточка цела.
    expect(page.locator("#weather-temp")).to_have_text("+4°")
    expect(page.locator("#weather-desc")).to_have_text("Дождь")
    expect(page.locator("#weather-tmax")).to_have_text("+12°")
    expect(page.locator("#weather-pop")).to_have_text("80\u2009%")
    expect(page.locator("#weather-wind")).to_have_text("ЮЗ, 5 м/с")


@pytest.mark.e2e
@pytest.mark.web
def test_tc_weather_006_seven_day_cards_full_fields(logged_in_page, web_base_url):
    """TC-weather-006 (Scenario «Семь карточек с полным набором полей»):
    секция «Прогноз на неделю» — ровно 7 карточек (сетка 4-в-ряд по
    мокапу A), у каждой — дата, описание, дневная/ночная температура,
    осадки (%), ветер; порядок строго по возрастанию даты, названия
    дней — по данным Europe/Moscow."""
    page = logged_in_page
    # Сетка мокапа A — 4-в-ряд (мобильная раскладка ≤880px — 2 колонки).
    page.set_viewport_size({"width": 1440, "height": 900})
    body = payload()
    dates = [datetime.fromisoformat(d).date() for d in
             (day["date"] for day in body["days"])]
    _stub_route(page, body)
    page.goto(f"{web_base_url}/weather")

    days = page.locator("#weather-days .day-card")
    expect(days).to_have_count(7)
    for i in range(7):
        card = days.nth(i)
        # Дата (по возрастанию), описание, день/ночь, осадки, ветер.
        expect(card.locator(".dc-name")).to_have_text(_expected_day_name(dates[i]))
        expect(card.locator(".dc-desc")).not_to_have_text("")
        expect(card.locator(".dc-t")).to_have_text(
            ("+" if round(body["days"][i]["temp_max"]) > 0 else "")
            + f"{round(body['days'][i]['temp_max'])}°"
        )
        expect(card.locator(".dc-n")).to_have_text(
            ("+" if round(body["days"][i]["temp_min"]) > 0 else "")
            + f"{round(body['days'][i]['temp_min'])}°"
        )
        expect(card.locator(".dc-pop")).to_have_text(
            f"Осадки: {round(body['days'][i]['precipitation'])}%"
        )
        expect(card.locator(".dc-wind")).to_contain_text("м/с")
    # Сетка мокапа A — 4 в ряд.
    columns = page.evaluate(
        "getComputedStyle(document.querySelector('#weather-days'))"
        ".gridTemplateColumns.split(' ').length"
    )
    assert columns == 4


@pytest.mark.e2e
@pytest.mark.web
def test_tc_weather_007_today_is_first_forecast_day(logged_in_page, web_base_url):
    """TC-weather-007 (Scenario «Сегодня входит в прогноз недели»):
    первая карточка прогноза — текущий московский день X, окно прогноза
    ровно [X .. X+6]; максимум/минимум первой карточки совпадают с
    карточкой «Сегодня» (тот же daily[0])."""
    page = logged_in_page
    today = moscow_today()
    body = payload(start=today)
    _stub_route(page, body)
    page.goto(f"{web_base_url}/weather")

    days = page.locator("#weather-days .day-card")
    expect(days).to_have_count(7)
    expect(days.first).to_have_class("day-card w-card today-mark")
    expect(days.first.locator(".dc-name")).to_have_text(_expected_day_name(today))
    # Согласованность с карточкой «Сегодня»: те же max/min (daily[0]).
    expect(page.locator("#weather-tmax")).to_have_text("+12°")
    expect(days.first.locator(".dc-t")).to_have_text("+12°")
    expect(page.locator("#weather-tmin")).to_have_text("+1°")
    expect(days.first.locator(".dc-n")).to_have_text("+1°")
    expect(page.locator("#weather-today-date")).to_contain_text("Сегодня")


# ------------------------------------------------- кейсы API/юнит-уровня

def test_tc_weather_005_missing_metric_api_variants(wclient, wenv, monkeypatch):
    """TC-weather-005, API-часть: три прогона провайдера — surface_pressure
    null, surface_pressure отсутствует, relative_humidity_2m отсутствует.
    Варьируемое поле деградирует точечно (null → прочерк во фронтенде),
    остальные 7 метрик и 7 дней не сломаны, 5xx нет."""
    baseline = payload()["today"]
    cases = (
        ("pressure_mmhg", lambda raw: raw["current"].__setitem__("surface_pressure", None)),
        ("pressure_mmhg", lambda raw: raw["current"].pop("surface_pressure")),
        ("humidity", lambda raw: raw["current"].pop("relative_humidity_2m")),
    )
    for missing_key, mutate in cases:
        # Прогон с чистого тома: успешный ответ кэшируется на 60 минут.
        wenv.unlink(missing_ok=True)
        raw = provider_raw()
        mutate(raw)
        monkeypatch.setattr(
            "app.provider.fetch", _stub_fetch([], result=normalize(raw))
        )
        response = wclient.get("/api/weather", cookies=_cookies())
        assert response.status_code == 200
        body = response.json()
        # Варьируемое поле деградирует точечно (прочерк «—» во фронтенде),
        # остальные 7 метрик — как в полном ответе, карточка не схлопнулась.
        assert body["today"][missing_key] is None
        for key, value in baseline.items():
            if key == missing_key:
                continue
            assert body["today"][key] == value, key
        assert len(body["days"]) == 7


def test_tc_weather_006_seven_days_contract(wclient, monkeypatch):
    """TC-weather-006, API-часть: days — ровно 7 с полным набором полей
    (дата, код/описание WMO, день/ночь, осадки %, ветер), порядок
    строго по возрастанию даты, fetched_at — московский offset."""
    monkeypatch.setattr("app.provider.fetch", _stub_fetch([], result=payload()))
    body = wclient.get("/api/weather", cookies=_cookies()).json()
    days = body["days"]
    assert len(days) == 7
    dates = [day["date"] for day in days]
    assert dates == sorted(dates)
    assert dates == [
        (moscow_today() + timedelta(days=i)).isoformat() for i in range(7)
    ]
    for day in days:
        assert set(day) == {
            "date", "code", "description", "temp_max", "temp_min",
            "precipitation", "wind",
        }
        assert set(day["wind"]) == {"dir", "speed"}
        assert day["description"]
    assert body["fetched_at"].endswith("+03:00")


def test_tc_weather_007_today_matches_first_day(wclient, monkeypatch):
    """TC-weather-007, API-часть: days[0] — день X (сегодня по Москве),
    max/min первой карточки == max/min карточки «Сегодня» (тот же
    daily[0], заведомо отличный от остальных), окно ровно [X .. X+6]."""
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch([], result=payload(payload_id=7))
    )
    body = wclient.get("/api/weather", cookies=_cookies()).json()
    today, days = body["today"], body["days"]
    assert days[0]["date"] == moscow_today().isoformat()
    assert [day["date"] for day in days] == [
        (moscow_today() + timedelta(days=i)).isoformat() for i in range(7)
    ]
    assert days[0]["temp_max"] == today["temp_max"] == 12.3  # заведомо свой
    assert days[0]["temp_min"] == today["temp_min"]
    assert days[0]["precipitation"] == today["precipitation"]


def test_tc_weather_008_provider_request_fixed_params(monkeypatch):
    """TC-weather-008 (Scenario «Запрос к провайдеру с зафиксированными
    параметрами»): URL — Open-Meteo Forecast API; latitude=55.7539,
    longitude=37.6208, timezone=Europe/Moscow, forecast_days=7,
    wind_speed_unit=ms; полный набор current/daily-полей;
    current.precipitation НЕ запрашивается; других внешних вызовов
    нет (счетчик mock-транспорта = 1)."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=provider_raw())

    _run(fetch(transport=httpx.MockTransport(handler)))

    assert len(captured) == 1  # никаких других внешних HTTP-вызовов
    request = captured[0]
    assert str(request.url).startswith("https://api.open-meteo.com/v1/forecast")
    params = dict(request.url.params)
    assert params["latitude"] == "55.7539"
    assert params["longitude"] == "37.6208"
    assert params["timezone"] == "Europe/Moscow"
    assert params["forecast_days"] == "7"
    assert params["wind_speed_unit"] == "ms"
    assert set(params["current"].split(",")) == {
        "temperature_2m", "apparent_temperature", "weather_code",
        "relative_humidity_2m", "surface_pressure", "wind_speed_10m",
        "wind_direction_10m",
    }
    assert "precipitation" not in params["current"].split(",")
    assert set(params["daily"].split(",")) == {
        "weather_code", "temperature_2m_max", "temperature_2m_min",
        "precipitation_probability_max", "wind_speed_10m_max",
        "wind_direction_10m_dominant",
    }


def test_tc_weather_015_broken_json_keeps_cache(wclient, wenv, monkeypatch):
    """TC-weather-015 (Scenario «Битый ответ провайдера не затирает кэш»):
    провайдер отвечает 200 с телом «not-json{{» (прогон 1) и валидным,
    но урезанным JSON без current (прогон 2) → ProviderError на
    провайдер-уровне; routes при этом ведет себя как при отказе
    провайдера: 200 устаревших данных, stale: true, прежний fetched_at,
    кэш-файл побайтово сохранен (sha256 совпал)."""
    # Прогон 1/2: невалидный и неполный ответ отброшен провайдер-клиентом.
    broken_bodies = (
        lambda: httpx.Response(200, text="not-json{{"),
        lambda: httpx.Response(200, json={"daily": provider_raw()["daily"]}),
    )
    for make_response in broken_bodies:
        with pytest.raises(ProviderError):
            _run(
                fetch(
                    transport=httpx.MockTransport(
                        lambda request, f=make_response: f()
                    )
                )
            )

    # Паритет отказу провайдера на роутере + кэш побайтово цел.
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=61)
    wcache.write(payload(fetched_at=stale_time))
    before_bytes = wenv.read_bytes()
    calls: list = []
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch(calls, fail_times=99)
    )
    response = wclient.get("/api/weather", cookies=_cookies())
    assert response.status_code == 200
    body = response.json()
    assert body["stale"] is True
    assert body["fetched_at"] == stale_time.isoformat(timespec="seconds")
    assert wenv.read_bytes() == before_bytes  # битым ответом НЕ затерт
    assert _file_hash(wenv) == hashlib.sha256(before_bytes).hexdigest()


def test_tc_weather_016_empty_cache_provider_down_is_503(wclient, wenv, monkeypatch):
    """TC-weather-016, API-часть (Scenario «Честное сообщение вместо
    данных»): том кэша пуст И провайдер недоступен → 503
    {\"error\": \"weather_unavailable\"} с Retry-After; кэш-файл
    попыткой НЕ создан; карточек с нулевыми/выдуманными данными нет
    (UI-часть — в test_..._honest_error_ui)."""
    calls: list = []
    monkeypatch.setattr("app.provider.fetch", _stub_fetch(calls, fail_times=99))
    response = wclient.get("/api/weather", cookies=_cookies())
    assert response.status_code == 503
    assert response.json() == {"error": "weather_unavailable"}
    assert response.headers.get("Retry-After") == "60"
    assert not wenv.exists()  # кэш-файл не создан


@pytest.mark.e2e
@pytest.mark.web
def test_tc_weather_016_honest_error_ui(logged_in_page, web_base_url):
    """TC-weather-016, UI-часть: 503 от API → страница показывает «Не
    удалось получить данные погоды» с кнопкой «Повторить»; карточек с
    выдуманными/нулевыми данными нет."""
    page = logged_in_page
    _stub_route(page, {"error": "weather_unavailable"}, status=503)
    page.goto(f"{web_base_url}/weather")

    error_box = page.locator("#weather-error")
    expect(error_box).to_be_visible()
    expect(error_box).to_contain_text("Не удалось получить данные погоды")
    expect(page.locator("#weather-retry")).to_be_visible()
    expect(page.locator("#weather-data")).to_be_hidden()


def test_tc_weather_017_provider_timeout_is_error_worker_free(wclient, monkeypatch):
    """TC-weather-017 (Scenario «Таймаут считается ошибкой провайдера»):
    соединение установлено, ответа нет (hang) → чтение прерывается по
    таймауту 5 с (не вечно), фиксируется ошибка провайдера и переход к
    ровно одному повтору (подключение №2 через ~6 с: 5 с таймаут + 1 с
    пауза), после второй неудачи — ProviderError (деградация по
    TC-weather-018); параллельный /api/health сервиса отвечает без
    задержки — воркер не заблокирован зависшим вызовом."""
    hang = _LocalProvider(hang=True)
    try:
        monkeypatch.setattr(provider_mod, "PROVIDER_URL", hang.url())
        result: dict = {}

        def run_fetch():
            result["started"] = time.monotonic()
            try:
                _run(fetch())
                result["error"] = None
            except ProviderError as exc:
                result["error"] = exc

        thread = threading.Thread(target=run_fetch, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        _wakeup = threading.Event()
        while not hang.connections and time.monotonic() < deadline:
            _wakeup.wait(0.05)

        # Воркер не блокирован: health отвечает мгновенно, пока fetch висит.
        health_started = time.monotonic()
        health = wclient.get("/api/health")
        health_elapsed = time.monotonic() - health_started
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        assert health_elapsed < 2.0

        thread.join(timeout=30)
        assert not thread.is_alive()
        # Обе попытки подключались и прерваны по таймауту чтения 5 с
        # (повтор начался через ~6 с после первой: 5 с + пауза 1 с).
        assert len(hang.connections) == 2
        gap = hang.connections[1] - hang.connections[0]
        assert 5.0 <= gap <= 8.0, f"повтор начался через {gap:.1f} с, ждали ~6 с"
        assert isinstance(result["error"], ProviderError)
    finally:
        hang.close()


def test_tc_weather_018_exactly_one_retry(wclient, monkeypatch):
    """TC-weather-018 (Scenario «Ровно один автоматический повтор»):
    fail→ok — провайдер вызван ровно 2 раза (попытка + повтор с паузой
    ~1 с), данные получены и сохранены в кэш, ответ без stale;
    fail→fail и fail→fail→fail — ровно 2 вызова, третьего повтора нет
    (ProviderError); суммарное время двух попыток ≤ ~11 с."""

    def scenario(handlers_bodies):
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            step = len(attempts)
            if step in handlers_bodies.get("fail_steps", (1,)):
                raise httpx.ConnectError("boom", request=request)
            return httpx.Response(200, json=provider_raw())

        started = time.monotonic()
        try:
            data = _run(fetch(transport=httpx.MockTransport(handler)))
            error = None
        except ProviderError as exc:
            data, error = None, exc
        return attempts, data, error, time.monotonic() - started

    # 1) первая попытка — ошибка, повтор — успех: ровно 2 вызова.
    attempts, data, error, elapsed = scenario({"fail_steps": (1,)})
    assert error is None and len(attempts) == 2
    assert data["days"][0]["description"] == "Дождь"
    assert elapsed <= 11.0  # 2 попытки + пауза ~1 с — с запасом
    # 2) обе неудачи: ровно 2 вызова, далее ProviderError.
    attempts, data, error, elapsed = scenario({"fail_steps": (1, 2)})
    assert error is not None and len(attempts) == 2
    assert elapsed <= 11.0
    # 3) три подряд ошибки: третьего повтора НЕТ — по-прежнему 2 вызова.
    attempts, data, error, elapsed = scenario({"fail_steps": (1, 2, 3)})
    assert error is not None and len(attempts) == 2

    # Успешный повтор на роутере: данные сохранены в кэш, ответ без stale.
    # Реальный fetch через локальный провайдер (первое соединение — обрыв,
    # второе — валидный ответ): повтор происходит ВНУТРИ fetch.
    flaky = _LocalProvider(fail_first=1)
    try:
        monkeypatch.setattr(provider_mod, "PROVIDER_URL", flaky.url())
        body = wclient.get("/api/weather", cookies=_cookies()).json()
        assert len(flaky.connections) == 2  # попытка + ровно один повтор
        assert body["stale"] is False
        cached = wcache.read()
        assert cached is not None
        assert cached == {
            key: body[key] for key in ("fetched_at", "today", "days")
        }  # ответ свежими данными сохранен в кэш
    finally:
        flaky.close()


@pytest.mark.skip(
    reason="TC-weather-019 требует docker-стенд wiki-test (compose.test.yaml): "
    "docker stop контейнера weather, замер управляемого nginx-503 с "
    "Retry-After (< 1–2 с, не 502/504) и проверку остальных разделов на "
    "живом стеке; локальный автостенд (uvicorn + http.server) без nginx "
    "и docker — кейс невоспроизводим, прогон вручную/на стенде."
)
def test_tc_weather_019_weather_container_stop_fast_503():
    """TC-weather-019 (Scenario «Маршрутизация и деградация»): остановка
    контейнера weather → nginx отвечает на /api/weather* быстрым
    управляемым 503 (JSON + Retry-After), остальные разделы работают.
    Шаги (ручной прогон на стенде): GET /api/weather (200) → docker stop
    weather → GET /api/weather 5× с замером (< 1–2 с, 503) → доска,
    поиск, wiki, галерея, видео работают как прежде."""


@pytest.mark.e2e
@pytest.mark.web
def test_tc_weather_023_mockup_a_no_external_no_b_c(logged_in_page, web_base_url):
    """TC-weather-023 (Scenario «Дизайн по мокапу A и валидация после
    dev»): /weather во всех состояниях (данные, устаревшие, ошибка)
    соответствует мокапу A (карточка «сегодня» сверху, 7 дней 4-в-ряд,
    токены V3); ни одного внешнего сетевого запроса (CDN/шрифты/JS) —
    страница работает на локальных токенах; реализация вариантов B/C
    в кодовой базе отсутствует."""
    page = logged_in_page

    for state_body, status in (
        (payload(), 200),
        (payload(fetched_at="2026-10-19T11:00:00+03:00") | {"stale": True}, 200),
        ({"error": "weather_unavailable"}, 503),
    ):
        requests_seen: list[str] = []
        page.on("request", lambda req: requests_seen.append(req.url))
        _stub_route(page, state_body, status=status)
        page.goto(f"{web_base_url}/weather")
        page.wait_for_load_state()
        expect(page.locator(".weather-page")).to_be_visible()
        # Внешних запросов нет: только тестовый стенд (единый origin/статика).
        for url in requests_seen:
            parsed = urlparse(url)
            if parsed.scheme.startswith("http"):
                assert parsed.hostname in ("127.0.0.1", "localhost"), url
        page.unroute("**/api/weather")

    # Мокап A: сетка 4-в-ряд, «сегодня» — первая карточка с меткой
    # (проверка в состоянии «данные»).
    page.set_viewport_size({"width": 1440, "height": 900})
    _stub_route(page, payload())
    page.goto(f"{web_base_url}/weather")
    expect(page.locator("#weather-data")).to_be_visible()
    columns = page.evaluate(
        "getComputedStyle(document.querySelector('#weather-days'))"
        ".gridTemplateColumns.split(' ').length"
    )
    assert columns == 4
    expect(page.locator("#weather-days .day-card").first).to_have_class(
        "day-card w-card today-mark"
    )

    # Вариантов B/C в кодовой базе нет: ни файлов, ни следов в коде
    # фронтенда (мокапы design/p18-weather/variant-*.html — не реализация).
    assert (REPO_ROOT / "design" / "p18-weather" / "variant-a.html").exists()
    for tree in ("frontend", "backend"):
        base = REPO_ROOT / tree
        for path in base.rglob("*"):
            assert "variant-b" not in path.name and "variant-c" not in path.name
    for template in (REPO_ROOT / "frontend" / "templates").glob("*.html"):
        content = template.read_text(encoding="utf-8")
        assert not re.search(r"variant-[bc]", content), template.name


def test_tc_weather_025_responsiveness_on_provider_failure(
    wclient, wenv, monkeypatch, web_base_url, http
):
    """TC-weather-025 (Scenario «Замер отзывчивости при отказе
    провайдера»): пустой кэш + провайдер-«hang» (локальный сервер без
    ответа — реальное течение read-таймаутов) → /api/weather завершается
    управляемым 503 не дольше ~11 с (2 попытки × 5 с + пауза ~1 с);
    параллельные разделы (/board, /search, /gallery, /video) отвечают
    без деградации, пока запрос висит; при свежем кэше — мгновенный
    ответ без вызова провайдера."""
    hang = _LocalProvider(hang=True)
    try:
        monkeypatch.setattr(provider_mod, "PROVIDER_URL", hang.url())

        from app import routes

        result: dict = {}

        def run_get_weather():
            result["response"] = _run(routes.get_weather())

        # Пустой кэш: замер полного времени до управляемой ошибки.
        started = time.monotonic()
        thread = threading.Thread(target=run_get_weather, daemon=True)
        thread.start()
        # Дожидаемся окна зависшего запроса и в нем меряем разделы.
        _wakeup2 = threading.Event()
        while thread.is_alive() and time.monotonic() - started < 5.0:
            _wakeup2.wait(0.1)
        if thread.is_alive():
            # Параллельные разделы отвечают, пока /api/weather ждет таймауты.
            for section in ("/board", "/search", "/gallery", "/video"):
                section_started = time.monotonic()
                resp = http.get(f"{web_base_url}{section}")
                assert resp.status_code in (200, 301, 302)
                assert time.monotonic() - section_started < 3.0, section
        thread.join(timeout=30)
        assert not thread.is_alive()
        elapsed = time.monotonic() - started
        response = result["response"]
        assert elapsed <= 12.5, f"/api/weather занял {elapsed:.1f} с (норма ≤ ~11 с)"
        assert response.status_code == 503
        assert json.loads(response.body) == {"error": "weather_unavailable"}
        assert response.headers.get("Retry-After") == "60"
        # Провайдер вызван ровно 2 раза (попытка + один повтор), кэш
        # ошибкой не создан.
        assert len(hang.connections) == 2
        assert not wenv.exists()

        # Свежий кэш — мгновенный ответ без вызова провайдера.
        wcache.write(payload())
        calls_before = len(hang.connections)
        quick_started = time.monotonic()
        quick = wclient.get("/api/weather", cookies=_cookies())
        assert quick.status_code == 200
        assert quick.json()["stale"] is False
        assert time.monotonic() - quick_started < 2.0
        assert len(hang.connections) == calls_before  # провайдер не вызывался
    finally:
        hang.close()
