# TC-set-002 — Негативный: неавторизованный доступ к настройкам

- **CHK:** CHK-104
- **Change:** add-r2-categories-settings
- **Источник:** settings: Страница настроек (FR-23, следствие NFR-7) / Scenario: Негативный: неавторизованный доступ к настройкам
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); Playwright (Python): `page`, `expect`; выполнен вход owner (логин `owner`, пароль `QaOwner_Pass_1!` — seed, как TC-UI-002 чеклиста e2e-critical-path); seed справочника выполнен (CHK-139 / TC-env-001).
- **Сценарий:**
  - **GIVEN** вызывающий не имеет действующей сессии
  - **WHEN** вызывающий открывает `/settings` и прямые API-пути категорий
  - **THEN** страница — редирект на `/login`, содержимое не отображается; API — 401
- **Шаги:**
  1. Новый контекст браузера БЕЗ куки `session`: `page.goto("{BASE_URL}/settings")` → зафиксировать `page.url`, наличие `page.get_by_role("heading", name="Вход")`.
  2. Зафиксировать отсутствие контента настроек: `expect(page.get_by_role("heading", name="Настройки", exact=True)).to_have_count(0)`.
  3. `curl -s -i {BASE_URL}/api/categories` (без кук) → код.
  4. `curl -s -i -X PATCH {BASE_URL}/api/categories/999999 -H "Content-Type: application/json" -d '{"name":"QAT-никогда"}'` (без кук — representative-проверка мутирующего метода; POST/DELETE аналогично 401 за общим middleware) → код.
- **Ожидаемый результат:** шаги 1–2 — URL заканчивается на `/login` (редирект, sdd §3.3), форма входа видна, содержимого настроек нет; шаги 3–4 — HTTP **401** `{"error": "unauthorized"}` — прямые вызовы `/api/categories/*` защищены тем же middleware (sdd §5 NFR-7, exempt-список не расширяется).
- **Тестовые данные:** контекст без куков; URL `{BASE_URL}/settings`, `{BASE_URL}/api/categories`.
