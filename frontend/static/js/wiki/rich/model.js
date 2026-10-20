/* Словарь rich-блоков P12 (design.md §1) — единый с backend/app/sanitize.py
 * (константы продублированы; тест согласования — tests/api/test_sanitize.py
 * test_rich_dictionary_matches_js_model).
 *
 * Хранение: блоки — те же санитизированные HTML-данные, блочные конструкции
 * на data-атрибутах фиксированного словаря:
 *   <div data-block="spoiler" data-title="…"><div data-block-part="body">…</div></div>
 *   <div data-block="code" data-lang="python"><pre><code>…</code></pre></div>
 *   <div data-block="tabs"><div data-block-part="tab" data-title="…">…</div>…</div>
 *
 * Инварианты (уроки rich-v1, design.md §7):
 * - никаких id и data-block-id — связи структурные (вложенность DOM);
 * - состояние отображения (свернут спойлер, активная вкладка) в контент
 *   НЕ пишется; при открытии спойлер развернут, вкладка первая;
 * - служебные узлы редактора помечаются data-editor + contenteditable="false"
 *   и вырезаются при сериализации (design.md §3, находка F1): сохраняемое
 *   ≡ DOM минус data-editor-узлы.
 *
 * Без внешних зависимостей (ОГР-8).
 */

export var BLOCK_ATTR = 'data-block';
export var PART_ATTR = 'data-block-part';
export var TITLE_ATTR = 'data-title';
export var LANG_ATTR = 'data-lang';

/* Значения словаря — дословно из backend/app/sanitize.py (§1). */
export var BLOCK_VALUES = ['spoiler', 'code', 'tabs'];
export var BLOCK_PART_VALUES = ['body', 'tab'];
export var LANG_VALUES = ['python', 'js', 'bash', 'json', 'sql', 'plain'];

/* Человеческие подписи языков в дропдауне (мокап tool-2-code). */
export var LANG_LABELS = {
  python: 'python',
  js: 'javascript',
  bash: 'bash',
  json: 'json',
  sql: 'sql',
  plain: 'plain text'
};

/* Лимиты (design.md §1/§6): вкладок ≤8, глубина блоков ≤5 (сервер —
 * sanitize.py MAX_BLOCK_DEPTH; редактор не предлагает вставку глубже). */
export var TAB_LIMIT = 8;
export var MAX_BLOCK_DEPTH = 5;

/* Пометка служебных узлов редактора (design.md §3, находка F1). */
export var EDITOR_MARK = 'data-editor';

/* Дефолтное название спойлера/вкладки при вставке. */
export var DEFAULT_SPOILER_TITLE = 'Спойлер';
export var DEFAULT_TAB_TITLE = 'Вкладка';

/* ------------------------------------------------------------------ */
/* Утилиты DOM (пользовательские данные — только textContent, XSS)     */
/* ------------------------------------------------------------------ */

export function el(tag, className, text) {
  var node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

/* Служебный узел редактора: data-editor + contenteditable="false" —
 * вырезается при сериализации, фокус в него не проваливается (§3). */
export function editorEl(tag, className, text) {
  var node = el(tag, className, text);
  node.setAttribute(EDITOR_MARK, '');
  node.setAttribute('contenteditable', 'false');
  return node;
}

/* Сериализация редактируемой области (design.md §3, находка F1):
 * сохраняемое ≡ DOM минус data-editor-узлы; контентные узлы не
 * перестраиваются (детерминированное вырезание поддеревьев). */
export function serializeArea(area) {
  var clone = area.cloneNode(true);
  var artifacts = clone.querySelectorAll('[' + EDITOR_MARK + ']');
  for (var i = 0; i < artifacts.length; i += 1) {
    artifacts[i].parentNode.removeChild(artifacts[i]);
  }
  /* Незакрытые contenteditable="false" на контентных узлах не ставятся —
   * атрибут не из whitelist'а, сервер его снимет. */
  return clone.innerHTML;
}

/* Тело блока: прямой ребенок [data-block-part] (body у спойлера, tab
 * у табов). Возвращается первый, если partName не задан. */
export function blockParts(block, partName) {
  var result = [];
  var children = block.children;
  for (var i = 0; i < children.length; i += 1) {
    var child = children[i];
    if (child.getAttribute && child.getAttribute(PART_ATTR)) {
      if (!partName || child.getAttribute(PART_ATTR) === partName) {
        result.push(child);
      }
    }
  }
  return result;
}

/* Компактный вариант в ячейке таблицы (design.md §3): класс определяется
 * по closest('td,th') при активации, в контенте НЕ хранится. */
export function cellContext(node) {
  return !!(node.closest && node.closest('td,th'));
}

/* Каретка внутри редактируемой области? */
export function caretIn(area) {
  var selection = window.getSelection();
  return !!(selection && area.contains(selection.anchorNode));
}

/* Поставить каретку в начало узла (зона содержимого после вставки). */
export function placeCaretStart(node) {
  var selection = window.getSelection();
  var range = document.createRange();
  range.selectNodeContents(node);
  range.collapse(true);
  selection.removeAllRanges();
  selection.addRange(range);
}
