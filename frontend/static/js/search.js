/* Поиск (tasks.md 7.3; FR-10, FR-11, FR-12; sdd.md §3.5). Два режима:
 *
 * 1) Конструктор (FR-11): submit → GET /api/search с query-параметрами
 *    priority, category, tag (повторяемый), due_before, due_after,
 *    archived (sdd §3.5; пустая форма = пустой фильтр = все задачи).
 * 2) Advanced (FR-12): переключатель → текстовое поле с SQL-подобным
 *    фильтром → POST /api/search/advanced {"query": ...}; 200 →
 *    normalized_query показывается под полем (синхронизация режимов);
 *    переключение конструктор → advanced переносит собранный фильтр
 *    текстом в поле (спека search, «Переключение конструктора в
 *    advanced»). Переключение режимов НЕ трогает результаты последнего
 *    поиска.
 *
 * Обработка ошибок API (паттерн board.js): 401 → redirect /login;
 * 400 → текст body.error КАК ЕСТЬ (filter syntax: ... — sdd §3.5);
 * 422 → error + details; сеть/сервер → общее сообщение. Пустой
 * результат → «Ничего не найдено» (не ошибка).
 *
 * XSS (ОГР-11): весь рендер пользовательских данных (title, категория,
 * теги) — createElement + textContent; innerHTML не используется.
 */
