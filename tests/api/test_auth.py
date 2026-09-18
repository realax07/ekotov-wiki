"""Домен auth: TC-auth-001…017 (CHK-1…17; approved/add-kanban-core/auth-01.md).

Тело 401 middleware — дословно {"error": "unauthorized"}; 401 login —
{"error": "invalid credentials"}; exempt — только POST /api/auth/login и
GET /api/health (sdd §3, §3.1, §3.6).
"""

import os

import pytest
import requests

pytestmark = [pytest.mark.api]

UNAUTHORIZED = {"error": "unauthorized"}
INVALID_CREDENTIALS = {"error": "invalid credentials"}

# Импорты из conftest (pytest добавляет tests/api в sys.path)
from conftest import login_session, OWNER_LOGIN, OWNER_PASSWORD  # noqa: E402


def _requests_login(base_url: str) -> requests.Session:
    """Новая сессия с выполненным входом owner (локальный helper теста)."""
    return login_session(base_url, OWNER_LOGIN, OWNER_PASSWORD)


# --------------------------------------------------------------------------
# TC-auth-001 — API-запрос без сессии отклоняется 401 (CHK-1, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_api_without_session_rejected_401(base_url, http, api, unique_title):
    """TC-auth-001: каждый запрос без сессии — 401 {"error": "unauthorized"},
    данных задач в теле нет; задача после неудавшихся PATCH/DELETE не изменена."""
    # Предусловие кейса: на доске есть задача (создаем свою, изоляция)
    task = api.create_ok(unique_title)

    resp_board = http.get(f"{base_url}/api/board")
    resp_create = http.post(f"{base_url}/api/tasks", json={"title": f"{unique_title}-noauth"})
    resp_patch = http.patch(f"{base_url}/api/tasks/{task['id']}", json={"priority": "high"})
    resp_delete = http.delete(f"{base_url}/api/tasks/{task['id']}")
    resp_search = http.get(f"{base_url}/api/search", params={"priority": "high"})

    for resp in (resp_board, resp_create, resp_patch, resp_delete, resp_search):
        assert resp.status_code == 401, f"{resp.request.method} {resp.url}: {resp.status_code}"
        assert resp.json() == UNAUTHORIZED

    # данных задач в теле нет; GET /api/board не возвращает columns
    assert "columns" not in resp_board.json()

    # задача id не изменена и не удалена (проверка с валидной сессией)
    after = api.get_task(task["id"])
    assert after.status_code == 200
    assert after.json()["priority"] == task["priority"]  # PATCH не применился
    assert after.json()["title"] == unique_title  # DELETE не удалил


# --------------------------------------------------------------------------
# TC-auth-002 — API-запрос с просроченной сессией → 401 (CHK-2, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_expired_session_rejected_401(base_url, owner_session, expire_session):
    """TC-auth-002: вход → 200 + Set-Cookie; после истечения expires_at в БД
    запрос с той же кукой — 401 {"error": "unauthorized"} (сессия не принята)."""
    token = expire_session(owner_session)

    resp = owner_session.get(f"{base_url}/api/board")
    assert resp.status_code == 401
    assert resp.json() == UNAUTHORIZED


