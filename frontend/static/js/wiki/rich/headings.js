/* H-toggle P12 (FR-121, design.md §3; мокап tool-4-headings-*). Модуль
 * редактора: кнопки H1/H2/H3 работают как переключатели.
 *
 * Mechanism (находка F4): сама замена блока выполняется управляемым
 * document.execCommand('formatBlock') — нативный undo-стек contenteditable
 * сохраняется (Ctrl+Z откатывает toggle); ручная замена тега — только
 * fallback. Повторный клик по активной кнопке снимает формат (текст →
 * абзац, текст не теряется); клик по соседней заменяет уровень;
 * одновременное нажатие двух уровней невозможно (формат один).
 * Backspace в пустом заголовке снимает формат (ОВ-5, keydown-перехват).
 */

var HEADING_TAGS = ['h1', 'h2', 'h3'];

/* Текущий блок под кареткой: h1/h2/h3/p (Selection.anchorNode → closest;
 * formatBlock как fallback). */
export function currentBlockTag(area) {
  var selection = window.getSelection();
  if (!selection || !selection.anchorNode || !area.contains(selection.anchorNode)) {
    return null;
  }
  var node = selection.anchorNode;
  var element = node.nodeType === 1 ? node : node.parentNode;
  var block = element.closest ? element.closest('h1,h2,h3,p') : null;
  if (block && area.contains(block)) return block.nodeName.toLowerCase();
  try {
    var value = String(document.queryCommandValue('formatBlock') || '').toLowerCase();
    return HEADING_TAGS.indexOf(value) !== -1 || value === 'p' ? value : null;
  } catch (err) {
    return null;
  }
}

/* Toggle/замена уровня (всегда через execCommand — undo-стек жив, F4). */
export function toggleHeading(area, level) {
  if (HEADING_TAGS.indexOf(level) === -1) return;
  /* Каретка обязана быть в области: тулбар не крадет фокус
   * (mousedown preventDefault в editor.js), но при клике «вслепую»
   * возвращаем фокус. */
  if (!area.contains(window.getSelection().anchorNode)) area.focus();
  var current = currentBlockTag(area);
  var target = current === level ? 'p' : level; // повторный клик → абзац
  document.execCommand('formatBlock', false, '<' + target + '>');
}

/* Backspace в пустом заголовке снимает формат (ОВ-5): keydown-перехват
 * (блок h*, textContent пуст) → тот же механизм снятия формата. */
export function installBackspace(area) {
  area.addEventListener('keydown', function (event) {
    if (event.key !== 'Backspace') return;
    var selection = window.getSelection();
    if (!selection || !selection.isCollapsed) return;
    if (!area.contains(selection.anchorNode)) return;
    var node = selection.anchorNode;
    var element = node.nodeType === 1 ? node : node.parentNode;
    var block = element.closest ? element.closest('h1,h2,h3') : null;
    if (!block || !area.contains(block)) return;
    if (block.textContent.replace(/\u200b/g, '').trim() !== '') return;
    event.preventDefault();
    document.execCommand('formatBlock', false, '<p>');
  });
}

/* Синхронизация aria-pressed по позиции курсора: нажата ровно одна
 * кнопка (или ни одной — CLEAR-состояние). */
export function syncStates(area, buttons) {
  var current = currentBlockTag(area);
  HEADING_TAGS.forEach(function (level) {
    var button = buttons[level];
    if (button) {
      button.setAttribute('aria-pressed', current === level ? 'true' : 'false');
    }
  });
}
