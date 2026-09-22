# TC-cat-004 — Создание категории в настройках (UI + API)

- **CHK:** CHK-85
- **Change:** add-r2-categories-settings
- **Источник:** categories: Управление справочником категорий (FR-20) / Scenario: Создание категории в настройках
- **Тип:** позитивный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); Playwright (Python): `page`, `expect`; выполнен вход owner (логин `owner`, пароль `QaOwner_Pass_1!` — seed, как TC-UI-002 чеклиста e2e-critical-path); seed справочника выполнен (CHK-139 / TC-env-001: `Дом`, `Работа`, `Личное` в справочнике до прогона).
- **Сценарий:**
  - **GIVEN** пользователь авторизован и находится на странице настроек
  - **WHEN** пользователь создает категорию `QAT-CAT-home`
  - **THEN** категория появляется в справочнике и доступна в поле категории формы задачи
- **Шаги:**
  1. API-контроль параллельно: `curl -s -i -b owner_cookies.txt -X POST {BASE_URL}/api/categories -H "Content-Type: application/json" -d '{"name":"QAT-CAT-home"}'` → код и тело.
  2. `GET {BASE_URL}/api/categories` → `QAT-CAT-home` присутствует.
  3. Открыть `{BASE_URL}/settings` — категория видна в списке справочника на странице.
  4. Открыть форму создания задачи → `QAT-CAT-home` есть среди опций поля «Категория».
  5. Cleanup (CHK-140): убедиться, что задач с категорией `QAT-CAT-home` нет, `DELETE /api/categories/{id}` → 200.
- **Ожидаемый результат:** шаг 1 — HTTP **201**, тело `{"id": …, "name": "QAT-CAT-home"}` (sdd §3.1); шаги 2–3 — категория в справочнике (API и страница настроек); шаг 4 — доступна в select формы. Cleanup удалил категорию.
- **Тестовые данные:** name=`QAT-CAT-home`.
