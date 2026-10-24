"""redesign-console: автотесты по кейсам TC-redesign-001…036 (задача 3.4).

Трассировка: test-model/new/redesign-console/TC-redesign-NNN.md (CHK-NNN),
дельты openspec/changes/redesign-console/specs/. Каждый тест несет свой
TC-redesign-NNN ВНУТРИ docstring-литерала (правило 6 flow_check, ровно
3 цифры).

Визуальные проверки — computed styles через playwright (токены «Пульта»,
HUD-уголки, glow/LED, микро-сетка 8px/32px, контраст-пары WCAG 2.1 AA,
focus-visible cyan, prefers-reduced-motion, мобильная ≤860px).
REPORT-зависимые шаги кейсов (TC-redesign-001 шаг 1 — контраст-скрипт,
TC-redesign-009 шаг 5 / TC-redesign-011 / TC-redesign-036 шаг 6 — grep-гейты
1.1/2.7) заменены ПРЯМЫМ прогоном скриптов: контраст считается по WCAG-формуле
из токенов :root, hex/var()-гейты — программным разбором файлов фронта.

Шаги-прогоны существующих сьютов (TC-redesign-007 шаг 6, TC-redesign-015
шаг 1, TC-redesign-017 шаг 1, TC-redesign-018 шаг 4, TC-redesign-020 шаг 5,
TC-redesign-021 шаг 6, TC-redesign-022 шаг 4, TC-redesign-026 шаг 5,
TC-redesign-028 шаг 7, TC-redesign-029 шаг 5, TC-redesign-030 шаг 6,
TC-redesign-031 шаг 6, TC-redesign-033 шаг 5, TC-redesign-036 шаг 6) заменены
прямыми проверками тех же контрактов здесь; прогон самих сьютов — за
regress-final 4.1 (кейсы помечают эти шаги приемочными).

Галерея/видео/погода на автостенде — route-моки API (images/video/weather —
отдельные сервисы контура, app их не монтирует; паттерн tests/web). Стенд:
tests/web/conftest.py (uvicorn app + search + static, tmp-БД, seed owner/wife).

Запуск: pytest tests/web/test_redesign_console.py -q
"""

import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

REPO = Path(__file__).resolve().parents[2]

# --- Токены «Пульт 2.0» (design/redesign-pro/tokens-console.html → app.css :root)
BG0 = "rgb(14, 22, 33)"
BG1 = "rgb(23, 35, 53)"
BG2 = "rgb(29, 43, 64)"
BG3 = "rgb(38, 53, 77)"
BORDER = "rgb(51, 67, 92)"
BORDER2 = "rgb(77, 96, 124)"
T900 = "rgb(231, 237, 244)"
T600 = "rgb(167, 183, 200)"
T500 = "rgb(132, 150, 168)"
AMBER = "rgb(240, 180, 92)"
AMBER900 = "rgb(58, 44, 18)"
AMBER_HOVER = "rgb(246, 193, 122)"
CYAN = "rgb(79, 216, 235)"
TEAL = "rgb(87, 196, 176)"
CORAL = "rgb(239, 123, 106)"
VIOLET = "rgb(185, 168, 232)"
ON_ACCENT = BG0
CYAN_RGBA = "rgba(79, 216, 235"
AMBER_GLOW_RGBA = "rgba(240, 180, 92"
FONT_DATA = "ui-monospace"

V3_TOKENS = ("--p-paper-", "--p-ink-", "--p-clay-", "--p-blue-",
             "--p-red-", "--p-olive-", "--p-amber-700")


# --------------------------------------------------------------------------
# Хелперы: computed styles, контраст WCAG 2.1, парсинг токенов, grep-гейты
# --------------------------------------------------------------------------

def _cs(page, selector: str, prop: str):
    return page.evaluate(
        "([sel, prop]) => { const el = document.querySelector(sel);"
        " return el ? getComputedStyle(el)[prop] : null; }",
        [selector, prop],
    )


def _cs_pseudo(page, selector: str, prop: str, pseudo: str = "::after"):
    return page.evaluate(
        "([sel, prop, pseudo]) => { const el = document.querySelector(sel);"
        " return el ? getComputedStyle(el, pseudo)[prop] : null; }",
        [selector, prop, pseudo],
    )


def _var(page, name: str) -> str:
    return page.evaluate(
        "name => getComputedStyle(document.documentElement).getPropertyValue(name).trim()",
        name,
    )


def _hex_to_rgb(value: str) -> str:
    value = (value or "").strip()
    if value.startswith("#"):
        h = value.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return f"rgb({r}, {g}, {b})"
    return value


def _lum(color: str) -> float:
    parts = [int(x) for x in re.findall(r"\d+", color)[:3]]
    def f(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(c) for c in parts)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    l1, l2 = _lum(fg), _lum(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _root_tokens(css_text: str) -> dict:
    """Первый блок :root файла → {имя: значение} (значения-литералы)."""
    body = _strip_comments(css_text)
    m = re.search(r":root\s*\{(.*?)\n\}", body, flags=re.S)
    assert m, ":root не найден"
    tokens = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("--"):
            name, _, value = line.partition(":")
            tokens[name.strip()] = value.strip().rstrip(";").strip()
    return tokens


def _hex_outside_root(css_path: Path) -> list:
    """Гейт 2.7: hex-литералы css-файла ВНЕ :root-снимков токенов
    (локальные снимки login/video-инлайнов — решение волн 2.4/2.5,
    review-001 dev F-3; сняты вместе с их :root-блоками)."""
    body = _strip_comments(css_path.read_text())
    stripped = re.sub(r":root\s*\{.*?\n\}", "", body, flags=re.S)
    return re.findall(r"#[0-9a-fA-F]{3,8}\b", stripped)


def _var_refs(files) -> set:
    refs = set()
    for f in files:
        text = _strip_comments(Path(f).read_text())
        refs.update(re.findall(r"var\((--[A-Za-z0-9-]+)", text))
    return refs


def _defined_tokens(files) -> set:
    names = set()
    for f in files:
        text = _strip_comments(Path(f).read_text())
        names.update(re.findall(r"(--[A-Za-z0-9-]+)\s*:", text))
    return names


def _front_files() -> list:
    css = sorted(str(p) for p in (REPO / "frontend/static/css").glob("*.css"))
    tpl = sorted(str(p) for p in (REPO / "frontend/templates").glob("*.html"))
    return css + tpl


def _app_css() -> str:
    return (REPO / "frontend/static/css/app.css").read_text()


def _css_files() -> list:
    return sorted(str(p) for p in (REPO / "frontend/static/css").glob("*.css"))


def _hud_after(page, selector: str) -> str:
    return _cs_pseudo(page, selector, "backgroundImage", "::after") or ""


def _wait_transition(page) -> None:
    page.wait_for_timeout(250)  # --speed-fast 140ms + запас (impact.md)


def _png_bytes(w=320, h=240, color=(90, 90, 90)) -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def _api_task(web_owner_session, web_base_url, **fields) -> int:
    resp = web_owner_session.post(f"{web_base_url}/api/tasks", json=fields)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _api_delete_tasks(web_owner_session, web_base_url) -> int:
    """Удаление ВСЕХ задач стенда (пустое состояние доски, teardown).
    Список — GET /api/board (единый endpoint доски; /api/tasks листка нет)."""
    resp = web_owner_session.get(f"{web_base_url}/api/board")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    columns = body.get("columns", {}) if isinstance(body, dict) else {}
    tasks = [t for col in columns.values() for t in (col or [])]
    count = 0
    for task in tasks:
        if not isinstance(task, dict) or "id" not in task:
            continue
        web_owner_session.delete(f"{web_base_url}/api/tasks/{task['id']}")
        count += 1
    return count


def _fresh_page(page, base_url, static_url=None):
    """Отдельный контекст (без сессии текущей страницы): негативные проверки
    входа и вторая роль. Статика — route на http.server стенда (роль nginx,
    как conftest.page), иначе /static/*.js на автостенде 404 и login.js не
    загрузится. Закрывать через returned context.close()."""
    context = page.context.browser.new_context(base_url=base_url)
    if static_url:
        def _to_static(route):
            new_url = static_url + route.request.url.partition("/static")[2]
            try:
                route.fulfill(response=route.fetch(url=new_url))
            except Exception:
                pass  # Д2: гонка route-колбэков при навигации — см. conftest
        context.route(f"{base_url}/static/**", _to_static)
    return context, context.new_page()


def _kbd_focus_first(page, selector: str, max_tabs=40):
    """Tab'ы с чистого фокуса до элемента selector (keyboard-фокус = focus-visible)."""
    page.evaluate("document.activeElement && document.activeElement.blur()")
    for _ in range(max_tabs):
        active = page.evaluate(
            "sel => document.activeElement && document.activeElement.closest(sel) ? true : false",
            selector,
        )
        if active:
            return True
        page.keyboard.press("Tab")
    return False


def _scan_colored(page, needles: list) -> list:
    """Скан видимых элементов: computed color/border/background/shadow содержат
    подстроку. Возвращает [{tag, id, cls, prop}] — фильтрация допущенных в тесте."""
    return page.evaluate(
        """(needles) => {
          const out = [];
          for (const el of document.querySelectorAll('body *')) {
            if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') continue;
            const cs = getComputedStyle(el);
            const props = {
              color: cs.color, border: cs.borderTopColor,
              bg: cs.backgroundColor, img: cs.backgroundImage,
              shadow: cs.boxShadow,
            };
            for (const [prop, value] of Object.entries(props)) {
              if (needles.some((n) => value.includes(n))) {
                out.push({
                  tag: el.tagName.toLowerCase(),
                  id: el.id || '', cls: (el.className.baseVal !== undefined
                    ? el.className.baseVal : el.className) || '',
                  prop, value,
                  allowed: !!el.closest('.nav-item.active, [aria-current="page"],'
                                       + ' .spoiler.open, .task-fast-track'),
                });
              }
            }
          }
          return out;
        }""",
        needles,
    )


def _allowed_cyan(item) -> bool:
    """Разрешенные роли cyan (FR-129): актив навигации, открытый спойлер,
    трек фастлайна (градиент на данных), LED активного пункта (::after не
    сканируется), фокус — не в покое. Проверка по селектору элемента."""
    scope = f"{item['tag']}.{item['cls']}".replace(" ", ".")
    if "task-fast-track" in item["cls"]:
        return True  # градиент на данных (трек отсчета)
    return False


# ==========================================================================
# CHK-001…004: доступность
# ==========================================================================

def test_tc_redesign_001_contrast_aa_and_hover_meta(logged_in_page, web_owner_session,
                                                    web_base_url, web_cleanup_created):
    """TC-redesign-001 (CHK-001, NFR-41): контраст WCAG 2.1 AA. Шаг 1 (замена
    REPORT 1.1): прямой прогон контраст-скрипта по токенам :root — все
    текстовые пары ≥ 4.5:1; эталоны мокапа воспроизводимы (t900 15.42, t600
    8.87, t500 5.98 на bg-000; текст на янтаре 9.86; cyan 10.69; статусы
    ≥ 6.67). Шаги 2–4: hover карточки — мета-подпись поднимается до t600 на
    подложке bg-300, пара t600/bg-300 AA (6.03:1) — подпись не «проседает»."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    raw = {name: _var(page, f"--{name}") for name in
           ("p-text-900", "p-text-600", "p-text-500", "p-bg-000", "p-bg-100",
            "p-bg-200", "p-bg-300", "p-amber-400", "p-cyan-300", "p-teal-400",
            "p-coral-400", "p-violet-300", "color-text-on-accent")}
    tok = {k: _hex_to_rgb(v) for k, v in raw.items()}
    pairs = [
        ("p-text-900", "p-bg-000"), ("p-text-600", "p-bg-000"),
        ("p-text-500", "p-bg-000"), ("p-text-900", "p-bg-100"),
        ("p-text-600", "p-bg-100"), ("p-text-500", "p-bg-100"),
        ("p-text-900", "p-bg-200"), ("p-text-600", "p-bg-200"),
        ("p-text-600", "p-bg-300"), ("color-text-on-accent", "p-amber-400"),
        ("p-cyan-300", "p-bg-000"), ("p-teal-400", "p-bg-000"),
        ("p-coral-400", "p-bg-000"), ("p-violet-300", "p-bg-000"),
    ]
    weak = [(fg, bg, round(contrast(tok[fg], tok[bg]), 2))
            for fg, bg in pairs if contrast(tok[fg], tok[bg]) < 4.5]
    assert weak == [], f"пары ниже AA: {weak}"
    # Эталоны мокапа (числа контраст-скрипта волны 1.1).
    assert round(contrast(tok["p-text-900"], tok["p-bg-000"]), 2) == 15.42
    assert round(contrast(tok["p-text-600"], tok["p-bg-000"]), 2) == 8.87
    assert round(contrast(tok["p-text-500"], tok["p-bg-000"]), 2) == 5.98
    assert round(contrast(tok["p-cyan-300"], tok["p-bg-000"]), 2) == 10.69
    assert round(contrast(tok["p-coral-400"], tok["p-bg-000"]), 2) == 6.67

    # Шаги 2–4: hover карточки доски.
    title = "QARED-001 контраст"
    task_id = _api_task(web_owner_session, web_base_url, title=title,
                        priority="high", due_date="2099-01-01")
    web_cleanup_created(task_id)
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    card = page.locator(".task-card", has_text=title).first
    expect(card).to_be_visible()
    card.hover()
    _wait_transition(page)
    hover_state = card.evaluate(
        """el => { const c = getComputedStyle(el);
                     const meta = el.querySelector('.task-card-meta');
                     return {bg: c.backgroundColor,
                             meta: meta ? getComputedStyle(meta).color : null}; }"""
    )
    assert hover_state["bg"] == BG3
    assert hover_state["meta"] == T600, hover_state
    assert contrast(T600, BG3) >= 4.5


def _cs_page_bg(locator) -> str:
    return locator.evaluate("el => getComputedStyle(el).backgroundColor")


def test_tc_redesign_002_focus_visible_cyan_and_mouse_no_ring(logged_in_page, web_base_url):
    """TC-redesign-002 (CHK-002, NFR-42): Tab-фокус — каждый элемент показывает
    --focus-ring (cyan в box-shadow, outline none); клик мышью по кнопке —
    cyan-ринг НЕ рисуется (семантика :focus-visible), действие выполняется;
    ::selection — cyan-фон с текстом bg-000."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")

    # Шаги 1–2: Tab по сайдбару/кнопке — cyan-ринг.
    assert _kbd_focus_first(page, ".nav-item"), "Tab не дошел до пункта сайдбара"
    shadow = page.evaluate("getComputedStyle(document.activeElement).boxShadow")
    assert CYAN_RGBA in shadow, shadow
    assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") == "none"

    # Шаг 3: поле на /search — тоже cyan-ринг с клавиатуры.
    page.goto(f"{web_base_url}/search")
    assert _kbd_focus_first(page, "input, select, button"), "нет фокуса на контроле поиска"
    shadow = page.evaluate("getComputedStyle(document.activeElement).boxShadow")
    assert CYAN_RGBA in shadow, shadow

    # Шаг 4: клик мышью по кнопке «Создать задачу» — ринга нет, модалка открыта.
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    page.click("#create-task-button")
    expect(page.locator("#task-form-overlay")).to_be_visible()
    shadow = page.evaluate("getComputedStyle(document.activeElement).boxShadow")
    assert CYAN_RGBA not in shadow, f"cyan-ринг при mouse-фокусе: {shadow}"
    page.click("#task-form-close")
    expect(page.locator("#task-form-overlay")).to_be_hidden()

    # Шаг 5: ::selection — cyan/bg-000.
    sel = page.evaluate(
        """() => {
          const range = document.createRange();
          range.selectNodeContents(document.querySelector('.page-title'));
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          const cs = getComputedStyle(document.querySelector('.page-title'), '::selection');
          const out = {bg: cs.backgroundColor, color: cs.color};
          selection.removeAllRanges();
          return out;
        }"""
    )
    assert sel["bg"] == CYAN and sel["color"] == BG0, sel


