/* Доска (tasks.md 4.3; FR-1, FR-2; sdd.md §3.3): при открытии страницы
 * GET /api/board и рендер задач по трем столбцам. Веб-морда — клиент
 * REST API (ОГР-2, design.md §7): данные только через API, сессионная
 * кука — credentials: "same-origin". Без сессии API отвечает 401 —
 * страница сама не открылась бы (middleware редиректит на /login).
 *
 * Структура ответа (sdd.md §3.3):
 * {"columns": {"todo": [Task], "in_progress": [Task], "done_note": "…"}}
 * Пустая доска → три пустых столбца, без ошибок (дельта board,
 * «Открытие пустой доски»). Карточка: title, priority-индикатор,
 * category, due_date (FR-9); детали карточки — задача 4.5. Визуальное
 * выделение fast line — задача 5.2 (данные is_fast в карточку уже
 * выводятся атрибутом data-fast).
 */
(function () {
  "use strict";

  var COLUMNS = ["todo", "in_progress"];

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function renderCard(task) {
    var card = el("article", "task-card");
    card.dataset.taskId = task.id;
    card.dataset.fast = task.is_fast ? "true" : "false";

    if (task.priority) {
      card.classList.add("task-priority-" + task.priority);
    }

    var header = el("div", "task-card-header");
    if (task.priority) {
      // Priority-индикатор (FR-9): цветная метка + текст приоритета.
      header.appendChild(
        el("span", "task-priority-badge priority-" + task.priority, task.priority)
      );
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

    return card;
  }

  function showError(message) {
    var box = document.getElementById("board-error");
    box.textContent = message;
    box.hidden = false;
  }

  function renderBoard(data) {
    var columns = data.columns || {};
    COLUMNS.forEach(function (status) {
      var container = document.querySelector(
        '.board-column[data-status="' + status + '"] [data-cards]'
      );
      container.textContent = "";
      (columns[status] || []).forEach(function (task) {
        container.appendChild(renderCard(task));
      });
    });
    var note = document.querySelector("[data-done-note]");
    if (note) {
      note.textContent = columns.done_note || "";
    }
    document.getElementById("board").dataset.loaded = "true";
  }

  fetch("/api/board", { credentials: "same-origin" })
    .then(function (response) {
      if (!response.ok) {
        throw new Error("board request failed: " + response.status);
      }
      return response.json();
    })
    .then(renderBoard)
    .catch(function () {
      showError("Не удалось загрузить доску. Обновите страницу.");
    });
})();
