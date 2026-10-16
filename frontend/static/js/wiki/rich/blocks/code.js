/* rich/blocks/code.js — код-блок с выбором языка (tasks.md 2.3а; design §2;
 * FR-122).
 *
 * Переносы/пробелы — буквально, без типографской обработки (pre, white-space
 * сохраняется); содержимое — ВСЕГДА текст (XSS-вектор код-блока — буквальный
 * рендер, NFR-35). Подсветка — собственный токенайзер rich/highlight.js
 * (vanilla, ОГР-8; без внешних CDN — сетевых запросов нет, NFR-33).
 */

"use strict";

import { el, observeWriteBack } from "../renderer.js";
import { registerBlock } from "../block-parser.js";
import { highlightInto } from "../highlight.js";

/* Языки выбора (подсветка базовая; неизвестный/пустой — без подсветки) */
export var CODE_LANGS = ["", "python", "javascript", "json", "css", "html"];

function serialize(node) {
  return "```" + node.lang + "\n" + node.code + "\n```";
}

function unfoldEntities(text) {
  return String(text).replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}

function render(node, h, options) {
  var box = el("div", "rich-code");
  var pre = el("pre", "rich-code-pre");
  var code = el("code", "rich-code-code");
  pre.appendChild(code);
  highlightInto(code, unfoldEntities(node.code), node.lang);
  box.appendChild(pre);

  if (options.editing) {
    /* Правка: plain pre без подсветки (переключение кнопкой), запись в
       узел на ввод; на blur — возврат к подсвеченному виду. */
    var plain = el("pre", "rich-code-pre rich-code-plain");
    var plainCode = el("code", "rich-code-code");
    plainCode.contentEditable = "true";
    plainCode.spellcheck = false;
    plainCode.textContent = unfoldEntities(node.code);
    /* Правка кода: MutationObserver (события input внутри канвы всплывают
       до editing host канвы — см. renderer.observeWriteBack). */
    observeWriteBack(plainCode, function () {
      node.code = String(plainCode.textContent)
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
      if (options.ctx) options.ctx.onChange();
    });
    plain.hidden = true;
    box.appendChild(plain);

    var bar = el("div", "rich-controls");
    var editButton = el("button", "rich-control-btn", "Править код");
    editButton.type = "button";
    editButton.addEventListener("click", function () {
      var switchingToPlain = plain.hidden;
      plain.hidden = !switchingToPlain;
      pre.hidden = switchingToPlain;
      if (switchingToPlain) plainCode.focus();
      else highlightInto(code, unfoldEntities(node.code), node.lang);
      editButton.textContent = plain.hidden ? "Править код" : "Готово";
    });
    bar.appendChild(editButton);

    var select = el("select", "rich-control-select");
    select.setAttribute("aria-label", "Язык кода");
    CODE_LANGS.forEach(function (lang) {
      var option = el("option", null, lang === "" ? "без языка" : lang);
      option.value = lang;
      if (lang === node.lang) option.selected = true;
      select.appendChild(option);
    });
    select.addEventListener("change", function () {
      node.lang = select.value;
      highlightInto(code, unfoldEntities(node.code), node.lang);
      if (options.ctx) options.ctx.onChange();
    });
    bar.appendChild(select);
    box.appendChild(bar);
  }
  return box;
}

function toolbar() {
  return {
    label: "Код",
    makeNode: function () {
      return { type: "code", lang: "python", code: "" };
    },
  };
}

var module = { type: "code", serialize: serialize, render: render, toolbar: toolbar };
export default module;

registerBlock(module);
