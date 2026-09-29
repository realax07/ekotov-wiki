"""Домен tooltip Релиза 4 (change add-r4-user-profile-ticket-view,
tasks.md 3.2; FR-43, ОГР-17, ОВ-25, TC-vis-105; design пакета §5/§11;
дельта navigation MODIFIED «Профиль…» — tooltip как идентификатор логина
(Д-10); дельта board «Единый механизм всплывашек» — механика модуля).

Кейсы_TC (фикстуры запуска dev'а по сценариям дельт, формат
tests/web/test_settings_profile_r4.py; TC-ID продолжают нумерацию
Релиза 4: TC-tip-101…):

board, Scenario «Единый механизм всплывашек» (механика общего модуля):
- оба вызова — один и тот же элемент #app-tooltip        → TC-tip-105 test_module_api_reuse_single_instance;

design §5 (механика: hover/focus показ, blur/mouseleave/Escape скрытие,
позиционирование без выхода за вьюпорт):
- hover → показ; mouseleave → скрытие                    → TC-tip-101 test_hover_shows_and_mouseleave_hides;
- focus → показ; Escape → скрытие (негативный путь)      → TC-tip-102 test_focus_shows_and_escape_hides;
- позиция у нижнего левого края, в пределах вьюпорта     → TC-tip-104 test_position_within_viewport_above_profile;

FR-43 / ОВ-25 (состав tooltip профиля):
- аватар-фоллбек, имя/логин (Д-10), логин, роль, bio     → TC-tip-101 test_hover_shows_and_mouseleave_hides;
- пустое bio — блок bio не показывается                  → TC-tip-103 test_empty_bio_block_absent;
- аватар задан — img в tooltip                           → TC-tip-106 test_avatar_in_tooltip.

TC-vis-105 / ОГР-17 (reduced-motion):
- эмуляция prefers-reduced-motion → мгновенный показ
  без transition                                         → TC-tip-107 test_reduced_motion_no_transition;

FR-39 regression (tooltip не мешает клику):
- клик по профилю при видимом tooltip → /settings/profile → TC-tip-108 test_click_with_visible_tooltip_opens_settings.
"""

import os
import sqlite3

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.web, pytest.mark.must]

OWNER_LOGIN = "owner"
OWNER_PASSWORD = "QaOwner_Pass_1!"
OWNER_DEFAULT_ROLE = "Product manager"  # ОВ-21 (бэкфилл миграции 1.1)

DB_PATH_ENV = "EKOTOV_WIKI_DB_PATH"

TOOLTIP = "#app-tooltip"


# --- Помощники состояния стенда (гигиена: teardown-восстановление) ---


def _owner_user_id(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE login = ?", (OWNER_LOGIN,)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row[0]


def _set_owner_profile(db_path: str, display_name, bio) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE users SET display_name = ?, bio = ? WHERE login = ?",
            (display_name, bio, OWNER_LOGIN),
        )
        conn.commit()
    finally:
        conn.close()


def _reset_avatar(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE users SET avatar_path = NULL, avatar_updated_at = NULL"
            " WHERE login = ?",
            (OWNER_LOGIN,),
        )
        conn.commit()
    finally:
        conn.close()


def _owner_avatar_file(db_path: str) -> str:
    avatars_dir = os.environ.get("EKOTOV_WIKI_AVATARS_DIR")
    assert avatars_dir, "нужен env EKOTOV_WIKI_AVATARS_DIR (tmp-каталог стенда)"
    return os.path.join(avatars_dir, f"{_owner_user_id(db_path)}.png")


@pytest.fixture
def profile_hygiene(web_db_path):
    """Teardown-гигиена: профиль/аватар owner восстанавливаются после
    теста независимо от его исхода (роль ОВ-21 не трогается)."""
    yield
    _set_owner_profile(web_db_path, None, None)
    try:
        os.remove(_owner_avatar_file(web_db_path))
    except OSError:
        pass
    _reset_avatar(web_db_path)


