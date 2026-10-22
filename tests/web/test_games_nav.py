"""UI-тест навигации «Игры» (P26 game-portal; PRODUCT_BACKLOG.md
«P26. Интеграция game-portal»).

TC-games-web-001 — пункт сайдбара «Игры» под логином: href /games/,
СТРОГО после «Погода» (позиция после weather — P26 ТЗ), стиль базового
.nav-item + иконка inline-SVG в едином стиле эталона (P21 п.9).

Прокси-роут /games/ на тестовом стенде НЕ поднимается: контейнер
game-portal — standalone вне compose, поднимает ПМ (RUNBOOK §9); тест
проверяет ТОЛЬКО навигацию (сайдбар) через существующие session-фикстуры
tests/web/conftest.py (uvicorn app + static, Playwright). Контракт
nginx-прокси (sub_filter, вырезание префикса) — ревью конфига, не web-тест.
"""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]


def test_games_nav_sidebar_item(logged_in_page, web_base_url):
    """TC-games-web-001: пункт «Игры» в сайдбаре, href /games/,
    СТРОГО после «Погода» (P26 ТЗ: позиция после «Погода»)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")

    games_link = page.locator(".sidebar-nav .nav-item-games")
    weather_link = page.locator(".sidebar-nav .nav-item-weather")
    expect(games_link).to_be_visible()
    expect(weather_link).to_be_visible()

    # Порядок — «Игры» сразу после «Погода» (P26 ТЗ).
    order = page.evaluate(
        """() => {
        const items = [...document.querySelectorAll('.sidebar-nav .nav-item')];
        return items.map((el) => ({
          cls: el.className,
          text: el.textContent.trim(),
        }));
      }"""
    )
    texts = [item["text"] for item in order]
    assert texts.index("Игры") == texts.index("Погода") + 1

    # Ссылка ведет на прокси-префикс хаба (trailing слэш — корень хаба).
    assert games_link.get_attribute("href") == "/games/"

    # Базовый стиль существующих пунктов (класс .nav-item).
    assert "nav-item" in (games_link.get_attribute("class") or "")

    # P21 п.9: иконка — inline-SVG в едином стиле эталона (ОГР-8: без
    # <img>/use/внешних файлов; 16px, viewBox 0 0 24 24, aria-hidden).
    games_icon = games_link.locator("svg.nav-icon")
    expect(games_icon).to_have_count(1)
    assert games_link.evaluate("a => a.querySelector('img, use') === null")
    attrs = games_icon.evaluate(
        """el => ({
          viewBox: el.getAttribute('viewBox'),
          hidden: el.getAttribute('aria-hidden'),
          strokeBad: [...el.querySelectorAll('[stroke]')].some(
            p => p.getAttribute('stroke') !== 'currentColor'),
          fillBad: [...el.querySelectorAll('[fill]')].some(
            p => p.getAttribute('fill') !== 'none' && p.getAttribute('fill') !== 'currentColor'),
        })"""
    )
    assert attrs["viewBox"] == "0 0 24 24", attrs
    assert attrs["hidden"] == "true", attrs
    assert not attrs["strokeBad"] and not attrs["fillBad"], attrs
    box = games_icon.bounding_box()
    assert box and abs(box["width"] - 16) <= 1 and abs(box["height"] - 16) <= 1, box
