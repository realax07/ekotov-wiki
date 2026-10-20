/* Табуляция P12 (FR-120, design.md §1/§3; мокап tool-3-tabs-*).
 *
 * Хранение:
 *   <div data-block="tabs">
 *     <div data-block-part="tab" data-title="Обзор">…</div>
 *     <div data-block-part="tab" data-title="Детали">…</div>
 *   </div>
 *
 * Инварианты:
 * - таб-бар (вкладки, «+», «×») — служебный data-editor: в контент не
 *   пишется; активная вкладка НЕ сохраняется — при открытии активна
 *   первая (§1);
 * - лимит 8 вкладок (ОВ-2), переполнение таб-бара — горизонтальный скролл
 *   (ОВ-3); последнюю вкладку удалить нельзя (× нет на единственной);
 * - переименование — двойной клик по вкладке в РЕЖИМЕ РЕДАКТИРОВАНИЯ
 *   (инлайн-input как у спойлера F-3; в статье вкладки не переименовываются
 *   вообще — только переключаются); tab-элемент — div role=tab (не button):
 *   input внутри button не получает фокус в части браузеров — дефект
 *   «переименовать нельзя» (багфикс p12-rich-2); Escape = отмена,
 *   единственная точка завершения (паттерн QA D1 спойлера);
 * - содержимое вкладок — независимые зоны с любым контентом (в т.ч.
 *   другие блоки, §6); сохранение дерево не перестраивает (урок rich-v1).
 */

import {
  el, editorEl, placeCaretStart,
  PART_ATTR, TITLE_ATTR, TAB_LIMIT, DEFAULT_TAB_TITLE
} from './model.js';

export function tabPanes(block) {
  var result = [];
  var children = block.children;
  for (var i = 0; i < children.length; i += 1) {
    if (children[i].getAttribute && children[i].getAttribute(PART_ATTR) === 'tab') {
      result.push(children[i]);
    }
  }
  return result;
}

function paneTitle(pane) {
  return pane.getAttribute(TITLE_ATTR) || DEFAULT_TAB_TITLE;
}

function activatePane(block, panes, buttons, index) {
  panes.forEach(function (pane, i) {
    pane.hidden = i !== index;
  });
  buttons.forEach(function (button, i) {
    button.classList.toggle('active', i === index);
    button.setAttribute('aria-selected', i === index ? 'true' : 'false');
  });
}

