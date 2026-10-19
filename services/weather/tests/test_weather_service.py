"""Тесты weather-сервиса (волна 3, задачи 3.1–3.2, 3.4; change
weather-service).

По конвенции services/video/tests: TestClient над app.main; провайдер
мокается (СТАБЫ, сеть не трогаем); env — фикстуры conftest (временная
sqlite users/sessions, временный кэш-файл).

Трассировка: сценарии дельты specs/weather-service — Requirement/Scenario
указаны в docstring каждого теста; нумерация TC-weather-NNN:

TC-weather-001…004 — auth (401 аноним без обращений к провайдеру/кэшу,
health exempt, openapi закрыт, доступ по сессии);
TC-weather-010…014 — контракт ответа (схема §6, 7 дней, today ↔ days[0],
конверсии давление/румб/WMO, деградация null-метрики);
TC-weather-020…024 — параметры запроса к провайдеру (координаты, tz,
forecast_days, wind_speed_unit=ms, набор полей БЕЗ current.precipitation,
User-Agent из конфига);
TC-weather-030…036 — кэш TTL и деградация (свежий кэш без вызова
провайдера, истечение TTL → обновление, отказ провайдера → stale,
битый JSON не затирает кэш, пустой кэш + отказ → 503 weather_unavailable,
ровно один повтор, сбой записи кэша не меняет ответ);
TC-weather-040…041 — конкурентное обновление под asyncio.Lock (одно
обновление), битый кэш-файл = «кэша нет».

Запуск (из services/weather/): python -m pytest tests/ -v
Без сети и внешних сервисов.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app import cache
from app.middleware import SESSION_COOKIE_NAME
from app.provider import ProviderError, build_params, fetch, normalize

# Пакетный импорт хелперов (НЕ голый conftest — урок BUG-video-001).
from tests.helpers import SESSION_TOKEN, cached_payload, provider_raw

AUTH = {"error": "unauthorized"}


def _stub_fetch(calls, *, result=None, fail_times=0, error=None):
    """Async-стаб app.provider.fetch: считает вызовы, первые fail_times
    попыток кидает ProviderError, дальше возвращает result (или свежий
    cached_payload())."""

    async def _fetch(user_agent_str=None, transport=None):
        calls.append(user_agent_str)
        if len(calls) <= fail_times:
            raise error or ProviderError("provider down (stub)")
        return result if result is not None else cached_payload()

    return _fetch


# ---------------------------------------------------------------- auth

def test_anonymous_gets_401_without_provider_or_cache(client, monkeypatch):
    """TC-weather-001 (Scenario «Негативный: /api/weather без сессии»):
    без валидной сессии — 401 {"error": "unauthorized"}; обращений к
    провайдеру и к кэшу нет."""
    calls = []
    monkeypatch.setattr("app.provider.fetch", _stub_fetch(calls))
    response = client.get("/api/weather")
    assert response.status_code == 401
    assert response.json() == AUTH
    assert calls == []  # провайдер не вызывался
    assert not cache.read()  # кэш-файл не создан


def test_health_is_exempt_and_stateless(client):
    """TC-weather-002 (Requirement «Отдельный контейнерный сервис…»,
    design §6): /api/health — 200 без сессии (healthcheck контейнера)."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_requires_session(client):
    """TC-weather-003 (NFR-7-паттерн, паритет video): /openapi.json —
    401 анониму; по сессии — 200."""
    assert client.get("/openapi.json").status_code == 401
    ok = client.get("/openapi.json", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN})
    assert ok.status_code == 200


def test_authorized_request_returns_payload(client, monkeypatch):
    """TC-weather-004 (Requirement «API погоды — только по сессии»):
    с валидной сессией — 200 и полезная нагрузка (схема §6)."""
    calls = []
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch(calls, result=cached_payload())
    )
    response = client.get("/api/weather", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"fetched_at", "stale", "today", "days"}
    assert body["stale"] is False
    assert len(calls) == 1


# ------------------------------------------------------------- контракт

