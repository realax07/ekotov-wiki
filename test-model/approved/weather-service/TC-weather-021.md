# TC-weather-021 — Процессное: пакет не добавляет миграций и не трогает MIGRATE_MODULE

- **Change:** weather-service
- **Источник:** weather-service: «Отдельный контейнерный сервис weather…» / Scenario: Миграций у пакета нет
- **Тип:** процессный | **Приоритет:** Should
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`; docker-доступ к стенду wiki-test (compose.test.yaml): контейнер `weather`, том `weather-cache`, конфиг nginx
- **Шаги:**
  1. Осмотреть `services/weather/` на наличие каталога/файлов миграций.
  2. Выполнить деплой пакета на существующий стек, сравнить список примененных миграций ядра до/после.
  3. Проверить diff `MIGRATE_MODULE` и таблиц БД (sqlite `.schema`).
- **Ожидаемый результат:** в пакете нет миграций; список миграций ядра до/после деплоя идентичен; `MIGRATE_MODULE` ядром/пакетом не изменен; новых таблиц в БД нет.
- **Тестовые данные:** git-diff деплоя; вывод `.schema`/журнала миграций ядра.
