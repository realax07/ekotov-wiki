/* rich/blocks/image-scale.js — масштаб изображения (tasks.md 2.4; design §1,
 * §2; FR-123 — закрытие долга add-wiki).
 *
 * Контрол масштаба в редакторе: шаг/проценты доступной ширины, 10..100
 * (whitelist NFR-34 — лимиты/хранение изображений не меняются). Хранение
 * {width=N} в диалекте (атрибут 1.1); применение при каждом рендере и на
 * просмотре — style.width = N% (масштаб не сбрасывается при правке другого
 * фрагмента: узел хранится в канве и сериализуется целиком — круговое
 * сохранение).
 */

"use strict";

import { el, safeUrl } from "../renderer.js";
import { registerBlock, WIDTH_MIN, WIDTH_MAX } from "../block-parser.js";

var SCALE_STEP = 10;

function render(node, h, options) {
  var box = el("span", "rich-image");
  var width = node.width === null || node.width === undefined ? 100 : node.width;
  var src = safeUrl(node.src);
  if (src) {
    /* Второй слой защиты (NFR-35): небезопасная схема (javascript: и т.п.)
       не вставляется даже в узел вне sanitize_rich. */
    var img = document.createElement("img");
    img.src = src;
    img.alt = node.alt;
    img.style.width = width + "%";
    img.className = "rich-image-img";
    box.appendChild(img);
  }
  return box;
}

/* Контрол масштаба в редакторе (FR-123а): проценты доступной ширины. */
function editControls(node, ctx) {
  var bar = el("div", "rich-controls rich-image-controls");

  var label = el("label", null, "Масштаб, %");
  label.className = "rich-control-label";
  bar.appendChild(label);

  var minus = scaleButton("−", function () {
    node.width = clamp((node.width === null || node.width === undefined ? 100 : node.width) - SCALE_STEP);
    sync();
  });
  var plus = scaleButton("+", function () {
    node.width = clamp((node.width === null || node.width === undefined ? 100 : node.width) + SCALE_STEP);
    sync();
  });

  var input = el("input", "rich-control-input rich-image-input");
  input.type = "number";
  input.min = String(WIDTH_MIN);
  input.max = String(WIDTH_MAX);
  input.step = "1";
  input.value = String(node.width === null || node.width === undefined ? 100 : node.width);
  input.setAttribute("aria-label", "Масштаб изображения в процентах");

  function sync() {
    input.value = String(node.width === null || node.width === undefined ? 100 : node.width);
    ctx.refreshActive(); // перерендер канвы — img с новым width
  }

  input.addEventListener("change", function () {
    var value = parseInt(input.value, 10);
    if (Number.isFinite(value) && value >= WIDTH_MIN && value <= WIDTH_MAX) {
      node.width = value; // {width=N} в диалекте, круговое сохранение (FR-123в)
    } else {
      input.value = String(node.width === null || node.width === undefined ? 100 : node.width);
      return; // вне whitelist — масштаб не меняется
    }
    ctx.refreshActive();
  });

  bar.appendChild(minus);
  bar.appendChild(input);
  bar.appendChild(plus);
  return bar;
}

function scaleButton(label, onClick) {
  var button = el("button", "rich-control-btn rich-image-scale-btn", label);
  button.type = "button";
  button.addEventListener("click", function (event) {
    event.preventDefault();
    onClick();
  });
  return button;
}

function clamp(value) {
  if (value < WIDTH_MIN) return WIDTH_MIN;
  if (value > WIDTH_MAX) return WIDTH_MAX;
  return value;
}

function toolbar() {
  return {
    label: "Изображение",
    makeNode: function () {
      return { type: "image", alt: "", src: "/images/", width: 100 };
    },
  };
}

var module = { type: "image", render: render, editControls: editControls, toolbar: toolbar };
export default module;

/* Сериализация — канонический встроенный сериализатор ядра (![alt](src){width=N});
 * регистрация в реестре (design §2). */
registerBlock(module);
