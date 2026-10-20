/* Контекстное управление таблицами P12 (FR-122, design.md §3; мокап
 * design/p12-rich/tool-5-table-*). Модуль ТОЛЬКО редактора — в рендере
 * таблица остается прежним HTML со стилями .article-body table.
 *
 * ОВ-4: панель появляется контекстно при фокусе внутри таблицы — «+»/«−»
 * строк и столбцов ОТНОСИТЕЛЬНО целевой ячейки (столбец целика — голубой
 * тинт), отдельная кнопка «Удалить таблицу». «−» на последней строке/
 * столбце неактивен (disabled + подсказка). Tab/Shift+Tab — навигация по
 * ячейкам; Enter в ячейке — перенос <br>, не новая строка.
 *
 * Панель — служебный узел data-editor: в сохраняемый контент не попадает
 * (design.md §3, находка F1). Кнопки работают на mousedown (фокус из
 * ячейки не уходит, выделение не сбивается — паттерн toolbar editor.js).
 */

import { el, editorEl } from './model.js';

var PANEL_CLASS = 'tbl-panel';

function targetCell(area) {
  var selection = window.getSelection();
  if (!selection || !area.contains(selection.anchorNode)) return null;
  /* anchorNode — обычно ТЕКСТОВЫЙ узел (closest есть только у элементов) */
  var node = selection.anchorNode;
  var element = node.nodeType === 1 ? node : node.parentNode;
  if (!element || !element.closest) return null;
  var cell = element.closest('td,th');
  return cell && area.contains(cell) ? cell : null;
}

function tableRows(table) {
  return Array.prototype.slice.call(table.querySelectorAll('tr'));
}

/* Ячейки целевого столбца (по индексу ячейки внутри tr). */
function columnCells(table, colIndex) {
  var cells = [];
  tableRows(table).forEach(function (row) {
    var cell = row.children[colIndex];
    if (cell) cells.push(cell);
  });
  return cells;
}

function columnCount(table) {
  var max = 0;
  tableRows(table).forEach(function (row) {
    if (row.children.length > max) max = row.children.length;
  });
  return max;
}

function markColumnTarget(table, colIndex) {
  table.querySelectorAll('.col-target').forEach(function (cell) {
    cell.classList.remove('col-target');
  });
  columnCells(table, colIndex).forEach(function (cell) {
    cell.classList.add('col-target');
  });
}

function clearColumnTarget(table) {
  table.querySelectorAll('.col-target').forEach(function (cell) {
    cell.classList.remove('col-target');
  });
}

/* Каретка в ячейку (после удаления строки/столбца — в соседнюю: выделение
 * не должно «повисать» на контейнере таблицы, иначе панель гаснет). */
function placeCaretInCell(cell) {
  if (!cell) return;
  var range = document.createRange();
  range.selectNodeContents(cell);
  range.collapse(true);
  var selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
}

/* Операции относительно целевой ячейки (spec FR-122): вставка ниже/правее
 * целевой; удаление — столбца/строки целика. */
