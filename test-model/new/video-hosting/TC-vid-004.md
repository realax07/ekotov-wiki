# TC-vid-004 — Маршрутизация /api/videos и деградация 503 при остановке video

- **Change:** video-hosting
- **Источник:** video-service: «Отдельный контейнерный сервис video, файлы вне БД» (FR-79) / Scenario: Маршрутизация и деградация
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); Playwright (Python): `page`, `expect`, `api_request_context`; прод-стек поднят, контейнер `video` запущен; доступ к хосту для `docker`
- **Шаги:**
  1. `GET {BASE_URL}/api/videos` с сессией owner.
  2. `docker stop <video-контейнер>`.
  3. Сразу повторить `GET {BASE_URL}/api/videos` и `GET {BASE_URL}/videos/<known>/preview.jpg`, замерить время ответа.
  4. Открыть доску, поиск, wiki, галерею.
  5. `docker start <video-контейнер>`.
- **Ожидаемый результат:** шаг 1 — 200 и JSON-список (проксирование сервису); шаг 3 — оба маршрута `/api/videos*` и `/videos/` отвечают HTTP 503 за < 2 с (не таймаут, управляемый ответ); шаг 4 — доска/поиск/wiki/галерея работают как прежде; шаг 5 — `/api/videos` снова 200.
- **Тестовые данные:** заведомо существующий `id` видео с `preview.jpg`; имя контейнера из `docker ps`.
