# TC-fast2-004 — Негативный: fast с явным priority=null через API → 422

- **CHK:** CHK-130
- **Change:** add-r2-categories-settings
- **Источник:** fastline MODIFIED (FR-27, ОГР-10) / Scenario: Негативный: fast-задача с приоритетом не-high через API — **явный null**
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200; `BASE_URL` по умолчанию `http://127.0.0.1:8080`); выполнен вход owner (логин `owner`, пароль `QaOwner_Pass_1!` — seed `tests/api/conftest.py`, куки в `owner_cookies.txt`); seed справочника выполнен (CHK-139 / TC-env-001: `Дом`, `Работа`, `Личное` в справочнике до прогона).
- **Сценарий:**
  - **GIVEN** вызывающий авторизован, активных fast-задач нет
  - **WHEN** вызывающий отправляет `POST /api/tasks` с `is_fast=true` и явным `priority=null`
  - **THEN** API отклоняет запрос 422 `details.priority="fast requires high"`; fast-задача не создается
- **Шаги:**
  1. Контроль: активных fast-задач нет (`GET /api/board`).
  2. `curl -s -i -b owner_cookies.txt -X POST {BASE_URL}/api/tasks -H "Content-Type: application/json" -d '{"title":"QAT-фаст-null","is_fast":true,"priority":null}'` → код и тело.
  3. `GET "/api/search?archived=false"` → посчитать задачи `QAT-фаст-null`.
- **Ожидаемый результат:** шаг 2 — HTTP **422**, тело `{"error": "validation", "details": {"priority": "fast requires high"}}` (sdd §3.2: явный priority != high отклоняется; случай «явный null» выписан отдельно от «отсутствия поля» — CHK-130 vs CHK-134, эскалация а); шаг 3 — 0 совпадений, fast-задача не создана.
- **Тестовые данные:** body: `{"title":"QAT-фаст-null","is_fast":true,"priority":null}`.
