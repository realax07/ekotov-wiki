/* Страница статьи /wiki/{id} (tasks.md 3.2 add-wiki; FR-108, FR-109,
 * FR-116; design §6–§7). Строго по утвержденному мокапу
 * design/wiki-page.html.
 *
 * ES-модуль роута /wiki/{id} (backend/app/pages.py): id берет из
 * data-page-id каркаса .wiki-layout (шаблон wiki.html, контейнер
 * #wiki-article). На /wiki (раздел-список) data-page-id нет — модуль
 * не активен (и шаблон его там не подключает).
 *
 * API (design.md §3, backend/app/wiki.py):
 * - GET    /api/wiki/pages/{id}       — страница + breadcrumb (цепочка
 *   предков от корня, сервер) + can_delete (нет дочерних);
 * - GET    /api/wiki/pages/{id}/versions + GET /api/users — мета шапки
 *   («Обновлено … · автор последней правки — … · N версий», мокап);
 * - DELETE /api/wiki/pages/{id}       — 200 → redirect /wiki; 409
 *   (появились дочерние с момента рендера) → баннер ошибки, страница
 *   остается (мокап .error-banner); 404 → redirect /wiki.
 *
 * Поведение по мокапу:
 * - breadcrumb: все элементы кликабельны (/wiki/{id}), текущая — без
 *   ссылки (aria-current="page", FR-109);
 * - действия: «Редактировать» → /wiki/{id}?edit=1 (редактор 3.3
 *   подхватит), «История» → /wiki/{id}/history (роут каркаса +
 *   history.js 3.4), «Удалить» — видна ТОЛЬКО при can_delete (лист);
 * - клик «Удалить» → диалог подтверждения (мокап демо-зоны:
 *   «Удалить страницу?», фокус на «Отмена», Esc — отмена);
 * - 404 от API (и нечисловой id каркаса) → «Страница не найдена»
 *   в контентной области.
 *
 * Контент статьи просанитизирован сервером (sanitize.py на записи и
 * при рендере, design §4) — вставка через <template>.innerHTML:
 * скрипты внутри template.content браузером не исполняются, узлы
 * переносятся во всегда пустую article-body (страховка поверх
 * серверного whitelist'а). Заголовки/авторы/даты — только
 * createElement + textContent (XSS, паттерн board/search).
 * 401 при протухшей сессии → редирект /login (паттерн tree/search).
 * Без внешних зависимостей (ОГР-8).
 */

"use strict";

/* Короткие месяцы для «Обновлено 2 окт 2026, 14:32» (мокап, без «г.»). */
var MONTHS_SHORT = [
  "янв", "фев", "мар", "апр", "май", "июн",
  "июл", "авг", "сен", "окт", "ноя", "дек",
];

