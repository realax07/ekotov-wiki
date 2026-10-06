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
 * r8 2.3 (FR-91, базой взята дельта feature/p12-23-comments-combobox,
 * cherry-pick — заодно, конфликта зон нет): шапка комментария
 * «Автор (bold) · дата, время» (Intl ru-RU «дд.мм.гггг, чч:мм»);
 * author_name приходит из API (join users, 2.3-бэкенд); без поля —
 * fallback-рендер только из имеющихся данных (данные не выдумываются).
 *
 * r8 2.2 (FR-90): вид окна — СТРОГО по утвержденному мокапу
 * design/polish-ticket-modal.html (заказчик 2026-10-06): шапка — кикер
 * «Задача · STAND-<id>», название-сериф, ряд бейджей приоритет/статус/
 * fast line (цвет + иконка + текст); тело — описание, признаки
 * (категория/срок/fast line/оценка — сетка 2 колонок), теги-чипы, люди
 * (assigned/creator с аватарами-инициалами), комментарии; футер —
 * кнопка «Редактировать». Read-only семантика не тронута: ни одного
 * поля ввода, значения — только textContent (XSS, ОГР-11). DOM-id не
 * переименованы (ОГР-28): #task-detail-attrs сохраняет свои ряды
 * данных задачи (контракт утвержденного e2e TC-UI-009: attrs содержат
 * ровно значения задачи); мокапные блоки (бейджи/чипы/люди/сетка
 * признаков) строятся в СОСЕДНИХ секциях разметки, контракт attrs не
 * расширяют.
 *
 * Состав просмотра (сценарии 1 и 4): название, описание, статус,
 * приоритет, категория, срок, теги, fast-признак, assigned/creator,
 * комментарии. assigned/creator рендерятся только при наличии
 * соотв. полей в ответе GET /api/tasks/{id} (доставка — данные 5.1;
 * сейчас их в ответе нет — секция «Люди» не выводится, данные не
 * выдумываются). Пустой assigned — курсивом «Unassigned» (ОВ-24).
 * done_at — ряд «Выполнено» при наличии (sdd §3.2, r5); created_at в
 * схеме Task (sdd §3.2) отсутствует — в view не показывается.
 *
 * Визуальная отличимость от форм (ОГР-18): отсутствие полей ввода +
 * оформление .task-view (board.css, токены V3).
 *
 * Доступность: окно role=dialog (разметка board.html), r8 2.2 —
 * focus trap по Tab (мокап: «Tab — обход внутри окна») и возврат
 * фокуса на карточку-триггер при закрытии (правило мокапа). Сущест-
 * вующие пути закрытия не тронуты: крестик/«Закрыть»/Escape/клик по
 * подложке (board-init.js) — поверх них только фокус-гигиена.
 *
 * XSS (ОГР-11): рендер значений — textContent, не innerHTML.
 */
"use strict";

import { el, showFormError, hideError } from "./dom.js";
import { api } from "./api.js";
import { boardState } from "./state.js";
import { createPriorityIcon, PRIORITY_LABELS } from "./priority-icons.js";
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

/* --- r8 2.2 (FR-90): блоки мокапа polish-ticket-modal.html --- */

var SVG_NS = "http://www.w3.org/2000/svg";

/* Иконка статуса в бейдже (мокап: круг с галочкой, 12px, currentColor —
 * цвет дает бейдж-обертка). */
function createStatusIcon() {
  var svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 12 12");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("aria-hidden", "true");
  var circle = document.createElementNS(SVG_NS, "circle");
  circle.setAttribute("cx", "6");
  circle.setAttribute("cy", "6");
  circle.setAttribute("r", "4.5");
  var check = document.createElementNS(SVG_NS, "path");
  check.setAttribute("d", "M3.8 6.2l1.6 1.6 2.8-3.4");
  svg.appendChild(circle);
  svg.appendChild(check);
  return svg;
}

