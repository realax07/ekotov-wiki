# Impact-анализ: p12-rich-tools

> Каноническая карта J58: openspec/changes/p12-rich-tools/impact.md (этот документ — проекция для ворот H5, содержание идентично).

**Затронуто:**
- backend/app/sanitize.py (словарь data-атрибутов, глубина ≤5, br→\n в code, unwrap table-in-table)
- frontend/static/js/wiki/rich/* (5 инструментов), editor.js (гейты вставки), wiki.css
- static_v: бамп p12-rich-1 (backend/app/pages.py, R7)
- contracts/openapi.json: НЕ меняется (новых эндпоинтов нет)
- deploy.sh/RUNBOOK: не затрагиваются (новых сервисов/миграций нет)
- тесты: test_sanitize (+15), test_wiki_rich, test_rich_tools, test_p12_rich_qa
