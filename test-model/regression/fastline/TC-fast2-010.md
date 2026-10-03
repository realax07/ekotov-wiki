# TC-fast2-010 — Миграция fast-задач: инвариант is_fast=1 ⇒ priority='high'

- **CHK:** CHK-136
- **Change:** add-r2-categories-settings
- **Источник:** fastline MODIFIED (FR-27) / Scenario: Существующие fast-задачи с не-high приоритетом приводятся в соответствие
- **Тип:** НФТ | **Приоритет:** Must
- **Среда/предусловия:** тестовая БД (env `EKOTOV_WIKI_DB_PATH`); доступ к `sqlite3`; миграционный скрипт пакета (sdd §5: приведение fast-задач к priority='high'); кейс — разовая проверка внедрения (метка `candidate-archive`, impact §3 п.2). Входное состояние: в БД есть fast-задача с priority≠high (до внедрения это было легально).
- **Сценарий:**
  - **GIVEN** до внедрения в системе существует fast-задача с приоритетом, отличным от high
  - **WHEN** выполняется внедрение изменения
  - **THEN** инвариант «fast ⇒ priority=high» выполняется для всех fast-задач; после этого любая fast-задача в системе имеет приоритет high
- **Шаги:**
  1. Контроль «до»: `sqlite3 "$EKOTOV_WIKI_DB_PATH" "SELECT id, title, is_fast, priority FROM tasks WHERE is_fast = 1;"` → зафиксировать список; при отсутствии нарушителя — создать: `UPDATE tasks SET priority = 'low' WHERE title = '<любая fast-задача>';` (или INSERT).
  2. Выполнить миграцию/скрипт приведения (пакет внедрения, sdd §5).
  3. Контроль «после»: `sqlite3 "$EKOTOV_WIKI_DB_PATH" "SELECT COUNT(*) FROM tasks WHERE is_fast = 1 AND priority != 'high';"` → 0.
  4. API-контроль: `GET /api/board` → каждая fast-задача имеет priority=high.
- **Ожидаемый результат:** шаг 1 — зафиксирован хотя бы один нарушитель инварианта «до»; шаг 3 — после миграции COUNT = 0 (все приведены к high, ни одна fast-задача не осталась с другим приоритетом); шаг 4 — API подтверждает. Результат — в протокол внедрения, метка `candidate-archive`.
- **Тестовые данные:** fast-задача с priority='low' (нарушитель «до»); счетчик `is_fast=1 AND priority!='high'`.
