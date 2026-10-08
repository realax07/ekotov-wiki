/* Мобильная оболочка модалок тикета (2.2 add-responsive-mobile; FR-102,
 * ОВ-4, design §4; мокапы design/mobile-p14/04-ticket-modal-view.html и
 * 05-ticket-modal-edit.html).
 *
 * На ≤480px обе оболочки — просмотр (read-only, Д-9) и форма — получают
 * общий fullscreen-контейнер. Геометрия — board.css (единый media-блок
 * ≤480px, desktop не тронут, NFR-29); здесь — только то, что CSS не
 * выражает:
 *
 * 1. Блокировка скролла ПОДЛОЖКИ-страницы (body) на время открытой
 *    модалки (design §4: «подложка overflow:hidden при открытой
 *    модалке» — double-скролл модалка+страница снят). Позиция доски
 *    восстанавливается ТОЧНО при закрытии (сценарий «Fullscreen-модалка
 *    на мобильном»: закрытие возвращает на доску в прежнюю scroll-
 *    позицию). Класс на <body> ставит состояние, значение запоминает
 *    модуль — путь закрытия (крестик/Escape/«Отмена»/подложка) не важен.
 * 2. scrollIntoView активного поля (focusin): iOS-клавиатура сжимает
 *    вьюпорт, нативная прокрутка браузера в flex-колонке со скроллом
 *    тела срабатывает поздно/частично — явный scrollIntoView (сценарий
 *    «Поля без авто-зума и клавиатура не перекрывает поле»).
 *
 * Инпуты ≥16px (NFR-24) и тач-таргеты ≥44px (NFR-23) — CSS (board.css,
 * media-блок 2.2). Действующая 480px-ветка формы FR-62 не тронута.
 *
 * Подключение: board-init.js (initMobileModalShell()) — до подписок
 * модалок; на /search форма задачи не существует (BUG-014), view там
 * закрывается своим обработчиком search.js — блокировка/возврат скролла
 * на него тоже распространяются (overlay id тот же), риск регресса
 * закрыт desktop-guard'ом matchMedia.
 */
"use strict";

var MOBILE_MQ = "(max-width: 480px)";
var LOCK_CLASS = "modal-shell-open";

/* Запомненная позиция скролла страницы на момент ПЕРВОГО открытия
 * (модалки наслаиваются: view → форма — блокировка считается счетчиком). */
var savedScrollY = 0;
var lockCount = 0;

function isMobile() {
  return window.matchMedia(MOBILE_MQ).matches;
}

function lockPageScroll() {
  if (lockCount === 0) {
    /* scrollY до блокировки: восстановление в прежнюю позицию доски
     * (сценарий spec board «Fullscreen-модалка на мобильном»). */
    savedScrollY = window.scrollY || 0;
    document.body.classList.add(LOCK_CLASS);
    window.scrollTo(0, 0);
  }
  lockCount += 1;
}

function unlockPageScroll() {
  if (lockCount === 0) {
    return;
  }
  lockCount -= 1;
  if (lockCount === 0) {
    document.body.classList.remove(LOCK_CLASS);
    /* Точная прежняя позиция (не «примерно вверх страницы»). */
    window.scrollTo(0, savedScrollY);
  }
}

/* Пересчет при смене ориентации/размера не нужен: позиция относится к
 * документу, layout-зависимость дает только восстановление в момент
 * закрытия (оно синхронно с классом). */

/* Клавиатура iOS (design §4): при фокусе инпута прокрутка активного поля
 * в видимость. focusin — с делегированием, ловит и поля внутри попапов
 * комбобокса; behavior по умолчанию (мгновенно) — ОГР-17 friendly. */
function initFocusScrollIntoView() {
  document.addEventListener("focusin", function (event) {
    if (!isMobile()) {
      return;
    }
    var view = document.getElementById("task-detail-overlay");
    var form = document.getElementById("task-form-overlay");
    var inView = view && !view.hidden && view.contains(event.target);
    var inForm = form && !form.hidden && form.contains(event.target);
    if (!inView && !inForm) {
      return;
    }
    var field = event.target;
    if (typeof field.scrollIntoView === "function") {
      field.scrollIntoView({ block: "center" });
    }
  });
}

/* Публичная точка: подписать обе модалки доски. Вызывается один раз из
 * board-init.js; повторный вызов идемпотентен (guard по data-атрибуту). */
export function initMobileModalShell() {
  if (document.body.dataset.modalShellInit === "1") {
    return;
  }
  document.body.dataset.modalShellInit = "1";

  ["task-detail-overlay", "task-form-overlay"].forEach(function (id) {
    var overlay = document.getElementById(id);
    if (!overlay) {
      return;
    }
    /* MutationObserver вместо обертки close-путей: крестик, Escape,
     * «Отмена», клик по подложке и сабмит закрывают модалку из трех
     * разных модулей — единая точка наблюдения надежнее перечисления
     * путей (ни один не забыт). */
    var observer = new MutationObserver(function () {
      if (overlay.hidden) {
        unlockPageScroll();
      } else if (isMobile()) {
        lockPageScroll();
      }
    });
    observer.observe(overlay, { attributes: true, attributeFilter: ["hidden"] });
    /* Открытая до подписки модалка (крайний случай) — синхронизация. */
    if (!overlay.hidden && isMobile()) {
      lockPageScroll();
    }
  });

  initFocusScrollIntoView();
}