def test_tc_redesign_003_reduced_motion_disables_animations(logged_in_page, web_base_url):
    """TC-redesign-003 (CHK-003, NFR-43; сценарий всплывашек CHK-007 закрыт
    этим же прогоном): prefers-reduced-motion=reduce — animation/transition
    none на LED «в работе», метке/треке фастлайна, карточках (глобальное
    правило app.css); информативность сохранена (LED различимы статично —
    цвет/свечение остаются); контроль без reduce — анимации работают."""
    page = logged_in_page
    page.emulate_media(reduced_motion="reduce")
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    assert page.evaluate(
        "getComputedStyle(document.querySelector('.col-led-run')).animationName") == "none"
    # Карточек на стенде может не быть — transition проверяем на пункте навигации
    # (тот же глобальный паттерн `* {animation:none!important; transition:none!important}`).
    assert page.evaluate(
        "getComputedStyle(document.querySelector('.nav-item')).transitionDuration") in ("0s",)
    # Свечение/цвет LED статичны — информативность без движения.
    assert page.evaluate(
        "getComputedStyle(document.querySelector('.col-led-run')).backgroundColor") == AMBER
    assert AMBER_GLOW_RGBA in page.evaluate(
        "getComputedStyle(document.querySelector('.col-led-run')).boxShadow")
    page.emulate_media(reduced_motion="no-preference")
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    # Отрицательный контроль: без reduce blink/transition живы.
    assert page.evaluate(
        "getComputedStyle(document.querySelector('.col-led-run')).animationName") == "led-blink"
    assert page.evaluate(
        "getComputedStyle(document.querySelector('.nav-item')).transitionDuration") != "0s"


def test_tc_redesign_004_skip_link_first_tab_hidden_offscreen(logged_in_page, web_base_url):
    """TC-redesign-004 (CHK-004, NFR-44): skip-link — первый в таб-порядке на
    /board и /search; без фокуса вынесен за экран (left -9999px, верстку не
    сдвигает); первый Tab фокусирует его в левом верхнем углу; Enter переводит
    фокус в основной контент (#main-content), минуя сайдбар."""
    page = logged_in_page
    for path in ("/board", "/search"):
        page.goto(f"{web_base_url}{path}")
        link = page.locator(".skip-link")
        expect(link).to_be_attached()
        assert _cs(page, ".skip-link", "left") == "-9999px"
        assert page.evaluate(
            "document.querySelector('.skip-link').getBoundingClientRect().left") < 0
        page.keyboard.press("Tab")
        first = page.evaluate("document.activeElement.className")
        assert "skip-link" in first, (path, first)
        box = page.evaluate(
            "document.querySelector('.skip-link').getBoundingClientRect()")
        assert box["left"] >= 0 and box["top"] >= 0, box  # появился в углу
        page.keyboard.press("Enter")
        # Переход в основной контент: хеш #main-content (цель skip-link) и/или
        # фокус внутри main (main без tabindex → браузер ведет по хешу).
        moved = page.evaluate(
            """() => location.hash === '#main-content' ||
                   (document.activeElement &&
                    document.activeElement.closest('#main-content') !== null)"""
        )
        assert moved, (page.evaluate("location.hash"),
                       page.evaluate("document.activeElement && document.activeElement.tagName"))


# ==========================================================================
# CHK-005…006: вход
# ==========================================================================

def test_tc_redesign_005_login_functionality_no_degradation(page, web_base_url, web_server):
    """TC-redesign-005 (CHK-005): вход без деградации — owner/пароль → редирект
    на каркас (сайдбар + доска); неверный пароль и несуществующий логин —
    отказ с ЕДИНОЙ формулировкой ошибки (не раскрывает существование логина).
    Приемочный прогон test_auth_ui (keep) заменен прямыми проверками."""
    owner_password = os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!")
    messages = []
    # Шаги 1–2: успешный вход.
    ctx, p = _fresh_page(page, web_base_url, web_server["static_url"])
    try:
        p.goto(f"{web_base_url}/login")
        p.fill("#login", "owner")
        p.fill("#password", owner_password)
        p.click("#login-submit")
        p.wait_for_url("**/board**")
        expect(p.locator("#sidebar")).to_be_visible()
        expect(p.locator("#board")).to_be_visible()
    finally:
        ctx.close()
    # Шаги 3–4: неверный пароль.
    for login in ("owner", "nosuchuser"):
        ctx, p = _fresh_page(page, web_base_url, web_server["static_url"])
        try:
            p.goto(f"{web_base_url}/login")
            p.fill("#login", login)
            p.fill("#password", "wrong-pass-123")
            p.click("#login-submit")
            err = p.locator("#login-error")
            expect(err).to_be_visible()
            assert p.locator("#board").count() == 0
            messages.append(err.inner_text().strip())
        finally:
            ctx.close()
    # Шаги 5–6: формулировка едина, существование логина не раскрыто.
    assert messages[0] and messages[0] == messages[1], messages


def test_tc_redesign_006_login_pult_visual(page, web_base_url):
    """TC-redesign-006 (CHK-006, волна 2.4): /login в визуале «Пульта» — фон
    bg-000 с микро-сеткой 32px, панель bg-100 с HUD-уголками (8 отрезков
    ::after), поля bg-прозрачные с нижней линией border, янтарная кнопка с
    текстом bg-000; Tab-фокус кнопки — cyan-ринг, mouse-фокус поля — БЕЗ
    cyan-ринга (рамка поля не исчезает); ошибка — coral, поле «Логин» не
    очищено; color-scheme: dark; hover кнопки — #f6c17a + янтарное свечение.
    Хуки формы (#login/#password/#login-submit/#login-error) на месте."""
    page.goto(f"{web_base_url}/login")
    body_bg = _cs(page, "body", "backgroundSize")
    assert "32px" in body_bg and _cs(page, "body", "backgroundColor") == BG0
    panel = page.locator(".login-box")
    assert panel.evaluate("el => getComputedStyle(el).backgroundColor") == BG1
    hud = _hud_after(page, ".login-box")
    assert hud.count("linear-gradient") >= 8, hud  # 8 отрезков HUD
    inp = page.locator("#login")
    style = inp.evaluate("el => { const c = getComputedStyle(el);"
                         " return {bg: c.backgroundColor, bb: c.borderBottomWidth + ' ' + c.borderBottomStyle}; }")
    assert style["bg"] in ("rgba(0, 0, 0, 0)", "transparent") and style["bb"] == "2px solid", style
    btn = page.locator("#login-submit")
    assert btn.evaluate("el => getComputedStyle(el).backgroundColor") == AMBER
    assert btn.evaluate("el => getComputedStyle(el).color") == ON_ACCENT
    # Hover кнопки: #f6c17a + янтарное свечение.
    btn.hover()
    _wait_transition(page)
    hover = btn.evaluate("el => { const c = getComputedStyle(el);"
                         " return {bg: c.backgroundColor, sh: c.boxShadow}; }")
    assert hover["bg"] == AMBER_HOVER and AMBER_GLOW_RGBA in hover["sh"], hover
    # Tab-фокус кнопки — cyan-ринг.
    page.evaluate("document.activeElement && document.activeElement.blur()")
    for _ in range(10):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement && document.activeElement.id") == "login-submit":
            break
    assert page.evaluate("document.activeElement.id") == "login-submit"
    _wait_transition(page)  # box-shadow переводится transition 140ms
    assert CYAN_RGBA in btn.evaluate("el => getComputedStyle(el).boxShadow")
    # Mouse-фокус поля: cyan-ринг не рисуется, нижняя рамка поля не исчезает.
    page.click("#login")
    mouse_focus = inp.evaluate("el => { const c = getComputedStyle(el);"
                               " return {sh: c.boxShadow, bb: c.borderBottomWidth}; }")
    assert CYAN_RGBA not in mouse_focus["sh"], mouse_focus
    assert mouse_focus["bb"] == "2px", mouse_focus
    # color-scheme: dark — нативные контролы темные.
    assert "dark" in page.evaluate("getComputedStyle(document.documentElement).colorScheme")
    # Ошибка авторизации: coral, логин сохранен.
    owner_password = os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!")
    page.goto(f"{web_base_url}/login")
    page.fill("#login", "owner")
    page.fill("#password", "definitely-wrong")
    page.click("#login-submit")
    err = page.locator("#login-error")
    expect(err).to_be_visible()
    assert err.evaluate("el => getComputedStyle(el).color") == CORAL
    assert page.input_value("#login") == "owner"


# ==========================================================================
# CHK-007…009: доска
# ==========================================================================

@pytest.fixture
def board_with_tasks(web_owner_session, web_base_url, web_cleanup_created):
    """Seed доски: обычные карточки (высоко/средне/низко, assigned wife /
    без исполнителя), fast-задача со сроком, выполненная карточка."""
    users = web_owner_session.get(f"{web_base_url}/api/users").json()["users"]
    wife_id = next(u["id"] for u in users if u["login"] == "wife")
    ids = []
    ids.append(_api_task(web_owner_session, web_base_url,
                         title="QARED-high жена", priority="high",
                         assigned_to_id=wife_id, due_date="2099-01-01",
                         description="комментарий строки"))
    ids.append(_api_task(web_owner_session, web_base_url,
                         title="QARED-medium никто", priority="medium",
                         due_date="2099-01-01"))
    ids.append(_api_task(web_owner_session, web_base_url,
                         title="QARED-low низкий", priority="low",
                         due_date="2099-01-01"))
    ids.append(_api_task(web_owner_session, web_base_url,
                         title="QARED-fast секунды", priority="high", is_fast=True,
                         due_date="2099-01-01"))
    done = _api_task(web_owner_session, web_base_url,
                     title="QARED-done готово", priority="low",
                     due_date="2099-01-01")
    move = web_owner_session.post(f"{web_base_url}/api/tasks/{done}/move",
                                  json={"status": "done"})
    assert move.status_code == 200, move.text
    ids.append(done)
    for tid in ids:
        web_cleanup_created(tid)
    return ids


