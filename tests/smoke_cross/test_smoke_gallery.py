"""TC-smoke-006: страница gallery через nginx (домен gallery, эшелон 2).

Представитель домена gallery: /gallery с сессией → 200 HTML (страницу отдает
app, данные — images:8379 через роутинг nginx). Read-only.
"""


def test_gallery_page_via_nginx(contour_url, owner_session):
    """TC-smoke-006: GET /gallery с сессией — 200 text/html."""
    resp = owner_session.get(f"{contour_url}/gallery", timeout=10)
    assert resp.status_code == 200, f"/gallery: {resp.status_code}"
    assert resp.headers.get("content-type", "").startswith("text/html"), (
        f"/gallery: content-type {resp.headers.get('content-type')}"
    )
