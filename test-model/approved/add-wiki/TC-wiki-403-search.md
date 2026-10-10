# TC-wiki-403 — Поиск по wiki: LIKE по заголовку и тексту, сниппет plain-текст, экранирование, не по версиям (FR-114)

- **Change:** add-wiki
- **Источник:** wiki (ADDED): Requirement «Поиск по wiki» (решение 4, ОВ-3, FR-114) — Scenario «Поиск находит по заголовку и тексту», «Поиск не затрагивает версии», «Поиск без совпадений»; DV-1 review-001 (major, исправлен); design §3; CHK-wiki-6, CHK-wiki-7, CHK-wiki-8
- **Тип:** ФТ, позитив + негатив | **Приоритет:** Must
- **Предусловия:** авторизованная сессия (стенд conftest или nginx-стенд 4.1); страницы: с подстрокой в заголовке, с подстрокой только в контенте, с подстрокой только в старой версии; страницы-пустышки для LIMIT
- **Шаги:**
  1. GET /api/wiki/search?q=<подстрока из заголовка> и q=<подстрока из контента> → обе страницы в выдаче: заголовок, путь в иерархии, фрагмент с match_offset/match_length.
  2. UI: ввод в поиск раздела Wiki → выдача с `<mark>` по оффсету, счетчик «Найдено: N».
  3. Проверить сниппет: plain-текст БЕЗ HTML-тегов (фикс DV-1: сервер режет теги до сниппета).
  4. q=<подстрока только из старой версии> → страница НЕ в выдаче (поиск только по текущему контенту, ОВ-3).
  5. q=<несуществующая подстрока> → пустой результат без ошибок; LIMIT 20 соблюден.
  6. q=`100%_` → экранирование `%`/`_`/`\` (ESCAPE-паттерн), ложных совпадений нет.
- **Ожидаемый результат:** поиск находит по заголовку и тексту с подсветкой; сниппет — чистый текст без тегов; версии не ищутся; пустой результат корректен; wildcards экранированы. Факт прогона 4.1: green (test_search_finds_title_and_content, test_search_snippet_plain_text_no_tags, test_search_escapes_like_wildcards, test_search_limit_20 — passed из 27); UI 4.2 desktop — DV-1 OK (03-search.png), 4.3 mobile п.4a — mark='версия три'.
- **Автотест:** tests/api/test_wiki_api.py::test_search_finds_title_and_content, ::test_search_snippet_plain_text_no_tags, ::test_search_escapes_like_wildcards, ::test_search_limit_20 + tests/web/test_p15_wiki_tree.py::test_wiki_search_title_and_snippet_mark (TC-wiki-002), ::test_wiki_search_no_results (TC-wiki-003)
- **Статус:** **approved** (QA 4.1 прогнан: 27 API passed / 0 failed; 4.2 desktop: wiki-сьют 29 passed + DV-контроль 14/14)
