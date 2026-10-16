/* rich/block-parser.js — фронтовый парсер диалекта rich-редактора
 * (change add-rich-editor, tasks.md 1.4а; design §1/§2; FR-117, FR-118,
 * FR-127).
 *
 * ЗЕРКАЛО грамматики backend/app/rich_blocks.py (design §4: фронтовый парсер
 * зеркалит серверный; идентичность проверяется тестом на общих grammar-
 * фикстурах). Отличие от сервера одно: строгий разбор бросает RichSyntaxError
 * с позицией строки — ошибки НОВОГО rich-контента показываются в редакторе ДО
 * отправки (design §1 fallback-политика: на сервере в этом случае 422 нет).
 *
 * Грамматика (design §1): GFM-таблицы; :::columns … ::: c <<<; :::callout
 * type=info|warn|success; :::aside; :::spoiler title="…"; ```lang … ```;
 * ![alt](src){width=N} (N∈10..100) — строка-кандидат в блок-изображение.
 *
 * Реестр блок-модулей (design §2): registerBlock(type, module) — контракт
 * модуля {type, parse?, serialize, render, toolbar?}; новый тип блока =
 * новый модуль + регистрация, без правки ядра.
 *
 * Vanilla ES-модуль (ОГР-8) — без внешних зависимостей.
 */

"use strict";

/* Типы контейнеров ::: (design §1). */
export var CONTAINER_TYPES = ["columns", "callout", "aside", "spoiler"];
export var CALLOUT_TYPES = ["info", "warn", "success"];

/* width∈10..100 — whitelist масштаба (tasks.md 1.2б; NFR-34 не меняется). */
export var WIDTH_MIN = 10;
export var WIDTH_MAX = 100;

var FENCE_RE = /^```(.*)$/;
var FENCE_CLOSE_RE = /^```\s*$/;
var CONTAINER_RE = /^:::([a-zA-Z]+)(.*)$/;
var CONTAINER_CLOSE_RE = /^:::\s*$/;
var COLUMN_SEP_RE = /^<<<\s*$/;
var SPOILER_TITLE_RE = /title="((?:[^"\\]|\\.)*)"/;
var CALLOUT_TYPE_RE = /type=([a-zA-Z]+)/;
var IMAGE_LINE_RE = /^!\[([^\]]*)\]\(([^)\s]+)\)(?:\{width=(\d+)\})?\s*$/;

/* Строгая ошибка структуры (позиция строки — 1-базная, как на сервере). */
export function RichSyntaxError(message, line) {
  var error = new Error(message + " (строка " + line + ")");
  error.name = "RichSyntaxError";
  error.line = line;
  return error;
}

/* ------------------------------------------------------------------ */
/* Реестр блок-модулей (design §2)                                     */
/* ------------------------------------------------------------------ */

var registry = Object.create(null);

export function registerBlock(module) {
  registry[module.type] = module;
}

export function getBlock(type) {
  return registry[type] || null;
}

export function registeredTypes() {
  return Object.keys(registry);
}

/* ------------------------------------------------------------------ */
/* Узлы дерева: {type, ...} — те же формы, что на сервере              */
/* ------------------------------------------------------------------ */

function textNode(text) {
  return { type: "text", text: text };
}

/* ------------------------------------------------------------------ */
/* Таблицы (FR-117) — GFM, \| экранированная черта                     */
/* ------------------------------------------------------------------ */

function splitRow(line) {
  var body = line.trim();
  if (body.charAt(0) === "|") body = body.slice(1);
  if (body.slice(-1) === "|" && body.slice(-2) !== "\\|") body = body.slice(0, -1);
  var cells = [];
  var buffer = "";
  var escaped = false;
  for (var i = 0; i < body.length; i += 1) {
    var char = body.charAt(i);
    if (escaped) {
      buffer += char === "|" ? "|" : "\\" + char;
      escaped = false;
      continue;
    }
    if (char === "\\") {
      escaped = true;
      continue;
    }
    if (char === "|") {
      cells.push(buffer.trim());
      buffer = "";
      continue;
    }
    buffer += char;
  }
  if (escaped) buffer += "\\";
  cells.push(buffer.trim());
  return cells;
}

