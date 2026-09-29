"""Дельта auth Релиза 4: профиль + смена пароля (change
add-r4-user-profile-ticket-view, tasks.md 2.1; FR-36/39/40/41, ОВ-21,
Д-10/Д-11, NFR-7).

TC-ID: TC-profile-001…TC-profile-009, TC-passwd-001…TC-passwd-005,
TC-me4-001…TC-me4-002. Формат: 1 сценарий дельты = 1 тест (contract 6);
кейсы утверждаются QA-контуром (задача 6.1 пакета: «профиль GET/PUT +
валидация роли; смена пароля Д-11; me — расширенный состав»); настоящий
файл — фикстуры запуска dev'а по контрактам sdd §3.1a-кватер, трассировка
в docstring каждого теста.

Requirement «Профиль пользователя — просмотр и редактирование»:
- GET /api/profile — 200 {login, display_name, role, bio, avatar_url};
- PUT /api/profile — 200; 422 при role вне справочника (ОВ-21) и
  неверном типе полей; пустой display_name допустим (Д-10);
- 401 без сессии (оба эндпоинта, NFR-7 — вне exempt-списка).

Requirement «Смена пароля» (FR-41, Д-11):
- успешная смена → 200 {"ok": true}; ТЕКУЩАЯ СЕССИЯ ЖИВА (me 200 без
  повторного входа); вход со старым паролем отклонен, с новым — успех;
- неверный текущий пароль → 422, пароль не изменен;
- пустой новый пароль → 422; 401 без сессии.

Requirement «API текущего пользователя» (MODIFIED, sdd §3.1a-кватер):
- расширенный состав me: {"user", "display_name", "role", "bio",
  "avatar_url"}, null при незаполненном профиле; ключ "user" сохранен.

Гигиена стенда: тесты правят общесистемные записи (профиль/пароль owner) —
каждый тест восстанавливает исходное состояние в teardown (роль owner =
«Product manager», ОВ-21 — иначе повторный прогон migrate_r4 даст exit 1;
пароль owner = seed-значение — иначе ломается регресс tests/api).
Политики сложности нового пароля в спеке нет (NFR не предписывает) —
проверяется только непустота (422 «пустой новый», sdd §3.1a-кватер).
"""

import bcrypt
import pytest
import requests

pytestmark = [pytest.mark.api]

from conftest import (  # noqa: E402
    OWNER_LOGIN,
    OWNER_PASSWORD,
    WIFE_LOGIN,
    DB_PATH_ENV,
    db_select_one,
    db_update,
    login_session,
)

UNAUTHORIZED = {"error": "unauthorized"}

OWNER_DEFAULT_ROLE = "Product manager"  # ОВ-21 (бэкфилл миграции 1.1)
PE_ROLE = "Product engineer"
PM_ROLE = "Product manager"

# Обязательный состав ответа профиля (sdd §3.1a-кватер).
PROFILE_KEYS = {"login", "display_name", "role", "bio", "avatar_url"}
ME_KEYS = {"user", "display_name", "role", "bio", "avatar_url"}


def _get_profile(base_url, session):
    return session.get(f"{base_url}/api/profile")


def _put_profile(base_url, session, **payload):
    return session.put(f"{base_url}/api/profile", json=payload)


def _change_password(base_url, session, current, new):
    return session.post(
        f"{base_url}/api/profile/password",
        json={"current_password": current, "new_password": new},
    )


def _restore_profile_defaults(db_path, base_url=None):
    """Возврат профиля owner к состоянию после миграции 1.1 (ОВ-21)."""
    db_update(
        db_path,
        "UPDATE users SET display_name = NULL, bio = NULL, role = ?"
        " WHERE login = ?",
        (OWNER_DEFAULT_ROLE, OWNER_LOGIN),
    )


@pytest.fixture
def db_path_env():
    """Путь SQLite-БД стенда (прямые проверки/восстановления состояния);
    без env EKOTOV_WIKI_DB_PATH тест skip — как в conftest-фикстурах."""
    import os

    path = os.environ.get(DB_PATH_ENV)
    if not path:
        pytest.skip(f"нужен env {DB_PATH_ENV} (путь SQLite-БД приложения)")
    return path


