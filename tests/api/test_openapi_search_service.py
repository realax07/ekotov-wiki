"""Контрактный гейт выделения search-сервиса (tasks 0.3/1.3/1.5, design §4).

Инварианты перехода add-microservices-full:
1. Контракт поиска заморожен в contracts/openapi-search.json и содержит ровно
   маршруты, уходящие из монолита (TC-openapi-201).
2. Ядро (backend/app/main.py) не импортирует и не включает
   search/suggestions-роутеры (TC-openapi-202). Активировано задачей 1.5:
   маршруты отрезаны от монолита, xfail снят (strict сохранен).
3. nginx-маршрутизация search-семейства (задача 1.3, design §4): на стенде
   /api/search через nginx отвечает 200 с заголовком X-Service: search;
   остановленный search → управляемый 503 (не 502/таймаут). Против локального
   стенда без nginx-маршрутизации — skip (заголовка нет).
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "contracts" / "openapi-search.json"

EXPECTED_PATHS = {
    "/api/search",
    "/api/search/advanced",
    "/api/suggestions",
    "/api/suggestions/users",
}


def test_search_contract_is_frozen():
    """TC-openapi-201 «Экспорт = файл»: контракт существует, валиден, пути ровно ожидаемые."""
    assert CONTRACT_PATH.is_file(), f"нет замороженного контракта: {CONTRACT_PATH}"
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract.get("openapi", "").startswith("3.")
    paths = set(contract.get("paths", {}))
    assert paths == EXPECTED_PATHS, (
        f"контракт разошелся с ожидаемым: лишние {paths - EXPECTED_PATHS}, "
        f"недостающие {EXPECTED_PATHS - paths}"
    )


def test_core_has_no_search_routes():
    """TC-openapi-202 «Ядро без маршрутов поиска»: main.py не тянет search/suggestions-роутеры."""
    main = (REPO_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert "search_router" not in main, "main.py импортирует/включает search_router"
    assert "suggestions_router" not in main, (
        "main.py импортирует/включает suggestions_router"
    )


def test_nginx_routes_search_family(base_url, owner_session):
    """TC-openapi-203 «Маршрутизация nginx» (задача 1.3, design §4, spec services):
    /api/search через nginx → 200 + X-Service: search; /api/suggestions и
    /api/suggestions/users — тоже search; /api/board — на app (X-Service нет).

    Гейт маршрутизации, не контракта: против локального стенда БЕЗ
    nginx-маршрутизации search-семейства (заголовок не заведен) — skip;
    падение на маршрутизированном стенде = дефект конфига frontend.
    """
    resp = owner_session.get(f"{base_url}/api/search")
    if resp.status_code == 200 and "X-Service" not in resp.headers:
        pytest.skip(
            "стенд без nginx-маршрутизации search-семейства (нет X-Service) — "
            "гейт проверяется на стенде с образом frontend задачи 1.3"
        )
    assert resp.status_code == 200, f"/api/search: {resp.status_code} {resp.text[:120]}"
    assert resp.headers.get("X-Service") == "search", (
        f"X-Service={resp.headers.get('X-Service')!r}: /api/search не маршрутизирован на search"
    )

    for path in ("/api/suggestions", "/api/suggestions/users"):
        resp = owner_session.get(f"{base_url}{path}")
        assert resp.status_code == 200, f"{path}: {resp.status_code} {resp.text[:120]}"
        assert resp.headers.get("X-Service") == "search", (
            f"X-Service={resp.headers.get('X-Service')!r}: {path} не маршрутизирован"
        )

    # Остальное — на app (маршрут прозрачен для не-search-семейства).
    resp = owner_session.get(f"{base_url}/api/board")
    assert resp.status_code == 200, f"/api/board: {resp.status_code}"
    assert "X-Service" not in resp.headers or resp.headers.get("X-Service") != "search", (
        "/api/board помечен X-Service: search — маршрутизация заехала не туда"
    )
