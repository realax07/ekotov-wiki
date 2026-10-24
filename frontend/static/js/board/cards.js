/* Рендер доски и карточек (P6: извлечено из board.js; tasks.md 4.3,
 * 4.5, 5.2 Релиза 1, 2.5; FR-1, FR-2, FR-9, FR-29).
 *
 * 2.5 (FR-29, ОГР-8): бейдж приоритета на карточке — пилюля с цветом,
 * inline SVG-иконкой (↓/=/↑, priority-icons.js) и текстом «Низкий/
 * Средний/Высокий» — различим без цвета; без внешних библиотек.
 *
 * 4.3: карточки (title, priority-индикатор, category, due_date — FR-9).
 * 5.2 (FR-3) + 2.1 add-ui-polish-r8 (FR-87): fast line подсвечена
 * светло-синим ТОЛЬКО на плитке fast-задачи (task-card-fast); окраска
 * столбца (прежний класс has-fast) убрана. Fast-задачи приходят с
 * сервера уже отсортированными по приоритету (sdd §3.3) — рендер
 * сохраняет порядок ответа.
 *
/**
 * 2.1/2.2 Релиза 3 (FR-31, ОГР-14, Д-6): drag-and-drop карточек между
 * столбцами — нативный HTML5 DnD, без новых зависимостей.
 *
 * Сценарий (design.md §1, спека board):
 * - dragstart: карточка получает класс drag-ghost (по пресету В
 *   «Выразительный» — визуал клона делает CSS), исходная позиция
 *   запоминается до подтверждения ответа сервера;
 * - dragover на столбце: preventDefault (иначе drop не сработает) +
 *   подсветка зоны-приемника классом drop-target; dragleave снимает;
 * - drop над столбцом: POST /api/tasks/{id}/move с целевым статусом —
 *   тот же API, что прежний перевод через селект (ОГР-14), серверные
 *   правила (fast line 409, архивация done) не меняются;
 * - ошибка (409 «fast line occupied», Д-6, и иные 4xx/сеть): ошибка в
 *   #board-error, доска перерисовывается из серверного состояния —
 *   плитка возвращается на исходное место;
 * - успех: перерисовка доски из ответа GET-подобного тела Task —
 *   refreshBoard (единый источник правды, порядок столбцов с сервера);
 * - отпускание вне зон-приемников: drop не вызывается, браузер сам
 *   возвращает визуал, статус не отправляется;
 * - touch не затрагивается (HTML5 DnD не срабатывает на touch — перенос
 *   прежним способом через карточку задачи, ОВ-19).
 *
 * Подсветка зоны и drag-образ — по пресету В (утвержден Заказчиком
 * 2026-09-27, design/p8-presets.html): классы drop-target/drag-ghost на
 * столбце/карточке, стили в board.css (только transform/opacity/фон;
 * prefers-reduced-motion отключает анимации).
 */
"use strict";

import { el, showBoardError, hideError } from "./dom.js";
import { api } from "./api.js";
import { COLUMNS, FASTLINE_STAGES, boardState, isFastTask } from "./state.js";
import { createPriorityIcon, priorityLabel } from "./priority-icons.js";
import { attachCardTooltip } from "./card-tooltip.js";

export { showBoardError } from "./dom.js";

/* --- DnD: перетаскивание карточек между столбцами (2.1/2.2, FR-31) --- */

/* Идет ли перенос: на время запроса move повторный dragstart той же
 * карточки блокируется (защита от двойного POST). */
let dragInProgress = false;

/* Состояние активной drag-сессии (2.1): id задачи и исходный столбец;
 * null — переноса нет. Исходная позиция восстанавливается перерисовкой
 * доски, если сервер отклонил перевод (Д-6). */
let dnd = null;

/* --- Рендер карточки (4.3, fast-бейдж; 4.5: клик → карточка) --- */

let onClickCard = null;

/* Точка входа регистрирует обработчик клика по карточке (в монолите —
 * прямой вызов openTaskDetail из замыкания). */
export function setCardClickHandler(handler) {
  onClickCard = handler;
}

/* Обработчик быстрого «Выполнено» ставит board-init.js (инъекция — как
 * setCardClickHandler: разрыв цикла cards ↔ task-form). */
let onQuickDone = null;

export function setQuickDoneHandler(handler) {
  onQuickDone = handler;
}

/* --- 5.1 (FR-45, ОВ-24): строка «assigned · creator» на карточке --- */

/* Подпись пользователя: display_name или логин — на карточке доступны
 * только логины из API (creator/assigned, sdd §3.2), Д-10 применяется
 * к данным, которые есть. */
