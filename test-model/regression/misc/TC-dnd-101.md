# TC-dnd-101 — DnD: перетаскивание карточки в другой столбец

- **CHK:** CHK-157
- **Change:** add-r3-visual-foundation
- **Источник:** board: «Перемещение карточки перетаскиванием» (FR-31, ОВ-19); Сценарий «Перетаскивание карточки в другой столбец»
- **Тип:** поз. | **Приоритет:** Must
- **Среда/предусловия:** web-стенд tests/web; вход owner; доска загружена (`data-loaded=true`); задача «QAT-dnd-перенос» в столбце «Ожидает» (создана самим тестом, префикс QAT, удаление в teardown). Механика: Playwright НЕ эмулирует нативный HTML5 DnD мышью — события возбуждаются `dispatchEvent` (dragstart/dragover/drop/dragend) с общим объектом `DataTransfer` (урок architect-ревью).
- **Шаги:**
  1. Найти карточку задачи; создать `new DataTransfer()`.
  2. `dispatchEvent('dragstart', {dataTransfer})` на карточке; прочитать class карточки.
  3. `dispatchEvent('dragover', {dataTransfer})` на секции столбца «В работе» (`[data-status="in_progress"]`); прочитать class столбца.
  4. `dispatchEvent('drop', {dataTransfer})` на том же столбце; `dispatchEvent('dragend', {dataTransfer})` на карточке.
  5. Автожидание: карточка появилась в `[data-status="in_progress"] [data-cards]`; затем `GET /api/board` API-сессией.
- **Ожидаемый результат:** шаг 2 — карточка имеет класс `drag-ghost` (прикреплена к курсору, исчезла с исходного места — визуал CSS); шаг 3 — столбец имеет класс `drop-target` (подсветка зоны-приемника); шаг 5 — карточка отображается в «В работе», сервер показывает статус `in_progress` — тот же результат, что при переводе существующим способом (ОГР-14).
- **Тестовые данные:** задача `QAT-dnd-перенос` (title), статус до: `todo`, после: `in_progress`.
