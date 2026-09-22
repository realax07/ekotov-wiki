/* Форма создания/редактирования задачи (P6: извлечено из board.js;
 * tasks.md 4.5; FR-5, FR-7, FR-9).
 *
 * 4.5: форма создания (7 полей FR-9 + is_fast, title обязателен —
 * UI-валидация до отправки), редактирование (PATCH). После мутации —
 * рефреш доски (sdd). 409 «fast line occupied» → «fast line занята»
 * (5.2): форма остается открытой, задача не создается.
 */
"use strict";

import { api } from "./api.js";
import { showFormError, hideError } from "./dom.js";
import { boardState } from "./state.js";
import { refreshBoard } from "./cards.js";

/* --- Форма создания/редактирования (FR-5, FR-7, FR-9) --- */

function splitTags(raw) {
  /* Строка через запятую → массив непустых тегов. */
  return raw
    .split(",")
    .map(function (tag) {
      return tag.trim();
    })
    .filter(function (tag) {
      return tag.length > 0;
    });
}

function fillTaskForm(task) {
  document.getElementById("task-title").value = task.title || "";
  document.getElementById("task-description").value = task.description || "";
  document.getElementById("task-priority").value = task.priority || "";
  document.getElementById("task-category").value = task.category || "";
  document.getElementById("task-due-date").value = task.due_date || "";
  document.getElementById("task-tags").value = (task.tags || []).join(", ");
  document.getElementById("task-is-fast").checked = false;
}

function clearTaskForm() {
  fillTaskForm({ tags: [] });
}

export function openCreateForm() {
  boardState.currentTaskId = null;
  document.getElementById("task-form-heading").textContent =
    "Создание задачи";
  document.getElementById("task-form-submit").textContent = "Создать";
  document.getElementById("task-is-fast").closest("label").hidden = false;
  clearTaskForm();
  hideError("task-form-error");
  document.getElementById("task-form-overlay").hidden = false;
  document.getElementById("task-title").focus();
}

export function openEditForm(task) {
  boardState.currentTaskId = task.id;
  document.getElementById("task-form-heading").textContent =
    "Редактирование задачи";
  document.getElementById("task-form-submit").textContent = "Сохранить";
  /* is_fast назначается только при создании (sdd §3.2, ОГР-5). */
  document.getElementById("task-is-fast").closest("label").hidden = true;
  fillTaskForm(task);
  hideError("task-form-error");
  /* Закрыть карточку, если открыта (тело closeTaskDetail дословно;
   * прямой импорт из task-detail.js создал бы цикл form ↔ detail). */
  document.getElementById("task-detail-overlay").hidden = true;
  document.getElementById("task-form-overlay").hidden = false;
  document.getElementById("task-title").focus();
}

export function closeTaskForm() {
  document.getElementById("task-form-overlay").hidden = true;
  boardState.currentTaskId = null;
}

function collectTaskForm() {
  /* 7 признаков FR-9; UI-валидация title — ДО отправки (FR-5). */
  var payload = {
    title: document.getElementById("task-title").value.trim(),
    description: document.getElementById("task-description").value.trim(),
    priority: document.getElementById("task-priority").value || null,
    category: document.getElementById("task-category").value.trim(),
    due_date: document.getElementById("task-due-date").value || null,
    tags: splitTags(document.getElementById("task-tags").value),
  };
  if (boardState.currentTaskId === null) {
    payload.is_fast = document.getElementById("task-is-fast").checked;
  }
  return payload;
}

export function submitTaskForm(event) {
  event.preventDefault();
  hideError("task-form-error");

  var payload = collectTaskForm();
  /* UI-валидация до отправки: название обязательно (FR-5). */
  if (!payload.title) {
    showFormError("task-form-error", "Укажите название задачи.");
    return;
  }

  var isCreate = boardState.currentTaskId === null;
  var path = isCreate
    ? "/api/tasks"
    : "/api/tasks/" + boardState.currentTaskId;
  var method = isCreate ? "POST" : "PATCH";
  api(
    path,
    {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    function (message) {
      showFormError("task-form-error", message);
    },
    function () {
      closeTaskForm();
      refreshBoard();
    }
  );
}