function userLabel(login) {
  return login ? String(login) : "—";
}

function buildAssigneeLine(task) {
  var line = el("div", "task-card-users");
  var assigned = el("span", "task-card-assigned");
  if (task.assigned) {
    assigned.textContent = userLabel(task.assigned);
  } else {
    /* Пустой assigned — курсивом «Unassigned» (ОВ-24; строка
     * отображается ВСЕГДА — в т.ч. без исполнителя). */
    assigned.appendChild(el("em", "task-card-unassigned", "Unassigned"));
  }
  line.appendChild(assigned);
  line.appendChild(el("span", "task-card-users-sep", "·"));
  var creator = el("span", "task-card-creator");
  creator.textContent = userLabel(task.creator);
  line.appendChild(creator);
  return line;
}

/* Дни до срока (T-отсчет fast-карточки): целые сутки по локальной дате;
 * due_date — YYYY-MM-DD. Просрочка — отрицательное значение (T+-Nд). */
function fastDaysLeft(dueDate) {
  var due = new Date(dueDate + "T00:00:00");
  var now = new Date();
  var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((due - today) / 86400000);
}

/* Доля трека отсчета, % (0…100) — окно 7 дней до срока. */
function fastTrackPercent(dueDate) {
  var left = fastDaysLeft(dueDate);
  if (left >= 7) return 100;
  if (left <= 0) return left === 0 ? 14 : 0;
  return Math.round((left / 7) * 100);
}

export function renderCard(task) {
  /* 2.1 (FR-31): карточка — источник перетаскивания (только мышь;
   * touch-устройства HTML5 DnD не срабатывает — перенос прежним
   * способом, ОВ-19). */
  var card = el("article", "task-card");
  card.draggable = true;
  card.dataset.taskId = task.id;
  card.dataset.fast = task.is_fast ? "true" : "false";
  if (task.is_fast) {
    /* 5.2 (FR-3): fast-карточка визуально выделена подсветкой
     * (плюс бейдж fast ниже). */
    card.classList.add("task-card-fast");
  }

  if (task.priority) {
    card.classList.add("task-priority-" + task.priority);
  }

  var header = el("div", "task-card-header");
  if (task.priority) {
    /* 5.2 (FR-29, ОГР-8): бейдж приоритета — пилюля «цвет + inline SVG
     * (↓/=/↑) + текст»; различим без цвета (иконка + текст). */
    var badge = el("span", "task-priority-badge priority-" + task.priority);
    badge.appendChild(createPriorityIcon(task.priority, 10, 2.5));
    badge.appendChild(
      document.createTextNode(priorityLabel(task.priority))
    );
    header.appendChild(badge);
  }
  if (task.is_fast) {
    header.appendChild(el("span", "task-fast-badge", "fast"));
  }
  card.appendChild(header);

  card.appendChild(el("h3", "task-card-title", task.title));

  var meta = el("div", "task-card-meta");
  if (task.category) {
    meta.appendChild(el("span", "task-category", task.category));
  }
  if (task.due_date) {
    meta.appendChild(el("span", "task-due-date", "до " + task.due_date));
  }
  if (task.is_fast && task.due_date) {
    /* redesign-console 2.2 (fastline дельта, мокап §fastline): T-отсчет до
     * срока — mono янтарь справа (decor; данные — реальный due_date).
     * due_date — дата без времени (sdd §4): отсчет в СУТКАХ до срока
     * («T-Nд»; сегодня — «T-0д», просрочено — «T+Nd»). */
    meta.appendChild(
      el("span", "task-due-t", "T-" + fastDaysLeft(task.due_date) + "д")
    );
  }
  if (meta.childNodes.length) {
    card.appendChild(meta);
  }
  if (task.is_fast && task.due_date) {
    /* Трек отсчета (мокап .fastline-track): полоса 2px, заполнение —
     * градиент amber→cyan; aria-hidden — decor. Окно отсчета — 7 дней
     * до срока (created_at в контракте задачи нет): доля = оставшиеся
     * сутки / 7, ограничено 0…100%. */
    var track = el("span", "task-fast-track");
    track.setAttribute("aria-hidden", "true");
    var fill = document.createElement("i");
    fill.style.width = fastTrackPercent(task.due_date) + "%";
    track.appendChild(fill);
    card.appendChild(track);
  }

  /* 5.1 (FR-45, ОВ-24): строка «assigned · creator» — ВСЕГДА (все
   * столбцы и fast line одинаково). Пустой assigned — курсивом
   * «Unassigned»; creator отображается всегда (задача без creator
   * в данных — прочерк «—», данные не выдумываются). Поля появляются
   * в ответах API с задачей 5.1 — до тех пор строка не строится
   * (гвард hasOwnProperty, как в task-detail.js). */
  if (
    Object.prototype.hasOwnProperty.call(task, "assigned") ||
    Object.prototype.hasOwnProperty.call(task, "creator")
  ) {
    var usersLine = buildAssigneeLine(task);
    card.appendChild(usersLine);
    /* 5.1 (FR-44, ОГР-17); Р5 polish: tooltip — ТОЛЬКО на строке
     * пользователей (assigned · creator), не на всей карточке (карточка —
     * зона drag/клика). Единый механизм tooltip.js (attach, задержка
     * 300мс, reduced-motion отключает анимацию CSS-ом app.css). Модуль
     * недоступен — карточка работает без всплывашки (строка
     * assigned · creator остается). */
    attachCardTooltip(usersLine, task);
  }

  /* 2.1 add-responsive-mobile (FR-101, design §3): быстрое «Выполнено» —
   * главное тач-действие карточки. Строится при наличии обработчика
   * (инъекция board-init.js, ниже) и вне столбца done (перевод «в
   * Выполнено»; задача из done убирается через view/редактирование).
   * Тач-таргет ≥44px дает CSS (board.css, ≤480px); на desktop кнопка
   * не строится — перенос там через DnD/меню (NFR-29, тач-DnD anti-scope). */
  if (onQuickDone && task.status !== "done") {
    var quick = document.createElement("button");
    quick.type = "button";
    quick.className = "task-quick-done";
    quick.setAttribute(
      "aria-label",
      "Переместить в «Выполнено»: " + task.title
    );
    quick.appendChild(document.createTextNode("Выполнено"));
    quick.addEventListener("click", function (event) {
      /* Клик по кнопке не должен открывать view-модалку карточки. */
      event.stopPropagation();
      onQuickDone(task.id);
    });
    card.appendChild(quick);
  }

  card.addEventListener("click", function () {
    if (onClickCard) {
      onClickCard(task.id);
    }
  });

  return card;
}

