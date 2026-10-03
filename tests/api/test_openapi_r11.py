"""Машинная схема OpenAPI — FR-68 (change add-containerization, tasks 0.2/0.3).

TC-ID: TC-openapi-101, TC-openapi-102 (test-model/regression/api/).

Контракт behavior (design §4):
  - openapi_url включен в main.py (единственная правка кода продукта пакета);
  - middleware НЕ менялся, exempt-список не расширялся: без сессии
    /openapi.json не публикуется — фактически 302 → /login (ветка страниц
    middleware); 401 — допустимый вариант спеки, но без правки middleware
    недостижим (зафиксирован фактический статус);
  - под сессией схема отдается 200 и это ровно то, что экспортирует
    scripts/export_openapi.py в contracts/openapi.json;
  - /docs и /redoc остаются выключенными (404).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"

pytestmark = pytest.mark.api


def test_openapi_without_session_not_public(base_url, http):
    """FR-68: без сессии схема не раскрывается публично — 302 → /login
    (фактическое поведение middleware; 401 допустим спекой, не фиксируется)."""
    resp = requests.get(f"{base_url}/openapi.json", allow_redirects=False)
    assert resp.status_code in (302, 307, 401), (
        f"/openapi.json без сессии = {resp.status_code}, ожидался 302/401"
    )
    if resp.status_code in (302, 307):
        location = resp.headers.get("location", "")
        assert location.endswith("/login"), (
            f"redirect {resp.status_code} на {location!r}, ожидался /login"
        )


@pytest.mark.parametrize("path", ["/docs", "/redoc"])
def test_docs_redoc_disabled(base_url, owner_session, path):
    """/docs и /redoc остаются выключенными (design §4: openapi_url —
    единственное включение; документация-UI не открывается даже под сессией)."""
    resp = owner_session.get(f"{base_url}{path}", allow_redirects=False)
    assert resp.status_code == 404, f"{path} = {resp.status_code}, ожидался 404"


def test_openapi_with_session_200_and_matches_contract(base_url, owner_session):
    """Под сессией схема 200 и соответствует зафиксированному контракту
    (tasks 0.3 «экспорт = зафиксированный файл»: пути не расходятся)."""
    resp = owner_session.get(f"{base_url}/openapi.json")
    assert resp.status_code == 200
    live = resp.json()

    assert CONTRACT_PATH.exists(), (
        "contracts/openapi.json отсутствует — запусти scripts/export_openapi.py"
    )
    fixed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert set(live["paths"]) == set(fixed["paths"]), (
        "живые пути /openapi.json разошлись с contracts/openapi.json — "
        "перегенерируй экспорт (python scripts/export_openapi.py)"
    )
