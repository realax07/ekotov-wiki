/* rich/blocks/tables.js — блок-модуль таблицы (tasks.md 1.5а; design §2;
 * FR-117).
 *
 * Контракт block-модуля (design §2): {type, serialize, render, toolbar} —
 * регистрируется в реестре block-parser.js. GFM-распознавание строк — в
 * ядре парсера (зеркало rich_blocks.py, построчная грамматика не может
 * жить в модуле); модуль дает каноническую сериализацию, рендер и
 * редактирование структуры (строки/столбцы/ячейки).
 *
 * Ячейки — только textContent (XSS: NFR-35 defense-in-depth).
 */

"use strict";

import { el, renderInline } from "../renderer.js";
import { registerBlock } from "../block-parser.js";

function serialize(node) {
  var lines = ["| " + node.header.map(escapeCell).join(" | ") + " |"];
  lines.push("| " + node.align.map(serializeAlign).join(" | ") + " |");
  node.rows.forEach(function (row) {
    lines.push("| " + row.map(escapeCell).join(" | ") + " |");
  });
  return lines.join("\n");
}

function escapeCell(cell) {
  return cell.replace(/\\\|/g, "\\\\|").replace(/\|/g, "\\|");
}

function serializeAlign(align) {
  return { default: "---", left: ":---", center: ":---:", right: "---:" }[align] || "---";
}

function alignClass(align) {
  return { left: "is-left", center: "is-center", right: "is-right" }[align] || "";
}

/* Рендер таблицы: thead/tbody, выравнивание колонок по канонической
 * форме; editing=true — ячейки contenteditable c записью в узел. */
function render(node, h, options) {
  var table = el("table", "rich-table");
  var thead = el("thead");
  var headRow = el("tr");
  node.header.forEach(function (cell, col) {
    var th = el("th", alignClass(node.align[col]));
    bindCell(th, node.header, col, options);
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  var tbody = el("tbody");
  node.rows.forEach(function (row, rowIndex) {
    var tr = el("tr");
    row.forEach(function (cell, col) {
      var td = el("td", alignClass(node.align[col]));
      bindCell(td, node.rows[rowIndex], col, options);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  return wrap(table);
}

function bindCell(cell, row, col, options) {
  var text = String(row[col] || "")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
  renderInline(cell, text);
  if (options.editing) {
    cell.contentEditable = "true";
    cell.addEventListener("input", function () {
      row[col] = textToDialect(cell.innerText);
      if (options.ctx) options.ctx.onChange();
    });
  }
}

/* Экранирование < > в тексте ячеек — каноническая форма диалекта
 * (зеркало backend sanitize_rich). */
function textToDialect(text) {
  return String(text).replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function wrap(table) {
  /* Горизонтальный скролл на узком экране без развала структуры (NFR-23) */
  var wrapper = el("div", "rich-table-wrap");
  wrapper.appendChild(table);
  return wrapper;
}

/* Правка структуры (tasks.md 1.5а): строки/столбцы; ячейки правятся
 * прямо в таблице. Структура меняет узел + перерендер канвы. */
function editControls(node, ctx) {
  var bar = el("div", "rich-controls");
  bar.appendChild(controlButton("+ строка", function () {
    var width = node.header.length;
    node.rows.push(new Array(width).fill(""));
    ctx.refreshActive();
  }));
  bar.appendChild(controlButton("− строка", function () {
    if (node.rows.length > 1) {
      node.rows.pop();
      ctx.refreshActive();
    }
  }));
  bar.appendChild(controlButton("+ столбец", function () {
    node.header.push("");
    node.align.push("default");
    node.rows.forEach(function (row) {
      row.push("");
    });
    ctx.refreshActive();
  }));
  bar.appendChild(controlButton("− столбец", function () {
    if (node.header.length > 1) {
      node.header.pop();
      node.align.pop();
      node.rows.forEach(function (row) {
        row.pop();
      });
      ctx.refreshActive();
    }
  }));
  return bar;
}

function controlButton(label, onClick) {
  var button = el("button", "rich-control-btn", label);
  button.type = "button";
  button.addEventListener("click", function (event) {
    event.preventDefault();
    onClick();
  });
  return button;
}

/* Кнопка тулбара (tasks.md 1.4в): вставка таблицы 2×2 (шапка + строка). */
function toolbar() {
  return {
    label: "Таблица",
    makeNode: function () {
      return {
        type: "table",
        header: ["Колонка 1", "Колонка 2"],
        align: ["default", "default"],
        rows: [["", ""]],
      };
    },
  };
}

var module = { type: "table", serialize: serialize, render: render, editControls: editControls, toolbar: toolbar };
export default module;

/* Саморегистрация в реестре (design §2): импорт модуля = блок доступен
 * ядру парсера/рендера/тулбара. */
registerBlock(module);
