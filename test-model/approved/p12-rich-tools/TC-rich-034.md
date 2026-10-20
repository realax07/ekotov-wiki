# TC-rich-034 — Скрипт и onclick вырезаются до рендера (базовая санитизация)

- **Change:** p12-rich-tools
- **Источник:** p12-rich-tools: wiki: «Санитизация HTML контента» / Scenario: Скрипт вырезается при отображении
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); тестовая страница wiki, созданная через `POST {BASE_URL}/api/wiki/pages`; Playwright (Python): `page`, `expect`, `api_request_context`
- **Шаги:**
  1. Через `PUT` записать контент со `<script>alert(1)</script>` и `<img src=x onerror=alert(2)>` вне rich-блоков (вставка HTML).
  2. Получить `GET`-контент.
  3. Открыть статью, осмотреть консоль.
- **Ожидаемый результат:** в отдаваемом HTML скрипт и обработчик отсутствуют — санитизация по whitelist удаляет их ДО рендера; alert не исполняется, ошибок в консоли нет (NFR-31).
- **Тестовые данные:** XSS-векторы: script, onerror