var OPS = {
  addRow: function (table, cell) {
    var row = cell.closest('tr');
    var fresh = el('tr');
    for (var i = 0; i < row.children.length; i += 1) {
      var td = el('td');
      td.innerHTML = '<br>';
      fresh.appendChild(td);
    }
    row.parentNode.insertBefore(fresh, row.nextSibling);
  },
  delRow: function (table, cell) {
    if (tableRows(table).length <= 1) return null; // последняя — нельзя
    var row = cell.closest('tr');
    var colIndex = Array.prototype.indexOf.call(row.children, cell);
    /* соседняя строка — по ПЛОСКОМУ списку строк таблицы (thead/tbody —
     * разные родители: previousElementSibling через секцию не проходит) */
    var rowsAll = tableRows(table);
    var index = rowsAll.indexOf(row);
    row.remove();
    var neighbor = rowsAll[index + 1] || rowsAll[index - 1] || null;
    if (neighbor && neighbor.children.length) {
      var target = Math.min(colIndex, neighbor.children.length - 1);
      /* каретка — в ту же колонку соседней строки; ставится ОТЛОЖЕННО
       * (см. обработчик кнопки): браузер асинхронно «хилит» выделение
       * после удаления якорного узла и затирает синхронную установку */
      return neighbor.children[target];
    }
    return null;
  },
  addCol: function (table, cell) {
    var index = Array.prototype.indexOf.call(cell.parentNode.children, cell);
    tableRows(table).forEach(function (row) {
      var ref = row.children[index] ? row.children[index].nextSibling : null;
      /* в строке шапки вставляется th (мокап: thead — заголовки) */
      var isHead = row.children[index] && row.children[index].nodeName === 'TH';
      var cellEl = el(isHead ? 'th' : 'td');
      cellEl.innerHTML = '<br>';
      row.insertBefore(cellEl, ref);
    });
  },
  delCol: function (table, cell) {
    if (columnCount(table) <= 1) return null; // последний столбец — нельзя
    var row = cell.parentNode; // ДО удаления ячейки (иначе parentNode null)
    var index = Array.prototype.indexOf.call(row.children, cell);
    tableRows(table).forEach(function (r) {
      if (r.children[index]) r.children[index].remove();
    });
    /* каретка — в соседний столбец той же строки (отложенно, см. delRow) */
    var target = Math.min(index, row.children.length - 1);
    return row.children[target] || null;
  }
};

/* Панель: собирается один раз, показывается у активной таблицы. */
function buildPanel(area, hide, show) {
  var panel = editorEl('div', PANEL_CLASS);
  panel.setAttribute('role', 'toolbar');
  panel.setAttribute('aria-label', 'Управление таблицей');

  function op(name, label, title) {
    var button = el('button', 'ctx-btn', label);
    button.type = 'button';
    button.title = title;
    button.setAttribute('aria-label', title);
    /* mousedown — ячейка остается целевой (фокус не уходит из таблицы). */
    button.addEventListener('mousedown', function (event) {
      event.preventDefault();
    });
    button.addEventListener('click', function (event) {
      event.preventDefault();
      var cell = targetCell(area);
      var table = cell ? cell.closest('table') : null;
      if (!table) return;
      var nextCell = OPS[name](table, cell);
      refresh(table, nextCell || cell);
      if (nextCell) {
        /* Браузер асинхронно «лечит» выделение после удаления якорного
         * узла (caret уезжает на контейнер таблицы) — ставим каретку в
         * соседнюю ячейку ОТЛОЖЕННО, после хила, и возвращаем панели
         * видимость (click-бабблинг успевает ее спрятать до хила). */
        window.setTimeout(function () {
          placeCaretInCell(nextCell);
          show();
          refresh(table, nextCell);
        }, 0);
      }
    });
    return button;
  }

  var delRowBtn = op('delRow', '−', 'Удалить строку');
  var delColBtn = op('delCol', '−', 'Удалить столбец');
  panel.appendChild(op('addRow', '+', 'Добавить строку ниже'));
  panel.appendChild(delRowBtn);
  panel.appendChild(op('addCol', '+', 'Добавить столбец справа'));
  panel.appendChild(delColBtn);

  /* Отдельная кнопка удаления таблицы (ОВ-4) — не «−» у краев. */
  var removeTable = el('button', 'ctx-btn ctx-remove', 'Удалить таблицу');
  removeTable.type = 'button';
  removeTable.title = 'Удалить таблицу целиком';
  removeTable.setAttribute('aria-label', 'Удалить таблицу целиком');
  removeTable.addEventListener('mousedown', function (event) {
    event.preventDefault();
  });
  removeTable.addEventListener('click', function (event) {
    event.preventDefault();
    var cell = targetCell(area);
    var table = cell ? cell.closest('table') : null;
    if (!table) return;
    var after = el('p');
    after.innerHTML = '<br>';
    table.parentNode.insertBefore(after, table.nextSibling);
    table.remove();
    hide();
    area.focus();
  });
  panel.appendChild(removeTable);

  /* Подсказка (мокап: строка-подсказка под таблицей). */
  panel.appendChild(
    el(
      'span',
      'tbl-hint',
      'Tab — следующая ячейка · Enter — перенос в ячейке · ' +
        'последнюю строку/столбец удалить нельзя'
    )
  );

  /* disabled «−» на последней строке/столбце (spec FR-122); aria-label
     синхронизируется с подсказкой — доступное имя = текущее состояние. */
  var refresh = function (table, cell) {
    delRowBtn.disabled = tableRows(table).length <= 1;
    delRowBtn.title = delRowBtn.disabled
      ? 'Последнюю строку удалить нельзя'
      : 'Удалить строку';
    delRowBtn.setAttribute('aria-label', delRowBtn.title);
    delColBtn.disabled = columnCount(table) <= 1;
    delColBtn.title = delColBtn.disabled
      ? 'Последний столбец удалить нельзя'
      : 'Удалить столбец';
    delColBtn.setAttribute('aria-label', delColBtn.title);
    if (cell) {
      var index = Array.prototype.indexOf.call(cell.parentNode.children, cell);
      markColumnTarget(table, index);
    }
  };
  panel.refresh = refresh;
  return panel;
}

