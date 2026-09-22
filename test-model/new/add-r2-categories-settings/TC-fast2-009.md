# TC-fast2-009 — Обычная задача с любым приоритетом не ограничена

- **CHK:** CHK-135
- **Change:** add-r2-categories-settings
- **Источник:** fastline MODIFIED (FR-27) / Scenario: Обычная задача с любым приоритетом не ограничена
- **Тип:** граничный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200; `BASE_URL` по умолчанию `http://127.0.0.1:8080`); выполнен вход owner (логин `owner`, пароль `QaOwner_Pass_1!` — seed `tests/api/conftest.py`, куки в `owner_cookies.txt`); seed справочника выполнен (CHK-139 / TC-env-001: `Дом`, `Работа`, `Личное` в справочнике до прогона).
- **Сценарий:**
  - **GIVEN** вызывающий авторизован
  - **WHEN** вызывающий создает обычную (не fast) задачу с `priority="low"`
  - **THEN** задача создается успешно с приоритетом «low» (ограничение действует только на fast-задачи)
- **Шаги:**
  1. `curl -s -i -b owner_cookies.txt -X POST {BASE_URL}/api/tasks -H "Content-Type: application/json" -d '{"title":"QAT-обычная-low","priority":"low"}'` → код и тело.
  2. `GET /api/tasks/{id}` → `priority`, `is_fast`.
- **Ожидаемый результат:** шаг 1 — HTTP **201**; шаг 2 — `priority="low"`, `is_fast=false` — обычные задачи ограничением fast×priority не задеты.
- **Тестовые данные:** body: `{"title":"QAT-обычная-low","priority":"low"}`.
