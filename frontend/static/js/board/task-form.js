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
 *
 * 4.1 (FR-34, DEF-005): визуальные зоны формы по мокапу V3 — только
 * отображение, без изменений логики/валидации:
 * - вид выбранных тегов: чипы .chip (крестик удаления) синхронно с
 *   input «Теги» (renderTagsChips; источник истины — input);
 * - выбранный приоритет: SVG-иконка в пилюле (renderPriorityPillIcon,
 *   priority-icons.js; цвет дает пилюля по :has(:checked));
 * - скрытие fast line в режиме редактирования — весь ряд .fast-row.
 *
 * 4.1 Релиза 4 (FR-47, Д-9; design §6 «текущее окно деталей …
 * разделяется на view-модалку и вызов task-form»): действия с задачей
 * из прежнего окна деталей переезжают сюда без изменения механики —
 * селект «Столбец» (POST /{id}/move, FR-6/ОГР-14), «Удалить»
 * (DELETE, FR-7), форма комментария (GET/POST /api/tasks/{id}/comments,
 * sdd §3.2). В режиме создания блок действий скрыт (задачи еще нет —
 * данные выдумывать нечем); в режиме редактирования он видим и работает
 * как прежде (веб-морда — клиент REST API, ОГР-2).
 */
"use strict";

import { api } from "./api.js";
import { el, showFormError, hideError } from "./dom.js";
import { boardState } from "./state.js";
import { refreshBoard } from "./cards.js";
import { createPriorityIcon, PRIORITY_LABELS } from "./priority-icons.js";

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
  renderPriorityPillIcon();
}

/* --- 4.1 (FR-34/DEF-005, зона «отображение выбранного приоритета»):
 * SVG-иконка выбранного приоритета внутри пилюли (мокап V3 — иконка +
 * текст; FR-29: различимость без цвета). Пилюля несет цвет по
 * :has(:checked) (board.css), иконка рисуется currentColor. Визуальный
 * отклик на выбор — только иконка; value/коллект payload не тронуты. */

var PRIORITY_PILL_ICON_ID = "task-priority-pill-icon";

function renderPriorityPillIcon() {
  var iconBox = document.getElementById(PRIORITY_PILL_ICON_ID);
  if (!iconBox) {
    return;
  }
  var priority = document.getElementById(PRIORITY_FIELD_ID).value;
  iconBox.textContent = "";
  if (priority && PRIORITY_LABELS[priority]) {
    iconBox.appendChild(createPriorityIcon(priority, 14, 2));
  }
  /* Пустой выбор — иконки нет (мокап: «—»); :empty прячет бокс (css). */
}

/* --- 4.1 (FR-34/DEF-005, зона «вид выбранных тегов»): чипы выбранных
 * тегов по мокапу V3 (.chip с крестиком удаления). Состояние
 * синхронизируется с input «Теги»: ввод/удаление в поле перерисовывает
 * чипы, крестик чипа правит строку того же input. Источник истины —
 * input (collectTaskForm не менялся); отправка — по-прежнему строка
 * input. Значения — только через textContent (XSS, dom.js). */

var TAGS_INPUT_ID = "task-tags";
var TAGS_CHIPS_ID = "task-tags-chips";

