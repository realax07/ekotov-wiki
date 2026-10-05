/* Галерея (tasks.md 1.5 add-gallery-service; FR-79…FR-86; design §0/§6).
 *
 * ES-модуль страницы /gallery (паттерн search.js/board-модулей). Вид —
 * по утвержденным мокапам 1.1 (design/gallery-grid.html,
 * gallery-lightbox.html, gallery-upload.html).
 *
 * Данные — API images-сервиса (истина — services/images/app/gallery.py):
 * - GET    /api/images?category=<ИМЯ>&tag=<имя> — список (created_at DESC):
 *          {id, filename, thumb_name, original_name, mime, size,
 *          uploaded_by, created_at, category, tags, likes, dislikes,
 *          comments, my_reaction, url, thumb_url}; tags — [имена] из
 *          агрегата image_tags+gallery_tags (задача 1.6, Э-3: паритет
 *          с detail-ответом; пилюли тегов на карточке — мокап 1.1);
 * - GET    /api/images/{id} — метаданные + теги + реакции + комментарии
 *          ({id, body, created_at, user_id, author});
 * - POST   /api/images (multipart: file, category?, tags?) — 201; 422
 *          {error, details} — текст показывается в форме (NFR-21);
 * - PUT    /api/images/{id}/like | /dislike — голос (повторное — снятие,
 *          противоположное — перенос); ответ {likes, dislikes, my_reaction};
 * - POST   /api/images/{id}/comments {body} — 201; пустой → 422;
 * - DELETE /api/images/{id}/comments/{cid} — только автор (чужой → 403).
 *
 * «Свой комментарий» (кнопка «удалить» — только у своих): автор в ответе —
 * display_name/логин (COALESCE), «свой» определяется прямым сравнением
 * comment.user_id === me.id из GET /api/auth/me (задача 1.6, Э-4: ядро
 * добавило id в состав /me; мост GET /api/users демонтирован).
 *
 * Фильтр category — по ИМЕНИ (эскалация Э-2 ревьюера 1.2 принята):
 * селекты фильтров и формы заполняются из фактических данных списка.
 *
 * XSS-дисциплина (ОГР-11): весь рендер пользовательских данных (названия,
 * категории, комментарии, имена файлов) — createElement + textContent;
 * innerHTML не используется; href/PUT-пути строятся из числовых id и
 * серверных url-полей.
 *
 * Клавиатура лайтбокса (FR-83): ArrowLeft/ArrowRight — листание по
 * текущей отфильтрованной выдаче (циклично), Esc — закрытие; фокус
 * возвращается на карточку-триггер.
 */

"use strict";

/* --- Состояние модуля --- */

var state = {
  images: [],          // текущая отфильтрованная выдача (для листания)
  categories: [],      // фактические имена категорий (из данных)
  tags: [],            // фактические имена тегов — из поля tags списка (Э-3)
  me: null,            // {id, user, ...} из /api/auth/me (id — Э-4/1.6)
  lightboxIndex: -1,   // позиция в state.images
  triggerCard: null,   // карточка-триггер (возврат фокуса)
  uploadFile: null,    // выбранный в форме файл
};

var LIKE_ICONS = null; // SVG-пути реакций (клонируются в карточки)

/* ---------------------------------------------------------------------
 * Утилиты (паттерн search.js)
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

function showBox(id, message) {
  var box = document.getElementById(id);
  box.textContent = message; // textContent — не innerHTML (XSS)
  box.hidden = false;
}

function hideBox(id) {
  var box = document.getElementById(id);
  box.textContent = "";
  box.hidden = true;
}

/* Единая обработка ошибок API (паттерн search.js): 401 → /login;
 * 422 → текст из error/details (форма 422 ядра/search);
 * прочее — общее сообщение со статусом. */
function apiErrorText(status, body) {
  if (body && typeof body.error === "string" && body.error) {
    var details = body.details;
    if (Array.isArray(details) && details.length > 0) {
      var first = details[0];
      if (first && typeof first.msg === "string" && first.msg) {
        return body.error + ": " + first.msg;
      }
    }
    if (typeof body.detail === "string" && body.detail) {
      return body.error + ": " + body.detail;
    }
    return body.error;
  }
  if (body && typeof body.detail === "string" && body.detail) {
    return body.detail;
  }
  return "Ошибка запроса (HTTP " + status + ").";
}

function handleApiError(response, body, onError) {
  if (response.status === 401) {
    window.location.href = "/login";
    return;
  }
  onError(apiErrorText(response.status, body));
}