function parseAlign(cell) {
  var stripped = cell.trim().replace(/ /g, "");
  if (!stripped || /[^\-:]/.test(stripped)) return null;
  var left = stripped.charAt(0) === ":";
  var right = stripped.charAt(stripped.length - 1) === ":";
  if (left && right) return "center";
  if (right) return "right";
  if (left) return "left";
  return "default";
}

function serializeAlign(align) {
  return { default: "---", left: ":---", center: ":---:", right: "---:" }[align] || "---";
}

function tryParseTable(lines, start) {
  if (start + 1 >= lines.length) return null;
  if (lines[start].trim().charAt(0) !== "|") return null;
  var header = splitRow(lines[start]);
  if (header.length === 0) return null;
  var sepCells = splitRow(lines[start + 1]);
  if (sepCells.length !== header.length) return null;
  var aligns = [];
  for (var i = 0; i < sepCells.length; i += 1) {
    var align = parseAlign(sepCells[i]);
    if (align === null) return null;
    aligns.push(align);
  }
  var rows = [];
  var pos = start + 2;
  while (pos < lines.length && lines[pos].trim().charAt(0) === "|") {
    var cells = splitRow(lines[pos]);
    while (cells.length < header.length) cells.push("");
    rows.push(cells.slice(0, header.length));
    pos += 1;
  }
  return [{ type: "table", header: header, align: aligns, rows: rows }, pos];
}

function escapeCell(cell) {
  return cell.replace(/\\\|/g, "\\\\|").replace(/\|/g, "\\|");
}

function serializeTable(node) {
  var lines = ["| " + node.header.map(escapeCell).join(" | ") + " |"];
  lines.push("| " + node.align.map(serializeAlign).join(" | ") + " |");
  node.rows.forEach(function (row) {
    lines.push("| " + row.map(escapeCell).join(" | ") + " |");
  });
  return lines.join("\n");
}

/* ------------------------------------------------------------------ */
/* Изображение с масштабом (FR-123)                                    */
/* ------------------------------------------------------------------ */

function parseImageLine(line) {
  var match = IMAGE_LINE_RE.exec(line);
  if (!match) return null;
  var width = null;
  if (match[3] !== undefined) {
    var candidate = parseInt(match[3], 10);
    if (candidate >= WIDTH_MIN && candidate <= WIDTH_MAX) width = candidate;
  }
  return { type: "image", alt: match[1], src: match[2], width: width };
}

function serializeImage(node) {
  var line = "![" + node.alt + "](" + node.src + ")";
  if (node.width !== null && node.width !== undefined) {
    line += "{width=" + node.width + "}";
  }
  return line;
}

/* ------------------------------------------------------------------ */
/* Контейнеры ::: (рекурсивно, FR-127)                                 */
/* ------------------------------------------------------------------ */

