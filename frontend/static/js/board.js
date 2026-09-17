/* Доска (tasks.md 4.3, 4.5; FR-1, FR-2, FR-5, FR-7, FR-9; sdd.md §3.2,
 * §3.3): при открытии страницы GET /api/board и рендер задач по трем
 * столбцам. Веб-морда — клиент REST API (ОГР-2, design.md §7): данные
 * только через API, сессионная кука — credentials: "same-origin".
 *
 * 4.3: доска, карточки (title, priority-индикатор, category, due_date —
 * FR-9); визуальная fast line — задача 5.2 (бейдж fast уже здесь).
 * 4.5: форма создания (7 полей FR-9 + is_fast, title обязателен —
 * UI-валидация до отправки), карточка с полными признаками и
 * комментариями, редактирование (PATCH), удаление с confirm (DELETE),
 * перемещение (POST /{id}/move).
 *
 * Обработка ошибок API: 401 → redirect /login; 422 → показ
 * error.details; прочие (сеть/сервер) → общее сообщение. После каждой
 * мутации — рефреш доски. Обработку 409 «fast line occupied» НЕ делаем
 * (задача 5.1) — сработает общий обработчик ошибок.
 *
 * XSS (ОГР-11 базовый уровень): весь рендер пользовательских данных
 * (title, описание, комментарии, теги, категория) — через
 * createElement + textContent; innerHTML не используется.
 */
