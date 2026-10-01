"""Домен settings-profile Релиза 4 (change add-r4-user-profile-ticket-view,
tasks.md 3.1; FR-39/40/41/42, ОГР-20, Д-10; дельты settings — оба ADDED
Requirement, navigation — MODIFIED Requirement «Профиль текущего
пользователя внизу сайдбара»: сценарии «display_name», «аватар», «клик»).

Кейсы_TC (фикстуры запуска dev'а по сценариям дельт, трассировка в
docstring каждого теста — формат tests/api/test_profile_r4.py;
TC-ID продолжают нумерацию QA-доменов Релиза 4: TC-setp-201… (settings
profile-страница), TC-passwd-101…, TC-ava-101…, TC-nav-201…):

settings, Requirement «Страница настроек пользователя»:
- «Негативный: неавторизованный доступ»     → TC-setp-201 test_unauthenticated_redirect;
- «Открытие страницы настроек пользователя» → TC-setp-202 test_page_composition
  (+ предзаполнение из GET /api/profile);
- «Настройки пользователя — только свои данные» → TC-setp-203 test_wife_sees_own_data;
- «Независимость от общих настроек»         → TC-setp-202 test_page_composition.

settings, Requirement «Форма профиля…»:
- «Редактирование и сохранение профиля»     → TC-setp-204 test_edit_display_name_bio_saves;
- «Роль — только выбор из справочника»      → TC-setp-205 test_role_select_exactly_two_options;
- «Очистка display_name — показывается логин» → TC-setp-206 test_clear_display_name_fallback_login.

auth-дельты (UI-половина API задач 2.2/2.3 — страница-потребитель):
- «Негативный: неверный текущий пароль»     → TC-passwd-101 test_password_wrong_current_error;
- «Успешная смена пароля» (Д-11: сессия жива) → TC-passwd-102 test_password_change_success_session_alive;
- «Негативный: тип файла не png/jpg»        → TC-ava-101 test_avatar_txt_rejected;
- «Успешная загрузка png» (превью на странице) → TC-ava-102 test_avatar_png_upload_preview.

navigation (MODIFIED):
- «Клик по профилю открывает настройки пользователя» → TC-nav-201 test_profile_click_opens_settings_profile;
- «Подпись профиля — display_name, если задан»       → TC-setp-204 (шаг сайдбара)
  / TC-setp-206 (fallback на логин, Д-10);
- «Аватар отображается в блоке профиля»      → TC-ava-102 (шаг сайдбара).

Гигиена стенда: тесты правят профиль/пароль/аватар owner — каждый тест
восстанавливает исходное состояние в teardown (роль «Product manager»,
ОВ-21; seed-пароль; avatar_path=NULL + файл удален).
"""

import io
import os
import sqlite3

import pytest
from PIL import Image
from playwright.sync_api import expect

pytestmark = [pytest.mark.web, pytest.mark.must]

OWNER_LOGIN = "owner"
OWNER_PASSWORD = "QaOwner_Pass_1!"
WIFE_LOGIN = "wife"
WIFE_PASSWORD = "QaWife_Pass_2!"
OWNER_DEFAULT_ROLE = "Product manager"  # ОВ-21 (бэкфилл миграции 1.1)

DB_PATH_ENV = "EKOTOV_WIKI_DB_PATH"


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


def _restore_profile(db_path: str) -> None:
    """Возврат профиля owner к состоянию после миграции 1.1 (ОВ-21)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE users SET display_name = NULL, bio = NULL, role = ?"
            " WHERE login = ?",
            (OWNER_DEFAULT_ROLE, OWNER_LOGIN),
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
    теста независимо от его исхода (пароль восстанавливается самим
    тестом обратной сменой — см. test_password_change_success)."""
    yield
    _restore_profile(web_db_path)
    try:
        os.remove(_owner_avatar_file(web_db_path))
    except OSError:
        pass
    _reset_avatar(web_db_path)