function formatBytes(bytes) {
  var n = Number(bytes);
  if (!isFinite(n) || n < 0) {
    return "";
  }
  if (n < 1024 * 1024) {
    return Math.round(n / 1024) + " КБ";
  }
  return (n / (1024 * 1024)).toFixed(1).replace(".", ",") + " МБ";
}

function formatExt(mime) {
  var map = {
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
  };
  return map[mime] || "";
}

function formatDate(iso) {
  /* created_at — ISO UTC; показ — локальная дата/время (мокап: «сегодня»,
   * «2 окт»; упрощение до даты-времени без относительных форм). */
  var d = new Date(iso);
  if (isNaN(d.getTime())) {
    return "";
  }
  return d.toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/* ---------------------------------------------------------------------
 * Загрузка данных
 * ------------------------------------------------------------------- */

function fetchMe() {
  return fetch("/api/auth/me", { credentials: "same-origin" })
    .then(function (response) {
      if (!response.ok) {
        return null;
      }
      return parseBody(response);
    })
    .then(function (body) {
      state.me = body && body.user ? body : null;
    })
    .catch(function () {
      state.me = null;
    });
}

function fetchImages() {
  var category = document.getElementById("filter-category").value;
  var tag = document.getElementById("filter-tag").value;
  var params = new URLSearchParams();
  if (category) {
    params.set("category", category);
  }
  if (tag) {
    params.set("tag", tag);
  }
  var qs = params.toString();
  return fetch("/api/images" + (qs ? "?" + qs : ""), {
    credentials: "same-origin",
  })
    .then(function (response) {
      return response.json().then(function (body) {
        return { response: response, body: body };
      });
    })
    .then(function (result) {
      if (!result.response.ok) {
        handleApiError(result.response, result.body, showGalleryError);
        return;
      }
      hideGalleryError();
      state.images = Array.isArray(result.body && result.body.images)
        ? result.body.images
        : [];
      collectFacets();       // категории + теги — из фактических данных (Э-2/Э-3)
      fillFilterOptions();   // опции категорий — из фактических данных (Э-2)
      renderGrid();
    })
    .catch(function () {
      showGalleryError("Не удалось загрузить галерею.");
    });
}

/* Факты для селектов и пилюль (Э-2: фильтр category по ИМЕНИ — значения из
 * фактических данных; Э-3/1.6: теги теперь приходят в поле tags списка —
 * словарь тегов фильтра наполняется сразу, не по мере открытий лайтбокса). */
function collectFacets() {
  var categories = {};
  state.images.forEach(function (img) {
    if (img.category) {
      categories[img.category] = true;
    }
    if (Array.isArray(img.tags)) {
      img.tags.forEach(function (name) {
        if (name && state.tags.indexOf(name) === -1) {
          state.tags.push(name);
        }
      });
    }
  });
  state.categories = Object.keys(categories).sort(function (a, b) {
    return a.localeCompare(b, "ru");
  });
  state.tags.sort(function (a, b) {
    return a.localeCompare(b, "ru");
  });
}

function refreshFiltersFromData() {
  fillFilterOptions();
  fillTagFilterOptions(); // опции тегов — из поля tags списка (Э-3 закрыт)
}

/* ---------------------------------------------------------------------
 * Сетка (мокап gallery-grid.html)
 * ------------------------------------------------------------------- */

function statIcon(pathD) {
  var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", pathD);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "2");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);
  return svg;
}

var ICON_LIKE =
  "M7 11v9H4a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3zm0 0l4-7a2.4 2.4 0 0 1 2.4 2.4V9H19a2 2 0 0 1 2 2.2l-1 6.6A2 2 0 0 1 18 19.5H7";
var ICON_DISLIKE =
  "M17 13V4h3a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-3zm0 0l-4 7a2.4 2.4 0 0 1-2.4-2.4V15H5a2 2 0 0 1-2-2.2l1-6.6A2 2 0 0 1 6 4.5h11";
var ICON_COMMENT = "M4 5h16v11H9l-5 4V5z";

function renderGrid() {
  var grid = document.getElementById("gallery-grid");
  grid.textContent = "";

  if (state.images.length === 0) {
    var empty = el("div", "gallery-empty",
      "По фильтру ничего не найдено. Загрузите первое изображение или сбросьте фильтры.");
    grid.appendChild(empty);
    updateCounter();
    return;
  }

  state.images.forEach(function (img, index) {
    grid.appendChild(buildCard(img, index));
  });
  updateCounter();
}

function buildCard(img, index) {
  var card = el("a", "g-card");
  card.href = "#";
  var title = img.original_name || img.filename || "Без названия";
  card.setAttribute("aria-label",
    title + (formatExt(img.mime) ? " (формат " + formatExt(img.mime) + ")" : "") +
    " — открыть просмотр");

  /* Превью: ячейка 4:3, изображение ЦЕЛИКОМ (object-fit: contain —
   * уточнение Заказчика 1.1) + бейдж формата. */
  var thumb = el("div", "g-thumb");
  var picture = document.createElement("img");
  picture.src = img.thumb_url || img.url;
  picture.alt = "";
  picture.loading = "lazy";
  thumb.appendChild(picture);
  var ext = formatExt(img.mime);
  if (ext) {
    thumb.appendChild(el("span", "fmt-badge", ext));
  }

  var body = el("div", "g-card-body");
  body.appendChild(el("h3", "g-card-title", title));

  var tagsRow = el("div", "g-card-tags");
  if (img.category) {
    tagsRow.appendChild(el("span", "task-category", img.category));
  }
  /* Пилюли тегов — по мокапу 1.1 (design/gallery-grid.html); tags приходят
   * в элементе списка (задача 1.6, Э-3 — паритет с detail-ответом). */
  if (Array.isArray(img.tags)) {
    img.tags.forEach(function (name) {
      tagsRow.appendChild(el("span", "task-tag", name));
    });
  }
  body.appendChild(tagsRow);

  var stats = el("div", "g-card-stats");

  stats.appendChild(buildStat(img, 1, ICON_LIKE, "Нравится"));
  stats.appendChild(buildStat(img, -1, ICON_DISLIKE, "Не нравится"));

  var comments = el("span", "stat");
  comments.appendChild(statIcon(ICON_COMMENT));
  comments.appendChild(el("span", null, String(img.comments || 0)));
  stats.appendChild(comments);

  stats.appendChild(el("span", "g-card-date", formatDate(img.created_at)));
  body.appendChild(stats);

  card.appendChild(thumb);
  card.appendChild(body);

  card.addEventListener("click", function (event) {
    event.preventDefault();
    openLightbox(index, card);
  });

  return card;
}

function buildStat(img, value, iconPath, label) {
  var mine = Number(img.my_reaction) === value;
  var stat = el("span", mine ? "stat my-vote" : "stat");
  stat.appendChild(statIcon(iconPath));
  stat.appendChild(el("span", null,
    String(value === 1 ? img.likes || 0 : img.dislikes || 0)));
  stat.title = mine ? "Ваш голос: " + label : label;
  return stat;
}

function updateCounter() {
  var counter = document.getElementById("filter-count");
  var total = state.images.length;
  counter.textContent = "Найдено: " + total;
}

function showGalleryError(message) {
  showBox("gallery-error", message);
}

function hideGalleryError() {
  hideBox("gallery-error");
}

/* ---------------------------------------------------------------------
 * Фильтры
 * ------------------------------------------------------------------- */

function fillFilterOptions() {
  var select = document.getElementById("filter-category");
  var current = select.value;
  /* Пересобираем опции, сохраняя выбор (после загрузки новая категория
   * могла появиться в данных). */
  select.textContent = "";
  select.appendChild(el("option", null, "Все категории")).value = "";
  state.categories.forEach(function (name) {
    var option = el("option", null, name);
    option.value = name;
    select.appendChild(option);
  });
  if (current && state.categories.indexOf(current) !== -1) {
    select.value = current;
  }
}

function refreshFiltersFromData() {
  fillFilterOptions();
  fillTagFilterOptions(); // опции тегов — из поля tags списка (Э-3 закрыт)
}

/* Селект тегов: пересборка с сохранением выбора (общая для первичного
 * наполнения из списка и точечных добавлений appendKnownTag). */
function fillTagFilterOptions() {
  var select = document.getElementById("filter-tag");
  var current = select.value;
  select.textContent = "";
  select.appendChild(el("option", null, "Все теги")).value = "";
  state.tags.forEach(function (tag) {
    var option = el("option", null, tag);
    option.value = tag;
    select.appendChild(option);
  });
  if (current && state.tags.indexOf(current) !== -1) {
    select.value = current;
  }
}

function appendKnownTag(name) {
  if (!name || state.tags.indexOf(name) !== -1) {
    return;
  }
  state.tags.push(name);
  state.tags.sort(function (a, b) {
    return a.localeCompare(b, "ru");
  });
  fillTagFilterOptions();
}

function bindFilters() {
  var reload = function () {
    fetchImages().then(syncLightboxWithList);
  };
  document.getElementById("filter-category").addEventListener("change", reload);
  document.getElementById("filter-tag").addEventListener("change", reload);
  document.getElementById("filter-reset").addEventListener("click", function () {
    document.getElementById("filter-category").value = "";
    document.getElementById("filter-tag").value = "";
    reload();
  });
}

/* ---------------------------------------------------------------------
 * FULL-SCREEN МОДАЛКА (мокап gallery-lightbox.html; FR-83)
 * ------------------------------------------------------------------- */

function lightboxElements() {
  return {
    overlay: document.getElementById("lightbox-overlay"),
    image: document.getElementById("lb-image"),
    title: document.getElementById("lb-title"),
    meta: document.getElementById("lb-meta"),
    like: document.getElementById("lb-like"),
    dislike: document.getElementById("lb-dislike"),
    likeCount: document.getElementById("lb-like-count"),
    dislikeCount: document.getElementById("lb-dislike-count"),
    download: document.getElementById("lb-download"),
    commentsList: document.getElementById("lb-comments-list"),
    commentsCount: document.getElementById("lb-comments-count"),
    counterPos: document.getElementById("lb-counter-pos"),
    input: document.getElementById("comment-input"),
    send: document.getElementById("comment-send"),
    error: document.getElementById("lb-error"),
    prev: document.getElementById("lb-prev"),
    next: document.getElementById("lb-next"),
  };
}

function openLightbox(index, triggerCard) {
  state.lightboxIndex = index;
  state.triggerCard = triggerCard || null;
  var elems = lightboxElements();
  elems.overlay.hidden = false;
  document.body.style.overflow = "hidden";
  loadLightboxImage(index);
  elems.close = document.getElementById("lb-close");
  elems.close.focus();
}

function closeLightbox() {
  var elems = lightboxElements();
  elems.overlay.hidden = true;
  document.body.style.overflow = "";
  state.lightboxIndex = -1;
  hideBox("lb-error");
  if (state.triggerCard) {
    state.triggerCard.focus(); // возврат фокуса на карточку-триггер
    state.triggerCard = null;
  }
}

function loadLightboxImage(index) {
  var img = state.images[index];
  if (!img) {
    return;
  }
  var elems = lightboxElements();
  hideBox("lb-error");

  var title = img.original_name || img.filename || "Без названия";
  elems.title.textContent = title;
  elems.image.src = img.url || ("/images/" + img.filename);
  elems.image.alt = title;
  elems.counterPos.textContent = (index + 1) + " / " + state.images.length;

  /* Мета: категория + теги (пилюли — мокап gallery-lightbox.html) + дата.
   * Загрузивший НЕ показывается: uploaded_by — числовой id, резолвить его
   * в логин без моста /api/users нечем (мост демонтирован, Э-4/1.6);
   * авторство видно по комментариям (author резолвит сам сервис). */
  elems.meta.textContent = "";
  if (img.category) {
    elems.meta.appendChild(el("span", "task-category", img.category));
  }
  if (Array.isArray(img.tags)) {
    img.tags.forEach(function (name) {
      elems.meta.appendChild(el("span", "task-tag", name));
    });
  }
  var metaParts = [];
  if (img.created_at) {
    metaParts.push("загружено " + formatDate(img.created_at));
  }
  if (metaParts.length > 0) {
    elems.meta.appendChild(el("span", null, "· " + metaParts.join(", ")));
  }

  /* Скачивание: <a download> на оригинал; имя — original_name
   * (атрибут download подсказывает имя, сервер отдаёт файл как есть). */
  elems.download.href = img.url || ("/images/" + img.filename);
  elems.download.setAttribute("download", title);

  /* Реакции: из полей списка; точные счетчики подтянет детальный ответ. */
  applyReactionState({
    likes: img.likes || 0,
    dislikes: img.dislikes || 0,
    my_reaction: img.my_reaction,
  });

  elems.input.value = "";
  elems.send.disabled = true;
  elems.commentsList.textContent = "";
  elems.commentsCount.textContent = "";

  /* Детальные данные + комментарии (заодно накапливаем теги, Э-3). */
  fetch("/api/images/" + img.id, { credentials: "same-origin" })
    .then(function (response) {
      return response.json().then(function (body) {
        return { response: response, body: body };
      });
    })
    .then(function (result) {
      if (!result.response.ok) {
        handleApiError(result.response, result.body, function (message) {
          showBox("lb-error", message);
        });
        return;
      }
      var detail = result.body;
      if (state.images[state.lightboxIndex] &&
          state.images[state.lightboxIndex].id === detail.id) {
        applyReactionState(detail);
        renderComments(detail.comments || []);
      }
      if (Array.isArray(detail.tags)) {
        detail.tags.forEach(appendKnownTag);
      }
    })
    .catch(function () {
      showBox("lb-error", "Не удалось загрузить данные изображения.");
    });
}

function applyReactionState(reaction) {
  var elems = lightboxElements();
  var my = reaction.my_reaction === 1 ? 1 : reaction.my_reaction === -1 ? -1 : 0;

  elems.likeCount.textContent = String(reaction.likes || 0);
  elems.dislikeCount.textContent = String(reaction.dislikes || 0);

  elems.like.classList.toggle("my-vote", my === 1);
  elems.like.setAttribute("aria-pressed", my === 1 ? "true" : "false");
  elems.like.setAttribute("aria-label",
    my === 1 ? "Нравится, ваш голос учтен. Снять голос" : "Нравится. Поставить голос");

  elems.dislike.classList.toggle("my-vote", my === -1);
  elems.dislike.setAttribute("aria-pressed", my === -1 ? "true" : "false");
  elems.dislike.setAttribute("aria-label",
    my === -1 ? "Не нравится, ваш голос учтен. Снять голос" : "Не нравится. Поставить голос");
}

function sendReaction(kind) {
  var img = state.images[state.lightboxIndex];
  if (!img) {
    return;
  }
  var elems = lightboxElements();
  elems.like.disabled = true;
  elems.dislike.disabled = true;
  fetch("/api/images/" + img.id + "/" + kind, {
    method: "PUT",
    credentials: "same-origin",
  })
    .then(function (response) {
      return response.json().then(function (body) {
        return { response: response, body: body };
      });
    })
    .then(function (result) {
      elems.like.disabled = false;
      elems.dislike.disabled = false;
      if (!result.response.ok) {
        handleApiError(result.response, result.body, function (message) {
          showBox("lb-error", message);
        });
        return;
      }
      applyReactionState(result.body);
      /* Обновить счетчики/бейдж на карточке сетки. */
      img.likes = result.body.likes;
      img.dislikes = result.body.dislikes;
      img.my_reaction = result.body.my_reaction;
      renderGrid();
      if (state.triggerCard) {
        /* renderGrid пересоздал карточки — триггер больше не в DOM;
         * фокус держим в модалке (крестик), вернем на закрытии. */
        state.triggerCard = document.querySelectorAll(".g-card")[state.lightboxIndex] || null;
      }
    })
    .catch(function () {
      elems.like.disabled = false;
      elems.dislike.disabled = false;
      showBox("lb-error", "Не удалось учесть голос.");
    });
}

function syncLightboxWithList() {
  /* После перезагрузки списка (фильтр/загрузка) — синхронизация
   * открытого лайтбокса: индекс мог исчезнуть из выдачи. */
  if (state.lightboxIndex < 0) {
    return;
  }
  if (state.lightboxIndex >= state.images.length) {
    closeLightbox();
    return;
  }
  loadLightboxImage(state.lightboxIndex);
}

function navigateLightbox(delta) {
  if (state.images.length === 0) {
    return;
  }
  /* Листание циклично по текущей отфильтрованной выдаче (design §6). */
  var next = (state.lightboxIndex + delta + state.images.length) % state.images.length;
  state.lightboxIndex = next;
  loadLightboxImage(next);
}

/* --- Комментарии (FR-82): список / добавление / удаление своего --- */

function isMyComment(comment) {
  /* Прямое сравнение по me.id (Э-4/1.6: ядро добавило id в /api/auth/me;
   * мост /api/users демонтирован). */
  return Boolean(state.me && state.me.id != null) &&
    Number(comment.user_id) === Number(state.me.id);
}

function renderComments(comments) {
  var elems = lightboxElements();
  elems.commentsList.textContent = "";
  elems.commentsCount.textContent = "(" + comments.length + ")";

  if (comments.length === 0) {
    elems.commentsList.appendChild(
      el("p", "lb-comments-empty", "Пока нет комментариев."));
    return;
  }

  comments.forEach(function (comment) {
    var item = el("div", "comment");
    var head = el("div", "comment-head");
    head.appendChild(el("span", "comment-author", comment.author || ""));
    head.appendChild(el("span", null, formatDate(comment.created_at)));
    if (isMyComment(comment)) {
      var del = el("button", "comment-delete", "удалить");
      del.type = "button";
      del.setAttribute("aria-label", "Удалить свой комментарий");
      del.addEventListener("click", function () {
        deleteComment(comment.id);
      });
      head.appendChild(del);
    }
    item.appendChild(head);
    item.appendChild(el("p", "comment-body", comment.body));
    elems.commentsList.appendChild(item);
  });
}

function reloadComments() {
  var img = state.images[state.lightboxIndex];
  if (!img) {
    return;
  }
  fetch("/api/images/" + img.id, { credentials: "same-origin" })
    .then(function (response) {
      return response.json().then(function (body) {
        return { response: response, body: body };
      });
    })
    .then(function (result) {
      if (!result.response.ok) {
        handleApiError(result.response, result.body, function (message) {
          showBox("lb-error", message);
        });
        return;
      }
      renderComments(result.body.comments || []);
      /* Счетчик комментариев на карточке сетки. */
      img.comments = (result.body.comments || []).length;
      renderGrid();
      if (state.triggerCard) {
        state.triggerCard = document.querySelectorAll(".g-card")[state.lightboxIndex] || null;
      }
    })
    .catch(function () {
      showBox("lb-error", "Не удалось загрузить комментарии.");
    });
}

function deleteComment(commentId) {
  var img = state.images[state.lightboxIndex];
  if (!img) {
    return;
  }
  fetch("/api/images/" + img.id + "/comments/" + commentId, {
    method: "DELETE",
    credentials: "same-origin",
  })
    .then(function (response) {
      return response.json().then(function (body) {
        return { response: response, body: body };
      });
    })
    .then(function (result) {
      if (!result.response.ok) {
        /* 403 чужого комментария до сервера не дойдет (кнопки у чужих
         * нет), но обработка по контракту — показать текст. */
        handleApiError(result.response, result.body, function (message) {
          showBox("lb-error", message);
        });
        return;
      }
      hideBox("lb-error");
      reloadComments();
    })
    .catch(function () {
      showBox("lb-error", "Не удалось удалить комментарий.");
    });
}

function submitComment(event) {
  event.preventDefault();
  var elems = lightboxElements();
  var img = state.images[state.lightboxIndex];
  var body = elems.input.value.trim();
  if (!img || !body) {
    return; // пустой не отправляем (кнопка и так disabled)
  }
  elems.send.disabled = true;
  fetch("/api/images/" + img.id + "/comments", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body: body }),
  })
    .then(function (response) {
      return response.json().then(function (payload) {
        return { response: response, body: payload };
      });
    })
    .then(function (result) {
      if (!result.response.ok) {
        handleApiError(result.response, result.body, function (message) {
          showBox("lb-error", message);
        });
        elems.send.disabled = elems.input.value.trim() === "";
        return;
      }
      elems.input.value = "";
      hideBox("lb-error");
      reloadComments();
    })
    .catch(function () {
      elems.send.disabled = false;
      showBox("lb-error", "Не удалось добавить комментарий.");
    });
}

