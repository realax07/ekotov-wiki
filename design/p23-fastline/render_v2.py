#!/usr/bin/env python3
"""Рендер мокапов P23 v2: v2-*.png (1440×900, @2x).

Запуск из этой папки: ../../venvs/wiki/bin/python render_v2.py
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).parent
PAGES = [
    "v2-empty",
    "v2-busy",
    "v2-blocked",
    "v2-dnd-move",
    "v2-dnd-blocked",
]


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(
            viewport={"width": 1440, "height": 900}, device_scale_factor=2
        )
        for name in PAGES:
            src = HERE / f"{name}.html"
            await page.goto(src.as_uri())
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(150)
            await page.screenshot(path=str(HERE / f"{name}.png"))
            print("saved", f"{name}.png")
        await browser.close()


asyncio.run(main())