def _make_png(width: int = 300, height: int = 200) -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (30, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _wait_tooltip_shown(page) -> None:
    """Автожидание показа: задержка attach() ~300мс + transition —
    класс tooltip-visible ставится show() сразу после hidden=false."""
    expect(page.locator(TOOLTIP)).to_have_class(
        __import__("re").compile(r"\btooltip-visible\b"), timeout=5_000
    )


def _wait_tooltip_hidden(page) -> None:
    """Автожидание скрытия: mouseleave → hide() → hidden через 250мс."""
    expect(page.locator(TOOLTIP)).to_be_hidden(timeout=5_000)


# ==========================================================================
# Механика: hover → показ, mouseleave → скрытие; состав (FR-43, ОВ-25)
# ==========================================================================


def test_hover_shows_and_mouseleave_hides(
    logged_in_page, web_base_url, web_db_path, profile_hygiene
):
    """Scenario design §5 «показ по hover/focus, скрытие по mouseleave» +
    состав tooltip профиля (ОВ-25): аватар-фоллбек (кружок с буквой),
    display_name (Д-10), логин, роль, bio; role=tooltip + aria-describedby."""
    _set_owner_profile(web_db_path, "QAT Владелец", "QAT био профиля")

    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    profile = page.locator("#sidebar-profile")
    expect(profile).to_contain_class("profile-filled", timeout=10_000)
    expect(profile.locator(".profile-name")).to_have_text("QAT Владелец")

    profile.hover()
    tooltip = page.locator(TOOLTIP)
    _wait_tooltip_shown(page)

    # aria-связка на время показа.
    expect(profile).to_have_attribute("aria-describedby", "app-tooltip")
    expect(tooltip).to_have_attribute("role", "tooltip")

    # Состав (ОВ-25): фоллбек-кружок с первой буквой (аватара нет),
    # имя = display_name (Д-10), логин, роль, bio.
    expect(tooltip.locator(".tooltip-profile-badge")).to_have_text("O")
    expect(tooltip.locator(".tooltip-profile-avatar")).to_have_count(0)
    expect(tooltip.locator(".tooltip-profile-name")).to_have_text("QAT Владелец")
    expect(tooltip.locator(".tooltip-profile-login")).to_have_text(OWNER_LOGIN)
    expect(tooltip.locator(".tooltip-profile-role")).to_have_text(OWNER_DEFAULT_ROLE)
    expect(tooltip.locator(".tooltip-profile-bio")).to_have_text("QAT био профиля")

    # Скрытие по mouseleave.
    page.mouse.move(500, 300)
    _wait_tooltip_hidden(page)
    expect(profile).not_to_have_attribute("aria-describedby", "app-tooltip")


def test_focus_shows_and_escape_hides(logged_in_page, web_base_url):
    """Scenario design §5 «скрытие по blur/Escape» (негативный путь):
    показ по фокусу с клавиатуры, Escape скрывает всплывашку."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    profile = page.locator("#sidebar-profile")
    expect(profile).to_contain_class("profile-filled", timeout=10_000)

    profile.focus()
    _wait_tooltip_shown(page)

    page.keyboard.press("Escape")
    _wait_tooltip_hidden(page)


def test_empty_bio_block_absent(logged_in_page, web_base_url, web_db_path, profile_hygiene):
    """ОВ-25 / дизайн состава: пустое bio — блок bio в tooltip не
    показывается (остальной состав на месте)."""
    _set_owner_profile(web_db_path, None, None)  # seed-состояние: всё пусто

    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    profile = page.locator("#sidebar-profile")
    expect(profile).to_contain_class("profile-filled", timeout=10_000)

    profile.hover()
    _wait_tooltip_shown(page)

    tooltip = page.locator(TOOLTIP)
    expect(tooltip.locator(".tooltip-profile-bio")).to_have_count(0)
    # Имя — fallback на логин (Д-10, display_name не задан).
    expect(tooltip.locator(".tooltip-profile-name")).to_have_text(OWNER_LOGIN)
    expect(tooltip.locator(".tooltip-profile-role")).to_have_text(OWNER_DEFAULT_ROLE)


def test_avatar_in_tooltip(
    logged_in_page, web_base_url, web_db_path, web_owner_session, profile_hygiene
):
    """ОВ-25 / FR-43: аватар задан — в tooltip показывается img
    (вместо кружка-фоллбека), src — URL аватара из me.avatar_url."""
    upload = web_owner_session.post(
        f"{web_base_url}/api/profile/avatar",
        files={"file": ("photo.png", _make_png(), "image/png")},
    )
    assert upload.status_code == 200, upload.text

    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    profile = page.locator("#sidebar-profile")
    expect(profile).to_contain_class("profile-filled", timeout=10_000)
    expect(profile.locator("img.profile-avatar")).to_be_visible()

    profile.hover()
    _wait_tooltip_shown(page)

    tooltip = page.locator(TOOLTIP)
    avatar = tooltip.locator("img.tooltip-profile-avatar")
    expect(avatar).to_be_visible()
    src = avatar.get_attribute("src")
    assert src is not None and "/avatars/" in src and "?v=" in src, src
    expect(tooltip.locator(".tooltip-profile-badge")).to_have_count(0)


# ==========================================================================
# Позиционирование (design §5/§11: нижний левый край, не выходит за вьюпорт)
# ==========================================================================


def test_position_within_viewport_above_profile(logged_in_page, web_base_url):
    """Design §11 (риск «tooltip у нижнего края вьюпорта — подбор вверх»):
    профиль висит у нижнего края — всплывашка целиком в пределах вьюпорта
    и завершается не ниже нижнего края блока профиля (позиция «вверх»)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    profile = page.locator("#sidebar-profile")
    expect(profile).to_contain_class("profile-filled", timeout=10_000)

    profile.hover()
    _wait_tooltip_shown(page)

    tooltip = page.locator(TOOLTIP)
    box = tooltip.bounding_box()
    profile_box = profile.bounding_box()
    assert box is not None and profile_box is not None
    viewport = page.viewport_size
    assert viewport is not None
    assert box["x"] >= 0, box
    assert box["y"] >= 0, box
    assert box["x"] + box["width"] <= viewport["width"], box
    assert box["y"] + box["height"] <= viewport["height"], box
    # Позиция «вверх»: низ всплывашки не ниже низа профиля (с допуском
    # на gap), т.е. не вылезает за нижний край вьюпорта.
    assert box["y"] + box["height"] <= profile_box["y"] + profile_box["height"] + 1, (
        box,
        profile_box,
    )
    # Нижний ЛЕВЫЙ край: левый край всплывашки совпадает с левым краем target.
    assert abs(box["x"] - profile_box["x"]) <= 1, (box, profile_box)


# ==========================================================================
# Единый механизм (ОГР-17): публичный API модуля — переиспользование в 5.1
# ==========================================================================


def test_module_api_reuse_single_instance(logged_in_page, web_base_url):
    """Scenario «Единый механизм всплывашек» (ОГР-17): публичный API
    show(target, content)/hide() модуля tooltip.js; повторный show на
    другой target переиспользует ТОТ ЖЕ элемент #app-tooltip — второй
    экземпляр не создается (как будет у карточек 5.1)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    expect(page.locator("#sidebar-profile")).to_contain_class(
        "profile-filled", timeout=10_000
    )

    result = page.evaluate(
        """async () => {
            const tooltip = await import('/static/js/tooltip.js');
            const a = document.createElement('div');
            a.id = 'tip-target-a';
            document.body.appendChild(a);
            const b = document.createElement('div');
            b.id = 'tip-target-b';
            document.body.appendChild(b);

            tooltip.show(a, 'первая всплывашка');
            const firstId = document.getElementById('app-tooltip') && document.getElementById('app-tooltip').textContent;
            const shownOnA = a.getAttribute('aria-describedby');

            tooltip.show(b, 'вторая всплывашка');
            const tip = document.getElementById('app-tooltip');
            const secondId = tip ? tip.textContent : null;
            const instanceCount = document.querySelectorAll('#app-tooltip').length;
            const shownOnB = b.getAttribute('aria-describedby');

            tooltip.hide();
            return { firstId, secondId, instanceCount, shownOnA, shownOnB };
        }"""
    )
    assert result["firstId"] == "первая всплывашка", result
    assert result["secondId"] == "вторая всплывашка", result
    assert result["instanceCount"] == 1, result  # один экземпляр на документ
    assert result["shownOnA"] == "app-tooltip", result
    assert result["shownOnB"] == "app-tooltip", result


# ==========================================================================
# TC-vis-105: prefers-reduced-motion — мгновенный показ, без transition
# ==========================================================================


def test_reduced_motion_no_transition(logged_in_page, web_base_url):
    """Scenario «Уменьшение движения отключает анимации всплывашек»
    (ОГР-17, TC-vis-105): при prefers-reduced-motion: reduce у всплывашки
    transition отключен (0s) и показ мгновенный — opacity 1 сразу после
    show, содержание не изменяется."""
    page = logged_in_page
    page.emulate_media(reduced_motion="reduce")
    page.goto(f"{web_base_url}/board")
    profile = page.locator("#sidebar-profile")
    expect(profile).to_contain_class("profile-filled", timeout=10_000)

    profile.hover()

    # Мгновенный показ: класс + opacity=1 читаются сразу, без ожидания
    # анимации (transition отключен).
    tooltip = page.locator(TOOLTIP)
    expect(tooltip).to_have_class(__import__("re").compile(r"\btooltip-visible\b"))
    computed = tooltip.evaluate(
        "el => ({ transitionDuration: getComputedStyle(el).transitionDuration,"
        " opacity: getComputedStyle(el).opacity })"
    )
    assert computed["transitionDuration"] == "0s", computed
    assert computed["opacity"] == "1", computed
    # Содержание не изменяется (сценарий board): состав профиля на месте.
    expect(tooltip.locator(".tooltip-profile-login")).to_have_text(OWNER_LOGIN)
    expect(tooltip.locator(".tooltip-profile-role")).to_have_text(OWNER_DEFAULT_ROLE)


# ==========================================================================
# FR-39 regression: tooltip не мешает клику
# ==========================================================================


def test_click_with_visible_tooltip_opens_settings(logged_in_page, web_base_url):
    """Scenario «Клик по профилю открывает настройки пользователя» при
    видимом tooltip (FR-39 regression 3.2): задержка показа ~300мс и
    pointer-events:none — клик по блоку с открытой всплывашкой открывает
    /settings/profile (не /settings, ОГР-20)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    profile = page.locator("#sidebar-profile")
    expect(profile).to_contain_class("profile-filled", timeout=10_000)

    profile.hover()
    _wait_tooltip_shown(page)

    profile.click()
    page.wait_for_url("**/settings/profile")
    expect(page.locator("h1", has_text="Профиль")).to_be_visible()
    expect(page.locator("#category-list")).to_have_count(0)
