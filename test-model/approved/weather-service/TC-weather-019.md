# TC-weather-019 — Деградация: остановка контейнера weather — быстрый 503 nginx, стек работает

- **Change:** weather-service
- **Источник:** weather-service: «Отдельный контейнерный сервис weather, кэш-файл в томе, без БД» / Scenario: Маршрутизация и деградация
- **Тип:** НФТ | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`; docker-доступ к стенду wiki-test (compose.test.yaml): контейнер `weather`, том `weather-cache`, конфиг nginx
- **Шаги:**
  1. Под owner выполнить `GET /api/weather` на живом стеке.
  2. Остановить контейнер `weather` (docker stop).
  3. Повторить `GET /api/weather` 5×, замерить времена и тела ответов.
  4. Проверить доску, поиск, wiki, галерею, видео.
- **Ожидаемый результат:** шаг 1 — запрос проксируется сервису `weather` (200); шаг 3 — nginx отвечает на `/api/weather*` быстрым управляемым 503 (JSON + Retry-After; каждый ответ < 1–2 с, не таймаут шлюза 502/504 по 60 с); шаг 4 — остальные разделы работают как прежде.
- **Тестовые данные:** docker stop/start контейнера weather; секундомер.
