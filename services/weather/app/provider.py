"""Клиент Open-Meteo Forecast API (change weather-service, design §3).

Запрос ЗАФИКСИРОВАН (граница PLAN — один город, Москва): координаты/
поля — константы кода, параметризация через конфиг/API НЕ предусмотрена
(spec «Провайдер Open-Meteo — параметры запроса»). Особенности:

- wind_speed_unit=ms — ветер приходит УЖЕ в м/с (дефолт провайдера
  км/ч; конверсия в коде не нужна, ревью №1 F2);
- current.precipitation НЕ запрашивается (это мм осадков; осадки
  карточки — вероятность % из daily[0].precipitation_probability_max,
  ревью №1 F2);
- таймауты connect/read 5 с (httpx, единый таймаут); ровно ОДИН
  автоматический повтор с паузой 1 с; после второй неудачи —
  ProviderError (деградацию делает routes: stale-кэш / 503);
- User-Agent — из конфига сервиса (env EKOTOV_WEATHER_USER_AGENT),
  не дефолт httpx (требование вежливости публичного API);
- валидация схема-минимум: current — словарь, daily-массивы — длины 7
  и равные; невалидный/неполный JSON = ProviderError, кэш не затирается.

Тесты подменяют транспорт (аргумент transport — httpx.AsyncBaseTransport);
в сеть из тестов НЕ ходим.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

from app.wmo import describe, rumb

logger = logging.getLogger("weather.provider")

PROVIDER_URL = "https://api.open-meteo.com/v1/forecast"

# Зафиксированные параметры запроса (design §3; город один — Москва).
LATITUDE = 55.7539
LONGITUDE = 37.6208
TIMEZONE = "Europe/Moscow"
FORECAST_DAYS = 7
CURRENT_FIELDS = (
    "temperature_2m,apparent_temperature,weather_code,"
    "relative_humidity_2m,surface_pressure,wind_speed_10m,wind_direction_10m"
)
DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max,wind_speed_10m_max,"
    "wind_direction_10m_dominant"
)

# Таймауты и повтор (design §3: суммарный потолок ~11 с).
TIMEOUT_SECONDS = 5.0
ATTEMPTS = 2  # первичный запрос + ровно один автоматический повтор
RETRY_PAUSE_SECONDS = 1.0

# Давление: гПа → мм рт. ст. (1 гПа = 0.750062 мм рт. ст.).
HPA_TO_MMHG = 0.750062

# Дефолт User-Agent (env EKOTOV_WEATHER_USER_AGENT переопределяет).
DEFAULT_USER_AGENT = "ekotov-wiki-weather/1.0 (https://ekotov-wiki)"

# ЭСКАЛАЦИЯ E1 (dev-волна 3, live-проверка на стенде): design §3/спека
# фиксируют daily-поле «wind_direction_10m_max» — У реального Open-Meteo
# такого поля НЕТ (проверено живым запросом 2026-10-19: 400 «Cannot
# initialize ForecastVariableDaily from invalid String value
# wind_direction_10m_max»); направление максимального/дневного ветра
# провайдер отдает как wind_direction_10m_dominant. В запрос включено
# рабочее поле wind_direction_10m_dominant (семантика та же — румб
# дневного ветра); дельту design/spec на правку термина — ПМ/архитектору.

# Часовой пояс данных — Москва, фиксированный UTC+3 (без перехода на
# летнее время); zoneinfo не нужен — offset зашит (design §3).
MSK = timezone(timedelta(hours=3))


class ProviderError(Exception):
    """Провайдер недоступен/невалиден (сеть, таймаут, 5xx, битый JSON)."""


def user_agent() -> str:
    """User-Agent из конфига сервиса (env), не дефолт httpx."""
    return os.environ.get("EKOTOV_WEATHER_USER_AGENT") or DEFAULT_USER_AGENT


def build_params() -> dict:
    """Параметры запроса к Open-Meteo — зафиксированный набор (design §3)."""
    return {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "timezone": TIMEZONE,
        "forecast_days": FORECAST_DAYS,
        "wind_speed_unit": "ms",
        "current": CURRENT_FIELDS,
        "daily": DAILY_FIELDS,
    }


def _num(value) -> float | None:
    """Число или None (деградация: null → прочерк во фронтенде)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round1(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def validate(raw) -> dict:
    """Схема-минимум ответа провайдера (design §3).

    Обязательное: current — словарь; daily — словарь с массивами,
    все длины ≥ 7 и равные. Значения отдельных метрик могут быть
    null (деградация в прочерк — это НЕ невалидность ответа).
    """
    if not isinstance(raw, dict):
        raise ProviderError("provider response is not an object")
    current = raw.get("current")
    daily = raw.get("daily")
    if not isinstance(current, dict) or not isinstance(daily, dict):
        raise ProviderError("provider response misses current/daily")

    times = daily.get("time")
    if not isinstance(times, list) or len(times) < FORECAST_DAYS:
        raise ProviderError("provider daily.time is too short")

    for key, value in daily.items():
        if key == "time":
            continue
        if not isinstance(value, list) or len(value) != len(times):
            raise ProviderError(f"provider daily.{key} length mismatch")
    return raw


def normalize(raw: dict) -> dict:
    """Ответ провайдера → полезная нагрузка контракта (design §6):
    {fetched_at, today, days[7]} — без ключа stale (его ставит routes:
    он отражает СОСТОЯНИЕ кэша, а не данные провайдера)."""

    def day_fields(code, t_max, t_min, pop, ws_max, wd) -> dict:
        description, _ = describe(code)
        return {
            "code": None if code is None else int(code),
            "description": description,
            "temp_max": _round1(_num(t_max)),
            "temp_min": _round1(_num(t_min)),
            # Осадки — ВЕРОЯТНОСТЬ (%) из daily (ревью №1 F2).
            "precipitation": None if pop is None else _round1(_num(pop)),
            "wind": {"dir": rumb(wd), "speed": _round1(_num(ws_max))},
        }

    current = raw["current"]
    daily = raw["daily"]

    today = day_fields(
        current.get("weather_code"),
        daily["temperature_2m_max"][0],
        daily["temperature_2m_min"][0],
        daily["precipitation_probability_max"][0],
        daily["wind_speed_10m_max"][0],
        daily["wind_direction_10m_dominant"][0],  # E1: dominant, см. шапку
    )
    # Карточка «Сегодня» — текущая температура/ощущается/влажность/давление
    # из current; max/min и осадки — уже из daily[0] (согласованность с
    # прогнозом, design §3).
    today["temperature"] = _round1(_num(current.get("temperature_2m")))
    today["apparent"] = _round1(_num(current.get("apparent_temperature")))
    today["humidity"] = _round1(_num(current.get("relative_humidity_2m")))
    pressure = _num(current.get("surface_pressure"))
    today["pressure_mmhg"] = (
        None if pressure is None else round(pressure * HPA_TO_MMHG)
    )

    days = [
        day_fields(
            daily["weather_code"][i],
            daily["temperature_2m_max"][i],
            daily["temperature_2m_min"][i],
            daily["precipitation_probability_max"][i],
            daily["wind_speed_10m_max"][i],
            daily["wind_direction_10m_dominant"][i],  # E1: dominant
        )
        | {"date": daily["time"][i]}
        for i in range(len(daily["time"]))
    ]

    return {
        "fetched_at": datetime.now(MSK).isoformat(timespec="seconds"),
        "today": today,
        "days": days,
    }


async def fetch(user_agent_str: str | None = None, transport=None) -> dict:
    """Запрос к провайдеру: таймаут 5 с, ровно один повтор → normalize.

    transport — точка подмены для тестов (httpx.MockTransport); в сеть
    из тестов не ходим. После ATTEMPTS неудач — ProviderError.
    """
    headers = {"User-Agent": user_agent_str or user_agent()}
    timeout = httpx.Timeout(
        TIMEOUT_SECONDS,
        connect=TIMEOUT_SECONDS,
        read=TIMEOUT_SECONDS,
        write=TIMEOUT_SECONDS,
        pool=TIMEOUT_SECONDS,
    )
    last_error: Exception | None = None
    for attempt in range(ATTEMPTS):
        if attempt:
            await asyncio.sleep(RETRY_PAUSE_SECONDS)
        try:
            async with httpx.AsyncClient(
                timeout=timeout, headers=headers, transport=transport
            ) as client:
                response = await client.get(PROVIDER_URL, params=build_params())
                if response.status_code != 200:
                    raise ProviderError(f"provider status {response.status_code}")
                return normalize(validate(response.json()))
        except (httpx.HTTPError, ValueError, ProviderError) as exc:  # noqa: PERF203
            last_error = exc
            logger.warning("weather provider attempt %d failed: %s", attempt + 1, exc)
    raise ProviderError(f"provider failed after {ATTEMPTS} attempts: {last_error}")
