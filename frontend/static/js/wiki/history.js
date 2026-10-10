/* История версий + откат (tasks.md 3.4 add-wiki; FR-112, FR-113; design
 * §6–§7). Строго по утвержденному мокапу design/wiki-history.html.
 *
 * ES-модуль роута /wiki/{id}/history (frontend/app/pages.py, задача 3.4).
 * Тот же шаблон wiki.html: в режиме истории (history_mode) контейнеры
 * #wiki-history внутри .wiki-content заполняет этот модуль.
 *
 * API (design.md §3, backend/app/wiki.py):
 * - GET  /api/wiki/pages/{id}            — страница (title, breadcrumb);
 * - GET  /api/wiki/pages/{id}/versions   — список версий от НОВЫХ к
 *   старым {id, author_id, created_at}; авторов резолвит карта из
 *   GET /api/users (один запрос, patтерн tooltip'ов доски — состав
 *   пользователей данные, не код);
 * - GET  /api/wiki/pages/{id}/versions/{vid} — контент версии
 *   (read-only источник просмотра);
 * - POST /api/wiki/pages/{id}/revert/{vid} — откат: контент версии
 *   становится текущим, создается НОВАЯ версия (автор — исполнитель),
 *   история не переписывается → 200 {new_version_id}.
 *
 * Поведение по мокапу:
 * - двухколонный layout .history-layout: список слева, просмотр справа;
 *   ≤880px складывается (CSS, media в wiki.css);
 * - текущая (первая в списке) версия — пилюля «текущая» (olive), кнопки
 *   «Откатить» у нее НЕТ; у прочих — «Смотреть» + «Откатить»;
 * - клик «Смотреть»/по строке версии → read-only просмотр (плашка
 *   «только чтение», контент как есть — innerHTML сюда не попадает:
 *   контент версии вставляется через DOMParser-санитизацию в набор
 *   элементов, см. insertSanitized);
 * - «Откатить» → диалог подтверждения с формулировкой мокапа («Откат
 *   будет записан как новая версия — история не переписывается»),
 *   Esc/«Отмена» — выход, «Откатить» — POST → success-баннер +
 *   обновление списка (в истории появляется новая версия);
 * - 401 (протухшая сессия) → redirect /login (паттерн search.js).
 *
 * XSS-дисциплина (ОГР-11, паттерн board/search/gallery): авторы, даты,
 * заголовки — createElement+textContent; контент версии — не innerHTML:
 * строка парсится DOMParser'ом и в дерево переносятся только узлы
 * whitelist-тегов с whitelist-атрибутами (сервер уже санитизирует на
 * записи §4 — здесь страховочный клиентский фильтр).
 */

"use strict";

/* ---------------------------------------------------------------------
 * Состояние модуля
 * ------------------------------------------------------------------- */

var state = {
  pageId: null,        // числовой id страницы (data-page-id каркаса)
  versions: [],        // список от новых к старым (как отдал API)
  authors: {},         // user_id → login (из GET /api/users)
  selectedVersionId: null,
  revertTarget: null,  // версия, подтверждаемая в диалоге
};

/* ---------------------------------------------------------------------
 * Утилиты (паттерн search.js/gallery.js)
 * ------------------------------------------------------------------- */

function el(tag, className, text) {
  var node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== undefined && text !== null) {
    node.textContent = text;
  }
  return node;
}

function parseBody(response) {
  /* json() может отклониться асинхронно (не-JSON тело 503 и т.п.). */
  return response.json().catch(function () {
    return null;
  });
}

function showBox(node, message) {
  node.textContent = message; // textContent — не innerHTML (XSS)
  node.hidden = false;
}

/* ISO «2026-10-02T14:32:00+03:00» → «02.10.2026 14:32» (мокап:
 * «02.10.2026 14:32»). Неразобранная дата — как вернул сервер. */
