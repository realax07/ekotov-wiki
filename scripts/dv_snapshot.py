#!/usr/bin/env python3
"""J25: снапшот ас-ис состояния UI прода (live-DOM) для дизайнера и design_validator.

Зачем: макеты дизайнера описывают ЦЕЛЕВОЕ состояние; ас-ис — это прод.
Change с UI-дельтой начинается со снапшота ас-ис (что есть) + мокап-дельты
(что будет) — так СА/дизайнер видят разрыв, а design_validator после
реализации сверяет код против мокапов.

Что снимает: для заданных страниц и вьюпортов — структуру DOM (теги, классы),
computed styles ключевых свойств, геометрию (boundingBox) видимых элементов.
Выход: JSON-артефакт design/as-is/snapshot-<label>-<дата>.json (label —
имя окружения: prod/stage/local).

Использование:
  python3 scripts/dv_snapshot.py --base-url https://... --label prod \
      --pages /login /gallery --width 375 --height 812

Логин (если страница требует сессии): WIKI_SNAPSHOT_LOGIN / WIKI_SNAPSHOT_PASS
в окружении; без них снимаются только публичные страницы.

Селекторы снапшота: все элементы с классом (класс = контракт дизайн-системы),
для каждого — tag, classes, rect, computed (display, position, z-index,
font-size, color, background-color, gap, padding, flex-direction).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from urllib.parse import urljoin

SNAPSHOT_JS = """
() => {
  const props = ["display","position","zIndex","fontSize","color",
                 "backgroundColor","gap","padding","flexDirection","overflow"];
  const out = [];
  document.querySelectorAll("*").forEach(el => {
    const cls = (el.classList && el.classList.length) ? [...el.classList] : [];
    if (!cls.length) return;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    const cs = getComputedStyle(el);
    const computed = {};
    for (const p of props) computed[p] = cs.getPropertyValue(
        p.replace(/[A-Z]/g, m => "-" + m.toLowerCase()));
    out.push({
      tag: el.tagName.toLowerCase(),
      classes: cls,
      rect: {x: +r.x.toFixed(1), y: +r.y.toFixed(1),
             w: +r.width.toFixed(1), h: +r.height.toFixed(1)},
      computed,
    });
  });
  return {url: location.pathname, viewport: {w: innerWidth, h: innerHeight},
          elements: out};
}
"""


def snapshot_page(page, url: str) -> dict:
    page.goto(urljoin(_base, url))
    page.wait_for_load_state("networkidle")
    data = page.evaluate(SNAPSHOT_JS)
    data["requested_url"] = url  # редирект (напр. /gallery → /login без сессии) не путаем
    return data


def main() -> int:
    global _base
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--label", default="prod", help="метка окружения (prod/stage/local)")
    ap.add_argument("--pages", nargs="+", default=["/login"],
                    help="пути страниц для снапшота")
    ap.add_argument("--width", type=int, default=375)
    ap.add_argument("--height", type=int, default=812)
    ap.add_argument("--mobile", action="store_true", default=True)
    ap.add_argument("--out", default="", help="путь JSON (по умолчанию design/as-is/)")
    args = ap.parse_args()
    _base = args.base_url.rstrip("/")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("dv_snapshot: нужен playwright (pip install playwright)")
        return 1

    shots = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": args.width, "height": args.height},
            has_touch=args.mobile, is_mobile=args.mobile,
            device_scale_factor=2)
        page = ctx.new_page()

        login, password = os.environ.get("WIKI_SNAPSHOT_LOGIN"), os.environ.get("WIKI_SNAPSHOT_PASS")
        if login and password:
            page.goto(urljoin(_base, "/login"))
            page.get_by_label("Логин").fill(login)
            page.get_by_label("Пароль").fill(password)
            page.get_by_role("button", name="Войти").click()
            page.wait_for_load_state("networkidle")

        for u in args.pages:
            try:
                shots.append(snapshot_page(page, u))
                print(f"dv_snapshot: {u} — ok ({len(shots[-1]['elements'])} эл-тов)")
            except Exception as e:
                print(f"dv_snapshot: {u} — FAIL: {e}", file=sys.stderr)
                shots.append({"url": u, "error": str(e)})
        browser.close()

    doc = {
        "schema": "as-is-snapshot/1",
        "label": args.label,
        "created": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "base_url": _base,
        "pages": shots,
    }
    out = Path(args.out) if args.out else (
        Path("design/as-is") / f"snapshot-{args.label}-{_dt.date.today():%Y%m%d}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"dv_snapshot: {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
