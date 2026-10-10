# TC-wiki-416 — Редактирование с записью версии: каждое сохранение → запись, история полная (FR-112)

- **Change:** add-wiki
- **Источник:** wiki (ADDED): Requirement «Редактирование страницы с записью версии» (FR-112) — Scenario «Сохранение правки создает версию», «История полная»; design §3, §6; CHK-wiki-21, CHK-wiki-22
- **Тип:** ФТ, данные | **Приоритет:** Must
- **Предусловия:** авторизованный пользователь; существующая страница; для «история полная» — правки от двух разных учеток (owner, wife)
- **Шаги:**
  1. Отредактировать контент → «Сохранить» → PUT 200 → в page_versions новая запись (контент после санитизации, author = текущая сессия, время), updated_at бампнут.
  2. Изменить только заголовок → версия записана, контент не тронут (test_update_title_only_keeps_content).
  3. Последовательно править от owner и wife → история содержит ВСЕ правки с верными авторами и временем, ни одна не потеряна.
  4. API-негативы: PUT пустой title → 422; PUT несуществующей страницы → 404.
- **Ожидаемый результат:** каждое сохранение (заголовок и/или контент) создает запись версии; история полная с авторами и временем. Факт прогона 4.1: green (test_update_creates_version_and_bumps_updated_at, test_update_title_only_keeps_content — passed из 27; паритет-смок: история 3 записи); 4.2 desktop: green (TC-wiki-202, TC-wiki-308); 4.4 смок п.11 — versions 1→2.
- **Автотест:** tests/web/test_p15_wiki_editor.py::test_save_edit_puts_new_version_and_redirects (TC-wiki-308), tests/web/test_p15_wiki_history.py::test_history_list_newest_first_with_author_and_datetime (TC-wiki-202) + tests/api/test_wiki_api.py::test_update_creates_version_and_bumps_updated_at, ::test_update_title_only_keeps_content, ::test_update_empty_title_422, ::test_update_missing_page_404
- **Статус:** **approved** (QA 4.1: 27 API passed / 0 failed; QA 4.2: 29 passed / 0 failed)
