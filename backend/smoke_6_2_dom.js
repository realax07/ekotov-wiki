/* Смоук DOM-логики 6.2: бейдж «Архивная» в карточке.
 * renderTaskDetail не экспортируется из board.js (IIFE), поэтому
 * проверяем: (а) DOM-контракт бейджа (hidden + статичный текст);
 * (б) операцию рендера board.js 1-в-1 — тот же операнд на реальных
 * Task-объектах (архивная / не-архивная). board.js при этом полностью
 * eval-ится в JSDOM: синтаксис и определение бейджа не ломают загрузку.
 * Запуск: node backend/smoke_6_2_dom.js */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("/home/openclaw/.hermes/hermes-agent/node_modules/jsdom");

const dom = new JSDOM(`<!DOCTYPE html><html><body>
<button id="create-task-button"></button>
<div id="board" class="board" data-loaded="false"></div>
<p id="board-error" class="board-error" hidden></p>
<div id="task-form-overlay" class="modal-overlay" hidden>
  <form id="task-form" class="modal task-form">
    <h2 id="task-form-heading"></h2><p id="task-form-error" class="form-error" hidden></p>
    <input type="text" id="task-title"><textarea id="task-description"></textarea>
    <select id="task-priority"><option value=""></option></select>
    <input type="text" id="task-category"><input type="date" id="task-due-date">
    <input type="text" id="task-tags">
    <label class="task-form-checkbox"><input type="checkbox" id="task-is-fast"> fast line</label>
    <button type="submit" id="task-form-submit"></button><button type="button" id="task-form-cancel"></button>
  </form>
</div>
<div id="task-detail-overlay" class="modal-overlay" hidden>
  <div class="modal task-detail">
    <h2 id="task-detail-title"></h2>
    <span id="task-detail-archive-badge" class="task-archive-badge" hidden>Архивная</span>
    <p id="task-detail-error" class="form-error" hidden></p>
    <dl id="task-detail-attrs"></dl>
    <div class="task-detail-actions">
      <select id="task-move-select"></select>
      <button type="button" id="task-edit-button"></button>
      <button type="button" id="task-delete-button"></button>
      <button type="button" id="task-detail-close"></button>
    </div>
    <section class="task-comments">
      <h3>Комментарии</h3>
      <ul id="task-comments-list"></ul>
      <form id="comment-form">
        <textarea id="comment-body"></textarea>
        <p id="comment-error" class="form-error" hidden></p>
        <button type="submit" id="comment-submit"></button>
      </form>
    </section>
  </div>
</div>
</body></html>`, { url: "https://test/board", runScripts: "outside-only" });

global.window = dom.window;
global.document = dom.window.document;

// Заглушка fetch: начальный refreshBoard() при инициализации IIFE
// (смоук 5.2-стиль) — все поля читаются лениво.
let fetchResponse = { ok: true, status: 200, body: { columns: {} } };
dom.window.fetch = function () {
  return Promise.resolve({
    get ok() { return fetchResponse.ok; },
    status: fetchResponse.status,
    json: function () { return Promise.resolve(fetchResponse.body); },
  });
};

// board.js должен загрузиться без ошибок на этом DOM (смоук 5.2-стиль)
const code = fs.readFileSync(
  path.join(__dirname, "..", "frontend", "static", "js", "board.js"), "utf8"
);
dom.window.eval(code);

const badge = document.getElementById("task-detail-archive-badge");
const failures = [];
function check(name, cond) {
  console.log((cond ? "PASS" : "FAIL") + ": " + name);
  if (!cond) failures.push(name);
}

check("DOM: бейдж существует, изначально hidden, текст «Архивная»",
  badge && badge.hidden === true && badge.textContent === "Архивная");

// Реальные формы Task из GET /api/tasks/{id} (sdd §3.2):
const archivedTask = {
  id: 1, title: "архивная", description: null, priority: null,
  category: null, due_date: null, tags: [], is_fast: false,
  status: "done", done_at: "2026-09-17T10:00:00+03:00",
  archived_at: "2026-09-18T00:00:00+03:00",
  created_at: "2026-09-16T10:00:00+00:00",
};
const liveTask = {
  id: 2, title: "живая", description: null, priority: null,
  category: null, due_date: null, tags: [], is_fast: false,
  status: "todo", done_at: null, archived_at: null,
  created_at: "2026-09-18T10:00:00+00:00",
};

// Тот же рендер-операнд, что в board.js renderTaskDetail (6.2):
// document.getElementById("task-detail-archive-badge").hidden = !task.archived_at;
function applyBadgeLogic(task) {
  document.getElementById("task-detail-archive-badge").hidden = !task.archived_at;
}

applyBadgeLogic(archivedTask);
check("архивная (archived_at NOT NULL): бейдж видим", badge.hidden === false);

applyBadgeLogic(liveTask);
check("не-архивная (archived_at null): бейдж скрыт", badge.hidden === true);

// Текст статичен — данные задачи не попадают в бейдж (XSS-safe)
check("XSS: текст бейджа не зависит от данных задачи",
  badge.textContent === "Архивная");

// board.js действительно содержит этот операнд (а не другую логику)
check("board.js: операнд рендера совпадает с проверенным (hidden = !task.archived_at)",
  /task-detail-archive-badge"\)\.hidden\s*=\s*\n?\s*!task\.archived_at;/.test(code));

if (failures.length) {
  console.log("ИТОГ: FAIL — " + failures.join(", "));
  process.exit(1);
}
console.log("ИТОГ: все проверки 6.2 DOM PASS");
