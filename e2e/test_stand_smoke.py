"""Сквозной сьют против compose-стенда (P11 ЭТАП 1, tasks 1.5; design §5).

Change add-containerization (FR-69): playwright + requests против полного
стека `deploy/compose.test.yaml` (nginx-контейнер :8443 + app-контейнер).
Проверяется то, что локальный web-стенд (tests/web: http.server вместо
nginx) не эмулирует:

  - заголовки кеша статики (`expires 7d`, Cache-Control public);
  - gzip (Vary: Accept-Encoding, сжатие CSS/JS ≥ gzip_min_length);
  - security-заголовки nginx (NFR-7);
  - смоук: неавторизованный → редирект /login; вход seeded-юзера owner;
    доска отрисована; статика отдается (nginx из образа).

Маркер `e2e_stand` — собственный скоуп (e2e/README.md, свой pytest.ini).

Конфигурация — только env (base URL стенда):
  EKOTOV_WIKI_E2E_BASE_URL   корень стенда, дефолт https://127.0.0.1:8443
  EKOTOV_WIKI_E2E_PASSWORD   пароль seeded owner (дефолт — тестовый из кейсов)

Без поднятия стенда тесты падают connection-error'ом — стенд поднимает
запускающий (README, CI-job e2e в flow.yml). Запуск: `pytest e2e`.
"""

from __future__ import annotations

import os

import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # self-signed стенда

BASE_URL_ENV = "EKOTOV_WIKI_E2E_BASE_URL"
PASSWORD_ENV = "EKOTOV_WIKI_E2E_PASSWORD"

OWNER_LOGIN = "owner"
OWNER_PASSWORD = os.environ.get(PASSWORD_ENV, "QaOwner_Pass_1!")

pytestmark = [pytest.mark.e2e_stand, pytest.mark.must]


def _base_url() -> str:
    return os.environ.get(BASE_URL_ENV, "https://127.0.0.1:8443").rstrip("/")


def _stand_session() -> requests.Session:
    """requests-сессия против стенда; TLS self-signed — verify=False
    (серт CN=194.58.34.122, клиенты ходят по IP — design compose.test.yaml)."""
    session = requests.Session()
    session.verify = False
    return session


def _login(session: requests.Session, base_url: str) -> requests.Session:
    resp = session.post(
        f"{base_url}/api/auth/login",
        json={"login": OWNER_LOGIN, "password": OWNER_PASSWORD},
    )
    assert resp.status_code == 200, (
        f"seed-вход owner не удался ({resp.status_code}): стенд поднят? "
        f"seed-юзер заведен? (e2e/README.md)"
    )
    return session


# --- Инфраструктура nginx (то, чего нет на http.server-стенде tests/web) ---


class TestNginxBehavior:
    """Поведение nginx-контейнера (design §5: кеш, gzip, security-заголовки)."""

    @pytest.fixture(scope="class")
    def static_headers(self):
        with _stand_session() as session:
            resp = session.get(f"{_base_url()}/static/css/app.css", timeout=10)
        assert resp.status_code == 200, f"статика не отдается: {resp.status_code}"
        return resp.headers

    def test_static_cache_headers_7d(self, static_headers):
        """FR-69: кеш статики — expires 7d + Cache-Control public
        (кеш-бастинг ?v= работает, URL не менялись — design §2)."""
        assert "expires" in static_headers, "нет заголовка Expires на статике"
        assert "public" in static_headers.get("Cache-Control", ""), (
            f"Cache-Control={static_headers.get('Cache-Control')!r} без public"
        )
        from email.utils import parsedate_to_datetime

        # expires ≈ date + 7 дней (допуск 1 мин на серверные часы).
        expires = parsedate_to_datetime(static_headers["expires"])
        date_hdr = parsedate_to_datetime(static_headers["date"])
        delta = expires.timestamp() - date_hdr.timestamp()
        assert abs(delta - 7 * 24 * 3600) < 60, (
            f"expires − date = {delta}s, ожидалось 7d (604800s)"
        )

    def test_gzip_enabled(self):
        """FR-69: gzip включен (Vary: Accept-Encoding; CSS ≥ min_length сжимается)."""
        with _stand_session() as session:
            resp = session.get(
                f"{_base_url()}/static/css/app.css",
                headers={"Accept-Encoding": "gzip"}, timeout=10,
            )
        assert resp.status_code == 200
        assert "gzip" in resp.headers.get("Content-Encoding", ""), (
            "ответ не сжат gzip — gzip off или mime-тип не в gzip_types"
        )
        assert "Accept-Encoding" in resp.headers.get("Vary", ""), (
            "нет Vary: Accept-Encoding (gzip_vary off)"
        )

    def test_security_headers(self):
        """NFR-7 через nginx-образ: nosniff, DENY, Referrer-Policy, HSTS."""
        with _stand_session() as session:
            resp = session.get(f"{_base_url()}/login", timeout=10)
        assert resp.status_code == 200
        headers = resp.headers
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "DENY"
        assert headers.get("Referrer-Policy") == "same-origin"
        assert "max-age=31536000" in headers.get("Strict-Transport-Security", "")

    def test_robots_txt_disallow_all(self):
        with _stand_session() as session:
            resp = session.get(f"{_base_url()}/robots.txt", timeout=10)
        assert resp.status_code == 200
        assert "Disallow: /" in resp.text


# --- Смоук авторизации и доски против compose-стенда ---


class TestSmoke:
    def test_unauthenticated_page_redirects_to_login(self):
        """Без сессии страницы → редирект /login (middleware через nginx)."""
        with _stand_session() as session:
            resp = session.get(f"{_base_url()}/board", allow_redirects=False, timeout=10)
        assert resp.status_code in (302, 307)
        assert resp.headers.get("location", "").endswith("/login")

    def test_openapi_without_session_not_public(self):
        """FR-68 сквозным путем через nginx: /openapi.json без сессии не 200."""
        with _stand_session() as session:
            resp = session.get(
                f"{_base_url()}/openapi.json", allow_redirects=False, timeout=10
            )
        assert resp.status_code in (302, 307, 401), (
            f"/openapi.json без сессии = {resp.status_code} — схема публична!"
        )

    def test_health_via_nginx(self):
        with _stand_session() as session:
            resp = session.get(f"{_base_url()}/api/health", timeout=10)
        assert resp.status_code == 200 and resp.json() == {"status": "ok"}

    def test_login_and_board_render(self):
        """Смоук: вход seeded owner → /board отрисован (данные через
        playwright-браузер — полный TLS-путь браузер → nginx → app)."""
        pytest.importorskip("playwright.sync_api", reason="playwright не установлен")

        from playwright.sync_api import expect, sync_playwright

        base_url = _base_url()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(ignore_https_errors=True)  # self-signed
            page = context.new_page()
            try:
                page.goto(f"{base_url}/login")
                page.get_by_label("Логин").fill(OWNER_LOGIN)
                page.get_by_label("Пароль").fill(OWNER_PASSWORD)
                page.get_by_role("button", name="Войти").click()
                expect(page.get_by_role("heading", name="Доска", exact=True)).to_be_visible()
                assert page.url.endswith("/board")
                # Сайдбар + три столбца доски (как TC-UI-002).
                for name in ("Доска", "Поиск", "Wiki"):
                    expect(page.get_by_role("link", name=name)).to_be_visible()
                for status in ("todo", "in_progress", "done"):
                    expect(page.locator(f'[data-status="{status}"]')).to_be_visible()
            finally:
                context.close()
                browser.close()
