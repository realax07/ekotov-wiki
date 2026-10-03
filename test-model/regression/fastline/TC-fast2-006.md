# TC-fast2-006 — Негативный: fast с priority=medium через API → 422

- **CHK:** CHK-132
- **Change:** add-r2-categories-settings
- **Источник:** fastline MODIFIED (FR-27, ОГР-10) / Scenario: Негативный: fast с приоритетом не-high — medium
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200; `BASE_URL` по умолчанию `http://127.0.0.1:8080`); выполнен вход owner (логин `owner`, пароль `QaOwner_Pass_1!` — seed `tests/api/conftest.py`, куки в `owner_cookies.txt`); seed справочника выполнен (CHK-139 / TC-env-001: `Дом`, `Работа`, `Личное` в справочнике до прогона).
- **Сценарий:**
  - **GIVEN** вызывающий авторизован, активных fast-задач нет
  - **WHEN** вызывающий отправляет `POST /api/tasks` с `is_fast=true` и `priority="medium"`
  - **THEN** API отклоняет запрос 422; fast-задача не создается
- **Шаги:**
  1. Контроль: активных fast-задач нет.
  2. `curl -s -i -b owner_cookies.txt -X POST {BASE_URL}/api/tasks -H "Content-Type: application/json" -d '{"title":"QAT-фаст-medium","is_fast":true,"priority":"medium"}'` → код и тело.
  3. `GET "/api/search?archived=false"` → посчитать задачи `QAT-фаст-medium`.
- **Ожидаемый результат:** шаг 2 — HTTP **422** `{"error": "validation", "details": {"priority": "fast requires high"}}`; шаг 3 — 0 совпадений.
- **Тестовые данные:** body: `{"title":"QAT-фаст-medium","is_fast":true,"priority":"medium"}`.