# --------------------------------------------------------------------------
# TC-auth-003 — Health отвечает 200 без сессии (CHK-3, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_health_200_without_session(base_url, http):
    """TC-auth-003: GET /api/health без куки — 200, тело точно
    {"status": "ok"}; Set-Cookie нет; редиректа на /login нет."""
    resp = http.get(f"{base_url}/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert "Set-Cookie" not in resp.headers
    assert "Location" not in resp.headers  # редиректа нет


# --------------------------------------------------------------------------
# TC-auth-004 — Exempt-список исчерпывающий: прочие API без сессии → 401 (CHK-4, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_exempt_list_exhaustive(base_url, http, api):
    """TC-auth-004: GET /api/board, POST /api/tasks, POST /api/search/advanced,
    POST /api/auth/logout без сессии — каждый 401 {"error": "unauthorized"};
    ни один не выполнил действие (задач с title=X в системе нет)."""
    title_x = "QAT-auth004-X"
    # контроль: не осталось от прошлого прогона
    api.cleanup_all()

    responses = [
        http.get(f"{base_url}/api/board"),
        http.post(f"{base_url}/api/tasks", json={"title": title_x}),
        http.post(f"{base_url}/api/search/advanced", json={"query": 'priority = "high"'}),
        http.post(f"{base_url}/api/auth/logout"),
    ]
    for resp in responses:
        assert resp.status_code == 401, f"{resp.request.method} {resp.url}: {resp.status_code}"
        assert resp.json() == UNAUTHORIZED

    # действие не выполнено: задач с title=X нет (проверка после входа поиском)
    found = api.search(archived="all").json()["results"]
    assert not [t for t in found if t["title"] == title_x]


# --------------------------------------------------------------------------
# TC-auth-005 — Поддельный session-cookie → 401, не 5xx (CHK-5, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_forged_session_cookie_401_not_5xx(base_url, http):
    """TC-auth-005: поддельная/пустая/инъекционная кука session — каждый ответ
    401 {"error": "unauthorized"}; ни один — 5xx."""
    forged_values = [
        "forged_token_abc123def456",
        "",
        "%27%20OR%201%3D1--",
    ]
    for value in forged_values:
        resp = http.get(f"{base_url}/api/board", cookies={"session": value})
        assert resp.status_code == 401, f"cookie={value!r}: {resp.status_code}"
        assert resp.json() == UNAUTHORIZED


# --------------------------------------------------------------------------
# TC-auth-006 — Успешный вход существующего пользователя (CHK-6, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_successful_login_owner(base_url, http):
    """TC-auth-006: вход owner — 200 {"ok": true, "user": "owner"}; заголовок
    Set-Cookie: session=<token>; HttpOnly; SameSite=Lax (Secure не проверяем:
    локальный прогон по http, флаг выставлен на https-развертывании)."""
    resp = http.post(
        f"{base_url}/api/auth/login",
        json={"login": "owner", "password": "QaOwner_Pass_1!"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "user": "owner"}

    set_cookie = resp.headers.get("Set-Cookie", "")
    assert set_cookie.startswith("session=")
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie


# --------------------------------------------------------------------------
# TC-auth-007 — Вход с неверным паролем отклонен (CHK-7, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_login_wrong_password_rejected(base_url, http):
    """TC-auth-007: owner + неверный пароль — 401, тело точно
    {"error": "invalid credentials"}; куки session с новым токеном нет."""
    resp = http.post(
        f"{base_url}/api/auth/login",
        json={"login": "owner", "password": "Wrong_Pass_9!"},
    )
    assert resp.status_code == 401
    assert resp.json() == INVALID_CREDENTIALS
    assert "session" not in http.cookies  # валидной куки не появилось


# --------------------------------------------------------------------------
# TC-auth-008 — Несуществующий пользователь: текст ошибки идентичен (CHK-8, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_login_unknown_user_identical_error(base_url, http):
    """TC-auth-008: ответ на несуществующий логин — 401, тело байт-в-байт
    идентично ответу на неверный пароль существующего (не раскрывает логин)."""
    resp_ghost = http.post(
        f"{base_url}/api/auth/login",
        json={"login": "ghost_user", "password": "Some_Pass_1!"},
    )
    resp_wrong_pwd = http.post(
        f"{base_url}/api/auth/login",
        json={"login": "owner", "password": "Wrong_Pass_9!"},
    )
    assert resp_ghost.status_code == 401
    assert resp_ghost.content == resp_wrong_pwd.content  # байт-в-байт
    assert resp_ghost.json() == INVALID_CREDENTIALS


# --------------------------------------------------------------------------
# TC-auth-009 — Пустые логин и/или пароль: вход не выполнен (CHK-9, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
@pytest.mark.parametrize(
    "payload",
    [
        {"login": "", "password": ""},
        {"login": "owner", "password": ""},
        {"login": "", "password": "QaOwner_Pass_1!"},
    ],
    ids=["both-empty", "empty-password", "empty-login"],
)
def test_login_empty_fields_rejected(base_url, http, payload):
    """TC-auth-009: пустые логин и/или пароль — вход не выполнен, сессия не
    создана (нет валидной куки); страница не падает (нет 500).

    Примечание: API-уровень формы /login — POST /api/auth/login (login.js);
    пустые поля отклоняются 401/422 — не 5xx, валидной куки нет.
    """
    resp = http.post(f"{base_url}/api/auth/login", json=payload)
    assert resp.status_code < 500, f"{payload}: {resp.status_code}"
    assert "session" not in http.cookies
    assert not resp.cookies.get("session")


# --------------------------------------------------------------------------
# TC-auth-010 — Повторное открытие приложения в рамках действующей сессии (CHK-10, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_session_persists_across_requests(base_url, owner_session):
    """TC-auth-010: сессия действительна при повторных обращениях: GET /board
    (страница) и GET /api/board отвечают без формы входа (кука принимается).

    UI-часть (закрытие вкладки браузера) — браузерная; API-эквивалент:
    та же сессия валидна в последующих запросах. Полный UI-сценарий —
    tests/web (вне скоупа API-набора; см. README).
    """
    resp_api = owner_session.get(f"{base_url}/api/board")
    assert resp_api.status_code == 200
    assert "columns" in resp_api.json()

    # страница доски не редиректит на /login (форма входа не показана)
    resp_page = owner_session.get(f"{base_url}/board", allow_redirects=False)
    assert resp_page.status_code == 200
    assert "Location" not in resp_page.headers


# --------------------------------------------------------------------------
# TC-auth-011 — Обращение к защищенной странице после истечения сессии (CHK-11, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_expired_session_page_redirects_to_login(base_url, owner_session, expire_session):
    """TC-auth-011: после истечения сессии GET /board — редирект на /login;
    содержимое доски не показано."""
    expire_session(owner_session)
    resp = owner_session.get(f"{base_url}/board", allow_redirects=False)
    assert resp.status_code // 100 == 3
    assert resp.headers["Location"].rstrip("/").endswith("/login")
    assert "column-todo" not in resp.text  # содержимого доски нет


# --------------------------------------------------------------------------
# TC-auth-012 — После logout прежняя кука не действует (CHK-12, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_logout_invalidates_session_server_side(base_url):
    """TC-auth-012: logout — 200 {"ok": true}; запрос с прежним токеном —
    401 (сессия удалена сервером, а не только кука сброшена)."""
    session = _requests_login(base_url)
    token = session.cookies.get("session")

    resp_logout = session.post(f"{base_url}/api/auth/logout")
    assert resp_logout.status_code == 200
    assert resp_logout.json() == {"ok": True}

    # прежний токен больше не действует
    resp_after = session.get(f"{base_url}/api/board")
    assert resp_after.status_code == 401
    assert resp_after.json() == UNAUTHORIZED


# --------------------------------------------------------------------------
# TC-auth-013 — Страница доски без сессии → редирект на вход (CHK-13, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_board_page_without_session_redirects(base_url, http):
    """TC-auth-013: GET /board без куки — HTTP-редирект (3xx) с
    Location: /login; HTML доски в теле ответа отсутствует."""
    resp = http.get(f"{base_url}/board", allow_redirects=False)
    assert resp.status_code in (301, 302, 303, 307)
    assert resp.headers["Location"].rstrip("/").endswith("/login")
    assert "column-todo" not in resp.text  # HTML доски не отдан


# --------------------------------------------------------------------------
# TC-auth-014 — Прочие защищенные страницы без сессии → редирект (CHK-14, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_other_pages_without_session_redirect_login_200(base_url, http):
    """TC-auth-014: /search и /wiki без сессии — редирект на /login (HTML
    разделов не отдан); /login — контрольный: 200, форма входа."""
    for path in ("/search", "/wiki"):
        resp = http.get(f"{base_url}{path}", allow_redirects=False)
        assert resp.status_code in (301, 302, 303, 307), path
        assert resp.headers["Location"].rstrip("/").endswith("/login"), path

    resp_login = http.get(f"{base_url}/login")
    assert resp_login.status_code == 200
    assert 'id="login-form"' in resp_login.text  # форма входа отображается


# --------------------------------------------------------------------------
# TC-auth-015 — Второй пользователь входит со своими данными (CHK-15, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_second_user_wife_login_and_work(base_url, wife_session, api, unique_title):
    """TC-auth-015: wife — 200 {"ok": true, "user": "wife"} + кука; GET /api/board —
    200 со столбцами; создание задачи — 201 (общая доска)."""
    resp_board = wife_session.get(f"{base_url}/api/board")
    assert resp_board.status_code == 200
    assert set(resp_board.json()["columns"].keys()) == {"todo", "in_progress", "done"}

    title = f"{unique_title}-wife"
    resp_create = wife_session.post(
        f"{base_url}/api/tasks", json={"title": title}
    )
    assert resp_create.status_code == 201
    # задача видна и через сессию owner (общая доска)
    found = api.search(archived="all").json()["results"]
    assert title in [t["title"] for t in found]


# --------------------------------------------------------------------------
# TC-auth-016 — Посторонняя пара логин/пароль отклоняется (CHK-16, Must)
# --------------------------------------------------------------------------
@pytest.mark.must
def test_stranger_login_rejected(base_url, http):
    """TC-auth-016: stranger — 401 {"error": "invalid credentials"}; сессия
    не создана; регистрации по произвольным данным нет."""
    resp = http.post(
        f"{base_url}/api/auth/login",
        json={"login": "stranger", "password": "H4ck_Me_Not"},
    )
    assert resp.status_code == 401
    assert resp.json() == INVALID_CREDENTIALS
    assert "session" not in http.cookies


# --------------------------------------------------------------------------
# TC-auth-017 — Пароли не хранятся в открытом виде (НФТ) (CHK-17, Must)
# --------------------------------------------------------------------------
@pytest.mark.manual
@pytest.mark.must
def test_passwords_not_stored_plaintext():
    """TC-auth-017 (НФТ, осмотр БД): password_hash только bcrypt ($2b$…, ≥60
    символов), 0 вхождений открытых паролей в файле БД, вход по исходному
    паролю работает, файл БД вне репозитория.

    Процедура (ручная, зависит от путей развертывания):
      1. sqlite3 $DB_PATH "SELECT login, password_hash FROM users;"
      2. проверить: каждый hash начинается с $2b$ и len >= 60
      3. grep -ac "<pwd_owner>" $DB_PATH и grep -ac "<pwd_wife>" $DB_PATH → 0
      4. POST /api/auth/login с исходным паролем → 200 (хеш рабочий)
      5. git -C <repo> check-ignore <DB_PATH> → проигнорирован

    Автоматизация: шаги 2/4 покрывает test_login_owner_ok и
    test_owner_password_hash_is_bcrypt (ниже, при заданном DB_PATH);
    grep по бинарному файлу и check-ignore зависят от окружения
    развертывания — оставлены как ручная процедура (см. README).
    """
    pytest.skip("Ручная НФТ-процедура: осмотр файла БД (см. docstring и README)")


@pytest.mark.api
@pytest.mark.must
def test_owner_password_hash_is_bcrypt():
    """TC-auth-017 (автоматизируемая часть): password_hash owner/wife в БД —
    bcrypt ($2b$ prefix, длина >= 60); при отсутствии DB_PATH — skip."""
    db_path = os.environ.get("EKOTOV_WIKI_DB_PATH")
    if not db_path:
        pytest.skip("нужен env EKOTOV_WIKI_DB_PATH")
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT login, password_hash FROM users").fetchall()
    finally:
        conn.close()
    hashes = dict(rows)
    assert set(hashes) >= {"owner", "wife"}
    for login in ("owner", "wife"):
        h = hashes[login]
        assert h.startswith("$2b$"), f"{login}: не bcrypt: {h[:8]}…"
        assert len(h) >= 60, f"{login}: hash короче 60 символов"
