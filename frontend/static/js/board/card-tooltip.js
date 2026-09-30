/*
 * Р5 polish (прод-репорт Заказчика): tooltip показывается ТОЛЬКО при
 * наведении на строку пользователей «assigned · creator» (строку строит
 * cards.js: buildAssigneeLine → .task-card-users), НЕ на всю карточку.
 * Зачем: карточка — зона drag (нативный HTML5 DnD, cards.js) и клика
 * (view-модалка) — всплывашка на всей площади мешала обзору и выглядела
 * как отклик на drag. Hover на заголовок/мету/тело карточки → всплывашки
 * НЕТ; drag карточки за остальную область — тоже без всплывашки.
 *
 * Экспортируется attachCardTooltip(target, task): cards.js передает
 * СТРОКУ пользователей. На карточках без строки (hasOwnProperty-гвард
 * в cards.js) tooltip не навешивается вовсе. Крупные карточки выдачи
 * поиска (search.js, «Исполнитель: … · Создатель: …») tooltip сейчас
 * не используют; если появятся — принцип тот же: таргет = строка
 * пользователей.
 *
 * Обертка над ПУБЛИЧНЫМ API единого модуля tooltip.js (attach — показ
 * по hover/focus с задержкой 300мс, скрытие по mouseleave/focusout/
 * Escape): тот же единственный на документ элемент #app-tooltip, что и
 * у профиля (ОГР-17 «единый механизм»), та же задержка, что у профиля
 * (profile.js attachProfileTooltip). Reduced-motion — CSS app.css
 * (transition: none при prefers-reduced-motion: reduce, TC-vis-105);
 * содержание при этом не меняется.
 *
 * Состав (ОВ-25/FR-44): «Исполнитель: <assigned или Unassigned курсивом>»,
 * «Создатель: <creator>». Контент строится из уже загруженных данных
 * карточки — отдельных запросов нет (design §5).
 *
 * Динамические карточки: attach навешивает обработчики на КОНКРЕТНЫЙ
 * элемент. renderCard создает новый элемент на каждую перерисовку —
 * detach не требуется (старые элементы уходят в garbage вместе со
 * своими обработчиками).
 *
 * Динамическое содержимое: buildContent вызывается на КАЖДЫЙ показ —
 * в узел пишутся значения task на момент рендера карточки.
 *
 * XSS (ОГР-11): значения — только через textContent (dom.js el).
 */
"use strict";

import { el } from "./dom.js";

/* Класс em «Unassigned» в tooltip — курсив задает элемент em (как
 * task-view-unassigned в view-модалке); цвет — board.css. */
function buildCardTooltipContent(task) {
  var box = el("div", "tooltip-task");

  var assignedRow = el("div", "tooltip-task-row");
  assignedRow.appendChild(el("span", "tooltip-task-label", "Исполнитель: "));
  if (task.assigned) {
    assignedRow.appendChild(el("span", "tooltip-task-value", String(task.assigned)));
  } else {
    assignedRow.appendChild(el("em", "task-card-unassigned", "Unassigned"));
  }
  box.appendChild(assignedRow);

  var creatorRow = el("div", "tooltip-task-row");
  creatorRow.appendChild(el("span", "tooltip-task-label", "Создатель: "));
  creatorRow.appendChild(
    el("span", "tooltip-task-value", task.creator ? String(task.creator) : "—")
  );
  box.appendChild(creatorRow);

  return box;
}

/* Р5 polish (прод-репорт): таргет tooltip — СТРОКА ПОЛЬЗОВАТЕЛЕЙ
 * (.task-card-users), не вся карточка (см. шапку файла). */
export function attachCardTooltip(usersLine, task) {
  /* Динамический import — как attachProfileTooltip в profile.js:
   * сбой загрузки модуля (сеть/путь) не ломает карточку — она остается
   * со строкой assigned · creator (ОВ-24 не зависит от всплывашки). */
  import("../tooltip.js")
    .then(function (tooltip) {
      tooltip.attach(usersLine, function () {
        return buildCardTooltipContent(task);
      }, { delay: 300 });
    })
    .catch(function () {
      /* модуль недоступен — карточка работает без всплывашки. */
    });
}
