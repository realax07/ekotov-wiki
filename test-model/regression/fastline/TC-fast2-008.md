# TC-fast2-008 — Автоподстановка: fast БЕЗ поля priority → 201, priority=high

- **CHK:** CHK-134
- **Change:** add-r2-categories-settings
- **Источник:** fastline MODIFIED (FR-27; sdd §3.2) — автоподстановка: отсутствие поля priority
- **Тип:** позитивный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200; `BASE_URL` по умолчанию `http://127.0.0.1:8080`); выполнен вход owner (логин `owner`, пароль `QaOwner_Pass_1!` — seed `tests/api/conftest.py`, куки в `owner_cookies.txt`); seed справочника выполнен (CHK-139 / TC-env-001: `Дом`, `Работа`, `Личное` в справочнике до прогона).
- **Сценарий:**
  - **GIVEN** вызывающий авторизован, активных fast-задач нет
  - **WHEN** вызывающий отправляет `POST /api/tasks` с `is_fast=true` БЕЗ поля priority
  - **THEN** 201, `priority="high"` установлен сервером (отдельный случай от явного null — CHK-130, эскалация а)
- **Шаги:**
  1. Контроль: активных fast-задач нет.
  2. `curl -s -i -b owner_cookies.txt -X POST {BASE_URL}/api/tasks -H "Content-Type: application/json" -d '{"title":"QAT-фаст-безприор","is_fast":true}'` → код и тело (ключ priority в запросе отсутствует).
  3. Cleanup: освободить линию (DELETE или move в done).
- **Ожидаемый результат:** шаг 2 — HTTP **201**, тело: `priority="high"` (не null!) — автоподстановка (sdd §3.2: «is_fast=true без priority → приоритет устанавливается high»); контраст с CHK-130 (явный null → 422) — трактовка «отсутствие поля = автоподстановка» подтверждена живым прогоном.
- **Тестовые данные:** body: `{"title":"QAT-фаст-безприор","is_fast":true}` (без ключа priority).
