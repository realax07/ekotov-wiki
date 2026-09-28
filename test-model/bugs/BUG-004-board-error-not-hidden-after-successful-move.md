# BUG-004: #board-error не скрывается после успешного перевода задачи

- **Кейс:** TC-dnd-106 (`test_dnd_success_after_409_hides_board_error`,
  tests/web/test_r3_dnd_ui.py) — «после 409 следующий успешный DnD скрывает
  #board-error».
- **Окружение:** стенд tests/web (uvicorn + http.server, chromium headless),
  ветка main после мерджа add-r3-visual-foundation (merge `23c8187`, включая
  фикс BUG-003 `f74c932`).
- **Ожидание (кейс, CHK/Д-6):** после успешного перевода (#board-error был
  показан по 409 «fast line занята») старое сообщение не висит — бокс скрыт.
- **Факт:** `#board-error` остается видимым с текстом «fast line занята» после
  успешного DnD-перевода. Воспроизводится детерминированно (3 прогона:
  полный сьют + 2 изолированных).

## Диагноз

Продукт нигде не скрывает `#board-error` после успешного действия:

- показ: `showBoardError()` (`frontend/static/js/board/dom.js:20`,
  `box.hidden = false`) — вызывается из `moveTask` onErr (cards.js:202) и из
  `refreshBoard` onErr (cards.js:160);
- скрытие: `hideError("board-error")` в коде доски — **0 вхождений**
  (`hideError` используется только для `task-detail-error`, `comment-error`,
  `task-form-error` в task-detail.js / task-form.js);
- `renderBoard()` (cards.js:128–157) перерисовывает столбцы, но не трогает
  `#board-error` — атрибут `hidden` (board.html:58) не восстанавливается.

История: бокс изначально — «ошибка загрузки доски» (перезагрузка страницы
очищает состояние); с 2.1/2.2 (Д-6) в него пишутся ошибки перевода, и
устаревшее сообщение стало вводить в заблуждение. Обнаружено при прогоне
BUG-003 (указан ПМ как кандидат BUG-004).

## Предложение исправления (на следующий цикл, задача не назначена)

В `renderBoard()` (или в onOk-ветке `moveTask` перед `refreshBoard`)
восстанавливать `hidden` и очищать текст:

```js
var box = document.getElementById("board-error");
box.textContent = "";
box.hidden = true;
```

(готовый хелпер `hideError("board-error")` из dom.js). После фикса ожидается
XPASS теста TC-dnd-106 (ассерт в тесте уже «правильный», ослаблений нет).

## Статус

НЕ исправляется в рамках Релиза 3 (решение ПМ): оформлен для следующего цикла.
До фикса TC-dnd-106 падает по продуктовому ассерту; требование кейса
не выполняется (продуктовый дефект, не теста).
