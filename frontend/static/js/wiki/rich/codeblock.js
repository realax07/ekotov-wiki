/* Блок кода P12 (FR-119, design.md §1/§3/§5; мокап tool-2-code-*).
 *
 * Хранение: <div data-block="code" data-lang="python"><pre><code>текст</code></pre></div>
 * В БД — чистый экранированный текст; спанов подсветки нет (§1): подсветка
 * выполняется лексером (highlight.js) ТОЛЬКО при отображении статьи. В
 * редакторе код — plain моно на темном фоне + нумерация строк (гуттер —
 * data-editor, обновляется по input) — сериализуемый DOM остается текстом.
 *
 * Шапка (data-editor): выбор языка (дропдаун, ОВ-2) и «Копировать» →
 * «✓ Скопировано» 1,5 с (Clipboard API над textContent — §8). Нераспознанный
 * язык (поврежден data-lang) → plain без ошибок (NFR-39).
 */

import {
  el, editorEl, placeCaretStart,
  LANG_ATTR, LANG_VALUES, LANG_LABELS
} from './model.js';
import { highlight } from './highlight.js';

var COPY_RESET_MS = 1500;

export function codeText(block) {
  var code = block.querySelector('pre > code') || block.querySelector('code');
  return code ? code.textContent : '';
}

/* Гуттер нумерации строк: числа 1..N по числу строк кода (data-editor).
 * Позиционируется абсолютно СБОКУ от pre (не внутри data-editor-обертки —
 * иначе сериализация вырезала бы pre вместе с оберткой: тот же класс
 * потери контента, что rich-v1; находка F1). */
function buildGutter(codeEl, block) {
  var gutter = editorEl('div', 'codeblock-nums');
  var text = codeEl.textContent.replace(/\n$/, '');
  var lines = text.length ? text.split('\n').length : 1;
  var parts = [];
  for (var i = 1; i <= lines; i += 1) parts.push(String(i));
  gutter.textContent = parts.join('\n');
  gutter.setAttribute('aria-hidden', 'true');
  /* top = высота шапки (гуттер начинается под ней) */
  var head = block.querySelector('.codeblock-head');
  if (head) gutter.style.top = head.offsetHeight + 'px';
  return gutter;
}

function syncGutter(block) {
  var code = block.querySelector('pre > code');
  var gutter = block.querySelector('.codeblock-nums');
  if (code && gutter) {
    var replacement = buildGutter(code, block); // F-2: block — вторым аргументом
    gutter.textContent = replacement.textContent;
  }
}

/* Кнопка «Копировать»: Clipboard API над textContent (§8); успех —
 * «✓ Скопировано» на 1,5 с (мокап). Отказ — короткое «Не скопировано». */
function buildCopyButton(block) {
  var button = editorEl('button', 'copy-btn', 'Копировать');
  button.type = 'button';
  button.addEventListener('click', function (event) {
    event.preventDefault();
    event.stopPropagation();
    var text = codeText(block);
    var done = function () {
      button.classList.add('ok');
      button.textContent = '✓ Скопировано';
      window.setTimeout(function () {
        button.classList.remove('ok');
        button.textContent = 'Копировать';
      }, COPY_RESET_MS);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () {
        button.textContent = 'Не скопировано';
      });
    } else {
      button.textContent = 'Не скопировано';
    }
  });
  return button;
}

/* Дропдаун выбора языка (ОВ-2): кнопка с текущим языком + меню словаря. */
function buildLangPicker(block, editable) {
  var wrap = el('span', 'codeblock-lang-wrap');
  wrap.style.position = 'relative';
  var current = block.getAttribute(LANG_ATTR);
  if (LANG_VALUES.indexOf(current) === -1) current = 'plain'; // NFR-39
  var button = editorEl('button', 'codeblock-lang');
  button.type = 'button';
  var label = function () {
    return (LANG_LABELS[current] || current) + (editable ? ' ▾' : '');
  };
  button.textContent = label();

  var menu = null;
  function closeMenu() {
    if (menu) {
      menu.remove();
      menu = null;
    }
    document.removeEventListener('click', onDocClick, true);
  }
  function onDocClick(event) {
    /* menu в document.body (BUG-025) — клик по опции не должен закрывать
       меню до срабатывания обработчика опции */
    if (!wrap.contains(event.target) &&
        !(menu && menu.contains(event.target))) {
      closeMenu();
    }
  }
  function openMenu() {
    menu = editorEl('div', 'lang-menu');
    LANG_VALUES.forEach(function (lang) {
      var option = el('div', 'lang-opt' + (lang === current ? ' sel' : ''));
      option.appendChild(el('span', null, LANG_LABELS[lang]));
      if (lang === current) option.appendChild(el('span', 'chk', '✓'));
      option.addEventListener('click', function () {
        current = lang;
        block.setAttribute(LANG_ATTR, lang);
        button.textContent = label();
        closeMenu();
        if (!editable) {
          applyHighlight(block); // язык сменился в рендере
        } else {
          /* каретка возвращается в код (фокус был в дропдауне) */
          var code = block.querySelector('pre > code');
          if (code) placeCaretStart(code);
        }
      });
      menu.appendChild(option);
    });
    /* BUG-025: меню позиционируется ВНЕ clip-контекста код-блока —
       .codeblock { overflow: hidden } (рамка/скругления pre) обрезал
       absolute-меню внутри шапки, выбор языка не работал. Меню —
       fixed от кнопки в document.body, над контентом (z-index слоя
       20; диалоги редактора — 40, выше меню). */
    document.body.appendChild(menu);
    var buttonRect = button.getBoundingClientRect();
    menu.style.left = buttonRect.left + 'px';
    menu.style.top = buttonRect.bottom + 2 + 'px';
    document.addEventListener('click', onDocClick, true);
  }
  button.addEventListener('click', function (event) {
    event.preventDefault();
    event.stopPropagation();
    if (menu) closeMenu();
    else openMenu();
  });
  wrap.appendChild(button);
  return wrap;
}

