"""Контрактный гейт выделения search-сервиса (tasks 0.3/1.5, design §4).

Два инварианта перехода add-microservices-full:
1. Контракт поиска заморожен в contracts/openapi-search.json и содержит ровно
   маршруты, уходящие из монолита.
2. После выделения (задача 1.3) ядро (backend/app/main.py) не импортирует и не
   включает search/suggestions-роутеры. До выделения инвариант нарушен — тест
   strict-xfail с причиной; задача 1.5 снимает xfail и тест зеленеет.
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
    """«Экспорт = файл»: контракт существует, валиден, пути ровно ожидаемые."""
    assert CONTRACT_PATH.is_file(), f"нет замороженного контракта: {CONTRACT_PATH}"
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract.get("openapi", "").startswith("3.")
    paths = set(contract.get("paths", {}))
    assert paths == EXPECTED_PATHS, (
        f"контракт разошелся с ожидаемым: лишние {paths - EXPECTED_PATHS}, "
        f"недостающие {EXPECTED_PATHS - paths}"
    )


@pytest.mark.xfail(
    reason="Активируется задачей 1.3: выделение search-сервиса (ЭТАП B)",
    strict=True,
)
def test_core_has_no_search_routes():
    """«Ядро без маршрутов поиска»: main.py не тянет search/suggestions-роутеры."""
    main = (REPO_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert "search_router" not in main, "main.py импортирует/включает search_router"
    assert "suggestions_router" not in main, (
        "main.py импортирует/включает suggestions_router"
    )
