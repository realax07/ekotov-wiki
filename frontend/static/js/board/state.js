/* Общее состояние и константы доски (P6: извлечено из board.js).
 *
 * currentTaskId в монолите была одной переменной замыкания, общей для
 * формы задачи, карточки и обработчиков: create/edit → null|id,
 * открытая карточка → id, submitComment/delete/move читают ее как
 * цель запроса. Поведение сохранено дословно — та же единственная
 * переменная, просто в модуле-состоянии (иначе cycle form ↔ detail).
 *
 * COLUMNS — три неизменяемых столбца доски (ОГР-3, sdd §3.3); в
 * монолите дублировалась константой STATUSES (не использовалась —
 * не переносится).
 *
 * P23 (openspec/changes/p23-fastline): зона FASTLINE над канбаном.
 * FASTLINE_STAGES — три столбца-этапа зоны (Ожидает/В работе/Выполнено);
 * ЭТАП ЗОНЫ = существующее поле status (design §2: маппинг 1:1, БЕЗ
 * нового поля fastline_stage). isFastTask — единственный признак
 * fast-карты (по is_fast из GET /api/board): разделение зоны/канбана —
 * клиентское (design §3). boardState.fastlineBusy — «слот занят»
 * (активная fast в todo/in_progress), вычисляется cards.js при каждом
 * рендере из последнего GET /api/board; читают гейты доступности
 * (кнопка — cards.js, чекбокс edit-формы — task-form.js 2.5).
 */
"use strict";

export const COLUMNS = ["todo", "in_progress", "done"];

export const FASTLINE_STAGES = ["todo", "in_progress", "done"];

export function isFastTask(task) {
  return !!task.is_fast;
}

export const boardState = { currentTaskId: null, fastlineBusy: false };
