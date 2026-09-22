/* SVG-иконки приоритетов (5.2, tasks.md; FR-29, ОГР-8, Д-4): inline SVG
 * без внешних библиотек — ↓ (low), = (medium), ↑ (high); рисуются
 * currentColor, цвет дает бейдж-обертка. Различимость без цвета —
 * иконка + текст («Низкий/Средний/Высокий») всегда вместе (FR-29).
 * createSvgNode — через createElementNS + setAttribute (innerHTML не
 * используется: XSS-политика dom.js, ОГР-11).
 */
"use strict";

var SVG_NS = "http://www.w3.org/2000/svg";

/* Пути иконок — дословно эталон design/form-style-v3.html (viewBox 0 0 14 14). */
var PRIO_PATHS = {
  low: "M7 2v9M3.5 7.5L7 11l3.5-3.5",
  medium: "M3 5h8M3 9h8",
  high: "M7 12V3M3.5 6.5L7 3l3.5 3.5",
};

export function createPriorityIcon(priority, size, strokeWidth) {
  var svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("viewBox", "0 0 14 14");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", strokeWidth);
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", "prio-icon");
  var path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", PRIO_PATHS[priority] || PRIO_PATHS.medium);
  svg.appendChild(path);
  return svg;
}

/* Человеческие подписи приоритетов (5.2): текст в бейджах и в деталях —
 * различимость без цвета + без знания иконок (FR-29, эталон V3). */
export var PRIORITY_LABELS = {
  low: "Низкий",
  medium: "Средний",
  high: "Высокий",
};

export function priorityLabel(priority) {
  return PRIORITY_LABELS[priority] || priority;
}
