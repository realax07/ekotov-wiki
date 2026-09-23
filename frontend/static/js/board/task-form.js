/* Форма создания/редактирования задачи (P6: извлечено из board.js;
 * tasks.md 4.5; FR-5, FR-7, FR-9).
 *
 * 4.5: форма создания (7 полей FR-9 + is_fast, title обязателен —
 * UI-валидация до отправки), редактирование (PATCH). После мутации —
 * рефреш доски (sdd). 409 «fast line occupied» → «fast line занята»
 * (5.2): форма остается открытой, задача не создается.
 *
 * 3.1 (FR-19, FR-21, FR-29, FR-30): поле категории — select из
 * GET /api/categories (не свободный текст; DEF-001). Опции
 * перезагружаются при каждом открытии формы (селект следует за
 * справочником, search-дельта «Изменение данных отражается в
 * селект-полях»). При 422 жесткой валидации категории (FR-21) поле
 * подсвечивается как невалидное с сообщением (подсветка снимается при
 * изменении значения и при следующем открытии формы).
 *
 * 4.1 (FR-26, Д-3): поле «Теги» — автодополнение через datalist
 * task-tag-hints, заполняемый из существующего GET /api/suggestions
 * (set() из тегов+категорий существующих задач; механизм един с
 * подсказками поиска — изменений эндпоинта нет, sdd r2 §3.2). Выбор
 * существующего значения ИЛИ ввод нового: datalist не ограничивает
 * ввод, новое значение сохраняется как тег обычным образом
 * (_set_tags, get-or-create). Подсказки перезагружаются при каждом
 * открытии формы (следуют за заведенными значениями). Сбой загрузки
 * оставляет datalist пустым — автодополнение не работает, ввод тегов
 * не блокируется.
 *
 * 4.3 (FR-27, BUG-004; fastline MODIFIED «Поле приоритета
 * заблокировано», CHK-129/TC-fast2-003): отметка fast line подставляет
 * в поле приоритета «высокий» (high) и блокирует его; снять блокировку
 * можно только сняв fast line. При отправке fast-задачи priority не
 * включается в payload вовсе — сервер сам ставит high (BUG-002: явный
 * priority=null при is_fast отклоняется 422; ОГР-10).
 */
"use strict";

import { api } from "./api.js";
import { el, showFormError, hideError } from "./dom.js";
import { boardState } from "./state.js";
import { refreshBoard } from "./cards.js";

/* --- Форма создания/редактирования (FR-5, FR-7, FR-9) --- */

var CATEGORY_FIELD_ID = "task-category";
var CATEGORY_FIELD_ERROR_ID = "task-category-error";
var PRIORITY_FIELD_ID = "task-priority";
var IS_FAST_FIELD_ID = "task-is-fast";

/* --- Блокировка приоритета fast-задачи (4.3, FR-27, BUG-004) --- */

function setPriorityLock(locked) {
  /* fast line отмечена → приоритет «высокий» и поле заблокировано
   * (сценарий «Поле приоритета заблокировано»; разблокировка — только
   * снятием fast line). Программная установка checked у чекбокса
   * событие change не возбуждает, поэтому при открытии/очистке формы
   * сброс блокировки — явный setPriorityLock(false) в fillTaskForm. */
  var select = document.getElementById(PRIORITY_FIELD_ID);
  if (locked) {
    select.value = "high";
  }
  select.disabled = locked;
}

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

function categoryField() {
  return document.getElementById(CATEGORY_FIELD_ID);
}

/* --- Автодополнение тегов: datalist из GET /api/suggestions (4.1, FR-26/Д-3) --- */

function fillTagHints(values) {
  /* Опции datalist — только через textContent (XSS, dom.js); полная
   * перезагрузка при каждом открытии формы (следует за заведенными
   * значениями, как и select категории за справочником). */
  var datalist = document.getElementById("task-tag-hints");
  datalist.textContent = "";
  values.forEach(function (value) {
    var option = el("option", null, value);
    option.value = value;
    datalist.appendChild(option);
  });
}

function loadTagHints() {
  /* Источник — существующий GET /api/suggestions (Д-3: механизм един
   * с подсказками поиска; sdd r2 §3.2 — эндпоинт без изменений).
   * Ответ 200: {"suggestions": [...]} — set() тегов+категорий
   * существующих задач, без дублей, отсортировано. Сбой (в т.ч. 401
   * при истекшей сессии) — datalist пустой: подсказки не показываются,
   * свободный ввод тегов сохраняется (новое значение — тег, FR-26). */
  api(
    "/api/suggestions",
    {},
    function () {
      fillTagHints([]);
    },
    function (body) {
      fillTagHints((body && body.suggestions) || []);
    }
  );
}

/* --- Категория: select из GET /api/categories (3.1, FR-19/FR-30) --- */

function fillCategorySelect(names, selected) {
  /* Полная перезагрузка опций: «ровно содержимое справочника», никаких
   * статических option в разметке (DEF-001). Пустое значение «—» —
   * признак «категория не задана» (nullable-модель, Д-2), а не элемент
   * справочника: в список имен оно не попадает. Значения — только через
   * textContent (XSS, dom.js). */
  var select = categoryField();
  select.textContent = "";
  select.appendChild(el("option", null, "—"));
  select.firstElementChild.value = "";
  names.forEach(function (name) {
    var option = el("option", null, name);
    option.value = name;
    select.appendChild(option);
  });
  select.value = selected || "";
}

