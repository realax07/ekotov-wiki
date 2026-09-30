/* View-модалка карточки задачи: read-only просмотр (4.1; FR-47, Д-9,
 * ОГР-18; дельта board «Просмотр карточки задачи — модальное окно
 * read-only», все 5 сценариев — первичный источник поведения).
 *
 * До Релиза 4 клик по карточке открывал окно деталей с полями
 * редактирования (селект «Столбец», «Удалить», форма комментария).
 * 4.1 разделяет его (design §6: «openTaskDetail переосмысляется»):
 * просмотр — read-only модалка БЕЗ полей ввода и сохранения; из
 * действий — только «Редактировать» (открывает существующую task-form
 * в режиме редактирования, Д-9) и закрытие (крестик/«Закрыть»/Escape/
 * клик вне, сценарий 5). Действия с задачей (перемещение, удаление,
 * добавление комментария) перенесены в форму редактирования
 * (task-form.js) без изменения механики.
 *
 * Состав просмотра (сценарии 1 и 4): название, описание, статус,
 * приоритет, категория, срок, теги, fast-признак, assigned/creator,
 * комментарии. assigned/creator рендерятся только при наличии
 * соотв. полей в ответе GET /api/tasks/{id} (появятся в задаче 5.1);
 * сейчас их в ответе нет — ряды не выводятся, данные не выдумываются.
 * Пустой assigned — курсивом «Unassigned» (ОВ-24). done_at — ряд
 * «Выполнено» при наличии (sdd §3.2, r5); created_at в схеме Task
 * (sdd §3.2) отсутствует — в view не показывается.
 *
 * Визуальная отличимость от форм (ОГР-18): отсутствие полей ввода +
 * оформление .task-view (board.css, токены V3).
 *
 * XSS (ОГР-11): рендер значений — textContent, не innerHTML.
 */
"use strict";

import { el, showFormError, hideError } from "./dom.js";
import { api } from "./api.js";
import { boardState } from "./state.js";
import {
  openEditForm,
  renderComments,
  loadComments,
} from "./task-form.js";

/* --- Read-only рендер (FR-47; сценарии 1, 4) --- */

function addDetailRow(dl, term, value) {
  if (value === null || value === undefined || value === "") {
    return;
  }
  dl.appendChild(el("dt", null, term));
  var dd = el("dd");
  dd.textContent = String(value); // textContent — не innerHTML (XSS)
  dl.appendChild(dd);
}

/* Ряд пользователя (assigned/creator, сценарий 4): имя или курсивом
 * «Unassigned» при пустом (ОВ-24). Выводится только при наличии поля
 * в ответе API (5.1) — до того ряд не создается вовсе. */
function addUserRow(dl, term, login) {
  dl.appendChild(el("dt", null, term));
  var dd = el("dd");
  if (login) {
    dd.textContent = String(login); // textContent — не innerHTML (XSS)
  } else {
    dd.appendChild(el("em", "task-view-unassigned", "Unassigned"));
  }
  dl.appendChild(dd);
}

var STATUS_LABELS = {
  todo: "Ожидает",
  in_progress: "В работе",
  done: "Выполнено",
};

function renderTaskDetail(task) {
  boardState.currentTaskId = task.id;
  document.getElementById("task-detail-title").textContent = task.title;

  var dl = document.getElementById("task-detail-attrs");
  dl.textContent = "";
  addDetailRow(dl, "Описание", task.description);
  /* Приоритет в просмотре — сырым значением (контракт утвержденного
   * e2e TC-UI-009: attrs содержат ровно значения задачи); цвет+иконка
   * приоритета — в форме (пилюля) и на карточке доски (бейдж, FR-29). */
  addDetailRow(dl, "Приоритет", task.priority);
  addDetailRow(dl, "Категория", task.category);
  addDetailRow(dl, "Срок", task.due_date);
  addDetailRow(dl, "Статус", STATUS_LABELS[task.status]);
  addDetailRow(dl, "Теги", (task.tags || []).join(", "));
  addDetailRow(dl, "Fast line", task.is_fast ? "да" : null);
  /* 4.1 (сценарий 4): creator/assigned — при наличии полей в ответе
   * API (задача 5.1); сейчас их там нет — ряды не выводятся. */
  if (Object.prototype.hasOwnProperty.call(task, "assigned")) {
    addUserRow(dl, "Исполнитель", task.assigned);
  }
  if (Object.prototype.hasOwnProperty.call(task, "creator")) {
    addUserRow(dl, "Создатель", task.creator);
  }
  /* Момент перевода в «Выполнено» (sdd §3.2 r5); created_at в схеме
   * Task отсутствует — не показывается (данные не выдумываются). */
  addDetailRow(dl, "Выполнено", task.done_at);
  /* 6.2 (FR-4): признак «архивная» — бейдж при archived_at IS NOT NULL. */
  document.getElementById("task-detail-archive-badge").hidden =
    !task.archived_at;
  hideError("task-detail-error");
}

function isValidTaskId(value) {
  return typeof value === "number" && isFinite(value);
}

/* --- Открытие/закрытие (сценарии 1 и 5: закрытие без изменения данных) --- */

export function openTaskDetail(taskId) {
  if (!isValidTaskId(taskId)) {
    return;
  }
  boardState.currentTaskId = taskId;
  document.getElementById("task-detail-overlay").hidden = false;
  renderComments(document.getElementById("task-comments-list"), []);
  /* GET /api/tasks/{id} — полный Task (sdd §3.2), затем комментарии. */
  api(
    "/api/tasks/" + taskId,
    {},
    function (message) {
      showFormError("task-detail-error", message);
    },
    function (task) {
      renderTaskDetail(task);
      loadComments(
        taskId,
        document.getElementById("task-comments-list"),
        function (message) {
          showFormError("task-detail-error", message);
        }
      );
    }
  );
}

export function closeTaskDetail() {
  document.getElementById("task-detail-overlay").hidden = true;
}

/* --- Управление view-модалкой: «Редактировать» (Д-9), закрытие --- */

export function initTaskViewControls() {
  /* Д-9 (сценарий 3): «Редактировать» → существующая форма
   * редактирования этой задачи. Свежая копия задачи
   * (GET /api/tasks/{id}) — как до 4.1. */
  document
    .getElementById("task-edit-button")
    .addEventListener("click", function () {
      if (boardState.currentTaskId === null) {
        return;
      }
      api(
        "/api/tasks/" + boardState.currentTaskId,
        {},
        function (message) {
          showFormError("task-detail-error", message);
        },
        openEditForm
      );
    });
  document
    .getElementById("task-detail-close")
    .addEventListener("click", closeTaskDetail);
  document
    .getElementById("task-view-close")
    .addEventListener("click", closeTaskDetail);
  /* Закрытие Escape (сценарий 5): только когда открыта view-модалка и
   * не открыта форма (Escape формы спекой не нормирован — не трогаем). */
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") {
      return;
    }
    var view = document.getElementById("task-detail-overlay");
    var form = document.getElementById("task-form-overlay");
    if (!view.hidden && form.hidden) {
      closeTaskDetail();
    }
  });
}
