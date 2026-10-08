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
 * Карточка задачи из результатов (BUG-001; FR-10 / CHK-E-17): клик по
 * карточке открывает модалку #task-detail-overlay (разметка в
 * search.html) с полными признаками (GET /api/tasks/{id}) и
 * комментариями (GET /api/tasks/{id}/comments).
 *
 * BUG-014 (r8-polish приемка п.2; BUG-013 закрыт как дубль): рендер
 * окна карточки УНИФИЦИРОВАН с доской — search.js импортирует
 * экспортируемый openTaskDetail/closeTaskDetail из board/task-detail.js
 * (ES-модуль: шапка .task-view-head с бейджами, тело .task-view-body с
 * .attr-grid по мокапу design/polish-ticket-modal.html, люди/чипы,
 * комментарии «автор · дата»). Старый локальный рендер (dl.task-view-
 * attrs-список + h2 без шапки мокапа) выведен из эксплуатации.
 * Подключение search.html: type=module (ОГР-8: свои модули допустимы).
 * Из поиска недоступно «Редактировать» (форма задачи и рефреш столбцов
 * живут на доске): initTaskViewControls здесь НЕ вызывается, кнопку
 * #task-edit-button search.js держит скрытой (guard в openTaskDetail).
 *
 * XSS (ОГР-11): весь рендер пользовательских данных (title, категория,
 * теги, комментарии) — createElement + textContent; innerHTML не
 * используется (и в search.js, и в board/task-detail.js).
 */
"use strict";

import { openTaskDetail, closeTaskDetail } from "./board/task-detail.js";

var mode = "builder"; // активный режим: builder | advanced

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

/* 2.1 add-ui-polish-r8 (FR-93): кнопкам действия «Найти» (id
 * search-builder-submit / search-advanced-submit) проставляется
 * единый класс .btn-action (app.css: токены V3, отступы 8px-сетки).
 * Разметка шаблона не менялась — класс ставится здесь, id сохранены
 * (ОГР-28), обработчики форм не затронуты. */