/* Навигация/ввод в ячейках: Tab/Shift+Tab — соседняя ячейка; Enter —
 * <br> внутри ячейки (spec FR-122, сценарий «Навигация и ввод»). */
function bindCellKeys(area) {
  area.addEventListener('keydown', function (event) {
    var cell = targetCell(area);
    if (!cell) return;
    var table = cell.closest('table');
    if (event.key === 'Tab') {
      event.preventDefault();
      var cells = [];
      tableRows(table).forEach(function (row) {
        Array.prototype.forEach.call(row.children, function (c) {
          cells.push(c);
        });
      });
      var index = cells.indexOf(cell);
      var step = event.shiftKey ? -1 : 1;
      var next = cells[index + step];
      if (next) {
        var range = document.createRange();
        range.selectNodeContents(next);
        range.collapse(!event.shiftKey);
        var selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      }
    } else if (event.key === 'Enter') {
      event.preventDefault();
      document.execCommand('insertHTML', false, '<br>');
    }
  });
}

/* Установка модуля в редактируемую область (editor.js вызывает один раз). */
export function install(area) {
  function hide() {
    panel.hidden = true;
    area.querySelectorAll('table').forEach(clearColumnTarget);
  }
  var panel = buildPanel(area, hide, showPanel);
  panel.hidden = true;
  area.appendChild(panel);
  bindCellKeys(area);

  /* Панель показывается при ЛЮБОМ движении фокуса/каретки в таблицу:
     focusin не fires при клике внутри уже-фокусированного contenteditable —
     дублируем click/keyup (панель одна, show идемпотентен). */
  function showPanel() {
    var cell = targetCell(area);
    var table = cell ? cell.closest('table') : null;
    if (!table) {
      hide();
      return;
    }
    panel.hidden = false;
    /* Позиционирование над таблицей (мокап: панель у целевого столбца). */
    var areaRect = area.getBoundingClientRect();
    var tableRect = table.getBoundingClientRect();
    panel.style.left = Math.max(0, tableRect.left - areaRect.left) + 'px';
    panel.style.top = Math.max(0, tableRect.top - areaRect.top - 34) + 'px';
    panel.refresh(table, cell);
  }

  area.addEventListener('focusin', showPanel);
  area.addEventListener('click', showPanel);
  area.addEventListener('keyup', showPanel);

  /* Уход фокуса из таблицы — панель прячется (клик по кнопке не считается:
   * mousedown с preventDefault фокус не меняет). */
  area.addEventListener('focusout', function (event) {
    window.setTimeout(function () {
      var active = document.activeElement;
      if (panel.contains(active)) return;
      var cell = targetCell(area);
      if (!cell || !cell.closest('table')) hide();
    }, 0);
  });

  return panel;
}
