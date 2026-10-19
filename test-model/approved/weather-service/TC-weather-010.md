# TC-weather-010 — Кэш: повторные запросы в течение часа — из кэша, без провайдера

- **Change:** weather-service
- **Источник:** weather-service: «Кэш 60 минут» / Scenario: Повторные запросы в течение часа идут из кэша
- **Тип:** позитивный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`; unit/integration-уровень: `services/weather` pytest с httpx.MockTransport (провайдер мокается, т.к. URL Open-Meteo зашит в конфиге); кэш — временный файл через env `EKOTOV_WEATHER_CACHE_PATH`
- **Шаги:**
  1. Прогреть кэш одним успешным ответом (fetched_at = T0).
  2. Выполнить подряд `/api/weather` под owner и pe (5+ запросов, unit: с mock-счетчиком провайдера).
  3. Сравнить ответы между собой и с кэш-файлом.
- **Ожидаемый результат:** все ответы — из кэша (мгновенно, без вызова провайдера: счетчик mock = 1), `stale: false`, `fetched_at` одинаков во всех ответах и равен кэш-файлу; кэш общий (не персональный) — данные для owner и pe идентичны.
- **Тестовые данные:** mock-счетчик вызовов провайдера; два пользователя owner/pe.