# --------------------------------------------------------------------------
# GET /api/profile — Scenario «Просмотр своего профиля» (Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_get_profile_of_session_user(base_url, owner_session):
    """TC-profile-001 — Scenario «Просмотр своего профиля»: профиль
    пользователя сессии: 200, состав ровно из 5 ключей, логин
    соответствует сессии, роль — дефолт миграции (ОВ-21), avatar_url null
    (аватара нет — FR-33 fallback на клиенте)."""
    resp = _get_profile(base_url, owner_session)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == PROFILE_KEYS
    assert body["login"] == OWNER_LOGIN
    assert body["role"] == OWNER_DEFAULT_ROLE
    assert body["avatar_url"] is None  # аватара нет → URL не строится


@pytest.mark.must
def test_get_profile_second_user_gets_own_data(base_url, wife_session):
    """TC-profile-002 — «Второй пользователь получает свои данные»: логин
    wife, роль wife (Product engineer, ОВ-21) — каждый пользователь видит
    свой профиль."""
    resp = _get_profile(base_url, wife_session)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == PROFILE_KEYS
    assert body["login"] == WIFE_LOGIN
    assert body["role"] == PE_ROLE


@pytest.mark.must
def test_profile_endpoints_401_without_session(base_url, http):
    """TC-profile-003 — Scenario «Негативный: без сессии — 401»: GET и
    PUT /api/profile (и password) без сессии — 401
    {"error": "unauthorized"} (эндпоинты вне exempt-списка, NFR-7)."""
    resp_get = http.get(f"{base_url}/api/profile")
    assert resp_get.status_code == 401
    assert resp_get.json() == UNAUTHORIZED

    resp_put = http.put(f"{base_url}/api/profile", json={"display_name": "X"})
    assert resp_put.status_code == 401
    assert resp_put.json() == UNAUTHORIZED

    resp_pwd = http.post(
        f"{base_url}/api/profile/password",
        json={"current_password": "x", "new_password": "y"},
    )
    assert resp_pwd.status_code == 401
    assert resp_pwd.json() == UNAUTHORIZED