/* ---------------------------------------------------------------------
 * Форма загрузки (мокап gallery-upload.html; FR-79, NFR-21)
 * ------------------------------------------------------------------- */

function openUpload() {
  document.getElementById("upload-overlay").hidden = false;
  document.body.style.overflow = "hidden";
  fillUploadCategories();
  resetUploadForm();
  document.getElementById("upload-close").focus();
}

function closeUpload() {
  document.getElementById("upload-overlay").hidden = true;
  document.body.style.overflow = "";
  resetUploadForm();
  hideBox("upload-error");
  document.getElementById("upload-button").focus();
}

function fillUploadCategories() {
  var select = document.getElementById("up-category");
  var current = select.value;
  select.textContent = "";
  select.appendChild(el("option", null, "Без категории")).value = "";
  state.categories.forEach(function (name) {
    var option = el("option", null, name);
    option.value = name;
    select.appendChild(option);
  });
  var newOption = el("option", null, "+ Новая категория…");
  newOption.value = "__new__";
  select.appendChild(newOption);
  /* «__new__» не восстанавливаем — после закрытия формы это не имеет смысла. */
  if (current && current !== "__new__" &&
      (current === "" || state.categories.indexOf(current) !== -1)) {
    select.value = current;
  }
  syncNewCategoryField();
}

