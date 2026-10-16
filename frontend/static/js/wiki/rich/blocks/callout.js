/* rich/blocks/callout.js — callout-блок info/warn/success (tasks.md 2.1а;
 * design §2; FR-119).
 *
 * Три типа с различимым цветовым оформлением (токены V3 из app.css :root,
 * без хардкода — селекторы в wiki.css); смена типа без потери текста
 * (меняется только атрибут узла, дети не трогаются — FR-119).
 * Разбор :::callout — в ядре парсера (зеркало бэкенда).
 */

"use strict";

import { el, renderCanvas } from "../renderer.js";
import { serializeNodes, registerBlock, CALLOUT_TYPES } from "../block-parser.js";

function serialize(node) {
  return ":::callout type=" + node.callout_type + "\n" + serializeNodes(node.children) + "\n:::";
}

function render(node, h, options) {
  var box = el(
    "div",
    "rich-callout rich-callout-" + node.callout_type
  );
  box.setAttribute("data-callout-type", node.callout_type);
  if (options.editing) {
    renderCanvas({ nodes: node.children, element: box }, options.ctx);
  } else {
    box.appendChild(h.renderChildren(node.children));
  }
  return box;
}

/* Смена типа без потери текста (FR-119): селект меняет атрибут узла. */
function editControls(node, ctx) {
  var bar = el("div", "rich-controls");
  var select = el("select", "rich-control-select");
  select.setAttribute("aria-label", "Тип callout");
  CALLOUT_TYPES.forEach(function (type) {
    var option = el("option", null, type);
    option.value = type;
    if (type === node.callout_type) option.selected = true;
    select.appendChild(option);
  });
  select.addEventListener("change", function () {
    node.callout_type = select.value; // дети (текст) не трогаются
    ctx.refreshActive();
  });
  bar.appendChild(select);
  return bar;
}

function toolbar() {
  return {
    label: "Callout",
    makeNode: function () {
      return {
        type: "callout",
        callout_type: "info",
        children: [{ type: "text", text: "" }],
      };
    },
  };
}

var module = { type: "callout", serialize: serialize, render: render, editControls: editControls, toolbar: toolbar };
export default module;

/* Саморегистрация в реестре (design §2) — см. tables.js. */
registerBlock(module);
