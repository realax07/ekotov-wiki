# REPORT-perf: замер NFR-37 (50 rich-блоков ≤ 2 с, ОВ-4)

Замер: tests/web/test_rich_perf_50_blocks.py (стенд conftest,
chromium; время goto → видимый рендер последнего блока).
Фикстура: tests/api/fixtures/rich_perf/page_50_blocks.content.txt

| Дата (UTC) | Время, с | Порог | Блоки (table/columns/callout/aside/spoiler/code) |
|---|---|---|---|
| 2026-10-16 10:47 | 0.26 (PASS) | 2.0 | 9/9/8/8/8/8 |
