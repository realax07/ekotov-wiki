# TC-weather-024 — NFR: healthcheck, mem_limit, ротация логов, резерв хосту ≥ 2 GB

- **Change:** weather-service
- **Источник:** weather-service: «Ресурсы и здоровье сервиса weather (NFR)» / Scenario: Здоровье и лимиты на стенде
- **Тип:** НФТ | **Приоритет:** Should
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`; docker-доступ к стенду wiki-test (compose.test.yaml): контейнер `weather`, том `weather-cache`, конфиг nginx
- **Шаги:**
  1. Проверить `GET {BASE_URL}/api/health` и docker healthcheck контейнера `weather`.
  2. Выполнить профиль обычной нагрузки (периодические запросы `/weather` и `/api/weather`, 10 мин), снимать `docker stats`.
  3. Проверить mem_limit, logging (json-file 10m×3) и суммарные лимиты стека; сверить с REPORT.
- **Ожидаемый результат:** healthcheck отвечает (healthy); потребление RAM контейнера в пределах mem_limit на всем профиле; ротация логов json-file 10m×3 настроена; суммарные лимиты стека сохраняют резерв хосту ≥ 2 GB; замеры зафиксированы в REPORT до выкатки.
- **Тестовые данные:** docker stats/inspect; REPORT стенда.