def _make_png(width: int = 300, height: int = 200) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _expect_profile_filled(page, badge: str, name: str) -> None:
    profile = page.locator("#sidebar-profile")
    expect(profile).to_contain_class("profile-filled", timeout=10_000)
    # Подпись асинхронна (GET /api/auth/me после ответа /me с display_name) —
    # автожидание текста, а не мгновенный ассерт.
    expect(profile.locator(".profile-name")).to_have_text(name, timeout=10_000)


def _goto_profile_settings(page, web_base_url) -> None:
    page.goto(f"{web_base_url}/settings/profile")
    # Автожидание предзаполнения: GET /api/profile асинхронен; форма
    # ставит data-loaded=true после применения значений (конвенция #board).
    # Роль PM — дефолт select, поэтому значение роли готовности НЕ сигналит.
    expect(page.locator("#profile-form")).to_have_attribute(
        "data-loaded", "true", timeout=10_000
    )


# ==========================================================================
# Страница: доступ и состав (Requirement «Страница настроек пользователя»)
# ==========================================================================


def test_unauthenticated_redirect(page, web_base_url):
    """Scenario «Негативный: неавторизованный доступ» (NFR-7): /settings/profile
    без сессии → редирект на /login; содержимое страницы не отображается."""
    response = page.goto(f"{web_base_url}/settings/profile")
    assert response is not None
    page.wait_for_url(f"**/login")
    expect(page.get_by_label("Логин")).to_be_visible()
    assert "#profile-form" not in page.content()


def test_page_composition(logged_in_page, web_base_url):
    """Scenario «Открытие страницы настроек пользователя» + «Независимость
    от общих настроек» (ОГР-20): три блока (форма профиля, смена пароля,
    аватар); предзаполнение из GET /api/profile; справочника категорий
    на странице НЕТ."""
    page = logged_in_page
    _goto_profile_settings(page, web_base_url)

    # Состав: формы трех независимых блоков с отдельными кнопками.
    expect(page.locator("#profile-form")).to_be_visible()
    expect(page.locator("#password-form")).to_be_visible()
    expect(page.locator("#avatar-form")).to_be_visible()
    expect(page.get_by_role("button", name="Сохранить")).to_have_count(1)
    expect(page.get_by_role("button", name="Сменить пароль")).to_have_count(1)
    # Хотфикс Р5: кроп-модуль активен (canvas доступен) → кнопка «Загрузить»
    # скрыта (hidden, из разметки не удалена). Путь загрузки: «Выбрать
    # файл…» → кроп → «Применить»; в fallback без canvas кнопка видима
    # (NFR-14, тесты — test_r5_crop_ui.py: hidden_when_crop_active /
    # visible_in_fallback).
    expect(page.locator("#avatar-upload")).to_have_count(1)
    expect(page.locator("#avatar-upload")).to_be_hidden()

    # Предзаполнение: пустой профиль seed-owner — поля пустые, роль = дефолт.
    expect(page.locator("#profile-display-name")).to_have_value("")
    expect(page.locator("#profile-bio")).to_have_value("")
    expect(page.locator("#profile-role")).to_have_value(OWNER_DEFAULT_ROLE)

    # ОГР-20: управления категориями на странице нет.
    expect(page.locator("#category-list")).to_have_count(0)
    expect(page.get_by_text("Категории")).to_have_count(0)


def test_wife_sees_own_data(logged_in_page, web_base_url, web_db_path, profile_hygiene):
    """Scenario «Настройки пользователя — только свои данные»: каждая сессия
    видит и редактирует свой профиль (профиль owner задан, wife входит —
    ее форма пуста; FR-39)."""
    page = logged_in_page
    _goto_profile_settings(page, web_base_url)
    page.locator("#profile-display-name").fill("QAT Владелец")
    page.get_by_role("button", name="Сохранить").click()
    expect(page.locator("#profile-success")).to_be_visible()
    _restore_profile(web_db_path)

    # Второй пользователь — свои данные (не данные owner).
    page2 = page.context.new_page()
    try:
        page2.goto(f"{web_base_url}/login")
        page2.get_by_label("Логин").fill(WIFE_LOGIN)
        page2.get_by_label("Пароль").fill(WIFE_PASSWORD)
        page2.get_by_role("button", name="Войти").click()
        expect(page2.get_by_role("heading", name="Доска", exact=True)).to_be_visible()
        page2.goto(f"{web_base_url}/settings/profile")
        # Роль wife — «Product engineer» (ее данные; предзаполнение асинхронно).
        expect(page2.locator("#profile-role")).to_have_value(
            "Product engineer", timeout=10_000
        )
        expect(page2.locator("#profile-display-name")).to_have_value("", timeout=10_000)
    finally:
        page2.close()


