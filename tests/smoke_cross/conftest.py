"""Фикстуры cross-domain smoke (эшелон 2, J54) — канонический контур vh9.

Контур: nginx:18443 → app:8080 + search:8378 + images:8379 + video:8380
(/tmp/vh9-stand: reset.sh — чистая БД+seed, launch.sh — старт). Базовый URL —
env ``EKOTOV_WIKI_BASE_URL`` (дефолт http://127.0.0.1:18443 — вход через
nginx: smoke проверяет ПОЛНЫЙ контур, а не отдельный app).

Помощники НЕ дублируются: ``login_session`` / ``LocalhostSession`` / seed-креды
переиспользуются из tests/api/conftest.py загрузкой модуля по пути (importlib).
Конфтесты tests/api и tests/web не видны каталогу tests/smoke_cross (pytest
резолвит conftest по иерархии каталогов), а голый ``import conftest``
недетерминирован (sys.modules['conftest'] затирается последним загруженным
конфтестом — см. docstring db_hooks в tests/api/conftest.py); загрузка по пути
дает стабильную ссылку на нужный модуль при любом порядке сбора.

Тесты смоука — read-only (логин создает только сессию), requests-based
(без playwright) — детерминированы при xdist (-n 4).
"""

import importlib.util
import os
import time
from pathlib import Path

import pytest

# --- переиспользование помощников tests/api/conftest.py (без дублей) -------
_API_CONF_PATH = (
    Path(__file__).resolve().parents[1] / "api" / "conftest.py"
)
_spec = importlib.util.spec_from_file_location(
    "_ekotov_api_conftest_smoke", _API_CONF_PATH
)
assert _spec is not None and _spec.loader is not None, (
    f"не удалось загрузить {_API_CONF_PATH}"
)
api_conf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api_conf)

OWNER_LOGIN = api_conf.OWNER_LOGIN
OWNER_PASSWORD = api_conf.OWNER_PASSWORD
login_session = api_conf.login_session
LocalhostSession = api_conf.LocalhostSession

BASE_URL_ENV = "EKOTOV_WIKI_BASE_URL"
DEFAULT_CONTOUR_URL = "http://127.0.0.1:18443"

# Прямые адреса сервисов контура (health-матрица); канонические порты vh9,
# переопределяются env для нестандартного размещения контура.
SMOKE_SERVICES = {
    "app:8080": os.environ.get("SMOKE_APP_URL", "http://127.0.0.1:8080"),
    "search:8378": os.environ.get("SMOKE_SEARCH_URL", "http://127.0.0.1:8378"),
    "images:8379": os.environ.get("SMOKE_IMAGES_URL", "http://127.0.0.1:8379"),
    "video:8380": os.environ.get("SMOKE_VIDEO_URL", "http://127.0.0.1:8380"),
}


def _resolve_contour_url() -> str:
    return (
        os.environ.get(BASE_URL_ENV) or DEFAULT_CONTOUR_URL
    ).rstrip("/")


@pytest.fixture(scope="session")
def contour_url() -> str:
    """Вход канонического контура (nginx). Готовность — poll /api/health
    с коротким таймаутом: смоук не должен висеть на мертвом стенде."""
    import requests

    url = _resolve_contour_url()
    deadline = 20.0
    started = time.monotonic()
    last_error = None
    while time.monotonic() - started < deadline:
        try:
            resp = requests.get(f"{url}/api/health", timeout=2)
            if resp.status_code == 200 and resp.json() == {"status": "ok"}:
                return url
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(
        f"Контур {url} не готов за {deadline}s (health через nginx): "
        f"{last_error}. Подними стенд: bash /tmp/vh9-stand/reset.sh "
        f"(или tests/smoke_cross/README.md)."
    )


@pytest.fixture
def anon_http(contour_url):
    """Анонимная HTTP-сессия (браузерное поведение Secure-кук на localhost —
    переиспользование LocalhostSession из tests/api)."""
    session = LocalhostSession()
    yield session
    session.close()


@pytest.fixture
def owner_session(contour_url):
    """Сессия owner с выполненным входом через nginx контура (на тест)."""
    session = login_session(contour_url, OWNER_LOGIN, OWNER_PASSWORD)
    yield session
    session.close()


@pytest.fixture(scope="session")
def owner_creds() -> tuple[str, str]:
    """Seed-креды owner (env-переопределяемые, из tests/api/conftest)."""
    return OWNER_LOGIN, OWNER_PASSWORD
