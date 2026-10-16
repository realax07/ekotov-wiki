/* rich/blocks/columns.js — блок-модуль многоколоночного блока (tasks.md
 * 1.5б; design §2; FR-118, FR-127).
 *
 * Колонки ≥2, порядок слева направо (FR-118), содержимое колонки —
 * вложенные блоки/текст (FR-127: таблица в колонке, код во врезке и т.п. —
 * вложенная канва того же renderCanvas, что и верхний уровень).
 * Ядро парсера отвечает за разбор :::columns/<<< (зеркало бэкенда);
 * модуль — сериализация, рендер рядом и правка структуры.
 */

"use strict";

import { el, renderCanvas } from "../renderer.js";
import { serializeNodes, registerBlock } from "../block-parser.js";

function serialize(node) {
  var body = node.columns
    .map(function (column) {
      /* рекурсивная сериализация вложенных узлов (FR-127) */
      return serializeNodes(column);
    })
    .join("\n<<<\n");
  return ":::columns\n" + body + "\n:::";
}

/* Рендер: колонки рядом (CSS grid), слева направо в порядке узла. */
function render(node, h, options) {
  var box = el("div", "rich-columns");
  node.columns.forEach(function (column) {
    var columnEl = el("div", "rich-column");
    if (options.editing) {
      var canvas = { nodes: column, element: columnEl };
      renderCanvas(canvas, options.ctx);
    } else {
      columnEl.appendChild(h.renderChildren(column));
    }
    box.appendChild(columnEl);
  });
  return box;
}

/* Правка структуры (FR-118): + колонка (справа), − колонка (минимум 2). */
function editControls(node, ctx) {
  var bar = el("div", "rich-controls");
  bar.appendChild(controlButton("+ колонка", function () {
    node.columns.push([{ type: "text", text: "" }]);
    ctx.refreshActive();
  }));
  bar.appendChild(controlButton("− колонка", function () {
    if (node.columns.length > 2) {
      node.columns.pop();
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

/* Кнопка тулбара: вставка блока с двумя пустыми колонками. */
function toolbar() {
  return {
    label: "Колонки",
    makeNode: function () {
      return {
        type: "columns",
        columns: [
          [{ type: "text", text: "" }],
          [{ type: "text", text: "" }],
        ],
      };
    },
  };
}

var module = { type: "columns", serialize: serialize, render: render, editControls: editControls, toolbar: toolbar };
export default module;

/* Саморегистрация в реестре (design §2) — см. tables.js. */
registerBlock(module);
