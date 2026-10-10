"""DV-сверка волны 3 add-wiki: playwright-снимки фактической верстки (review-001-design).
Статика (/static/*) раздается через route-перехват с диска (в проде — nginx)."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8099"
REPO = Path("/home/openclaw/ekotov-wiki")
OUT = REPO / "test-model/reviews/add-wiki/screenshots"
TMP = Path("/tmp/dv")
os.makedirs(OUT, exist_ok=True)
os.makedirs(TMP, exist_ok=True)

MIME = {
    ".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml",
    ".png": "image/png", ".ico": "image/x-icon",
}

def serve_static(route):
    url = route.request.url
    rel = url.split("/static/", 1)[1].split("?")[0]
    path = REPO / "frontend/static" / rel
    if path.exists():
        route.fulfill(
            body=path.read_bytes(),
            content_type=MIME.get(path.suffix, "application/octet-stream"),
        )
    else:
        route.fulfill(status=404, body="not found")

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.route("**/static/**", serve_static)
    page = ctx.new_page()
    msgs = []
    page.on("console", lambda m: msgs.append((m.type, m.text[:150])))
    page.on("pageerror", lambda e: msgs.append(("pageerror", str(e)[:250])))

    page.goto(BASE + "/login")
    page.fill("#login", "owner")
    page.fill("#password", "dv-pass-123")
    page.click("#login-submit")
    page.wait_for_url("**/board", timeout=10000)
    print("after login url:", page.url)

    page.goto(BASE + "/wiki")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(400)
    page.screenshot(path=f"{OUT}/01-tree.png", full_page=True)
    tree_html = page.evaluate("document.querySelector('aside.wiki-tree').outerHTML")
    (TMP / "-tree.html").write_text(tree_html)
    print("TREE_LEN", len(tree_html))

    page.fill("#wiki-search", "смета")
    page.wait_for_timeout(800)
    page.screenshot(path=f"{OUT}/02-search.png", full_page=True)
    (TMP / "-search.html").write_text(
        page.evaluate("document.getElementById('wiki-search-results').outerHTML"))
    print("COUNTER:", page.evaluate("document.querySelector('.filter-count').textContent"))

    page.goto(BASE + "/wiki/1")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(700)
    page.screenshot(path=f"{OUT}/03-article.png", full_page=True)
    (TMP / "-article.html").write_text(
        page.evaluate("(document.getElementById('wiki-article')||{}).outerHTML + '|||BC|||' + ((document.querySelector('nav.wiki-breadcrumb')||{}).outerHTML||'')"))
    print("breadcrumb:", page.evaluate("[...document.querySelectorAll('nav.wiki-breadcrumb li')].map(l=>l.textContent)"))
    print("meta:", page.evaluate("(document.querySelector('.article-meta')||{}).textContent"))

    page.goto(BASE + "/wiki/3")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    print("delete visible:", page.locator(".article-actions .btn-danger").is_visible())
    page.locator(".article-actions .btn-danger").click()
    page.wait_for_timeout(250)
    page.screenshot(path=f"{OUT}/04-delete-dialog.png")
    (TMP / "-dialog.html").write_text(
        page.evaluate("(document.querySelector('.confirm-backdrop')||{}).outerHTML||''"))
    print("dialog focus on:", page.evaluate("document.activeElement && document.activeElement.className"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(150)
    print("dialog closed by Esc:", page.evaluate("!document.querySelector('.confirm-backdrop')"))

    page.goto(BASE + "/wiki/1")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    print("page1 delete hidden:", page.evaluate("(() => { const b=document.querySelector('.article-actions .btn-danger'); return !b || b.hidden; })()"))

    page.goto(BASE + "/wiki/1?edit=1")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(700)
    page.screenshot(path=f"{OUT}/05-editor.png", full_page=True)
    (TMP / "-editor.html").write_text(
        page.evaluate("(document.getElementById('wiki-editor')||{}).outerHTML"))
    print("editor h1:", page.evaluate("(document.querySelector('#wiki-editor h1')||{}).textContent"))

    page.locator("#wiki-editor .editor-area").click()
    page.keyboard.type("test")
    page.keyboard.press("Home")
    page.keyboard.down("Shift")
    page.keyboard.press("End")
    page.keyboard.up("Shift")
    page.locator("#wiki-editor .tb-btn[aria-label='Полужирный']").click()
    page.wait_for_timeout(150)
    print("bold pressed:", page.evaluate("(document.querySelector('#wiki-editor .tb-btn[aria-label=Полужирный]')||{}).getAttribute && document.querySelector('#wiki-editor .tb-btn[aria-label=Полужирный]').getAttribute('aria-pressed')"))
    page.screenshot(path=f"{OUT}/05b-editor-pressed.png")

    page.locator("#wiki-editor .tb-btn[aria-label='Изображение']").click()
    page.wait_for_timeout(600)
    page.screenshot(path=f"{OUT}/05c-image-dialog.png")
    print("img dialog:", page.evaluate("!!document.querySelector('.editor-img-dialog')"))
    print("radio labels:", page.evaluate("[...document.querySelectorAll('.editor-img-dialog .radio-row label')].map(l=>l.textContent.trim())"))
    page.locator(".editor-img-dialog .dialog-actions .btn-secondary").click()
    page.wait_for_timeout(200)

    page.locator("#wiki-editor .tb-btn[aria-label='Ссылка']").click()
    page.wait_for_timeout(250)
    print("link dialog:", page.evaluate("!!document.querySelector('.editor-link-dialog')"))
    page.screenshot(path=f"{OUT}/05d-link-dialog.png")
    page.locator(".editor-link-dialog .dialog-actions .btn-secondary").click()

    page.fill("#page-title", "")
    page.locator("#wiki-editor .btn-primary").click()
    page.wait_for_timeout(250)
    page.screenshot(path=f"{OUT}/06-editor-error.png")
    print("EDITOR_ERR:", page.evaluate("(document.querySelector('#wiki-editor .error-banner')||{}).textContent"))

    page.goto(BASE + "/wiki/1/history")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(900)
    page.screenshot(path=f"{OUT}/07-history.png", full_page=True)
    (TMP / "-history.html").write_text(
        page.evaluate("(document.getElementById('wiki-history')||{}).outerHTML"))
    print("history subtitle:", page.evaluate("(document.getElementById('wiki-history-subtitle')||{}).textContent"))
    print("pill:", page.evaluate("(document.querySelector('.pill-current')||{}).textContent"))
    print("first item buttons:", page.evaluate("document.querySelectorAll('.version-item')[0].querySelectorAll('button').length"))
    print("ro-banner:", page.evaluate("(document.querySelector('.readonly-banner')||{}).textContent"))

    page.locator(".version-item .btn-secondary", has_text="Откатить").last.click()
    page.wait_for_timeout(250)
    page.screenshot(path=f"{OUT}/08-revert-dialog.png")
    print("revert dialog text:", page.evaluate("(document.querySelector('.confirm p')||{}).textContent"))
    print("revert focus:", page.evaluate("document.activeElement && document.activeElement.textContent"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(150)
    print("revert closed:", page.evaluate("!document.querySelector('.confirm-backdrop')"))

    for w, name in ((800, "09-history-880"), (470, "10-history-470")):
        page.set_viewport_size({"width": w, "height": 900})
        page.wait_for_timeout(250)
        page.screenshot(path=f"{OUT}/{name}.png", full_page=True)

    page.goto(BASE + "/wiki")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    page.set_viewport_size({"width": 470, "height": 900})
    page.wait_for_timeout(250)
    page.screenshot(path=f"{OUT}/11-tree-470.png", full_page=True)
    page.set_viewport_size({"width": 800, "height": 900})
    page.wait_for_timeout(250)
    page.screenshot(path=f"{OUT}/12-tree-800.png")

    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(300)
    (TMP / "-aria.txt").write_text(page.locator("main").aria_snapshot())

    print("--- console messages ---")
    for t, m in msgs:
        print(t, m)
    browser.close()
print("DONE")
