# TC-rich-023 — Подмена значений data-атрибутов — снятие и деградация

- **Change:** p12-rich-tools
- **Источник:** p12-rich-tools: «Безопасность и деградация rich-блоков (NFR-39)» / Scenario: Подмена значений data-атрибутов
- **Тип:** негативный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner `owner/QaOwner_Pass_1!`, второй пользователь `pe/QaPe_Pass_1!` (seed); тестовая страница wiki, созданная через `POST {BASE_URL}/api/wiki/pages`; Playwright (Python): `page`, `expect`, `api_request_context`
- **Шаги:**
  1. Через `PUT` записать `<div data-block="evil" data-lang="javascript">текст</div>` (оба значения вне словаря design §1).
  2. Получить `GET`-контент, открыть статью.
  3. Проверить консоль и попытаться исполнить что-либо из контента.
- **Ожидаемый результат:** невалидные `data-block` и `data-lang` сняты (`_safe_block_attr`): блок деградировал в обычный контент «текст»; в отдаваемом HTML нет `data-block="evil"`; исполнение кода невозможно, ошибок нет (NFR-39).
- **Тестовые данные:** подмененные значения `evil`, `javascript`
