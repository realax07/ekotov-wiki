# TC-dnd-102 — DnD: отпускание вне зоны столбца возвращает карточку

- **CHK:** CHK-158
- **Change:** add-r3-visual-foundation
- **Источник:** board: «Перемещение карточки перетаскиванием» (FR-31); Сценарий «Отпускание вне зоны столбца возвращает карточку»
- **Тип:** нег. | **Приоритет:** Must
- **Среда/предусловия:** web-стенд tests/web; вход owner; задача «QAT-dnd-вне-зоны» в «Ожидает». Механика — dispatchEvent с DataTransfer (урок architect-ревью).
- **Шаги:**
  1. `dispatchEvent('dragstart', {dataTransfer})` на карточке; перехватить сетевые запросы страницы (page.on request / route-счетчик POST /api/tasks/*/move).
  2. `dispatchEvent('dragover', {dataTransfer})` на элементе ВНЕ `.board-column` (например, заголовок страницы `h1.page-title`).
  3. `dispatchEvent('drop', {dataTransfer})` там же; `dispatchEvent('dragend', {dataTransfer})` на карточке.
  4. Автожидание статичности доски; `GET /api/board`.
- **Ожидаемый результат:** запрос POST /api/tasks/{id}/move НЕ отправлялся (счетчик 0); dragover вне столбца не ставит `drop-target` (preventDefault не вызван — drop браузер не разрешит); после dragend класс `drag-ghost` снят, карточка на исходном месте; сервер: статус `todo` не изменился.
- **Тестовые данные:** задача `QAT-dnd-вне-зоны` (title), статус `todo` до и после.