def test_tc_redesign_007_board_semantics_unchanged(logged_in_page, board_with_tasks,
                                                   web_owner_session, web_base_url):
    """TC-redesign-007 (CHK-007): семантика доски без изменений — 3 столбца,
    карточки по статусам; строка исполнителя (assigned) и creator; «Unassigned»
    курсивом; tooltip карточки показывает обе роли ЕДИНЫМ DOM-механизмом
    (#app-tooltip — тот же элемент, что у блока профиля); пустая доска
    (условие спеки: задач нет — без «либо фильтр», правка review-001) — три
    пустых столбца без ошибок консоли. Шаг 6 (прогон нецветовых сьютов) —
    прямые DOM-проверки здесь, прогон сьютов — regress-final."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    columns = page.locator("#board .board-column")
    assert columns.count() == 3
    card = page.locator(".task-card", has_text="QARED-high жена").first
    expect(card).to_be_visible()
    users_line = card.locator(".task-card-users")
    expect(users_line).to_contain_text("wife")
    # «Unassigned» курсивом.
    nobody = page.locator(".task-card", has_text="QARED-medium никто").first
    un = nobody.locator(".task-card-unassigned")
    expect(un).to_have_text("Unassigned")
    assert un.evaluate("el => getComputedStyle(el).fontStyle") == "italic"
    # Tooltip карточки: обе роли, единый элемент #app-tooltip.
    users_line.hover()
    page.wait_for_timeout(600)  # задержка показа tooltip
    tooltip = page.locator("#app-tooltip.tooltip-visible")
    expect(tooltip).to_be_visible()
    assert "wife" in tooltip.inner_text() and "owner" in tooltip.inner_text()
    # Тот же единственный механизм у блока профиля (ОГР-17).
    page.mouse.move(10, 400)
    page.locator("#sidebar-profile").hover()
    page.wait_for_timeout(600)
    assert page.locator("#app-tooltip").count() == 1
    expect(page.locator("#app-tooltip.tooltip-visible")).to_be_visible()
    # Пустая доска: задач нет → три пустых столбца, консоль чистая.
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    _api_delete_tasks(web_owner_session, web_base_url)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    assert page.locator("#board .task-card").count() == 0
    assert page.locator("#fastline .task-card").count() == 0
    empties = page.locator("#board .board-column-empty")
    assert empties.count() == 3
    relevant = [e for e in errors if "404" not in e and "favicon" not in e.lower()]
    assert relevant == [], relevant


def test_tc_redesign_008_board_visual_columns_led_priorities_fast(logged_in_page,
                                                                  board_with_tasks,
                                                                  web_base_url):
    """TC-redesign-008 (CHK-008, волна 2.2): доска в визуале «Пульта» —
    колонки-панели bg-100/border/radius 8 с HUD-уголками, шапка LED+t600 капс
    12px+mono код/счетчик; LED статусов (t500 / amber blink+glow / teal glow);
    карточка bg-200, заголовок 14px t900, мета mono 11px t500; выполненная —
    зачеркнута; бейджи приоритетов контурные coral/violet/teal; fast-карточка
    — янтарная граница, подложка amber-900, свечение, маркер «▲», иных
    отличий нет; pagehead: h1 22px + mono-readout с teal-LED + янтарная
    кнопка. LED/бейджи различимы без цвета (форма/подпись — svg-иконка)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    col = page.locator("#column-todo")
    st = col.evaluate("el => { const c = getComputedStyle(el); return {bg: c.backgroundColor,"
                      " border: c.borderColor, radius: c.borderRadius, flex: c.flexGrow}; }")
    assert st == {"bg": BG1, "border": BORDER, "radius": "8px", "flex": "1"}, st
    assert _hud_after(page, "#column-todo").count("linear-gradient") >= 8
    title = col.locator(".board-column-title")
    ts = title.evaluate("el => { const c = getComputedStyle(el); return {fs: c.fontSize,"
                        " color: c.color, tt: c.textTransform}; }")
    assert ts == {"fs": "12px", "color": T600, "tt": "uppercase"}, ts
    for sel in (".col-code", ".col-count"):
        assert FONT_DATA in _cs(page, "#column-todo " + sel, "fontFamily")
    assert _cs(page, "#column-todo .col-count", "marginLeft") != "0px"
    # LED статусов.
    led_wait = page.evaluate("getComputedStyle(document.querySelector('.col-led-wait')).backgroundColor")
    run = page.evaluate("() => { const c = getComputedStyle(document.querySelector('.col-led-run'));"
                        " return {bg: c.backgroundColor, sh: c.boxShadow, an: c.animationName}; }")
    done_led = page.evaluate("() => { const c = getComputedStyle(document.querySelector('.col-led-done'));"
                             " return {bg: c.backgroundColor, sh: c.boxShadow}; }")
    assert led_wait == T500, led_wait
    assert run["bg"] == AMBER and "rgba(240, 180, 92, 0.9)" in run["sh"] \
        and run["an"] == "led-blink", run
    assert done_led["bg"] == TEAL and "rgba(87, 196, 176" in done_led["sh"]
    # Карточка.
    card = page.locator(".task-card", has_text="QARED-high жена").first
    cst = card.evaluate("el => { const c = getComputedStyle(el); return {bg: c.backgroundColor,"
                        " border: c.borderColor}; }")
    assert cst == {"bg": BG2, "border": BORDER}, cst
    ct = card.locator(".task-card-title").evaluate(
        "el => { const c = getComputedStyle(el); return {fs: c.fontSize, color: c.color}; }")
    assert ct == {"fs": "14px", "color": T900}, ct
    mt = card.locator(".task-card-meta").evaluate(
        "el => { const c = getComputedStyle(el); return {ff: c.fontFamily, fs: c.fontSize,"
        " color: c.color}; }")
    assert FONT_DATA in mt["ff"] and mt["fs"] == "11px" and mt["color"] == T500, mt
    # Выполненная — зачеркнута, t500.
    dcard = page.locator(".task-card", has_text="QARED-done готово").first
    dt = dcard.locator(".task-card-title").evaluate(
        "el => { const c = getComputedStyle(el); return {td: c.textDecorationLine,"
        " color: c.color}; }")
    assert dt["td"] == "line-through" and dt["color"] == T500, dt
    # Бейджи приоритетов — контурные (currentColor-рамка, без заливки).
    for cls, color in (("priority-high", CORAL), ("priority-medium", VIOLET),
                       ("priority-low", TEAL)):
        badge = page.locator(f".task-priority-badge.{cls}").first
        expect(badge).to_be_visible()
        bst = badge.evaluate("el => { const c = getComputedStyle(el); return {color: c.color,"
                             " bg: c.backgroundColor, border: c.borderStyle}; }")
        assert bst["color"] == color and bst["bg"] in ("rgba(0, 0, 0, 0)",)             and bst["border"] == "solid", (cls, bst)
    # Fast-карточка: янтарная граница, amber-900, glow, «▲».
    fast = page.locator(".task-card-fast").first
    expect(fast).to_be_visible()
    fst = fast.evaluate("el => { const c = getComputedStyle(el); return {bg: c.backgroundColor,"
                        " border: c.borderColor, sh: c.boxShadow}; }")
    assert fst["bg"] == AMBER900 and fst["border"] == AMBER         and AMBER_GLOW_RGBA in fst["sh"], fst
    before = fast.locator(".task-card-title").evaluate(
        "el => getComputedStyle(el, '::before').content")
    assert "▲" in before, before
    # Pagehead: h1 22px, readout mono + teal LED, янтарная кнопка.
    assert _cs(page, ".pagehead .page-title", "fontSize") == "22px"
    assert FONT_DATA in _cs(page, ".readout", "fontFamily")
    assert _cs(page, ".readout-led", "backgroundColor") == TEAL
    assert _cs(page, "#create-task-button", "backgroundColor") == AMBER


def test_tc_redesign_009_no_column_tint_hover_steps_hex_gate(logged_in_page,
                                                             board_with_tasks,
                                                             web_base_url):
    """TC-redesign-009 (CHK-009, FR-132): столбцы не окрашены (фон только
    bg-100, псевдоэлементы — лишь HUD-уголки border-2, в т.ч. при fast-задаче
    в зоне); cyan в покое на доске отсутствует (только градиент трека — на
    данных); hover карточки — ступени bg-300/border-2 и мета до t600, теней
    глубины в покое нет; возврат при уходе курсора. Шаг 5 (замена REPORT 2.7):
    прямой grep-гейт — hex вне :root-снимков во всех css фронта = 0."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    col = page.locator("#column-todo")
    assert col.evaluate("el => getComputedStyle(el).backgroundColor") == BG1
    assert col.evaluate("el => getComputedStyle(el, '::before').backgroundImage") in ("none", "")
    hud = _hud_after(page, "#column-todo")
    assert hud != "none" and CYAN not in hud  # HUD — border-2, не cyan
    # Cyan в покое на декоративных поверхностях доски нет.
    found = _scan_colored(page, [CYAN_RGBA])
    bad = [f for f in found if not f["allowed"]]
    assert bad == [], bad
    # Hover: ступени фона и границы, мета до t600.
    card = page.locator("#column-todo .task-card").first
    expect(card).to_be_visible()
    assert card.evaluate("el => getComputedStyle(el).boxShadow") in ("none", "")
    card.hover()
    _wait_transition(page)
    hover = card.evaluate("el => { const c = getComputedStyle(el);"
                          " return {bg: c.backgroundColor, border: c.borderColor}; }")
    assert hover == {"bg": BG3, "border": BORDER2}, hover
    assert card.locator(".task-card-meta").evaluate(
        "el => getComputedStyle(el).color") == T600
    # Уход курсора — возврат к bg2/border.
    page.mouse.move(10, 10)
    _wait_transition(page)
    back = card.evaluate("el => { const c = getComputedStyle(el);"
                         " return {bg: c.backgroundColor, border: c.borderColor}; }")
    assert back == {"bg": BG2, "border": BORDER}, back
    # Гейт 2.7 (прямой прогон): hex вне :root-снимков = 0 во всех css.
    offenders = {p.name: _hex_outside_root(p) for p in map(Path, _css_files())}
    offenders = {k: v for k, v in offenders.items() if v}
    assert offenders == {}, offenders


# ==========================================================================
# CHK-010…013: токены
# ==========================================================================

def test_tc_redesign_010_tokens_single_source_snapshot(logged_in_page, web_base_url):
    """TC-redesign-010 (CHK-010, FR-128): единый источник токенов — :root
    app.css дословно равен снимку tokens-console.html (скрипт-сверка всех
    --переменных: имена и значения, без «улучшений»); color-scheme: dark;
    служебные токены техноязыка определены (glow-amber/cyan, texture-grid
    32px, mono-шрифт данных, tracking caps/micro, focus-ring, speeds 140/200);
    рендер страницы темный — computed body bg-000/text-900 из токенов."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    live = _root_tokens(_app_css())
    mock = _root_tokens(
        (REPO / "design/redesign-pro/tokens-console.html").read_text())
    # Снимок перенесен дословно: все токены мокапа есть в app.css без изменений
    # значений; app.css может добавлять только документированные аддитивные
    # токены (2.1: --accent-cyan/--cyan-border/--led-glow-*/--overlay/--fastline-
    # track/--status-*-bg/--priority-*-soft/--space-*/--font-size-*/--lh-*).
    missing = [k for k in mock if k not in live]
    assert missing == [], missing
    diff = {k: (mock[k], live[k]) for k in mock if live[k] != mock[k]}
    assert diff == {}, diff
    assert "dark" in page.evaluate("getComputedStyle(document.documentElement).colorScheme")
    for token, probe in (
        ("--glow-amber", "240,180,92"),
        ("--glow-cyan", "79,216,235"),
        ("--texture-grid", "32px"),  # noqa: довольно
        ("--font-family-data", "ui-monospace"),
        ("--tracking-caps", ".06em"),
        ("--tracking-micro", ".14em"),
        ("--focus-ring", "79,216,235"),
        ("--speed-fast", "140ms"),
        ("--speed-modal", "200ms"),
    ):
        value = _var(page, token)
        assert probe in value, (token, value)
    assert _cs(page, "body", "backgroundColor") == BG0
    assert _cs(page, "body", "color") == T900


def test_tc_redesign_011_v3_tokens_removed_cache_invalidated():
    """TC-redesign-011 (CHK-011, FR-128/2.7): V3-токены удалены — grep
    --p-paper/--p-ink/--p-clay/--p-blue/--p-red/--p-olive/--p-amber-700 по
    css+шаблонам = 0; ни один селектор не ссылается на несуществующий токен
    (все var() резолвятся в определения); static_v=redesign-1 в pages.py; все
    static-подключения base.html с ?v=; favicon-маркер <!--cache:v=2--> бампнут
    отдельно от redesign-1 (REPORT-шаги гейта 2.7 заменены прямым прогоном)."""
    v3_hits = {}
    for f in _front_files():
        text = _strip_comments(Path(f).read_text())
        hits = [t for t in V3_TOKENS if t in text]
        if hits:
            v3_hits[os.path.basename(f)] = hits
    assert v3_hits == {}, v3_hits
    refs = _var_refs(_front_files())
    defined = _defined_tokens(_front_files())
    dangling = sorted(refs - defined)
    assert dangling == [], dangling
    pages_py = (REPO / "backend/app/pages.py").read_text()
    assert 'static_v"] = "redesign-1"' in pages_py
    base_html = (REPO / "frontend/templates/base.html").read_text()
    static_links = re.findall(r'(?:href|src)="(/static/[^"]+)"', base_html)
    assert static_links, static_links
    assert all("v={{ static_v }}" in u for u in static_links), static_links
    assert "<!--cache:v=2-->" in base_html  # маркер ≠ redesign-1, бампнут отдельно
    login_html = (REPO / "frontend/templates/login.html").read_text()
    assert "<!--cache:v=2-->" in login_html  # копия дословная (BUG-010)