function loadCategoryOptions(selected) {
  /* Опции select — фактическое содержимое справочника на момент
   * открытия формы (sdd r2 §3.1: 200 {"categories": [{id, name}, ...],
   * отсортировано по name}). Сбой загрузки список не подменяет:
   * select остается с одним пустым значением, выбор категории
   * невозможен — свободный текст не появляется (FR-19: выбор из
   * справочника, не ввод). */
  api(
    "/api/categories",
    {},
    function () {
      fillCategorySelect([], null);
    },
    function (body) {
      var names = ((body && body.categories) || []).map(function (item) {
        return item.name;
      });
      fillCategorySelect(names, selected);
    }
  );
}

/* --- Подсветка невалидной категории (3.1, FR-21/FR-29) --- */

function markCategoryInvalid(message) {
  var field = categoryField();
  field.classList.add("field-invalid");
  field.setAttribute("aria-invalid", "true");
  showFormError(CATEGORY_FIELD_ERROR_ID, message);
}

function clearCategoryInvalid() {
  var field = categoryField();
  field.classList.remove("field-invalid");
  field.removeAttribute("aria-invalid");
  hideError(CATEGORY_FIELD_ERROR_ID);
}

function isCategoryValidation(body) {
  /* 422 по категории (FR-21): тело дословно sdd r2 §3.2 —
   * {"error": "validation", "details": {"category": "not in categories"}};
   * pydantic-формат details (массив {loc, msg}) — fallback. */
  if (!body || body.error !== "validation") {
    return false;
  }
  var details = body.details;
  if (details && !Array.isArray(details) && typeof details === "object") {
    return Object.prototype.hasOwnProperty.call(details, "category");
  }
  if (Array.isArray(details)) {
    return details.some(function (item) {
      return item && item.loc && item.loc.indexOf("category") !== -1;
    });
  }
  return false;
}

function handleSubmitError(message, response, body) {
  /* 422 по категории → подсветка поля (состояние ошибки, FR-29);
   * прочие ошибки — общее сообщение формы, без подсветки. */
  if (response && response.status === 422 && isCategoryValidation(body)) {
    markCategoryInvalid(message);
  } else {
    showFormError("task-form-error", message);
  }
}

function fillTaskForm(task) {
  document.getElementById("task-title").value = task.title || "";
  document.getElementById("task-description").value = task.description || "";
  document.getElementById(PRIORITY_FIELD_ID).value = task.priority || "";
  /* Значение задачи проставляется после загрузки опций (loadCategoryOptions):
   * пока опций нет, value селекта молча не применится. */
  document.getElementById("task-due-date").value = task.due_date || "";
  document.getElementById("task-tags").value = (task.tags || []).join(", ");
  document.getElementById(IS_FAST_FIELD_ID).checked = false;
  /* Форма открывается без fast line → приоритет разблокирован (4.3:
   * сброс состояния предыдущего открытия формы). */
  setPriorityLock(false);
}

function clearTaskForm() {
  fillTaskForm({ tags: [] });
  loadCategoryOptions(null);
  loadTagHints();
}

export function openCreateForm() {
  boardState.currentTaskId = null;
  document.getElementById("task-form-heading").textContent =
    "Создание задачи";
  document.getElementById("task-form-submit").textContent = "Создать";
  document.getElementById("task-is-fast").closest("label").hidden = false;
  clearTaskForm();
  hideError("task-form-error");
  clearCategoryInvalid();
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
  /* Категория задачи, удаленной из справочника, в списке не значится:
   * опции = ровно справочник (FR-30), значение сбрасывается на «—».
   * Сохранение такой задачи в прежнем виде отклонится 422 (FR-21) —
   * с подсветкой поля. */
  loadCategoryOptions(task.category);
  /* Подсказки тегов — и в режиме редактирования: те же заведенные
   * значения (FR-26 действует на форму в обоих режимах). */
  loadTagHints();
  hideError("task-form-error");
  clearCategoryInvalid();
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
    priority: document.getElementById(PRIORITY_FIELD_ID).value || null,
    category: categoryField().value || null,
    due_date: document.getElementById("task-due-date").value || null,
    tags: splitTags(document.getElementById("task-tags").value),
  };
  if (boardState.currentTaskId === null) {
    var isFast = document.getElementById(IS_FAST_FIELD_ID).checked;
    payload.is_fast = isFast;
    if (isFast) {
      /* BUG-004 (4.3, BUG-002): явный priority (даже null) при is_fast
       * отклоняется сервером 422 (ОГР-10) — при fast priority не
       * отправляется вовсе, сервер сам ставит «высокий». */
      delete payload.priority;
    }
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
    handleSubmitError,
    function () {
      closeTaskForm();
      refreshBoard();
    }
  );
}

/* Сброс подсветки при изменении значения (пользователь отреагировал). */
categoryField().addEventListener("change", clearCategoryInvalid);

/* 4.3 (FR-27): отметка fast line → приоритет «высокий» и блокировка
 * поля; снятие fast line — единственный способ разблокировать. */
document
  .getElementById(IS_FAST_FIELD_ID)
  .addEventListener("change", function (event) {
    setPriorityLock(event.target.checked);
  });