function renderTagsChips() {
  var input = document.getElementById(TAGS_INPUT_ID);
  var chips = document.getElementById(TAGS_CHIPS_ID);
  chips.textContent = "";
  var tags = splitTags(input.value);
  chips.hidden = tags.length === 0;
  tags.forEach(function (tag) {
    var chip = el("span", "chip");
    chip.appendChild(el("span", null, tag));
    var remove = el("button", null, "×");
    remove.type = "button";
    remove.setAttribute("aria-label", "Убрать тег " + tag);
    remove.addEventListener("click", function () {
      var rest = splitTags(input.value).filter(function (item) {
        return item !== tag;
      });
      input.value = rest.join(", ");
      renderTagsChips();
    });
    chip.appendChild(remove);
    chips.appendChild(chip);
  });
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

/* --- Исполнитель: select из GET /api/users (5.1, ОВ-26, Д-10) --- */

var ASSIGNED_FIELD_ID = "task-assigned";

function assignedField() {
  return document.getElementById(ASSIGNED_FIELD_ID);
}

function fillAssignedSelect(users, selectedId) {
  /* Полная перезагрузка опций при каждом открытии формы (следует за
   * составом пользователей; состав — данные, не код — хардкод
   * отклонен ревью B-1). Первая опция «Не назначено» (value="") —
   * признак «без исполнителя» (nullable, FR-37/ОВ-26), не элемент
   * списка пользователей. Подпись опции = display_name или логин
   * (Д-10, сервер display_name НЕ подставляет — fallback на клиенте).
   * Значения — только через textContent (XSS, dom.js). */
  var select = assignedField();
  select.textContent = "";
  var none = el("option", null, "Не назначено");
  none.value = "";
  select.appendChild(none);
  (users || []).forEach(function (user) {
    var label = user.display_name || user.login;
    var option = el("option", null, label);
    option.value = String(user.id);
    select.appendChild(option);
  });
  select.value = selectedId === null || selectedId === undefined
    ? ""
    : String(selectedId);
}

function loadAssignedOptions(selectedId) {
  /* Источник — read-only GET /api/users (sdd §3.1a-кватер-бис, ОВ-26):
   * 200 {"users": [{id, login, display_name}]}, отсортированы по login.
   * Сбой загрузки список не подменяет: select остается с одним «Не
   * назначено» — назначить исполнителя нельзя, но и произвольного
   * значения не появляется (значения только из пользователей). */
  api(
    "/api/users",
    {},
    function () {
      fillAssignedSelect([], null);
    },
    function (body) {
      fillAssignedSelect((body && body.users) || [], selectedId);
    }
  );
}

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
   * пока опций нет, value селекта молча не применятся. */
  document.getElementById("task-due-date").value = task.due_date || "";
  document.getElementById("task-tags").value = (task.tags || []).join(", ");
  document.getElementById(IS_FAST_FIELD_ID).checked = false;
  /* 5.1: исполнителя в select ставит loadAssignedOptions (по task.assigned_to_id
   * — сервер возвращает его в ответе задачи; до 5.1 ответ поля не имел —
   * select открывается на «Не назначено»). */
  document.getElementById("task-assigned").value = "";
  /* Форма открывается без fast line → приоритет разблокирован (4.3:
   * сброс состояния предыдущего открытия формы). */
  setPriorityLock(false);
  /* 4.1 (DEF-005): визуальные зоны — иконка приоритета и чипы тегов —
   * перерисовываются под заполненные значения (в т.ч. при очистке). */
  renderPriorityPillIcon();
  renderTagsChips();
}

function clearTaskForm() {
  fillTaskForm({ tags: [] });
  loadCategoryOptions(null);
  loadAssignedOptions(null);
  loadTagHints();
}

/* --- 4.1 Релиза 4: действия с задачей из окна деталей (FR-6/FR-7) ---
 * Механика перенесена из task-detail.js без изменений (та же
 * API-логика); изменилось только место в UI (окно формы). */

function renderCommentsInto(list, comments) {
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

/* Экспорт для view-модалки (task-detail.js): рендер того же формата
 * комментариев в стороннем списке. */
export function renderComments(list, comments) {
  renderCommentsInto(list, comments);
}

function isValidTaskId(value) {
  return typeof value === "number" && isFinite(value);
}

/* Загрузка комментариев в указанный список; onError — колбэк вызывающей
 * модалки (у view и формы свои боксы ошибок). */
export function loadComments(taskId, list, onError) {
  api(
    "/api/tasks/" + taskId + "/comments",
    {},
    onError,
    function (body) {
      renderCommentsInto(list, body && body.comments);
    }
  );
}

function deleteCurrentTask() {
  if (boardState.currentTaskId === null) {
    return;
  }
  var taskId = boardState.currentTaskId;
  /* Подтверждение удаления (FR-7). */
  if (!window.confirm("Удалить задачу? Действие необратимо.")) {
    return;
  }
  hideError("task-form-error");
  api(
    "/api/tasks/" + taskId,
    { method: "DELETE" },
    function (message) {
      showFormError("task-form-error", message);
    },
    function () {
      closeTaskForm();
      refreshBoard();
    }
  );
}

function moveCurrentTask() {
  if (!isValidTaskId(boardState.currentTaskId)) {
    return;
  }
  var status = document.getElementById("task-move-select").value;
  hideError("task-form-error");
  api(
    "/api/tasks/" + boardState.currentTaskId + "/move",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: status }),
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

export function submitComment(event) {
  event.preventDefault();
  hideError("task-comment-error");

  /* Guard (integer-баг): комментарий можно отправить только из
   * режима редактирования открытой задачи. Без задачи в currentTaskId
   * путь был бы /api/tasks/null/comments → 422 int_parsing от сервера. */
  if (!isValidTaskId(boardState.currentTaskId)) {
    showFormError(
      "task-comment-error",
      "Карточка задачи не открыта — откройте задачу и попробуйте еще раз."
    );
    return;
  }

  var body = document.getElementById("comment-body").value.trim();
  /* UI-валидация до отправки: текст обязателен (sdd §3.2, 422). */
  if (!body) {
    showFormError("task-comment-error", "Комментарий не может быть пустым.");
    return;
  }
  var taskId = boardState.currentTaskId;
  api(
    "/api/tasks/" + taskId + "/comments",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: body }),
    },
    function (message) {
      showFormError("task-comment-error", message);
    },
    function () {
      document.getElementById("comment-body").value = "";
      loadComments(
        taskId,
        document.getElementById("task-form-comments-list"),
        function (message) {
          showFormError("task-comment-error", message);
        }
      );
    }
  );
}

/* --- Открытие формы (режимы создания/редактирования) --- */