# ==========================================================================
# Форма профиля (Requirement «Форма профиля на странице настроек»)
# ==========================================================================


def test_edit_display_name_bio_saves(
    logged_in_page, web_base_url, web_db_path, profile_hygiene
):
    """Scenario «Редактирование и сохранение профиля» (FR-40): сохранение
    → PUT /api/profile уходит; после обновления страницы форма показывает
    сохраненные значения, блок профиля — display_name (Д-10, FR-43)."""
    page = logged_in_page
    _goto_profile_settings(page, web_base_url)

    page.locator("#profile-display-name").fill("QAT Владелец")
    page.locator("#profile-role").select_option(OWNER_DEFAULT_ROLE)
    page.locator("#profile-bio").fill("QAT био профиля")
    page.get_by_role("button", name="Сохранить").click()
    expect(page.locator("#profile-success")).to_be_visible()

    # Значения сохранены (GET /api/profile читает обновленный профиль).
    page.reload()
    expect(page.locator("#profile-display-name")).to_have_value(
        "QAT Владелец", timeout=10_000
    )
    expect(page.locator("#profile-bio")).to_have_value("QAT био профиля")

    # Блок профиля сайдбара показывает display_name (Д-10).
    _expect_profile_filled(page, "O", "QAT Владелец")

    # Факт на сервере: профиль в БД обновлен (PUT заменил состав).
    conn = sqlite3.connect(web_db_path)
    try:
        row = conn.execute(
            "SELECT display_name, role, bio FROM users WHERE login = ?",
            (OWNER_LOGIN,),
        ).fetchone()
    finally:
        conn.close()
    assert row == ("QAT Владелец", OWNER_DEFAULT_ROLE, "QAT био профиля"), row


def test_role_select_exactly_two_options(logged_in_page, web_base_url):
    """Scenario «Роль — только выбор из справочника» (ОВ-21): ровно два
    значения; свободный ввод роли невозможен (select)."""
    page = logged_in_page
    _goto_profile_settings(page, web_base_url)

    role = page.locator("#profile-role")
    options = role.locator("option")
    expect(options).to_have_count(2)
    expect(options.nth(0)).to_have_attribute("value", "Product manager")
    expect(options.nth(1)).to_have_attribute("value", "Product engineer")
    assert role.evaluate("el => el.tagName.toLowerCase()") == "select"
    # Свободный ввод роли невозможен (элемент — select, не text-input).
    assert role.evaluate("el => [ ...el.options ].map(o => o.value)") == [
        "Product manager",
        "Product engineer",
    ]


def test_clear_display_name_fallback_login(
    logged_in_page, web_base_url, web_db_path, profile_hygiene
):
    """Scenario «Очистка display_name — показывается логин» (Д-10): очистка
    и сохранение успешны; в местах отображения имени — логин."""
    page = logged_in_page
    _goto_profile_settings(page, web_base_url)

    page.locator("#profile-display-name").fill("Временное имя")
    page.get_by_role("button", name="Сохранить").click()
    expect(page.locator("#profile-success")).to_be_visible()

    # Блок профиля сайдбара показывает display_name (Д-10) — после
    # обновления страницы (сценарий navigation: подпись из me).
    page.reload()
    expect(page.locator("#profile-form")).to_have_attribute(
        "data-loaded", "true", timeout=10_000
    )
    _expect_profile_filled(page, "O", "Временное имя")

    # Очистка display_name и сохранение — успех.
    page.locator("#profile-display-name").fill("")
    page.get_by_role("button", name="Сохранить").click()
    expect(page.locator("#profile-success")).to_be_visible()
    expect(page.locator("#profile-error")).to_be_hidden()

    # Имя в местах отображения — логин (fallback Д-10).
    page.reload()
    expect(page.locator("#profile-display-name")).to_have_value("", timeout=10_000)
    _expect_profile_filled(page, "O", OWNER_LOGIN)


