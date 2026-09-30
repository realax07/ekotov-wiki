# TC-sugg-r4-101 — GET /api/suggestions/users: состав из данных, сортировка, UNION-уникальность, 401

- **CHK:** CHK-R4-102
- **Change:** add-r4-user-profile-ticket-view
- **Источник:** auth (ADDED): «suggestions/users как отдельный API-контракт» (FR-46); СЦ «Подсказки значений фильтров assigned/creator — из БД» (search, механизм FR-35/DEF-001); sdd §3.5 / design §7 (документирующий фикс I3); backend/app/suggestions.py (`_USER_SUGGESTIONS_SQL`: DISTINCT + UNION + ORDER BY)
- **Тип:** гран. | **Приоритет:** Should
- **Маркер:** api (сьют tests/api; существующий web-тест TC-search-r4-ui-001 проверяет только подсказки через UI — НЕ дублируется, контракт эндпоинта напрямую не покрыт)
- **Среда/предусловия:** тестовый стенд tests/api; сессии owner и wife (conftest); категории seed (TC-env-001); изоляция через префикс `QAT-` + cleanup; БД задач НЕ пустая к шагу 1 (создаем данные своим тестом — самодостаточно).
- **Шаги:**
  1. Без сессии (requests.Session без логина): `GET {BASE_URL}/api/suggestions/users` → статус и тело.
  2. Войти owner. Создать 3 задачи через `POST /api/tasks`: A `{"title": "QAT-s102-А", "assigned_to_id": <id wife>}` (wife в assigned_to_id), B `{"title": "QAT-s102-Б", "assigned_to_id": <id wife>, "tags": ["QAT-x"]}` (wife второй раз — через другую ветку), C `{"title": "QAT-s102-В"}` без исполнителя (creator = owner автоматически).
  3. `GET /api/suggestions/users` (сессия owner) — тело ответа.
  4. Проверки состава: `set(body.keys()) == {"users"}` (единственный ключ — контракт не расширяется, чтобы не ломать форму ответа /api/suggestions); каждый элемент — строка-логин, реально встречающийся в данных: `"owner" in users` и `"wife" in users`; посторонних логинов нет (users ⊆ {owner, wife}).
  5. Сортировка и уникальность: `users == sorted(users)`; `len(users) == len(set(users))` — wife, встречающаяся в creator И в assigned (ветки UNION), входит ровно ОДИН раз (UNION, не UNION ALL).
  6. Формат элемента: все элементы — логины (строки), не id, не display_name: `set(users) <= {"owner", "wife"}` и `all(isinstance(u, str) for u in users)`.
  7. Cleanup: удалить задачи A/B/C (fixture-финализатор).
- **Ожидаемый результат:** шаг 1 — 401 `{"error": "unauthorized"}` (путь НЕ в exempt-списке middleware, NFR-7). Шаги 3–6 — 200 `{"users": [...]}`: только логины из creator_id/assigned_to_id существующих задач (JOIN, НЕ весь справочник /api/users); без дублей при пересечении веток (UNION-уникальность); отсортировано по возрастанию; владелец без задач в конкретной роли (например жена без созданных задач) не «выкидывается», если встречается хотя бы в одной ветке — состав определяется данными, а не справочником. Ответ вида `{"users": ["owner", "wife"]}` (все логины встречаются), `users == sorted(set(users))`.
- **Тестовые данные:** задачи `QAT-s102-А/Б/В` (префикс QAT); assigned = wife; creator проставляется сервером (owner); seed-логины owner/wife; пустая ветка assigned у задачи C легальна (creator-ветка покрывает owner).
