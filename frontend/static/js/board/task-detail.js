/* Карточка задачи: полный набор признаков + комментарии (P6: извлечено
 * из board.js; tasks.md 4.5; FR-9) и действия карточки (FR-7,
 * перемещение POST /{id}/move).
 *
 * 4.5: карточка с полными признаками и комментариями, удаление с
 * confirm (DELETE). Комментарии — GET/POST /api/tasks/{id}/comments
 * (sdd §3.2); guard submitComment — только из открытой карточки.
 * XSS (ОГР-11): рендер значений — textContent, не innerHTML.
 */
"use strict";

import { el, showFormError, hideError } from "./dom.js";
import { api } from "./api.js";
import { boardState } from "./state.js";
import { refreshBoard } from "./cards.js";
import { openEditForm } from "./task-form.js";

/* --- Карточка задачи: полный набор признаков + комментарии (FR-9) --- */

function addDetailRow(dl, term, value) {
  if (value === null || value === undefined || value === "") {
    return;
  }
  dl.appendChild(el("dt", null, term));
  var dd = el("dd");
  dd.textContent = String(value); // textContent — не innerHTML (XSS)
  dl.appendChild(dd);
}

function renderTaskDetail(task) {
  boardState.currentTaskId = task.id;
  document.getElementById("task-detail-title").textContent = task.title;

  var dl = document.getElementById("task-detail-attrs");
  dl.textContent = "";
  addDetailRow(dl, "Описание", task.description);
  addDetailRow(dl, "Приоритет", task.priority);
  addDetailRow(dl, "Категория", task.category);
  addDetailRow(dl, "Срок", task.due_date);
  addDetailRow(dl, "Теги", (task.tags || []).join(", "));
  addDetailRow(dl, "Fast line", task.is_fast ? "да" : null);
  /* 6.2 (FR-4): признак «архивная» — бейдж при archived_at IS NOT NULL.
   * Не-архивные (archived_at null) — бейдж скрыт. */
  document.getElementById("task-detail-archive-badge").hidden =
    !task.archived_at;
  document.getElementById("task-move-select").value = task.status;
  hideError("task-detail-error");
  hideError("comment-error");
}

export function renderComments(comments) {
  var list = document.getElementById("task-comments-list");
  list.textContent = "";
  (comments || []).forEach(function (comment) {
    var item = el("li", "task-comment");
    /* Метка только из имеющихся полей — без «· undefined». */
    var meta = ["id " + comment.id, comment.created_at]
      .filter(function (part) {
        return part !== undefined && part !== null && part !== "";
      })
      .join(" · ");
    if (meta) {
      item.appendChild(el("div", "task-comment-meta", meta));
    }
    var body = el("p", "task-comment-body");
    body.textContent = comment.body; // textContent — не innerHTML (XSS)
    item.appendChild(body);
    list.appendChild(item);
  });
}

function loadComments(taskId) {
  api(
    "/api/tasks/" + taskId + "/comments",
    {},
    function (message) {
      showFormError("comment-error", message);
    },
    function (body) {
      renderComments(body && body.comments);
    }
  );
}

function isValidTaskId(value) {
  return typeof value === "number" && isFinite(value);
}

export function openTaskDetail(taskId) {
  if (!isValidTaskId(taskId)) {
    return;
  }
  boardState.currentTaskId = taskId;
  document.getElementById("task-detail-overlay").hidden = false;
  renderComments([]);
  /* GET /api/tasks/{id} — полный Task (sdd §3.2), затем комментарии. */
  api(
    "/api/tasks/" + taskId,
    {},
    function (message) {
      showFormError("task-detail-error", message);
    },
    function (task) {
      renderTaskDetail(task);
      loadComments(taskId);
    }
  );
}

export function closeTaskDetail() {
  document.getElementById("task-detail-overlay").hidden = true;
}

export function submitComment(event) {
  event.preventDefault();
  hideError("comment-error");

  /* Guard (integer-баг): комментарий можно отправить только из
   * открытой карточки. Без задачи в currentTaskId путь был бы
   * /api/tasks/null/comments → 422 int_parsing от сервера. */
  if (!isValidTaskId(boardState.currentTaskId)) {
    showFormError(
      "comment-error",
      "Карточка задачи не открыта — откройте задачу и попробуйте еще раз."
    );
    return;
  }

  var body = document.getElementById("comment-body").value.trim();
  /* UI-валидация до отправки: текст обязателен (sdd §3.2, 422). */
  if (!body) {
    showFormError("comment-error", "Комментарий не может быть пустым.");
    return;
  }
  api(
    "/api/tasks/" + boardState.currentTaskId + "/comments",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: body }),
    },
    function (message) {
      showFormError("comment-error", message);
    },
    function () {
      document.getElementById("comment-body").value = "";
      loadComments(boardState.currentTaskId);
    }
  );
}

/* --- Действия карточки: редактирование, удаление, перемещение --- */

function deleteCurrentTask() {
  if (boardState.currentTaskId === null) {
    return;
  }
  var taskId = boardState.currentTaskId;
  /* Подтверждение удаления (FR-7). */
  if (!window.confirm("Удалить задачу? Действие необратимо.")) {
    return;
  }
  hideError("task-detail-error");
  api(
    "/api/tasks/" + taskId,
    { method: "DELETE" },
    function (message) {
      showFormError("task-detail-error", message);
    },
    function () {
      closeTaskDetail();
      refreshBoard();
    }
  );
}

function moveCurrentTask() {
  if (!isValidTaskId(boardState.currentTaskId)) {
    return;
  }
  var status = document.getElementById("task-move-select").value;
  hideError("task-detail-error");
  api(
    "/api/tasks/" + boardState.currentTaskId + "/move",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: status }),
    },
    function (message) {
      showFormError("task-detail-error", message);
    },
    function () {
      closeTaskDetail();
      refreshBoard();
    }
  );
}

export function initTaskDetailControls() {
  document
    .getElementById("comment-form")
    .addEventListener("submit", submitComment);
  document
    .getElementById("task-delete-button")
    .addEventListener("click", deleteCurrentTask);
  document
    .getElementById("task-edit-button")
    .addEventListener("click", function () {
      if (boardState.currentTaskId === null) {
        return;
      }
      /* Свежая копия задачи для формы редактирования (GET /api/tasks/{id}). */
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
    .getElementById("task-move-select")
    .addEventListener("change", moveCurrentTask);
}