function applyActionButtonClass() {
  ["search-builder-submit", "search-advanced-submit"].forEach(function (id) {
    var button = document.getElementById(id);
    if (button) {
      button.classList.add("btn-action");
    }
  });
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

  /* searchMode — параметр API рендера (advanced/builder); отображение режима — future P8 */
function renderResults(tasks, searchMode) { // eslint-disable-line no-unused-vars
  var container = document.getElementById("search-results");
  container.textContent = "";
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

  /* 5.2 (FR-45, ОВ-24): строка исполнителя/создателя в КАЖДОЙ карточке
   * выдачи. assigned пустой (null/нет поля) → курсивом «Unassigned». */
  card.appendChild(renderUsersRow(task));

  /* BUG-001 (FR-10 / CHK-E-17): клик по карточке открывает карточку
   * задачи — рендер единый с доской (BUG-014): board/task-detail.js
   * openTaskDetail через openSearchTaskDetail ниже (guard кнопки
   * «Редактировать»). */
  card.addEventListener("click", function () {
    openSearchTaskDetail(task.id);
  });

  return card;
}

/* 5.2 (FR-45, ОВ-24): строка «Исполнитель: … · Создатель: …» карточки
 * результата. assigned без значения → <em>Unassigned</em> (курсив).
 * textContent — не innerHTML (XSS, ОГР-11). */
function renderUsersRow(task) {
  var row = el("div", "task-card-users");
  row.appendChild(el("span", "task-user-term", "Исполнитель: "));
  if (task.assigned) {
    row.appendChild(el("span", "task-user-assigned", task.assigned));
  } else {
    row.appendChild(el("em", "task-user-unassigned", "Unassigned"));
  }
  row.appendChild(el("span", "task-user-sep", " · "));
  row.appendChild(el("span", "task-user-term", "Создатель: "));
  row.appendChild(el("span", "task-user-creator", task.creator || "—"));
  return row;
}

/* --- Карточка задачи из результатов (BUG-001; FR-9/FR-10; BUG-014) ---
 *
 * Рендер окна карточки — board/task-detail.js (импорт openTaskDetail
 * выше): шапка .task-view-head + бейджи, тело .task-view-body с
 * .attr-grid по мокапу polish-ticket-modal.html, dl#task-detail-attrs,
 * комментарии, футер. Локальный старый рендер (renderTaskDetail/
 * renderComments/loadComments/addDetailRow/addUserRow этого файла)
 * выведен из эксплуатации и удален (BUG-014).
 *
 * Из поиска «Редактировать» не поддержан (форма задачи живет на
 * доске) — кнопка #task-edit-button держится скрытой (guard ниже);
 * закрытие/Escape/подложка — через импортированный closeTaskDetail.
 */

function openSearchTaskDetail(taskId) {
  if (typeof taskId !== "number" || !isFinite(taskId)) {
    return;
  }
  /* Guard: разметка окна дословно досочная (включая кнопку
   * «Редактировать»), но формы задачи на странице поиска нет —
   * действие недоступно, кнопка не показывается. */
  var editButton = document.getElementById("task-edit-button");
  if (editButton) {
    editButton.hidden = true;
  }
  openTaskDetail(taskId);
}

/* Закрытие Escape (4.1, сценарий 5 дельты board): поиск — отдельная
 * страница, форма задачи здесь не существует; закрытие — тот же
 * closeTaskDetail доски (возврат фокуса на карточку-триггер).
 * Escape-обработчик task-detail.js (initTaskViewControls) здесь не
 * подписан (он тянет форму доски) — на /search закрытие
 * крестик/«Закрыть»/подложка/Escape подписывает search.js ниже. */
document.addEventListener("keydown", function (event) {
  if (event.key === "Escape") {
    var overlay = document.getElementById("task-detail-overlay");
    if (overlay && !overlay.hidden) {
      closeTaskDetail();
    }
  }
});

/* Подписки закрытия окна на /search (аналог закрытий
 * initTaskViewControls, без «Редактировать» — см. шапку файла). */
document
  .getElementById("task-view-close")
  .addEventListener("click", closeTaskDetail);

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
  /* 5.2 (FR-46, ОВ-24): assigned = login | none («без исполнителя»). */
  var assigned = document.getElementById("search-assigned").value;
  if (assigned) {
    params.append("assigned", assigned);
  }
  var creator = document.getElementById("search-creator").value;
  if (creator) {
    params.append("creator", creator);
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
  /* 5.2 (FR-46): assigned/creator — грамматика advanced (= и IS NULL).
   * «Без исполнителя» (none) → assigned IS NULL (ОВ-24). Логин — в
   * кавычках (кавычка внутри логина не встречается; _quote на сервере
   * экранирует, здесь достаточно простой обертки — как для тегов). */
  var assigned = document.getElementById("search-assigned").value;
  if (assigned === "none") {
    parts.push("assigned IS NULL");
  } else if (assigned) {
    parts.push('assigned = "' + assigned + '"');
  }
  var creator = document.getElementById("search-creator").value;
  if (creator) {
    parts.push('creator = "' + creator + '"');
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

/* --- Подсказки (Релиз 1, 1.3 / P4) --- */

/* --- Селект категории фильтра из справочника (3.1; FR-30/DEF-001) --- */

/* GET /api/categories → {"categories": [{id, name}, ...]} (sdd r2
 * §3.1) — тот же источник, что у селекта формы задачи. Полная
 * перезагрузка опций: список = ровно фактическое содержимое
 * справочника, никаких статических/захардкоженных значений. Пустое
 * значение «любая» — признак «фильтр не задан», в справочник не
 * входит. Значения — только через textContent (XSS, ОГР-11).
 * Сбой загрузки фильтру не мешает: остается только «любая»
 * (пустой фильтр категории = все задачи). */
function loadCategoryFilterOptions() {
  fetch("/api/categories", { credentials: "same-origin" })
    .then(function (response) {
      if (!response.ok) {
        return null;
      }
      return response.json().catch(function () {
        return null;
      });
    })
    .then(function (body) {
      if (!body || !Array.isArray(body.categories)) {
        return;
      }
      var select = document.getElementById("search-category");
      select.textContent = "";
      var any = el("option", null, "любая");
      any.value = "";
      select.appendChild(any);
      body.categories.forEach(function (item) {
        var option = el("option", null, item.name);
        option.value = item.name;
        select.appendChild(option);
      });
    })
    .catch(function () {
      /* Справочник недоступен — фильтр по категории просто не задан. */
    });
}

/* --- Подсказки тегов (Релиз 1, 1.3 / P4) --- */

/* GET /api/suggestions → {"suggestions": [...]} — множество (set,
 * без дублей, отсортировано) из объединения тегов и категорий
 * существующих задач (уточнение Заказчика). Заполняет datalist
 * #tag-hints, привязанный к полю «Теги» конструктора (поле категории —
 * select из справочника, 3.1). Сбой загрузки подсказки поиску не
 * мешает: остается пустой datalist.
 * DEF-001 (FR-35, 5.2): 401 (потерянная сессия — например, Secure-кука
 * не сохранена на не-trustworthy origin) больше НЕ тишина — показываем
 * неблокирующее предупреждение в #search-error: поиск доступен и без
 * подсказок, но пользователь должен видеть причину пустого списка.
 * Прочие сбои (сеть, 5xx) — прежнее поведение: тихо, без предупреждения. */
function loadSuggestions() {
  fetch("/api/suggestions", { credentials: "same-origin" })
    .then(function (response) {
      if (response.status === 401) {
        showError(
          "Подсказки недоступны: сессия не активна. Откройте сайт по адресу https://194.58.34.122:10443 и войдите снова."
        );
        return null;
      }
      if (!response.ok) {
        return null;
      }
      return response.json().catch(function () {
        return null;
      });
    })
    .then(function (body) {
      if (!body || !Array.isArray(body.suggestions)) {
        return;
      }
      var datalist = document.getElementById("tag-hints");
      /* set-семантика на клиенте тоже: дубли из ответа в option не пишем. */
      var seen = {};
      body.suggestions.forEach(function (value) {
        if (typeof value !== "string" || seen[value]) {
          return;
        }
        seen[value] = true;
        datalist.appendChild(el("option", null, value));
      });
    })
    .catch(function () {
      /* Подсказки — необязательное украшение: тихо остаемся без них. */
    });
}

/* --- Подсказки assigned/creator (5.2, FR-46) --- */

/* GET /api/suggestions/users → {"users": [...]} — уникальные логины
 * из столбцов creator/assigned существующих задач (JOIN tasks→users;
 * механизм FR-35/DEF-001 — «значения из данных», не статические
 * списки). Заполняет select'ы «Исполнитель» и «Создатель» конструктора:
 * у assigned статические опции «любой» (пусто = фильтр не задан) и
 * «без исполнителя» (none → assigned IS NULL, ОВ-24) сохраняются,
 * логины дописываются после них; у creator — «любой» + логины.
 * Сбой загрузки фильтру не мешает: select'ы остаются со статическими
 * опциями (пустой фильтр = все задачи). textContent — XSS (ОГР-11). */
function loadUserSuggestions() {
  fetch("/api/suggestions/users", { credentials: "same-origin" })
    .then(function (response) {
      if (!response.ok) {
        return null;
      }
      return response.json().catch(function () {
        return null;
      });
    })
    .then(function (body) {
      if (!body || !Array.isArray(body.users)) {
        return;
      }
      var assigned = document.getElementById("search-assigned");
      var creator = document.getElementById("search-creator");
      var seen = {};
      body.users.forEach(function (login) {
        if (typeof login !== "string" || !login || seen[login]) {
          return;
        }
        seen[login] = true;
        var optAssigned = el("option", null, login);
        optAssigned.value = login;
        assigned.appendChild(optAssigned);
        var optCreator = el("option", null, login);
        optCreator.value = login;
        creator.appendChild(optCreator);
      });
    })
    .catch(function () {
      /* Подсказки — необязательное украшение: тихо остаемся без них. */
    });
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
document
  .getElementById("task-detail-close")
  .addEventListener("click", closeTaskDetail);
/* Клик по подложке модалки (вне .modal) — закрыть (паттерн board.js). */
document
  .getElementById("task-detail-overlay")
  .addEventListener("click", function (event) {
    if (event.target === event.currentTarget) {
      closeTaskDetail();
    }
  });

/* Подсказки тегов/категорий (Релиз 1, 1.3 / P4): загрузка множества
 * при открытии вкладки поиска. Селект категории фильтра — из
 * справочника (3.1, FR-30). loadSuggestions идет последней: ее
 * предупреждение при 401 (DEF-001, 5.2) не затирается 200-ответом
 * справочника, а общий порядок сети не меняется. */
loadCategoryFilterOptions();
loadSuggestions();
loadUserSuggestions();
/* FR-93: класс кнопки действия — после DOM (модульный скрипт
 * deferred: исполняется после разбора разметки). */
applyActionButtonClass();
