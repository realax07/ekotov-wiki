"""Рендер мокапов P12 rich-редактора: tool-N-{edit,view}.png из tool-N-*.html."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).parent
TOOLS = ["tool-1-spoiler", "tool-2-code", "tool-3-states", "tool-4-headings", "tool-5-table"]
TOOLS = ["tool-1-spoiler", "tool-2-code", "tool-3-tabs", "tool-4-headings", "tool-5-table"]


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1180, "height": 900}, device_scale_factor=2)
        for tool in TOOLS:
            src = HERE / f"{tool}.html"
            await page.goto(src.as_uri())
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(150)
            for state in ("edit", "view"):
                el = page.locator(f"#{state}")
                out = HERE / f"{tool.rsplit('-', 0)[0] if False else tool}-{state}.png"
                out = HERE / f"{tool}-{state}.png"
                await el.screenshot(path=str(out))
                print("saved", out.name)
        await browser.close()


asyncio.run(main())
