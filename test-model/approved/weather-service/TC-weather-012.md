# TC-weather-012 — Истечение TTL при доступном провайдере: обновление, новый fetched_at, переживает перезапуск

- **Change:** weather-service
- **Источник:** weather-service: «Кэш 60 минут» / Scenario: Истечение TTL — обновление с провайдера
- **Тип:** позитивный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`; docker-доступ к стенду wiki-test (compose.test.yaml): контейнер `weather`, том `weather-cache`, конфиг nginx
- **Шаги:**
  1. Прогреть кэш, дождаться/смоделировать возраст кэша > 60 минут.
  2. Выполнить `/api/weather`, зафиксировать `fetched_at` и содержимое кэш-файла.
  3. Перезапустить контейнер `weather` (docker restart). Повторить `/api/weather` до истечения нового TTL.
- **Ожидаемый результат:** шаг 2 — данные свежие с провайдера, новый `fetched_at`, кэш-файл в томе `weather-cache` обновлен; шаг 3 — после перезапуска ответ отдается из кэша с тем же `fetched_at` (кэш-файл в томе пережил перезапуск).
- **Тестовые данные:** доступ docker к стенду; кэш-файл `/cache/weather.json` в томе `weather-cache`.
