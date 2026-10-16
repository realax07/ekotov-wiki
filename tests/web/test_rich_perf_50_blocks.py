"""Perf-чек NFR-37 (change add-rich-editor, tasks.md 2.6; design §5): страница
с 50 rich-блоками (микс типов) открывается на стенде ≤ 2 с (порог
подтвержден Заказчиком, ОВ-4).

Замер: время от навигации до видимого рендера тела статьи с rich-блоками
(стенд conftest: uvicorn app + static, tmp-БД). Результат пишется в
test-model/reports/add-rich-editor/REPORT-perf.md (append-only по датам
прогонов — история не переписывается, AGENTS.md #7).

Фикстура контента: tests/api/fixtures/rich_perf/page_50_blocks.content.txt
(50 блоков: таблицы ×8, колонки ×8, callout ×9, врезки ×8, спойлеры ×8,
код ×9).

Запуск (из корня репозитория): python -m pytest tests/web/test_rich_perf_50_blocks.py -q
"""

import os
import time
from datetime import datetime
from pathlib import Path

import pytest
import requests
from playwright.sync_api import expect

_REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_BACKEND_DIR = _REPO_ROOT / "backend"

pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.should]

PERF_THRESHOLD_SECONDS = 2.0
FIXTURE = _REPO_ROOT / "tests/api/fixtures/rich_perf/page_50_blocks.content.txt"
REPORT = _REPO_ROOT / "test-model/reports/add-rich-editor/REPORT-perf.md"


@pytest.fixture(scope="session", autouse=True)
def perf_stand_schema(web_server):
    db_path = web_server.get("db_path") if isinstance(web_server, dict) else None
    if not db_path:
        return
    import subprocess as sp
    import sys

    env = dict(os.environ, DB_PATH=db_path, SECRET_KEY="web-tests-secret-key")
    env.pop("PYTHONPATH", None)
    sp.run(
        [sys.executable, "-m", "app.migrate_wiki"],
        cwd=str(REPO_BACKEND_DIR), env=env, capture_output=True, text=True,
    )


def test_page_with_50_rich_blocks_opens_under_2s(
    logged_in_page, web_base_url, web_owner_session
):
    """TC-rich-perf-001 (NFR-37): открытие страницы с 50 rich-блоками ≤ 2 с."""
    content = FIXTURE.read_text(encoding="utf-8")
    resp = web_owner_session.post(
        f"{web_base_url}/api/wiki/pages",
        json={"title": "QAT-rich-perf-50", "content": content},
    )
    assert resp.status_code == 201, resp.text
    page_id = resp.json()["id"]
    try:
        page = logged_in_page
        started = time.monotonic()
        page.goto(f"{web_base_url}/wiki/{page_id}")
        body = page.locator(".article-body")
        expect(body).to_be_visible()
        # рендер rich-блоков завершился: последний блок типа «код» на месте
        expect(body.locator(".rich-code").last).to_be_visible()
        expect(body.locator(".rich-callout").last).to_be_visible()
        elapsed = time.monotonic() - started

        blocks = {
            "table": body.locator(".rich-table").count(),
            "columns": body.locator(".rich-columns").count(),
            "callout": body.locator(".rich-callout").count(),
            "aside": body.locator(".rich-aside").count(),
            "spoiler": body.locator(".rich-spoiler").count(),
            "code": body.locator(".rich-code").count(),
        }
        assert elapsed <= PERF_THRESHOLD_SECONDS, (
            f"открытие страницы с 50 rich-блоками: {elapsed:.2f} с > "
            f"{PERF_THRESHOLD_SECONDS} с (NFR-37)"
        )
        _write_report(elapsed, blocks)
    finally:
        web_owner_session.delete(f"{web_base_url}/api/wiki/pages/{page_id}")


def _write_report(elapsed: float, blocks: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    header_needed = not REPORT.exists()
    with open(REPORT, "a", encoding="utf-8") as fh:
        if header_needed:
            fh.write(
                "# REPORT-perf: замер NFR-37 (50 rich-блоков ≤ 2 с, ОВ-4)\n\n"
                "Замер: tests/web/test_rich_perf_50_blocks.py (стенд conftest,\n"
                "chromium; время goto → видимый рендер последнего блока).\n"
                "Фикстура: tests/api/fixtures/rich_perf/page_50_blocks.content.txt\n\n"
                "| Дата (UTC) | Время, с | Порог | Блоки (table/columns/callout/aside/spoiler/code) |\n"
                "|---|---|---|---|\n"
            )
        stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        mix = "/".join(str(blocks[k]) for k in ("table", "columns", "callout", "aside", "spoiler", "code"))
        verdict = "PASS" if elapsed <= PERF_THRESHOLD_SECONDS else "FAIL"
        fh.write(f"| {stamp} | {elapsed:.2f} ({verdict}) | {PERF_THRESHOLD_SECONDS} | {mix} |\n")
