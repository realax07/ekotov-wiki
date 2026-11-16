"""Контрактный тест путей weather-сервиса (add-p20-contracts, волна 4, 4.3).

Замороженная спека contracts/openapi-weather.json = живому /openapi.json
сервиса под сессией, 1:1 (/api/weather + /api/health), плюс присутствие
схемы карточки («Сегодня» + ровно 7 дней, null-метрики) и Error/$ref
(ОВ-7; Open-Meteo в спеке нет — Д-17). Существующий TC-weather-003
401-паттерн (test_weather_service.py) не трогается.

Дрейф поверхности краснит тест еще до включения гейта IR-10 (волна 7).
Схемная валидация payloads — волна 5 (design §3).

Трассировка: TC-weather-042/043 (продолжение нумерации
services/weather/tests).
"""

import json
from pathlib import Path

import pytest

from app.main import app
from app.middleware import SESSION_COOKIE_NAME

# Замороженный контракт — из корня репозитория
# (services/weather/tests/x.py → parents[3] = корень).
CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "openapi-weather.json"

EXPECTED_PATHS = {"/api/weather", "/api/health"}


@pytest.fixture()
def client(db_path, cache_file):
    """TestClient с валидной сессией (фикстуры conftest: БД + кэш)."""
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        test_client.cookies.set(SESSION_COOKIE_NAME, "test-token-1")
        yield test_client


def test_contract_paths_match_live(client):
    """TC-weather-042: замороженная спека = живой /openapi.json, 1:1."""
    frozen = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    live = client.get("/openapi.json").json()
    assert set(frozen["paths"]) == set(live["paths"])
    assert set(frozen["paths"]) == EXPECTED_PATHS


def test_contract_card_and_error_schemas_present():
    """TC-weather-043: ОВ-7 + задача 4.2 — Error/$ref на 401/503, схема
    карточки (ровно 7 дней, null-метрики), Open-Meteo в спеке отсутствует."""
    frozen = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    schemas = frozen["components"]["schemas"]
    assert schemas["Error"]["required"] == ["error"]
    responses = frozen["paths"]["/api/weather"]["get"]["responses"]
    for status in ("401", "503"):
        assert responses[status]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/Error"
        }, status
    weather = schemas["WeatherResponse"]
    days = weather["properties"]["days"]
    assert days["minItems"] == days["maxItems"] == 7
    assert weather["properties"]["today"]["properties"]["temperature"] == {
        "type": ["number", "null"]
    }
    assert "open-meteo" not in json.dumps(frozen["paths"]).lower()
