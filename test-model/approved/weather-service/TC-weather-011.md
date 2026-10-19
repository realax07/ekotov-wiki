# TC-weather-011 — Граница TTL: 59:59 — из кэша, ровно 60:00 — обновление с провайдера

- **Change:** weather-service
- **Источник:** weather-service: «Кэш 60 минут» (граница TTL; сценарии «Повторные запросы…» + «Истечение TTL…»)
- **Тип:** граничный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`; unit/integration-уровень: `services/weather` pytest с httpx.MockTransport (провайдер мокается, т.к. URL Open-Meteo зашит в конфиге); кэш — временный файл через env `EKOTOV_WEATHER_CACHE_PATH`
- **Шаги:**
  1. Прогреть кэш (fetched_at = T0), выставить mock-счетчик провайдера в 0.
  2. Сместить fetched_at в кэш-файле на 59:59 назад, выполнить `/api/weather`.
  3. Сместить fetched_at ровно на 60:00 назад, выполнить `/api/weather` снова.
- **Ожидаемый результат:** шаг 2 — ответ из кэша, `stale: false`, вызовов провайдера нет; шаг 3 — сервис запрашивает провайдера, возвращает свежие данные с новым `fetched_at`, кэш-файл перезаписан (граница инклюзивна к обновлению: ≥ 60 мин = истек).
- **Тестовые данные:** правка `fetched_at` в кэш-файле (`EKOTOV_WEATHER_CACHE_PATH`); mock-счетчик провайдера.
