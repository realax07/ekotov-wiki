/* review add-ui-polish-r8 #49 (blocker): node-симуляция межформенной
 * утечки committed-леджера комбобокса тегов.
 *
 * Воспроизводит жизненный цикл: редактирование задачи A (теги X,Y +
 * выбор Z из дропдауна) → сохранить → открыть задачу B (тег P) →
 * сохранить без правок. Утечка = PATCH B содержит «Z».
 *
 * Код модулей скопирован 1:1 из боевых файлов
 * (frontend/static/js/board/tag-combobox.js, task-form.js):
 * - committedTags/flushCommittedToInput/resetCommittedFromInput/
 *   closeTagHints/splitTags — без изменений;
 * - ОРИГИНАЛЬНОЕ поведение fillTaskForm (input пишется напрямую) —
 *   в режиме --fixed первый строкой тела вызывает resetTagLedger()
 *   (фикс #49). Запуск: node tag-ledger-leak-sim.js [--fixed]
 */
"use strict";

/* --- 1:1: task-form.js, splitTags --- */
function splitTags(raw) {
  return raw
    .split(",")
    .map(function (tag) {
      return tag.trim();
    })
    .filter(function (tag) {
      return tag.length > 0;
    });
}

/* --- 1:1: tag-combobox.js (state + леджер) --- */
var committedTags = [];

/* 1:1 flushCommittedToInput (публичное имя — без тегов модуля). */
function flushCommittedToInput(input) {
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

/* 1:1 resetCommittedFromInput. */
function resetCommittedFromInput(input) {
  if (!input) {
    return;
  }
  if (splitTags(input.value).length === 0 && input.value !== ",") {
    committedTags = [];
  }
}

/* 1:1 closeTagHints (дропдаун-часть не нужна симуляции). */
function closeTagHints(input) {
  resetCommittedFromInput(input);
}

/* Фикс #49: экспортируемый сброс леджера. */
function resetTagLedger() {
  committedTags = [];
}

/* --- task-form.js: границы жизненного цикла формы --- */

/* ОРИГИНАЛ: input пишется напрямую. В --fixed первая строка тела —
 * resetTagLedger() (ровно как в пропатченном fillTaskForm). */
function fillTaskForm(task) {
  if (process.argv.includes("--fixed")) {
    resetTagLedger();
  }
  task._input.value = (task.tags || []).join(", ");
}

function closeTaskForm(task) {
  closeTagHints(task._input);
  if (process.argv.includes("--fixed")) {
    resetTagLedger();
  }
}

function submitTaskForm(task) {
  /* capture-хук комбобокса на submit — 1:1 порядок: flush ДО чтения
   * input в collectTaskForm. */
  flushCommittedToInput(task._input);
  return { title: task.title, tags: splitTags(task._input.value) };
}

/* --- Сценарий (как в ревью) --- */
var taskA = { title: "A", tags: ["X", "Y"], _input: { value: "" } };
var taskB = { title: "B", tags: ["P"], _input: { value: "" } };

/* 1. Редактирование A: форма заполнена тегами X,Y. */
fillTaskForm(taskA);

/* 2. Выбор Z из дропдауна (chooseValue): Z уходит в committedTags,
 * токен ввода убирается из поля (syncInputAndDom); X,Y — rest, остаются
 * в строке: итог «Z, X, Y,» (чипы X,Y,Z). */
committedTags.push("Z");
taskA._input.value = "Z, X, Y,";

/* 3. Сохранение A: flush добавляет committed в input, сабмит собирает
 * payload, closeTaskForm закрывает форму. */
flushCommittedToInput(taskA._input);
var patchA = submitTaskForm(taskA);
closeTaskForm(taskA);

/* 4. Редактирование B: fillTaskForm пишет input напрямую. */
fillTaskForm(taskB);

/* 5. Сохранение B без правок. */
var patchB = submitTaskForm(taskB);
closeTaskForm(taskB);

var leaked = patchB.tags.indexOf("Z") !== -1;
console.log("PATCH A tags:", JSON.stringify(patchA.tags));
console.log("PATCH B tags:", JSON.stringify(patchB.tags));
console.log(
  process.argv.includes("--fixed") ? "[FIXED]" : "[BEFORE FIX]",
  leaked ? "FAIL: утечка — Z перенесен в задачу B" : "OK: утечки нет"
);
process.exit(leaked ? 1 : 0);