export function renderBoard(data) {
  var columns = data.columns || {};
  /* P23: разделение задач по is_fast (design §3) — fast ТОЛЬКО в столбцы
   * зоны FASTLINE, обычные ТОЛЬКО в канбан; ответ и сортировка GET
   * /api/board не меняются. Слот зоны «1 задача»: инвариант считает
   * только АКТИВНУЮ fast (todo/in_progress, design §2) — выполненная в
   * «Выполнено» зоны слот не занимает (кнопка активна, чип скрыт). */
  var fastlineBusy = false;
  COLUMNS.forEach(function (status) {
    var container = document.querySelector(
      '#board .board-column[data-status="' + status + '"] [data-cards]'
    );
    container.textContent = "";
    /* 2.1 add-ui-polish-r8 (FR-87): подсветка fast line — только на
     * плитке (.task-card-fast в renderCard); класс столбца has-fast
     * больше не ставится — окраска столбца убрана. P23: fast-карты
     * в канбан не попадают вовсе. */
    (columns[status] || []).forEach(function (task) {
      if (!isFastTask(task)) {
        container.appendChild(renderCard(task));
      }
    });
    /* 3.1 (FR-32): оформленный пустой state пустого столбца —
     * пунктирная зона (board.css), текст дает CSS (::before). */
    var column = container.closest(".board-column");
    var isEmpty = !container.firstElementChild;
    column.classList.toggle("board-column-empty", isEmpty);
    container.hidden = false;
  });
  /* P23: зона FASTLINE — этап = status (design §2). Пустые столбцы зоны
   * отображаются ПОЛНОСТЬЮ и БЕЗ подсказок (ОВ-3): board-column-empty
   * в зоне не ставится, вид дает CSS (min-height контейнера). */
  FASTLINE_STAGES.forEach(function (status) {
    var container = document.querySelector(
      '#fastline .fastline-column[data-fastline-stage="' + status + '"] [data-cards]'
    );
    container.textContent = "";
    (columns[status] || []).forEach(function (task) {
      if (isFastTask(task)) {
        container.appendChild(renderCard(task));
        if (status !== "done") {
          fastlineBusy = true;
        }
      }
    });
  });
  /* Гейты доступности (design §4.1): состояние из последнего GET
   * /api/board — кнопка «+ Fast-задача» (disabled + чип при занятой
   * зоне, v2-blocked) и boardState.fastlineBusy для чекбокса
   * edit-формы (task-form.js 2.5). */
  boardState.fastlineBusy = fastlineBusy;
  var addButton = document.getElementById("fastline-add-button");
  if (addButton) {
    addButton.disabled = fastlineBusy;
  }
  var chip = document.getElementById("fastline-blocked-hint");
  if (chip) {
    chip.hidden = !fastlineBusy;
  }
  /* Столбец «Выполнено» (sdd r5 §3.3) — реальный список задач: done
   * сегодня по МСК; автоархивация — на сервере (GET /api/board).
   * done_note прежней редакции больше не существует. */
  document.getElementById("board").dataset.loaded = "true";
  updateDecor(columns);
}