function makeRename(pane, button, block) {
  function startRename() {
    if (button.querySelector('.tab-rename')) return;
    var closeSpan = button.querySelector('.tab-close');
    var input = editorEl('input', 'tab-rename');
    input.type = 'text';
    input.value = paneTitle(pane);
    input.setAttribute('aria-label', 'Название вкладки');
    button.textContent = '';
    button.appendChild(input);
    input.focus();
    input.select();

    /* Единственная точка завершения переименования (паттерн QA D1
     * спойлера): первый close() финален, повторный (blur после Escape)
     * — no-op. Escape = ОТМЕНА: data-title не меняется, «×» возвращается
     * (до фикса blur после Escape коммитил введенный текст и терял «×»). */
    var finished = false;
    function close(commit) {
      if (finished) return;
      finished = true;
      var value;
      if (commit) {
        value = input.value.trim() || DEFAULT_TAB_TITLE + ' ' + (
          tabPanes(block).indexOf(pane) + 1
        );
        pane.setAttribute(TITLE_ATTR, value);
      } else {
        value = paneTitle(pane);
      }
      /* текст + крестик «×»: textContent затер бы служебный span */
      button.textContent = value;
      if (closeSpan) button.appendChild(closeSpan);
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
  return startRename;
}

/* Таб-бар: кнопки вкладок [+ «×»/переименование в редакторе] + «+». */
function buildTabBar(block, editable) {
  var bar = editorEl('div', 'tabbar');
  bar.setAttribute('role', 'tablist');
  bar.setAttribute('aria-label', 'Вкладки');

  var panes = tabPanes(block);
  var buttons = [];

  function refreshAddButton() {
    var add = bar.querySelector('.tab-add');
    if (!add) return;
    var full = tabPanes(block).length >= TAB_LIMIT;
    add.disabled = full;
    add.title = full
      ? 'Лимит — ' + TAB_LIMIT + ' вкладок'
      : 'Добавить вкладку';
  }

  function rebuild() {
    /* Пересборка ТОЛЬКО data-editor таб-бара; контентные pane-узлы
     * (data-block-part) не трогаются — инвариант сериализации (§3). */
    bar.textContent = '';
    var panes = tabPanes(block);
    buttons = [];
    panes.forEach(function (pane, index) {
      /* div role=tab (НЕ button): input внутри <button> не получает фокус
       * в части браузеров — переименование «не работает» (p12-rich-2).
       * Стили — по классу .tab, смена тега разметку не меняет. */
      var button = el('div', 'tab');
      button.setAttribute('role', 'tab');
      button.tabIndex = 0;
      button.setAttribute('aria-selected', 'false');
      button.textContent = paneTitle(pane);
      if (editable) {
        var close = editorEl('span', 'tab-close', '×');
        close.title = 'Удалить вкладку';
        close.addEventListener('click', function (event) {
          event.stopPropagation();
          if (tabPanes(block).length <= 1) return; // последнюю не удалить
          pane.remove();
          close.remove();
          rebuild();
          activatePane(block, tabPanes(block), buttons, 0);
        });
        button.appendChild(close);
        button.addEventListener('dblclick', makeRename(pane, button, block));
        button.addEventListener('click', function () {
          activatePane(block, tabPanes(block), buttons, index);
          /* Каретка — в активированную панель (в редакторе): раньше переносил
           * побочный эффект фокуса button, после div role=tab делаем явно,
           * иначе ввод после переключения вкладки идет мимо (p12-rich-2). */
          var paneNow = tabPanes(block)[index];
          if (paneNow) placeCaretStart(paneNow);
        });
      } else {
        button.addEventListener('click', function () {
          activatePane(block, tabPanes(block), buttons, index);
        });
      }
      /* Клавиатурная активация (у div нет нативной кнопочной): Enter/Space.
       * Во время rename event.target — input, не переключаем. */
      button.addEventListener('keydown', function (event) {
        if (event.target.closest('.tab-rename')) return;
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          activatePane(block, tabPanes(block), buttons, index);
          var paneNow = tabPanes(block)[index];
          if (paneNow) placeCaretStart(paneNow);
        }
      });
      /* В обоих режимах индекс вкладки фиксируется на момент сборки:
       * в редакторе rebuild пересобирает кнопки после добавления/удаления. */
      buttons.push(button);
      bar.insertBefore(button, bar.querySelector('.tab-add'));
    });
    if (editable) {
      var add = el('button', 'tab-add', '+');
      add.type = 'button';
      add.setAttribute('aria-label', 'Добавить вкладку');
      add.addEventListener('click', function () {
        if (tabPanes(block).length >= TAB_LIMIT) return; // лимит 8 (ОВ-2)
        var pane = el('div');
        pane.setAttribute(PART_ATTR, 'tab');
        pane.setAttribute(
          TITLE_ATTR,
          DEFAULT_TAB_TITLE + ' ' + (tabPanes(block).length + 1)
        );
        pane.innerHTML = '<p><br></p>';
        block.appendChild(pane);
        pane.classList.add('tab-pane');
        rebuild();
        var fresh = tabPanes(block);
        activatePane(block, fresh, buttons, fresh.length - 1);
        refreshAddButton();
        placeCaretStart(pane);
      });
      bar.appendChild(add);
    }
    activatePane(block, panes, buttons, 0);
    refreshAddButton();
  }

  rebuild();
  return bar;
}

function enhance(block, editable) {
  if (block.classList.contains('rich-active')) return;
  block.classList.add('rich-active', 'tabswidget');
  var panes = tabPanes(block);
  panes.forEach(function (pane) {
    pane.classList.add('tab-pane');
  });
  if (!panes.length) {
    var pane = el('div');
    pane.setAttribute(PART_ATTR, 'tab');
    pane.setAttribute(TITLE_ATTR, DEFAULT_TAB_TITLE + ' 1');
    pane.innerHTML = '<p><br></p>';
    block.appendChild(pane);
    pane.classList.add('tab-pane');
  }
  var bar = buildTabBar(block, editable);
  block.insertBefore(bar, block.firstChild);
}

export function enhanceEditor(block) {
  enhance(block, true);
}

export function activateView(block) {
  enhance(block, false);
}

/* Разметка нового таб-виджета (две вкладки — мокап). */
export function newTabsHtml() {
  return (
    '<div data-block="tabs">' +
    '<div data-block-part="tab" data-title="Вкладка 1"><p><br></p></div>' +
    '<div data-block-part="tab" data-title="Вкладка 2"><p><br></p></div>' +
    '</div><p><br></p>'
  );
}

/* После insertHTML: каретка в содержимое первой вкладки. */
export function focusInsertedTabs(area) {
  var blocks = area.querySelectorAll('[data-block="tabs"]');
  var block = blocks[blocks.length - 1];
  if (!block) return null;
  var pane = tabPanes(block)[0];
  if (pane) placeCaretStart(pane);
  return block;
}
