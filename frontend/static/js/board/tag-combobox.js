/* Кастомный комбобокс подсказок тегов (r6, задачи 2.1+2.2; FR-57…FR-59,
 * NFR-17/18, ОВ-1/ОВ-2; r8 2.3 — FR-92 сброс поля после выбора).
 *
 * Замена нативного datalist у поля «Теги» формы задачи. Стили и
 * aria-паттерн — 1:1 по живому макету design/tag-combobox-v3.html
 * (47ee8e5; DEF-004): дропдаун .combobox-popup (bg-surface,
 * radius-field, shadow-soft), пункты li.option с подсветкой совпавшей
 * подстроки <mark> (терракота на accent-soft), активный с клавиатуры —
 * aria-selected + терракотовая плашка, «+ Добавить тег „…“» —
 * .option-add secondary с .add-fragment.
 *
 * Поведение (NFR-17): фокус/ввод → открытие; фильтрация ЛОКАЛЬНАЯ
 * (case-insensitive подстрока, ≤100 мс, без запроса на каждый символ);
 * уже введенные теги исключены (FR-58); выбор кликом/тач-тапом/
 * стрелками+Enter/Tab → дописать в input + перерисовать чипы
 * (источник истины — input, ОГР-27); Escape закрывает ТОЛЬКО дропдаун
 * (stopPropagation — форма не реагирует, СЦ-8/FR-61); клик вне —
 * закрытие; тач — mousedown preventDefault (фокус остается в input,
 * скролл страницы не ломается).
 *
 * Доступность (NFR-18, ARIA APG «Combobox with Listbox Popup»): input
 * role=combobox aria-expanded/aria-controls/aria-autocomplete=list,
 * активный стрелками пункт — aria-activedescendant=tag-opt-N на input;
 * дропдаун role=listbox, пункты role=option aria-selected; количество
 * подсказок — aria-live=polite узел. Значения в DOM — только через
 * textContent/createTextNode (XSS, dom.js).
 *
 * Источник данных ведет task-form.js (loadTagHints →
 * GET /api/suggestions?kind=tags, Д-14/ОВ-1) и передает множество сюда
 * через setTagHints(). Сбой загрузки — подсказок нет, дропдаун не
 * показан, ввод тегов не блокируется (NFR-17, СЦ-5).
 */
"use strict";

import { el } from "./dom.js";
import { splitTags } from "./task-form.js";

var TAGS_INPUT_ID = "task-tags";
var LISTBOX_ID = "task-tag-combobox";
var LIVE_ID = "task-tag-combobox-live";
/* id пунктов — tag-opt-N (макет: aria-activedescendant=tag-opt-2). */
var OPTION_ID_PREFIX = "tag-opt-";

/* r8 2.3 (FR-92): выбранные (и созданные) теги после выбора ТЕКСТОМ в
 * поле не остаются — из input строка убирается, чип рисует task-form.js
 * из данных committedTags (см. syncInputAndDom). Источник истины ОГР-27
 * сохраняется на границах сохранения/удаления: перед сабмитом формы и
 * перед правкой строки крестиком чипа committed-теги ДОписываются в
 * input, поэтому collectTaskForm/splitTags (замороженный task-form.js)
 * и renderTagsChips работают без изменений. */
var committedTags = [];
var ledgerAttachCount = 0;

/* Множество значений из GET /api/suggestions?kind=tags (перезагрузка
 * при каждом открытии формы — loadTagHints, преемственность FR-26). */
var allHints = [];
var optionSeq = 0;
/* Защита: выбор пункта dispatch'ит input (перерисовка чипов) — свой
 * обработчик input не должен переоткрыть дропдаун поверх закрытия. */
var choosing = false;

function tagsInput() {
  return document.getElementById(TAGS_INPUT_ID);
}

function listbox() {
  return document.getElementById(LISTBOX_ID);
}

/* Текущий ввод без завершенных тегов: фильтрация по последней
 * (незавершенной запятой) части строки. */
function currentToken(raw) {
  var parts = String(raw).split(",");
  return parts[parts.length - 1].trim();
}

/* Строка ввода после выбора: последний токен заменяется значением,
 * запятая в хвосте — поле готово к вводу следующего тега (СЦ-3).
 * r8 2.3 (FR-92): с committed-схемой выбор больше не дописывает тег в
 * input (поле очищается — chooseValue/syncInputAndDom); функция остается
 * как документация прежнего поведения datalist-совместимости.
 * Deprecated (review add-ui-polish-r8 #49 minor): мертвый код — выбор
 * через него больше не идет (chooseValue уводит тег в committedTags и
 * очищает токен ввода — syncInputAndDom). Не удаляется (минимизация
 * диффа волны); новых вызовов не добавлять. */
