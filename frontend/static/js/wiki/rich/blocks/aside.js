/* rich/blocks/aside.js — врезка (tasks.md 2.1б; design §2; FR-120).
 *
 * Оформление, отличное и от абзаца, и от callout (селекторы в wiki.css:
 * акцентная линия слева, без цветовой заливки типов callout).
 */

"use strict";

import { el, renderCanvas } from "../renderer.js";
import { serializeNodes, registerBlock } from "../block-parser.js";

function serialize(node) {
  return ":::aside\n" + serializeNodes(node.children) + "\n:::";
}

function render(node, h, options) {
  var box = el("aside", "rich-aside");
  if (options.editing) {
    renderCanvas({ nodes: node.children, element: box }, options.ctx);
  } else {
    box.appendChild(h.renderChildren(node.children));
  }
  return box;
}

function toolbar() {
  return {
    label: "Врезка",
    makeNode: function () {
      return { type: "aside", children: [{ type: "text", text: "" }] };
    },
  };
}

var module = { type: "aside", serialize: serialize, render: render, toolbar: toolbar };
export default module;

registerBlock(module);
