# TC-GAL-120 — Инфра: 503-деградация при остановленном images (управляемый отказ, соседи не затронуты)

- **Change:** add-gallery-service
- **Источник:** gallery (ADDED): «Изображения обслуживаются отдельным сервисом images» (FR-79) — Scenario «Деградация при отказе images»; deploy (MODIFIED): error_page-паттерн @images_down по образцу @search_down; CHK-GAL-3
- **Тип:** НФТ, инфраструктура, нег. + сред. | **Приоритет:** Must
- **Маркер:** ручной/стендовый — REPORT-2.1 (инфра-чеки 503)
- **Предусловия:** стенд поднят, все контейнеры healthy; активная сессия в браузере (открыта /gallery)
- **Шаги:**
  1. Зафиксировать базовое поведение: `GET /api/images` через nginx → 200.
  2. `docker compose stop images` (или `docker stop <images>`); засечь время ответа `GET /api/images` и `GET /api/images/<id>` через nginx — код, тело (JSON), заголовок Retry-After.
  3. Проверить соседей: `/api/tasks`, `/api/search`, страницы `/`, `/tasks`, `/wiki` — работают как прежде; доска, поиск и страницы доступны.
  4. `docker compose start images`, дождаться healthcheck; повторить `GET /api/images` — восстановление; убедиться в отсутствии stale-DNS (resolver 127.0.0.11 valid=10s — восстановление без перезагрузки nginx).
- **Ожидаемый результат:** шаг 2 — nginx отвечает БЫСТРЫМ управляемым 503 на `/api/images*` (паттерн @images_down: JSON-тело + Retry-After, не таймаут 60s); шаг 3 — доска, поиск и страницы работают как прежде (отказ images изолирован); шаг 4 — после restart images восстановление без stale-DNS, `/api/images*` снова 200.