function applySelection(raw, value) {
  var parts = String(raw).split(",");
  parts[parts.length - 1] = " " + value;
  var next = parts.join(",");
  if (!/[,:]$/.test(next)) {
    next += ",";
  }
  return next;
}

/* Фильтрация (FR-58): case-insensitive подстрока, уже введенные теги
 * исключены; порядок — серверный (множество отсортировано). */
function visibleHints(query) {
  var needle = query.toLowerCase();
  var entered = splitTags(tagsInput().value).map(function (tag) {
    return tag.toLowerCase();
  });
  return allHints.filter(function (hint) {
    if (entered.indexOf(hint.toLowerCase()) !== -1) {
      return false;
    }
    return hint.toLowerCase().indexOf(needle) !== -1;
  });
}

/* Есть ли точное совпадение с запросом (условие пункта «+ Добавить
 * тег», FR-59). */
function hasExactMatch(query, hints) {
  return hints.some(function (hint) {
    return hint.toLowerCase() === query.toLowerCase();
  });
}

/* Содержимое пункта с подсветкой совпавшей подстроки (FR-58, «как в
 * Jira»; макет: ре<mark>диз</mark>айн). Узлы — createTextNode/mark с
 * textContent (XSS). */
function fillOptionLabel(option, text, query) {
  var at = query ? text.toLowerCase().indexOf(query.toLowerCase()) : -1;
  if (at === -1) {
    option.appendChild(document.createTextNode(text));
    return;
  }
  if (at > 0) {
    option.appendChild(document.createTextNode(text.slice(0, at)));
  }
  option.appendChild(el("mark", null, text.slice(at, at + query.length)));
  if (at + query.length < text.length) {
    option.appendChild(document.createTextNode(text.slice(at + query.length)));
  }
}

/* Пункт li.option: role=option, детерминированный id tag-opt-N,
 * aria-selected=false; тач — mousedown preventDefault (фокус не уходит
 * из input: blur-закрытие не опережает click, скролл цел). */
function buildOption(className, value) {
  var option = document.createElement("li");
  option.className = className;
  option.id = OPTION_ID_PREFIX + ++optionSeq;
  option.setAttribute("role", "option");
  option.setAttribute("aria-selected", "false");
  option.setAttribute("data-value", value);
  option.addEventListener("mousedown", function (event) {
    event.preventDefault();
  });
  return option;
}

/* Дропдаун скрыт/очищен; aria-состояние input сброшено (NFR-18). */
function closeDropdown() {
  var box = listbox();
  if (!box) {
    return;
  }
  box.hidden = true;
  box.textContent = "";
  var input = tagsInput();
  if (input) {
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }
}

/* Активный пункт (aria-selected=true; input держит его id в
 * aria-activedescendant — макет/ARIA APG). */
function activeOption() {
  var box = listbox();
  return box && !box.hidden
    ? box.querySelector('[aria-selected="true"]')
    : null;
}

function setActive(option) {
  var box = listbox();
  /* ВАЖНО: селектор БЕЗ класса пункта — активным может быть и
   * li.option, и div.option-add («+ Добавить тег», FR-59). */
  var previous = box.querySelector('[aria-selected="true"]');
  if (previous) {
    previous.setAttribute("aria-selected", "false");
  }
  if (!option) {
    tagsInput().removeAttribute("aria-activedescendant");
    return;
  }
  option.setAttribute("aria-selected", "true");
  tagsInput().setAttribute("aria-activedescendant", option.id);
  /* Активный пункт докручивается в видимую область (NFR-17). */
  if (option.scrollIntoView) {
    option.scrollIntoView({ block: "nearest" });
  }
}

function optionByOffset(from, delta) {
  var options = Array.prototype.slice.call(
    listbox().querySelectorAll(".option, .option-add")
  );
  if (options.length === 0) {
    return null;
  }
  var index = from
    ? options.indexOf(from) + delta
    : delta > 0
      ? 0
      : options.length - 1;
  if (index < 0) {
    index = options.length - 1;
  }
  if (index >= options.length) {
    index = 0;
  }
  return options[index];
}