def test_contract_shape_today_and_seven_days(client, monkeypatch):
    """TC-weather-010 (Scenario «Полная карточка по мокапу A» +
    «Семь карточек с полным набором полей»): today — 8 метрик,
    days — ровно 7, упорядочены по дате, days[0] ↔ today (максимум/
    минимум того же дня)."""
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch([], result=cached_payload())
    )
    body = client.get(
        "/api/weather", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN}
    ).json()
    today = body["today"]
    assert set(today) == {
        "temperature", "description", "code", "apparent", "temp_max",
        "temp_min", "precipitation", "wind", "humidity", "pressure_mmhg",
    }
    assert set(today["wind"]) == {"dir", "speed"}
    days = body["days"]
    assert len(days) == 7
    dates = [d["date"] for d in days]
    assert dates == sorted(dates)
    for day in days:
        assert set(day) == {
            "date", "code", "description", "temp_max", "temp_min",
            "precipitation", "wind",
        }
    # days[0] ↔ today: экстремумы и осадки того же дня.
    assert days[0]["temp_max"] == today["temp_max"]
    assert days[0]["temp_min"] == today["temp_min"]
    assert days[0]["precipitation"] == today["precipitation"]


def test_conversions_pressure_rumb_wmo(client, monkeypatch):
    """TC-weather-011 (Scenario «Полная карточка по мокапу A»): давление
    гПа → мм рт. ст. (984 → 738), румб 225° → «ЮЗ», м/с без конверсии
    (wind_speed_unit=ms), WMO 63 → «Дождь» на русском."""
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch([], result=cached_payload())
    )
    today = client.get(
        "/api/weather", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN}
    ).json()["today"]
    assert today["pressure_mmhg"] == 738  # 984 * 0.750062 = 738.06 → 738
    assert today["wind"] == {"dir": "ЮЗ", "speed": 5.0}
    assert today["description"] == "Дождь"
    assert today["code"] == 63


def test_missing_metric_degrades_to_null(client, monkeypatch):
    """TC-weather-012 (Scenario «Деградация при отсутствии метрики»):
    давление null в ответе провайдера → null в API (прочерк «—» во
    фронтенде), остальные 7 метрик не сломаны."""
    raw = provider_raw()
    raw["current"]["surface_pressure"] = None
    raw["current"]["relative_humidity_2m"] = None
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch([], result=normalize(raw))
    )
    today = client.get(
        "/api/weather", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN}
    ).json()["today"]
    assert today["pressure_mmhg"] is None
    assert today["humidity"] is None
    assert today["temperature"] is not None
    assert today["wind"]["dir"] == "ЮЗ"
    assert today["precipitation"] == 80


def test_today_precipitation_is_probability_from_daily(client, monkeypatch):
    """TC-weather-013 (ревью №1 F2, design §6): today.precipitation —
    ВЕРОЯТНОСТЬ (%) из daily[0].precipitation_probability_max."""
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch([], result=cached_payload())
    )
    body = client.get(
        "/api/weather", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN}
    ).json()
    assert body["today"]["precipitation"] == 80
    assert body["days"][0]["precipitation"] == 80


def test_moscow_dates_in_payload(client, monkeypatch):
    """TC-weather-014 (Scenario «Локальное время Москвы в данных»):
    fetched_at — с offset +03:00; даты дней — как вернул провайдер
    (timezone=Europe/Moscow), без пересчета."""
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch([], result=cached_payload())
    )
    body = client.get(
        "/api/weather", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN}
    ).json()
    assert body["fetched_at"].endswith("+03:00")
    assert body["days"][0]["date"] == "2026-10-19"


# ------------------------------------------------- параметры провайдера

def _capturing_transport(captured: list[httpx.Request], response: httpx.Response):
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return response

    return httpx.MockTransport(handler)


def test_provider_request_fixed_params(monkeypatch):
    """TC-weather-020 (Scenario «Запрос к провайдеру с зафиксированными
    параметрами»): URL содержит latitude/longitude/timezone/forecast_days/
    wind_speed_unit=ms и полный набор current/daily-полей; поле
    current.precipitation ОТСУТСТВУЕТ (ревью №1 F2); других вызовов нет."""
    captured: list[httpx.Request] = []
    response = httpx.Response(200, json=provider_raw())
    monkeypatch.setenv("EKOTOV_WEATHER_USER_AGENT", "ekotov-wiki-tests-UA/1.0")

    asyncio.run(fetch(transport=_capturing_transport(captured, response)))

    assert len(captured) == 1  # никаких других внешних вызовов
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
    assert request.headers["User-Agent"] == "ekotov-wiki-tests-UA/1.0"


