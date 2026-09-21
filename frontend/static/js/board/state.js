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
 */
"use strict";

export const COLUMNS = ["todo", "in_progress", "done"];

export const boardState = { currentTaskId: null };