# ==========================================================================
# Смена пароля (Requirement «Смена пароля», Д-11 — UI-половина)
# ==========================================================================


@pytest.fixture
def owner_password_guard(web_db_path):
    """Гарантия seed-пароля owner после теста (прямым bcrypt-хешем в БД,
    как tests/api/test_profile_r4.owner_password_guard) — регресс не
    зависит от исхода теста."""
    yield
    import bcrypt

    new_hash = bcrypt.hashpw(
        OWNER_PASSWORD.encode("utf-8"), bcrypt.gensalt()
    ).decode("ascii")
    conn = sqlite3.connect(web_db_path)
    try:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE login = ?",
            (new_hash, OWNER_LOGIN),
        )
        conn.commit()
    finally:
        conn.close()


def test_password_wrong_current_error(logged_in_page, web_base_url, owner_password_guard):
    """Scenario «Негативный: неверный текущий пароль»: ошибка на странице
    («Неверный текущий пароль»); пароль не изменен — вход со старым
    работает (Д-11)."""
    page = logged_in_page
    _goto_profile_settings(page, web_base_url)

    page.locator("#password-current").fill("Wrong_Current_Pass!")
    page.locator("#password-new").fill("QaWhatever_9!")
    page.get_by_role("button", name="Сменить пароль").click()
    expect(page.locator("#password-error")).to_contain_text(
        "Неверный текущий пароль"
    )

    # Пароль не изменен: свежий вход со старым паролем работает.
    check = page.context.new_page()
    try:
        check.goto(f"{web_base_url}/login")
        check.get_by_label("Логин").fill(OWNER_LOGIN)
        check.get_by_label("Пароль").fill(OWNER_PASSWORD)
        check.get_by_role("button", name="Войти").click()
        expect(
            check.get_by_role("heading", name="Доска", exact=True)
        ).to_be_visible()
    finally:
        check.close()


def test_password_change_success_session_alive(
    logged_in_page, web_base_url, owner_password_guard
):
    """Scenario «Успешная смена пароля» (Д-11): успех на странице;
    ТЕКУЩАЯ сессия жива — страница перезагружается без редиректа на
    /login; вход с новым паролем выполняется."""
    page = logged_in_page
    _goto_profile_settings(page, web_base_url)

    new_password = "QaNew_Pass_77!"
    page.locator("#password-current").fill(OWNER_PASSWORD)
    page.locator("#password-new").fill(new_password)
    page.get_by_role("button", name="Сменить пароль").click()
    expect(page.locator("#password-success")).to_contain_text("Пароль изменен")

    # Д-11: текущая сессия сохраняется — та же страница работает без
    # повторного входа (GET /api/profile отвечает 200, не редирект).
    page.reload()
    expect(page.locator("#profile-form")).to_be_visible()
    expect(page.get_by_label("Логин")).to_have_count(0)

    # Вход с новым паролем успешен (отдельная сессия).
    fresh = page.context.new_page()
    try:
        fresh.goto(f"{web_base_url}/login")
        fresh.get_by_label("Логин").fill(OWNER_LOGIN)
        fresh.get_by_label("Пароль").fill(new_password)
        fresh.get_by_role("button", name="Войти").click()
        expect(
            fresh.get_by_role("heading", name="Доска", exact=True)
        ).to_be_visible()
    finally:
        fresh.close()


# ==========================================================================
# Аватар (Requirement «Загрузка аватара» — UI-половина: ошибки API, превью)
# ==========================================================================


