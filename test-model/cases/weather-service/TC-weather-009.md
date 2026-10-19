# TC-weather-009 — Локальное время Москвы в данных независимо от таймзоны браузера

- **Change:** weather-service
- **Источник:** weather-service: «Провайдер Open-Meteo — параметры запроса» / Scenario: Локальное время Москвы в данных
- **Тип:** позитивный | **Приоритет:** Should
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`
- **Шаги:**
  1. В браузере выставить таймзону, отличную от московской (контекст Playwright `timezoneId='America/New_York'`).
  2. Открыть `/weather` под owner.
  3. Сверить даты карточек и время обновления (`fetched_at`) с московским временем стенда.
- **Ожидаемый результат:** даты дней и время последнего обновления показаны в московском времени (UTC+3) и совпадают с данными `/api/weather`; сдвига на таймзону браузера нет.
- **Тестовые данные:** Playwright-контекст с timezoneId ≠ Europe/Moscow; `fetched_at` из API.
