"""DV: пустое состояние + 409-баннер + success-баннер отката (динамические состояния)."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8099"
REPO = Path("/home/openclaw/ekotov-wiki")
OUT = REPO / "test-model/reviews/add-wiki/screenshots"

MIME = {".css": "text/css", ".js": "text/javascript"}

def serve_static(route):
    rel = route.request.url.split("/static/", 1)[1].split("?")[0]
    path = REPO / "frontend/static" / rel
    if path.exists():
        route.fulfill(body=path.read_bytes(), content_type=MIME.get(path.suffix, "application/octet-stream"))
    else:
        route.fulfill(status=404, body="not found")

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.route("**/static/**", serve_static)
    page = ctx.new_page()

    page.goto(BASE + "/login")
    page.fill("#login", "owner")
    page.fill("#password", "dv-pass-123")
    page.click("#login-submit")
    page.wait_for_url("**/board", timeout=10000)

    # --- Пустое состояние: перехват /api/wiki/pages -> [] ---
    page.route("**/api/wiki/pages", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"pages": []})))
    page.goto(BASE + "/wiki")
    page.wait_for_timeout(600)
    page.screenshot(path=f"{OUT}/13-empty-state.png")
    empty_h = page.evaluate("(document.querySelector('.wiki-empty h2')||{}).textContent")
    empty_btn = page.evaluate("(document.querySelector('.wiki-empty .wiki-create')||{}).textContent")
    print("EMPTY:", empty_h, "|", empty_btn)
    page.unroute("**/api/wiki/pages")

    # --- 409-баннер удаления: перехват DELETE -> 409 ---
    page.goto(BASE + "/wiki/3")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)

    def on_pages(route):
        if route.request.method == "DELETE":
            route.fulfill(status=409, content_type="application/json",
                          body=json.dumps({"error": "conflict"}))
        else:
            route.continue_()
    page.route("**/api/wiki/pages/3", on_pages)
    page.locator(".article-actions .btn-danger").click()
    page.wait_for_timeout(200)
    page.locator(".confirm .btn-danger-solid").click()
    page.wait_for_timeout(400)
    page.screenshot(path=f"{OUT}/14-409-banner.png")
    banner = page.evaluate("(document.querySelector('.error-banner')||{}).textContent")
    print("409 BANNER:", banner)
    page.unroute("**/api/wiki/pages/3")

    # --- success-баннер отката: перехват revert ---
    page.goto(BASE + "/wiki/1/history")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    page.route("**/api/wiki/pages/1/revert/**", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"new_version_id": 1})))
    page.locator(".version-item .btn-secondary", has_text="Откатить").last.click()
    page.wait_for_timeout(200)
    page.locator(".confirm .btn-primary").click()
    page.wait_for_timeout(900)
    page.screenshot(path=f"{OUT}/15-success-banner.png")
    sb = page.evaluate("(document.getElementById('wiki-history-banner')||{}).textContent")
    sb_cls = page.evaluate("(document.getElementById('wiki-history-banner')||{}).className")
    print("SUCCESS:", sb, "|", sb_cls)
    browser.close()
print("DONE2")
