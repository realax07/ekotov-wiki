/* Индикатор точек мобильной доски (2.1 add-responsive-mobile; FR-101, ОВ-3,
 * design §3; мокап design/mobile-p14/03-board-swipe.html).
 *
 * На ширинах ≤480px доска — горизонтальный свайп-контейнер колонок со
 * scroll-snap (board.css, ≤480px-ветка). Здесь — видимый индикатор текущей
 * колонки:
 *  - активная точка синхронна scroll-позиции контейнера (слушатель scroll
 *    + расчет ближайшей колонки — design §3);
 *  - тап по точке — скролл к колонке (scrollIntoView({ behavior: "smooth" }),
 *    при prefers-reduced-motion — behavior: "auto" (ОГР-17 — без анимации).
 *
 * Разметка строится только на мобильной ветке (matchMedia "(max-width:
 * 480px)"); на desktop точек нет — доска три колонки рядом, NFR-29.
 * Контейнер вставляется сразу после #board (соседний элемент), стили —
 * .board-dots в board.css (та же ≤480px-ветка).
 *
 * Перерисовка доски (refreshBoard → renderBoard чистит только [data-cards])
 * разметку точек не трогает: #board сам не пересоздается. Resize между
 * ветками: при выходе из ≤480px точки скрываются CSS + перестают быть
 * tab-табами (hidden), при возврате — восстанавливаются.
 */
"use strict";

/* Медиа-условие мобильной доски — единое с CSS-веткой ≤480px (design §1:
 * два магических числа 480/768 пакета; здесь — 480). */
var MOBILE_QUERY = "(max-width: 480px)";

/* rAF-дедупликация scroll-событий: пересчет ближайшей колонки — не чаще
 * кадра (дешево и без дребезга активной точки при инерционном свайпе). */
var scrollScheduled = false;