function syncNewCategoryField() {
  var select = document.getElementById("up-category");
  var field = document.getElementById("up-category-new-field");
  field.hidden = select.value !== "__new__";
}

function resetUploadForm() {
  state.uploadFile = null;
  document.getElementById("upload-form").reset();
  document.getElementById("file-row").hidden = true;
  document.getElementById("up-category-new-field").hidden = true;
  var chips = document.getElementById("tags-chips");
  chips.textContent = "";
  chips.hidden = true;
  document.getElementById("upload-progress").hidden = true;
  document.getElementById("upload-submit").disabled = false;
  hideBox("upload-error");
}

function setUploadFile(file) {
  state.uploadFile = file || null;
  var row = document.getElementById("file-row");
  if (!file) {
    row.hidden = true;
    row.classList.remove("invalid");
    return;
  }
  row.hidden = false;
  row.classList.remove("invalid");
  document.getElementById("file-name").textContent = file.name;
  var meta = formatBytes(file.size) + (file.type ? " · " + file.type : "");
  document.getElementById("file-meta").textContent = meta +
    " · оригинал сохраняется как есть, превью для сетки — автоматически";
}

function renderTagChips(raw) {
  var chips = document.getElementById("tags-chips");
  chips.textContent = "";
  var names = splitTagNames(raw);
  if (names.length === 0) {
    chips.hidden = true;
    return;
  }
  chips.hidden = false;
  names.forEach(function (name) {
    var chip = el("span", "chip");
    chip.appendChild(document.createTextNode(name + " "));
    var remove = document.createElement("button");
    remove.type = "button";
    remove.setAttribute("aria-label", "Убрать тег " + name);
    remove.textContent = "✕";
    remove.addEventListener("click", function () {
      removeTagFromInput(name);
    });
    chip.appendChild(remove);
    chips.appendChild(chip);
  });
}