/* r8 2.3 (FR-92): committed-рендер списка тегов. Вместо строки выбора в
 * input тег уходит в committedTags, input ОЧИЩАЕТСЯ от токена ввода
 * (текст в поле не остается — FR-92), а чипы перерисовываются существующим
 * рендером task-form.js (renderTagsChips, подписан на input) из
 * completeness-строки committed-тегов + ручных токенов. Источник истины
 * ОГР-27 не переносится в этот файл: на границах чтения/правки строки
 * внешним кодом committed-теги дописываются в input
 * (flushCommittedToInput), после правки крестиком — пересинхронизируются
 * (resyncCommittedAfterChipEdit). */
function syncInputAndDom() {
  var input = tagsInput();
  if (!input) {
    return;
  }
  /* Ручные токены (введены без дропдауна и еще не выбраны) НЕ затираются:
   * убирается только токен ввода выбранного тега — FR-92 про введенный
   * текст подсказки, не про остальное содержимое поля. ИСКЛЮЧЕНИЕ
   * (BUG-012): непустой токен, ЧАСТЬЮ которого является выбранное
   * значение (selected.startsWith(token) — «QATkbдва» выбран при токене
   * «QATkb»), потреблен выбором: выбор по Enter/клику делается ради
   * этого токена, оставлять его в rest — двойной чип «выбранный тег +
   * его же недобор» (не «два тега», а одна сущность). Токены, не
   * связанные с выбором (префиксом не являются), остаются как были. */
  var rest = splitTags(input.value).filter(function (tag) {
    if (committedTags.indexOf(tag) !== -1) {
      return false;
    }
    if (!currentToken(input.value)) {
      return true;
    }
    var token = currentToken(input.value).toLowerCase();
    var consumed = committedTags.some(function (selected) {
      return selected.toLowerCase().indexOf(token) !== -1;
    });
    return !consumed;
  });
  var line = committedTags.concat(rest).join(", ");
  if (line) {
    line += ",";
  }
  if (input.value !== line) {
    input.value = line;
  }
  /* Перерисовка чипов существующим рендером (событие input); свой
   * перерендер дропдауна на это событие подавлен (choosing). */
  choosing = true;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  choosing = false;
}

/* r8 2.3 (FR-92, совместимость ОГР-27): перед чтением строки тегов
 * внешним кодом (сабмит формы — collectTaskForm; правка крестиком чипа —
 * его click-обработчик читает input.value ДО подписки комбобокса)
 * committed-теги дописываются в input: внешние читатели видят полный
 * состав, рассинхрона «чип есть — в строке нет» не возникает. */
function flushCommittedToInput() {
  var input = tagsInput();
  if (!input || committedTags.length === 0) {
    return;
  }
  var rest = splitTags(input.value).filter(function (tag) {
    return committedTags.indexOf(tag) === -1;
  });
  var line = committedTags.concat(rest).join(", ");
  if (rest.length > 0) {
    line += ",";
  }
  input.value = line;
}

/* r8 2.3 (FR-92): после ПРАВКИ строки крестиком чипа committed-список
 * пересинхронизируется с итоговой строкой: удаленный крестиком тег уходит
 * и из committed (иначе следующий flush его воскресит). Вызывается из
 * capture-подписки клика ПОСЛЕ flush — читает строку, которую task-form
 * еще не успел править (его обработчик тоже на click, но позже — bubbling
 * после capture), поэтому в момент вызова строка еще «до удаления» и
 * пересинхронизация здесь ранняя. Окончательная синхронизация — на
 * document-level capture НЕ возможна после bubbling-правки; вместо этого
 * удаление тега из committed вычисляется по факту: подписка task-form на
 * input сработает и чипы перерисуются из строки; committed догоняет
 * строку отложенно (setTimeout 0 — после bubbling-обработчиков). */
function resyncCommittedAfterChipEdit() {
  setTimeout(function () {
    var input = tagsInput();
    if (!input) {
      return;
    }
    var line = splitTags(input.value);
    committedTags = committedTags.filter(function (tag) {
      return line.indexOf(tag) !== -1;
    });
  }, 0);
}

/* Подписки внешнего кода на границы чтения input (capture-фаза — раньше
 * внешних обработчиков): submit формы и клик по крестику чипа. */
