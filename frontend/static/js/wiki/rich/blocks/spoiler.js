/* rich/blocks/spoiler.js — спойлер-блок (tasks.md 2.2; design §2; FR-121).
 *
 * Заголовок + скрытое содержимое; на просмотре содержимое скрыто до
 * действия читателя, раскрытие БЕЗ перезагрузки (toggle класса); после
 * перезагрузки снова скрыт — персистенции раскрытия НЕТ (FR-121).
 */

"use strict";

import { el, renderCanvas } from "../renderer.js";
import { serializeNodes, registerBlock } from "../block-parser.js";

function serialize(node) {
  var title = node.title.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  return ':::spoiler title="' + title + '"\n' + serializeNodes(node.children) + "\n:::";
}

function render(node, h, options) {
  var box = el("section", "rich-spoiler");

  var toggle = el("button", "rich-spoiler-toggle");
  toggle.type = "button";
  toggle.setAttribute("aria-expanded", "false");
  toggle.appendChild(el("span", "rich-spoiler-arrow", "▸"));
  toggle.appendChild(el("span", "rich-spoiler-title", unfolded(node.title)));
  toggle.addEventListener("click", function () {
    /* Раскрытие без перезагрузки (FR-121); без персистенции */
    var open = box.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    body.hidden = !open;
  });
  box.appendChild(toggle);

  var body = el("div", "rich-spoiler-body");
  body.hidden = true; // содержимое скрыто на свежей загрузке (FR-121)
  if (options.editing) {
    body.hidden = false; // в редакторе содержимое правится открыто
    renderCanvas({ nodes: node.children, element: body }, options.ctx);
  } else {
    body.appendChild(h.renderChildren(node.children));
  }
  box.appendChild(body);
  return box;
}

function unfolded(text) {
  return String(text).replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}

/* Правка заголовка (текстChildren не затрагиваются). */
function editControls(node, ctx) {
  var bar = el("div", "rich-controls");
  var input = el("input", "rich-control-input");
  input.type = "text";
  input.value = unfolded(node.title);
  input.setAttribute("aria-label", "Заголовок спойлера");
  input.addEventListener("input", function () {
    node.title = String(input.value).replace(/</g, "&lt;").replace(/>/g, "&gt;");
    /* Заголовок на кнопке спойлера обновляется сразу (без перерендера) */
    var block = input.closest(".rich-block");
    var label = block && block.querySelector(".rich-spoiler-title");
    if (label) label.textContent = unfolded(node.title);
    ctx.onChange();
  });
  bar.appendChild(input);
  return bar;
}

function toolbar() {
  return {
    label: "Спойлер",
    makeNode: function () {
      return {
        type: "spoiler",
        title: "Спойлер",
        children: [{ type: "text", text: "" }],
      };
    },
  };
}

var module = { type: "spoiler", serialize: serialize, render: render, editControls: editControls, toolbar: toolbar };
export default module;

registerBlock(module);