function formatDateTime(iso) {
  var parsed = new Date(iso);
  if (isNaN(parsed.getTime())) {
    return iso;
  }
  var pad = function (n) {
    return String(n).padStart(2, "0");
  };
  return (
    pad(parsed.getDate()) +
    "." +
    pad(parsed.getMonth() + 1) +
    "." +
    parsed.getFullYear() +
    " " +
    pad(parsed.getHours()) +
    ":" +
    pad(parsed.getMinutes())
  );
}

/* Единая обработка ошибок API (паттерн search.js): 401 → /login;
 * прочее — текст error/details или общий статус. */
function handleApiError(response, body, onError) {
  if (response.status === 401) {
    window.location.href = "/login";
    return;
  }
  if (body && typeof body.error === "string" && body.error) {
    onError(body.error);
    return;
  }
  if (body && typeof body.detail === "string" && body.detail) {
    onError(body.detail);
    return;
  }
  onError("Ошибка запроса (HTTP " + response.status + ").");
}

function api(path, options, onError, onOk) {
  fetch(path, Object.assign({ credentials: "same-origin" }, options))
    .then(function (response) {
      var done = function (body) {
        if (response.ok) {
          onOk(body);
        } else {
          handleApiError(response, body, onError);
        }
      };
      if (response.status === 204) {
        done(null);
        return;
      }
      parseBody(response).then(done);
    })
    .catch(function () {
      onError("Сетевая ошибка. Проверьте соединение и попробуйте еще раз.");
    });
}

/* Страховочный клиентский фильтр контента версии (сервер санитизирует
 * на записи §4; здесь — защита от «грязных» данных старых версий).
 * Паттерн: DOMParser → перенос в живое дерево только whitelist-тегов с
 * whitelist-атрибутами; script/style — с содержимым, прочие запрещенные
 * — разворот (дети остаются). Пользовательский HTML через innerHTML НЕ
 * вставляется — parser сам изолированный документ. */
var ALLOWED_TAGS = [
  "h1", "h2", "h3", "p", "br", "b", "strong", "i", "em", "u",
  "ul", "ol", "li", "blockquote", "pre", "code", "a", "img",
  "table", "thead", "tbody", "tr", "th", "td", "div", "span",
];
var ALLOWED_ATTRS = {
  a: ["href", "title"],
  img: ["src", "alt"],
  td: ["colspan", "rowspan"],
  th: ["colspan", "rowspan"],
};

function insertSanitized(html, target) {
  var doc = new DOMParser().parseFromString(html, "text/html");
  var appendClean = function (source, destination) {
    Array.prototype.forEach.call(source.childNodes, function (child) {
      if (child.nodeType === Node.TEXT_NODE) {
        destination.appendChild(document.createTextNode(child.nodeValue));
        return;
      }
      if (child.nodeType !== Node.ELEMENT_NODE) {
        return;
      }
      var tag = child.tagName.toLowerCase();
      if (tag === "script" || tag === "style") {
        return; // запрещенные с содержимым — целиком
      }
      if (ALLOWED_TAGS.indexOf(tag) === -1) {
        appendClean(child, destination); // разворот: содержимое остается
        return;
      }
      var clone = document.createElement(tag);
      (ALLOWED_ATTRS[tag] || []).forEach(function (attr) {
        var value = child.getAttribute(attr);
        var isUrlAttr =
          (tag === "a" && attr === "href") || (tag === "img" && attr === "src");
        if (value === null || (isUrlAttr && /^(javascript|data):/i.test(value.trim()))) {
          return;
        }
        clone.setAttribute(attr, value);
      });
      appendClean(child, clone);
      destination.appendChild(clone);
    });
  };
  appendClean(doc.body, target);
}

/* ---------------------------------------------------------------------
 * Диалог подтверждения отката (мокап: .confirm-backdrop > .confirm)
 * ------------------------------------------------------------------- */

