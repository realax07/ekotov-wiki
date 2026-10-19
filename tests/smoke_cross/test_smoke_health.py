"""TC-smoke-001/002: health-матрица контура (эшелон 2, cross-domain smoke).

Домен-независимый эшелон смоука: каждый сервис контура отвечает {"status":"ok"}
и nginx маршрутизирует на app. Read-only, requests-based (xdist-безопасно).
"""

import os

import requests

# Канонические порты контура vh9 (tests/smoke_cross/conftest.py), env-оверрайд
# для нестандартного размещения.
SERVICES = {
    "app:8080": os.environ.get("SMOKE_APP_URL", "http://127.0.0.1:8080"),
    "search:8378": os.environ.get("SMOKE_SEARCH_URL", "http://127.0.0.1:8378"),
    "images:8379": os.environ.get("SMOKE_IMAGES_URL", "http://127.0.0.1:8379"),
    "video:8380": os.environ.get("SMOKE_VIDEO_URL", "http://127.0.0.1:8380"),
}


def test_health_all_services():
    """TC-smoke-001: /api/health каждого сервиса контура — 200 {"status":"ok"}."""
    for name, base in SERVICES.items():
        resp = requests.get(f"{base}/api/health", timeout=5)
        assert resp.status_code == 200, f"{name}: HTTP {resp.status_code}"
        assert resp.json() == {"status": "ok"}, f"{name}: {resp.text[:100]}"


def test_health_via_nginx(contour_url):
    """TC-smoke-002: вход контура (nginx) маршрутизирует /api/health на app."""
    resp = requests.get(f"{contour_url}/api/health", timeout=5)
    assert resp.status_code == 200, f"nginx→app: HTTP {resp.status_code}"
    assert resp.json() == {"status": "ok"}