function reducedMotion() {
  return (
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function columns() {
  return Array.prototype.slice.call(
    document.querySelectorAll("#board .board-column")
  );
}

function dotsContainer() {
  return document.querySelector(".board-dots");
}

/* Снимок геометрии колонок: индекс активной точки + scroll-позиция
 * прилипания (snap) для перехода по точкам.
 *
 * ВАЖНО (урок реализации): offsetLeft колонки отсчитывается от общего
 * offsetParent (app-shell), а не от контейнера #board — «граница колонки»
 * в координатах скролла = offsetLeft - board.offsetLeft (+ board padding,
 * здесь 0). Прямой offsetLeft завышает цель на сдвиг контейнера (16px на
 * 375px) — точки вели бы на колонку позади. */
function boardMetrics() {
  var board = document.getElementById("board");
  if (!board) {
    return null;
  }
  var cols = columns();
  /* Скролл-позиции прилипания колонок (scrollLeft, при котором колонка
   * выровнена по левому краю контейнера): разность rect.left минус
   * rect.left контейнера — смещение В ЭКРАНЕ, оно уже включает текущий
   * scrollLeft, поэтому цель = смещение + scrollLeft. Без поправки
   * «цель уезжает» при каждом скролле (урок реализации: на оседшей
   * позиции targets = [-316, -0.5, 315] при scrollLeft=316 — и верные
   * скролл-цели 0/315.5/631 получаются только добавлением scrollLeft). */
  var scrollLeft = board.scrollLeft;
  var boardLeft = board.getBoundingClientRect().left;
  var targets = cols.map(function (column) {
    return column.getBoundingClientRect().left - boardLeft + scrollLeft;
  });
  return { board: board, cols: cols, targets: targets };
}

function columnIndexByScrollLeft(container) {
  /* Ближайшая колонка к левому краю видимой области: snap-align start —
   * колонка прилипает левым краем к контейнеру, поэтому минимум
   | columnLeft - scrollLeft | и есть текущая (на середину свайпа точка
   * переключается в момент, когда новая колонка становится ближе).
   * Границы колонок — в координатах скролла (boardMetrics.targets,
   * вычисленные в том же кадре, что и scrollLeft: разделение замеров
   * на два evaluate давало расхождение «активная точка отстала на
   * колонку» на инерционном свайпе). */
  var metrics = boardMetrics();
  if (!metrics) {
    return 0;
  }
  var best = 0;
  var bestDist = Infinity;
  metrics.targets.forEach(function (left, index) {
    var dist = Math.abs(left - metrics.board.scrollLeft);
    if (dist < bestDist) {
      bestDist = dist;
      best = index;
    }
  });
  return best;
}

function setActiveDot(index) {
  var dots = dotsContainer();
  if (!dots) {
    return;
  }
  Array.prototype.forEach.call(dots.querySelectorAll("button"), function (
    button,
    i
  ) {
    if (i === index) {
      button.setAttribute("aria-current", "true");
    } else {
      button.setAttribute("aria-current", "false");
    }
  });
}

function onScroll() {
  if (scrollScheduled) {
    return;
  }
  scrollScheduled = true;
  window.requestAnimationFrame(function () {
    scrollScheduled = false;
    var dots = dotsContainer();
    if (!dots || dots.hidden) {
      return;
    }
    setActiveDot(columnIndexByScrollLeft());
  });
}

/* Финальная синхронизация после оседания snap: scroll-поток обрывается до
 * последнего rAF-тика при инерционном доводе mandatory-snap — последний
 * кадр пересчета может быть ДО оседания (наблюдалось: точки отставали на
 * колонку после свайпа). scrollend надежнее, но в старых WebKit его нет —
 * дублируем через таймер-тихий-хвост (120ms без событий = осело). */
var settleTimer = null;

function scheduleSettleCheck() {
  if (settleTimer) {
    window.clearTimeout(settleTimer);
  }
  settleTimer = window.setTimeout(function () {
    settleTimer = null;
    var dots = dotsContainer();
    if (!dots || dots.hidden) {
      return;
    }
    setActiveDot(columnIndexByScrollLeft());
  }, 120);
}

/* Тап по точке — скролл к колонке (smooth; reduced-motion — auto, ОГР-17). */
function onDotClick(event) {
  var button = event.target.closest("button");
  if (!button) {
    return;
  }
  var dots = dotsContainer();
  var index = Array.prototype.indexOf.call(
    dots.querySelectorAll("button"),
    button
  );
  var metrics = boardMetrics();
  if (metrics && metrics.targets[index] !== undefined) {
    metrics.board.scrollTo({
      left: metrics.targets[index],
      behavior: reducedMotion() ? "auto" : "smooth",
    });
  }
}

/* Построение/удаление разметки при переходах через 480px (matchMedia). */
function syncVisibility() {
  var dots = dotsContainer();
  if (!dots) {
    return;
  }
  var mobile = window.matchMedia(MOBILE_QUERY).matches;
  dots.hidden = !mobile;
}

function buildDots() {
  if (dotsContainer()) {
    return; // идемпотентность: повторный вызов разметку не дублирует
  }
  var board = document.getElementById("board");
  if (!board) {
    return;
  }
  var dots = document.createElement("div");
  dots.className = "board-dots";
  dots.setAttribute("role", "tablist");
  dots.setAttribute("aria-label", "Текущая колонка");
  columns().forEach(function (column) {
    var button = document.createElement("button");
    button.type = "button";
    button.setAttribute("role", "tab");
    var title = column.querySelector(".board-column-title");
    button.setAttribute(
      "aria-label",
      "Колонка " + (title ? title.textContent.trim() : column.dataset.status)
    );
    button.setAttribute("aria-current", "false");
    dots.appendChild(button);
  });
  board.insertAdjacentElement("afterend", dots);
  dots.addEventListener("click", onDotClick);
  syncVisibility();
}

/* Инициализация (board-init.js, один раз при загрузке страницы). */
export function initBoardDots() {
  buildDots();

  /* Синхронизация активной точки со scroll-позицией (design §3). */
  var board = document.getElementById("board");
  if (board) {
    board.addEventListener("scroll", function (event) {
      onScroll();
      scheduleSettleCheck();
    }, { passive: true });
    /* Начальное состояние: первая колонка активна (в т.ч. после refreshBoard —
     * DOM #board не пересоздается, позиция скролла сохраняется). */
    setActiveDot(columnIndexByScrollLeft(board));
  }

  /* Переходы 480px (поворот, ресайз окна): скрыть/показать табы. */
  if (window.matchMedia) {
    var query = window.matchMedia(MOBILE_QUERY);
    var listener = function () {
      syncVisibility();
    };
    if (query.addEventListener) {
      query.addEventListener("change", listener);
    } else if (query.addListener) {
      query.addListener(listener); // старые Safari — без addEventListener
    }
  }
}
