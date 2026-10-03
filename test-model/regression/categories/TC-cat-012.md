# TC-cat-012 — Негативный: создание задачи с категорией вне справочника через API

- **CHK:** CHK-93
- **Change:** add-r2-categories-settings
- **Источник:** categories: Жесткая валидация категории задачи (FR-21) / Scenario: Негативный: создание задачи с категорией вне справочника через API
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200; `BASE_URL` по умолчанию `http://127.0.0.1:8080`); выполнен вход owner (логин `owner`, пароль `QaOwner_Pass_1!` — seed `tests/api/conftest.py`, куки в `owner_cookies.txt`); seed справочника выполнен (CHK-139 / TC-env-001: `Дом`, `Работа`, `Личное` в справочнике до прогона).
- **Сценарий:**
  - **GIVEN** вызывающий авторизован; категория `QAT-ghost` в справочнике отсутствует
  - **WHEN** вызывающий отправляет `POST /api/tasks` с категорией `QAT-ghost`
  - **THEN** API отклоняет запрос 422 с детализацией по полю category; задача не создается
- **Шаги:**
  1. Контроль: `GET /api/categories` — `QAT-ghost` отсутствует.
  2. `curl -s -i -b owner_cookies.txt -X POST {BASE_URL}/api/tasks -H "Content-Type: application/json" -d '{"title":"QAT-ghost-задача","category":"QAT-ghost"}'` → код и тело.
  3. `GET "/api/search?archived=false"` → посчитать задачи с title=`QAT-ghost-задача`.
- **Ожидаемый результат:** шаг 2 — HTTP **422**, тело `{"error": "validation", "details": {"category": "not in categories"}}` (sdd §3.2, FR-21); шаг 3 — 0 совпадений (задача не создана). Обход жесткой валидации через API невозможен.
- **Тестовые данные:** title=`QAT-ghost-задача`, category=`QAT-ghost` (обе должны быть ОТВЕРГНУТЫ).
