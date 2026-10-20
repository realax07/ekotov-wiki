/* Спойлер P12 (FR-118, design.md §3/§6; мокап design/p12-rich/tool-1-*).
 *
 * Хранение (design.md §1):
 *   <div data-block="spoiler" data-title="…"><div data-block-part="body">…</div></div>
 *
 * Инварианты:
 * - шапка (шеврон + название + подсказка) — служебный узел data-editor:
 *   в сохраняемый контент не попадает; toggle-состояние (open/closed)
 *   тоже не сохраняется — при открытии спойлер развернут (§1);
 * - клик по ВСЕЙ шапке сворачивает/разворачивает (ОВ-1); клик по названию
 *   в редакторе — инлайн-переименование (input с focus-ring);
 * - в ячейке таблицы — компактный класс (closest('td,th') при активации,
 *   в контенте не хранится);
 * - вложенность (спойлер в спойлере) — независимые состояния; сохранение
 *   не перестраивает дерево (урок rich-v1 «потеря контента»).
 */

import {
  el, editorEl, blockParts, cellContext, placeCaretStart,
  TITLE_ATTR, PART_ATTR, DEFAULT_SPOILER_TITLE
} from './model.js';

/* Статический SVG шеврона (мокап; не данные пользователя — innerHTML безопасен). */
var CARET_SVG =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7" ' +
  'fill="none" stroke="currentColor" stroke-width="2.5"/></svg>';

export function caretIcon() {
  var span = el('span', 'spoiler-caret');
  span.setAttribute('aria-hidden', 'true');
  span.innerHTML = CARET_SVG;
  return span;
}

/* Тело спойлера: существующий [data-block-part="body"] либо новый пустой. */
export function ensureBody(spoiler) {
  var body = blockParts(spoiler, 'body')[0];
  if (!body) {
    body = el('div');
    body.setAttribute(PART_ATTR, 'body');
    body.innerHTML = '<p><br></p>';
    spoiler.appendChild(body);
  }
  body.classList.add('spoiler-body');
  return body;
}

/* Шапка: head — служебный (data-editor). titleText — текущее название.
 * editable — rename-ветка только в редакторе: в статье клик по названию
 * = toggle (F-3, review-001; ОВ-1 «кликабельна ВСЯ шапка»). */
function buildHead(spoiler, titleText, withHint, editable) {
  var head = editorEl('div', 'spoiler-head');
  head.appendChild(caretIcon());
  var title = el('span', 'spoiler-title', titleText || DEFAULT_SPOILER_TITLE);
  head.appendChild(title);
  if (withHint) {
    head.appendChild(
      el('span', 'spoiler-title-hint', 'клик по названию — переименовать')
    );
  }
  head.addEventListener('click', function (event) {
    if (head.querySelector('.spoiler-title-input')) return; // идет rename
    if (editable && event.target.closest('.spoiler-title')) {
      startRename(spoiler, head, title);
      return;
    }
    toggleSpoiler(spoiler);
  });
  return head;
}

export function toggleSpoiler(spoiler) {
  var closed = spoiler.classList.toggle('closed');
  spoiler.classList.toggle('open', !closed);
  return !closed;
}

/* Инлайн-переименование: клик по названию → input; Enter/blur — фиксация
 * в data-title, Escape — отмена (спека ОВ; QA D1: первый исход финален). */
export function startRename(spoiler, head, titleSpan) {
  if (head.querySelector('.spoiler-title-input')) return;
  if (!titleSpan || titleSpan.parentNode !== head) return; // гонка commit
  var current = spoiler.getAttribute(TITLE_ATTR) || DEFAULT_SPOILER_TITLE;
  var input = editorEl('input', 'spoiler-title-input');
  input.type = 'text';
  input.value = current;
  input.setAttribute('aria-label', 'Название спойлера');
  head.replaceChild(input, titleSpan);
  input.focus();
  input.select();

  /* Единственная точка завершения переименования (QA D1): первый вызов
   * close() закрывает rename, повторный (blur после Escape и т.п.) —
   * no-op. Гонка Escape→blur детерминирована: Escape → close(false)
   * возвращает исходное название, последующий blur не коммитит и не
   * делает второй replaceChild (pageerror «Failed to execute
   * 'replaceChild'» снят). */
  var closed = false;
  function close(commit) {
    if (closed) return;
    closed = true;
    var value = commit ? input.value.trim() || current : current;
    spoiler.setAttribute(TITLE_ATTR, value);
    titleSpan.textContent = value;
    if (input.parentNode === head) head.replaceChild(titleSpan, input);
  }
  input.addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      close(true);
    } else if (event.key === 'Escape') {
      close(false);
    }
  });
  input.addEventListener('blur', function () {
    close(true);
  });
}

/* Общая активация (edit и view): классы виджета, шапка, тело, компакт. */
function enhance(spoiler, options) {
  if (spoiler.classList.contains('rich-active')) return;
  spoiler.classList.add('rich-active', 'spoiler', 'open');
  if (cellContext(spoiler)) spoiler.classList.add('rich-compact');
  var body = ensureBody(spoiler);
  var head = buildHead(
    spoiler,
    spoiler.getAttribute(TITLE_ATTR),
    !!options.editable,
    !!options.editable
  );
  spoiler.insertBefore(head, spoiler.firstChild);
  if (options.editable) {
    /* Зона содержимого редактируется; свернутый сохраняет содержимое —
     * body остается в DOM (display:none), сериализация его не теряет. */
    body.setAttribute('data-rich-editable', '');
  }
}

/* Редактор: шапка с подсказкой + инлайн-переименование. */
export function enhanceEditor(spoiler) {
  enhance(spoiler, { editable: true });
}

/* Рендер статьи: та же шапка без подсказок (клик по всей шапке — ОВ-1). */
export function activateView(spoiler) {
  enhance(spoiler, { editable: false });
}

/* Разметка нового спойлера для вставки в позицию курсора (design.md §1). */
export function newSpoilerHtml() {
  return (
    '<div data-block="spoiler" data-title="' + DEFAULT_SPOILER_TITLE + '">' +
    '<div data-block-part="body"><p><br></p></div></div><p><br></p>'
  );
}

/* После insertHTML: найти вставленный спойлер и вернуть его тело
 * (фокус — в зону содержимого, design.md §3). */
export function focusInsertedBody(area) {
  var blocks = area.querySelectorAll('[data-block="spoiler"]');
  var spoiler = blocks[blocks.length - 1];
  if (!spoiler) return null;
  var body = ensureBody(spoiler);
  placeCaretStart(body);
  return spoiler;
}