def test_build_params_has_no_current_precipitation():
    """TC-weather-021 (ревью №1 F2): зафиксированные параметры (юнит) —
    wind_speed_unit=ms и отсутствие current.precipitation в наборе."""
    params = build_params()
    assert params["wind_speed_unit"] == "ms"
    assert "precipitation" not in params["current"]
    assert params["latitude"] == 55.7539 and params["longitude"] == 37.6208
    assert params["timezone"] == "Europe/Moscow"
    assert params["forecast_days"] == 7


def test_provider_user_agent_from_config(monkeypatch):
    """TC-weather-022 (Requirement «Таймауты провайдера и повтор…»):
    User-Agent берется из конфига сервиса (env), не дефолт httpx."""
    captured: list[httpx.Request] = []
    monkeypatch.setenv("EKOTOV_WEATHER_USER_AGENT", "wiki-weather-prod/2.0")
    asyncio.run(
        fetch(
            transport=_capturing_transport(
                captured, httpx.Response(200, json=provider_raw())
            )
        )
    )
    assert captured[0].headers["User-Agent"] == "wiki-weather-prod/2.0"


# --------------------------------------------------- кэш TTL, деградация

def test_fresh_cache_served_without_provider(client, monkeypatch):
    """TC-weather-030 (Scenario «Повторные запросы в течение часа идут
    из кэша»): свежий кэш — ответ из кэша, провайдер НЕ вызывается,
    fetched_at одинаков в повторных ответах (кэш общий)."""
    fetched = datetime.now(timezone.utc) - timedelta(minutes=5)
    cache.write(cached_payload(payload_id=7, fetched_at=fetched))
    calls = []
    monkeypatch.setattr("app.provider.fetch", _stub_fetch(calls))
    cookies = {SESSION_COOKIE_NAME: SESSION_TOKEN}
    first = client.get("/api/weather", cookies=cookies).json()
    second = client.get("/api/weather", cookies=cookies).json()
    assert calls == []  # обращений к Open-Meteo нет
    assert first["fetched_at"] == second["fetched_at"]
    assert first["stale"] is False


def test_expired_ttl_refreshes_from_provider(client, monkeypatch):
    """TC-weather-031 (Scenario «Истечение TTL — обновление с
    провайдера»): кэш старше 60 минут → запрос провайдеру, новый
    fetched_at, stale: false, кэш-файл перезаписан."""
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=61)
    cache.write(cached_payload(payload_id=1, fetched_at=stale_time))
    calls = []
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch(calls, result=cached_payload(payload_id=2))
    )
    body = client.get(
        "/api/weather", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN}
    ).json()
    assert len(calls) == 1
    assert body["stale"] is False
    assert body["fetched_at"] != stale_time.isoformat(timespec="seconds")
    refreshed = cache.read()
    assert refreshed is not None and refreshed["fetched_at"] == body["fetched_at"]


def test_provider_down_serves_stale_cache(client, monkeypatch):
    """TC-weather-032 (Scenario «Отдача устаревшего кэша при отказе
    провайдера»): TTL истек, провайдер недоступен → 200 из кэша со
    stale: true и прежним fetched_at; кэш-файл не изменен."""
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=61)
    cache.write(cached_payload(payload_id=3, fetched_at=stale_time))
    before = cache.read()
    calls = []
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch(calls, fail_times=99)
    )
    body = client.get(
        "/api/weather", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN}
    ).json()
    assert body["stale"] is True
    assert body["fetched_at"] == before["fetched_at"]
    assert cache.read() == before  # кэш-файл сохранен байт-в-байт


def test_invalid_provider_json_keeps_cache(client, monkeypatch):
    """TC-weather-033 (Scenario «Битый ответ провайдера не затирает
    кэш»): провайдер ответил 200 с невалидным JSON → невалидный ответ
    отброшен, кэш сохранен, пользователь получает устаревшие данные со
    stale: true (паритет отказу провайдера)."""
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=61)
    cache.write(cached_payload(payload_id=4, fetched_at=stale_time))
    before = cache.read()

    async def broken_fetch(user_agent_str=None, transport=None):
        raise ProviderError("invalid json (stub)")

    monkeypatch.setattr("app.provider.fetch", broken_fetch)
    body = client.get(
        "/api/weather", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN}
    ).json()
    assert body["stale"] is True
    assert cache.read() == before  # битый ответ кэш НЕ затер


