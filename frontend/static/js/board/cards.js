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
 * Обработчик клика по карточке инъецируется точкой входа
 * (board-init.js), а не импортируется из task-detail.js: task-detail
 * использует refreshBoard — прямой импорт создал бы цикл
 * cards → task-detail → cards.
 * XSS (ОГР-11): рендер — createElement + textContent, не innerHTML.
 */
"use strict";

import { el, showBoardError } from "./dom.js";
import { api } from "./api.js";
import { COLUMNS } from "./state.js";
import { createPriorityIcon, priorityLabel } from "./priority-icons.js";

export { showBoardError } from "./dom.js";

/* --- Рендер карточки (4.3, fast-бейдж; 4.5: клик → карточка) --- */

let onClickCard = null;

/* Точка входа регистрирует обработчик клика по карточке (в монолите —
 * прямой вызов openTaskDetail из замыкания). */
export function setCardClickHandler(handler) {
  onClickCard = handler;
}

export function renderCard(task) {
  var card = el("article", "task-card");
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
    container
      .closest(".board-column")
      .classList.toggle("has-fast", hasFast);
  });
  /* Столбец «Выполнено» (sdd r5 §3.3) — реальный список задач: done
   * сегодня по МСК; автоархивация — на сервере (GET /api/board).
   * done_note прежней редакции больше не существует. */
  document.getElementById("board").dataset.loaded = "true";
}

export function refreshBoard() {
  api("/api/board", {}, showBoardError, renderBoard);
}
