# TC-wiki-414 — WYSIWYG-редактор: тулбар, undo/redo, сохранение, WYSIWYG-совпадение (FR-110, ОГР-8, NFR-33)

- **Change:** add-wiki
- **Источник:** wiki (ADDED): Requirement «WYSIWYG-редактор страниц» (решение 2, FR-110, ОГР-8, NFR-33) — Scenario «Тулбар применяет форматирование», «Undo/redo», «Редактор без внешних зависимостей»; design §5, мокап wiki-editor.html; CHK-wiki-15, CHK-wiki-16, CHK-wiki-17, CHK-wiki-18
- **Тип:** ФТ, UI-редактор + кроссбраузерность | **Приоритет:** Must
- **Предусловия:** авторизованный пользователь; страница в режиме `?create=1` / `?edit=1`; Chromium и Firefox (для кроссбраузерной части — стенд compose.test)
- **Шаги:**
  1. Применить каждый инструмент тулбара к выделению: H1–H3, B/I/U, нумерованный/маркированный список, цитата, код-блок, ссылка, таблица 3×3 → форматирование в поле редактирования; aria-pressed у кнопок-состояний.
  2. Undo/redo тулбара → правка отменяется / повторно применяется.
  3. «Сохранить» → POST (создание) / PUT (правка) → редирект на статью; сохраненный вид = отредактированному (WYSIWYG).
  4. Повторное `?edit=1` → GET заполняет редактор → правка → сохранение → правка в статье.
  5. Сетевой контроль: внешних CDN-запросов нет; кроссбраузерно (Chromium 153 / Firefox 155) — тот же сценарий, 0 JS-ошибок.
  6. Негатив: `javascript:` в диалоге ссылки → отклонен.
- **Ожидаемый результат:** тулбар полностью функционален, WYSIWYG-совпадение вида, undo/redo работают, редактор vanilla без внешних зависимостей, работает в обоих браузерах. Факт прогона 4.2: green (TC-wiki-301…304, 307/308 в составе 29 passed; DV 04-editor.png); 4.4 кроссбраузер: 16/16 на браузер, 0 pageerror.
- **Автотест:** tests/web/test_p15_wiki_editor.py::test_toolbar_formats_change_tags (TC-wiki-301), ::test_toolbar_lists_and_undo_redo (TC-wiki-302), ::test_toolbar_inserts_table_3x3 (TC-wiki-303), ::test_link_javascript_scheme_rejected (TC-wiki-304), ::test_save_edit_puts_new_version_and_redirects (TC-wiki-308) + tests/api/test_sanitize.py::test_toolbar_markup_passes, ::test_full_toolbar_document_roundtrip; кроссбраузерность — прогон 4.4 REPORT-4.4 §(в) (скрипт)
- **Статус:** **approved** (QA 4.2 прогнан: 29 passed / 0 failed; QA 4.4: кроссбраузерность PASS)
