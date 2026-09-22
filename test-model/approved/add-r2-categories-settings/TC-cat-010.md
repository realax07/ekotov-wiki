# TC-cat-010 — PATCH/DELETE несуществующего id категории → 404

- **CHK:** CHK-91
- **Change:** add-r2-categories-settings
- **Источник:** categories: Управление справочником (FR-20; дополнение: состояние, sdd §3.1)
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200; `BASE_URL` по умолчанию `http://127.0.0.1:8080`); выполнен вход owner (логин `owner`, пароль `QaOwner_Pass_1!` — seed `tests/api/conftest.py`, куки в `owner_cookies.txt`); seed справочника выполнен (CHK-139 / TC-env-001: `Дом`, `Работа`, `Личное` в справочнике до прогона).
- **Сценарий:**
  - **GIVEN** пользователь авторизован; id `999999` в справочнике не существует
  - **WHEN** вызываются PATCH и DELETE с этим id
  - **THEN** оба запроса → 404; справочник не изменяется
- **Шаги:**
  1. `GET /api/categories` → снимок списка `S0`.
  2. `curl -s -i -b owner_cookies.txt -X PATCH {BASE_URL}/api/categories/999999 -H "Content-Type: application/json" -d '{"name":"QAT-никогда"}'` → код.
  3. `curl -s -i -b owner_cookies.txt -X DELETE {BASE_URL}/api/categories/999999` → код.
  4. `GET /api/categories` → сверить с `S0`.
- **Ожидаемый результат:** шаги 2–3 — HTTP **404** (оба, sdd §3.1); шаг 4 — справочник идентичен снимку `S0` (ни записи не добавлено, ни одна не изменена/не удалена).
- **Тестовые данные:** несуществующий id=`999999`; name=`QAT-никогда` (не должен появиться).
