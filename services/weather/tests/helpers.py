"""Общие хелперы сервисных тестов weather (волна 3).

ОТДЕЛЬНЫЙ модуль (не conftest) — урок BUG-video-001/свертки J52: тестовые
модули импортируют хелперы как пакет (`from tests.helpers import …`),
а НЕ голым `from conftest import …` — при смешанных прогонах голый
conftest-импорт дает collection errors (tests/api/conftest.py, шапка).
"""

from datetime import datetime, timedelta, timezone

# Валидная сессия тестов (фикстура conftest сеет тот же токен).
SESSION_TOKEN = "test-token-1"


def payload_extra(payload_id: int) -> dict:
    """Маркер в generationtime_ms — различать ответы в тестах TTL."""
    return {"generationtime_ms": float(payload_id)}


def provider_raw(payload_id: int = 1) -> dict:
    """Валидный ответ провайдера Open-Meteo (схема design §3) — 7 дней.

    Значения подобраны под конверсионные ассерты тестов (давление
    984 гПа → 738 мм рт. ст.; ветер 225° → ЮЗ; код 63 → «Дождь»).
    """
    return {
        "latitude": 55.7539,
        "longitude": 37.6208,
        "timezone": "Europe/Moscow",
        "generationtime_ms": float(payload_id),
        "current": {
            "time": "2026-10-19T12:00",
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
            "time": [f"2026-10-{19 + i:02d}" for i in range(7)],
            "weather_code": [63, 3, 2, 61, 3, 2, 71],
            "temperature_2m_max": [5.0, 5.1, 7.0, 6.0, 4.0, 2.0, 1.0],
            "temperature_2m_min": [1.0, 2.0, 3.0, 2.0, 0.0, -1.0, -2.0],
            "precipitation_probability_max": [80, 30, 15, 55, 40, 20, 65],
            "wind_speed_10m_max": [5.0, 4.0, 3.0, 6.0, 5.0, 3.0, 4.0],
            "wind_direction_10m_dominant": [225, 270, 225, 180, 315, 0, 45],
        },
    }


def cached_payload(payload_id: int = 1, fetched_at: datetime | None = None) -> dict:
    """Полезная нагрузка кэша/ответа (design §6 БЕЗ stale) — через
    provider.normalize, чтобы тесты кэша не дублировали контракт."""

    from app.provider import normalize

    data = normalize(provider_raw(payload_id))
    if fetched_at is not None:
        data["fetched_at"] = fetched_at.isoformat(timespec="seconds")
    return data
