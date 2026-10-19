# TC-weather-020 — Кэш в томе переживает пересоздание контейнера; данных в репозитории и БД нет

- **Change:** weather-service
- **Источник:** weather-service: «Отдельный контейнерный сервис weather…» / Scenario: Кэш в томе переживает пересоздание контейнера
- **Тип:** позитивный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`; docker-доступ к стенду wiki-test (compose.test.yaml): контейнер `weather`, том `weather-cache`, конфиг nginx
- **Шаги:**
  1. Прогреть кэш живым запросом, зафиксировать `fetched_at` T0.
  2. Выполнить `docker compose down && up` (пересоздание контейнера).
  3. Выполнить `/api/weather` до истечения TTL; осмотреть том `weather-cache`.
  4. Проверить отсутствие погодных данных в git-репозитории и БД ядра.
- **Ожидаемый результат:** после пересоздания кэш-файл присутствует в томе `weather-cache`, первый запрос отдан из кэша с `fetched_at` = T0 без вызова провайдера; в репозитории и БД данных погоды нет.
- **Тестовые данные:** docker compose down/up; кэш-файл; `git status` и sqlite-схема БД (таблиц weather_* нет).