(function () {
  "use strict";

  var mode = "builder"; // активный режим: builder | advanced
  var lastSearchMode = null; // каким режимом получены текущие результаты

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

  /* --- Ошибки и сообщения --- */

  function showError(message) {
    var box = document.getElementById("search-error");
    box.textContent = message; // textContent — не innerHTML (XSS)
    box.hidden = false;
  }

  function hideError() {
    var box = document.getElementById("search-error");
    box.textContent = "";
    box.hidden = true;
  }

  function parseBody(response) {
    /* json() может отклониться асинхронно (не-JSON тело) — .catch. */
    return response.json().catch(function () {
      return null;
    });
  }

  /* Единая обработка ответа API: 401 → /login; 400 → текст ошибки как
   * есть (filter syntax: ..., sdd §3.5); 422 → error + details. */
  function handleApiError(response, body, onError) {
    if (response.status === 401) {
      window.location.href = "/login";
      return;
    }
    if (!body) {
      onError("Ошибка запроса (HTTP " + response.status + ").");
      return;
    }
    if (response.status === 400) {
      /* Ошибка синтаксиса фильтра — показываем текст сервера как есть. */
      onError(body.error || "Ошибка запроса (HTTP 400).");
      return;
    }
    if (response.status === 422) {
      var parts = [];
      if (body.error) {
        parts.push(body.error);
      }
      var details = body.details;
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

  function api(path, options, onError, onOk) {
    fetch(path, Object.assign({ credentials: "same-origin" }, options))
      .then(function (response) {
        if (response.ok) {
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

  /* --- Рендер результатов (общий для обоих режимов; XSS-safe) --- */

  function renderResults(tasks, searchMode) {
    var container = document.getElementById("search-results");
    container.textContent = "";
    lastSearchMode = searchMode;
    if (!tasks || !tasks.length) {
      container.appendChild(
        el("p", "search-empty", "Ничего не найдено")
      );
      return;
    }
    tasks.forEach(function (task) {
      container.appendChild(renderCard(task));
    });
  }

  function renderCard(task) {
    var card = el("article", "task-card");

    var header = el("div", "task-card-header");
    if (task.priority) {
      header.appendChild(
        el("span", "task-priority-badge priority-" + task.priority, task.priority)
      );
    }
    /* FR-10/6.2: признак «архивная» — бейдж при archived_at IS NOT NULL;
     * текст статический — пользовательских данных нет (XSS-safe). */
    if (task.archived_at) {
      header.appendChild(el("span", "task-archive-badge", "Архивная"));
    }
    card.appendChild(header);

    card.appendChild(el("h3", "task-card-title", task.title)); // textContent

    var meta = el("div", "task-card-meta");
    if (task.category) {
      meta.appendChild(el("span", "task-category", task.category));
    }
    if (task.due_date) {
      meta.appendChild(el("span", "task-due-date", "до " + task.due_date));
    }
    (task.tags || []).forEach(function (tag) {
      meta.appendChild(el("span", "task-tag", tag)); // textContent
    });
    if (meta.childNodes.length) {
      card.appendChild(meta);
    }
    return card;
  }

  /* --- Режим 1: конструктор → GET /api/search --- */

  function splitTags(raw) {
    return raw
      .split(",")
      .map(function (tag) {
        return tag.trim();
      })
      .filter(function (tag) {
        return tag.length > 0;
      });
  }

  function builderParams() {
    var params = new URLSearchParams();
    var priority = document.getElementById("search-priority").value;
    if (priority) {
      params.append("priority", priority);
    }
    var category = document.getElementById("search-category").value.trim();
    if (category) {
      params.append("category", category);
    }
    splitTags(document.getElementById("search-tags").value).forEach(function (
      tag
    ) {
      params.append("tag", tag); // повторяемый параметр (sdd §3.5)
    });
    var dueBefore = document.getElementById("search-due-before").value;
    if (dueBefore) {
      params.append("due_before", dueBefore);
    }
    var dueAfter = document.getElementById("search-due-after").value;
    if (dueAfter) {
      params.append("due_after", dueAfter);
    }
    var archived = document.getElementById("search-archived").value;
    if (archived) {
      params.append("archived", archived); // пусто = all (дефолт сервера)
    }
    return params;
  }

  /* Текст фильтра из полей конструктора — для переноса в advanced при
   * переключении (грамматика design.md §6 / build() 7.2). */
  function buildFilterText() {
    var parts = [];
    var priority = document.getElementById("search-priority").value;
    if (priority) {
      parts.push('priority = "' + priority + '"');
    }
    var category = document.getElementById("search-category").value.trim();
    if (category) {
      parts.push('category = "' + category + '"');
    }
    var tags = splitTags(document.getElementById("search-tags").value);
    if (tags.length) {
      parts.push(
        "tag IN (" +
          tags
            .map(function (tag) {
              return '"' + tag + '"';
            })
            .join(", ") +
          ")"
      );
    }
    var dueAfter = document.getElementById("search-due-after").value;
    if (dueAfter) {
      parts.push("due >= " + dueAfter);
    }
    var dueBefore = document.getElementById("search-due-before").value;
    if (dueBefore) {
      parts.push("due <= " + dueBefore);
    }
    var archived = document.getElementById("search-archived").value;
    if (archived) {
      parts.push("archived = " + archived);
    }
    return parts.join(" AND ");
  }

  function submitBuilder(event) {
    event.preventDefault();
    hideError();
    var params = builderParams();
    var query = params.toString();
    api(query ? "/api/search?" + query : "/api/search", {}, showError, function (
      body
    ) {
      renderResults(body && body.results, "builder");
    });
  }

  /* --- Режим 2: advanced → POST /api/search/advanced --- */

  function showNormalized(text) {
    var box = document.getElementById("search-advanced-normalized");
    if (!text) {
      box.hidden = true;
      box.textContent = "";
      return;
    }
    box.textContent = "Нормализованный фильтр: " + text; // textContent
    box.hidden = false;
  }

  function submitAdvanced(event) {
    event.preventDefault();
    hideError();
    var query = document.getElementById("search-advanced-query").value;
    api(
      "/api/search/advanced",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query }),
      },
      showError,
      function (body) {
        /* 200: normalized_query — сериализация распарсенного фильтра
         * (sdd §3.5); показываем и оставляем в поле для правки. */
        showNormalized(body && body.normalized_query);
        if (body && body.normalized_query) {
          document.getElementById("search-advanced-query").value =
            body.normalized_query;
        }
        renderResults(body && body.results, "advanced");
      }
    );
  }

  /* --- Переключение режимов (FR-12) --- */

  function setMode(next) {
    if (next === mode) {
      return;
    }
    mode = next;
    var isBuilder = mode === "builder";
    document.getElementById("search-builder").hidden = !isBuilder;
    document.getElementById("search-advanced").hidden = isBuilder;
    document.getElementById("search-mode-builder").classList.toggle("active", isBuilder);
    document.getElementById("search-mode-builder").setAttribute("aria-pressed", String(isBuilder));
    document.getElementById("search-mode-advanced").classList.toggle("active", !isBuilder);
    document.getElementById("search-mode-advanced").setAttribute("aria-pressed", String(!isBuilder));
    if (!isBuilder) {
      /* Сценарий «Переключение конструктора в advanced»: текстовое поле
       * показывает текущий фильтр конструктора (если он задан).
       * Ручная правка поля при этом не затирается, если конструктор
       * пуст (поле остается как есть). */
      var built = buildFilterText();
      if (built) {
        document.getElementById("search-advanced-query").value = built;
        showNormalized(built);
      }
    }
    /* Результаты последнего поиска НЕ очищаются (задание 7.3, п.4). */
  }

  /* --- Инициализация --- */

  document
    .getElementById("search-builder-form")
    .addEventListener("submit", submitBuilder);
  document
    .getElementById("search-advanced-form")
    .addEventListener("submit", submitAdvanced);
  document
    .getElementById("search-mode-builder")
    .addEventListener("click", function () {
      setMode("builder");
    });
  document
    .getElementById("search-mode-advanced")
    .addEventListener("click", function () {
      setMode("advanced");
    });
})();