function parseSpoilerTitle(attrs, lineNo) {
  var match = SPOILER_TITLE_RE.exec(attrs);
  if (!match) throw RichSyntaxError('spoiler требует title="…"', lineNo);
  return match[1].replace(/\\"/g, '"').replace(/\\\\/g, "\\");
}

function serializeSpoilerTitle(title) {
  return title.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

/* Толерантный fallback (ревью A-2): сырые строки кандидата → текст. */
function fallbackText(lines, start) {
  var collected = [];
  var pos = start;
  while (pos < lines.length) {
    collected.push(lines[pos]);
    if (CONTAINER_CLOSE_RE.test(lines[pos])) {
      return [textNode(collected.join("\n")), pos + 1, true];
    }
    pos += 1;
  }
  return [textNode(collected.join("\n")), pos, false];
}

function parseContainer(lines, start, blockType, attrs, strict, warnings) {
  var lineNo = start + 1;
  if (blockType === "columns") {
    return parseColumns(lines, start, strict, warnings, fallbackText(lines, start));
  }
  var parsed;
  try {
    if (blockType === "spoiler") parseSpoilerTitle(attrs, lineNo);
  } catch (error) {
    if (strict) throw error;
    warnings.push("строка " + lineNo + ": spoiler без title — текст");
    return fallbackText(lines, start);
  }
  parsed = parseLines(lines, start + 1, true, strict, warnings);
  if (!parsed[2]) {
    if (strict) {
      throw RichSyntaxError("незакрытый контейнер :::" + blockType, lineNo);
    }
    warnings.push("строка " + lineNo + ": незакрытый :::" + blockType + " — текст");
    return fallbackText(lines, start);
  }
  if (blockType === "callout") {
    var match = CALLOUT_TYPE_RE.exec(attrs);
    var value = match ? match[1].toLowerCase() : "";
    if (CALLOUT_TYPES.indexOf(value) === -1) {
      if (strict) {
        throw RichSyntaxError("callout требует type=info|warn|success", lineNo);
      }
      warnings.push("строка " + lineNo + ": callout с недопустимым type — текст");
      return fallbackText(lines, start);
    }
    return [{ type: "callout", callout_type: value, children: parsed[0] }, parsed[1], true];
  }
  if (blockType === "aside") {
    return [{ type: "aside", children: parsed[0] }, parsed[1], true];
  }
  return [
    { type: "spoiler", title: parseSpoilerTitle(attrs, lineNo), children: parsed[0] },
    parsed[1],
    true,
  ];
}

function parseColumns(lines, start, strict, warnings, fallback) {
  var lineNo = start + 1;
  var segments = [[]];
  var depth = 0;
  var inFence = false;
  var pos = start + 1;
  var closed = false;
  while (pos < lines.length) {
    var line = lines[pos];
    if (inFence) {
      segments[segments.length - 1].push(line);
      if (FENCE_CLOSE_RE.test(line)) inFence = false;
      pos += 1;
      continue;
    }
    if (FENCE_RE.test(line)) {
      inFence = true;
      segments[segments.length - 1].push(line);
      pos += 1;
      continue;
    }
    if (CONTAINER_RE.test(line)) {
      depth += 1;
      segments[segments.length - 1].push(line);
      pos += 1;
      continue;
    }
    if (CONTAINER_CLOSE_RE.test(line)) {
      if (depth === 0) {
        closed = true;
        pos += 1;
        break;
      }
      depth -= 1;
      segments[segments.length - 1].push(line);
      pos += 1;
      continue;
    }
    if (depth === 0 && COLUMN_SEP_RE.test(line)) {
      segments.push([]);
      pos += 1;
      continue;
    }
    segments[segments.length - 1].push(line);
    pos += 1;
  }
  if (!closed) {
    if (strict) throw RichSyntaxError("незакрытый контейнер :::columns", lineNo);
    warnings.push("строка " + lineNo + ": незакрытый :::columns — текст");
    return fallback;
  }
  if (segments.length < 2) {
    if (strict) {
      throw RichSyntaxError("колонок меньше двух (нужен разделитель <<<)", lineNo);
    }
    warnings.push("строка " + lineNo + ": одна колонка в :::columns — текст");
    return fallback;
  }
  var columns = [];
  segments.forEach(function (segment) {
    columns.push(parseLines(segment, 0, false, strict, warnings)[0]);
  });
  return [{ type: "columns", columns: columns }, pos, true];
}

function serializeContainer(node) {
  if (node.type === "columns") {
    var body = node.columns
      .map(function (column) {
        return serializeNodes(column);
      })
      .join("\n<<<\n");
    return ":::columns\n" + body + "\n:::";
  }
  var opener;
  if (node.type === "callout") opener = ":::callout type=" + node.callout_type;
  else if (node.type === "spoiler") {
    opener = ':::spoiler title="' + serializeSpoilerTitle(node.title) + '"';
  } else opener = ":::" + node.type;
  return opener + "\n" + serializeNodes(node.children) + "\n:::";
}

/* ------------------------------------------------------------------ */
/* Ядро: построчный разбор                                             */
/* ------------------------------------------------------------------ */

function parseLines(lines, start, stopAtClose, strict, warnings) {
  var nodes = [];
  var textBuffer = [];
  var pos = start;

  function flushText() {
    if (textBuffer.length > 0) {
      nodes.push(textNode(textBuffer.join("\n")));
      textBuffer = [];
    }
  }

  while (pos < lines.length) {
    var line = lines[pos];

    if (stopAtClose && CONTAINER_CLOSE_RE.test(line)) {
      flushText();
      return [nodes, pos + 1, true];
    }

    var fence = FENCE_RE.exec(line);
    if (fence) {
      var close = null;
      for (var scan = pos + 1; scan < lines.length; scan += 1) {
        if (FENCE_CLOSE_RE.test(lines[scan])) {
          close = scan;
          break;
        }
      }
      if (close === null) {
        if (strict) throw RichSyntaxError("незакрытый fenced code ```", pos + 1);
        warnings.push("строка " + (pos + 1) + ": незакрытый ``` — текст");
        textBuffer.push(line);
        pos += 1;
        continue;
      }
      flushText();
      nodes.push({ type: "code", lang: fence[1].trim(), code: lines.slice(pos + 1, close).join("\n") });
      pos = close + 1;
      continue;
    }

    var container = CONTAINER_RE.exec(line);
    if (container) {
      var blockType = container[1].toLowerCase();
      if (CONTAINER_TYPES.indexOf(blockType) === -1) {
        if (strict) {
          throw RichSyntaxError("неизвестный тип контейнера :::" + blockType, pos + 1);
        }
        warnings.push("строка " + (pos + 1) + ": неизвестный контейнер — текст");
        textBuffer.push(line);
        pos += 1;
        continue;
      }
      flushText();
      var parsed = parseContainer(lines, pos, blockType, container[2], strict, warnings);
      if (parsed[0].type === "text") textBuffer.push(parsed[0].text);
      else nodes.push(parsed[0]);
      pos = parsed[1];
      continue;
    }

    if (COLUMN_SEP_RE.test(line)) {
      if (strict) throw RichSyntaxError("<<< вне контейнера :::columns", pos + 1);
      warnings.push("строка " + (pos + 1) + ": <<< вне колонок — текст");
      textBuffer.push(line);
      pos += 1;
      continue;
    }

    if (line.trim().charAt(0) === "|") {
      var candidate = tryParseTable(lines, pos);
      if (candidate) {
        flushText();
        nodes.push(candidate[0]);
        pos = candidate[1];
        continue;
      }
      /* GFM-шапка без валидного разделителя — НЕ блок (legacy-текст) */
    }

    var image = parseImageLine(line.trim());
    if (image) {
      flushText();
      nodes.push(image);
      pos += 1;
      continue;
    }

    textBuffer.push(line);
    pos += 1;
  }

  flushText();
  return [nodes, pos, false];
}

/* Толерантный разбор (fallback-политика design §1): кандидат не блока —
 * текст; исключений не бросает. */
export function parse(content) {
  if (content === "") return [];
  return parseLines(String(content).split("\n"), 0, false, false, [])[0];
}

/* Строгий разбор (новый rich-контент в редакторе): структурная ошибка →
 * RichSyntaxError с позицией строки (зеркало rich_blocks.validate). */
export function parseStrict(content) {
  return parseLines(String(content).split("\n"), 0, false, true, [])[0];
}

export function validate(content) {
  return parseStrict(content);
}

export function hasRichBlocks(nodes) {
  for (var i = 0; i < nodes.length; i += 1) {
    if (nodes[i].type !== "text") return true;
  }
  return false;
}

export function contentHasBlocks(content) {
  if (typeof content !== "string") return hasRichBlocks(content);
  return hasRichBlocks(parse(content));
}

/* ------------------------------------------------------------------ */
/* Сериализация (зеркало rich_blocks.serialize_nodes)                  */
/* ------------------------------------------------------------------ */

export function serializeNodes(nodes) {
  return nodes.map(serializeNode).join("\n");
}

function serializeNode(node) {
  if (node.type === "text") return node.text;
  var module = getBlock(node.type);
  if (module && typeof module.serialize === "function") {
    return module.serialize(node);
  }
  if (node.type === "table") return serializeTable(node);
  if (node.type === "code") return "```" + node.lang + "\n" + node.code + "\n```";
  if (node.type === "image") return serializeImage(node);
  return serializeContainer(node);
}

export function serialize(contentOrNodes) {
  if (typeof contentOrNodes === "string") return serializeNodes(parse(contentOrNodes));
  return serializeNodes(contentOrNodes);
}
