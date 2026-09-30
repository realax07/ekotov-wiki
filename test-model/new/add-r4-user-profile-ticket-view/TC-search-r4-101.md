# TC-search-r4-101 — API-выдача поиска: объект-сравнение ВСЕГО состава полей, включая tags-массив

- **CHK:** CHK-R4-99
- **Change:** add-r4-user-profile-ticket-view
- **Источник:** search (MODIFIED): «Поиск через API» (FR-45, FR-8/46); урок волны 5 / дефект 8225bbf (search.py row[10] — tags=[] в каждой строке; дефект пойман web-сьютом, API-сьют пропустил, т.к. проверял только assigned/creator); impact §4 «Хрупкость row-индексов search.py»
- **Тип:** гран. | **Приоритет:** Must
- **Маркер:** api (сьют tests/api)
- **Среда/предусловия:** тестовый стенд tests/api (`EKOTOV_WIKI_BASE_URL`); сессия owner (conftest); категории seed «Дом», «Работа», «Личное» (TC-env-001); isolation через префикс `QAT-` и cleanup-фикстуры (никаких sleep).
- **Шаги:**
  1. Войти owner (`POST /api/auth/login`, константы conftest). Узнать id wife через `GET /api/users`.
  2. Создать задачу-эталон со ВСЕМИ атрибутами: `POST /api/tasks` `{"title": "QAT-s101-эталон", "description": "QAT описание s101", "priority": "high", "category": "Работа", "due_date": "2026-12-01", "tags": ["QAT-s101-тег-А", "QAT-s101-тег-Б"], "assigned_to_id": <id wife>}` — 201. Зафиксировать ответ как эталонный объект E.
  3. `GET /api/search?tag=QAT-s101-тег-А` — найти созданную задачу в `results` (ровно она).
  4. ОБЪЕКТ-СРАВНЕНИЕ (не выборочное): результат поиска == эталон E ПОЛНОСТЬЮ — множество ключей и значения каждого поля: `id`, `title`, `description`, `priority`, `category`, `due_date`, `is_fast`, `status`, `done_at`, `archived_at`, `creator`, `assigned` И `tags` как МАССИВ ЗНАЧЕНИЙ: `tags == ["QAT-s101-тег-А", "QAT-s101-тег-Б"]` (не «ключ присутствует» и не «не пустой» — точный состав и порядок).
  5. `POST /api/search/advanced` с `{"query": "assigned = \"wife\" AND tag IN (\"QAT-s101-тег-А\")"}` — повторить объект-сравнение шага 4 для advanced-выдачи (та же `_row_to_task_with_users`; грамматика advanced допускает для tag ТОЛЬКО `IN (...)` — `tag = "..."` дает 400, см. search.py «tag supports only IN»).
  6. Граничный контроль: создать вторую задачу `{"title": "QAT-s101-без-тегов"}` БЕЗ тегов; `GET /api/search?tag=...` не находит ее, а `GET /api/search?archived=all` содержит ее с `tags == []` — ровно пустой список (тип list, не null, не отсутствие ключа).
  7. Cleanup: удалить обе задачи (fixture-финализатор).
- **Ожидаемый результат:** шаги 3–5 — строка выдачи (GET и advanced) ПОБИТОВО равна эталону: все 13 ключей контракта, значения совпадают, `tags` — точный массив `["QAT-s101-тег-А", "QAT-s101-тег-Б"]` (объект-сравнение переносит класс дефекта 8225bbf в API-сьют); шаг 6 — у задачи без тегов `tags == []`, ключ присутствует.
- **Тестовые данные:** title `QAT-s101-эталон` / `QAT-s101-без-тегов` (префикс QAT — изоляция); теги `QAT-s101-тег-А`, `QAT-s101-тег-Б`; категория «Работа» (seed); due_date `2026-12-01`; priority `high`; assigned = wife.
