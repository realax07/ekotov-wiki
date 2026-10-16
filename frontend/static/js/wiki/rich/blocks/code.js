/* rich/blocks/code.js — код-блок с выбором языка (tasks.md 2.3а; design §2;
 * FR-122).
 *
 * Переносы/пробелы — буквально, без типографской обработки (pre, white-space
 * сохраняется); содержимое — ВСЕГДА текст (XSS-вектор код-блока — буквальный
 * рендер, NFR-35). Подсветка — собственный токенайзер rich/highlight.js
 * (vanilla, ОГР-8; без внешних CDN — сетевых запросов нет, NFR-33).
 *
 * BUG-020 (живая приемка p15-wiki-8, решение Заказчика дословно: «нужна
 * только подсветка синтаксиса и графический фон»): режим/кнопка «править
 * код» УДАЛЕНЫ. Код — обычный редактируемый текст прямо в блоке
 * (моноширинный, графический фон rich-code); подсветка поверх — рендер
 * токенайзером, при blur переподсвечивается. Сохранение 1:1 (FR-122):
 * запись в узел — по текстовому содержимому DOM (BR → \n).
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

function foldCode(text) {
  /* Каноническая экранированная форма диалекта (зеркало sanitize_rich;
   * &amp; не создаем — бэкенд его не экранирует, roundtrip-сохранность). */
  return String(text).replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* Текстовое содержимое редактируемого кода 1:1: текстовые узлы как есть,
 * <br> → \n (Chromium вставляет br при Enter в части состояний editing
 * host'а), пустые блочные дети (div/p) → \n. FR-122: переносы/пробелы
 * буквально. */
function codeToText(host) {
  var out = "";
  Array.prototype.forEach.call(host.childNodes, function (child) {
    if (child.nodeType === 3) {
      out += child.data;
    } else if (child.nodeName === "BR") {
      out += "\n";
    } else {
      out += codeToText(child);
      if (
        (child.nodeName === "DIV" || child.nodeName === "P") &&
        child.childNodes.length === 0
      ) {
        out += "\n";
      }
    }
  });
  return out;
}

function writeBack(code, node, ctx) {
  var value = foldCode(codeToText(code));
  if (node.code !== value) {
    node.code = value;
    if (ctx) ctx.onChange();
  }
}

function render(node, h, options) {
  var box = el("div", "rich-code");
  var pre = el("pre", "rich-code-pre");
  var code = el("code", "rich-code-code");
  pre.appendChild(code);
  highlightInto(code, unfoldEntities(node.code), node.lang);
  box.appendChild(pre);

  if (options.editing) {
    /* Правка прямо в блоке: editing host — pre (блочный, кликабелен целиком,
     * включая ПУСТОЙ код; вложенный инлайн host был ненадежен — caret
     * вставал на границу нулевого элемента и ввод терялся). Код правится
     * поверх подсветки; на blur — запись в узел и переподсветка. Никаких
     * режимов и кнопки «править код» — BUG-020. Запись правок в узел —
     * MutationObserver (события input внутри канвы всплывают до editing
     * host канвы — см. renderer.observeWriteBack). */
    pre.contentEditable = "true";
    pre.spellcheck = false;
    observeWriteBack(pre, function () {
      writeBack(pre, node, options.ctx);
    });
    pre.addEventListener("focusout", function () {
      writeBack(pre, node, options.ctx);
      /* Канонизация: editing host вставляет текст узлами pre МИМО code —
         перед переподсветкой весь текст сворачивается в code, иначе после
         highlightInto текст задвоен (набранный + подсвеченный). Наблюдатель
         асинхронен: сработает один раз на итоговый DOM. */
      while (pre.firstChild !== code && pre.firstChild) {
        pre.removeChild(pre.firstChild);
      }
      while (pre.lastChild !== code && pre.lastChild) {
        pre.removeChild(pre.lastChild);
      }
      highlightInto(code, unfoldEntities(node.code), node.lang);
    });

    var bar = el("div", "rich-controls");
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