function splitTagNames(raw) {
  return String(raw || "")
    .split(",")
    .map(function (part) {
      return part.trim();
    })
    .filter(function (part, index, all) {
      return part !== "" || index < all.length - 1;
    });
}

function removeTagFromInput(name) {
  var input = document.getElementById("up-tags");
  var parts = splitTagNames(input.value).filter(function (part) {
    return part !== name;
  });
  input.value = parts.length > 0 ? parts.join(",") + "," : "";
  renderTagChips(input.value);
}

/* Сообщения 422 (NFR-21: тип/размер/неизвестная категория) — человекочитаемо */
function uploadErrorText(status, body) {
  if (body && Array.isArray(body.details) && body.details.length > 0) {
    var first = body.details[0] || {};
    var msg = typeof first.msg === "string" ? first.msg : "";
    if (msg.indexOf("too_large") !== -1) {
      return "Файл больше 10 МБ — уменьшите или сожмите изображение.";
    }
    if (msg.indexOf("bad_type") !== -1 || msg.indexOf("not_image") !== -1) {
      return "Тип не поддерживается. Разрешены JPEG, PNG, GIF, WebP.";
    }
    if (msg.indexOf("unknown category") !== -1) {
      return "Категория не найдена — выберите из списка или создайте новую.";
    }
    if (msg) {
      return "Проверьте форму: " + msg;
    }
  }
  return apiErrorText(status, body);
}