function openConfirmDialog(version, onConfirm) {
  var backdrop = el("div", "confirm-backdrop");
  backdrop.setAttribute("role", "presentation");

  var dialog = el("div", "confirm");
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-labelledby", "wiki-revert-title");

  var title = el("h2", null, "Откатить к версии V" + version.seq + "?");
  title.id = "wiki-revert-title";
  dialog.appendChild(title);

  var text = el(
    "p",
    null,
    "Статья получит содержимое версии V" + version.seq +
      " (" + formatDateTime(version.created_at) + ", " +
      authorName(version) + "). Откат будет записан как новая версия — история не переписывается."
  );
  dialog.appendChild(text);

  var actions = el("div", "confirm-actions");
  var cancel = el("button", "btn btn-secondary", "Отмена");
  cancel.type = "button";
  var confirmBtn = el("button", "btn btn-primary", "Откатить");
  confirmBtn.type = "button";
  actions.appendChild(cancel);
  actions.appendChild(confirmBtn);
  dialog.appendChild(actions);

  backdrop.appendChild(dialog);
  document.body.appendChild(backdrop);

  var close = function () {
    document.removeEventListener("keydown", onKey);
    backdrop.remove();
    confirmBtn.removeEventListener("click", onConfirmClick);
    cancel.removeEventListener("click", close);
  };
  var onConfirmClick = function () {
    close();
    onConfirm();
  };
  var onKey = function (event) {
    if (event.key === "Escape") {
      close();
    }
  };
  confirmBtn.addEventListener("click", onConfirmClick);
  cancel.addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  confirmBtn.focus();
}

/* ---------------------------------------------------------------------
 * Рендер списка версий (мокап: ul.versions > li.version-item)
 * ------------------------------------------------------------------- */

function authorName(version) {
  var login = state.authors[version.author_id];
  return login ? login : "user #" + version.author_id;
}

function renderVersionsList(versionsBody) {
  versionsBody.textContent = "";

  if (!state.versions.length) {
    versionsBody.appendChild(
      el("p", "history-empty", "У страницы пока нет версий")
    );
    return;
  }

  var list = el("ul", "versions");
  list.setAttribute("aria-label", "Версии страницы");

  state.versions.forEach(function (version, index) {
    var item = el("li", "version-item");
    if (version.id === state.selectedVersionId) {
      item.classList.add("selected");
    }
    item.dataset.versionId = String(version.id);

    var main = el("div", "version-main");
    var head = el("div", "version-head");
    head.appendChild(el("span", "version-num", "V" + version.seq));
    if (index === 0) {
      // Текущая (последняя) версия — пилюля, кнопки «Откатить» нет (мокап).
      head.appendChild(el("span", "pill-current", "текущая"));
    }
    main.appendChild(head);
    main.appendChild(
      el(
        "div",
        "version-meta",
        authorName(version) + " · " + formatDateTime(version.created_at)
      )
    );
    item.appendChild(main);

    var viewBtn = el("button", "btn btn-secondary version-view-link", "Смотреть");
    viewBtn.type = "button";
    if (version.id === state.selectedVersionId) {
      viewBtn.setAttribute("aria-pressed", "true");
    }
    viewBtn.addEventListener("click", function () {
      selectVersion(version.id, versionsBody);
    });
    item.appendChild(viewBtn);

    if (index !== 0) {
      var revertBtn = el("button", "btn btn-secondary", "Откатить");
      revertBtn.type = "button";
      revertBtn.addEventListener("click", function () {
        state.revertTarget = version;
        openConfirmDialog(version, function () {
          performRevert(version, versionsBody);
        });
      });
      item.appendChild(revertBtn);
    }

    list.appendChild(item);
  });

  versionsBody.appendChild(list);
}

/* ---------------------------------------------------------------------
 * Просмотр версии (read-only; мокап: .version-view + .readonly-banner)
 * ------------------------------------------------------------------- */

var RO_ICON =
  '<svg class="ro-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" stroke-width="2"/></svg>';