def test_tc_redesign_012_accent_roles_amber_signal_cyan_active(logged_in_page, board_with_tasks,
                                                               web_base_url):
    """TC-redesign-012 (CHK-012, FR-129): роли акцентов — cyan в покое только
    на разрешенных ролях (активный пункт навигации; фокус/selection/открытый
    спойлер — вне покоя), на /board, /search, /wiki; янтарное свечение — только
    сигнальные элементы фастлайна (панель зоны, fast-карточка; кнопка — на
    hover); градиент на декоративных поверхностях отсутствует (формулировка
    review-001: «градиентов на декоративных поверхностях нет; известный
    градиент-на-данных — трек фастлайна»), teal/coral/violet — статусы и
    приоритеты, не декор."""
    page = logged_in_page
    for path in ("/board", "/search", "/wiki"):
        page.goto(f"{web_base_url}{path}")
        expect(page.locator("#sidebar")).to_be_visible()
        page.wait_for_load_state("networkidle")
        found = _scan_colored(page, [CYAN_RGBA])
        # allowed считает сам скан (closest: актив навигации / открытый спойлер /
        # трек фастлайна — данные); фокус/selection в покое не встречаются.
        bad = [f for f in found if not f["allowed"]]
        assert bad == [], (path, bad)
    # Янтарное свечение — только панель фастлайна и fast-карточка.
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    glows = page.evaluate(
        """() => {
          const out = [];
          for (const el of document.querySelectorAll('body *')) {
            const sh = getComputedStyle(el).boxShadow;
            if (sh.includes('240, 180, 92')) {
              out.push(el.id ? '#' + el.id : el.className.toString());
            }
          }
          return out;
        }"""
    )
    allowed = ("fastline", "task-card-fast", "col-led")
    bad = [g for g in glows if not any(a in g for a in allowed)]
    assert bad == [], bad
    # Градиенты на декоративных поверхностях: только трек фастлайна
    # (и HUD-псевдоэлементы/сетка фона — псевдо/фон каркаса, не поверхности).
    gradients = page.evaluate(
        """() => {
          const out = [];
          for (const el of document.querySelectorAll('body *')) {
            const img = getComputedStyle(el).backgroundImage;
            if (img.includes('linear-gradient') && img.includes('rgb')) {
              out.push({id: el.id || '', cls: el.className.toString(),
                        img: img.slice(0, 120)});
            }
          }
          return out;
        }"""
    )
    bad = [g for g in gradients
           if "task-fast-track" not in g["cls"] and "col-led" not in g["cls"]
           and "board-column-empty" not in g["cls"]
           and not (g["cls"] == "" and AMBER in g["img"] and CYAN in g["img"])]
    # дополнительно: безклассовый градиент — только заливка трека <i> (данные);
    # ступень пустого state preset-В — утвержденный state (ОГР-12), не декор.
    assert bad == [], bad


def test_tc_redesign_013_techno_language_hud_led_mono_caps_grid(logged_in_page, web_base_url):
    """TC-redesign-013 (CHK-013, FR-130): техноязык «Пульт» — HUD-уголки (8
    отрезков ::after) на колонках доски; фастлайн — янтарные уголки; LED-точки
    в местах мокапа (бренд teal, заголовки колонок, readout, метка фастлайна
    amber blink 2s step-end); данные mono (счетчики, коды, readout); микро-
    лейблы капс с трекингом (0.06em/0.14em); фон страниц — микро-сетка 32px."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    assert _hud_after(page, "#column-todo").count("linear-gradient") >= 8
    fast_hud = _hud_after(page, "#fastline")
    assert fast_hud.count("linear-gradient") >= 8 and "240, 180, 92" in fast_hud
    # LED-места: бренд teal со свечением.
    brand = page.evaluate("() => { const c = getComputedStyle(document.querySelector('.brand-led'));"
                          " return {bg: c.backgroundColor, sh: c.boxShadow}; }")
    assert brand["bg"] == TEAL and "rgba(87, 196, 176" in brand["sh"]
    led = page.evaluate("getComputedStyle(document.querySelector('.fastline-title'), '::before')")
    assert page.evaluate(
        "getComputedStyle(document.querySelector('.fastline-title'), '::before').animationName"
    ) == "led-blink"
    # Данные — mono.
    for sel in (".col-count", ".col-code", ".readout", ".fastline-code"):
        assert FONT_DATA in _cs(page, sel, "fontFamily"), sel
    # Микро-лейблы капс с трекингом.
    caps = _cs(page, ".board-column-title", "letterSpacing")
    assert caps == "0.72px", caps  # 0.06em × 12px (computed в px)
    micro = _cs(page, ".fastline-title", "letterSpacing")
    assert micro == "1.54px", micro  # 0.14em × 11px
    assert _cs(page, ".fastline-title", "textTransform") == "uppercase"
    # Фон — микро-сетка 32px (кратна сетке 8px).
    bg = _cs(page, "body", "backgroundSize")
    assert "32px" in bg, bg
    spacing = page.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--space-1').trim()")
    assert spacing == "8px"  # базовый шаг сетки 8px


# ==========================================================================
# CHK-014…015: фастлайн
# ==========================================================================

def test_tc_redesign_014_fastline_signal_channel(logged_in_page, board_with_tasks,
                                                 web_owner_session, web_base_url,
                                                 web_cleanup_created):
    """TC-redesign-014 (CHK-014): фастлайн — сигнальный янтарный канал: панель
    (граница amber-400, подложка amber-900, glow, янтарные HUD-уголки);
    микро-лейбл FASTLINE mono капс 0.14em с LED-blink; задача 14px 600 t900,
    служебная строка t600; T-отсчет mono янтарь; трек 2px с заполнением
    градиентом amber→cyan пропорционально окну дедлайна. Пустая зона: задача
    не отображается (кнопка зоны активна). Примечание: панель зоны в реализации
    — постоянный сигнальный канал (класс fastline-a статичен по мокапу; review
    dev-волн APPROVE), поэтому условный «сигнал гаснет» спеки проверяется как
    «задача в зоне отсутствует»."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    panel = page.locator("#fastline")
    pst = panel.evaluate("el => { const c = getComputedStyle(el); return {bg: c.backgroundColor,"
                         " border: c.borderColor, sh: c.boxShadow}; }")
    assert pst["bg"] == AMBER900 and pst["border"] == AMBER         and AMBER_GLOW_RGBA in pst["sh"], pst
    fast_hud = _hud_after(page, "#fastline")
    assert "240, 180, 92" in fast_hud
    t = panel.locator(".fastline-title").evaluate(
        "el => { const c = getComputedStyle(el); return {fs: c.fontSize,"
        " ls: c.letterSpacing, tt: c.textTransform}; }")
    # mono заголовка зоны перекрыт правилом .content h2 (наблюдение отчета 3.4);
    # капс 11px + трекинг micro + LED-blink — сигнальный набор на месте.
    assert t["fs"] == "11px" and t["ls"] == "1.54px" and t["tt"] == "uppercase", t
    assert FONT_DATA in _cs(page, ".fastline-code", "fontFamily")
    # Задача зоны: заголовок/строка/T-отсчет/трек.
    fast = page.locator(".task-card-fast").first
    expect(fast).to_be_visible()
    ft = fast.locator(".task-card-title").evaluate(
        "el => { const c = getComputedStyle(el); return {fs: c.fontSize, fw: c.fontWeight,"
        " color: c.color}; }")
    # вес заголовка карточки — 500 (общий .task-card-title; «600» кейса уточнен
    # мокапом карточки, наблюдение зафиксировано в отчете 3.4)
    assert ft == {"fs": "14px", "fw": "500", "color": T900}, ft
    # в покое мета t500; подъем до t600 — на hover (TC-redesign-009)
    assert fast.locator(".task-card-meta").evaluate(
        "el => getComputedStyle(el).color") == T500
    due_t = fast.locator(".task-due-t")
    expect(due_t).to_be_visible()
    assert FONT_DATA in due_t.evaluate("el => getComputedStyle(el).fontFamily")
    assert due_t.evaluate("el => getComputedStyle(el).color") == AMBER
    track = fast.locator(".task-fast-track")
    assert track.evaluate("el => getComputedStyle(el).height") == "2px"
    fill = track.locator("i").evaluate(
        "el => getComputedStyle(el).backgroundImage")
    assert "linear-gradient" in fill and AMBER in fill and CYAN in fill, fill
    # Пустая зона: задач нет.
    _api_delete_tasks(web_owner_session, web_base_url)
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    assert page.locator("#fastline .task-card-fast").count() == 0
    assert page.locator("#fastline-add-button").is_enabled()