function submitUpload(event) {
  event.preventDefault();
  hideBox("upload-error");

  var file = state.uploadFile;
  if (!file) {
    showBox("upload-error", "Выберите файл — загрузка без изображения невозможна.");
    return;
  }
  /* Предварительная клиентская проверка лимита (NFR-21): сервер проверит
   * по факту, но 12 МБ гнать не зачем — экономит трафик, текст тот же. */
  if (file.size > 10 * 1024 * 1024) {
    showBox("upload-error",
      "Файл больше 10 МБ (" + formatBytes(file.size) + ") — уменьшите или сожмите изображение.");
    return;
  }

  var select = document.getElementById("up-category");
  var category = select.value === "__new__"
    ? document.getElementById("up-category-new").value.trim()
    : select.value;

  var tags = splitTagNames(document.getElementById("up-tags").value)
    .filter(function (name) {
      return name !== "";
    })
    .join(",");

  var form = new FormData();
  form.append("file", file);
  if (category) {
    form.append("category", category);
  }
  if (tags) {
    form.append("tags", tags);
  }

  document.getElementById("upload-submit").disabled = true;
  document.getElementById("upload-progress").hidden = false;

  fetch("/api/images", {
    method: "POST",
    credentials: "same-origin",
    body: form,
  })
    .then(function (response) {
      return response.json().then(function (body) {
        return { response: response, body: body };
      });
    })
    .then(function (result) {
      document.getElementById("upload-submit").disabled = false;
      document.getElementById("upload-progress").hidden = true;
      if (!result.response.ok) {
        if (result.response.status === 422) {
          showBox("upload-error", uploadErrorText(result.response.status, result.body));
        } else {
          handleApiError(result.response, result.body, function (message) {
            showBox("upload-error", message);
          });
        }
        return;
      }
      /* Успех: новая категория/теги — в факты, форма закрывается,
       * карточка появляется в сетке (мокап: «после успеха — модалка
       * закрывается, карточка появляется в сетке»). */
      var created = result.body;
      if (created.category_id && created.tags) {
        created.tags.forEach(appendKnownTag);
      }
      closeUpload();
      fetchImages().then(function () {
        /* Загруженное — последнее (created_at DESC): открыть просмотр. */
        openLightbox(0, document.querySelectorAll(".g-card")[0] || null);
      });
    })
    .catch(function () {
      document.getElementById("upload-submit").disabled = false;
      document.getElementById("upload-progress").hidden = true;
      showBox("upload-error", "Не удалось загрузить файл.");
    });
}