/* Иконка fast line в бейдже (мокап: стрелка-«ускорение», 12px,
 * currentColor). */
function createFastIcon() {
  var svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 12 12");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("aria-hidden", "true");
  var path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", "M2 6h6M5.5 2.5L9 6l-3.5 3.5");
  svg.appendChild(path);
  return svg;
}

/* Бейдж шапки (мокап .badge): цвет-класс + иконка + текст — различимость
 * без цвета (паттерн FR-29). Классы окраски — board.css: .badge-priority-*,
 * .badge-status, .badge-fast. */
function buildBadge(className, icon, text) {
  var badge = el("span", "badge " + className);
  badge.appendChild(icon);
  badge.appendChild(el("span", null, text));
  return badge;
}

/* Аватар-инициалы (мокап .person-avatar): до двух первых символов имени
 * в верхнем регистре; aria-hidden — имя рядом текстом. */
function buildAvatar(name) {
  var source = String(name || "").trim();
  var initials = source ? source.slice(0, 2).toUpperCase() : "—";
  var avatar = el("span", "person-avatar", initials);
  avatar.setAttribute("aria-hidden", "true");
  return avatar;
}

/* Персона (мокап .person): аватар + имя + роль («Исполнитель»/«Автор»).
 * secondary — второй участник (серо-чернильный аватар в мокапе). Пустое
 * имя — «Unassigned» (ОВ-24; своей формой — не addUserRow). */
function buildPerson(name, role, secondary) {
  var person = el("div", "person" + (secondary ? " secondary" : ""));
  person.appendChild(buildAvatar(name));
  var meta = el("span", "person-meta");
  meta.appendChild(
    el("span", "person-name", name ? String(name) : "Unassigned")
  );
  meta.appendChild(el("span", "person-role", role));
  person.appendChild(meta);
  return person;
}

/* Шапка окна (мокап .modal-head): кикер «Задача · STAND-<id>», заголовок
 * (id сохранен, ОГР-28), бейдж-ряд. Бейджи — только фактические значения
 * задачи: приоритет без значения — бейджа нет (данные не выдумываются). */
function buildViewHead(task) {
  var head = el("div", "task-view-head");

  head.appendChild(
    el("p", "task-view-kicker", "Задача · STAND-" + task.id)
  );

  var title = document.getElementById("task-detail-title");
  title.className = "task-view-title";
  title.textContent = task.title;
  head.appendChild(title);

  var badges = el("div", "badge-row");
  var priority = task.priority;
  if (priority && PRIORITY_LABELS[priority]) {
    badges.appendChild(
      buildBadge(
        "badge-priority-" + priority,
        createPriorityIcon(priority, 12, 2),
        "Приоритет: " + PRIORITY_LABELS[priority]
      )
    );
  }
  if (task.status && STATUS_LABELS[task.status]) {
    badges.appendChild(
      buildBadge("badge-status", createStatusIcon(), STATUS_LABELS[task.status])
    );
  }
  if (task.is_fast) {
    badges.appendChild(buildBadge("badge-fast", createFastIcon(), "Fast line"));
  }
  head.appendChild(badges);
  return head;
}

/* Признак (мокап .attr): карточка bg-subtle с dt/dd. Пустое значение —
 * приглушенный текст (мокап: «не указана»). */
function buildAttr(term, value, mutedText) {
  var attr = el("div", "attr");
  attr.appendChild(el("dt", null, term));
  var dd = el("dd");
  if (value === null || value === undefined || value === "") {
    dd.appendChild(el("span", "attr-muted", mutedText || "не указано"));
  } else {
    dd.textContent = String(value); // textContent — не innerHTML (XSS)
  }
  attr.appendChild(dd);
  return attr;
}

/* Сетка признаков (мокап .attr-grid): категория / срок / fast line /
 * оценка — ровно как в утвержденном макете. Оценки в схеме Task нет —
 * карточка всегда показывает muted-«не указана» (данные не выдумываются). */
