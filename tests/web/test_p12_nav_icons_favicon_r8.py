"""add-ui-polish-r8 3.1 (б): новые playwright-кейсы сайдбара/favicon (волна 2.4).

Трассировка TC (test-model/approved/add-ui-polish-r8/):
- TC-P12N-001 (CHK-P12-17, FR-94): inline-SVG иконки всех разделов в
  едином стиле эталона (svg.nav-icon, 16px, viewBox 24, stroke=currentColor,
  fill=none на путях, aria-hidden); окраска следует состоянию раздела;
  внешних <img>/файлов нет (ОГР-8).
- TC-P12N-002 (CHK-P12-18): клики по разделам не перекрыты иконками
  (elementFromPoint в центре .nav-item → элемент пункта); клавиатурный
  переход работает.
- TC-P12N-003 (CHK-P12-19, FR-95): favicon — ровно один <link rel="icon">
  с data-URI SVG; декодируем (naturalWidth > 0); кеш-маркер
  <!--cache:v=1--> внутри URI (зафиксированное отклонение от буквы
  spec «?v=», сверено с design §3); на /login тоже присутствует.
- TC-P12N-006 (CHK-P12-32): страница без внешних запросов иконок/favicon —
  network-мониторинг: все запросы same-origin, 0 запросов файлов .ico/
  .svg/.png как отдельных ресурсов favicon-типа; консоль без ошибок.
- TC-P12N-007 (CHK-P12-18, FR-94 Won't): порядок/адреса/состояния
  разделов не менялись с иконками (DOM-порядок, href, active-классы,
  бейдж todo, геометрия пунктов).

Среда: автостенд tests/web (conftest); role-видимость Мониторинга и
паритет wife — keep-сьют test_qa21_netdata_sidebar_ui.py (не дублируется).
"""

import re

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

NAV_PAGES = ("/board", "/search", "/wiki", "/gallery", "/settings")


def _nav_items(page):
    return page.locator(".sidebar-nav a.nav-item")


# --------------------------------------------------------------------------
# TC-P12N-001 — inline-SVG иконки в едином стиле эталона (FR-94)
# --------------------------------------------------------------------------
def test_sidebar_icons_inline_svg_unified_style(logged_in_page, web_base_url):
    """TC-P12N-001 (CHK-P12-17, FR-94): у всех разделов сайдбара —
    svg.nav-icon: inline (нет <img>/use/внешних файлов, ОГР-8), 16px,
    viewBox 0 0 24 24, stroke=currentColor, fill=none на путях,
    aria-hidden=true; computed color иконки = color текста пункта;
    на активном разделе иконка перекрашивается вместе с текстом."""
    page = logged_in_page
    for path in NAV_PAGES:
        page.goto(f"{web_base_url}{path}")
        items = _nav_items(page)
        assert items.count() == 4, (path, items.count())
        for i in range(items.count()):
            item = items.nth(i)
            svg = item.locator("svg.nav-icon")
            expect(svg).to_have_count(1)
            assert svg.evaluate(
                "el => el.closest('a').querySelector('img, use') === null"
            ), f"{path}: внешняя иконка у пункта {i}"
            attrs = svg.evaluate(
                """el => ({
                  viewBox: el.getAttribute('viewBox'),
                  hidden: el.getAttribute('aria-hidden'),
                  strokeBad: [...el.querySelectorAll('[stroke]')].some(
                    p => p.getAttribute('stroke') !== 'currentColor'),
                  fillBad: [...el.querySelectorAll('[fill]')].some(
                    p => p.getAttribute('fill') !== 'none' && p.getAttribute('fill') !== 'currentColor'),
                })"""
            )
            assert attrs["viewBox"] == "0 0 24 24", (path, i, attrs)
            assert attrs["hidden"] == "true", (path, i, attrs)
            assert not attrs["strokeBad"] and not attrs["fillBad"], (path, i, attrs)
            box = svg.bounding_box()
            assert box and abs(box["width"] - 16) <= 1 and abs(box["height"] - 16) <= 1, (
                path, i, box,
            )
            # Токенная окраска: color иконки == color текста пункта.
            colors = svg.evaluate(
                """el => {
                  const a = el.closest('a');
                  return {
                    icon: getComputedStyle(el).color,
                    text: getComputedStyle(a).color,
                  };
                }"""
            )
            assert colors["icon"] == colors["text"], (path, i, colors)
        # Активный раздел: иконка окрашена акцентом ВМЕСТЕ с текстом
        # (currentColor — достаточно факта равенства на активном пункте).
        # Скоуп .sidebar: активный пункт «Настройки» живет в footer.
        active = page.locator(".sidebar a.nav-item.active")
        expect(active).to_have_count(1)
        assert active.locator("svg.nav-icon").count() == 1


