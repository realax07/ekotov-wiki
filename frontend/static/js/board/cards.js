/* Рендер доски и карточек (P6: извлечено из board.js; tasks.md 4.3,
 * 4.5, 5.2 Релиза 1, 2.5; FR-1, FR-2, FR-9, FR-29).
 *
 * 2.5 (FR-29, ОГР-8): бейдж приоритета на карточке — пилюля с цветом,
 * inline SVG-иконкой (↓/=/↑, priority-icons.js) и текстом «Низкий/
 * Средний/Высокий» — различим без цвета; без внешних библиотек.
 *
 * 4.3: карточки (title, priority-индикатор, category, due_date — FR-9).
 * 5.2 (FR-3): fast line подсвечена светло-синим прозрачным (столбец с
 * fast-задачей — класс has-fast, карточка — task-card-fast); fast-задачи
 * приходят с сервера уже отсортированными по приоритету (sdd §3.3) —
 * рендер сохраняет порядок ответа.
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
import { COLUMNS } from "./state.js";
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
  if (meta.childNodes.length) {
    card.appendChild(meta);
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
    card.appendChild(buildAssigneeLine(task));
    /* 5.1 (FR-44, ОГР-17): tooltip карточки (assigned + creator) —
     * единый механизм tooltip.js (attach, задержка 300мс, reduced-motion
     * отключает анимацию CSS-ом app.css). Модуль недоступен — карточка
     * работает без всплывашки (строка assigned · creator остается). */
    attachCardTooltip(card, task);
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
  COLUMNS.forEach(function (status) {
    var container = document.querySelector(
      '.board-column[data-status="' + status + '"] [data-cards]'
    );
    container.textContent = "";
    var hasFast = false;
    /* Порядок ответа сервера сохраняется: сервер (sdd §3.3) уже
     * отсортировал задачи в столбце по приоритету (fast — первыми). */
    (columns[status] || []).forEach(function (task) {
      if (task.is_fast) {
        hasFast = true;
      }
      container.appendChild(renderCard(task));
    });
    /* 5.2 (FR-3): столбец с fast-задачей = подсвеченная fast line. */
    var column = container.closest(".board-column");
    column.classList.toggle("has-fast", hasFast);
    /* 3.1 (FR-32): оформленный пустой state пустого столбца —
     * пунктирная зона (board.css), текст дает CSS (::before). */
    var isEmpty = !container.firstElementChild;
    column.classList.toggle("board-column-empty", isEmpty);
    container.hidden = false;
  });
  /* Столбец «Выполнено» (sdd r5 §3.3) — реальный список задач: done
   * сегодня по МСК; автоархивация — на сервере (GET /api/board).
   * done_note прежней редакции больше не существует. */
  document.getElementById("board").dataset.loaded = "true";
}

export function refreshBoard() {
  api("/api/board", {}, showBoardError, renderBoard);
}

/* --- 2.1/2.2 (FR-31, Д-6): HTML5 DnD --- */

/* Столбец-приемник по status-атрибуту; null — вне зон. */
function columnByStatus(status) {
  return document.querySelector(
    '.board-column[data-status="' + status + '"]'
  );
}

function clearDropHighlight() {
  COLUMNS.forEach(function (status) {
    var column = columnByStatus(status);
    if (column) {
      column.classList.remove("drop-target");
    }
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
  var column = card.closest(".board-column");
  dnd = {
    taskId: Number(card.dataset.taskId),
    fromStatus: column ? column.dataset.status : null,
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
  var column = event.target.closest(".board-column");
  if (!dnd || !column) {
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
  column.classList.add("drop-target");
}

function onDragLeave(event) {
  var column = event.target.closest(".board-column");
  if (!dnd || !column) {
    return;
  }
  /* Мерцание: dragleave летит и при входе на ребенка столбца; снимаем
   * подсветку только если курсор реально покинул столбец. */
  var to = event.relatedTarget;
  if (!to || !column.contains(to)) {
    column.classList.remove("drop-target");
  }
}

function onDrop(event) {
  var column = event.target.closest(".board-column");
  if (!dnd || !column) {
    return; /* Вне зон-приемников: статус не отправляется. */
  }
  event.preventDefault();
  var targetStatus = column.dataset.status;
  var taskId = dnd.taskId;
  var fromStatus = dnd.fromStatus;
  clearDropHighlight();
  dnd = null;
  if (targetStatus === fromStatus) {
    /* «Перенос» в свой столбец — no-op без запроса. */
    return;
  }
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

/* Регистрация обработчиков DnD на контейнере доски (делегирование —
 * переживает перерисовки renderBoard). Вызывает board-init.js. */
export function initCardDragAndDrop() {
  var board = document.getElementById("board");
  board.addEventListener("dragstart", onDragStart);
  board.addEventListener("dragover", onDragOver);
  board.addEventListener("dragleave", onDragLeave);
  board.addEventListener("drop", onDrop);
  board.addEventListener("dragend", onDragEnd);
}