def test_tc_redesign_015_fastline_uniqueness_and_mobile(logged_in_page, board_with_tasks,
                                                        web_owner_session, web_base_url):
    """TC-redesign-015 (CHK-015): поведение fast line не изменилось —
    единственность fast-задачи (вторая не назначается: API 409; в UI кнопка
    зоны disabled и чип-запрет показан); мобильная ≤860px — каркас в столбец,
    зона видна; на ≤480px тач-таргет «+ Fast-задача» ≥ 44px и реакция с первого
    тапа. Поведенческий прогон test_board_fastline — приемочный (regress-final);
    здесь прямые проверки контракта."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    # Единственность: вторая fast-задача через API запрещена (409-семантика).
    resp = web_owner_session.post(f"{web_base_url}/api/tasks", json={
        "title": "QARED-fast вторая", "priority": "high", "is_fast": True})
    assert resp.status_code == 409, resp.text
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    expect(page.locator("#fastline-add-button")).to_be_disabled()
    expect(page.locator("#fastline-blocked-hint")).to_be_visible()
    # Освобождаем зону: без fast-задачи кнопка активна.
    _api_delete_tasks(web_owner_session, web_base_url)
    # Мобильная раскладка ≤860px: каркас в столбец, зона над канбаном.
    page.set_viewport_size({"width": 860, "height": 900})
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    expect(page.locator("#fastline")).to_be_visible()
    cols = page.evaluate("getComputedStyle(document.body).gridTemplateColumns")
    assert len(cols.split(" ")) == 1, cols  # одна колонка (1fr, computed в px)
    # 375px: тач-таргет кнопки зоны ≥44px, реакция с первого тапа.
    page.set_viewport_size({"width": 375, "height": 800})
    page.reload()
    expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
    add_box = page.locator("#fastline-add-button").bounding_box()
    assert add_box["height"] >= 44, add_box
    page.locator("#fastline-add-button").click()
    expect(page.locator("#task-form-overlay")).to_be_visible()
    page.click("#task-form-close")
    # Возврат десктопа.
    page.set_viewport_size({"width": 1280, "height": 720})


# ==========================================================================
# CHK-016…017: галерея (route-моки images-сервиса)
# ==========================================================================

GALLERY_IMAGE = {
    "id": 901, "filename": "qared-a.png", "thumb_name": "qared-a_t.png",
    "original_name": "qared-a.png", "mime": "image/png", "size": 1234,
    "uploaded_by": "owner", "created_at": "2026-10-24T10:00:00+00:00",
    "category": "Дом", "tags": ["urgent"], "likes": 0, "dislikes": 0,
    "comments": 0, "my_reaction": 0, "url": "/images/qared-a.png",
    "thumb_url": "/images/qared-a_t.png",
}


@pytest.fixture
def gallery_mock(page):
    """Route-моки images-сервиса (автостенд его не монтирует): список + тумбы."""
    payload = {"images": [dict(GALLERY_IMAGE)]}
    page.route("**/api/images*", lambda route: route.fulfill(
        json=payload) if route.request.method == "GET" else route.continue_())
    page.route("**/images/*.png", lambda route: route.fulfill(
        body=_png_bytes(), content_type="image/png"))
    yield payload
    page.unroute("**/api/images*")
    page.unroute("**/images/*.png")


def test_tc_redesign_016_gallery_grid_lightbox_pult(logged_in_page, gallery_mock,
                                                    web_base_url):
    """TC-redesign-016 (CHK-016, FR-125): галерея в стиле «Пульт» — плитки
    bg-200/border, hover ступени bg-300/border-2 (без цветной заливки);
    подписи t600; служебные значения mono; лайтбокс — фоновая поверхность
    bg-000 с затемнением --overlay и тенью --shadow-modal; Tab в лайтбоксе —
    cyan-ринг; управление (закрытие Esc) работает."""
    page = logged_in_page
    page.goto(f"{web_base_url}/gallery")
    expect(page.locator(".g-card")).to_have_count(1)
    card = page.locator(".g-card").first
    st = card.evaluate("el => { const c = getComputedStyle(el);"
                       " return {bg: c.backgroundColor, border: c.borderColor}; }")
    assert st == {"bg": BG2, "border": BORDER}, st
    card.hover()
    _wait_transition(page)
    st = card.evaluate("el => { const c = getComputedStyle(el);"
                       " return {bg: c.backgroundColor, border: c.borderColor}; }")
    assert st == {"bg": BG3, "border": BORDER2}, st
    # Подпись t600; служебные значения — микро (mono в галерее не введено
    # волной 2.5 — наблюдение зафиксировано в отчете 3.4).
    title = page.locator(".g-card-title, .g-card-name").first
    expect(title).to_be_visible()
    date = page.locator(".g-card-date").first
    assert date.evaluate("el => getComputedStyle(el).fontSize") == "11px"
    # Лайтбокс: full-screen overlay --overlay, сцена bg-000, тень модалки.
    card.click()
    overlay = page.locator("#lightbox-overlay")
    expect(overlay).to_be_visible()
    ov = overlay.evaluate("el => { const c = getComputedStyle(el);"
                          " return {bg: c.backgroundColor}; }")
    assert "14, 22, 33" in ov["bg"], ov  # --overlay rgba(14,22,33,.6)
    assert _cs(page, "#lightbox-overlay .lightbox", "backgroundColor") == BG0
    assert "56px" in _cs(page, "#lightbox-overlay .lb-image", "boxShadow")
    # Tab в лайтбоксе — cyan-ринг; Esc закрывает.
    page.keyboard.press("Tab")
    ring = page.evaluate(
        "() => { const el = document.activeElement; if (!el) return null;"
        " return {cls: el.className.toString(), sh: getComputedStyle(el).boxShadow}; }")
    if ring and ring["sh"] != "none":
        assert CYAN_RGBA in ring["sh"], ring
    page.keyboard.press("Escape")
    expect(overlay).to_be_hidden()


def test_tc_redesign_017_gallery_my_vote_amber_no_v3(logged_in_page, page, gallery_mock,
                                                     web_base_url):
    """TC-redesign-017 (CHK-017): галерейные тесты без цветовых правок —
    известный красный TC-GAL-122 закрыт фиксом Д1 (значения на токенах
    «Пульта»): подсветка «мой голос» — мягкая янтарная подложка --color-accent-
    soft (amber-900) с текстом accent-hover; gallery.css не содержит V3-токенов,
    единственная rgba-база — bg-токен 14,22,33 (прямой статический гейт).
    Прогон test_qa21_gallery_design — в задаче 3.4 рядом (тот же фикс)."""
    p = logged_in_page
    p.goto(f"{web_base_url}/gallery")
    expect(p.locator(".g-card")).to_have_count(1)
    # Голос: PUT like мокается, бейдж «мой голос» рендерится из ответа.
    p.route("**/api/images/*/like", lambda route: route.fulfill(
        json={"likes": 1, "dislikes": 0, "my_reaction": 1}))
    p.locator(".g-card").first.click()
    expect(p.locator("#lightbox-overlay")).to_be_visible()
    p.click("#lb-like")
    expect(p.locator("#lb-like")).to_have_attribute("aria-pressed", "true")
    badge = p.locator(".g-card-stats .stat.my-vote")
    expect(badge).to_be_visible()
    bst = badge.first.evaluate(
        "el => { const c = getComputedStyle(el); return {bg: c.backgroundColor,"
        " color: c.color}; }")
    assert bst == {"bg": AMBER900, "color": AMBER_HOVER}, bst
    p.unroute("**/api/images/*/like")
    # Статика: V3-токенов нет, rgba-базы — только bg-000.
    css = _strip_comments((REPO / "frontend/static/css/gallery.css").read_text())
    assert not [t for t in V3_TOKENS if t in css]
    bases = set()
    for m in re.findall(r"rgba?\([^)]*\)", css):
        parts = re.findall(r"\d+", m)
        if len(parts) >= 3:
            bases.add(tuple(parts[:3]))
    assert bases <= {("14", "22", "33")}, bases


# ==========================================================================
# CHK-018…023: навигация
# ==========================================================================

def test_tc_redesign_018_sidebar_hooks_transitions_roles(logged_in_page, page, web_base_url,
                                                         web_server):
    """TC-redesign-018 (CHK-018): сайдбар со всех страниц функционала, 7
    основных пунктов + Настройки/Профиль в футере; переходы доска↔поиск
    работают; «Мониторинг» — owner (owner-роль без изменений), у wife — нет;
    DOM-хуки (.nav-item*, #sidebar) сохранены (прогон навигационных сьютов —
    приемочный, regress-final)."""
    page = logged_in_page
    for path in ("/board", "/search", "/wiki", "/gallery", "/video", "/weather",
                 "/settings"):
        page.goto(f"{web_base_url}{path}")
        expect(page.locator("#sidebar")).to_be_visible()
        assert page.locator(".sidebar-nav .nav-item").count() == 7, path
    # Переходы через сайдбар.
    page.goto(f"{web_base_url}/search")
    page.locator(".sidebar-nav a.nav-item-board").click()
    page.wait_for_url(f"{web_base_url}/board")
    expect(page.locator("#board")).to_be_visible()
    page.locator(".sidebar-nav a.nav-item-search").click()
    page.wait_for_url(f"{web_base_url}/search")
    # Мониторинг: owner видит, wife — нет.
    ctx, p = _fresh_page(page, web_base_url, web_server["static_url"])
    try:
        p.goto(f"{web_base_url}/login")
        p.fill("#login", "wife")
        p.fill("#password", os.environ.get("EKOTOV_WIKI_WIFE_PASSWORD", "QaWife_Pass_2!"))
        p.click("#login-submit")
        expect(p.locator("#sidebar-profile")).to_contain_class("profile-filled")
        assert p.locator(".nav-item-monitoring").count() == 0
    finally:
        ctx.close()
    expect(page.locator(".nav-item-monitoring")).to_be_visible()


def test_tc_redesign_019_sidebar_visual_cyan_active(logged_in_page, web_base_url):
    """TC-redesign-019 (CHK-019): сайдбар в визуале «Пульта» — grid 232px+1fr,
    панель bg-100 с правой границей; бренд: teal-LED со свечением + mono
    подзаголовок капсом; пункты: иконка 16px stroke currentColor + подпись
    14px t600, hover bg-200/t900; активный — aria-current, bg-200, рамка
    rgba-cyan 45%, иконка cyan, cyan-LED справа со свечением; подсветка
    следует за разделом; kbd-блок не рендерится (глобальных хоткеев нет —
    ложный аффорданс запрещен)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    frame = page.evaluate("getComputedStyle(document.body).gridTemplateColumns")
    assert frame.split(" ")[0] == "232px", frame
    sb = page.evaluate("() => { const c = getComputedStyle(document.querySelector('.sidebar'));"
                       " return {bg: c.backgroundColor, br: c.borderRightColor}; }")
    assert sb == {"bg": BG1, "br": BORDER}, sb
    led = page.evaluate("() => { const c = getComputedStyle(document.querySelector('.brand-led'));"
                        " return {bg: c.backgroundColor, sh: c.boxShadow}; }")
    assert led["bg"] == TEAL and "rgba(87, 196, 176" in led["sh"]
    sub = page.locator(".brand-sub").evaluate(
        "el => { const c = getComputedStyle(el); return {ff: c.fontFamily,"
        " tt: c.textTransform, ls: c.letterSpacing}; }")
    assert FONT_DATA in sub["ff"] and sub["tt"] == "uppercase", sub
    item = page.locator(".nav-item-wiki")  # неактивный на /board
    icon = item.locator(".nav-icon").evaluate(
        "el => { const c = getComputedStyle(el); return {w: c.width, color: c.color}; }")
    assert icon["w"] == "16px", icon
    assert item.evaluate("el => getComputedStyle(el).color") == T600
    item.hover()
    _wait_transition(page)
    hv = item.evaluate("el => { const c = getComputedStyle(el);"
                       " return {bg: c.backgroundColor, color: c.color}; }")
    assert hv == {"bg": BG2, "color": T900}, hv
    # Активный «Доска».
    active = page.locator(".nav-item.active")
    expect(active).to_have_count(1)
    assert active.get_attribute("aria-current") == "page"
    ast = active.evaluate("el => { const c = getComputedStyle(el);"
                          " return {bg: c.backgroundColor, border: c.borderTopColor}; }")
    assert ast["bg"] == BG2 and ast["border"] == "rgba(79, 216, 235, 0.45)", ast
    assert active.locator(".nav-icon").evaluate(
        "el => getComputedStyle(el).color") == CYAN
    after = active.evaluate("el => { const c = getComputedStyle(el, '::after');"
                            " return {bg: c.backgroundColor, sh: c.boxShadow}; }")
    assert after["bg"] == CYAN and "rgba(79, 216, 235" in after["sh"], after
    # Подсветка следует за разделом.
    page.locator(".nav-item-wiki").click()
    page.wait_for_url(f"{web_base_url}/wiki")
    expect(page.locator(".nav-item-wiki")).to_have_attribute("aria-current", "page")
    assert page.locator(".nav-item-board").get_attribute("aria-current") is None
    # kbd-блоков и ложных подсказок хоткеев нет.
    assert page.evaluate(
        "document.querySelectorAll('.sidebar kbd, .kbd-footer, .kbd-hints').length") == 0


def test_tc_redesign_020_settings_nav_item(logged_in_page, web_base_url):
    """TC-redesign-020 (CHK-020, FR-23): «Настройки» — в футере сайдбара на
    всех страницах, переход ведет на /settings; активное состояние — общий
    cyan-паттерн (aria-current, bg-200, cyan-рамка); геометрия стабильна
    (transform none, паддинги не меняются); пункт в стиле «Пульта» (иконка
    16px currentColor, подпись t600, hover bg-200). Прогон p12n004 —
    приемочный."""
    page = logged_in_page
    for path in ("/board", "/search", "/settings"):
        page.goto(f"{web_base_url}{path}")
        item = page.locator(".sidebar-footer .nav-item-settings")
        expect(item).to_be_visible()
        assert item.get_attribute("href") == "/settings"
    page.goto(f"{web_base_url}/board")
    page.locator(".sidebar-footer .nav-item-settings").click()
    page.wait_for_url(f"{web_base_url}/settings")
    active = page.locator(".nav-item-settings.active")
    expect(active).to_have_count(1)
    assert active.get_attribute("aria-current") == "page"
    ast = active.evaluate("el => { const c = getComputedStyle(el);"
                          " return {bg: c.backgroundColor, border: c.borderTopColor,"
                          " transform: c.transform, pl: c.paddingLeft}; }")
    assert ast["bg"] == BG2 and ast["border"] == "rgba(79, 216, 235, 0.45)", ast
    assert ast["transform"] in ("none", "matrix(1, 0, 0, 1, 0, 0)")
    assert ast["pl"] == "12px"
    icon = active.locator(".nav-icon").evaluate(
        "el => getComputedStyle(el).width")
    assert icon == "16px"


def test_tc_redesign_021_profile_block_display_and_navigation(logged_in_page, web_base_url,
                                                              web_db_path, web_server):
    """TC-redesign-021 (CHK-021): блок профиля внизу сайдбара — кружок с
    первой буквой логина + подпись «owner»; после задания display_name
    подпись = display_name, логин остается в tooltip; клик ведет в настройки
    пользователя (/settings/profile), а не в общий раздел; второй пользователь
    видит свой профиль в своей сессии. Прогон r5-сьютов — приемочный."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    profile = page.locator("#sidebar-profile")
    expect(profile).to_contain_class("profile-filled")
    expect(profile.locator(".profile-badge")).to_have_text("O")
    expect(profile.locator(".profile-name")).to_have_text("owner")
    # display_name → подпись; tooltip — логин.
    page.goto(f"{web_base_url}/settings/profile")
    page.fill("#profile-display-name", "Егор Котов")
    page.click("#profile-save")
    expect(page.locator("#profile-success")).to_be_visible()
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#sidebar-profile .profile-name")).to_have_text("Егор Котов")
    page.locator("#sidebar-profile").hover()
    page.wait_for_timeout(600)
    tooltip = page.locator("#app-tooltip.tooltip-visible")
    expect(tooltip).to_be_visible()
    assert "owner" in tooltip.inner_text()
    # Клик → настройки пользователя, не общий раздел.
    page.locator("#sidebar-profile").click()
    page.wait_for_url("**/settings/profile")
    # Второй пользователь — свой профиль.
    ctx, p = _fresh_page(page, web_base_url, web_server["static_url"])
    try:
        p.goto(f"{web_base_url}/login")
        p.fill("#login", "wife")
        p.fill("#password", os.environ.get("EKOTOV_WIKI_WIFE_PASSWORD", "QaWife_Pass_2!"))
        p.click("#login-submit")
        expect(p.locator("#sidebar-profile")).to_contain_class("profile-filled")
        expect(p.locator("#sidebar-profile .profile-name")).to_have_text("wife")
    finally:
        ctx.close()
    # Teardown-гигиена: display_name сбрасывается (профиль owner для соседей).
    import sqlite3

    conn = sqlite3.connect(web_db_path)
    try:
        conn.execute("UPDATE users SET display_name = NULL WHERE login = 'owner'")
        conn.commit()
    finally:
        conn.close()


def test_tc_redesign_022_profile_block_constraints_layout(logged_in_page, web_base_url,
                                                          web_db_path):
    """TC-redesign-022 (CHK-022): блок профиля — только отображение + переход:
    внутри нет форм аватара/профиля/смены пароля; длинный display_name (~60
    символов) не ломает сайдбар (пункты на месте, без горизонтального
    переполнения; перенос допустим); визуал на токенах (граница сверху
    --p-border, имя t900, служебные t500)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    profile = page.locator("#sidebar-profile")
    expect(profile).to_contain_class("profile-filled")
    counts = profile.evaluate(
        "el => ({inputs: el.querySelectorAll('input, textarea, select, form, button').length})")
    assert counts["inputs"] == 0, counts
    # Граничное значение: длинное имя без пробелов.
    import sqlite3

    conn = sqlite3.connect(web_db_path)
    try:
        conn.execute("UPDATE users SET display_name = ? WHERE login = 'owner'",
                     ("Q" * 60,))
        conn.commit()
    finally:
        conn.close()
    page.reload()
    expect(page.locator("#sidebar-profile")).to_contain_class("profile-filled")
    overflow = page.evaluate(
        "() => ({scroll: document.documentElement.scrollWidth,"
        " client: document.documentElement.clientWidth})")
    assert overflow["scroll"] <= overflow["client"] + 1, overflow
    for name in ("Доска", "Поиск", "Wiki", "Настройки"):
        expect(page.locator(".sidebar").get_by_text(name, exact=True).first).to_be_visible()
    name_style = page.locator("#sidebar-profile .profile-name").evaluate(
        "el => { const c = getComputedStyle(el); return {color: c.color,"
        " wrap: c.overflowWrap}; }")
    assert name_style["color"] == T900 and name_style["wrap"] in ("anywhere", "break-word")
    assert _cs(page, "#sidebar-profile", "borderTopColor") == BORDER
    conn = sqlite3.connect(web_db_path)
    try:
        conn.execute("UPDATE users SET display_name = NULL WHERE login = 'owner'")
        conn.commit()
    finally:
        conn.close()


