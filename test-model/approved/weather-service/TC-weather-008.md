# TC-weather-008 — Запрос к провайдеру: зафиксированные координаты, tz, 7 дней, м/с и полный набор полей

- **Change:** weather-service
- **Источник:** weather-service: «Провайдер Open-Meteo — параметры запроса» / Scenario: Запрос к провайдеру с зафиксированными параметрами
- **Тип:** позитивный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`; unit/integration-уровень: `services/weather` pytest с httpx.MockTransport (провайдер мокается, т.к. URL Open-Meteo зашит в конфиге); кэш — временный файл через env `EKOTOV_WEATHER_CACHE_PATH`
- **Шаги:**
  1. На unit-уровне подставить httpx.MockTransport, захватывающий URL/params запроса.
  2. Прогнать сценарий «кэш истек → запрос провайдера».
  3. Проверить captured query и перечень внешних вызовов.
- **Ожидаемый результат:** URL = api.open-meteo.com Forecast API, параметры: latitude=55.7539, longitude=37.6208, timezone=Europe/Moscow, forecast_days=7, wind_speed_unit=ms; current = temperature_2m, apparent_temperature, weather_code, relative_humidity_2m, surface_pressure, wind_speed_10m, wind_direction_10m; daily = weather_code, temperature_2m_max, temperature_2m_min, precipitation_probability_max, wind_speed_10m_max, wind_direction_10m_dominant; `current.precipitation` НЕ запрашивается; других внешних HTTP-вызовов сервис не делает (счетчик mock-транспорта = 1).
- **Тестовые данные:** mock-транспорта-регистратор запросов; эталонный набор параметров design §3.
