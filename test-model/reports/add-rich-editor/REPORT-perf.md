# REPORT-perf: замер NFR-37 (50 rich-блоков ≤ 2 с, ОВ-4)

Замер: tests/web/test_rich_perf_50_blocks.py (стенд conftest,
chromium; время goto → видимый рендер последнего блока).
Фикстура: tests/api/fixtures/rich_perf/page_50_blocks.content.txt

| Дата (UTC) | Время, с | Порог | Блоки (table/columns/callout/aside/spoiler/code) |
|---|---|---|---|
| 2026-10-16 10:47 | 0.26 (PASS) | 2.0 | 9/9/8/8/8/8 |
| 2026-10-16 12:27 | 0.24 (PASS) | 2.0 | 9/9/8/8/8/8 |
| 2026-10-16 13:53 | 0.20 (PASS) | 2.0 | 9/9/8/8/8/8 |
| 2026-10-16 13:58 | 0.18 (PASS) | 2.0 | 9/9/8/8/8/8 |
| 2026-10-16 15:38 | 0.32 (PASS) | 2.0 | 9/9/8/8/8/8 |