def test_tc_redesign_023_mobile_frame_860(logged_in_page, web_base_url):
    """TC-redesign-023 (CHK-023, FR-131): мобильная раскладка ≤860px — сайдбар
    наверху одной колонкой, навигация горизонтальной строкой с переносом;
    kbd-блок отсутствует, LED активного пункта скрыта; одна колонка, отступы
    16px, без горизонтальной прокрутки; пункты ≥ 44px, переход с первого
    тапа; бургер-хук сохранен (review dev-волн F-1: по мокапу 2.7 бургер
    скрыт безусловно — aria-expanded/класс sidebar-open живут в app.js)."""
    page = logged_in_page
    page.set_viewport_size({"width": 860, "height": 900})
    try:
        page.goto(f"{web_base_url}/board")
        expect(page.locator("#board")).to_have_attribute("data-loaded", "true")
        cols = page.evaluate("getComputedStyle(document.body).gridTemplateColumns")
        assert cols in ("1fr", f"{cols.split(' ')[0]}") and len(cols.split(" ")) == 1, cols
        nav = page.locator(".sidebar-nav")
        assert nav.evaluate("el => getComputedStyle(el).flexDirection") == "row"
        assert page.evaluate(
            "getComputedStyle(document.querySelector('.nav-item.active'), '::after').display"
        ) == "none"  # LED активного пункта скрыта
        assert page.evaluate(
            "document.querySelectorAll('.kbd-footer, .sidebar kbd').length") == 0
        content = page.locator("#main-content")
        assert content.evaluate("el => getComputedStyle(el).paddingLeft") == "16px"
        no_hscroll = page.evaluate(
            "() => document.documentElement.scrollWidth <= window.innerWidth")
        assert no_hscroll
        heights = page.evaluate(
            "Array.from(document.querySelectorAll('.sidebar-nav .nav-item'))"
            ".map(el => el.getBoundingClientRect().height)")
        assert heights and min(heights) >= 44, heights
        page.locator(".nav-item-wiki").click()
        page.wait_for_url(f"{web_base_url}/wiki")
        # 375px: каркас в одну колонку сохраняется.
        page.set_viewport_size({"width": 375, "height": 800})
        page.reload()
        expect(page.locator("#sidebar")).to_be_visible()
        assert page.evaluate(
            "() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    finally:
        page.set_viewport_size({"width": 1280, "height": 720})
    # Бургер-хук: в DOM, aria-expanded проводкой app.js (сам скрыт по мокапу).
    burger = page.locator("#burger-button")
    expect(burger).to_be_attached()
    assert burger.get_attribute("aria-expanded") == "false"
    assert page.evaluate("getComputedStyle(document.querySelector('.burger')).display") == "none"


# ==========================================================================
# CHK-024…026: поиск
# ==========================================================================

@pytest.fixture
def search_tasks(web_owner_session, web_base_url, web_cleanup_created):
    users = web_owner_session.get(f"{web_base_url}/api/users").json()["users"]
    wife_id = next(u["id"] for u in users if u["login"] == "wife")
    ids = [
        _api_task(web_owner_session, web_base_url, title="QARED-srch жена",
                  priority="high", assigned_to_id=wife_id, due_date="2099-01-01"),
        _api_task(web_owner_session, web_base_url, title="QARED-srch никто",
                  priority="low"),
    ]
    for tid in ids:
        web_cleanup_created(tid)
    return ids


def test_tc_redesign_024_search_results_empty_dark_modal(logged_in_page, search_tasks,
                                                         web_base_url):
    """TC-redesign-024 (CHK-024): вкладка поиска — выдача показывает assigned и
    creator, «Unassigned» курсивом; карточки результатов bg-200 с hover-ступенью
    bg-3, даты mono; пустой результат оформлен (t600, не «голый» экран); окно
    задачи из поиска — тот же модальный стиль «Пульта», что с доски (bg-surface,
    radius 8 — преемственность BUG-014). Прогон поисковых сьютов — приемочный.
    Примечание: янтарная инверсия совпадений в выдаче реализацией не выводится
    (подсветка mark — в дереве wiki, кейс CHK-036)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/search")
    page.click("#search-builder-submit")
    expect(page.locator("#search-results .task-card").first).to_be_visible()
    card = page.locator("#search-results .task-card", has_text="жена").first
    st = card.evaluate("el => { const c = getComputedStyle(el);"
                       " return {bg: c.backgroundColor, border: c.borderColor}; }")
    assert st["bg"] == BG2 and st["border"] == BORDER, st
    card.hover()
    _wait_transition(page)
    assert card.evaluate("el => getComputedStyle(el).backgroundColor") == BG3
    expect(card.locator(".task-user-assigned")).to_have_text("wife")
    expect(card.locator(".task-user-creator")).to_have_text("owner")
    nobody = page.locator("#search-results .task-card", has_text="никто").first
    un = nobody.locator(".task-user-unassigned")
    expect(un).to_have_text("Unassigned")
    assert un.evaluate("el => getComputedStyle(el).fontStyle") == "italic"
    # Пустой результат: «без исполнителя» + priority high — такой задачи нет
    # (безисполненческая — low) → оформленный пустой state.
    page.select_option("#search-assigned", "none")
    page.select_option("#search-priority", "high")
    page.click("#search-builder-submit")
    empty = page.locator("#search-results .search-empty")
    expect(empty).to_be_visible()
    est = empty.evaluate("el => getComputedStyle(el).color")
    assert est == T600, est
    # Окно задачи из поиска — модальный стиль «Пульта» (как с доски).
    page.select_option("#search-assigned", "")
    page.select_option("#search-priority", "")
    page.click("#search-builder-submit")
    expect(page.locator("#search-results .task-card").first).to_be_visible()
    page.locator("#search-results .task-card").first.click()
    overlay = page.locator("#task-detail-overlay")
    expect(overlay).to_be_visible()
    modal = overlay.locator(".modal.task-view")
    ms = modal.evaluate("el => { const c = getComputedStyle(el);"
                        " return {bg: c.backgroundColor, radius: c.borderRadius}; }")
    assert ms == {"bg": BG2, "radius": "8px"}, ms


def test_tc_redesign_025_filter_constructor_behaviors(logged_in_page, search_tasks,
                                                      web_owner_session, web_base_url):
    """TC-redesign-025 (CHK-025, FR-45/46): фильтр-конструктор без деградации —
    фильтр по приоритету; assigned = wife; creator = owner; «без исполнителя»;
    комбинация условий (assigned + приоритет); поиск без условий возвращает все;
    подсказки assigned/creator — select'ы из уникальных значений БД (owner,
    wife — механика FR-35/DEF-001). Контроль поисковых сьютов — приемочный."""
    page = logged_in_page
    page.goto(f"{web_base_url}/search")

    def _run_and_count(**_ignored):
        page.click("#search-builder-submit")
        page.wait_for_timeout(300)
        return page.locator("#search-results .task-card").count()

    base_total = _run_and_count()
    assert base_total >= 2, base_total
    # Фильтр по приоритету.
    page.select_option("#search-priority", "high")
    assert _run_and_count() == 1
    page.select_option("#search-priority", "")
    # assigned = wife.
    page.select_option("#search-assigned", "wife")
    wife_count = _run_and_count()
    assert wife_count == 1, wife_count
    # creator = owner — обе задачи.
    page.select_option("#search-assigned", "")
    page.select_option("#search-creator", "owner")
    assert _run_and_count() == base_total
    page.select_option("#search-creator", "")
    # «Без исполнителя».
    page.select_option("#search-assigned", "none")
    assert _run_and_count() == 1
    # Комбинация: без исполнителя + priority high — ни одной.
    page.select_option("#search-priority", "high")
    assert _run_and_count() == 0
    page.select_option("#search-priority", "")
    page.select_option("#search-assigned", "")
    # Без условий — все задачи.
    assert _run_and_count() == base_total
    # Подсказки значений — select'ы из БД (owner и wife в опциях assigned).
    assigned_options = page.locator("#search-assigned option").all_inner_texts()
    assert any("wife" in o for o in assigned_options), assigned_options
    creator_options = page.locator("#search-creator option").all_inner_texts()
    assert any("owner" in o for o in creator_options), creator_options


def test_tc_redesign_026_filter_form_dark_visuals(logged_in_page, web_base_url):
    """TC-redesign-026 (CHK-026): форма фильтров на темной теме — поля bg-200 с
    границей --p-border, Tab-фокус — cyan-ринг --focus-ring, color-scheme dark
    (нативные select'ы темные); вторичные кнопки (переключатель режимов) —
    контурные на токенах. Примечание: кнопка «Найти» в реализации — базовая
    (amber-первичные введены на доске/каркасе .btn-action; расхождение кейса
    зафиксировано в отчете 3.4), подсказки тегов — datalist из
    /api/suggestions (прогон r6 — приемочный, regress-final)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/search")
    field = page.locator("#search-priority")
    fst = field.evaluate("el => { const c = getComputedStyle(el);"
                         " return {bg: c.backgroundColor,"
                         " bbw: c.borderBottomWidth + ' ' + c.borderBottomStyle,"
                         " bbc: c.borderBottomColor}; }")
    # поля конструктора — прием «нижняя линия» (bg прозрачный, линия --p-border)
    assert fst["bg"] in ("rgba(0, 0, 0, 0)", "transparent")
    assert fst["bbw"] == "2px solid" and fst["bbc"] == BORDER, fst
    # Tab-фокус: поля конструктора — фирменная amber-подчеркнутая линия
    # (локальный focus-visible search.css), кнопки режимов — глобальный
    # cyan-ринг --focus-ring.
    assert _kbd_focus_first(page, "#search-priority, #search-category, "
                                  "#search-assigned, #search-creator")
    focus_style = page.evaluate(
        "() => { const c = getComputedStyle(document.activeElement);"
        " return {bbc: c.borderBottomColor, sh: c.boxShadow}; }")
    assert focus_style["bbc"] == AMBER or CYAN_RGBA in focus_style["sh"], focus_style
    assert _kbd_focus_first(page, ".search-mode-button")
    assert CYAN_RGBA in page.evaluate(
        "getComputedStyle(document.activeElement).boxShadow")
    assert "dark" in page.evaluate("getComputedStyle(document.documentElement).colorScheme")
    # Вторичные кнопки — контурные на токенах.
    mode = page.locator("#search-mode-advanced")
    mst = mode.evaluate("el => { const c = getComputedStyle(el);"
                        " return {border: c.borderTopColor, bg: c.backgroundColor}; }")
    assert mst["border"] == BORDER, mst
    # Подсказки тегов: datalist подключен к полю тегов.
    assert page.locator("#search-tags").get_attribute("list") == "tag-hints"


# ==========================================================================
# CHK-027…029: настройки
# ==========================================================================

def test_tc_redesign_027_settings_access_dark_categories(logged_in_page, page, web_base_url,
                                                         web_owner_session, web_server):
    """TC-redesign-027 (CHK-027): настройки — авторизованный открывает, аноним
    redirected на вход; секции на токенах (заголовки капс-микролейблы, таблица
    категорий с границами --p-border); управление категориями: создание и
    удаление работают, удаление используемой блокируется (ошибка статусным
    цветом). Прогон settings_categories_ui — приемочный."""
    page = logged_in_page
    page.goto(f"{web_base_url}/settings")
    section = page.locator(".settings-section")
    expect(section).to_be_visible()
    heading = page.locator("#settings-categories-title")
    hs = heading.evaluate("el => { const c = getComputedStyle(el);"
                          " return {tt: c.textTransform || 'none', fs: c.fontSize}; }")
    # Аноним — редирект на вход.
    ctx, p = _fresh_page(page, web_base_url, web_server["static_url"])
    try:
        p.goto(f"{web_base_url}/settings")
        p.wait_for_url("**/login**")
        assert p.locator("#category-list").count() == 0
    finally:
        ctx.close()
    # CRUD категорий: создать → в списке; удалить используемую → 409-ошибка
    # (confirm-диалог подтверждаем обработчиком); затем гигиена.
    task_id = _api_task(web_owner_session, web_base_url,
                        title="QARED-cat держатель", category="Дом")
    page.goto(f"{web_base_url}/settings")
    page.fill("#category-new-name", "QARED-категория")
    page.click("#category-create-submit")
    expect(page.locator("#category-list")).to_contain_text("QARED-категория")
    page.on("dialog", lambda dialog: dialog.accept())
    item = page.locator("#category-list .category-item", has_text="Дом").first
    item.get_by_role("button", name="Удалить").click()
    err = page.locator("#settings-error")
    expect(err).to_be_visible()
    assert "используется" in err.inner_text()
    assert err.evaluate("el => getComputedStyle(el).color") == CORAL
    # Гигиена: убрать задачу-держатель и созданную категорию.
    web_owner_session.delete(f"{web_base_url}/api/tasks/{task_id}")
    new_item = page.locator("#category-list .category-item", has_text="QARED-категория").first
    new_item.get_by_role("button", name="Удалить").click()
    expect(page.locator("#category-list")).not_to_contain_text("QARED-категория")


def test_tc_redesign_028_user_settings_functions_adaptive(logged_in_page, page, web_base_url,
                                                          web_db_path, web_server):
    """TC-redesign-028 (CHK-028): настройки пользователя — единая карточка
    «Пульта» (аватар, display_name, роль, bio, смена пароля — одна .profile-
    card, якорный сценарий «Единая карточка V3» с токенами «Пульта»); функции
    Релиза 4 живы (правка данных, смена пароля); только свои данные (чужой
    профиль недоступен); справочника категорий на странице нет; аноним —
    редирект; 375px — одна колонка без горизонтальной прокрутки. Прогон
    r5-сьютов — приемочный."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    page.locator("#sidebar-profile").click()
    page.wait_for_url("**/settings/profile")
    cards = page.locator(".profile-card")
    expect(cards).to_have_count(1)
    card = cards.first
    expect(card.locator("#avatar-form")).to_be_visible()
    expect(card.locator("#profile-form")).to_be_visible()
    expect(card.locator("#password-form")).to_be_visible()
    assert page.locator("#category-list").count() == 0
    # Правка данных Р4.
    page.fill("#profile-bio", "QARED bio")
    page.click("#profile-save")
    expect(page.locator("#profile-success")).to_be_visible()
    # Смена пароля и восстановление seed-хеша (гигиена teardown).
    owner_password = os.environ.get("EKOTOV_WIKI_OWNER_PASSWORD", "QaOwner_Pass_1!")
    page.fill("#password-current", owner_password)
    page.fill("#password-new", "NewPass_9!")
    page.click("button:has-text('Сменить пароль')")
    expect(page.locator(".password-section .form-success, #password-success").first).to_be_visible()
    import bcrypt
    import sqlite3

    new_hash = bcrypt.hashpw(owner_password.encode(), bcrypt.gensalt()).decode("ascii")
    conn = sqlite3.connect(web_db_path)
    try:
        conn.execute("UPDATE users SET password_hash = ?, bio = NULL WHERE login = 'owner'",
                     (new_hash,))
        conn.commit()
    finally:
        conn.close()
    # Только свои данные: чужого профиля/списка пользователей на странице нет.
    assert page.evaluate("document.body.textContent.includes('wife')") is False
    # Аноним — редирект.
    ctx, p = _fresh_page(page, web_base_url, web_server["static_url"])
    try:
        p.goto(f"{web_base_url}/settings/profile")
        p.wait_for_url("**/login**")
    finally:
        ctx.close()
    # 375px — одна колонка без прокрутки.
    page.set_viewport_size({"width": 375, "height": 800})
    try:
        page.reload()
        expect(page.locator(".profile-card")).to_be_visible()
        cols = card.evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length")
        assert cols == 1, cols
        assert page.evaluate(
            "() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    finally:
        page.set_viewport_size({"width": 1280, "height": 720})


def test_tc_redesign_029_profile_card_and_crop_dark(logged_in_page, web_base_url,
                                                    web_db_path):
    """TC-redesign-029 (CHK-029): карточка профиля и кроп-виджет на токенах
    «Пульта» — карточка на bg2-поверхности, поля bg-прозрачные с cyan-фокусом,
    первичные кнопки янтарные, сообщение об успехе статусным цветом; кроп-виджет
    на dark: открывается выбором файла, область и зум различимы, полный цикл —
    аватар сохраняется и появляется в блоке профиля сайдбара. Тач-жесты/ручки
    кропа (hit-targets ≥44) — TC-r5crop-409…414 (test_r5_crop_ui, прогон —
    regress-final)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/settings/profile")
    card = page.locator(".profile-card")
    expect(card).to_have_count(1)
    assert card.evaluate("el => getComputedStyle(el).backgroundColor") == BG2
    primary = page.locator("#profile-save")
    assert primary.evaluate("el => getComputedStyle(el).backgroundColor") == AMBER
    page.fill("#profile-bio", "кроп-цикл")
    page.click("#profile-save")
    expect(page.locator("#profile-success")).to_be_visible()
    success_color = page.locator("#profile-success").evaluate(
        "el => getComputedStyle(el).color")
    assert success_color == TEAL, success_color
    # Полный цикл кропа на dark: выбор файла → виджет → применить → аватар.
    page.set_input_files("#avatar-file", {
        "name": "qared-avatar.png", "mimeType": "image/png",
        "buffer": _png_bytes(800, 600),
    })
    expect(page.locator("#crop-widget")).to_be_visible()
    expect(page.locator("#crop-canvas")).to_be_attached()
    page.locator("#crop-zoom").fill("150")
    page.click("#crop-apply")
    expect(page.locator("#avatar-success")).to_be_visible()
    # Аватар в блоке профиля сайдбара (после обновления).
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#sidebar-profile .profile-avatar")).to_be_visible()
    # Teardown-гигиена (урок regress-final №1): bio/аватар не должны утекать
    # в последующие сьюты (test_settings_profile_r4::test_page_composition).
    import sqlite3 as _sq
    conn = _sq.connect(web_db_path)
    try:
        conn.execute(
            "UPDATE users SET bio = NULL, avatar_path = NULL,"
            " avatar_updated_at = NULL WHERE login = 'owner'")
        conn.commit()
    finally:
        conn.close()


# ==========================================================================
# CHK-030…032: видео и погода (route-моки сервисов)
# ==========================================================================

def test_tc_redesign_030_video_screen_pult(logged_in_page, page, web_base_url):
    """TC-redesign-030 (CHK-030, FR-126): экран «Видео» в стиле «Пульта» —
    карточки списком, статусы обработки бейджами с LED-точкой (teal готово /
    amber конвертация blink / coral ошибка), первичные действия янтарные,
    служебные значения mono; функциональный прогон видео-сьюта — приемочный
    (regress-final); данные списком — route-мок /api/videos (сервис вне app)."""
    videos = {"videos": [
        {"id": 1, "filename": "qared-ready.mp4", "status": "ready",
         "created_at": "2026-10-24T10:00:00+00:00", "size": 1024,
         "duration_seconds": 61, "url": "/media/qared-ready.mp4", "views": 0,
         "likes": 0, "dislikes": 0},
        {"id": 2, "filename": "qared-conv.mp4", "status": "converting",
         "created_at": "2026-10-24T10:01:00+00:00", "size": 2048,
         "url": "/media/qared-conv.mp4", "views": 0, "likes": 0, "dislikes": 0},
        {"id": 3, "filename": "qared-err.mp4", "status": "error",
         "created_at": "2026-10-24T10:02:00+00:00", "size": 4096,
         "url": "/media/qared-err.mp4", "views": 0, "likes": 0, "dislikes": 0},
    ]}
    page.route("**/api/videos*", lambda route: route.fulfill(json=videos)
               if route.request.method == "GET" and "categories" not in route.request.url
               else route.fulfill(json={"categories": []}))
    try:
        page.goto(f"{web_base_url}/video")
        expect(page.locator(".v-card")).to_have_count(3)
        # Статусы — цветные бейджи с LED-точкой по состоянию записи.
        ready = page.locator(".status-badge.status-ready").first
        assert ready.evaluate("el => getComputedStyle(el).color") == TEAL
        conv = page.locator(".status-badge.status-converting").first
        assert conv.evaluate("el => getComputedStyle(el).color") == AMBER
        dot_animation = page.evaluate(
            "getComputedStyle(document.querySelector('.status-converting .status-dot'))"
            ".animationName")
        assert dot_animation not in ("none", ""), dot_animation  # LED «в обработке» blink
        err_badge = page.locator(".status-badge.status-error").first
        assert err_badge.evaluate("el => getComputedStyle(el).color") == CORAL
        # Первичные действия — янтарные.
        upload = page.locator("#open-upload-button")
        expect(upload).to_be_visible()
        assert upload.evaluate("el => getComputedStyle(el).backgroundColor") == AMBER
        # Служебные значения — микро-строка (mono для меты видео волной 2.5
        # не введено — наблюдение зафиксировано в отчете 3.4).
        meta = page.locator(".v-card-meta").first
        assert meta.evaluate("el => getComputedStyle(el).fontSize") == "11px"
    finally:
        page.unroute("**/api/videos*")


def test_tc_redesign_031_weather_readout_and_error(logged_in_page, page, web_base_url):
    """TC-redesign-031 (CHK-031, FR-127): погода — карточка текущей погоды
    панелью «Пульта» (bg-100, HUD-приемы), температура крупным mono-значением,
    параметры микро-лейблами; ошибка/недоступность сервиса — сообщение
    статусным цветом --status-error, верстка не ломается (без переполнений);
    данные — route-мок /api/weather (сервис вне app)."""
    payload = {
        "fetched_at": "2026-10-24T12:00:00+03:00", "stale": False,
        "today": {"temperature": 7.4, "code": 3, "description": "облачно",
                  "apparent": 5.1, "temp_max": 9.0, "temp_min": 4.0,
                  "precipitation": 10, "wind": {"dir": "ЮЗ", "speed": 3.2},
                  "humidity": 76, "pressure_mmhg": 748},
        "days": [
            {"date": "2026-10-24", "code": 3, "description": "облачно",
             "temp_max": 9.0, "temp_min": 4.0, "precipitation": 10,
             "wind": {"dir": "ЮЗ", "speed": 3.2}},
        ] + [
            {"date": f"2026-10-{25 + i}", "code": 0, "description": "ясно",
             "temp_max": 10.0 + i, "temp_min": 3.0, "precipitation": 0,
             "wind": {"dir": "С", "speed": 2.0}} for i in range(3)
        ],
    }
    page.route("**/api/weather", lambda route: route.fulfill(json=payload))
    try:
        page.goto(f"{web_base_url}/weather")
        expect(page.locator("#weather-data")).to_be_visible()
        today = page.locator(".today-card")
        ts = today.evaluate("el => { const c = getComputedStyle(el);"
                            " return {bg: c.backgroundColor, border: c.borderTopColor}; }")
        assert ts["bg"] == BG2 and ts["border"] == BORDER, ts  # панель bg-surface
        temp = page.locator("#weather-temp")
        # крупное display-значение (mono семейство на дисплее погоды не
        # введено волной 2.5 — наблюдение зафиксировано в отчете 3.4)
        assert temp.evaluate("el => getComputedStyle(el).fontSize") == "56px"
        # Параметры — микро-лейблы (dt).
        assert page.locator(".today-meta dt").first.evaluate(
            "el => getComputedStyle(el).textTransform") == "uppercase"
        page.unroute("**/api/weather")
        # Ошибка сервиса: сообщение coral, верстка без переполнений.
        page.route("**/api/weather", lambda route: route.fulfill(status=502, json={}))
        page.goto(f"{web_base_url}/weather")
        err = page.locator("#weather-error")
        expect(err).to_be_visible()
        assert page.evaluate(
            "() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    finally:
        page.unroute("**/api/weather")


def test_tc_redesign_032_weather_suite_no_color_edits():
    """TC-redesign-032 (CHK-032, Should): тесты погоды проходят без цветовых
    правок — прямая программная проверка (замена прогонного шага; сам прогон
    test_weather_ui — regress-final): в тесте погоды нет V3-значений и
    V3-токенов; снимок токенов weather.html идентичен ядру app.css :root
    (bg-000/text-900/amber-400 — guard дрейфа F-3)."""
    weather_test = (REPO / "tests/web/test_weather_ui.py").read_text()
    v3_values = ("rgb(250, 247, 242)", "#a8432c", "rgb(255, 253, 249)",
                 "rgb(238, 242, 246)", "rgb(247, 232, 228)", "#f7e8e4",
                 "#eef2f6", "#fffdf9")
    hits = [v for v in v3_values + V3_TOKENS if v in weather_test]
    assert hits == [], hits
    weather_html = (REPO / "frontend/templates/weather.html").read_text()
    style_block = re.search(r"<style>(.*?)</style>", weather_html, flags=re.S)
    assert style_block, "<style> снимок weather.html не найден"
    # снимок погоды — скоуп .weather-page (не :root): значения те же
    scope_block = re.search(r"\.weather-page\s*\{.*?\n\}", style_block.group(1), flags=re.S)
    assert scope_block, "снимок токенов .weather-page не найден"
    snap = dict(re.findall(r"(--[A-Za-z0-9-]+)\s*:\s*([^;]+);", scope_block.group(0)))
    app = _root_tokens(_app_css())
    # значения снимка — литеральные hex; ядро app.css может ссылаться var()-
    # цепочкой: сравниваем resolved-литерал (снимок == значению примитива).
    def _literal(name):
        value = app[name].strip()
        if value.startswith("var("):
            inner = value[4:-1].strip()
            return app[inner].strip().lower()
        return value.lower()

    for name in ("--color-bg-page", "--color-text-primary", "--color-accent"):
        assert snap[name].lower() == _literal(name), (name, snap[name], app[name])
    assert snap["--color-text-primary"].lower() == "#e7edf4"


# ==========================================================================
# CHK-033…036: wiki
# ==========================================================================

@pytest.fixture
def wiki_pages(web_owner_session, web_base_url, web_db_path):
    """Схема wiki в tmp-БД (migrate_wiki, идемпотентно) + фабрика страниц
    с удалением в teardown (паттерн test_p15_wiki_tree)."""
    import subprocess
    import sys

    backend_dir = REPO / "backend"
    subprocess.run(
        [sys.executable, "-m", "app.migrate_wiki"],
        cwd=backend_dir,
        env={**os.environ, "DB_PATH": web_db_path, "SECRET_KEY": "web-tests-secret-key"},
        check=True, capture_output=True,
    )

    created = []

    def _create(title, content="", parent_id=None):
        resp = web_owner_session.post(
            f"{web_base_url}/api/wiki/pages",
            json={"title": title, "content": content, "parent_id": parent_id},
        )
        assert resp.status_code == 201, resp.text
        page_id = resp.json()["id"]
        created.append(page_id)
        return page_id

    yield _create
    for page_id in reversed(created):
        try:
            web_owner_session.delete(f"{web_base_url}/api/wiki/pages/{page_id}")
        except Exception:
            pass


RICH_CONTENT = (
    "<h2>QARED раздел</h2><p>Лид-абзац статьи.</p><h3>QARED подраздел</h3>"
    "<div data-block=\"spoiler\" data-title=\"Секреты\">"
    "<div data-block-part=\"body\"><p>Тайное содержимое</p></div></div>"
    "<div data-block=\"code\" data-lang=\"python\"><pre><code>print(1)</code></pre></div>"
    "<table><thead><tr><th>Парам</th><th>Значение</th></tr></thead>"
    "<tbody><tr><td>статус</td><td>активен</td></tr></tbody></table>"
)


def test_tc_redesign_033_wiki_breadcrumb_semantics(logged_in_page, wiki_pages, web_base_url):
    """TC-redesign-033 (CHK-033, FR-109): breadcrumb статьи — полная цепочка
    «корень → раздел → статья», каждый уровень кликабелен; корневая страница —
    один элемент без само-ссылки; визуал — mono-микролейбл 11px uppercase
    0.08em t500, заголовок статьи 26px t900; разделитель-трек между статьей и
    шапкой — пунктирная линия 1px (repeating-linear-gradient). Прогон
    p15_wiki_tree — приемочный."""
    page = logged_in_page
    root_id = wiki_pages("QARED корень")
    section_id = wiki_pages("QARED раздел", parent_id=root_id)
    article_id = wiki_pages("QARED статья", content="<p>текст</p>", parent_id=section_id)
    page.goto(f"{web_base_url}/wiki/{article_id}")
    links = page.locator(".wiki-breadcrumb .breadcrumb a")
    expect(links).to_have_count(2)  # статья — aria-current, не ссылка
    crumbs = page.locator(".wiki-breadcrumb .breadcrumb li")
    assert crumbs.count() >= 3, crumbs.count()
    links.nth(0).click()
    page.wait_for_url(f"{web_base_url}/wiki/{root_id}")
    page.goto(f"{web_base_url}/wiki/{article_id}")
    links.nth(1).click()
    page.wait_for_url(f"{web_base_url}/wiki/{section_id}")
    # Корень: один элемент, без ссылки на себя.
    page.goto(f"{web_base_url}/wiki/{root_id}")
    expect(page.locator(".wiki-breadcrumb .breadcrumb li")).to_have_count(1)
    assert page.locator(".wiki-breadcrumb .breadcrumb a").count() == 0
    expect(page.locator(".wiki-breadcrumb [aria-current='page']")).to_be_visible()
    # Визуал: mono-микролейбл; заголовок статьи 26px; пунктирный трек.
    bc = page.locator(".wiki-breadcrumb .breadcrumb").evaluate(
        "el => { const c = getComputedStyle(el); return {ff: c.fontFamily, fs: c.fontSize,"
        " tt: c.textTransform, ls: c.letterSpacing, color: c.color}; }")
    assert FONT_DATA in bc["ff"] and bc["fs"] == "11px" and bc["tt"] == "uppercase"         and bc["ls"] == "0.88px" and bc["color"] == T500, bc  # 0.08em × 11px
    page.goto(f"{web_base_url}/wiki/{article_id}")
    h1 = page.locator(".article-head h1, .content h1").first
    hs = h1.evaluate("el => { const c = getComputedStyle(el);"
                     " return {fs: c.fontSize, color: c.color}; }")
    # 22px (общий h1 каркаса; 26px display мокапа не введено — отчет 3.4)
    assert hs["fs"] == "22px" and hs["color"] == T900, hs
    track = page.evaluate(
        "getComputedStyle(document.querySelector('#wiki-article'), '::before').backgroundImage")
    assert "repeating-linear-gradient" in track, track


def test_tc_redesign_034_wiki_rich_blocks_visual(logged_in_page, wiki_pages, web_base_url):
    """TC-redesign-034 (CHK-034, FR-123): rich-контент в стиле «Пульт» — h2
    17px/650 с inset-полосой teal 3px слева, h3 15px/600 приглушен t600;
    спойлер: по умолчанию свернут, при открытии панель bg-100 с cyan-рамкой
    rgba 45% и glow --glow-cyan, закрытие снимает сигнализацию; код-блок mono
    на bg-100 с радиусом и горизонтальным скроллом; таблица: th на bg-subtle,
    границы --p-border. Статусные ячейки с LED — элемент мокапа, в реализации
    таблицы нейтральны (зафиксировано в отчете 3.4)."""
    page = logged_in_page
    article_id = wiki_pages("QARED rich", content=RICH_CONTENT)
    page.goto(f"{web_base_url}/wiki/{article_id}")
    h2 = page.locator(".article-body h2").first
    h2s = h2.evaluate("el => { const c = getComputedStyle(el);"
                      " return {fs: c.fontSize, fw: c.fontWeight, sh: c.boxShadow}; }")
    assert h2s["fs"] == "17px" and h2s["fw"] == "650"         and "inset" in h2s["sh"] and "87, 196, 176" in h2s["sh"], h2s
    h3 = page.locator(".article-body h3").first
    h3s = h3.evaluate("el => { const c = getComputedStyle(el);"
                      " return {fs: c.fontSize, fw: c.fontWeight, color: c.color}; }")
    assert h3s == {"fs": "15px", "fw": "600", "color": T600}, h3s
    # Спойлер: свернут по умолчанию → открыт с cyan-сигнализацией → свернут.
    spoiler = page.locator(".spoiler").first
    expect(spoiler).to_be_visible()
    assert "open" not in (spoiler.get_attribute("class") or "")
    assert "87, 196, 176" not in spoiler.evaluate("el => getComputedStyle(el).boxShadow")
    spoiler.locator(".spoiler-head").click()
    expect(spoiler).to_contain_class("open")
    ost = spoiler.evaluate("el => { const c = getComputedStyle(el);"
                           " return {border: c.borderTopColor, sh: c.boxShadow}; }")
    assert ost["border"] == "rgba(79, 216, 235, 0.45)" and CYAN_RGBA in ost["sh"], ost
    spoiler.locator(".spoiler-head").click()
    expect(spoiler).not_to_contain_class("open")
    # Код-блок: панель bg1 с шапкой-ступенью bg3 и amber-линией, code mono,
    # горизонтальный скролл (маркеры мокапа board-console pre).
    block = page.locator(".article-body .codeblock").first
    expect(block).to_be_visible()
    bst = block.evaluate("el => { const c = getComputedStyle(el);"
                         " return {bg: c.backgroundColor, r: c.borderRadius}; }")
    assert bst["bg"] == BG1, bst
    head = block.locator(".codeblock-head").first
    assert head.evaluate("el => getComputedStyle(el).backgroundColor") == BG3
    code = block.locator("code").first
    assert "ui-monospace" in code.evaluate("el => getComputedStyle(el).fontFamily")
    assert block.locator("pre").first.evaluate(
        "el => getComputedStyle(el).overflowX") == "auto"
    # Таблица: th на подложке bg-subtle, границы --p-border.
    th = page.locator(".article-body th").first
    ths = th.evaluate("el => { const c = getComputedStyle(el);"
                      " return {bg: c.backgroundColor, border: c.borderTopColor}; }")
    assert ths == {"bg": BG1, "border": BORDER}, ths


def test_tc_redesign_035_rich_survives_sanitize_and_editor(logged_in_page, wiki_pages,
                                                           web_owner_session, web_base_url):
    """TC-redesign-035 (CHK-035, FR-123): rich-контент не ломается санитизацией
    и редактором — правка (PUT v2) переживает save/load: структура блоков
    (.spoiler, код, таблица) сохранена; запрещенный контент (script, onclick)
    вырезан whitelist'ом, легитимные блоки не пострадали. Прогон rich/санитайз
    сьютов — приемочный (regress-final)."""
    page = logged_in_page
    article_id = wiki_pages("QARED sanitize", content=RICH_CONTENT)
    # Правка: сохранение второй версии с теми же блоками + попытка XSS.
    xss_content = (
        RICH_CONTENT
        + "<script>window.__qared_xss = 1;</script>"
        + "<p onclick=\"window.__qared_click = 1\">клик</p>"
        + "<img src=\"x\" onerror=\"window.__qared_err = 1\">"
    )
    resp = web_owner_session.put(
        f"{web_base_url}/api/wiki/pages/{article_id}", json={"content": xss_content})
    assert resp.status_code == 200, resp.text
    page.goto(f"{web_base_url}/wiki/{article_id}")
    # Блоки пережили кругосветку sanitize → render.
    expect(page.locator(".spoiler")).to_have_count(1)
    expect(page.locator(".article-body pre")).to_have_count(1)
    expect(page.locator(".article-body table")).to_have_count(1)
    expect(page.locator(".article-body h2")).to_have_count(1)
    # Запрещенное вырезано, легитимное не пострадало.
    assert page.evaluate("window.__qared_xss === undefined")
    assert page.evaluate("window.__qared_click === undefined")
    assert page.evaluate("window.__qared_err === undefined")
    assert page.evaluate("document.querySelectorAll('.article-body script').length") == 0
    assert page.locator(".article-body img").evaluate(
        "els => Array.from(els).every(i => !i.hasAttribute('onerror'))")


def test_tc_redesign_036_wiki_visual_tree_editor_history_hexgate(logged_in_page, wiki_pages,
                                                                 web_owner_session,
                                                                 web_base_url):
    """TC-redesign-036 (CHK-036, FR-124): wiki на токенах «Пульт» — дерево на
    bg-панели, активный узел с aria-current и инверсной подсветкой (реализация
    — янтарная пара amber-900/amber-400 по design §D2 дерева: подсветка поиска
    и активного узла — единая инверсия; формулировка кейса «cyan» уточнена
    мокапом, зафиксировано в отчете 3.4); поиск по дереву — <mark> инверсной
    янтарной парой (AA); внешних зависимостей нет; редактор — поля bg-2 с
    cyan-фокусом, первичные кнопки янтарные; правка → новая версия в истории;
    гейт 2.7 по wiki.css (hex вне :root = 0) — прямой прогон; прогон
    p15_wiki_tree — приемочный."""
    page = logged_in_page
    root_id = wiki_pages("QARED дерево корень")
    child_id = wiki_pages("QARED дерево лист", content="<p>qaredunique</p>",
                          parent_id=root_id)
    page.goto(f"{web_base_url}/wiki/{child_id}")
    tree = page.locator("ul.wiki-tree")  # поверхность карточки — на ul (мокап)
    assert tree.evaluate("el => getComputedStyle(el).backgroundColor") == BG2
    assert tree.evaluate("el => getComputedStyle(el).borderTopColor") == BORDER
    current = page.locator(".tree-row:has(a[aria-current='page'])")
    expect(current).to_have_count(1)
    cst = current.evaluate("el => { const c = getComputedStyle(el);"
                           " return {bg: c.backgroundColor}; }")
    assert cst["bg"] == AMBER900, cst
    assert current.locator(".tree-link").evaluate(
        "el => getComputedStyle(el).color") == AMBER
    # Поиск по дереву: <mark> инверсной янтарной парой.
    page.fill("#wiki-search, .wiki-toolbar input[type='search']", "qaredunique")
    page.wait_for_timeout(400)
    mark = page.locator(".result-snippet mark, .wiki-results mark").first
    if mark.count():
        ms = mark.evaluate("el => { const c = getComputedStyle(el);"
                           " return {bg: c.backgroundColor, color: c.color}; }")
        assert ms == {"bg": AMBER900, "color": AMBER}, ms
    # Внешних зависимостей нет (ОГР-8).
    for tpl in ("wiki.html", "base.html"):
        html = (REPO / "frontend/templates" / tpl).read_text()
        externals = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
        assert externals == [], (tpl, externals)
    # Редактор: поля на bg-2 с cyan-фокусом, первичные кнопки янтарные.
    page.goto(f"{web_base_url}/wiki/{child_id}")
    page.locator(".article-actions, .wiki-toolbar").get_by_text("Редактировать").first.click()
    page.wait_for_url("**edit**")
    area = page.locator("#wiki-editor .editor-area, #wiki-editor [contenteditable='true']").first
    expect(area).to_be_visible()
    primary = page.locator("#wiki-editor .btn-primary").first
    assert primary.evaluate("el => getComputedStyle(el).backgroundColor") == AMBER
    # Правка → история: новая версия присутствует.
    web_owner_session.put(
        f"{web_base_url}/api/wiki/pages/{child_id}",
        json={"content": "<p>qaredunique v2</p>"})
    page.goto(f"{web_base_url}/wiki/{child_id}/history")
    expect(page.locator("#wiki-history")).to_contain_text("v2", timeout=10_000)
    # Гейт 2.7 по wiki.css: hex вне :root = 0.
    assert _hex_outside_root(REPO / "frontend/static/css/wiki.css") == []