def test_no_cache_and_provider_down_is_503(client, monkeypatch):
    """TC-weather-034 (Scenario «Честное сообщение вместо данных»):
    том пуст И провайдер недоступен → 503 {"error":
    "weather_unavailable"}; кэш-файл при этом НЕ создается."""
    calls = []
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch(calls, fail_times=99)
    )
    response = client.get(
        "/api/weather", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN}
    )
    assert response.status_code == 503
    assert response.json() == {"error": "weather_unavailable"}
    assert not cache.read()  # кэш-файл не создан


def test_exactly_one_retry(monkeypatch):
    """TC-weather-035 (Scenario «Ровно один автоматический повтор»):
    первая попытка не удалась → ровно один повтор; успех повтора —
    данные без stale-ветки; две неудачи → ровно 2 попытки и ProviderError."""

    async def scenario():
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            if len(attempts) == 1:
                raise httpx.ConnectError("boom", request=request)
            return httpx.Response(200, json=provider_raw())

        data = await fetch(transport=httpx.MockTransport(handler))
        assert len(attempts) == 2  # первичный + ровно один повтор
        assert data["today"]["description"] == "Дождь"

        failed: list[int] = []

        def failing_handler(request: httpx.Request) -> httpx.Response:
            failed.append(1)
            raise httpx.ConnectError("down", request=request)

        with pytest.raises(ProviderError):
            await fetch(transport=httpx.MockTransport(failing_handler))
        assert len(failed) == 2  # не больше одного повтора

    asyncio.run(scenario())


def test_cache_write_failure_does_not_change_response(client, monkeypatch):
    """TC-weather-036 (ревью №1 O2): невозможность ЗАПИСАТЬ кэш ответ
    не меняет — пользователю отдается полученное от провайдера как при
    успехе; прежний кэш не затерт."""
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=61)
    cache.write(cached_payload(payload_id=5, fetched_at=stale_time))
    before = cache.read()

    def broken_write(payload):
        raise OSError("volume is read-only (stub)")

    monkeypatch.setattr(cache, "write", broken_write)
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch([], result=cached_payload(payload_id=6))
    )
    body = client.get(
        "/api/weather", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN}
    ).json()
    assert body["stale"] is False
    assert body["fetched_at"] != before["fetched_at"]
    assert cache.read() == before  # прежний кэш-файл остался


# -------------------------------------------- конкурентность и целостность

def test_concurrent_refresh_single_provider_call(monkeypatch, cache_file):
    """TC-weather-040 (design §4, ревью №1 O1): два одновременных
    запроса при истекшем кэше инициируют ОДНО обновление — второй
    дожидается и получает свежий результат (asyncio.Lock в routes)."""

    async def scenario():
        from app import routes

        stale_time = datetime.now(timezone.utc) - timedelta(minutes=61)
        cache.write(cached_payload(payload_id=1, fetched_at=stale_time))

        calls = []

        async def slow_fetch(user_agent_str=None, transport=None):
            calls.append(1)
            await asyncio.sleep(0.05)  # имитация latency провайдера
            return cached_payload(payload_id=9)

        monkeypatch.setattr("app.provider.fetch", slow_fetch)

        results = await asyncio.gather(
            routes.get_weather(), routes.get_weather()
        )
        assert len(calls) == 1  # двойных вызовов провайдера нет
        fetched_at = {r["fetched_at"] for r in results}
        assert len(fetched_at) == 1  # оба ответа — один и тот же свежий

    asyncio.run(scenario())


def test_broken_cache_file_counts_as_missing(client, cache_file, monkeypatch):
    """TC-weather-041 (design §4): битый кэш-файл = «кэша нет» — сервис
    не падает, идет к провайдеру, файл перезаписывается валидным."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(
        "app.provider.fetch", _stub_fetch([], result=cached_payload(payload_id=8))
    )
    body = client.get(
        "/api/weather", cookies={SESSION_COOKIE_NAME: SESSION_TOKEN}
    ).json()
    assert body["stale"] is False
    # Кэш-файл перезаписан валидной полезной нагрузкой.
    assert json.loads(cache_file.read_text(encoding="utf-8"))["today"]["code"] == 63