function ensureLedgerFlushHooks() {
  if (ledgerAttachCount > 0) {
    return;
  }
  var form = document.getElementById("task-form");
  if (form) {
    form.addEventListener("submit", flushCommittedToInput, true);
    ledgerAttachCount += 1;
  }
  document.addEventListener("click", function (event) {
    var target = event.target;
    if (
      target &&
      target.nodeType === 1 &&
      target.closest &&
      target.closest("#task-tags-chips .chip button")
    ) {
      flushCommittedToInput();
      resyncCommittedAfterChipEdit();
    }
  }, true);
  ledgerAttachCount += 1;
}

/* Выбор пункта: тег уходит в committedTags (чип — существующим рендером
 * через syncInputAndDom), токен ввода УБИРАЕТСЯ из поля (FR-92), дропдаун
 * закрывается, фокус возвращается полю (FR-92: поле не блокируется —
 * можно сразу вводить следующий тег). */
function chooseValue(value) {
  var input = tagsInput();
  if (!input) {
    return;
  }
  if (committedTags.indexOf(value) === -1) {
    committedTags.push(value);
  }
  syncInputAndDom();
  closeDropdown();
  /* Фокус возвращается полю ввода (FR-92; после клика он и так там —
   * mousedown preventDefault; после keyboard-выбора тем более). Явный
   * focus() страхует тач-устройства, где тап по пункту не держит фокус
   * в input. */
  if (document.activeElement !== input && input.focus) {
    input.focus();
  }
}

function chooseActive() {
  var option = activeOption();
  if (option) {
    chooseValue(option.getAttribute("data-value"));
  }
}

/* aria-live=polite узел: количество подсказок озвучивается скринридером
 * (NFR-18; макет: «Найдено 4 тегов»). Текст — только при смене числа. */
var lastAnnounced = null;
function announce(count) {
  var live = document.getElementById(LIVE_ID);
  if (!live || lastAnnounced === count) {
    return;
  }
  lastAnnounced = count;
  live.textContent =
    count === 0 ? "Подсказок нет" : "Найдено тегов: " + count;
}

/* Рендер дропдауна (FR-58/59, NFR-18). query — текущий токен ввода.
 * Структура по макету: ul.combobox-list > li.option* + div.option-add. */
function renderDropdown(query) {
  var input = tagsInput();
  var box = listbox();
  if (!input || !box) {
    return;
  }
  var hints = visibleHints(query);
  var exact = hasExactMatch(query, hints);
  var total = hints.length;
  box.textContent = "";

  var list = document.createElement("ul");
  list.className = "combobox-list";
  hints.forEach(function (hint) {
    var option = buildOption("option", hint);
    fillOptionLabel(option, hint, query);
    option.addEventListener("click", function () {
      chooseValue(hint);
    });
    list.appendChild(option);
  });
  box.appendChild(list);

  /* FR-59: явный пункт создания нового значения — когда точного
   * совпадения нет (и ввод непуст); состояние «нет совпадений» —
   * в дропдауне только пункт добавления (макет, требование 3). */
  if (query && !exact) {
    total += 1;
    var add = buildOption("option-add", query);
    add.appendChild(document.createTextNode("+ Добавить тег «"));
    add.appendChild(el("span", "add-fragment", query));
    add.appendChild(document.createTextNode("»"));
    add.addEventListener("click", function () {
      chooseValue(query);
    });
    box.appendChild(add);
  }

  if (total === 0) {
    closeDropdown();
    announce(0);
    return;
  }

  box.hidden = false;
  input.setAttribute("aria-expanded", "true");
  setActive(box.querySelector(".option, .option-add"));
  announce(total);
}

/* --- Публичная точка: множество подсказок (вызывает loadTagHints) --- */

export function setTagHints(values) {
  var next = Array.isArray(values) ? values : [];
  /* Ответ с тем же множеством (повторное открытие формы) — идемпотентно:
   * перерисовка породила бы НОВЫЕ id пунктов при открытом дропдауне и
   * рассинхрон aria-activedescendant/клавиатурного выбора (выбор по id
   * старого элемента). Состав не изменился — только данные. */
  if (
    next.length === allHints.length &&
    next.every(function (value, index) {
      return value === allHints[index];
    })
  ) {
    return;
  }
  allHints = next;
  /* Guard (review 2.1/2.2, major): перерисовать открытый дропдаун
   * ТОЛЬКО когда поле в фокусе (поздний ответ пришел после focus-
   * рендера). Иначе — только данные: пересоздание option-узлов под
   * невидимым/неактуальным дропдауном ловит клик («option intercepts
   * pointer events») и переоткрывает список под курсором. */
  var input = tagsInput();
  if (input && document.activeElement === input) {
    renderDropdown(currentToken(input.value));
  }
}

