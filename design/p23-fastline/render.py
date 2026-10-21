#!/usr/bin/env python3
"""Рендер мокапов P23: variant-{a,b}-{empty,tasks,dnd}.png (1440×900).

Запуск из этой папки: ../venvs/wiki/bin/python render.py
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).parent
PAGES = [
    "variant-a-empty",
    "variant-a-tasks",
    "variant-a-dnd",
    "variant-b-empty",
    "variant-b-tasks",
    "variant-b-dnd",
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
