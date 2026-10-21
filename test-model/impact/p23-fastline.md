# Impact-анализ: p23-fastline

> Каноническая карта J58: openspec/changes/p23-fastline/impact.md (проекция для ворот H5).

**Затронуто:**
- frontend/static/js/board/ (cards/state/task-form/api/dnd_helpers), board.html, board.css — зона FASTLINE, гейты вставки, DnD
- backend/app/pages.py — static_v p23-fastline-1 (IR-03)
- backend board.py/tasks.py — НЕ меняются (ограничения уже серверные: 409/422)
- contracts/openapi.json — НЕ меняется
- deploy.sh/RUNBOOK, миграции — не затрагиваются
- тесты: test_board_fastline.py (новый), test_fastline_ui.py, test_r3_dnd_ui.py, test_p12_ui_polish_r8.py (правки), test_p23_qa_wave4.py (новый), хелперы conftest/dnd_helpers/pages