/* ---------------------------------------------------------------------
 * Focus trap модалок (паттерн доступности: Tab не покидает диалог)
 * ------------------------------------------------------------------- */

function trapFocus(overlayId) {
  var overlay = document.getElementById(overlayId);
  overlay.addEventListener("keydown", function (event) {
    if (event.key !== "Tab") {
      return;
    }
    var focusable = overlay.querySelectorAll(
      "button:not([disabled]), a[href], input:not([hidden]):not([disabled]), select:not([disabled]), textarea:not([disabled])"
    );
    var visible = Array.prototype.filter.call(focusable, function (node) {
      return node.offsetParent !== null;
    });
    if (visible.length === 0) {
      return;
    }
    var first = visible[0];
    var last = visible[visible.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
}

/* ---------------------------------------------------------------------
 * Инициализация
 * ------------------------------------------------------------------- */

function bindLightbox() {
  var elems = lightboxElements();

  document.getElementById("lb-close").addEventListener("click", closeLightbox);
  elems.prev.addEventListener("click", function () {
    navigateLightbox(-1);
  });
  elems.next.addEventListener("click", function () {
    navigateLightbox(1);
  });

  elems.like.addEventListener("click", function () {
    sendReaction("like");
  });
  elems.dislike.addEventListener("click", function () {
    sendReaction("dislike");
  });

  elems.send.disabled = true;
  elems.input.addEventListener("input", function () {
    elems.send.disabled = elems.input.value.trim() === "";
  });
  document.getElementById("lb-comment-form").addEventListener("submit", submitComment);

  /* Клавиатура (FR-83): стрелки — листание, Esc — закрытие.
   * Слушаем на document: фокус может быть в панели. */
  document.addEventListener("keydown", function (event) {
    if (elems.overlay.hidden) {
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      navigateLightbox(-1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      navigateLightbox(1);
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeLightbox();
    }
  });

  trapFocus("lightbox-overlay");
}

function bindUpload() {
  document.getElementById("upload-button").addEventListener("click", openUpload);
  document.getElementById("upload-close").addEventListener("click", closeUpload);
  document.getElementById("upload-cancel").addEventListener("click", closeUpload);
  document.getElementById("upload-form").addEventListener("submit", submitUpload);

  var dropzone = document.getElementById("upload-dropzone");
  var fileInput = document.getElementById("upload-file");

  dropzone.addEventListener("click", function () {
    fileInput.click();
  });
  dropzone.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInput.click();
    }
  });
  fileInput.addEventListener("change", function () {
    setUploadFile(fileInput.files && fileInput.files[0]);
  });

  ["dragenter", "dragover"].forEach(function (name) {
    dropzone.addEventListener(name, function (event) {
      event.preventDefault();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach(function (name) {
    dropzone.addEventListener(name, function (event) {
      event.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });
  dropzone.addEventListener("drop", function (event) {
    var file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
    setUploadFile(file || null);
  });

  document.getElementById("file-remove").addEventListener("click", function () {
    fileInput.value = "";
    setUploadFile(null);
  });

  document.getElementById("up-category").addEventListener("change", syncNewCategoryField);
  var tagsInput = document.getElementById("up-tags");
  tagsInput.addEventListener("input", function () {
    renderTagChips(tagsInput.value);
  });

  trapFocus("upload-overlay");
}

function init() {
  bindFilters();
  bindLightbox();
  bindUpload();

  fetchMe().then(fetchImages).catch(function () {
    showGalleryError("Не удалось загрузить галерею.");
  });
}

init();
