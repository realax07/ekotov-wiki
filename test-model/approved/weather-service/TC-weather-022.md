# TC-weather-022 — nginx: /api/weather* — только за middleware сервиса; деградация без auth_request и подмены 503

- **Change:** weather-service
- **Источник:** weather-service: «nginx-маршрутизация API погоды (только /api/weather*)» / Scenario: API-семейство за middleware, деградация nginx
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`; docker-доступ к стенду wiki-test (compose.test.yaml): контейнер `weather`, том `weather-cache`, конфиг nginx
- **Шаги:**
  1. Без сессии выполнить `GET /api/weather` и `GET /api/weather/anything`.
  2. С валидной сессией остановить контейнер `weather` и повторить запросы.
  3. С валидной сессией заставить живой сервис вернуть 503 `weather_unavailable` (пустой кэш + недоступный провайдер, см. TC-weather-016).
  4. Проверить конфиг nginx: location `/api/weather*`, `/weather`.
- **Ожидаемый результат:** шаг 1 — 401 JSON от middleware сервиса (не 30x/401 от auth_request — на API-локациях auth_request не используется); шаг 2 — быстрый управляемый 503 nginx (JSON + Retry-After); шаг 3 — честный 503 `weather_unavailable` живого сервиса доходит до клиента без подмены (`proxy_intercept_errors` off); шаг 4 — nginx маршрутизирует только `/api/weather*`, страница `/weather` nginx'ом не обслуживается; upstream через переменную + resolver.
- **Тестовые данные:** запросы с/без cookie; docker stop; конфиг nginx стенда.
