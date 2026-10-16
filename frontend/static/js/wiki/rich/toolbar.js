/* rich/toolbar.js — расширение тулбара rich-блоками (tasks.md 1.4в;
 * design §2, §4).
 *
 * Каркас: кнопки вставки блоков строятся из реестра (module.toolbar() →
 * {label, makeNode()}); редактор (editor.js, 1.6) передает onInsert(makeNode)
 * — вставка в активную канву. Новый тип блока = новый модуль + регистрация,
 * тулбар расширяется без правки ядра. Доп. кнопки расширений — hook
 * registerExtraButton (2.5: вставка блока внутрь вложенной канвы).
 */

"use strict";

import { el } from "./renderer.js";
import { getBlock } from "./block-parser.js";

/* Дополнительные кнопки вне реестра блоков (hook расширений, design §2). */
var extraButtons = [];

export function registerExtraButton(definition) {
  extraButtons.push(definition);
}

export function resetExtraButtons() {
  extraButtons = [];
}

/* Порядок кнопок rich-блоков (мокап: после встроенных групп тулбара). */
var BLOCK_ORDER = ["table", "columns", "callout", "aside", "spoiler", "code", "image"];

/* Панель вставки rich-блоков. onInsert(makeNode, label) вызывает редактор:
 * блок из makeNode() уходит в активную канву. */
export function buildBlockBar(onInsert) {
  var bar = el("div", "tb-group rich-tb-group");
  bar.setAttribute("role", "group");
  bar.setAttribute("aria-label", "Вставка блоков");

  function addDefinition(definition) {
    var button = el("button", "tb-btn tb-btn-block", definition.label);
    button.type = "button";
    button.title = "Вставить: " + definition.label;
    button.setAttribute("aria-label", "Вставить блок «" + definition.label + "»");
    button.addEventListener("mousedown", function (event) {
      event.preventDefault(); // выделение в редакторе не сбивается
    });
    button.addEventListener("click", function () {
      onInsert(definition.makeNode, definition.label);
    });
    bar.appendChild(button);
  }

  BLOCK_ORDER.forEach(function (type) {
    var module = getBlock(type);
    if (module && typeof module.toolbar === "function") {
      addDefinition(module.toolbar());
    }
  });
  extraButtons.forEach(addDefinition);
  return bar;
}
