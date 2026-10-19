"""TC-smoke-005: страница wiki через nginx (домен wiki, эшелон 2).

Представитель домена wiki: /wiki анонимно → редирект на /login, с сессией →
200 HTML. Read-only.
"""

import requests


def test_wiki_page_via_nginx(contour_url, owner_session):
    """TC-smoke-005: GET /wiki — анонимно 302 → /login, с сессией 200 text/html."""
    anon = requests.get(f"{contour_url}/wiki", allow_redirects=False, timeout=10)
    assert anon.status_code in (301, 302, 303, 307), (
        f"анонимный /wiki: {anon.status_code} (ожидался редирект на /login)"
    )

    resp = owner_session.get(f"{contour_url}/wiki", timeout=10)
    assert resp.status_code == 200, f"/wiki с сессией: {resp.status_code}"
    assert resp.headers.get("content-type", "").startswith("text/html"), (
        f"/wiki: content-type {resp.headers.get('content-type')}"
    )
