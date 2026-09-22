# TC-cat-013 — Негативный: редактирование задачи с категорией вне справочника через API

- **CHK:** CHK-94
- **Change:** add-r2-categories-settings
- **Источник:** categories: Жесткая валидация (FR-21; sdd §3.2 PATCH) / Scenario: Негативный: редактирование задачи с категорией вне справочника через API
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200; `BASE_URL` по умолчанию `http://127.0.0.1:8080`); выполнен вход owner (логин `owner`, пароль `QaOwner_Pass_1!` — seed `tests/api/conftest.py`, куки в `owner_cookies.txt`); seed справочника выполнен (CHK-139 / TC-env-001: `Дом`, `Работа`, `Личное` в справочнике до прогона).
- **Сценарий:**
  - **GIVEN** существует задача с валидной категорией `Дом`; `QAT-ghost` в справочнике отсутствует
  - **WHEN** вызывающий отправляет `PATCH /api/tasks/{id}` с категорией `QAT-ghost`
  - **THEN** API отклоняет запрос 422; категория задачи не изменяется
- **Шаги:**
  1. Создать задачу-носитель: `POST /api/tasks` `{"title":"QAT-носитель-патча","category":"Дом"}` → 201, зафиксировать `id`.
  2. `curl -s -i -b owner_cookies.txt -X PATCH {BASE_URL}/api/tasks/{id} -H "Content-Type: application/json" -d '{"category":"QAT-ghost"}'` → код и тело.
  3. `GET /api/tasks/{id}` → поле `category`.
  4. Cleanup: DELETE задачи → 204.
- **Ожидаемый результат:** шаг 2 — HTTP **422**, тело `{"error": "validation", "details": {"category": "not in categories"}}`; шаг 3 — `category` осталась `Дом` (отклоненный PATCH не изменяет данных); валидация действует и на редактирование (FR-21).
- **Тестовые данные:** задача `QAT-носитель-патча` (Дом → попытка на `QAT-ghost`).
