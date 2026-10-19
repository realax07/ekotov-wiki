# TC-weather-005 — Деградация: отсутствующая метрика — прочерк, карточка не ломается

- **Change:** weather-service
- **Источник:** weather-service: «Карточка «Сегодня» с 8 метриками» / Scenario: Деградация при отсутствии метрики
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`; unit/integration-уровень: `services/weather` pytest с httpx.MockTransport (провайдер мокается, т.к. URL Open-Meteo зашит в конфиге); кэш — временный файл через env `EKOTOV_WEATHER_CACHE_PATH`
- **Шаги:**
  1. Скормить сервису (unit-mock) ответ провайдера без `surface_pressure` (null и отсутствие поля — два прогона).
  2. Открыть `/weather`, осмотреть карточку «Сегодня».
  3. Повторить с отсутствующим полем влажности.
- **Ожидаемый результат:** в поле давления — прочерк «—», остальные 7 метрик отображаются как обычно; валидного JSON-парсинга ошибок/5xx нет; варьируемое поле деградирует точечно (прочерк), карточка не схлопывается.
- **Тестовые данные:** фикстуры ответа: без surface_pressure (null), без ключа surface_pressure, без relative_humidity_2m.
