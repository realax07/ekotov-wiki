# TC-fast2-011 — PATCH-случаи: обычная→high легальна; is_fast не меняется; fast PATCH на не-high отклоняется

- **CHK:** CHK-137
- **Change:** add-r2-categories-settings
- **Источник:** fastline MODIFIED (FR-27; дополнение: PATCH-случаи, sdd §3.2)
- **Тип:** граничный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200; `BASE_URL` по умолчанию `http://127.0.0.1:8080`); выполнен вход owner (логин `owner`, пароль `QaOwner_Pass_1!` — seed `tests/api/conftest.py`, куки в `owner_cookies.txt`); seed справочника выполнен (CHK-139 / TC-env-001: `Дом`, `Работа`, `Личное` в справочнике до прогона).
- **Сценарий:**
  - **GIVEN** существуют обычная задача `QAT-патч-обычная` (medium) и fast-задача `QAT-патч-фаст` (high)
  - **WHEN** обычная патчится на priority=high; fast патчится на priority≠high (если достижимо)
  - **THEN** PATCH обычной → 200 легален; PATCH не назначает/не снимает is_fast (ОГР-5); PATCH fast на не-high — отклоняется 422
- **Шаги:**
  1. Подготовка: `POST /api/tasks` `{"title":"QAT-патч-обычная","priority":"medium"}` → 201; fast-задача `QAT-патч-фаст` (`is_fast:true`) → 201; зафиксировать id обоих.
  2. `PATCH /api/tasks/{id_обычной}` `{"priority":"high"}` → код; `GET /api/tasks/{id_обычной}` → priority, is_fast.
  3. `PATCH /api/tasks/{id_обычной}` `{"is_fast":true}` → код; `GET` → is_fast (должен остаться false — смена is_fast вне дельты, ОГР-5).
  4. `PATCH /api/tasks/{id_фаст}` `{"priority":"medium"}` → код и тело (если эндпоинт допускает такой PATCH).
  5. Cleanup: DELETE обеих задач.
- **Ожидаемый результат:** шаг 2 — HTTP **200**, `priority="high"`, `is_fast=false` (ограничение — только fast); шаг 3 — `is_fast` не изменился (PATCH не назначает fast, ОГР-5: смена is_fast после создания вне дельты; фактический код ответа зафиксировать — ожидаемо 200 с игнором или 422, главное — is_fast=false после); шаг 4 — HTTP **422** `details.priority="fast requires high"` (если путь достижим; если PATCH priority у fast отклоняется иначе — зафиксировать, инвариант «после PATCH priority fast-задачи = high» обязателен).
- **Тестовые данные:** задачи `QAT-патч-обычная` (medium→high, попытка is_fast), `QAT-патч-фаст` (high→попытка medium).
