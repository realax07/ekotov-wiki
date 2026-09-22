/* Точка входа доски (P6: инициализация из board.js; tasks.md 4.3, 4.5,
 * 5.2 Релиза 1, 2.5; FR-1, FR-2, FR-3, FR-5, FR-7, FR-9, FR-28; sdd.md
 * §3.2, §3.3).
 *
 * Подключение в board.html: <script type="module"
 * src="/static/js/board/board-init.js">. app.js (base.html, классический
 * скрипт) не конфликтует: модуль исполняется в своем скоупе, глобали
 * не создает. При открытии страницы GET /api/board и рендер задач по
 * трем столбцам COLUMNS — todo, in_progress и done (ОГР-3). Веб-морда —
 * клиент REST API (ОГР-2, design.md §7): данные только через API,
 * сессионная кука — credentials: "same-origin".
 */
"use strict";

import { COLUMNS } from "./state.js";
import { refreshBoard, setCardClickHandler } from "./cards.js";
import { openCreateForm, submitTaskForm, closeTaskForm } from "./task-form.js";
import {
  openTaskDetail,
  initTaskDetailControls,
} from "./task-detail.js";

/* --- Инициализация --- */

document
  .getElementById("create-task-button")
  .addEventListener("click", openCreateForm);

document
  .getElementById("task-form")
  .addEventListener("submit", submitTaskForm);
document
  .getElementById("task-form-cancel")
  .addEventListener("click", closeTaskForm);

/* 5.1 (FR-28): крестик закрытия формы — правый верхний угол; закрытие
 * без сохранения — тот же closeTaskForm, что и «Отмена». */
document
  .getElementById("task-form-close")
  .addEventListener("click", closeTaskForm);

initTaskDetailControls();

[document.getElementById("task-form-overlay"),
 document.getElementById("task-detail-overlay")].forEach(function (overlay) {
  overlay.addEventListener("click", function (event) {
    if (event.target === overlay) {
      overlay.hidden = true;
    }
  });
});

/* Клик по карточке → карточка задачи (инъекция вместо импорта —
 * разрыв цикла cards ↔ task-detail, см. cards.js). */
setCardClickHandler(openTaskDetail);

void COLUMNS; // столбцы рендерит cards.js; список закреплен здесь (ОГР-3)

refreshBoard();
