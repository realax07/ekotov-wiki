# TC-wiki-401 — Права доступа: паритет owner/wife, 401 аноним на API, 302 на страницы

- **Change:** add-wiki
- **Источник:** wiki (ADDED): Requirement «Права доступа к wiki» (решение 7, FR-115) — Scenario «Паритет owner и wife», «Анонимный доступ к странице», «Анонимный вызов API»; design §3; CHK-wiki-26, CHK-wiki-27
- **Тип:** ФТ, безопасность | **Приоритет:** Must
- **Предусловия:** стенд nginx :18443 (REPORT-4.1 §1: app + search + images + nginx, БД с миграциями wiki); сессии owner (`QaOwner_Pass_1!`) и wife (`QaWife_Pass_2!`); третья сессия — анонимная (без кук)
- **Шаги:**
  1. Анонимно вызвать каждый из 9 методов wiki-API (GET/POST /api/wiki/pages, GET/PUT/DELETE /api/wiki/pages/{id}, GET versions, GET versions/{vid}, POST revert, GET search) → ожидается 401 `{"error":"unauthorized"}`.
  2. Анонимно открыть GET /wiki и GET /wiki/{id} → ожидается 302 → /login (middleware).
  3. Owner создает страницу, wife читает её (200), редактирует (PUT 200) — в page_versions появляется запись с author_id = wife.
  4. Owner открывает историю (3 записи: создание + правки), откатывает версию wife (revert 200) — ничего не потеряно.
- **Ожидаемый результат:** разделения прав owner/wife нет — оба выполняют чтение, создание, редактирование и работу с версиями одинаково успешно; анонимный вызов любого wiki-API → 401; анонимный GET страниц → 302 /login. Факт прогона 4.1: green (test_all_endpoints_require_session passed из 27 API-passed; REPORT-4.1-api.md, §2 «Права»); смок 4.4 пп. 6/7/9/14/15 — PASS.
- **Автотест:** tests/api/test_wiki_api.py::test_all_endpoints_require_session (+ tests/web/test_p15_wiki_history.py::test_history_page_requires_session); двухсессионный паритет — смок-скрипт прогона (автотеста нет — прогон 4.1 REPORT-4.1 §2, скрипт)
- **Статус:** **approved** (QA 4.1 прогнан: 27 API passed / 0 failed; 4.4 смок 16/16)