export function openCreateForm() {
  boardState.currentTaskId = null;
  document.getElementById("task-form-heading").textContent =
    "Создание задачи";
  document.getElementById("task-form-submit").textContent = "Создать";
  /* is_fast назначается только при создании (sdd §3.2, ОГР-5). */
  document.getElementById("task-is-fast").closest(".fast-row").hidden = false;
  /* 4.1 Релиза 4: в режиме создания задачи еще нет — блока действий
   * (Столбец/Удалить/комментарии) не существует, данные не выдумываются. */
  document.getElementById("task-actions").hidden = true;
  document.getElementById("task-comments").hidden = true;
  clearTaskForm();
  renderCommentsInto(document.getElementById("task-form-comments-list"), []);
  hideError("task-form-error");
  hideError("task-comment-error");
  clearCategoryInvalid();
  document.getElementById("task-form-overlay").hidden = false;
  document.getElementById("task-title").focus();
}

export function openEditForm(task) {
  boardState.currentTaskId = task.id;
  document.getElementById("task-form-heading").textContent =
    "Редактирование задачи";
  document.getElementById("task-form-submit").textContent = "Сохранить";
  /* is_fast назначается только при создании (sdd §3.2, ОГР-5):
   * скрывается весь ряд fast line (.fast-row). */
  document.getElementById("task-is-fast").closest(".fast-row").hidden = true;
  /* 4.1 Релиза 4: блок действий задачи — только в режиме редактирования. */
  document.getElementById("task-actions").hidden = false;
  document.getElementById("task-comments").hidden = false;
  /* Селект «Столбец» — актуальный статус задачи (как в прежнем окне
   * деталей). */
  document.getElementById("task-move-select").value = task.status;
  fillTaskForm(task);
  /* Категория задачи, удаленной из справочника, в списке не значится:
   * опции = ровно справочник (FR-30), значение сбрасывается на «—».
   * Сохранение такой задачи в прежнем виде отклонится 422 (FR-21) —
   * с подсветкой поля. */
  loadCategoryOptions(task.category);
  /* 5.1: select исполнителя — текущее значение задачи (ОВ-26).
   * assigned_to_id возвращается в ответе задачи (5.1, sdd §3.2);
   * смена/очистка — тем же селектом, отправка через PATCH. */
  loadAssignedOptions(task.assigned_to_id !== undefined ? task.assigned_to_id : null);
  /* Подсказки тегов — и в режиме редактирования: те же заведенные
   * значения (FR-26 действует на форму в обоих режимах). */
  loadTagHints();
  /* Комментарии загружаются заново (прежнее окно деталей показывало их
   * здесь же; источник данных — GET /api/tasks/{id}/comments). */
  renderCommentsInto(document.getElementById("task-form-comments-list"), []);
  loadComments(
    task.id,
    document.getElementById("task-form-comments-list"),
    function (message) {
      showFormError("task-comment-error", message);
    }
  );
  hideError("task-form-error");
  hideError("task-comment-error");
  clearCategoryInvalid();
  /* Закрыть view-модалку, если открыта (тело closeTaskDetail дословно;
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
    /* 5.1 (ОВ-26): пустой select = «без исполнителя» → null (легально);
     * выбранное значение — id пользователя. assigned_to_id допустим и в
     * POST (опционально), и в PATCH; creator_id не отправляется — его
     * ставит сервер (FR-37). */
    assigned_to_id:
      document.getElementById(ASSIGNED_FIELD_ID).value === ""
        ? null
        : Number(document.getElementById(ASSIGNED_FIELD_ID).value),
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

/* Подписка действий с задачей (4.1 Релиза 4; вызывается board-init.js):
 * обработчики рядом с их логикой — селект «Столбец» (FR-6/ОГР-14) и
 * «Удалить» (FR-7). Комментарий подписывает board-init (submitComment
 * экспортирован для этого). */
export function initTaskActions() {
  document
    .getElementById("task-move-select")
    .addEventListener("change", moveCurrentTask);
  document
    .getElementById("task-delete-button")
    .addEventListener("click", deleteCurrentTask);
}

/* Сброс подсветки при изменении значения (пользователь отреагировал). */
categoryField().addEventListener("change", clearCategoryInvalid);

/* 4.1 (FR-34/DEF-005): живой отклик визуальных зон на ввод —
 * иконка приоритета (change) и чипы тегов (input). Логика значений
 * (collectTaskForm) не задействована. */
document
  .getElementById(PRIORITY_FIELD_ID)
  .addEventListener("change", renderPriorityPillIcon);
document
  .getElementById(TAGS_INPUT_ID)
  .addEventListener("input", renderTagsChips);

/* 4.3 (FR-27): отметка fast line → приоритет «высокий» и блокировка
 * поля; снятие fast line — единственный способ разблокировать. */
document
  .getElementById(IS_FAST_FIELD_ID)
  .addEventListener("change", function (event) {
    setPriorityLock(event.target.checked);
  });
