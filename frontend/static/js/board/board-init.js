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
 *
 * 4.1 Релиза 4 (FR-47, Д-9): клик по карточке открывает view-модалку
 * (task-detail.js, read-only); редактирование и действия с задачей
 * (селект «Столбец», «Удалить», комментарии) — из view кнопкой
 * «Редактировать» в существующей task-form (task-form.js).
 */
"use strict";

import { COLUMNS } from "./state.js";
import { showBoardError, hideError } from "./dom.js";
import {
  refreshBoard,
  setCardClickHandler,
  setQuickDoneHandler,
  initCardDragAndDrop,
} from "./cards.js";
import {
  openCreateForm,
  submitTaskForm,
  closeTaskForm,
  initTaskActions,
  submitComment,
} from "./task-form.js";
import {
  openTaskDetail,
  initTaskViewControls,
} from "./task-detail.js";
import { initMobileModalShell } from "./modal-shell.js";
import { initBoardDots } from "./board-dots.js";

/* --- Инициализация --- */

/* 2.2 add-responsive-mobile (FR-102, design §4): мобильная fullscreen-
 * оболочка модалок — блокировка скролла страницы под модалкой с точным
 * возвратом позиции при закрытии + scrollIntoView активного поля
 * (клавиатура iOS). До подписок модалок: MutationObserver на overlay
 * ловит открытие любым путем (openCreateForm/openTaskDetail). */
initMobileModalShell();

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

/* 4.1 Релиза 4: подписка действий с задачей (селект «Столбец»,
 * «Удалить») — обработчики в task-form.js рядом с их логикой. */
initTaskActions();
document
  .getElementById("comment-form")
  .addEventListener("submit", submitComment);

/* Управление view-модалкой («Редактировать», закрытие, Escape). */
initTaskViewControls();

[document.getElementById("task-form-overlay"),
 document.getElementById("task-detail-overlay")].forEach(function (overlay) {
  overlay.addEventListener("click", function (event) {
    if (event.target === overlay) {
      overlay.hidden = true;
    }
  });
});

/* Клик по карточке → view-модалка (read-only, FR-47; инъекция вместо
 * импорта — разрыв цикла cards ↔ task-detail, см. cards.js). */
setCardClickHandler(openTaskDetail);

/* 2.1 add-responsive-mobile (FR-101, design §3): быстрое «Выполнено» на
 * карточке — тот же POST /api/tasks/{id}/move, что и DnD/селект (ОГР-14);
 * отказ (409 иные) — ошибка в #board-error + перерисовка (Д-6-паттерн). */
setQuickDoneHandler(function (taskId) {
  fetch("/api/tasks/" + taskId + "/move", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ status: "done" }),
  }).then(function (response) {
    if (!response.ok) {
      response
        .json()
        .catch(function () { return {}; })
        .then(function (body) {
          showBoardError(body.error || "Не удалось переместить задачу");
        });
    } else {
      hideError("board-error");
    }
    refreshBoard();
  });
});

/* 2.1 add-responsive-mobile (FR-101, design §3): индикатор точек мобильной
 * доски — активная точка синхронна scroll-позиции, тап — скролл к колонке
 * (smooth; reduced-motion — без анимации, ОГР-17). Разметка — после #board,
 * видима только в мобильной ветке ≤480px (см. board.css). */
initBoardDots();

/* 2.1/2.2 Релиза 3 (FR-31): drag-and-drop карточек между столбцами —
 * обработчики на контейнере #board (делегирование, см. cards.js). */
initCardDragAndDrop();

void COLUMNS; // столбцы рендерит cards.js; список закреплен здесь (ОГР-3)

refreshBoard();