function selectVersion(versionId, versionsBody) {
  state.selectedVersionId = versionId;
  renderVersionsList(versionsBody);
  var viewPane = document.getElementById("wiki-history-view");

  var version = null;
  state.versions.forEach(function (item) {
    if (item.id === versionId) {
      version = item;
    }
  });
  if (!version) {
    return;
  }

  viewPane.textContent = "";
  viewPane.appendChild(el("p", "history-loading", "Загрузка версии…"));

  api(
    "/api/wiki/pages/" + state.pageId + "/versions/" + versionId,
    { method: "GET" },
    function (message) {
      viewPane.textContent = "";
      viewPane.appendChild(el("p", "form-error", message));
    },
    function (body) {
      viewPane.textContent = "";

      var view = el("div", "version-view");
      var banner = el("div", "readonly-banner");
      banner.insertAdjacentHTML("afterbegin", RO_ICON); // статический SVG, не пользовательские данные
      banner.appendChild(
        document.createTextNode(
          "Просмотр версии V" + version.seq +
            " от " + formatDateTime(version.created_at) +
            " (" + authorName(version) + ") — только чтение, правки недоступны"
        )
      );
      view.appendChild(banner);

      var bodyNode = el("div", "version-body");
      insertSanitized(body.content, bodyNode);
      view.appendChild(bodyNode);

      viewPane.appendChild(view);
    }
  );
}

/* ---------------------------------------------------------------------
 * Откат (POST revert → success-баннер + обновление списка)
 * ------------------------------------------------------------------- */

function performRevert(version, versionsBody) {
  var banner = document.getElementById("wiki-history-banner");
  banner.hidden = true;

  api(
    "/api/wiki/pages/" + state.pageId + "/revert/" + version.id,
    { method: "POST" },
    function (message) {
      showBox(banner, message);
      banner.classList.remove("success-banner");
      banner.classList.add("error-banner");
    },
    function (body) {
      // Обновление списка: revert = НОВАЯ версия — она вверху, «текущая».
      loadVersions(versionsBody, function () {
        state.selectedVersionId = body.new_version_id;
        renderVersionsList(versionsBody);
        selectVersion(body.new_version_id, versionsBody);
      });
      showBox(
        banner,
        "Откат выполнен: создана версия V" + versionSeqOf(body.new_version_id) +
          " (содержимое V" + version.seq + "). Ранние версии остались без изменений."
      );
      banner.classList.remove("error-banner");
      banner.classList.add("success-banner");
    }
  );
}

function versionSeqOf(versionId) {
  var seq = "";
  state.versions.forEach(function (item) {
    if (item.id === versionId) {
      seq = item.seq;
    }
  });
  return seq;
}

/* ---------------------------------------------------------------------
 * Загрузка данных
 * ------------------------------------------------------------------- */

function loadVersions(versionsBody, onReady) {
  api(
    "/api/wiki/pages/" + state.pageId + "/versions",
    { method: "GET" },
    function (message) {
      versionsBody.textContent = "";
      versionsBody.appendChild(el("p", "form-error", message));
    },
    function (body) {
      state.versions = body.versions || [];
      // Номер V{n} — позиция от старых к новым: последняя версия = V1.
      var total = state.versions.length;
      state.versions.forEach(function (version, index) {
        version.seq = total - index;
      });
      if (state.selectedVersionId === null && state.versions.length) {
        state.selectedVersionId = state.versions[0].id;
      }
      if (onReady) {
        onReady();
      } else {
        renderVersionsList(versionsBody);
        if (state.selectedVersionId !== null) {
          selectVersion(state.selectedVersionId, versionsBody);
        }
      }
    }
  );
}

/* ---------------------------------------------------------------------
 * Инициализация
 * ------------------------------------------------------------------- */

