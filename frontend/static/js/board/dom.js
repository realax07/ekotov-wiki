/* DOM-хелперы (P6: извлечены из board.js; используются модулями доски).
 * XSS (ОГР-11): рендер пользовательских данных — только через
 * textContent (фабрика el, показ/скрытие ошибок); innerHTML не
 * используется.
 */
"use strict";

export function el(tag, className, text) {
  var node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

/* Ошибка загрузки доски (board-error под столбцами). */
export function showBoardError(message) {
  var box = document.getElementById("board-error");
  box.textContent = message;
  box.hidden = false;
}

export function showFormError(id, message) {
  var box = document.getElementById(id);
  if (box) {
    box.textContent = message;
    box.hidden = false;
  }
}

export function hideError(id) {
  var box = document.getElementById(id);
  if (box) {
    box.textContent = "";
    box.hidden = true;
  }
}