(function () {
  "use strict";

  var COLUMNS = ["todo", "in_progress"];
  var STATUSES = ["todo", "in_progress", "done"];
  var currentTaskId = null;

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

  /* --- Ошибки API --- */

  function showBoardError(message) {
    var box = document.getElementById("board-error");
    box.textContent = message;
    box.hidden = false;
  }

  function showFormError(id, message) {
    var box = document.getElementById(id);
    if (box) {
      box.textContent = message;
      box.hidden = false;
    }
  }

  function hideError(id) {
    var box = document.getElementById(id);
    if (box) {
      box.textContent = "";
      box.hidden = true;
    }
  }

  function parseBody(response) {
    /* json() может отклониться асинхронно (не-JSON тело: HTML 502 от
     * nginx и т.п.) — try/catch это не ловит, поэтому .catch. */
    return response.json().catch(function () {
      return null;
    });
  }

  /* Единая обработка ответа API (sdd §3): 401 → /login; 422 →
   * error.details; остальное — общее сообщение. */
  function handleApiError(response, body, onError) {
    if (response.status === 401) {
      window.location.href = "/login";
      return;
    }
    /* Не-JSON тело при полученном HTTP-статусе (HTML-страница 502 и
     * т.п.) — не вводим в заблуждение «сетевой ошибкой». */
    if (!body) {
      onError("Ошибка запроса (HTTP " + response.status + ").");
      return;
    }
    if (response.status === 422) {
      var parts = [];
      if (body.error) {
        parts.push(body.error);
      }
      var details = body.details;
      /* Сервер (tasks.py install_error_handlers) отдает details
       * МАССИВОМ pydantic-ошибок ({loc, msg, type, ...}); формат
       * «объект {поле: [тексты]}» — fallback. */
      if (Array.isArray(details)) {
        details.forEach(function (item) {
          var text =
            (item.loc && item.loc.length ? item.loc.join(".") + ": " : "") +
            (item.msg || "");
          if (text) {
            parts.push(text);
          }
        });
      } else if (details && typeof details === "object") {
        Object.keys(details).forEach(function (key) {
          var value = details[key];
          var text = Array.isArray(value) ? value.join("; ") : String(value);
          parts.push(key + ": " + text);
        });
      }
      onError(parts.length ? parts.join(". ") : "Ошибка валидации (422).");
      return;
    }
    onError("Ошибка запроса (HTTP " + response.status + ").");
  }

  /* Запрос к API: сеть (reject) → общее сообщение; HTTP-ошибка →
   * handleApiError; иначе onOk(тело). */
  function api(path, options, onError, onOk) {
    fetch(path, Object.assign({ credentials: "same-origin" }, options))
      .then(function (response) {
        if (response.ok) {
          if (response.status === 204) {
            onOk(null);
            return;
          }
          return parseBody(response).then(function (body) {
            onOk(body);
          });
        }
        return parseBody(response).then(function (body) {
          handleApiError(response, body, onError);
        });
      })
      .catch(function () {
        onError("Сетевая ошибка. Проверьте соединение и попробуйте еще раз.");
      });
  }

  /* --- Рендер карточки (4.3, fast-бейдж; 4.5: клик → карточка) --- */

  function renderCard(task) {
    var card = el("article", "task-card");
    card.dataset.taskId = task.id;
    card.dataset.fast = task.is_fast ? "true" : "false";

    if (task.priority) {
      card.classList.add("task-priority-" + task.priority);
    }

    var header = el("div", "task-card-header");
    if (task.priority) {
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

    card.addEventListener("click", function () {
      openTaskDetail(task.id);
    });

    return card;
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

  function refreshBoard() {
    api("/api/board", {}, showBoardError, renderBoard);
  }

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

  function openCreateForm() {
    currentTaskId = null;
    document.getElementById("task-form-heading").textContent =
      "Создание задачи";
    document.getElementById("task-form-submit").textContent = "Создать";
    document.getElementById("task-is-fast").closest("label").hidden = false;
    clearTaskForm();
    hideError("task-form-error");
    document.getElementById("task-form-overlay").hidden = false;
    document.getElementById("task-title").focus();
  }

  function openEditForm(task) {
    currentTaskId = task.id;
    document.getElementById("task-form-heading").textContent =
      "Редактирование задачи";
    document.getElementById("task-form-submit").textContent = "Сохранить";
    /* is_fast назначается только при создании (sdd §3.2, ОГР-5). */
    document.getElementById("task-is-fast").closest("label").hidden = true;
    fillTaskForm(task);
    hideError("task-form-error");
    closeTaskDetail();
    document.getElementById("task-form-overlay").hidden = false;
    document.getElementById("task-title").focus();
  }

  function closeTaskForm() {
    document.getElementById("task-form-overlay").hidden = true;
    currentTaskId = null;
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
    if (currentTaskId === null) {
      payload.is_fast = document.getElementById("task-is-fast").checked;
    }
    return payload;
  }

  function submitTaskForm(event) {
    event.preventDefault();
    hideError("task-form-error");

    var payload = collectTaskForm();
    /* UI-валидация до отправки: название обязательно (FR-5). */
    if (!payload.title) {
      showFormError("task-form-error", "Укажите название задачи.");
      return;
    }

    var isCreate = currentTaskId === null;
    var path = isCreate ? "/api/tasks" : "/api/tasks/" + currentTaskId;
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
    currentTaskId = task.id;
    document.getElementById("task-detail-title").textContent = task.title;

    var dl = document.getElementById("task-detail-attrs");
    dl.textContent = "";
    addDetailRow(dl, "Описание", task.description);
    addDetailRow(dl, "Приоритет", task.priority);
    addDetailRow(dl, "Категория", task.category);
    addDetailRow(dl, "Срок", task.due_date);
    addDetailRow(dl, "Теги", (task.tags || []).join(", "));
    addDetailRow(dl, "Fast line", task.is_fast ? "да" : null);
    document.getElementById("task-move-select").value = task.status;
    hideError("task-detail-error");
    hideError("comment-error");
  }

  function renderComments(comments) {
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

  function openTaskDetail(taskId) {
    currentTaskId = taskId;
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

  function closeTaskDetail() {
    document.getElementById("task-detail-overlay").hidden = true;
  }

  function submitComment(event) {
    event.preventDefault();
    hideError("comment-error");

    var body = document.getElementById("comment-body").value.trim();
    /* UI-валидация до отправки: текст обязателен (sdd §3.2, 422). */
    if (!body) {
      showFormError("comment-error", "Комментарий не может быть пустым.");
      return;
    }
    api(
      "/api/tasks/" + currentTaskId + "/comments",
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
        loadComments(currentTaskId);
      }
    );
  }

  /* --- Действия карточки: редактирование, удаление, перемещение --- */

  function deleteCurrentTask() {
    if (currentTaskId === null) {
      return;
    }
    var taskId = currentTaskId;
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
    if (currentTaskId === null) {
      return;
    }
    var status = document.getElementById("task-move-select").value;
    hideError("task-detail-error");
    api(
      "/api/tasks/" + currentTaskId + "/move",
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

  /* --- Инициализация --- */

  document
    .getElementById("create-task-button")
    .addEventListener("click", openCreateForm);

  document
    .getElementById("task-form")
    .addEventListener("submit", submitTaskForm);
  document
    .getElementById("task-form-cancel")
    .addEventListener("click", closeTaskForm);

  document
    .getElementById("comment-form")
    .addEventListener("submit", submitComment);
  document
    .getElementById("task-delete-button")
    .addEventListener("click", deleteCurrentTask);
  document
    .getElementById("task-edit-button")
    .addEventListener("click", function () {
      if (currentTaskId === null) {
        return;
      }
      /* Свежая копия задачи для формы редактирования (GET /api/tasks/{id}). */
      api(
        "/api/tasks/" + currentTaskId,
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

  [document.getElementById("task-form-overlay"),
   document.getElementById("task-detail-overlay")].forEach(function (overlay) {
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) {
        overlay.hidden = true;
      }
    });
  });

  refreshBoard();
})();