/* Иконки действий — статические SVG из мокапа (не данные пользователя). */
var ICONS = {
  edit:
    '<svg class="btn-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4l11-11-4-4L4 16v4zM14 6l4 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  history:
    '<svg class="btn-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7v5l3 3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  trash:
    '<svg class="btn-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M9 7V5h6v2M7 7l1 13h8l1-13M10 11v6M14 11v6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};

/* Текст 409 по мокапу (демо-зона .error-banner). */
var CONFLICT_MESSAGE =
  "Страницу удалить нельзя: у неё есть дочерние страницы. " +
  "Сначала перенесите или удалите их.";

/* ---------------------------------------------------------------------
 * Утилиты (паттерн tree.js/search.js)
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

/* ISO «2026-10-02T14:32:00+03:00» → «2 окт 2026, 14:32» (мокап). */
function formatDate(iso) {
  var parsed = new Date(iso);
  if (isNaN(parsed.getTime())) {
    return String(iso || "");
  }
  var pad = function (n) {
    return String(n).padStart(2, "0");
  };
  return (
    parsed.getDate() + " " + MONTHS_SHORT[parsed.getMonth()] + " " +
    parsed.getFullYear() + ", " + pad(parsed.getHours()) + ":" +
    pad(parsed.getMinutes())
  );
}

/* «1 версия / 2 версии / 5 версий» (с 11–14 исключением). */
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

function makeButton(className, iconSvg, label, onClick) {
  var button = el("button", className, label);
  button.type = "button";
  button.innerHTML = iconSvg; // статический SVG из мокапа, не данные
  button.appendChild(document.createTextNode(label));
  button.addEventListener("click", onClick);
  return button;
}

/* ---------------------------------------------------------------------
 * Пустые состояния
 * ------------------------------------------------------------------- */

/* 404 (и нечисловой id каркаса) — «страница не найдена» в контентной
 * области (задача 3.2; мокапа для состояния нет — токены V3). */
function renderNotFound(container) {
  var box = el("div", "wiki-notfound");
  box.appendChild(el("h2", null, "Страница не найдена"));
  box.appendChild(
    el(
      "p",
      null,
      "Такой страницы нет или она была удалена."
    )
  );
  var back = el("a", "wiki-notfound-link", "← Вернуться в Wiki");
  back.href = "/wiki";
  box.appendChild(back);
  container.replaceChildren(box);
  container.dataset.loaded = "true";
}

function showError(container, message) {
  container.replaceChildren(el("p", "wiki-error", message));
  container.dataset.loaded = "true";
}

/* ---------------------------------------------------------------------
 * Breadcrumb (FR-109): все элементы кликабельны, текущая — без ссылки
 * ------------------------------------------------------------------- */

export function renderBreadcrumb(nav, breadcrumb, currentId) {
  var chain = Array.isArray(breadcrumb) && breadcrumb.length > 0
    ? breadcrumb
    : []; // не должно случиться (сервер всегда отдает саму страницу)

  var ol = el("ol", "breadcrumb");
  chain.forEach(function (node, index) {
    if (index > 0) {
      var sep = el("li", "crumb-sep", "/");
      sep.setAttribute("aria-hidden", "true");
      ol.appendChild(sep);
    }
    var isCurrent = index === chain.length - 1 || node.id === currentId;
    if (isCurrent) {
      var current = el("li", null, node.title);
      current.setAttribute("aria-current", "page");
      ol.appendChild(current);
    } else {
      var li = el("li");
      var link = el("a", null, node.title);
      link.href = "/wiki/" + node.id;
      li.appendChild(link);
      ol.appendChild(li);
    }
  });
  nav.replaceChildren(ol);
}

/* ---------------------------------------------------------------------
 * Диалог подтверждения удаления (мокап демо-зоны wiki-page.html)
 * ------------------------------------------------------------------- */

function openDeleteConfirm(page, onDelete) {
  var backdrop = el("div", "confirm-backdrop");
  backdrop.setAttribute("role", "presentation");

  var dialog = el("div", "confirm");
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-labelledby", "wiki-delete-confirm-title");

  var title = el("h2", null, "Удалить страницу?");
  title.id = "wiki-delete-confirm-title";

  var text = el(
    "p",
    null,
    "«" + page.title + "» будет удалена безвозвратно. История версий " +
    "страницы удаляется вместе с ней."
  );

  var actions = el("div", "confirm-actions");
  var cancel = el("button", "btn btn-secondary", "Отмена");
  cancel.type = "button";
  var confirm = el("button", "btn btn-danger-solid", "Удалить");
  confirm.type = "button";
  actions.appendChild(cancel);
  actions.appendChild(confirm);

  dialog.appendChild(title);
  dialog.appendChild(text);
  dialog.appendChild(actions);
  backdrop.appendChild(dialog);
  document.body.appendChild(backdrop);

  function close() {
    document.removeEventListener("keydown", onKeydown);
    backdrop.remove();
  }

  function onKeydown(event) {
    if (event.key === "Escape") {
      close();
    }
  }

  cancel.addEventListener("click", close);
  backdrop.addEventListener("click", function (event) {
    if (event.target === backdrop) {
      close();
    }
  });
  confirm.addEventListener("click", function () {
    close();
    onDelete();
  });
  document.addEventListener("keydown", onKeydown);

  /* Мокап: фокус в диалоге — на кнопке «Отмена». */
  cancel.focus();
}

/* ---------------------------------------------------------------------
 * Удаление: DELETE → 200 redirect /wiki; 409 → баннер, страница остается
 * ------------------------------------------------------------------- */

function showDeleteBanner(container, message) {
  var existing = document.getElementById("wiki-delete-error");
  if (existing) {
    existing.remove();
  }
  var banner = el("div", "error-banner", message);
  banner.id = "wiki-delete-error";
  banner.setAttribute("role", "alert");
  container.prepend(banner); // над шапкой статьи; страница остается
}

async function deletePage(container, pageId) {
  var response = await fetch("/api/wiki/pages/" + pageId, {
    method: "DELETE",
    credentials: "same-origin",
  });
  if (response.status === 401) {
    window.location.href = "/login";
    return;
  }
  if (response.status === 404) {
    window.location.href = "/wiki"; // страницу уже удалили
    return;
  }
  if (response.status === 409) {
    showDeleteBanner(container, CONFLICT_MESSAGE);
    return;
  }
  if (!response.ok) {
    showDeleteBanner(
      container,
      "Не удалось удалить страницу. Попробуйте еще раз."
    );
    return;
  }
  window.location.href = "/wiki";
}

/* ---------------------------------------------------------------------
 * Мета шапки: «Обновлено … · автор последней правки — … · N версий»
 * ------------------------------------------------------------------- */

async function enrichMeta(metaNode, page) {
  var parts = ["Обновлено " + formatDate(page.updated_at)];
  try {
    var versions = [];
    var authors = {};
    var versionsResp = await fetch(
      "/api/wiki/pages/" + page.id + "/versions",
      { credentials: "same-origin" }
    );
    if (versionsResp.ok) {
      var body = await versionsResp.json();
      versions = Array.isArray(body.versions) ? body.versions : [];
    }
    var usersResp = await fetch("/api/users", { credentials: "same-origin" });
    if (usersResp.ok) {
      var usersBody = await usersResp.json();
      (usersBody.users ?? []).forEach(function (user) {
        authors[user.id] = user.login;
      });
    }
    /* Автор последней правки = автор НОВОЙ (первой в списке) версии;
     * без версий — автор страницы. */
    var last = versions.length > 0 ? versions[0] : null;
    var authorId = last ? last.author_id : page.author_id;
    if (authors[authorId]) {
      parts.push("автор последней правки — " + authors[authorId]);
    }
    if (versions.length > 0) {
      parts.push(versions.length + " " + pluralVersions(versions.length));
    }
  } catch (error) {
    /* мета — украшение: без автора/счетчика шапка не ломается */
  }
  metaNode.textContent = parts.join(" · ");
}

/* ---------------------------------------------------------------------
 * Рендер статьи (мокап: .article-head + article.article > .article-body)
 * ------------------------------------------------------------------- */

function renderArticle(container, page) {
  var head = el("div", "article-head");
  head.appendChild(el("h1", null, page.title));

  var meta = el("div", "article-meta", "Обновлено " + formatDate(page.updated_at));
  head.appendChild(meta);

  var actions = el("div", "article-actions");
  actions.appendChild(
    makeButton("btn btn-primary", ICONS.edit, "Редактировать", function () {
      window.location.href = "/wiki/" + page.id + "?edit=1"; // редактор 3.3
    })
  );
  actions.appendChild(
    makeButton("btn btn-secondary", ICONS.history, "История", function () {
      window.location.href = "/wiki/" + page.id + "/history"; // 3.4
    })
  );
  var deleteButton = makeButton(
    "btn btn-danger",
    ICONS.trash,
    "Удалить",
    function () {
      openDeleteConfirm(page, function () {
        deletePage(container, page.id);
      });
    }
  );
  deleteButton.hidden = !page.can_delete; // видна ТОЛЬКО листу (can_delete)
  actions.appendChild(deleteButton);
  head.appendChild(actions);

  var article = el("article", "article");
  var body = el("div", "article-body");
  var tpl = document.createElement("template");
  /* Контент просанитизирован сервером (sanitize.py, design §4).
   * <template>.innerHTML: скрипты внутри не исполняются, узлы
   * переносятся как статические — страховка поверх серверного
   * whitelist'а. */
  tpl.innerHTML = String(page.content ?? "");
  body.appendChild(tpl.content);
  article.appendChild(body);

  container.replaceChildren(head, article);
  container.dataset.loaded = "true";

  enrichMeta(meta, page);
}

/* ---------------------------------------------------------------------
 * Инициализация
 * ------------------------------------------------------------------- */

export async function initWikiPage() {
  var layout = document.querySelector(".wiki-layout");
  if (!layout) {
    return null; // не каркас wiki — модуль не активен
  }
  var rawId =
    layout.dataset && layout.dataset.pageId ? layout.dataset.pageId : "";
  if (!rawId) {
    return null; // /wiki (раздел-список) — рендерит tree.js/search.js
  }

  var nav = document.querySelector("nav.wiki-breadcrumb");
  var container = document.getElementById("wiki-article");
  if (!container) {
    return null;
  }

  if (!/^\d+$/.test(rawId)) {
    if (nav) nav.replaceChildren();
    renderNotFound(container); // нечисловой id — «не найдена» (3.2)
    return null;
  }

  var response = await fetch("/api/wiki/pages/" + rawId, {
    credentials: "same-origin",
  });
  if (response.status === 401) {
    window.location.href = "/login";
    return null;
  }
  if (response.status === 404) {
    if (nav) nav.replaceChildren();
    renderNotFound(container);
    return null;
  }
  if (!response.ok) {
    showError(container, "Не удалось загрузить страницу");
    return null;
  }

  var page = await response.json();
  document.title = page.title + " · ekotov-wiki";
  if (nav) {
    renderBreadcrumb(nav, page.breadcrumb, page.id);
  }
  renderArticle(container, page);
  return page;
}

/* Автозапуск ES-модуля (подключение — <script type="module"> в wiki.html,
 * только на роуте /wiki/{id}). */
initWikiPage();
