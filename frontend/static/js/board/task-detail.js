/* View-модалка карточки задачи: read-only просмотр (4.1; FR-47, Д-9,
 * ОГР-18; дельта board «Просмотр карточки задачи — модальное окно
 * read-only», все 5 сценариев — первичный источник поведения).
 *
 * r8 2.3 (FR-91): список комментариев модалки рендерится СВОЕЙ шапкой —
 * «Автор (bold) · дата, время» (Intl ru-RU «дд.мм.гггг, чч:мм» из
 * created_at) по утвержденному мокапу polish-ticket-modal.html; id и
 * сырой timestamp больше не показываются. Форма (task-form.js, зона
 * волны 2.1) продолжает показывать прежний формат до своей правки.
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
import { openEditForm } from "./task-form.js";

/* --- Read-only рендер (FR-47; сценарии 1, 4) --- */

/* r8 2.3 (FR-91, design §5): человекочитаемые дата и время комментария —
 * «дд.мм.гггг, чч:мм» (Intl ru-RU; формат утвержденного мокапа
 * design/polish-ticket-modal.html: 05.10.2026, 14:32). Из ISO created_at
 * (контракт GET списка комментариев). Без Intl (старые движки) —
 * детерминированный ручной формат того же вида. Значение — только через
 * textContent (XSS, ОГР-11). null/пустое — ряд не рисуется. */
function formatCommentDateTime(iso) {
  if (!iso) {
    return null;
  }
  var date = new Date(iso);
  if (isNaN(date.getTime())) {
    return null;
  }
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  } catch (e) {
    var pad = function (n) {
      return (n < 10 ? "0" : "") + n;
    };
    return (
      pad(date.getDate()) +
      "." +
      pad(date.getMonth() + 1) +
      "." +
      date.getFullYear() +
      ", " +
      pad(date.getHours()) +
      ":" +
      pad(date.getMinutes())
    );
  }
}

/* Шапка комментария (r8 2.3, FR-91): «Автор (bold) · дата, время» —
 * вместо прежних «id N · timestamp». Структура по мокапу
 * polish-ticket-modal.html: .comment-head > .comment-author +
 * .comment-sep «·» + time.comment-date (datetime — исходный ISO).
 * Значения — createTextNode/textContent (XSS, ОГР-11). Без автора
 * (старый кэш ответа без author_name) — шапка не рисуется частично:
 * рендерится только дата (данные не выдумываются). */
function buildCommentHead(comment) {
  var head = el("div", "comment-head");
  var authorName =
    comment.author_name !== undefined &&
    comment.author_name !== null &&
    comment.author_name !== ""
      ? String(comment.author_name)
      : null;
  var dateText = formatCommentDateTime(comment.created_at);
  if (authorName) {
    head.appendChild(el("span", "comment-author", authorName));
  }
  if (authorName && dateText) {
    head.appendChild(el("span", "comment-sep", "·"));
  }
  if (dateText) {
    var time = el("time", "comment-date", dateText);
    time.setAttribute("datetime", String(comment.created_at));
    head.appendChild(time);
  }
  return head.childNodes.length > 0 ? head : null;
}

/* Список комментариев view-модалки (r8 2.3): то же множество данных, что
 * грузит loadComments (task-form.js), но шапка — своя, по мокапу
 * (автор · дата/время вместо id · timestamp, FR-91). Вызывается вместо
 * renderComments task-form.js, чей формат метки остался прежним
 * (task-form.js — зона параллельной волны 2.1, не менялся). */
function renderDetailComments(list, comments) {
  list.textContent = "";
  (comments || []).forEach(function (comment) {
    var item = el("li", "task-comment");
    var head = buildCommentHead(comment);
    if (head) {
      item.appendChild(head);
    }
    var body = el("p", "task-comment-body");
    body.textContent = comment.body; // textContent — не innerHTML (XSS)
    item.appendChild(body);
    list.appendChild(item);
  });
}

/* Загрузка комментариев view-модалки с собственным рендером (r8 2.3):
 * тот же GET /api/tasks/{id}/comments, onError — как у loadComments. */
function loadDetailComments(taskId, list, onError) {
  api(
    "/api/tasks/" + taskId + "/comments",
    {},
    onError,
    function (body) {
      renderDetailComments(list, body && body.comments);
    }
  );
}

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
  renderDetailComments(document.getElementById("task-comments-list"), []);
  /* GET /api/tasks/{id} — полный Task (sdd §3.2), затем комментарии
   * (r8 2.3: собственный рендер шапки «автор · дата, время», FR-91). */
  api(
    "/api/tasks/" + taskId,
    {},
    function (message) {
      showFormError("task-detail-error", message);
    },
    function (task) {
      renderTaskDetail(task);
      loadDetailComments(
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
