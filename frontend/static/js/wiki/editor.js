/* WYSIWYG-редактор страниц Wiki (tasks.md 3.3 add-wiki; FR-110, FR-111;
 * design §5, §7) — СТРОГО по утвержденному мокапу design/wiki-editor.html.
 *
 * Vanilla contenteditable + document.execCommand/Selection API — БЕЗ внешних
 * библиотек/CDN (ОГР-8). Разметку тулбара/диалогов рисует модуль
 * (createElement + textContent; статические SVG — innerHTML из мокапа,
 * данных пользователя там нет).
 *
 * Режимы (вход — параметры URL, ТЗ 3.3):
 *   - правка существующей: /wiki/{id}?edit=1  → GET /api/wiki/pages/{id}
 *     → заполнение → PUT /api/wiki/pages/{id};
 *   - создание новой: /wiki?create=1[&parent={id}] → POST /api/wiki/pages.
 * Без параметров модуль не активен (контейнер #wiki-editor остается hidden).
 *
 * Сохранение: HTML из редактора уходит КАК ЕСТЬ — санитизация на сервере
 * (design §4); пустой заголовок — ошибка по мокапу БЕЗ запроса; успех —
 * redirect /wiki/{id}; 401 (протухшая сессия) — redirect /login.
 *
 * Изображения (design §5, FR-111): диалог «из галереи / с диска» —
 *   галерея: GET /api/images (грид-выбор превью);
 *   диск:    file input → POST /api/images (multipart; 422 лимитов NFR-21 —
 *            в баннере диалога);
 *   вставка: <img src="/images/{...}" alt [width]> (относительный URL из
 *            ответа images-API — data.url, /images/{filename}; design.md §5
 *            «/images/{id}» — плейсхолдер этой относительной ссылки).
 *   Масштаб (возврат живой приемки 2026-10-11, как в Confluence): выбор
 *   «Оригинал / Среднее (480 px) / Маленькое (240 px) / Свой размер (px)»;
 *   свой размер — только целые 16..4096, невалид — отказ вставки; клик по
 *   уже вставленному img открывает тот же выбор и меняет width на месте.
 *
 * Ссылка: модальный ввод (по мокапу); схема проверяется ДО вставки —
 * только http:, https: и относительные «/...» (javascript:/data: — отказ,
 * ничего не вставляется).
 *
 * Rich-блоки (change add-rich-editor, tasks.md 1.6; design §4 D4): при
 * загрузке страницы контент парсится (rich/block-parser.js — зеркало
 * серверной грамматики); блоки диалекта → интерактивное редактирование
 * block-модулями через renderCanvas (тот же renderer, что на просмотре —
 * WYSIWYG FR-124); legacy-HTML без блоков — существующее поведение без
 * изменений (FR-125). При сохранении: сериализация блоков в диалект,
 * структурные ошибки перехватываются rich-валидатором ДО отправки
 * (строгая валидация НОВОГО rich-контента — design §1: на сервере в этом
 * случае 422 нет). Кнопки вставки блоков — rich/toolbar.js (реестр).
 */

import * as richParser from "./rich/block-parser.js";
import { renderCanvas, legacyHtmlNode } from "./rich/renderer.js";
import { buildBlockBar } from "./rich/toolbar.js";
/* Импорт = саморегистрация блок-модулей в реестре (design §2) */
import "./rich/blocks/tables.js";
import "./rich/blocks/columns.js";
import "./rich/blocks/callout.js";
import "./rich/blocks/aside.js";
import "./rich/blocks/spoiler.js";
import "./rich/blocks/code.js";
import "./rich/blocks/image-scale.js";

