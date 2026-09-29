/* Единый tooltip-механизм (tasks.md 3.2 add-r4-user-profile-ticket-view;
 * FR-43, ОГР-17, ОВ-25; design пакета §5, TC-vis-105).
 *
 * ES-модуль без зависимостей (ОГР-1, ванильный JS). Один экземпляр
 * всплывашки на документ (div#app-tooltip, role="tooltip") переиспользуется
 * всеми целями — профиль внизу сайдбара (3.2) и карточки задач доски/поиска
 * (5.1, assigned/creator) — ОГР-17 «единый механизм».
 *
 * Публичный API (для переиспользования в 5.1):
 * - show(target, content) — показать всплывашку у target немедленно;
 *   content — DOM-узел (рендерится вызывающей стороной из уже загруженных
 *   данных, design §5: без отдельных запросов) или строка (textContent);
 *   возвращает элемент всплывашки.
 * - hide() — скрыть всплывашку.
 * - attach(target, buildContent, options) — привязать показ по
 *   hover/focus со задержкой (options.delay, мс, по умолчанию 300 —
 *   всплывашка не мешает клику по target) и скрытие по mouseleave/
 *   focusout/Escape; buildContent() — фабрика узла контента (свежий узел
 *   на каждый показ). Возвращает detach().
 *
 * Позиционирование (design §5): у нижнего левого края target; при нехватке
 * места снизу (профиль у нижнего края вьюпорта — риск design §11) —
 * подбор позиции ВВЕРХ; по горизонтали клампится в вьюпорт. Позиция fixed
 * по getBoundingClientRect — не зависит от скролла/position родителей.
 *
 * Доступность: role="tooltip" + aria-describedby на target на время
 * показа; скрытие по blur (focusout)/mouseleave/Escape; при
 * prefers-reduced-motion: reduce анимация появления/скрытия отключена
 * CSS-ом (app.css, TC-vis-105) — появляется мгновенно (ОГР-17).
 *
 * pointer-events: none на всплывашке (CSS) — она никогда не перехватывает
 * клик по target (сценарий «Клик по профилю открывает настройки»).
 *
 * XSS-дисциплина (как profile.js): контент-строка пишется через
 * textContent; узлы — только созданные вызывающей стороной
 * (createElement + textContent).
 */
"use strict";

const TOOLTIP_ID = "app-tooltip";
const HIDE_DELAY_MS = 250; /* >= --speed-fast (160ms): дать transition скрытия доиграть */

let tooltipEl = null;
let currentTarget = null;
let hideTimer = null;

function ensureTooltip() {
  if (tooltipEl && document.body.contains(tooltipEl)) {
    return tooltipEl;
  }
  tooltipEl = document.createElement("div");
  tooltipEl.id = TOOLTIP_ID;
  tooltipEl.className = "app-tooltip";
  tooltipEl.setAttribute("role", "tooltip");
  tooltipEl.hidden = true;
  document.body.appendChild(tooltipEl);
  return tooltipEl;
}

function positionAt(target, tip) {
  const margin = 8;
  const gap = 8;
  const rect = target.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  /* Замер по нулевой позиции, чтобы ширина/высота не влияли на кламп. */
  tip.style.left = "0px";
  tip.style.top = "0px";
  const tipWidth = tip.offsetWidth;
  const tipHeight = tip.offsetHeight;

  /* Левый край — у левого края target, но не за вьюпорт. */
  let left = rect.left;
  left = Math.max(margin, Math.min(left, viewportWidth - tipWidth - margin));

  /* По умолчанию — под target (нижний левый край); не влезает снизу —
   * вверх (профиль висит у нижнего края вьюпорта, design §11). */
  let top = rect.bottom + gap;
  if (top + tipHeight > viewportHeight - margin) {
    top = rect.top - tipHeight - gap;
  }
  if (top < margin) {
    top = margin;
  }

  tip.style.left = String(Math.round(left)) + "px";
  tip.style.top = String(Math.round(top)) + "px";
}

export function show(target, content) {
  const tip = ensureTooltip();
  if (hideTimer !== null) {
    window.clearTimeout(hideTimer);
    hideTimer = null;
  }

  if (typeof content === "string") {
    tip.textContent = content;
  } else if (content) {
    tip.replaceChildren(content);
  } else {
    tip.replaceChildren();
  }

  tip.hidden = false;
  positionAt(target, tip);

  /* reflow между hidden=false и классом — иначе transition от opacity:0
   * не стартует (браузер схлопнул бы оба изменения в один кадр). */
  void tip.offsetWidth;
  tip.classList.add("tooltip-visible");

  target.setAttribute("aria-describedby", TOOLTIP_ID);
  currentTarget = target;
  return tip;
}

export function hide() {
  if (!tooltipEl || tooltipEl.hidden) {
    return;
  }
  tooltipEl.classList.remove("tooltip-visible");
  if (currentTarget) {
    currentTarget.removeAttribute("aria-describedby");
    currentTarget = null;
  }
  const tip = tooltipEl;
  hideTimer = window.setTimeout(function () {
    tip.hidden = true;
    hideTimer = null;
  }, HIDE_DELAY_MS);
}

export function attach(target, buildContent, options) {
  const delay = options && typeof options.delay === "number" ? options.delay : 300;
  let showTimer = null;

  function cancelPendingShow() {
    if (showTimer !== null) {
      window.clearTimeout(showTimer);
      showTimer = null;
    }
  }

  function requestShow() {
    cancelPendingShow();
    showTimer = window.setTimeout(function () {
      showTimer = null;
      show(target, buildContent());
    }, delay);
  }

  function requestHide() {
    cancelPendingShow();
    hide();
  }

  function onKeydown(event) {
    if (event.key === "Escape") {
      cancelPendingShow();
      hide();
    }
  }

  target.addEventListener("mouseenter", requestShow);
  target.addEventListener("mouseleave", requestHide);
  target.addEventListener("focusin", requestShow);
  target.addEventListener("focusout", requestHide);
  target.addEventListener("keydown", onKeydown);

  return function detach() {
    cancelPendingShow();
    target.removeEventListener("mouseenter", requestShow);
    target.removeEventListener("mouseleave", requestHide);
    target.removeEventListener("focusin", requestShow);
    target.removeEventListener("focusout", requestHide);
    target.removeEventListener("keydown", onKeydown);
  };
}