/* --- redesign-console 2.2 (decor): mono-счетчики колонок и терминальный
 * readout pagehead (дата, ACT/DONE) — из реальных данных GET /api/board;
 * элементы декоративные (aria-hidden в разметке), поведение не трогают. */
function updateDecor(columns) {
  var act = 0;
  var done = 0;
  COLUMNS.forEach(function (status) {
    var n = (columns[status] || []).length;
    if (status === "done") {
      done = n;
    } else {
      act += n;
    }
    var counter = document.querySelector('[data-col-count="' + status + '"]');
    if (counter) {
      counter.textContent = String(n);
    }
  });
  var actOut = document.getElementById("readout-act");
  var doneOut = document.getElementById("readout-done");
  var dateOut = document.getElementById("readout-date");
  if (actOut) actOut.textContent = String(act);
  if (doneOut) doneOut.textContent = String(done);
  if (dateOut) {
    dateOut.textContent = new Date().toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
    });
  }
}

export function refreshBoard() {
  api("/api/board", {}, showBoardError, renderBoard);
}

/* --- 2.1/2.2 (FR-31, Д-6) + P23: HTML5 DnD канбана и зоны FASTLINE --- */

/* P23: зона события по столбцу — #fastline (столбцы .fastline-column,
 * этап в data-fastline-stage) или #board (канбан, data-status). null —
 * событие вне зон-приемников. */
function dropTargetInfo(column) {
  if (!column) {
    return null;
  }
  if (column.closest("#fastline")) {
    return { zone: "fastline", status: column.dataset.fastlineStage, column: column };
  }
  if (column.closest("#board")) {
    return { zone: "kanban", status: column.dataset.status, column: column };
  }
  return null;
}

function eventColumn(event) {
  return event.target.closest(".board-column, .fastline-column");
}

/* Направление разрешено? (design §5, ОВ-4): fast-карта перемещается
 * ТОЛЬКО между столбцами зоны (голубой приемник), обычная — только по
 * канбану (терракота). DnD не назначает is_fast (move не меняет его —
 * Э2): обычная задача в зоне не окажется ни в каком направлении. */
function dropAllowed(info) {
  return dnd.fast ? info.zone === "fastline" : info.zone === "kanban";
}

function clearDropHighlight() {
  document
    .querySelectorAll(".drop-target, .drop-forbidden")
    .forEach(function (column) {
      column.classList.remove("drop-target");
      column.classList.remove("drop-forbidden");
    });
}

/* Перевод задачи в столбец (тот же POST /api/tasks/{id}/move, что и
 * прежний перевод селектом в карточке задачи — ОГР-14). Успех —
 * перерисовка доски; отказ (409 fast line занята — Д-6, иные 4xx,
 * сеть) — ошибка в #board-error и перерисовка: плитка возвращается на
 * исходное место, инварианты сервера не нарушены (2.2).
 *
 * dragInProgress снимается по факту ответа (review-001-2.1-2.2 №2):
 * api() в каждой ветке — ok/204, 4xx (включая 409) и сеть — вызывает
 * ровно один из колбэков onOk/onError, так что разблокировка здесь
 * покрывает все исходы запроса; таймер-предохранитель не нужен. */
function moveTask(taskId, status) {
  api(
    "/api/tasks/" + taskId + "/move",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: status }),
    },
    function (message) {
      /* Д-6: отказ перевода — ошибка видима в UI (бокс под столбцами,
       * тот же, что при загрузке доски). */
      showBoardError(message);
      refreshBoard();
      dragInProgress = false;
    },
    function () {
      /* BUG-004 (TC-dnd-106): успех — устаревшую ошибку доски (например
       * 409 «fast line занята» предыдущего отказа) убираем ДО
       * перерисовки: renderBoard не трогает #board-error (скрытие здесь,
       * а не в renderBoard — иначе onErr-ветка moveTask, которая тоже
       * перерисовывает доску, гасила бы свежую ошибку 409 и ломала
       * TC-dnd-103). Новый отказ снова покажет бокс через onErr. */
      hideError("board-error");
      refreshBoard();
      dragInProgress = false;
    }
  );
}