(function () {
  'use strict';

  /* ------------------------------------------------------------------ */
  /* Состояние модуля                                                    */
  /* ------------------------------------------------------------------ */

  var state = {
    mode: null, // 'create' | 'edit'
    pageId: null,
    parentPreselect: null,
    titleInput: null,
    parentSelect: null,
    area: null,
    errorBox: null,
    toolbarButtons: {}, // aria-label → button
    /* rich-блоки (tasks.md 1.6): null = legacy-режим (существующее
       поведение), иначе { canvas, activeCanvas } — канвы renderCanvas */
    rich: null,
    /* диалог изображения */
    imgDialog: null,
    imgError: null,
    imgGrid: null,
    imgFileInput: null,
    imgRadioGallery: null,
    imgRadioDisk: null,
    imgSelectedUrl: null,
    imgSelectedAlt: '',
    imgSelectedName: '',
    /* масштаб изображения (возврат живой приемки 2026-10-11, как в
       Confluence): refs пикеров {radios, customWrap, customInput} —
       отдельный для диалога вставки и модалки уже вставленного img */
    imgScale: null,
    /* модалка масштаба УЖЕ вставленного img (усиление в духе Confluence) */
    imgScaleEditorDialog: null,
    imgScaleEditorError: null,
    imgScaleTarget: null,
    imgScaleEditor: null,
    /* диалог ссылки */
    linkDialog: null,
    linkInput: null,
    linkError: null
  };

  /* ------------------------------------------------------------------ */
  /* Утилиты DOM (данные пользователя — только textContent, XSS-паттерн) */
  /* ------------------------------------------------------------------ */

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function svgIcon(markup) {
    /* Статические inline-SVG из мокапа (не данные) */
    var span = el('span', 'tb-icon');
    span.setAttribute('aria-hidden', 'true');
    span.innerHTML = markup;
    return span;
  }

  var ICONS = {
    bold: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h6a3.5 3.5 0 0 1 0 7H7zm0 7h7a3.5 3.5 0 0 1 0 7H7z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
    italic: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 5h8M6 19h8M14 5l-4 14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    underline: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4v7a5 5 0 0 0 10 0V4M5 20h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    ul: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6h11M9 12h11M9 18h11" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="4.5" cy="6" r="1.4" fill="currentColor"/><circle cx="4.5" cy="12" r="1.4" fill="currentColor"/><circle cx="4.5" cy="18" r="1.4" fill="currentColor"/></svg>',
    ol: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 6h10M10 12h10M10 18h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><text x="3" y="8" font-size="7" fill="currentColor">1</text><text x="3" y="14" font-size="7" fill="currentColor">2</text><text x="3" y="20" font-size="7" fill="currentColor">3</text></svg>',
    quote: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h4M5 12h9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M4 6v12" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>',
    code: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M9 10l-2.5 2L9 14M15 10l2.5 2L15 14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    link: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 14a4 4 0 0 0 6 .5l3-3a4 4 0 0 0-5.7-5.7l-1.5 1.5M14 10a4 4 0 0 0-6-.5l-3 3a4 4 0 0 0 5.7 5.7l1.5-1.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    table: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3 10h18M9 10v9M15 10v9" stroke="currentColor" stroke-width="2"/></svg>',
    image: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="9" cy="9.5" r="1.6" fill="currentColor"/><path d="M4.5 17.5l5-5.5 4 4.5 3-3 3 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    undo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5L3 10l5 5M3 10h11a6 6 0 0 1 0 12h-3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    redo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 5l5 5-5 5M21 10H10a6 6 0 0 0 0 12h3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    save: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 13l4 4L19 7" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
  };

  /* ------------------------------------------------------------------ */
  /* API-хелперы (паттерн history.js/search.js: 401 → /login)            */
  /* ------------------------------------------------------------------ */

  function parseBody(response) {
    try {
      return response.json();
    } catch (err) {
      return Promise.resolve(null);
    }
  }

  function handleApiError(response, body, onError) {
    if (response.status === 401) {
      window.location.href = '/login';
      return;
    }
    if (body && typeof body.error === 'string' && body.error) {
      onError(body.error);
      return;
    }
    if (body && body.detail) {
      /* detail — машинный текст ответа («Not Found» и т.п.), пользователю
         показываем человеческую формулировку (DV-8 review-001) */
      if (typeof body.detail === 'string' && body.detail.length > 0) {
        onError(friendlyApiMessage(response.status, body.detail));
        return;
      }
      /* FastAPI 422-валидация: detail — массив объектов с msg */
      onError('Проверьте правильность заполнения формы.');
      return;
    }
    onError('Ошибка запроса (HTTP ' + response.status + ').');
  }

  /* Сырой detail (например «Not Found» при недоступном /api/images) в
     баннер не попадает — только человекочитаемый текст (DV-8 review-001). */
  function friendlyApiMessage(status, detail) {
    var known = [
      'not found',
      'not allowed',
      'forbidden',
      'unauthorized',
      'validation error',
      'server error'
    ];
    var text = String(detail).trim();
    if (
      text.length <= 32 &&
      known.some(function (word) { return text.toLowerCase().indexOf(word) !== -1; })
    ) {
      return 'Не удалось загрузить данные (HTTP ' + status + ').';
    }
    return text;
  }

  function api(path, options, onError, onOk) {
    fetch(path, Object.assign({ credentials: 'same-origin' }, options))
      .then(function (response) {
        var done = function (body) {
          if (response.ok) {
            onOk(body);
          } else {
            handleApiError(response, body, onError);
          }
        };
        parseBody(response).then(done);
      })
      .catch(function () {
        onError('Сетевая ошибка. Проверьте соединение и попробуйте еще раз.');
      });
  }

  /* ------------------------------------------------------------------ */
  /* Rich-блоки: режим канвы, вставка, сериализация (tasks.md 1.6)       */
  /* ------------------------------------------------------------------ */

  var richCtx = {
    editing: true,
    onChange: function () {}, // привязки канвы пишут в узлы напрямую
    registerCanvas: function (canvas) {
      /* Активная канва верхнего уровня — при рендере документа; вложенные
         канвы (колонки/callout/врезка/спойлер) становятся активными по
         фокусу (bindAreaFocusTracking — вставка внутрь, 2.5). */
      if (canvas.element === state.area) {
        state.rich.activeCanvas = canvas;
      }
    },
    refreshActive: function () {
      if (!state.rich) return;
      renderCanvas(state.rich.activeCanvas || state.rich.canvas, richCtx);
    },
  };

  function enterRichMode(initialNodes) {
    if (state.rich) return;
    var nodes = initialNodes || [legacyHtmlNode(state.area.innerHTML)];
    var canvas = { nodes: nodes, element: state.area };
    state.rich = { canvas: canvas, activeCanvas: canvas };
    renderCanvas(canvas, richCtx);
  }

  function insertIndex(canvas) {
    /* Индекс вставки: по каретке (selection anchor) внутри канвы, иначе —
       в конец канвы. Фокус при клике в канве уходит внешнему editing host
       (наблюдение Chromium), поэтому активный элемент неинформативен. */
    var selection = window.getSelection();
    if (selection && selection.anchorNode) {
      var node =
        selection.anchorNode.nodeType === 1
          ? selection.anchorNode
          : selection.anchorNode.parentNode;
      while (node && node !== canvas.element) {
        if (node.__richCanvas === canvas && node.__richIndex !== undefined) {
          return node.__richIndex;
        }
        node = node.parentElement;
      }
    }
    return canvas.nodes.length - 1;
  }

  function onInsertBlock(makeNode) {
    if (!state.rich) enterRichMode();
    var canvas = state.rich.activeCanvas || state.rich.canvas;
    var index = insertIndex(canvas);
    canvas.nodes.splice(index + 1, 0, makeNode());
    renderCanvas(canvas, richCtx);
    state.rich.activeCanvas = canvas;
    /* фокус в первый редактируемый элемент нового блока */
    var inserted = canvas.element.children[index + 1];
    if (inserted) {
      var editable = inserted.querySelector('[contenteditable="true"]');
      if (editable) editable.focus();
    }
  }

  function serializeRichContent() {
    /* Канонический диалект: legacy-сегменты — HTML как есть (санитизация
       на сервере), блоки — сериализатор реестра (зеркало бэкенда). */
    return state.rich.canvas.nodes
      .map(function (node) {
        if (node.type === "legacyhtml") return node.html;
        return richParser.serializeNodes([node]);
      })
      .join("\n");
  }

  function bindAreaFocusTracking(area) {
    /* Активная канва для вставки блоков (в т.ч. вложенных, 2.5).
       Фокус (focusin) при клике в канве уходит внешнему editing host
       (Chromium), поэтому канву определяем по ФАКТИЧЕСКОМУ элементу клика
       (mousedown.target) и по позиции каретки (keyup — переходы стрелками). */
    function resolveFromTarget(target) {
      var node = target;
      while (node && node !== area) {
        if (node.__richCanvas) {
          state.rich.activeCanvas = node.__richCanvas;
          return true;
        }
        node = node.parentNode;
      }
      return false;
    }

    area.addEventListener(
      "mousedown",
      function (event) {
        if (!state.rich) return;
        if (resolveFromTarget(event.target)) return;
        state.rich.activeCanvas = state.rich.canvas;
      },
      true
    );
    area.addEventListener(
      "keyup",
      function (event) {
        if (!state.rich) return;
        if (event.target === area && !resolveFromCaret()) {
          state.rich.activeCanvas = state.rich.canvas;
        }
      },
      true
    );

    function resolveFromCaret() {
      var selection = window.getSelection();
      if (!selection || !selection.anchorNode || !area.contains(selection.anchorNode)) {
        return false;
      }
      var node =
        selection.anchorNode.nodeType === 1
          ? selection.anchorNode
          : selection.anchorNode.parentNode;
      while (node && node !== area) {
        if (node.__richCanvas) {
          state.rich.activeCanvas = node.__richCanvas;
          return true;
        }
        node = node.parentNode;
      }
      return false;
    }
  }

  /* ------------------------------------------------------------------ */
  /* Построение каркаса редактора (мокап wiki-editor.html)               */
  /* ------------------------------------------------------------------ */

  function toolbarButton(label, iconMarkup, className, onClick, options) {
    var button = el('button', 'tb-btn' + (className ? ' ' + className : ''));
    button.type = 'button';
    /* title может нести подсказку хоткея (мокап: «Отменить (Ctrl+Z)»),
       aria-label — без нее (скринридер читает только действие) */
    button.title = options && options.title ? options.title : label;
    button.setAttribute('aria-label', label);
    /* aria-pressed — только у кнопок-состояний (мокап: B/I/U, списки,
       H1–H3, цитата, код-блок; у «ссылка/таблица/изображение/undo/redo»
       нажатие — действие, не состояние — DV-7 review-001) */
    if (!options || options.stateful !== false) {
      button.setAttribute('aria-pressed', 'false');
    }
    if (iconMarkup) button.appendChild(svgIcon(iconMarkup));
    /* mousedown preventDefault — выделение в редакторе не сбивается */
    button.addEventListener('mousedown', function (event) {
      event.preventDefault();
    });
    button.addEventListener('click', onClick);
    state.toolbarButtons[label] = button;
    return button;
  }

  function headingButton(label, text) {
    var button = toolbarButton(label, null, 'tb-heading', function () {
      focusAreaAndRun(function () {
        document.execCommand('formatBlock', false, '<' + text.toLowerCase() + '>');
      });
      updateToolbarStates();
    });
    button.textContent = text;
    return button;
  }

  function execInArea(command, value) {
    /* Команда применяется к редактируемой области: каретка/выделение
       уже в ней (mousedown тулбара не забирает фокус). */
    document.execCommand(command, false, value || null);
  }

  function focusAreaAndRun(run) {
    if (!state.area.contains(window.getSelection().anchorNode)) {
      state.area.focus();
    }
    run();
  }

  function blockIs(tagName) {
    /* Активен ли блок tagName под кареткой (по formatBlock) */
    try {
      var value = String(document.queryCommandValue('formatBlock') || '').toLowerCase();
      return value === tagName.toLowerCase();
    } catch (err) {
      return false;
    }
  }

  function toggleCodeBlock() {
    if (blockIs('pre')) {
      document.execCommand('formatBlock', false, '<p>');
      updateToolbarStates();
      return;
    }
    document.execCommand('formatBlock', false, '<pre>');
    /* Обернуть содержимое затронутых pre в code (мокап: pre>code) */
    var seen = [];
    var node = window.getSelection().anchorNode;
    while (node && node !== state.area) {
      if (node.nodeName === 'PRE' && seen.indexOf(node) === -1) seen.push(node);
      node = node.parentNode;
    }
    seen.forEach(function (pre) {
      if (pre.querySelector('code')) return;
      var code = document.createElement('code');
      while (pre.firstChild) code.appendChild(pre.firstChild);
      pre.appendChild(code);
    });
    updateToolbarStates();
  }

  function insertTable3x3() {
    /* Таблица 3×3 по мокапу: строка заголовков + 2 строки ячеек */
    var th = '<thead><tr><th>Колонка 1</th><th>Колонка 2</th><th>Колонка 3</th></tr></thead>';
    var row = '<tr><td><br></td><td><br></td><td><br></td></tr>';
    var html = '<table>' + th + '<tbody>' + row + row + '</tbody></table><p><br></p>';
    document.execCommand('insertHTML', false, html);
  }

  /* ------------------------------------------------------------------ */
  /* Масштаб изображения (возврат живой приемки 2026-10-11, как в        */
  /* Confluence): пресеты — решение PM в рамках возврата.                */
  /* ------------------------------------------------------------------ */

  /* Пресеты масштаба: оригинал — без width, среднее — 480px,
     маленькое — 240px. Значения фиксированы решением PM (возврат). */
  var IMG_SCALE_PRESET_WIDTH = { original: null, medium: 480, small: 240 };
  var IMG_SCALE_MIN_PX = 16;
  var IMG_SCALE_MAX_PX = 4096;

  /* Свой размер: только целые 16..4096 px — невалид (дробное, меньше 16,
     больше 4096, мусор) — отказ ВСТАВКИ, как у схем ссылок: ничего не
     вставляется, показывается ошибка. */
  function parseCustomScaleWidth(raw) {
    var value = String(raw || '').trim();
    if (!/^\d+$/.test(value)) return null;
    var parsed = parseInt(value, 10);
    if (parsed < IMG_SCALE_MIN_PX || parsed > IMG_SCALE_MAX_PX) return null;
    return parsed;
  }

  function selectedScaleWidth(picker) {
    var target = picker || state.imgScale;
    var checked = target.radios.filter(function (radio) {
      return radio.checked;
    })[0];
    var scale = checked ? checked.value : 'original';
    if (scale !== 'custom') return IMG_SCALE_PRESET_WIDTH[scale];
    return parseCustomScaleWidth(target.customInput.value);
  }

  function buildScalePicker(dialog, idSuffix) {
    var ids = {
      original: 'img-scale-original' + idSuffix,
      medium: 'img-scale-medium' + idSuffix,
      small: 'img-scale-small' + idSuffix,
      custom: 'img-scale-custom' + idSuffix,
      customValue: 'img-scale-custom-value' + idSuffix
    };
    var field = el('div', 'meta-field img-scale-field');
    var label = el('label', null, 'Масштаб');
    label.htmlFor = ids.original;
    field.appendChild(label);

    var radios = el('div', 'radio-row img-scale-row');
    var options = [
      { value: 'original', text: ' Оригинал', id: 'img-scale-original' },
      { value: 'medium', text: ' Среднее (480 px)', id: 'img-scale-medium' },
      { value: 'small', text: ' Маленькое (240 px)', id: 'img-scale-small' },
      { value: 'custom', text: ' Свой размер (px)', id: 'img-scale-custom' }
    ];
    var radioInputs = [];
    var customWrap;
    var customInput;
    function switchInput() {
      var checked = radioInputs.filter(function (radio) {
        return radio.checked;
      })[0];
      var isCustom = !!checked && checked.value === 'custom';
      customWrap.hidden = !isCustom;
      if (isCustom) customInput.focus();
    }
    radioInputs = options.map(function (option) {
      var radioLabel = el('label');
      var radio = el('input');
      radio.type = 'radio';
      radio.name = 'img-scale';
      radio.id = ids[option.value];
      radio.value = option.value;
      radio.checked = option.value === 'original';
      radio.addEventListener('change', switchInput);
      radioLabel.appendChild(radio);
      radioLabel.appendChild(document.createTextNode(option.text));
      radios.appendChild(radioLabel);
      return radio;
    });
    field.appendChild(radios);

    customWrap = el('div', 'img-scale-custom-wrap');
    customWrap.hidden = true;
    customInput = el('input', 'meta-title img-scale-custom-input');
    customInput.type = 'number';
    customInput.id = ids.customValue;
    customInput.min = String(IMG_SCALE_MIN_PX);
    customInput.max = String(IMG_SCALE_MAX_PX);
    customInput.step = '1';
    customInput.placeholder = IMG_SCALE_MIN_PX + '–' + IMG_SCALE_MAX_PX;
    customInput.setAttribute('aria-label', 'Свой размер в пикселях');
    customWrap.appendChild(customInput);
    field.appendChild(customWrap);

    dialog.appendChild(field);
    /* refs локальны диалогу (вставка и модалка img имеют ПО ОДНОМУ
       пикеру — общее state не переиспользуется) */
    return { radios: radioInputs, customWrap: customWrap, customInput: customInput };
  }

  function resetScalePicker(picker) {
    picker.radios.forEach(function (radio) {
      radio.checked = radio.value === 'original';
    });
    picker.customInput.value = '';
    picker.customWrap.hidden = true;
  }

  function buildToolbar() {
    var toolbar = el('div', 'toolbar');
    toolbar.setAttribute('role', 'toolbar');
    toolbar.setAttribute('aria-label', 'Форматирование');

    function group(children) {
      var div = el('div', 'tb-group');
      children.forEach(function (child) {
        div.appendChild(child);
      });
      return div;
    }

    function sep() {
      return el('span', 'tb-sep');
    }

    toolbar.appendChild(
      group([
        headingButton('Заголовок 1', 'H1'),
        headingButton('Заголовок 2', 'H2'),
        headingButton('Заголовок 3', 'H3')
      ])
    );
    toolbar.appendChild(sep());
    toolbar.appendChild(
      group([
        toolbarButton('Полужирный', ICONS.bold, null, function () {
          execInArea('bold');
          updateToolbarStates();
        }),
        toolbarButton('Курсив', ICONS.italic, null, function () {
          execInArea('italic');
          updateToolbarStates();
        }),
        toolbarButton('Подчеркнутый', ICONS.underline, null, function () {
          execInArea('underline');
          updateToolbarStates();
        })
      ])
    );
    toolbar.appendChild(sep());
    toolbar.appendChild(
      group([
        toolbarButton('Маркированный список', ICONS.ul, null, function () {
          execInArea('insertUnorderedList');
          updateToolbarStates();
        }),
        toolbarButton('Нумерованный список', ICONS.ol, null, function () {
          execInArea('insertOrderedList');
          updateToolbarStates();
        })
      ])
    );
    toolbar.appendChild(sep());
    toolbar.appendChild(
      group([
        toolbarButton('Цитата', ICONS.quote, null, function () {
          execInArea(
            'formatBlock',
            blockIs('blockquote') ? '<p>' : '<blockquote>'
          );
          updateToolbarStates();
        }),
        toolbarButton('Код-блок', ICONS.code, null, toggleCodeBlock)
      ])
    );
    toolbar.appendChild(sep());
    toolbar.appendChild(
      group([
        toolbarButton('Ссылка', ICONS.link, null, openLinkDialog, { stateful: false }),
        toolbarButton('Таблица', ICONS.table, null, function () {
          focusAreaAndRun(insertTable3x3);
        }, { stateful: false }),
        toolbarButton('Изображение', ICONS.image, 'tb-media', function () {
          focusAreaAndRun(openImageDialog);
        }, { stateful: false })
      ])
    );
    /* Текстовый лейбл «Изображение» рядом с иконкой (мокап: tb-media —
       ключевое действие; DV-5 review-001) */
    var mediaButton = state.toolbarButtons['Изображение'];
    if (mediaButton) {
      mediaButton.appendChild(document.createTextNode('Изображение'));
    }
    /* Rich-блоки (1.6): вставка таблицы/колонок и прочих блоков реестра */
    toolbar.appendChild(buildBlockBar(onInsertBlock));
    toolbar.appendChild(sep());
    toolbar.appendChild(
      group([
        toolbarButton('Отменить', ICONS.undo, null, function () {
          execInArea('undo');
          updateToolbarStates();
        }, { title: 'Отменить (Ctrl+Z)', stateful: false }),
        toolbarButton('Повторить', ICONS.redo, null, function () {
          execInArea('redo');
          updateToolbarStates();
        }, { title: 'Повторить (Ctrl+Shift+Z)', stateful: false })
      ])
    );
    return toolbar;
  }

  function buildMetaCard(title) {
    var card = el('div', 'meta-card');

    var titleField = el('div', 'meta-field');
    var titleLabel = el('label', null, 'Заголовок');
    titleLabel.htmlFor = 'page-title';
    var titleInput = el('input', 'meta-title');
    titleInput.type = 'text';
    titleInput.id = 'page-title';
    titleInput.value = title || '';
    titleInput.setAttribute('aria-label', 'Заголовок страницы');
    titleField.appendChild(titleLabel);
    titleField.appendChild(titleInput);
    card.appendChild(titleField);
    state.titleInput = titleInput;

    var row = el('div', 'meta-row');
    var parentField = el('div', 'meta-field');
    var parentLabel = el('label', null, 'Родительская страница');
    parentLabel.htmlFor = 'page-parent';
    var parentSelect = el('select', 'meta-select');
    parentSelect.id = 'page-parent';
    parentSelect.setAttribute('aria-label', 'Родительская страница');
    parentField.appendChild(parentLabel);
    parentField.appendChild(parentSelect);
    row.appendChild(parentField);
    card.appendChild(row);
    state.parentSelect = parentSelect;

    return card;
  }

  function buildEditorCard(titleText) {
    var card = el('div', 'editor-card');
    card.appendChild(buildToolbar());

    var area = el('div', 'editor-area');
    area.setAttribute('contenteditable', 'true');
    area.setAttribute('aria-label', 'Текст страницы');
    area.setAttribute('role', 'textbox');
    area.setAttribute('aria-multiline', 'true');
    card.appendChild(area);
    state.area = area;

    var footer = el('div', 'editor-footer');
    var status = el(
      'span',
      'editor-status',
      'HTML уходит как есть — санитизация на сервере (FR-110)'
    );
    footer.appendChild(status);

    var cancelButton = el('button', 'btn btn-secondary', 'Отмена');
    cancelButton.type = 'button';
    cancelButton.addEventListener('click', function () {
      window.location.href =
        state.mode === 'edit' ? '/wiki/' + state.pageId : '/wiki';
    });
    footer.appendChild(cancelButton);

    var saveButton = el('button', 'btn btn-primary');
    saveButton.type = 'button';
    saveButton.appendChild(svgIcon(ICONS.save));
    saveButton.appendChild(document.createTextNode('Сохранить'));
    saveButton.addEventListener('click', save);
    footer.appendChild(saveButton);

    card.appendChild(footer);
    return card;
  }

  /* ------------------------------------------------------------------ */
  /* Состояния кнопок тулбара (aria-pressed по текущему блоку/стилю)     */
  /* ------------------------------------------------------------------ */

  var PRESSED_BY_BLOCK = {
    'Заголовок 1': 'h1',
    'Заголовок 2': 'h2',
    'Заголовок 3': 'h3',
    'Цитата': 'blockquote',
    'Код-блок': 'pre'
  };

  var PRESSED_BY_STATE = {
    'Полужирный': 'bold',
    'Курсив': 'italic',
    'Подчеркнутый': 'underline',
    'Маркированный список': 'insertUnorderedList',
    'Нумерованный список': 'insertOrderedList'
  };

  function setPressed(label, pressed) {
    var button = state.toolbarButtons[label];
    if (button) button.setAttribute('aria-pressed', pressed ? 'true' : 'false');
  }

  function updateToolbarStates() {
    var selection = window.getSelection();
    if (!selection || !state.area) return;
    if (!state.area.contains(selection.anchorNode)) return;

    Object.keys(PRESSED_BY_BLOCK).forEach(function (label) {
      setPressed(label, blockIs(PRESSED_BY_BLOCK[label]));
    });
    Object.keys(PRESSED_BY_STATE).forEach(function (label) {
      var value = false;
      try {
        value = document.queryCommandState(PRESSED_BY_STATE[label]);
      } catch (err) {
        value = false;
      }
      setPressed(label, value);
    });
  }

  /* ------------------------------------------------------------------ */
  /* Диалог ссылки (модальный ввод по мокапу + проверка схемы)           */
  /* ------------------------------------------------------------------ */

  function validLinkUrl(raw) {
    var value = String(raw || '').trim();
    if (!value) return { ok: false, reason: 'empty' };
    if (value.charAt(0) === '/') return { ok: true, url: value };
    try {
      var parsed = new URL(value, window.location.origin);
      if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
        return { ok: true, url: parsed.href };
      }
    } catch (err) {
      /* parse error — запрещенный формат */
    }
    return { ok: false, reason: 'scheme' };
  }

  function buildLinkDialog() {
    var backdrop = el('div', 'editor-dialog-backdrop');
    backdrop.hidden = true;

    var dialog = el('div', 'dialog editor-link-dialog');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'wiki-link-dialog-title');

    var title = el('h3', null, 'Вставить ссылку');
    title.id = 'wiki-link-dialog-title';
    dialog.appendChild(title);

    var field = el('div', 'meta-field');
    var label = el('label', null, 'Адрес ссылки');
    label.htmlFor = 'wiki-link-url';
    var input = el('input', 'meta-title');
    input.type = 'text';
    input.id = 'wiki-link-url';
    input.placeholder = 'https://example.com или /wiki/1';
    field.appendChild(label);
    field.appendChild(input);
    dialog.appendChild(field);
    state.linkInput = input;

    var error = el('p', 'error-banner');
    error.setAttribute('role', 'alert');
    error.hidden = true;
    dialog.appendChild(error);
    state.linkError = error;

    var actions = el('div', 'dialog-actions');
    var cancel = el('button', 'btn btn-secondary', 'Отмена');
    cancel.type = 'button';
    cancel.addEventListener('click', function () {
      closeLinkDialog();
    });
    var insert = el('button', 'btn btn-primary', 'Вставить');
    insert.type = 'button';
    insert.addEventListener('click', applyLink);
    actions.appendChild(cancel);
    actions.appendChild(insert);
    dialog.appendChild(actions);

    backdrop.appendChild(dialog);
    backdrop.addEventListener('mousedown', function (event) {
      if (event.target === backdrop) closeLinkDialog();
    });
    document.body.appendChild(backdrop);
    state.linkDialog = backdrop;
    return backdrop;
  }

  function openLinkDialog() {
    state.linkInput.value = '';
    state.linkError.hidden = true;
    state.linkDialog.hidden = false;
    state.linkInput.focus();
  }

  function closeLinkDialog() {
    state.linkDialog.hidden = true;
    state.area.focus();
  }

  function applyLink() {
    var check = validLinkUrl(state.linkInput.value);
    if (!check.ok) {
      state.linkError.textContent =
        check.reason === 'empty'
          ? 'Укажите адрес ссылки.'
          : 'Допустимы только ссылки http/https или относительные (начинающиеся с «/»).';
      state.linkError.hidden = false;
      return; /* javascript:/data: и прочее — НЕ вставляем */
    }
    state.linkError.hidden = true;
    state.linkDialog.hidden = true;
    focusAreaAndRun(function () {
      document.execCommand('createLink', false, check.url);
    });
    state.area.focus();
  }

  /* ------------------------------------------------------------------ */
  /* Диалог изображения: «из галереи / с диска» (мокап)                  */
  /* ------------------------------------------------------------------ */

  function buildImageDialog() {
    var backdrop = el('div', 'editor-dialog-backdrop');
    backdrop.hidden = true;

    var dialog = el('div', 'dialog editor-img-dialog');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'wiki-img-dialog-title');

    var title = el('h3', null, 'Вставить изображение');
    title.id = 'wiki-img-dialog-title';
    dialog.appendChild(title);

    var radios = el('div', 'radio-row');

    var galleryLabel = el('label');
    var galleryRadio = el('input');
    galleryRadio.type = 'radio';
    galleryRadio.name = 'img-src';
    galleryRadio.checked = true;
    galleryRadio.addEventListener('change', switchImageSource);
    galleryLabel.appendChild(galleryRadio);
    galleryLabel.appendChild(document.createTextNode(' Из галереи (выбрать загруженное)'));
    radios.appendChild(galleryLabel);

    var diskLabel = el('label');
    var diskRadio = el('input');
    diskRadio.type = 'radio';
    diskRadio.name = 'img-src';
    diskRadio.addEventListener('change', switchImageSource);
    diskLabel.appendChild(diskRadio);
    diskLabel.appendChild(document.createTextNode(' Загрузить с диска'));
    radios.appendChild(diskLabel);

    dialog.appendChild(radios);
    state.imgRadioGallery = galleryRadio;
    state.imgRadioDisk = diskRadio;

    var error = el('p', 'error-banner');
    error.setAttribute('role', 'alert');
    error.hidden = true;
    dialog.appendChild(error);
    state.imgError = error;

    var grid = el('div', 'img-pick-grid');
    grid.setAttribute('role', 'listbox');
    grid.setAttribute('aria-label', 'Изображения галереи');
    dialog.appendChild(grid);
    state.imgGrid = grid;

    var diskPane = el('div', 'img-disk-pane');
    diskPane.hidden = true;
    var diskHint = el(
      'p',
      'img-disk-hint',
      'Файл до 10 МБ, JPEG/PNG/GIF/WebP (NFR-21). После выбора файл загрузится и будет вставлен.'
    );
    var fileInput = el('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/jpeg,image/png,image/gif,image/webp';
    fileInput.setAttribute('aria-label', 'Файл изображения с диска');
    fileInput.className = 'img-file-input';
    fileInput.addEventListener('change', function () {
      uploadAndInsert(fileInput.files && fileInput.files[0]);
    });
    diskPane.appendChild(diskHint);
    diskPane.appendChild(fileInput);
    dialog.appendChild(diskPane);
    state.imgFileInput = fileInput;

    /* масштаб: Оригинал / Среднее / Маленькое / Свой размер (px) —
       возврат живой приемки 2026-10-11 */
    state.imgScale = buildScalePicker(dialog, '');

    var actions = el('div', 'dialog-actions');
    var cancel = el('button', 'btn btn-secondary', 'Отмена');
    cancel.type = 'button';
    cancel.addEventListener('click', closeImageDialog);
    var insert = el('button', 'btn btn-primary', 'Вставить');
    insert.type = 'button';
    insert.setAttribute('data-role', 'img-insert');
    insert.addEventListener('click', insertSelectedImage);
    actions.appendChild(cancel);
    actions.appendChild(insert);
    dialog.appendChild(actions);

    backdrop.appendChild(dialog);
    backdrop.addEventListener('mousedown', function (event) {
      if (event.target === backdrop) closeImageDialog();
    });
    document.body.appendChild(backdrop);
    state.imgDialog = backdrop;
    return backdrop;
  }

  function switchImageSource() {
    var disk = state.imgRadioDisk.checked;
    state.imgGrid.hidden = disk;
    var diskPane = state.imgDialog.querySelector('.img-disk-pane');
    if (diskPane) diskPane.hidden = !disk;
    state.imgError.hidden = true;
  }

  function openImageDialog() {
    state.imgError.hidden = true;
    state.imgSelectedUrl = null;
    state.imgSelectedAlt = '';
    state.imgSelectedName = '';
    resetScalePicker(state.imgScale);
    state.imgRadioGallery.checked = true;
    state.imgRadioDisk.checked = false;
    switchImageSource();
    state.imgDialog.hidden = false;
    loadGallery();
  }

  function closeImageDialog() {
    state.imgDialog.hidden = true;
    state.area.focus();
  }

  /* ------------------------------------------------------------------ */
  /* Масштаб уже вставленного изображения (усиление в духе Confluence,   */
  /* возврат живой приемки 2026-10-11): клик по img в редакторе →        */
  /* модальный выбор масштаба → width меняется НА МЕСТЕ (src/alt не      */
  /* трогаются). Валидация та же: целые 16..4096, невалид — width        */
  /* не меняется, показывается ошибка.                                   */
  /* ------------------------------------------------------------------ */

  function buildImgScaleEditorDialog() {
    var backdrop = el('div', 'editor-dialog-backdrop');
    backdrop.hidden = true;

    var dialog = el('div', 'dialog editor-img-scale-dialog');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'wiki-img-scale-dialog-title');

    var title = el('h3', null, 'Масштаб изображения');
    title.id = 'wiki-img-scale-dialog-title';
    dialog.appendChild(title);

    state.imgScaleEditor = buildScalePicker(dialog, '-edit');

    var error = el('p', 'error-banner');
    error.setAttribute('role', 'alert');
    error.hidden = true;
    dialog.appendChild(error);
    state.imgScaleEditorError = error;

    var actions = el('div', 'dialog-actions');
    var cancel = el('button', 'btn btn-secondary', 'Отмена');
    cancel.type = 'button';
    cancel.addEventListener('click', closeImgScaleEditor);
    var apply = el('button', 'btn btn-primary', 'Применить');
    apply.type = 'button';
    apply.addEventListener('click', applyImgScale);
    actions.appendChild(cancel);
    actions.appendChild(apply);
    dialog.appendChild(actions);

    backdrop.appendChild(dialog);
    backdrop.addEventListener('mousedown', function (event) {
      if (event.target === backdrop) closeImgScaleEditor();
    });
    document.body.appendChild(backdrop);
    state.imgScaleEditorDialog = backdrop;
  }

  function openImgScaleEditor(img) {
    state.imgScaleTarget = img;
    resetScalePicker(state.imgScaleEditor);
    var width = parseInt(img.getAttribute('width') || '', 10);
    if (Number.isFinite(width)) {
      var preset = Object.keys(IMG_SCALE_PRESET_WIDTH).filter(function (key) {
        return IMG_SCALE_PRESET_WIDTH[key] === width;
      })[0];
      if (preset) {
        state.imgScaleEditor.radios.forEach(function (radio) {
          radio.checked = radio.value === preset;
        });
      } else {
        state.imgScaleEditor.radios.forEach(function (radio) {
          radio.checked = radio.value === 'custom';
        });
        state.imgScaleEditor.customInput.value = String(width);
        state.imgScaleEditor.customWrap.hidden = false;
      }
    }
    if (state.imgScaleEditorError) state.imgScaleEditorError.hidden = true;
    state.imgScaleEditorDialog.hidden = false;
  }

  function closeImgScaleEditor() {
    state.imgScaleEditorDialog.hidden = true;
    state.imgScaleTarget = null;
    state.area.focus();
  }

  function applyImgScale() {
    var img = state.imgScaleTarget;
    if (!img) {
      closeImgScaleEditor();
      return;
    }
    var width = selectedScaleWidth(state.imgScaleEditor);
    if (
      state.imgScaleEditor.radios[state.imgScaleEditor.radios.length - 1].checked &&
      width === null
    ) {
      state.imgScaleEditorError.textContent =
        'Укажите целый размер в пикселях: ' + IMG_SCALE_MIN_PX + '–' +
        IMG_SCALE_MAX_PX + '.';
      state.imgScaleEditorError.hidden = false;
      return;
    }
    if (width) {
      img.setAttribute('width', String(width));
    } else {
      img.removeAttribute('width'); // «Оригинал» — без width
    }
    closeImgScaleEditor();
  }

  function bindAreaImageScale(area) {
    /* Клик по img внутри contenteditable не двигает каретку мимо —
       открываем выбор масштаба вместо «мёртвого» клика (Confluence). */
    area.addEventListener('click', function (event) {
      var target = event.target;
      if (target && target.nodeName === 'IMG' && area.contains(target)) {
        event.preventDefault();
        openImgScaleEditor(target);
      }
    });
  }

  function loadGallery() {
    state.imgGrid.textContent = '';
    state.imgGrid.appendChild(el('p', 'img-pick-loading', 'Загрузка…'));
    api(
      '/api/images',
      { method: 'GET' },
      function (message) {
        state.imgGrid.textContent = '';
        state.imgError.textContent = message;
        state.imgError.hidden = false;
      },
      function (body) {
        renderGallery((body && body.images) || []);
      }
    );
  }

  function renderGallery(images) {
    state.imgGrid.textContent = '';
    if (images.length === 0) {
      state.imgGrid.appendChild(
        el('p', 'img-pick-loading', 'Галерея пуста — загрузите файл с диска.')
      );
      return;
    }
    images.forEach(function (image) {
      var option = el('button', 'img-pick-item');
      option.type = 'button';
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', 'false');
      var url = image.url || ('/images/' + image.filename);
      option.dataset.url = url;
      option.dataset.alt = image.original_name || '';
      var thumb = document.createElement('img');
      thumb.src = image.thumb_url || image.url || ('/images/' + image.filename);
      thumb.alt = '';
      option.appendChild(thumb);
      option.appendChild(el('span', 'img-pick-name', image.original_name || url));
      option.addEventListener('click', function () {
        state.imgGrid.querySelectorAll('.img-pick-item').forEach(function (item) {
          item.setAttribute('aria-selected', 'false');
          item.classList.remove('selected');
        });
        option.setAttribute('aria-selected', 'true');
        option.classList.add('selected');
        state.imgSelectedUrl = option.dataset.url;
        state.imgSelectedAlt = option.dataset.alt;
        state.imgSelectedName = option.dataset.alt;
      });
      state.imgGrid.appendChild(option);
    });
  }

  function attrEscape(value) {
    /* Атрибут URL/alt: кавычки и амперсанды — сущности (URL приходит
       от сервера, страховка от символа кавычки в имени файла) */
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function insertImageMarkup(url, alt, width) {
    var widthAttr = width ? ' width="' + parseInt(width, 10) + '"' : '';
    var html =
      '<img src="' + attrEscape(url) + '" alt="' + attrEscape(alt || '') + '"' +
      widthAttr + '>';
    focusAreaAndRun(function () {
      document.execCommand('insertHTML', false, html + '<p><br></p>');
    });
  }

  function insertSelectedImage() {
    if (!state.imgRadioDisk.checked && state.imgSelectedUrl) {
      var width = selectedScaleWidth();
      var radios = state.imgScale.radios;
      if (radios[radios.length - 1].checked && width === null) {
        /* «Свой размер» с невалидным числом — отказ вставки (как у схем
           ссылок): ничего не вставляем, ошибка в диалоге */
        state.imgError.textContent =
          'Укажите целый размер в пикселях: ' + IMG_SCALE_MIN_PX + '–' +
          IMG_SCALE_MAX_PX + '.';
        state.imgError.hidden = false;
        return;
      }
      closeImageDialog();
      insertImageMarkup(state.imgSelectedUrl, state.imgSelectedAlt, width);
      return;
    }
    if (state.imgRadioGallery.checked && !state.imgSelectedUrl) {
      state.imgError.textContent = 'Выберите изображение из галереи.';
      state.imgError.hidden = false;
    }
  }

  function uploadAndInsert(file) {
    if (!file) return;
    state.imgError.hidden = true;
    var form = new FormData();
    form.append('file', file, file.name);
    state.imgGrid.hidden = true;
    fetch('/api/images', {
      method: 'POST',
      credentials: 'same-origin',
      body: form
    })
      .then(function (response) {
        return parseBody(response).then(function (body) {
          if (response.status === 401) {
            window.location.href = '/login';
            return;
          }
          if (!response.ok) {
            var message =
              response.status === 422
                ? 'Файл не принят: до 10 МБ, только JPEG/PNG/GIF/WebP (NFR-21).'
                : 'Ошибка загрузки (HTTP ' + response.status + ').';
            showImageError(message);
            return;
          }
          closeImageDialog();
          insertImageMarkup(
            body.url || ('/images/' + body.filename),
            body.original_name || file.name,
            selectedScaleWidth()
          );
        });
      })
      .catch(function () {
        showImageError('Сетевая ошибка при загрузке файла.');
      });
  }

  function showImageError(message) {
    state.imgError.textContent = message;
    state.imgError.hidden = false;
    state.imgGrid.hidden = state.imgRadioDisk.checked;
    state.imgFileInput.value = '';
  }

  /* ------------------------------------------------------------------ */
  /* Выбор родителя («Без родителя» / дерево из GET /api/wiki/pages)     */
  /* ------------------------------------------------------------------ */

  function pathOf(pagesById, pageId) {
    var parts = [];
    var guard = 0;
    var current = pagesById[pageId];
    while (current && guard < 100) {
      parts.unshift(current.title);
      current = current.parent_id ? pagesById[current.parent_id] : null;
      guard += 1;
    }
    return parts.join(' → ');
  }

  function isDescendant(pagesById, candidateId, ancestorId) {
    var current = pagesById[candidateId];
    var guard = 0;
    while (current && current.parent_id && guard < 100) {
      if (current.parent_id === ancestorId) return true;
      current = pagesById[current.parent_id];
      guard += 1;
    }
    return false;
  }

  function fillParentSelect(pages, onDone) {
    var select = state.parentSelect;
    select.textContent = '';
    var none = el('option', null, 'Без родителя (корень раздела)');
    none.value = '';
    select.appendChild(none);

    var pagesById = {};
    pages.forEach(function (page) {
      pagesById[page.id] = page;
    });

    var options = pages.filter(function (page) {
      if (state.mode !== 'edit') return true;
      /* себя и своих потомков родителем выбрать нельзя (цикл) */
      return page.id !== state.pageId && !isDescendant(pagesById, page.id, state.pageId);
    });
    options.sort(function (a, b) {
      return pathOf(pagesById, a.id).localeCompare(pathOf(pagesById, b.id), 'ru');
    });
    options.forEach(function (page) {
      var option = el('option', null, pathOf(pagesById, page.id));
      option.value = String(page.id);
      select.appendChild(option);
    });

    var preselect =
      state.mode === 'create' && state.parentPreselect
        ? String(state.parentPreselect)
        : null;
    if (preselect && select.querySelector('option[value="' + preselect + '"]')) {
      select.value = preselect;
    }
    if (onDone) onDone();
  }

  /* ------------------------------------------------------------------ */
  /* Сохранение: POST (создание) / PUT (правка) → redirect /wiki/{id}    */
  /* ------------------------------------------------------------------ */

  function showError(message) {
    state.errorBox.textContent = message;
    state.errorBox.hidden = false;
    state.errorBox.scrollIntoView({ block: 'nearest' });
  }

  function save() {
    var title = state.titleInput.value.trim();
    if (!title) {
      /* Мокап: пустой заголовок — ошибка БЕЗ сохранения (422-случай) */
      showError(
        'Заголовок не может быть пустым — заполните поле «Заголовок» и повторите сохранение.'
      );
      state.titleInput.focus();
      return;
    }
    state.errorBox.hidden = true;
    var content;
    if (state.rich) {
      /* Rich-режим: сериализация блоков в диалект; структурные ошибки
         перехватываются ДО отправки (design §1: на сервере 422 нет —
         строгая валидация нового rich-контента в редакторе, tasks 1.6б). */
      content = serializeRichContent();
      try {
        richParser.validate(content);
      } catch (error) {
        showError(
          'Структурная ошибка блока: ' + error.message +
          ' — исправьте блок и повторите сохранение (запрос не отправлялся).'
        );
        return;
      }
    } else {
      content = state.area.innerHTML;
    }

    var request;
    if (state.mode === 'edit') {
      request = api(
        '/api/wiki/pages/' + state.pageId,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: title, content: content })
        },
        showError,
        function () {
          window.location.href = '/wiki/' + state.pageId;
        }
      );
    } else {
      var parentId = state.parentSelect.value ? parseInt(state.parentSelect.value, 10) : null;
      request = api(
        '/api/wiki/pages',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: title,
            content: content,
            parent_id: parentId
          })
        },
        showError,
        function (body) {
          window.location.href = '/wiki/' + (body && body.id);
        }
      );
    }
    return request;
  }

  /* ------------------------------------------------------------------ */
  /* Инициализация                                                       */
  /* ------------------------------------------------------------------ */

  function markActiveContent() {
    var content = state.area.closest('.wiki-content');
    if (content) content.classList.add('editor-active');
  }

  function init() {
    var container = document.getElementById('wiki-editor');
    if (!container) return; // не режим редактора — модуль не активен

    var params = new URLSearchParams(window.location.search);
    var layout = container.closest('.wiki-layout');
    var pageIdRaw = layout && layout.dataset ? layout.dataset.pageId : '';

    if (params.get('create') === '1') {
      state.mode = 'create';
      var parentParam = parseInt(params.get('parent'), 10);
      state.parentPreselect = Number.isFinite(parentParam) ? parentParam : null;
    } else if (/^\d+$/.test(String(pageIdRaw)) && params.get('edit') === '1') {
      state.mode = 'edit';
      state.pageId = String(pageIdRaw);
    } else {
      return; // обычный просмотр — редактор не открываем
    }

    container.hidden = false;
    container.textContent = '';

    var heading = el(
      'h1',
      null,
      state.mode === 'edit' ? 'Редактирование' : 'Создание страницы'
    );
    container.appendChild(heading);

    /* error-banner ПОД заголовком, рядом с формой (мокап wiki-editor:
       баннер над meta-card, не выше h1 — DV-6 review-001) */
    state.errorBox = el('p', 'error-banner');
    state.errorBox.setAttribute('role', 'alert');
    state.errorBox.hidden = true;
    container.appendChild(state.errorBox);

    container.appendChild(buildMetaCard(''));
    container.appendChild(buildEditorCard());
    buildLinkDialog();
    buildImageDialog();
    buildImgScaleEditorDialog();
    bindAreaImageScale(state.area);
    bindAreaFocusTracking(state.area);
    markActiveContent();

    document.addEventListener('selectionchange', updateToolbarStates);

    if (state.mode === 'edit') {
      api(
        '/api/wiki/pages/' + state.pageId,
        { method: 'GET' },
        function (message) {
          showError(message === 'not found' ? 'Страница не найдена' : message);
        },
        function (page) {
          state.titleInput.value = page.title;
          heading.textContent = 'Редактирование: ' + page.title;
          document.title = 'Редактирование: ' + page.title + ' · ekotov-wiki';
          /* Контент сервером уже санитизирован на записи (design §4).
           * Rich-блоки (1.6): блоки диалекта → канва (renderCanvas);
           * legacy-HTML без блоков — существующее поведение (FR-125). */
          var richNodes = richParser.parse(page.content || '');
          if (richParser.hasRichBlocks(richNodes)) {
            enterRichMode(
              richNodes.map(function (node) {
                return node.type === 'text' ? legacyHtmlNode(node.text) : node;
              })
            );
          } else {
            state.area.innerHTML = page.content || '';
          }
          fillParentSelect([], function () {
            if (page.parent_id) {
              var option = state.parentSelect.querySelector(
                'option[value="' + page.parent_id + '"]'
              );
              if (!option) {
                option = el('option', null, 'Текущий родитель (id ' + page.parent_id + ')');
                option.value = String(page.parent_id);
                state.parentSelect.appendChild(option);
              }
              state.parentSelect.value = String(page.parent_id);
            }
          });
        }
      );
    }

    /* Список страниц для выбора родителя (обоими режимами) */
    api(
      '/api/wiki/pages',
      { method: 'GET' },
      function () {
        /* ошибка списка не блокирует редактор — останется «Без родителя» */
      },
      function (body) {
        if (state.mode === 'create') {
          fillParentSelect((body && body.pages) || []);
        } else {
          /* в edit список догрузится и обновит select (текущий родитель —
             сохраняется, если еще в списке) */
          var currentValue = state.parentSelect.value;
          fillParentSelect((body && body.pages) || []);
          if (
            currentValue &&
            state.parentSelect.querySelector('option[value="' + currentValue + '"]')
          ) {
            state.parentSelect.value = currentValue;
          }
        }
      }
    );

    state.titleInput.focus();
  }

  init();
})();
