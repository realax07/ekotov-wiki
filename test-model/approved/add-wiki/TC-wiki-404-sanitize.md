# TC-wiki-404 — Санитизация HTML: whitelist-фильтр на записи и при отображении (NFR-31)

- **Change:** add-wiki
- **Источник:** wiki (ADDED): Requirement «Санитизация HTML контента» (NFR-31, FR-110) — Scenario «Скрипт вырезается при отображении», «Разрешенные теги проходят»; design §4; CHK-wiki-29, CHK-wiki-30
- **Тип:** ФТ, безопасность, негатив + позитив | **Приоритет:** Must
- **Предусловия:** авторизованная сессия; юнит-часть — чистый `app.sanitize` без БД; сквозная часть — API на стенде
- **Шаги:**
  1. Негативы sanitizer (юнит): контент с `<script>`/`<style>` (с содержимым), `onclick`/`onerror`, `javascript:`-href, `data:`-href, `iframe`, вложенной мутацией `<scr<script>ipt>` → опасное вырезано/развернуто, текст сохранен.
  2. Сквозной негатив: POST страницы с `<script>` в контенте → GET отдает контент БЕЗ скрипта (санитизация на записи); откат к версии с опасным контентом → хранимое тоже санитизировано.
  3. Позитивы: вся разметка тулбара (H1–H3, B/I/U, ul/ol/li, blockquote, pre/code, a[href,title], img[src,alt], table/thead/tbody/tr/th/td, colspan/rowspan) → проходит без искажений; URL-фильтр http/https/относительные; data:-src у img разрешен.
- **Ожидаемый результат:** скрипты, обработчики on*, javascript:-URL и внешние embed не проходят до рендера; whitelist-разметка редактора сохраняется 1:1. Факт прогона 4.1: green (test_sanitize.py — 35 passed / 0 failed; сквозные test_create_sanitizes_content, test_revert_sanitizes_stored_content — passed).
- **Автотест:** tests/api/test_sanitize.py::test_script_tag_removed_with_content, ::test_style_tag_removed_with_content, ::test_onclick_attribute_stripped, ::test_javascript_href_removed_with_attribute, ::test_nested_mutation_scr_script_ipt, ::test_iframe_unwrapped_content_kept, ::test_toolbar_markup_passes, ::test_full_toolbar_document_roundtrip + tests/api/test_wiki_api.py::test_create_sanitizes_content, ::test_revert_sanitizes_stored_content
- **Статус:** **approved** (QA 4.1 прогнан: 35 sanitize-проверок passed / 0 failed; REPORT-4.1-api.md §2)