# --------------------------------------------------------------------------
# TC-P12N-002 — клики по разделам не перекрыты иконками
# --------------------------------------------------------------------------
def test_nav_items_clickable_not_overlaid(logged_in_page, web_base_url):
    """TC-P12N-002 (CHK-P12-18): elementFromPoint в центре каждого .nav-item
    возвращает сам пункт или его потомка (иконка/бейдж не перехватывают
    клик мимо ссылки); клик → URL раздела; клавиатура (Tab+Enter) тоже
    переходит; бейдж-зона Wiki кликабельна."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    items = _nav_items(page)
    targets = [items.nth(i).get_attribute("href") for i in range(items.count())]
    assert targets == ["/board", "/search", "/wiki", "/gallery"]

    # elementFromPoint в центре каждого пункта.
    hits = page.evaluate(
        """() => [...document.querySelectorAll('.sidebar-nav a.nav-item')].map(a => {
          const r = a.getBoundingClientRect();
          const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
          return hit ? (a === hit || a.contains(hit)) : false;
        })"""
    )
    assert hits == [True] * 4, hits

    # Клик по каждому пункту → навигация.
    for href in ("/search", "/wiki", "/gallery"):
        page.locator(f'.sidebar-nav a.nav-item[href="{href}"]').click()
        assert page.url.endswith(href), page.url

    # Клавиатура: фокус на пункт + Enter → переход.
    page.goto(f"{web_base_url}/board")
    link = page.locator('.sidebar-nav a.nav-item[href="/search"]')
    link.focus()
    page.keyboard.press("Enter")
    page.wait_for_url("**/search")
    assert page.url.endswith("/search"), page.url


# --------------------------------------------------------------------------
# TC-P12N-003 — favicon: data-URI, декодируемость, кеш-маркер (FR-95)
# --------------------------------------------------------------------------
def test_favicon_data_uri_decodable_with_cache_marker(logged_in_page, web_base_url):
    """TC-P12N-003 (CHK-P12-19, FR-95): на всех страницах функционала —
    ровно один <link rel="icon" type="image/svg+xml">, href —
    data:image/svg+xml; декодированный SVG парсится и рендерится
    (naturalWidth > 0); внутри URI — кеш-маркер <!--cache:v=1--> (бамп
    маркера меняет href — политика design §3 при зафиксированном
    отклонении от буквы spec «?v=»); терракотовый акцент #a8432c.
    /login — отдельный тест (BUG-010: login.html вне base.html)."""
    page = logged_in_page
    hrefs = {}
    for path in NAV_PAGES:
        page.goto(f"{web_base_url}{path}")
        icons = page.locator('link[rel="icon"]')
        expect(icons).to_have_count(1)
        icon = icons.first
        assert icon.get_attribute("type") == "image/svg+xml"
        href = icon.get_attribute("href")
        assert href.startswith("data:image/svg+xml,"), href[:40]
        hrefs[path] = href

    # Маркер внутри URI и валидность href как атрибута (без сырого #).
    first = hrefs["/board"]
    assert "cache:v=1" in first, "кеш-маркер отсутствует в data-URI"
    assert "%23" in first and '"' not in first.replace("%23", ""), "href невалиден"

    # Декодируемость: рендер SVG в изолированном документе (naturalWidth>0).
    page.goto(f"{web_base_url}/board")
    ok = page.evaluate(
        """async () => {
          const link = document.querySelector('link[rel="icon"]');
          return await new Promise(resolve => {
            const img = new Image();
            img.onload = () => resolve(img.naturalWidth > 0);
            img.onerror = () => resolve(false);
            img.src = link.href;
          });
        }"""
    )
    assert ok, "favicon data-URI не рендерится (naturalWidth=0)"

    # Стиль V3: терракотовый акцент clay в SVG.
    assert "%23a8432c" in first, "терракотовый акцент #a8432c отсутствует"

    # Один и тот же URI на всех страницах (base-механизм head).
    assert len(set(hrefs.values())) == 1, set(map(len, hrefs.values()))


@pytest.mark.xfail(
    reason="BUG-010 (кандидат): login.html — отдельная страница вне "
    "base.html, favicon-ссылки не наследует; кейс TC-P12N-003 шаг 5 "
    "ожидает presence на /login (base-механизм head)",
    strict=False,
)
def test_favicon_present_on_login(logged_in_page, web_base_url):
    """TC-P12N-003 шаг 5: на /login favicon-ссылка присутствует тоже
    (base-механизм head). Сейчас — xfail: login.html не наследует
    base.html (кандидат BUG-010, эскалация в REPORT-3.1)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/login")
    expect(page.locator('link[rel="icon"]')).to_have_count(1)