function onDragStart(event) {
  var card = event.target.closest(".task-card");
  if (!card || dragInProgress) {
    /* Тянуть можно только карточку; во время незавершенного перевода —
     * никакую (dragInProgress не дает устроить двойной POST). */
    event.preventDefault();
    return;
  }
  var info = dropTargetInfo(
    card.closest(".board-column, .fastline-column")
  );
  dnd = {
    taskId: Number(card.dataset.taskId),
    fromStatus: info ? info.status : null,
    /* P23: направление задает признак fast-карты (dataset ставит
     * renderCard), не зона-источник — карточка и есть «что тащим». */
    fast: card.dataset.fast === "true",
  };
  /* Пресет В: перетаскиваемая карточка — drag-ghost (клон к курсору
   * рисует браузер, визуал — CSS-класс; оригинал исчезает с места). */
  requestAnimationFrame(function () {
    card.classList.add("drag-ghost");
  });
  event.dataTransfer.effectAllowed = "move";
  /* Firefox требует данных для старта drag-сессии. */
  event.dataTransfer.setData("text/plain", String(dnd.taskId));
}

function onDragOver(event) {
  var info = dropTargetInfo(eventColumn(event));
  if (!dnd || !info) {
    return;
  }
  if (!dropAllowed(info)) {
    /* P23 (v2-dnd-blocked, Э2): обычная карта над столбцом зоны —
     * красный пунктир + знак запрета (cursor not-allowed дает CSS);
     * preventDefault НЕТ — drop не сработает и POST не уйдет.
     * fast-карта над канбаном — без подсветки: канбан не-приемник. */
    clearDropHighlight();
    if (info.zone === "fastline") {
      info.column.classList.add("drop-forbidden");
    }
    return;
  }
  /* Без preventDefault браузер не даст drop над столбцом. */
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
  /* Подсветка зоны-приемника (пресет В): класс только на текущем
   * столбце — dragleave-мерцание между детьми гасим перерисовкой.
   * BUG-003: тогглим класс только на column (текущем приемнике),
   * снимаем с предыдущего (баг: forEach по COLUMNS ставил/снимал
   * класс на одном и том же элементе — подсветка удерживалась лишь
   * на последнем столбце COLUMNS). */
  clearDropHighlight();
  info.column.classList.add("drop-target");
}

function onDragLeave(event) {
  var column = eventColumn(event);
  if (!dnd || !column) {
    return;
  }
  /* Мерцание: dragleave летит и при входе на ребенка столбца; снимаем
   * подсветку только если курсор реально покинул столбец. */
  var to = event.relatedTarget;
  if (!to || !column.contains(to)) {
    column.classList.remove("drop-target");
    column.classList.remove("drop-forbidden");
  }
}

function onDrop(event) {
  var info = dropTargetInfo(eventColumn(event));
  if (!dnd || !info) {
    return; /* Вне зон-приемников: статус не отправляется. */
  }
  if (!dropAllowed(info)) {
    /* P23: запрещенное направление (канбан→зона, зона→канбан) —
     * запрос НЕ отправляется (v2-dnd-blocked; Э2). */
    return;
  }
  event.preventDefault();
  var targetStatus = info.status;
  var taskId = dnd.taskId;
  var fromStatus = dnd.fromStatus;
  clearDropHighlight();
  dnd = null;
  if (targetStatus === fromStatus) {
    /* «Перенос» в свой столбец — no-op без запроса. */
    return;
  }
  /* O1 (ревью №1): ровно один POST move на один drop — dnd обнулен ДО
   * moveTask (повторный drop/dragend в этой сессии — ранний return),
   * dragInProgress не пускает новый dragstart до ответа сервера. */
  dragInProgress = true;
  moveTask(taskId, targetStatus);
}

function onDragEnd(event) {
  var card = event.target.closest(".task-card");
  if (card) {
    card.classList.remove("drag-ghost");
  }
  clearDropHighlight();
}

/* Регистрация обработчиков DnD на контейнерах обеих зон (делегирование —
 * переживает перерисовки renderBoard). Вызывает board-init.js. */
export function initCardDragAndDrop() {
  ["board", "fastline"].forEach(function (zoneId) {
    var zone = document.getElementById(zoneId);
    if (!zone) {
      return;
    }
    zone.addEventListener("dragstart", onDragStart);
    zone.addEventListener("dragover", onDragOver);
    zone.addEventListener("dragleave", onDragLeave);
    zone.addEventListener("drop", onDrop);
    zone.addEventListener("dragend", onDragEnd);
  });
}
