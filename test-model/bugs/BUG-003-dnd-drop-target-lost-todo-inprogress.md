# BUG-003: подсветка drop-target не удерживается на столбцах todo/in_progress

- **Кейс:** TC-dnd-101/103/106, TC-vis-103 (CHK-157, CHK-159, CHK-163, CHK-166) —
  «столбец-приемник подсвечен (класс `drop-target`) при dragover».
- **Окружение:** стенд tests/web (uvicorn + http.server, chromium headless, playwright 1.63).
- **Ожидание (кейсы):** dragover на столбце-приемнике ставит и УДЕРЖИВАЕТ класс
  `drop-target` на этом столбце (пресет В, board.css `.preset-v .board-column.drop-target`).
- **Факт:** класс ставится и немедленно снимается в том же вызове обработчика
  для столбцов `todo` и `in_progress`; удерживается только на `done` (последнем
  в `COLUMNS`). Устойчиво воспроизводится (dispatchEvent-механика кейсов,
  синтетический `DataTransfer`; автоожидание и кадры rAF не меняют результат).

## Диагноз (frontend/static/js/board/cards.js, `onDragOver`, строки ~246–248)

```js
COLUMNS.forEach(function (status) {
  column.classList.toggle("drop-target", status === column.dataset.status);
});
```

Замысел — «класс только на текущем столбце»: на каждой итерации снимается
класс со «всех прочих». Но `column` не меняется между итерациями — все три
`toggle` применяются к ОДНОМУ и тому же столбцу-приемнику:

- `COLUMNS = ["todo", "in_progress", "done"]` (state.js);
- dragover на `todo`: итерация 1 ставит класс (`'todo'==='todo'` → true),
  итерации 2–3 СНИМАЮТ его с того же элемента (`'in_progress'==='todo'` → false);
- dragover на `in_progress`: итерация 1 снимает, 2 ставит, 3 снимает — класс
  не удерживается;
- dragover на `done`: единственный выживающий случай — добавление в последней
  итерации.

Подсветка работает только для «Выполнено», у «Ожидает»/«В работе» визуально
отсутствует (FR-31/CHK-157 не выполняется для 2 из 3 столбцов; TC-vis-103 —
«подсветка drop-target» — падает на перенос в «В работе»).

## Воспроизведение (автотесты этапа 5)

- `tests/web/test_r3_dnd_ui.py::test_dnd_move_card_to_another_column` —
  dragover на `[data-status="in_progress"]` → в классе столбца нет `drop-target`.
- Инструментально: инструментированный `DOMTokenList.prototype.toggle`
  логирует в пределах ОДНОГО dragover: `force=true` (итерация todo), затем
  `force=false` на том же элементе (итерация in_progress).

## Предложение исправления

Тоглить класс только на текущем столбце, снимать — с остальных:

```js
COLUMNS.forEach(function (status) {
  var col = document.querySelector('.board-column[data-status="' + status + '"]');
  if (col) col.classList.toggle("drop-target", status === column.dataset.status);
});
```

(или `clearDropHighlight(); column.classList.add("drop-target");`).

## Статус

Автотесты написаны по кейсам как есть (ассерты не ослаблены): падение =
дефект продукта, тест-код не подгоняется. До исправления падают
`test_r3_dnd_ui.py::test_dnd_move_card_to_another_column`,
`test_dnd_fast_line_occupied_409_error_and_return`,
`test_dnd_success_after_409_hides_board_error` и
`test_r3_vis_ui.py::test_reduced_motion_disables_animations_keeps_function`
(TC-vis-105, шаг 2 «подсветка drop-target применяется» на переводе в
«В работе») — все на отсутствии `drop-target` вне столбца done.
Функциональная часть (сам перенос/409/скрытие ошибки) при этом работает:
падает только подсветка приемника.