# --------------------------------------------------------------------------
# PUT /api/profile — Scenario «Сохранение профиля» (Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_put_profile_save_and_read_back(base_url, owner_session, db_path_env):
    """TC-profile-004 — Scenario «Сохранение профиля»: PUT → 200; повторный
    GET возвращает сохраненные значения; me отдает тот же состав
    (источник tooltip'а, FR-43)."""
    new_name = "QAT Владелец"
    new_bio = "QAT био профиля"
    try:
        resp = _put_profile(
            base_url,
            owner_session,
            display_name=new_name,
            role=PE_ROLE,
            bio=new_bio,
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == new_name

        read_back = _get_profile(base_url, owner_session).json()
        assert read_back["display_name"] == new_name
        assert read_back["role"] == PE_ROLE
        assert read_back["bio"] == new_bio

        me = owner_session.get(f"{base_url}/api/auth/me").json()
        assert me["display_name"] == new_name
        assert me["role"] == PE_ROLE
        assert me["bio"] == new_bio
    finally:
        _restore_profile_defaults(db_path_env)


@pytest.mark.must
def test_put_profile_role_outside_directory_422_unchanged(
    base_url, owner_session, db_path_env
):
    """TC-profile-005 — Scenario «Негативный: роль вне справочника
    отклоняется» (ОВ-21): role «Admin» → 422, профиль НЕ изменяется —
    прежние значения сохраняются."""
    resp = _put_profile(
        base_url,
        owner_session,
        display_name="Взлом",
        role="Admin",
        bio="не должно сохраниться",
    )
    assert resp.status_code == 422

    body = _get_profile(base_url, owner_session).json()
    assert body["role"] == OWNER_DEFAULT_ROLE
    row = db_select_one(
        db_path_env,
        "SELECT display_name, bio FROM users WHERE login = ?",
        (OWNER_LOGIN,),
    )
    assert row[0] is None and row[1] is None  # измененные поля не применены


@pytest.mark.must
def test_put_profile_wrong_type_422(base_url, owner_session):
    """TC-profile-006 — Негативный (sdd §3.1a-кватер): display_name/bio
    неверного типа → 422, тело в форме {"error", "details"} (sdd §3)."""
    resp = _put_profile(
        base_url, owner_session, display_name=12345, role=PM_ROLE, bio="x"
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body and "details" in body

    resp_bio = _put_profile(
        base_url, owner_session, display_name="ok", role=PM_ROLE, bio=[]
    )
    assert resp_bio.status_code == 422


@pytest.mark.must
def test_put_profile_empty_display_name_allowed_fallback_login(
    base_url, owner_session, db_path_env
):
    """TC-profile-007 — Д-10 (спека: «Сохранение пустого display_name
    допустимо»): пустая строка сохраняется; значение читается как null
    (пустые значения — null, sdd §3.1a-кватер) — клиент показывает логин."""
    try:
        resp = _put_profile(
            base_url,
            owner_session,
            display_name="",
            role=PM_ROLE,
            bio="био есть, имени нет",
        )
        assert resp.status_code == 200
        body = _get_profile(base_url, owner_session).json()
        assert body["display_name"] is None
        assert body["bio"] == "био есть, имени нет"
        assert body["login"] == OWNER_LOGIN
    finally:
        _restore_profile_defaults(db_path_env)


# --------------------------------------------------------------------------
# POST /api/profile/password — Requirement «Смена пароля» (Must, Д-11)
# --------------------------------------------------------------------------
@pytest.fixture
def owner_password_guard(base_url, db_path_env):
    """Гарантия исходного пароля owner после теста: если тест сменил пароль
    и упал до собственного возврата — teardown возвращает seed-пароль
    напрямую bcrypt-хешем в БД (регресс tests/api не зависит от падения)."""
    yield

    try:
        login_session(base_url, OWNER_LOGIN, OWNER_PASSWORD).close()
    except AssertionError:
        new_hash = bcrypt.hashpw(
            OWNER_PASSWORD.encode("utf-8"), bcrypt.gensalt()
        ).decode("ascii")
        db_update(
            db_path_env,
            "UPDATE users SET password_hash = ? WHERE login = ?",
            (new_hash, OWNER_LOGIN),
        )


@pytest.mark.must
def test_password_change_success_session_survives(
    base_url, owner_session, owner_password_guard
):
    """TC-passwd-001 — Scenario «Успешная смена пароля» (Д-11): пароль
    изменен; ТЕКУЩАЯ сессия сохраняется (me 200 без повторного входа);
    вход со старым паролем отклонен, с новым — успешен. Обратный возврат —
    той же механикой (current = новый пароль)."""
    new_password = "QaNew_Pass_77!"
    resp = _change_password(base_url, owner_session, OWNER_PASSWORD, new_password)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # Д-11: та же сессия жива — запрос прошел, не разлогинен
    me = owner_session.get(f"{base_url}/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"] == OWNER_LOGIN

    # старый пароль больше не работает (401, единый текст login-ошибки)
    fresh_old = requests.Session()
    try:
        resp_old = fresh_old.post(
            f"{base_url}/api/auth/login",
            json={"login": OWNER_LOGIN, "password": OWNER_PASSWORD},
        )
        assert resp_old.status_code == 401
        assert resp_old.json() == {"error": "invalid credentials"}
    finally:
        fresh_old.close()

    # вход с новым паролем успешен
    fresh_new = login_session(base_url, OWNER_LOGIN, new_password)
    try:
        assert fresh_new.get(f"{base_url}/api/auth/me").json()["user"] == OWNER_LOGIN
    finally:
        fresh_new.close()

    # возврат seed-пароля (current = новый, Д-11-механика)
    back = _change_password(base_url, owner_session, new_password, OWNER_PASSWORD)
    assert back.status_code == 200


@pytest.mark.must
def test_password_change_wrong_current_422_unchanged(
    base_url, owner_session, owner_password_guard
):
    """TC-passwd-002 — Scenario «Негативный: неверный текущий пароль»:
    422 с единым текстом {"error": "invalid current password"}; пароль НЕ
    изменен — вход со старым паролем продолжает работать (Д-11)."""
    resp = _change_password(
        base_url, owner_session, "Wrong_Current_Pass!", "QaWhatever_9!"
    )
    assert resp.status_code == 422
    assert resp.json() == {"error": "invalid current password"}

    # пароль не изменен: вход со старым работает
    fresh = login_session(base_url, OWNER_LOGIN, OWNER_PASSWORD)
    fresh.close()


@pytest.mark.must
def test_password_change_empty_new_422(base_url, owner_session):
    """TC-passwd-003 — Негативный (sdd §3.1a-кватер: «пустой новый»):
    пустая строка → 422; пароль при этом не меняется (вход с прежним
    работает)."""
    resp = _change_password(base_url, owner_session, OWNER_PASSWORD, "")
    assert resp.status_code == 422

    fresh = login_session(base_url, OWNER_LOGIN, OWNER_PASSWORD)
    fresh.close()


@pytest.mark.must
def test_password_change_session_record_untouched(
    base_url, owner_session, db_path_env
):
    """TC-passwd-004 — Д-11 на уровне данных: запись sessions текущей
    сессии после смены пароля не удалена и не пересоздана (sdd
    §3.1a-кватер: «сессии не трогаются»); сессия продолжает проходить
    middleware."""
    token = owner_session.cookies.get("session")

    def _session_row():
        return db_select_one(
            db_path_env,
            "SELECT token, user_id FROM sessions WHERE token = ?",
            (token,),
        )

    before = _session_row()
    assert before is not None

    resp = _change_password(
        base_url, owner_session, OWNER_PASSWORD, OWNER_PASSWORD
    )
    assert resp.status_code == 200  # смена на тот же пароль допустима

    after = _session_row()
    # Д-11: сессия не удалена и не пересоздана (token/user_id те же).
    # expires_at не сравнивается: скользящее продление TTL middleware
    # обновляет его на КАЖДОМ запросе (design §2) — это штатная обработка
    # запроса, а не реакция на смену пароля.
    assert after == before
    assert owner_session.get(f"{base_url}/api/auth/me").status_code == 200


# --------------------------------------------------------------------------
# GET /api/auth/me — MODIFIED Requirement «API текущего пользователя»
# --------------------------------------------------------------------------
@pytest.mark.must
def test_me_extended_composition(base_url, owner_session, db_path_env):
    """TC-me4-001 — Расширенный состав me (sdd §3.1a-кватер, MODIFIED
    Requirement «API текущего пользователя»): все 5 ключей; ключ "user"
    (логин) сохранен — обратная совместимость; значение профиля видно."""
    try:
        _put_profile(
            base_url,
            owner_session,
            display_name="QAT Me",
            role=PM_ROLE,
            bio="QAT bio",
        )
        body = owner_session.get(f"{base_url}/api/auth/me").json()
        assert set(body) == ME_KEYS
        assert body["user"] == OWNER_LOGIN
        assert body["display_name"] == "QAT Me"
        assert body["role"] == PM_ROLE
        assert body["bio"] == "QAT bio"
        assert body["avatar_url"] is None
    finally:
        _restore_profile_defaults(db_path_env)


@pytest.mark.must
def test_me_defaults_when_profile_empty(base_url, owner_session, db_path_env):
    """TC-me4-002 — Scenario «Дефолты при незаполненном профиле»: поля
    профиля — null, логин заполнен (Д-10). Предусловие «никогда не
    заполнял» создается прямой БД-правкой (role тоже NULL) и откатывается
    в teardown."""
    db_update(
        db_path_env,
        "UPDATE users SET display_name = NULL, role = NULL, bio = NULL"
        " WHERE login = ?",
        (OWNER_LOGIN,),
    )
    try:
        body = owner_session.get(f"{base_url}/api/auth/me").json()
        assert set(body) == ME_KEYS
        assert body["user"] == OWNER_LOGIN
        assert body["display_name"] is None
        assert body["role"] is None
        assert body["bio"] is None
        assert body["avatar_url"] is None

        profile = _get_profile(base_url, owner_session).json()
        assert profile["login"] == OWNER_LOGIN
        assert profile["display_name"] is None
        assert profile["role"] is None
        assert profile["bio"] is None
    finally:
        _restore_profile_defaults(db_path_env)