function init() {
  var container = document.getElementById("wiki-history");
  if (!container) {
    return; // не режим истории (/wiki, /wiki/{id}) — модуль не активен
  }
  var layout = container.closest(".wiki-layout");
  var pageIdRaw =
    layout && layout.dataset && layout.dataset.pageId
      ? layout.dataset.pageId
      : "";
  if (!/^\d+$/.test(pageIdRaw)) {
    showBox(container, "Страница не найдена");
    return;
  }
  state.pageId = pageIdRaw;

  container.textContent = "";

  var errorBox = el("p", "form-error");
  errorBox.id = "wiki-history-error";
  errorBox.hidden = true;
  container.appendChild(errorBox);

  var banner = el("p");
  banner.id = "wiki-history-banner";
  banner.setAttribute("role", "status");
  banner.hidden = true;
  container.appendChild(banner);

  var title = el("h1", null, "История версий");
  container.appendChild(title);

  var subtitle = el("p", "history-subtitle");
  subtitle.id = "wiki-history-subtitle";
  container.appendChild(subtitle);

  var layoutDiv = el("div", "history-layout");

  var versionsBody = el("div");
  versionsBody.id = "wiki-history-versions";
  versionsBody.appendChild(el("p", "history-loading", "Загрузка…"));
  layoutDiv.appendChild(versionsBody);

  var viewPane = el("div");
  viewPane.id = "wiki-history-view";
  layoutDiv.appendChild(viewPane);

  container.appendChild(layoutDiv);

  /* Breadcrumb «статья → История» (мокап wiki-history: ol.breadcrumb,
     текущая — «История версий» без ссылки; DV-10 review-001) */
  var nav = el("nav");
  nav.setAttribute("aria-label", "Иерархия страниц");
  var breadcrumb = el("ol", "breadcrumb");
  var crumb = el("li");
  var crumbLink = el("a", null, "Статья");
  crumbLink.href = "/wiki/" + state.pageId;
  crumb.appendChild(crumbLink);
  breadcrumb.appendChild(crumb);
  var sep = el("li", "crumb-sep", "/");
  sep.setAttribute("aria-hidden", "true");
  breadcrumb.appendChild(sep);
  var current = el("li", null, "История версий");
  current.setAttribute("aria-current", "page");
  breadcrumb.appendChild(current);
  nav.appendChild(breadcrumb);
  container.insertBefore(nav, container.firstChild);

  // Заголовок статьи приходит из GET страницы — breadcrumb обновляется там же.

  // Автор и заголовок страницы — параллельно: версии + справочник логинов.
  api(
    "/api/wiki/pages/" + state.pageId,
    { method: "GET" },
    function (message) {
      // 404 несуществующей страницы — сообщение вместо пустой панели.
      subtitle.textContent = "";
      showBox(errorBox, message === "not found" ? "Страница не найдена" : message);
    },
    function (page) {
      document.title = "История — " + page.title + " · ekotov-wiki";
      // Название статьи в breadcrumb (мокап: «… / Чек: крепеж и уголки»).
      var crumbLink = container.querySelector(".breadcrumb a");
      if (crumbLink && page.title) {
        crumbLink.textContent = page.title;
      }
    }
  );

  // Порядок: авторы резолвятся до рендера списка (логин в строке версии).
  fetch("/api/users", { credentials: "same-origin" })
    .then(function (response) {
      return response.ok ? response.json() : null;
    })
    .then(function (body) {
      if (body && Array.isArray(body.users)) {
        body.users.forEach(function (user) {
          state.authors[user.id] = user.login;
        });
      }
    })
    .catch(function () {
      /* fallback «user #id» — историю не ломает */
    })
    .then(function () {
      loadVersions(versionsBody, function () {
        var total = state.versions.length;
        subtitle.textContent =
          total + " " + pluralVersions(total) +
          " · от новых к старым · откат создает новую версию, история не переписывается";
        renderVersionsList(versionsBody);
        if (state.selectedVersionId !== null) {
          selectVersion(state.selectedVersionId, versionsBody);
        }
      });
    });
}

function pluralVersions(n) {
  var mod10 = n % 10;
  var mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) {
    return "версия";
  }
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return "версии";
  }
  return "версий";
}

init();