def test_avatar_txt_rejected(logged_in_page, web_base_url, web_db_path, profile_hygiene):
    """Scenario «Негативный: тип файла не png/jpg» (FR-42): загрузка txt →
    ошибка на странице (текст 422 invalid file type); превью не появилось,
    аватар в БД не изменен."""
    page = logged_in_page
    _goto_profile_settings(page, web_base_url)

    page.locator("#avatar-file").set_input_files(
        files=[{"name": "note.txt", "mimeType": "text/plain", "buffer": b"hello"}]
    )
    # Хотфикс Р5: невалидный txt отклоняется ДО открытия виджета
    # (NFR-12), но кроп-модуль активен (canvas есть) → кнопка «Загрузить»
    # скрыта (hotfix: hidden после initAvatarCrop). Р4-обработчик change
    # через подписку виджета НЕ вызван — ошибка уже показана кроп-модулем
    # (тот же текст, что Р4-ответ сервера: правила едины, NFR-10/ОВ-22).
    expect(page.locator("#avatar-error")).to_be_visible()
    expect(page.locator("#crop-widget")).not_to_contain_class("is-open")
    expect(page.locator("#avatar-preview")).to_be_hidden()

    # Аватар не сохранен.
    conn = sqlite3.connect(web_db_path)
    try:
        row = conn.execute(
            "SELECT avatar_path FROM users WHERE login = ?", (OWNER_LOGIN,)
        ).fetchone()
    finally:
        conn.close()
    assert row[0] is None, row


def test_avatar_png_upload_preview(
    logged_in_page, web_base_url, web_db_path, profile_hygiene
):
    """Scenario «Успешная загрузка png» (FR-42): превью на странице после
    загрузки; аватар появляется в блоке профиля сайдбара вместо кружка
    (после обновления страницы — из me.avatar_url)."""
    page = logged_in_page
    _goto_profile_settings(page, web_base_url)

    page.locator("#avatar-file").set_input_files(
        files=[
            {
                "name": "photo.png",
                "mimeType": "image/png",
                "buffer": _make_png(),
            }
        ]
    )
    # Хотфикс Р5: валидный png открывает кроп-виджет (Д-12), сабмит формы
    # перехватывается виджетом (= «Применить», capture на document) —
    # путь загрузки: кроп открыт → «Применить» (canvas 256×256 → POST).
    expect(page.locator("#crop-widget")).to_contain_class("is-open", timeout=10_000)
    page.locator("#crop-apply").click()
    expect(page.locator("#avatar-success")).to_be_visible()

    # Превью: img показан, src — URL аватара из ответа API (?v= версия).
    preview = page.locator("#avatar-preview")
    expect(preview).to_be_visible()
    src = preview.get_attribute("src")
    assert src is not None and "/avatars/" in src and "?v=" in src, src

    # Аватар в БД сохранен.
    conn = sqlite3.connect(web_db_path)
    try:
        row = conn.execute(
            "SELECT avatar_path FROM users WHERE login = ?", (OWNER_LOGIN,)
        ).fetchone()
    finally:
        conn.close()
    assert row[0] is not None, row

    # Блок профиля сайдбара: img.avatar-avatar вместо кружка (после
    # обновления страницы — данные из GET /api/auth/me).
    page.goto(f"{web_base_url}/board")
    profile = page.locator("#sidebar-profile")
    expect(profile).to_contain_class("profile-filled", timeout=10_000)
    expect(profile.locator("img.profile-avatar")).to_be_visible()
    expect(profile.locator(".profile-badge")).to_have_count(0)


# ==========================================================================
# navigation MODIFIED: клик по блоку профиля (FR-39, ОГР-20, Д-10)
# ==========================================================================


def test_profile_click_opens_settings_profile(
    logged_in_page, web_base_url, web_db_path, profile_hygiene
):
    """Scenario «Клик по профилю открывает настройки пользователя»: клик по
    блоку профиля внизу сайдбара открывает /settings/profile (свой
    профиль) — а не общий раздел /settings (ОГР-20)."""
    page = logged_in_page
    page.goto(f"{web_base_url}/board")
    _expect_profile_filled(page, "O", OWNER_LOGIN)

    page.locator("#sidebar-profile").click()
    page.wait_for_url("**/settings/profile")
    expect(page.locator("h1", has_text="Профиль")).to_be_visible()
    # Не общий раздел настроек: справочника категорий нет.
    expect(page.locator("#category-list")).to_have_count(0)
