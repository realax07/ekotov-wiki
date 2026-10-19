"""TC-smoke-003/004: авторизация и поиск через nginx (домен auth-search).

Представитель домена auth-search на смоук-эшелоне: вход по seed-кредам,
негативы 401 и поисковый эндпоинт (search:8378 через роутинг nginx).
Read-only: логин создает только сессию.
"""

import requests


def test_auth_login_ok_and_negative(contour_url, anon_http, owner_creds):
    """TC-smoke-003: login owner → 200 + кука session; неверный пароль → 401;
    анонимный запрос к API → 401."""
    login, password = owner_creds
    resp = anon_http.post(
        f"{contour_url}/api/auth/login",
        json={"login": login, "password": password},
    )
    assert resp.status_code == 200, f"login owner: {resp.status_code}"
    assert anon_http.cookies.get("session"), "нет куки session после входа"

    bad = requests.Session()
    bad_resp = bad.post(
        f"{contour_url}/api/auth/login",
        json={"login": "owner", "password": "wrong-password"},
    )
    assert bad_resp.status_code == 401, (
        f"неверный пароль: {bad_resp.status_code}"
    )

    anon_resp = requests.Session().get(f"{contour_url}/api/tasks", timeout=5)
    assert anon_resp.status_code == 401, (
        f"анонимный /api/tasks: {anon_resp.status_code}"
    )


def test_search_via_nginx(contour_url, owner_session):
    """TC-smoke-004: GET /api/search через nginx (→ search:8378) с сессией —
    200 и контрактный формат {"results": [...]}."""
    resp = owner_session.get(
        f"{contour_url}/api/search", params={"q": "QAT"}, timeout=10
    )
    assert resp.status_code == 200, f"поиск: {resp.status_code} {resp.text[:100]}"
    assert "results" in resp.json(), f"нет ключа results: {resp.text[:100]}"
