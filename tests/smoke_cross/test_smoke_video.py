"""TC-smoke-007: страница video через nginx (домен video, эшелон 2).

Представитель домена video: /video с сессией → 200 HTML (страницу отдает app,
видео-данные — video:8380 через роутинг nginx /api/videos*). Read-only.
"""


def test_video_page_via_nginx(contour_url, owner_session):
    """TC-smoke-007: GET /video с сессией — 200 text/html."""
    resp = owner_session.get(f"{contour_url}/video", timeout=10)
    assert resp.status_code == 200, f"/video: {resp.status_code}"
    assert resp.headers.get("content-type", "").startswith("text/html"), (
        f"/video: content-type {resp.headers.get('content-type')}"
    )
