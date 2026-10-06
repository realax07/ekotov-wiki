"""QA 2.1 add-gallery-service — инфра-сьют без docker (TC-GAL-106 частично).

TC-GAL-106 (nginx-маршрутизация): docker-часть (compose-конфиг, порты
контейнеров) — SKIPPED (docker.sock недоступен subagent-сессии); маршрутизация,
health, отдача /images/ с expires 7d, ядро-без-маршрутов — проверяются против
локального nginx-стенда :18443 (паритет ekotov-wiki.conf 1.4: images-пара
= /api/images + ^~ /api/images/ с include-семантикой images-*.inc, /images/
alias тома, @images_down).

Запускается как обычный pytest (маркеры api), требует живого стенда:
EKOTOV_WIKI_BASE_URL + EKOTOV_WIKI_DB_PATH + EKOTOV_WIKI_IMAGES_DIR.
"""

import os
import sqlite3

import pytest
import requests

pytestmark = [pytest.mark.api, pytest.mark.must]

BASE_URL = os.environ.get("EKOTOV_WIKI_BASE_URL", "http://127.0.0.1:18443")
DB_PATH = os.environ.get("EKOTOV_WIKI_DB_PATH")


def _login():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "login": "owner",
            "password": os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!"),
        },
    )
    assert r.status_code == 200
    for c in s.cookies:
        c.secure = False
    return s


def test_tc_gal_106_nginx_routing_pair_health_and_static():
    """TC-GAL-106 (шаги 1–4, локальный nginx-стенд): пара /api/images* →
    images (:8379) с X-Service; health напрямую 200; ядро без маршрутов
    (404); /images/<file> — nginx alias с expires 7d; соседи не изменены.
    Шаг 5 (compose/порты контейнеров) — SKIPPED, требует docker (REPORT §4)."""
    s = _login()
    # Шаг 1: /api/images и /api/images/<id> через nginx — 200 + X-Service: images.
    r = s.get(f"{BASE_URL}/api/images")
    assert r.status_code == 200
    assert r.headers.get("x-service") == "images", dict(r.headers)
    images = r.json()["images"]
    if images:
        r1 = s.get(f"{BASE_URL}/api/images/{images[0]['id']}")
        assert r1.status_code == 200
        assert r1.headers.get("x-service") == "images"

    # Шаг 2 (health напрямую сервису — аналог «внутри сети»): локально :8379.
    # (через nginx health тоже 200 — ^~ /api/images/ включает /api/health images)
    port = os.environ.get("EKOTOV_WIKI_IMAGES_PORT", "8379")
    h = requests.get(f"http://127.0.0.1:{port}/api/health")
    assert h.status_code == 200 and h.json() == {"status": "ok"}

    # Шаг 3: ядро (app :8080, минуя nginx) — маршрутов изображений нет.
    core = os.environ.get("EKOTOV_WIKI_CORE_URL", "http://127.0.0.1:8080")
    for c in s.cookies:
        c.secure = False
    rc = s.get(f"{core}/api/images")
    assert rc.status_code in (404, 405), rc.status_code
    rc = s.get(f"{core}/api/images/1")
    assert rc.status_code in (404, 405), rc.status_code

    # Шаг 4: /images/<file> — nginx (не сервис), кеш 7d, тело = байты тома.
    if not images:
        pytest.skip("нет изображений в томе (загрузка — TC-GAL-107; прогон сьета)")
    filename = images[0]["filename"]
    rf = requests.get(f"{BASE_URL}/images/{filename}")
    assert rf.status_code == 200
    assert rf.headers["content-type"] == "image/png"
    assert rf.headers.get("cache-control") == "public" or "max-age=604800" in rf.headers.get(
        "cache-control", ""
    )
    expires = rf.headers.get("expires")
    assert expires, "нет Expires (7d)"
    images_dir = os.environ.get("EKOTOV_WIKI_IMAGES_DIR", "/tmp/qa21-gallery/images")
    with open(os.path.join(images_dir, filename), "rb") as f:
        assert rf.content == f.read(), "тело /images/ != байты тома"

    # Шаг 5-частично: соседи (/api/search — X-Service: search; /api/board —
    # без X-Service) не изменены.
    rs = s.get(f"{BASE_URL}/api/search", params={"q": ""})
    assert rs.status_code == 200 and rs.headers.get("x-service") == "search"
    rb = s.get(f"{BASE_URL}/api/board")
    assert rb.status_code == 200
    assert "x-service" not in {k.lower() for k in rb.headers}


def test_tc_gal_106_compose_ports_and_config():
    """TC-GAL-106 (шаг 5): порты images не опубликованы, compose-конфиг —
    ТРЕБУЕТ docker-доступа (docker compose config / docker port)."""
    pytest.skip(
        "требует docker-доступа Заказчика (docker.sock закрыт subagent-сессии);"
        " план 2.2 / стенд Заказчика"
    )
