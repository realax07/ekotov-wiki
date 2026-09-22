# TC-fast2-001 — Создание fast-задачи: приоритет high автоматически, на fast line

- **CHK:** CHK-127
- **Change:** add-r2-categories-settings
- **Источник:** fastline MODIFIED: Назначение задачи на fast line вручную при создании (FR-27, FR-3) / Scenario: Создание задачи с назначением на fast line
- **Тип:** позитивный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200; `BASE_URL` по умолчанию `http://127.0.0.1:8080`); выполнен вход owner (логин `owner`, пароль `QaOwner_Pass_1!` — seed `tests/api/conftest.py`, куки в `owner_cookies.txt`); seed справочника выполнен (CHK-139 / TC-env-001: `Дом`, `Работа`, `Личное` в справочнике до прогона).
- **Сценарий:**
  - **GIVEN** пользователь авторизован, активных fast-задач нет
  - **WHEN** пользователь создает задачу с назначением на fast line (без указания приоритета)
  - **THEN** задача создается как fast с приоритетом «высокий» (high) автоматически и отображается на fast line
- **Шаги:**
  1. Контроль: `GET /api/board` — активных fast-задач нет.
  2. `curl -s -i -b owner_cookies.txt -X POST {BASE_URL}/api/tasks -H "Content-Type: application/json" -d '{"title":"QAT-фаст-high","is_fast":true}'` (поле priority НЕ передано) → код и тело.
  3. `GET /api/board` → проверить позицию задачи.
  4. Cleanup: DELETE задачи (или move в done — по сценарию сюиты) для освобождения линии.
- **Ожидаемый результат:** шаг 2 — HTTP **201**, тело: `is_fast=true`, `status="todo"`, **`priority="high"`** (автоподстановка сервером, sdd §3.2); шаг 3 — карточка на fast line, столбец подсвечен.
- **Тестовые данные:** title=`QAT-фаст-high`, is_fast=true, priority отсутствует.
