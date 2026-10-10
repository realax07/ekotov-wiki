# TC-wiki-417 — История версий и откат: список от новых к старым, read-only, откат = новая версия (FR-113, решение 6)

- **Change:** add-wiki
- **Источник:** wiki (ADDED): Requirement «История версий и откат» (решение 6, FR-113) — Scenario «Список версий от новых к старым», «Просмотр версии read-only», «Откат создает новую версию»; design §6, мокап wiki-history.html; CHK-wiki-23, CHK-wiki-24, CHK-wiki-25
- **Тип:** ФТ, UI + данные | **Приоритет:** Must
- **Предусловия:** авторизованный пользователь; страница с версиями V1, V2, V3 от разных авторов (V3 — последняя)
- **Шаги:**
  1. Открыть /wiki/{id}/history → h1 «История версий», подзаголовок «N версий · от новых к старым…»; список: номер версии, автор, дата-время — от новых к старым; у последней пилюля «текущая», у нее НЕТ кнопки «Откатить».
  2. «Смотреть» на любой версии → read-only просмотр с плашкой «… — только чтение, правки недоступны»; правки в этом просмотре невозможны.
  3. «Откатить» к V1 → диалог подтверждения («Откатить к версии V1?… история не переписывается») → подтвердить → success-баннер «Откат выполнен: создана версия V4…»; статья показывает контент V1; в списке появилась V4, V1–V3 не изменены.
  4. «Отмена» в диалоге → ничего не происходит.
  5. Раскладка: две колонки (minmax(300px,360px)+1fr) на desktop; ≤880px — одна колонка без X-прокрутки.
  6. API-негативы: revert чужой версии / несуществующей страницы → 404; список версий — от новых к старым, без контента.
- **Ожидаемый результат:** история полная и упорядоченная, просмотр read-only, откат создает НОВУЮ запись (V4 = контент V1), история не переписывается и не удаляется. Факт прогона 4.1: green (test_versions_list_newest_first_without_content, test_revert_creates_new_version_not_rewrite, test_revert_missing_page_or_version_404 — passed из 27); 4.2 desktop: green (TC-wiki-201…207 в составе 29 passed; DV 07-history.png, 08-revert-dialog.png, 15-success-banner.png); 4.4 смок п.13 — new_version_id=3, история растущая.
- **Автотест:** tests/web/test_p15_wiki_history.py::test_history_page_requires_session (TC-wiki-201), ::test_history_list_newest_first_with_author_and_datetime (TC-wiki-202), ::test_current_pill_on_latest_no_revert_button (TC-wiki-203), ::test_version_view_readonly (TC-wiki-204), ::test_revert_confirm_dialog_cancel (TC-wiki-205), ::test_revert_creates_new_version_updates_list (TC-wiki-206), ::test_history_layout_collapses_narrow (TC-wiki-207) + tests/api/test_wiki_api.py::test_versions_list_newest_first_without_content, ::test_get_version_content_and_foreign_version_404, ::test_revert_creates_new_version_not_rewrite, ::test_revert_missing_page_or_version_404
- **Статус:** **approved** (QA 4.1: 27 API passed / 0 failed; QA 4.2 прогнан: 29 passed / 0 failed + DV 14/14)
