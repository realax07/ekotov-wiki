/* rich/renderer.js — дерево блоков → DOM (tasks.md 1.4б; design §2;
 * FR-124, NFR-35).
 *
 * БЕЗОПАСНОСТЬ (NFR-35 defense-in-depth, design §6): DOM rich-блоков
 * строится ТОЛЬКО через createElement/textContent — пользовательский
 * контент никогда не интерпретируется как HTML (innerHTML для
 * пользовательского контента запрещен). Единственный innerHTML — legacy-
 * сегмент (HTML, уже санитизированный сервером на записи, design §1/§6):
 * тот же уровень доверия и тот же путь, что у существующего page.js до
 * пакета (template.innerHTML, scripts не исполняются).
 *
 * Инлайн-разметка (design §1): **b**, *i*, `code`, [link](url),
 * ![img](src){width=N} — также только textContent + проверка схем URL
 * (страховка поверх серверной sanitize_rich).
 *
 * WYSIWYG (FR-124): тот же renderMixed используется и на просмотре
 * (page.js), и в редакторе (editor.js) — соответствие по построению.
 */

"use strict";

import { getBlock, WIDTH_MIN, WIDTH_MAX } from "./block-parser.js";

/* ------------------------------------------------------------------ */
/* Утилиты DOM                                                         */
/* ------------------------------------------------------------------ */