/* Подсветка при отображении (§5): текст кода → экранированные спаны. */
export function applyHighlight(block) {
  var code = block.querySelector('pre > code');
  if (!code) return;
  var lang = block.getAttribute(LANG_ATTR);
  var html = highlight(code.textContent, lang); // неизвестный lang → plain
  code.innerHTML = html;
}

/* Общая активация: классы, шапка (язык + копировать), гуттер. */
function enhance(block, editable) {
  if (block.classList.contains('rich-active')) return;
  block.classList.add('rich-active', 'codeblock');
  var pre = block.querySelector('pre');
  var code = block.querySelector('pre > code');
  if (!code) {
    code = el('code');
    if (!pre) {
      pre = el('pre');
      block.appendChild(pre);
    }
    pre.appendChild(code);
  }

  var head = editorEl('div', 'codeblock-head');
  head.appendChild(buildLangPicker(block, editable));
  head.appendChild(buildCopyButton(block));
  block.insertBefore(head, block.firstChild);

  /* Нумерация строк (ОВ-2): гуттер — data-editor СИБЛИНГ pre (абсолютное
   * позиционирование; pre — прямой контентный узел, сериализация его
   * сохраняет). В редакторе гуттер обновляется по правке кода. */
  var gutter = buildGutter(code, block);
  block.appendChild(gutter);
}

/* F-1 (review-001): br внутри code (Enter в Chromium) — перенос строки
 * КОДА. Заменяем br на текстовый «\n» ДО сериализации: иначе гуттер считает
 * строки по textContent (br невидим), а канал «редактор показал ≠
 * сохранилось» держится только на санитайзере. br-якорь каретки ПУСТОГО
 * кода (data-caret из newCodeblockHtml) удаляется — это мусор, не перенос.
 * Возвращает true, если DOM менялся. */
function normalizeNewlines(code) {
  var brs = code.querySelectorAll('br');
  if (!brs.length) return false;
  if (!code.textContent) {
    // пустой код: якорные br не трогаем (санитайзер отсечет их \n)
    return false;
  }
  var changed = false;
  Array.prototype.forEach.call(brs, function (br) {
    if (br.getAttribute('data-caret') !== null) {
      br.parentNode.removeChild(br);
    } else {
      br.parentNode.replaceChild(document.createTextNode('\n'), br);
    }
    changed = true;
  });
  return changed;
}

/* Нормализация кода после ввода (вызывается делегированным input-слушателем
 * области — input-события в contenteditable таргетятся в editing host,
 * до pre/block они не доезжают). Chromium-квирк: ввод на границе ПУСТОГО
 * inline code пишет текст прямо в pre (мимо code). Все узлы pre, кроме
 * самого code, переносятся внутрь code; при переносе каретка — в конец
 * кода. Сериализация всегда дает <pre><code>текст</code></pre>. */
export function normalizeCodeInput(block) {
  var pre = block.querySelector('pre');
  var code = block.querySelector('pre > code');
  if (!pre || !code) return;
  var moved = false;
  while (pre.firstChild && pre.firstChild !== code) {
    code.insertBefore(pre.firstChild, null);
    moved = true;
  }
  var newlined = normalizeNewlines(code);
  if (moved) {
    var selection = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(code);
    range.collapse(false); // в конец кода
    selection.removeAllRanges();
    selection.addRange(range);
  }
  syncGutter(block);
}

export function enhanceEditor(block) {
  enhance(block, true);
}

export function activateView(block) {
  enhance(block, false);
  applyHighlight(block); // подсветка только при отображении (§1/§5)
}

/* Разметка нового блока для вставки в позицию курсора. <br data-caret>
 * в пустом code — каретка-якорь: Chromium пишет текст на границе ПУСТОГО
 * inline-элемента в родительский pre; с br каретка встает внутрь code.
 * Якорь помечен data-caret: normalizeCodeInput удаляет его при первом
 * вводе текста (мусор, не перенос — F-1), санитайзер пустой блок с
 * якорем сохраняет пустым. */
export function newCodeblockHtml() {
  return (
    '<div data-block="code" data-lang="python"><pre><code>' +
    '<br data-caret="1"></code></pre></div><p><br></p>'
  );
}

/* После insertHTML: каретка в КОНЕЦ code (за br-якорь — ввод идет внутрь
 * code, не в pre). */
export function focusInsertedCode(area) {
  var blocks = area.querySelectorAll('[data-block="code"]');
  var block = blocks[blocks.length - 1];
  if (!block) return null;
  var code = block.querySelector('pre > code');
  if (code) {
    var selection = window.getSelection();
    var range = document.createRange();
    range.selectNodeContents(code);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  }
  return block;
}