/* r8 2.3 (FR-92): вызвавший открытие формы код (task-form.js) сбрасывает
 * поля через clearTaskForm/fillTaskForm — committed-состояние комбобокса
 * должно следовать за строкой input, а не жить своей жизнью между
 * открытиями формы (иначе тег прошлого тикета «всплывет» чипом в новом).
 * Строка input падает до пустой — committed-список тоже. */
function resetCommittedFromInput() {
  var input = tagsInput();
  if (!input) {
    return;
  }
  if (splitTags(input.value).length === 0 && input.value !== ",") {
    committedTags = [];
  }
}

/* review add-ui-polish-r8 #49 (blocker): полный сброс committed-леджера.
 * resetCommittedFromInput (условный, только через closeTagHints) не
 * покрывает флоу «сохранил задачу A → открыл задачу B»: после сабмита
 * input непуст (flushCommittedToInput) — условие сброса ложно, леджер
 * переживает закрытие формы, а следующий fillTaskForm пишет input
 * напрямую, без сброса. Экспортируется: вызывающий открытие/закрытие
 * формы (task-form.js) вызывает это в fillTaskForm — владелец цикла
 * жизни формы знает момент замены задачи лучше, чем эвристика по
 * содержимому input. committedTags — приватное состояние модуля,
 * наружу значение не отдается (единственный источник правды — сам
 * леджер; проверяет его перерисовка чипов). */
export function resetTagLedger() {
  committedTags = [];
  lastAnnounced = null;
}

export function closeTagHints() {
  allHints = [];
  closeDropdown();
  resetCommittedFromInput();
  /* Сброс (review 2.1/2.2, minor): без него переоткрытие с тем же
   * числом подсказок не озвучивается — announce видит «то же число». */
  lastAnnounced = null;
}

/* --- Инициализация (один раз при загрузке task-form.js) --- */

export function initTagCombobox() {
  var input = tagsInput();
  var box = listbox();
  if (!input || !box) {
    return;
  }

  /* r8 2.3 (FR-92): подписки сброса committed-состояния на границах
   * жизненного цикла формы (см. ensureLedgerFlushHooks). */
  ensureLedgerFlushHooks();

  /* NFR-18: role=combobox + aria-связь со списком (значения дублируют
   * статичную разметку board.html — источник истины один, JS). */
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-controls", LISTBOX_ID);
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-haspopup", "listbox");

  box.setAttribute("role", "listbox");
  box.setAttribute("aria-label", "Подсказки тегов");
  box.hidden = true;

  /* Открытие по фокусу — полный (отфильтрованный) список; если запрос
   * подсказок еще в полете, дропдаун перерисует setTagHints по приходу
   * ответа (поле в фокусе). */
  input.addEventListener("focus", function () {
    renderDropdown(currentToken(input.value));
  });

  /* Фильтрация по вводу — локальная, на каждый символ (NFR-17: без
   * сетевых запросов, отклик ≤100 мс). */
  input.addEventListener("input", function () {
    if (choosing) {
      return;
    }
    renderDropdown(currentToken(input.value));
  });

  input.addEventListener("keydown", function (event) {
    var open = !listbox().hidden;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!open) {
        renderDropdown(currentToken(input.value));
      } else {
        setActive(
          optionByOffset(activeOption(), event.key === "ArrowDown" ? 1 : -1)
        );
      }
      event.preventDefault();
      return;
    }
    if (event.key === "Enter") {
      /* Enter при открытом дропдауне выбирает активный пункт и НЕ
       * отправляет форму; при закрытом — сабмит как прежде. */
      if (open) {
        chooseActive();
        event.preventDefault();
      }
      return;
    }
    if (event.key === "Escape") {
      /* Escape закрывает ТОЛЬКО дропдаун; stopPropagation — обработчик
       * формы (FR-61) на первое нажатие не реагирует (макет/design.md
       * §2, СЦ-8: форму закрывает следующий Escape). */
      if (open) {
        event.stopPropagation();
        closeDropdown();
      }
      return;
    }
    if (event.key === "Tab" && open) {
      /* Tab — выбрать активный пункт и уйти по таб-порядку. */
      chooseActive();
    }
  });

  /* Клик/тач вне дропдауна — закрытие (NFR-17). */
  document.addEventListener("click", function (event) {
    if (
      !listbox().hidden &&
      !listbox().contains(event.target) &&
      event.target !== input
    ) {
      closeDropdown();
    }
  });
}
