# TC-fast2-005 — Негативный: fast с priority=low через API → 422

- **CHK:** CHK-131
- **Change:** add-r2-categories-settings
- **Источник:** fastline MODIFIED (FR-27, ОГР-10) / Scenario: Негативный: fast с приоритетом не-high — low
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200; `BASE_URL` по умолчанию `http://127.0.0.1:8080`); выполнен вход owner (логин `owner`, пароль `QaOwner_Pass_1!` — seed `tests/api/conftest.py`, куки в `owner_cookies.txt`); seed справочника выполнен (CHK-139 / TC-env-001: `Дом`, `Работа`, `Личное` в справочнике до прогона).
- **Сценарий:**
  - **GIVEN** вызывающий авторизован, активных fast-задач нет
  - **WHEN** вызывающий отправляет `POST /api/tasks` с `is_fast=true` и `priority="low"`
  - **THEN** API отклоняет запрос 422; fast-задача не создается
- **Шаги:**
  1. Контроль: активных fast-задач нет.
  2. `curl -s -i -b owner_cookies.txt -X POST {BASE_URL}/api/tasks -H "Content-Type: application/json" -d '{"title":"QAT-фаст-low","is_fast":true,"priority":"low"}'` → код и тело.
  3. `GET "/api/search?archived=false"` → посчитать задачи `QAT-фаст-low`.
- **Ожидаемый результат:** шаг 2 — HTTP **422** `{"error": "validation", "details": {"priority": "fast requires high"}}`; шаг 3 — 0 совпадений (ОГР-10: обход через API невозможен).
- **Тестовые данные:** body: `{"title":"QAT-фаст-low","is_fast":true,"priority":"low"}`.