export function el(tag, className, text) {
  var node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

/* Схемы URL инлайн-ссылок/изображений: http/https/относительные —
 * проходят; javascript:/data:/прочие — нейтрализуются (зеркало
 * sanitize_rich; здесь — второй слой защиты рендера). */
export function safeUrl(url) {
  var value = String(url || "").trim();
  if (!value) return "";
  var lowered = value.replace(/[\x00-\x20\x7f]+/g, "").toLowerCase();
  if (lowered.indexOf("data:") === 0) return "";
  if (/^[a-z][a-z0-9+.-]*:/.test(lowered) &&
      lowered.indexOf("http:") !== 0 && lowered.indexOf("https:") !== 0) {
    return "";
  }
  return value;
}

function escTextToNode(target, text) {
  /* Развернуть экранированные сущности sanitize_rich в литеральный текст
   * (textContent — безопасно, теги не интерпретируются). &amp; НЕ разворачивается:
   * бэкенд & не экранирует (sanitize_rich._HTML_ESCAPES — только &lt;/&gt;),
   * литерал «&amp;» в тексте пользователя при декодировании мутировал бы в «&»
   * и терялся бы при сохранении — roundtrip-сохранность (review-001-4.1 #4). */
  target.textContent = String(text)
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

/* ------------------------------------------------------------------ */
/* Инлайн-разметка: **b**, *i*, `code`, [текст](url), ![alt](src){w=N} */
/* ------------------------------------------------------------------ */

/* URL-группа = дословное зеркало _URL_GROUP в sanitize_rich.py: допускает
 * ЛЮБОЕ число групп скобок (http://x/a(b)c(d)) — иначе бэкенд сохраняет
 * такую инлайн-ссылку/картинку, а токенайзер рендерил бы литеральным текстом
 * (FR-124 «что видишь — то сохранишь», review-001-4.1 #3; не security —
 * safeUrl ниже второй слой). Менять только синхронно с бэкендом + кейс в
 * grammar-фикстурах. */
var INLINE_TOKEN_RE =
  /(\*\*([^*]+)\*\*)|(\*([^*]+)\*)|(`([^`]+)`)|(!\[([^\]]*)\]\(((?:[^()\s]|\([^()]*\))*)\)(?:\{width=(\d+)\})?)|(\[([^\]]*)\]\(((?:[^()\s]|\([^()]*\))*)\))/g;

export function renderInline(target, text) {
  var lastIndex = 0;
  var match;
  INLINE_TOKEN_RE.lastIndex = 0;
  while ((match = INLINE_TOKEN_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      target.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
    }
    if (match[1]) {
      var bold = el("strong");
      bold.textContent = match[2];
      target.appendChild(bold);
    } else if (match[3]) {
      var italic = el("em");
      italic.textContent = match[4];
      target.appendChild(italic);
    } else if (match[5]) {
      var code = el("code", "rich-inline-code");
      code.textContent = match[6];
      target.appendChild(code);
    } else if (match[7]) {
      var width = match[10] ? parseInt(match[10], 10) : null;
      appendImage(target, match[8], match[9], width);
    } else if (match[11]) {
      var url = safeUrl(match[13]);
      if (url) {
        var link = el("a");
        link.href = url;
        link.textContent = match[12];
        target.appendChild(link);
      } else {
        /* Схема нейтрализована — остается только текст ссылки */
        target.appendChild(document.createTextNode(match[12]));
      }
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    target.appendChild(document.createTextNode(text.slice(lastIndex)));
  }
  if (target.childNodes.length === 0) {
    target.appendChild(document.createTextNode(text));
  }
}

function appendImage(target, alt, src, width) {
  var url = safeUrl(src);
  if (!url) return; /* src нейтрализован — изображение не вставляется */
  var img = document.createElement("img");
  img.src = url;
  img.alt = alt;
  if (width !== null && width >= WIDTH_MIN && width <= WIDTH_MAX) {
    /* NFR-123: width=N — процент доступной ширины */
    img.style.width = width + "%";
  }
  target.appendChild(img);
}

/* Развернуть текст инлайн-разметки в целевой контейнер (экранированные
 * сущности sanitize_rich → литералы; &amp; не разворачивается — бэкенд его
 * не создает, review-001-4.1 #4). */
export function renderTextContent(target, text) {
  var plain = String(text)
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
  renderInline(target, plain);
}

/* ------------------------------------------------------------------ */
/* Рендер дерева                                                       */
/* ------------------------------------------------------------------ */

export function renderNode(node, options) {
  var module = getBlock(node.type);
  if (module && typeof module.render === "function") {
    return module.render(node, api, options || {});
  }
  /* Незарегистрированный тип — безопасная деградация: текст (design §6) */
  var fallback = el("div", "rich-block-fallback");
  fallback.textContent = serializeInlineFallback(node);
  return fallback;
}

function serializeInlineFallback(node) {
  return JSON.stringify(node);
}

export function renderChildren(nodes, options) {
  var fragment = document.createDocumentFragment();
  nodes.forEach(function (node) {
    if (node.type === "text") {
      appendTextParagraphs(fragment, node.text, options);
    } else {
      fragment.appendChild(renderNode(node, options));
    }
  });
  return fragment;
}

/* Текст (legacy-сегмент или текст между блоками) → абзацы.
 * editing=true: contenteditable привязка заполняется вызывающим кодом
 * (editor.js), здесь только абзацы-носители. */
export function appendTextParagraphs(fragment, text, options) {
  var plain = String(text)
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">"); /* &amp; не разворачивается — review-001-4.1 #4 */
  var lines = plain.split("\n");
  var paragraph = null;
  lines.forEach(function (line) {
    if (paragraph === null) {
      paragraph = el("p", "rich-text");
      fragment.appendChild(paragraph);
    }
    if (line === "") {
      /* пустая строка — разрыв абзаца (следующая строка — новый <p>) */
      paragraph = null;
      return;
    }
    if (paragraph.childNodes.length > 0) {
      paragraph.appendChild(document.createElement("br"));
    }
    renderInline(paragraph, line);
  });
}

export var api = {
  el: el,
  renderNode: renderNode,
  renderChildren: renderChildren,
  renderInline: renderInline,
  renderTextContent: renderTextContent,
  appendTextParagraphs: appendTextParagraphs,
  safeUrl: safeUrl,
  escTextToNode: escTextToNode,
};

/* ------------------------------------------------------------------ */
/* Смешанный контент (design §1: legacy + блоки в одной колонке)       */
/* ------------------------------------------------------------------ */

export function renderMixed(nodes, options) {
  var fragment = document.createDocumentFragment();
  nodes.forEach(function (node) {
    if (node.type === "text") {
      /* Legacy-HTML: серверно санитизирован на записи (design §6) —
       * существующий путь page.js (template.innerHTML, scripts не
       * исполняются). Это ЕДИНСТВЕННЫЙ innerHTML; rich-блоки — только
       * createElement/textContent. */
      var template = document.createElement("template");
      template.innerHTML = node.text;
      fragment.appendChild(template.content);
    } else {
      fragment.appendChild(renderNode(node, options));
    }
  });
  return fragment;
}

/* ------------------------------------------------------------------ */
/* Канва редактора (design §4): модель {nodes, element} + рендер с      */
/* привязками правки. Один и тот же renderNode, что на просмотре        */
/* (FR-124 по построению). Используется editor.js (1.6) и block-        */
/* модулями для вложенных канв (колонки/callout/врезка/спойлер — 2.5).  */
/* ------------------------------------------------------------------ */

/* special-узел ТОЛЬКО верхнего уровня документа: legacy-HTML сегмент
 * (серверно санитизирован на записи) — правится как раньше, целиком. */
export function legacyHtmlNode(html) {
  return { type: "legacyhtml", html: html };
}

/*
 * ctx = {
 *   editing: true|false,
 *   onChange(): контент изменился (editor — пометка «есть правки»),
 *   registerCanvas(canvas): редактор запоминает канву для тулбара,
 *   refreshCanvas(canvas): перерендер канвы после структурной правки,
 *   requestCanvas(element): активная канва по сфокусированному элементу.
 * }
 */
export function renderCanvas(canvas, ctx) {
  var element = canvas.element;
  element.textContent = "";
  element.__richCanvas = canvas;
  canvas.nodes.forEach(function (node, index) {
    var rendered;
    if (node.type === "legacyhtml") {
      rendered = el("div", "rich-legacy");
      rendered.contentEditable = "true";
      rendered.innerHTML = node.html; // legacy-HTML, санитизирован сервером
      /* Запись правок через MutationObserver: внутри contenteditable-канвы
       * события input от вложенных editing host'ов всплывают до editing host
       * канвы (target — не элемент), поэтому наблюдаем изменения DOM. */
      observeWriteBack(rendered, function () {
        node.html = rendered.innerHTML;
        ctx.onChange();
      });
    } else if (node.type === "text") {
      rendered = el("div", "rich-textline");
      if (ctx.editing) {
        rendered.contentEditable = "true";
        rendered.innerText = unfolded(node.text);
        observeWriteBack(rendered, function () {
          node.text = folded(rendered.innerText);
          ctx.onChange();
        });
      } else {
        appendTextParagraphs(rendered, node.text);
      }
    } else {
      rendered = el("div", "rich-block rich-block-" + node.type);
      rendered.appendChild(renderNode(node, { editing: ctx.editing, ctx: ctx }));
      if (ctx.editing) {
        var module = getBlock(node.type);
        if (module && typeof module.editControls === "function") {
          rendered.appendChild(module.editControls(node, ctx));
        }
      }
    }
    rendered.__richIndex = index;
    rendered.__richCanvas = canvas;
    element.appendChild(rendered);
  });
  if (ctx.editing && ctx.registerCanvas) ctx.registerCanvas(canvas);
  return element;
}

/* Экранированный текст sanitize_rich → литералы для contenteditable и
 * обратно (в диалект текст пишется в канонической экранированной форме —
 * зеркально backend sanitize_rich). &amp; НЕ разворачивается: бэкенд его
 * не создает, декодирование мутировало бы литеральный «&amp;» пользователя
 * в «&» при сохранении — roundtrip-сохранность (review-001-4.1 #4). */
function unfolded(text) {
  return String(text).replace(/&lt;/g, "<").replace(/&gt;/g, ">");
}

function folded(text) {
  return String(text).replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* Привязка правки через MutationObserver (см. комментарий в renderCanvas):
 * изменения текста/структуры редактируемого элемента → writeback в узел. */
export function observeWriteBack(element, write) {
  var observer = new MutationObserver(function () {
    write();
  });
  observer.observe(element, {
    characterData: true,
    childList: true,
    subtree: true,
    attributes: true,
  });
  return observer;
}

