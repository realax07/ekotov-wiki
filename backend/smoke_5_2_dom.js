/* Смоук JS-логики 5.2 в jsdom: подсветка fast-линии при рендере и ветка 409.
 * Запуск: node backend/smoke_5_2_dom.js */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("/home/openclaw/.hermes/hermes-agent/node_modules/jsdom");

const dom = new JSDOM(`<!DOCTYPE html><html><body>
<button id="create-task-button"></button>
<div id="board" class="board" data-loaded="false">
  <section class="board-column" id="column-todo" data-status="todo">
    <h2 class="board-column-title">Ожидает</h2><div class="board-column-cards" data-cards></div>
  </section>
  <section class="board-column" id="column-in_progress" data-status="in_progress">
    <h2 class="board-column-title">В работе</h2><div class="board-column-cards" data-cards></div>
  </section>
  <section class="board-column board-column-done" id="column-done" data-status="done">
    <h2 class="board-column-title">Выполнено</h2><p class="board-done-note" data-done-note></p>
  </section>
</div>
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
    <h2 id="task-detail-title"></h2><p id="task-detail-error" class="form-error" hidden></p>
    <dl id="task-detail-attrs"></dl>
    <div class="task-detail-actions">
      <select id="task-move-select"></select>
      <button type="button" id="task-edit-button"></button>
      <button type="button" id="task-delete-button"></button>
      <button type="button" id="task-detail-close"></button>
    </div>
    <section class="task-comments">
      <h3>Комментарии</h3><ul id="task-comments-list"></ul>
      <form id="comment-form"><textarea id="comment-body"></textarea>
      <p id="comment-error" class="form-error" hidden></p><button type="submit"></button></form>
    </section>
  </div>
</div>
</body></html>`, { url: "http://localhost/board", runScripts: "dangerously" });

const { window } = dom;
let fetchResponse = { ok: true, status: 200, body: { columns: {} } };
window.fetch = function () {
  /* Заглушка ответа: все поля читаются лениво — начальный refreshBoard()
   * из IIFE вызывается до того, как тест подставит данные доски. */
  return Promise.resolve({
    get ok() {
      return fetchResponse.ok;
    },
    get status() {
      return fetchResponse.status;
    },
    json: () => {
      if (fetchResponse.rejectJson) {
        return Promise.reject(new Error("not json"));
      }
      return Promise.resolve(fetchResponse.body);
    },
  });
};

const src = fs.readFileSync(path.join(__dirname, "..", "frontend", "static", "js", "board.js"), "utf-8");
window.eval(src);

function assert(cond, msg) {
  if (!cond) { console.error("FAIL", msg); process.exitCode = 1; } else { console.log("OK ", msg); }
}

// --- Сценарий 1: fast-задача на доске: подсветка столбца и карточки, порядок ---
fetchResponse = { ok: true, status: 200, body: { columns: {
  todo: [
    { id: 2, title: "normal", is_fast: false, priority: "high" },
    { id: 1, title: "urgent fast", is_fast: true, priority: "medium" },
    { id: 3, title: "low", is_fast: false, priority: "low" },
  ],
  in_progress: [],
  done_note: "done",
}}};

window.eval("void 0");
/* refreshBoard вызывается при инициализации IIFE; fetch — Promise, дадим микротаскам выполниться. */
setTimeout(() => {
  const todoColumn = window.document.getElementById("column-todo");
  const fastCard = window.document.querySelector('[data-task-id="1"]');
  const normalCard = window.document.querySelector('[data-task-id="2"]');

  assert(todoColumn.classList.contains("has-fast"), "столбец с fast-задачей получил класс has-fast");
  assert(!window.document.getElementById("column-in_progress").classList.contains("has-fast"),
    "столбец без fast-задач не подсвечен");
  assert(fastCard.classList.contains("task-card-fast"), "fast-карточка получила класс task-card-fast");
  assert(!normalCard.classList.contains("task-card-fast"), "обычная карточка без подсветки");
  assert(fastCard.dataset.fast === "true" && fastCard.querySelector(".task-fast-badge") !== null,
    "у fast-карточки data-fast=true и бейдж fast");
  const order = [...todoColumn.querySelectorAll(".task-card")].map((c) => c.dataset.taskId);
  assert(order.join(",") === "2,1,3", "порядок карточек = порядок ответа сервера (2,1,3): " + order.join(","));

  // --- Сценарий 2: 409 fast line occupied -> сообщение «fast line занята», задача не создается ---
  // Форма сначала открывается через openCreateForm (как это делает UI).
  fetchResponse = { ok: true, status: 200, body: { columns: {} } };
  window.document.getElementById("create-task-button").click();
  if (window.document.getElementById("task-form-overlay").hidden) {
    console.error("FAIL форму создания не удалось открыть кликом по create-task-button");
    process.exitCode = 1;
  }

  fetchResponse = { ok: false, status: 409, body: { error: "fast line occupied" } };
  window.document.getElementById("task-title").value = "вторая fast";
  window.document.getElementById("task-is-fast").checked = true;
  const event = new window.Event("submit", { bubbles: true, cancelable: true });
  window.document.getElementById("task-form").dispatchEvent(event);

  setTimeout(() => {
    const err = window.document.getElementById("task-form-error");
    assert(err.hidden === false && err.textContent === "fast line занята",
      "после 409 показано «fast line занята» (task-form-error, рядом с чекбоксом)");
    assert(window.document.getElementById("task-form-overlay").hidden === false,
      "форма осталась открытой (задача не создана)");

    // --- Сценарий 3: повторная попытка без fast — успех (сценарий спеки «Повторная попытка») ---
    fetchResponse = { ok: true, status: 200, body: { id: 9 } };
    window.document.getElementById("task-is-fast").checked = false;
    window.document.getElementById("task-form").dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
    setTimeout(() => {
      assert(window.document.getElementById("task-form-overlay").hidden === true,
        "создание без fast прошло — форма закрыта");
      assert(err.hidden === true, "сообщение об ошибке скрыто при следующей отправке");
      console.log(process.exitCode ? "\nDOM SMOKE: ЕСТЬ ПРОВАЛЫ" : "\nDOM SMOKE 5.2: все проверки зеленые");
    }, 10);
  }, 10);
}, 10);