function buildAttrsGrid(task) {
  var grid = el("dl", "attr-grid");
  grid.appendChild(buildAttr("Категория", task.category));
  grid.appendChild(buildAttr("Срок", task.due_date));
  grid.appendChild(
    buildAttr(
      "Fast line",
      task.is_fast ? "Да" : null,
      "нет · назначается при создании"
    )
  );
  grid.appendChild(buildAttr("Оценка", task.estimate, "не указана"));
  return grid;
}

/* Люди (мокап .people-row): только при наличии полей assigned/creator в
 * ответе API — иначе секция не выводится (сценарий 4, ОВ-24). */
function buildPeople(task) {
  var hasAssigned = Object.prototype.hasOwnProperty.call(task, "assigned");
  var hasCreator = Object.prototype.hasOwnProperty.call(task, "creator");
  if (!hasAssigned && !hasCreator) {
    return null;
  }
  var row = el("div", "people-row");
  if (hasCreator) {
    row.appendChild(buildPerson(task.creator, "Автор", true));
  }
  if (hasAssigned) {
    row.appendChild(buildPerson(task.assigned, "Исполнитель", false));
  }
  return row;
}

/* Тело окна по мокапу собирается ЦЕЛИКОМ в JS (разметка board.html
 * остается прежней — DOM-id не переименованы и не добавлены, ОГР-28):
 * секции (Описание → Признаки → Теги → Люди) рендерятся в контейнер
 * .task-view-body, который task-detail.js создает один раз и ставит
 * ПЕРЕД существующим dl#task-detail-attrs (контракт attrs и порядок
 * «тело → комментарии» сохранены). */
function ensureViewBody(dl) {
  var body = dl.parentElement.querySelector(".task-view-body");
  if (!body) {
    body = el("div", "task-view-body");
    dl.parentElement.insertBefore(body, dl);
  }
  return body;
}

