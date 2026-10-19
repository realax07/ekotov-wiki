# TC-weather-003 — Негатив: /api/weather без сессии — 401, без обращений к провайдеру и кэшу

- **Change:** weather-service
- **Источник:** weather-service: «API погоды — только по сессии» / Scenario: Негативный: /api/weather без сессии
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`; unit/integration-уровень: `services/weather` pytest с httpx.MockTransport (провайдер мокается, т.к. URL Open-Meteo зашит в конфиге); кэш — временный файл через env `EKOTOV_WEATHER_CACHE_PATH`
- **Шаги:**
  1. Выполнить `GET {BASE_URL}/api/weather` без cookie сессии.
  2. Выполнить `GET {BASE_URL}/api/weather?x=1` и `GET {BASE_URL}/api/health` без сессии.
  3. На unit-уровне: вызвать маршрут без сессии при httpx.MockTransport-заглушке, считающей вызовы провайдера.
- **Ожидаемый результат:** шаг 1 — ответ 401 с телом `{"error": "unauthorized"}`; шаг 2 — семейство `/api/weather*` закрыто так же (401), `/api/health` отвечает по своему контракту; шаг 3 — обращений к провайдеру (0 вызовов mock-транспорта) и чтения/записи кэша нет; анонимное получение данных погоды невозможно.
- **Тестовые данные:** запросы без cookie; mock-транспорта-счетчик вызовов.