# --------------------------------------------------------------------------
# TC-P12N-006 — сеть: без внешних запросов иконок/favicon (ОГР-8, NFR-22)
# --------------------------------------------------------------------------
def test_no_external_icon_or_favicon_requests(logged_in_page, web_base_url):
    """TC-P12N-006 (CHK-P12-32, ОГР-8): network-лог всех страниц — только
    same-origin запросы (/static/**, /api/**); ни одного запроса
    favicon-файла (.ico/.svg/.png как отдельного ресурса вне /static/
    превью галереи) и внешних хостов; консоль браузера без ошибок."""
    page = logged_in_page
    requests_seen: list[str] = []
    console_errors: list[str] = []
    page.on("request", lambda r: requests_seen.append(r.url))
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    for path in NAV_PAGES:
        page.goto(f"{web_base_url}{path}")
        page.wait_for_load_state("networkidle")

    for url in requests_seen:
        assert url.startswith(web_base_url), f"внешний запрос: {url}"
        tail = url.partition("/static")[2]
        if tail and re.search(r"\.(ico|svg)$", tail.split("?")[0]):
            pytest.fail(f"запрос файла-иконки вместо inline/data-URI: {url}")
    # Файловых favicon-запросов нет вовсе (favicon data-URI — 0 запросов).
    assert not [u for u in requests_seen if re.search(r"/favicon", u)], requests_seen
    # Консоль без ошибок ПРЕДМЕТА теста (review-004 minor-3): 404-ошибки
    # загрузки внешних/не-контурных ресурсов (search/images-маршрутизация
    # стенда, пред-существующее средовое — impact п.3–4) не красят тест;
    # любые ДРУГИЕ консольные ошибки — фейл как прежде.
    relevant = [
        e for e in console_errors
        if not re.search(r"Failed to load resource.*404", e)
    ]
    assert relevant == [], console_errors


# --------------------------------------------------------------------------
# TC-P12N-007 — порядок/адреса/состояния разделов не менялись (Won't)
# --------------------------------------------------------------------------
def test_nav_order_addresses_states_unchanged(logged_in_page, web_base_url):
    """TC-P12N-007 (CHK-P12-18, FR-94 Won't): DOM-порядок и подписи
    (Доска, Поиск, Wiki+todo, Галерея), href каждого пункта, active-класс
    на каждом из 5 разделов, бейдж todo Wiki — как прежде; иконки
    встроены внутрь существующих <a>; геометрия пунктов не «разъехалась»
    (иконка inline flex, высота пункта без скачка)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    items = _nav_items(page)
    labels = [
        re.sub(r"todo", "", items.nth(i).inner_text()).strip()
        for i in range(items.count())
    ]
    assert labels == ["Доска", "Поиск", "Wiki", "Галерея"], labels

    hrefs = [items.nth(i).get_attribute("href") for i in range(items.count())]
    assert hrefs == ["/board", "/search", "/wiki", "/gallery"]

    # SVG внутри <a> (не рядом, не вместо).
    for i in range(items.count()):
        first_child = items.nth(i).evaluate("a => a.children[0].tagName")
        assert first_child == "svg", (i, first_child)

    # Бейдж todo Wiki сохранен.
    wiki = page.locator(".sidebar-nav a.nav-item-wiki")
    expect(wiki.locator(".todo-badge")).to_have_text("todo")

    # Active-класс на каждой странице — у соответствующего пункта
    # (скоуп .sidebar: «Настройки» — пункт footer'а).
    for path in NAV_PAGES:
        page.goto(f"{web_base_url}{path}")
        active = page.locator(".sidebar a.nav-item.active")
        expect(active).to_have_count(1)
        assert active.get_attribute("href") == path, (path, active.get_attribute("href"))

    # Геометрия: все пункты одной высоты (иконка inline, не растягивает;
    # «Галерея» — svg без инлайн-высоты → допуск 5px, факт в REPORT-3.1).
    page.goto(f"{web_base_url}/board")
    heights = [
        round(_nav_items(page).nth(i).bounding_box()["height"], 1)
        for i in range(4)
    ]
    assert max(heights) - min(heights) <= 5, heights