function renderTaskDetail(task) {
  boardState.currentTaskId = task.id;

  /* Шапка (кикер/заголовок/бейджи) + тело (секции мокапа). */
  var modal = document.querySelector("#task-detail-overlay .modal");
  var head = modal.querySelector(".task-view-head");
  if (!head) {
    head = el("div", "task-view-head");
    /* Шапка — первым блоком окна (после крестика). */
    modal.insertBefore(head, modal.firstChild);
  }
  head.textContent = "";
  head.appendChild(buildViewHead(task));

  var dl = document.getElementById("task-detail-attrs");
  var body = ensureViewBody(dl);
  body.textContent = "";

  /* Описание — секция мокапа: подпись-кикер + параграф .modal-desc
   * (пустое — muted-строка). */
  var descSection = el("section", "task-view-section");
  descSection.appendChild(el("p", "section-label", "Описание"));
  var desc = el("p", "task-view-desc");
  if (task.description) {
    desc.textContent = task.description; // textContent — не innerHTML (XSS)
  } else {
    desc.appendChild(el("span", "attr-muted", "Описание не указано"));
  }
  descSection.appendChild(desc);
  body.appendChild(descSection);

  /* Признаки — сетка мокапа (категория/срок/fast line/оценка). */
  var attrsSection = el("section", "task-view-section");
  attrsSection.appendChild(el("p", "section-label", "Признаки"));
  attrsSection.appendChild(buildAttrsGrid(task));
  body.appendChild(attrsSection);

  /* Теги — чипы мокапа; пустой список — секция не выводится. */
  var tags = task.tags || [];
  if (tags.length) {
    var tagsSection = el("section", "task-view-section");
    tagsSection.appendChild(el("p", "section-label", "Теги"));
    var chips = el("div", "tag-chips");
    tags.forEach(function (tag) {
      chips.appendChild(el("span", "tag-chip", String(tag)));
    });
    tagsSection.appendChild(chips);
    body.appendChild(tagsSection);
  }

  /* Люди — секция при наличии полей в ответе API (сценарий 4). */
  var people = buildPeople(task);
  if (people) {
    var peopleSection = el("section", "task-view-section");
    peopleSection.appendChild(el("p", "section-label", "Люди"));
    peopleSection.appendChild(people);
    body.appendChild(peopleSection);
  }

  /* #task-detail-attrs (id сохранен, ОГР-28): те же данные задачи, что
   * и раньше — контракт утвержденного e2e TC-UI-009 (attrs содержат
   * ровно значения задачи) сохранен дословно. */
  dl.textContent = "";
  addDetailRow(dl, "Описание", task.description);
  /* Приоритет в attrs — сырым значением (контракт утвержденного
   * e2e TC-UI-009: attrs содержат ровно значения задачи); цвет+иконка
   * приоритета — в шапке (бейдж), в форме и на карточке (FR-29). */
  addDetailRow(dl, "Приоритет", task.priority);
  addDetailRow(dl, "Категория", task.category);
  addDetailRow(dl, "Срок", task.due_date);
  addDetailRow(dl, "Статус", STATUS_LABELS[task.status]);
  addDetailRow(dl, "Теги", tags.join(", "));
  addDetailRow(dl, "Fast line", task.is_fast ? "да" : null);
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

/* --- r8 2.2: focus trap + возврат фокуса (мокап, правило 5 ui_designer) --- */

var lastViewTrigger = null;

/* Триггер (карточка) запоминается ДО открытия окна — возврат фокуса
 * при закрытии (Escape/крестик/«Закрыть»/подложка — все через
 * closeTaskDetail, кроме «Редактировать»). */
function rememberViewTrigger(target) {
  lastViewTrigger = target && typeof target.focus === "function" ? target : null;
}

function restoreViewFocus() {
  if (lastViewTrigger && document.contains(lastViewTrigger)) {
    lastViewTrigger.focus();
  }
  lastViewTrigger = null;
}

/* Tab-цикл внутри окна (мокап): фокус не покидает dialog, пока открыта
 * view-модалка и не открыта форма (тот же инвариант, что у Escape). */
function initFocusTrap() {
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Tab") {
      return;
    }
    var view = document.getElementById("task-detail-overlay");
    var form = document.getElementById("task-form-overlay");
    if (view.hidden || !form.hidden) {
      return;
    }
    var focusables = view.querySelectorAll(
      "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])"
    );
    if (!focusables.length) {
      return;
    }
    var first = focusables[0];
    var last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
}

/* --- Открытие/закрытие (сценарии 1 и 5: закрытие без изменения данных) --- */

export function openTaskDetail(taskId) {
  if (!isValidTaskId(taskId)) {
    return;
  }
  boardState.currentTaskId = taskId;
  /* r8 2.2 (мокап): триггер запоминается до показа; фокус — крестик. */
  rememberViewTrigger(document.activeElement);
  document.getElementById("task-detail-overlay").hidden = false;
  var closeBtn = document.getElementById("task-view-close");
  if (closeBtn) {
    closeBtn.focus();
  }
  renderDetailComments(document.getElementById("task-comments-list"), []);
  /* GET /api/tasks/{id} — полный Task (sdd §3.2), затем комментарии. */
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
  /* r8 2.2 (мокап): возврат фокуса на триггер (карточку). */
  restoreViewFocus();
}

/* --- Управление view-модалкой: «Редактировать» (Д-9), закрытие --- */

export function initTaskViewControls() {
  initFocusTrap();
  /* Д-9 (сценарий 3): «Редактировать» → существующая форма
   * редактирования этой задачи. Свежая копия задачи
   * (GET /api/tasks/{id}) — как до 4.1. */
  document
    .getElementById("task-edit-button")
    .addEventListener("click", function () {
      if (boardState.currentTaskId === null) {
        return;
      }
      /* Форма закрывает view сама (openEditForm, task-form.js), минуя
       * closeTaskDetail — запомненный триггер сбрасываем вручную. */
      lastViewTrigger = null;
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
