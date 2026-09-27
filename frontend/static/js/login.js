/* Вход (tasks.md 2.3; sdd.md §3.1, §1): submit → POST /api/auth/login (JSON).
 *
 * 200 → редирект на страницу доски (первая страница функционала, sdd.md §3.6);
 * 401 → единый текст «Неверный логин или пароль» — причина (несуществующий
 * логин / неверный пароль) не раскрывается (NFR-7, дельта auth).
 *
 * DEF-001 (FR-35, DEV 5.2): 200 логина не гарантирует сохранение сессии —
 * Secure-кука молча отбрасывается браузером на не-trustworthy origin
 * (например, набор адреса без схемы, когда браузер открывает http://IP:порт;
 * architecture/def001-diagnosis.md §2). После 200 — контрольный
 * GET /api/auth/me: 401 → кук нет, редирект на /board дал бы немой возврат
 * на /login; вместо этого показываем явное сообщение открыть сайт по
 * https://… и НЕ редиректим. Флаг Secure куки не ослабляется (NFR-7,
 * design.md §2).
 */
(function () {
  "use strict";

  var form = document.getElementById("login-form");
  var errorEl = document.getElementById("login-error");
  var submitBtn = document.getElementById("login-submit");

  function showMessage(text) {
    /* Единый элемент сообщения (login.html #login-error): модальность
     * «ошибка входа» сохранена — пользователю виден один текст. */
    errorEl.textContent = text;
    errorEl.hidden = false;
    submitBtn.disabled = false;
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    errorEl.hidden = true;
    submitBtn.disabled = true;

    fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        login: document.getElementById("login").value,
        password: document.getElementById("password").value,
      }),
    })
      .then(function (response) {
        if (response.ok) {
          // Контроль сессии (DEF-001): кука Secure на не-trustworthy origin
          // молча не сохраняется — проверяем фактическую сессию прежде,
          // чем уводить пользователя с страницы входа.
          fetch("/api/auth/me", { credentials: "same-origin" })
            .then(function (me) {
              if (me.ok) {
                // Сессия сохранена — на доску (sdd.md §3.6).
                window.location.href = "/board";
                return;
              }
              showMessage(
                "Сессия не сохранена. Откройте сайт по адресу https://194.58.34.122:10443 (подтвердите исключение безопасности сертификата) и войдите снова."
              );
            })
            .catch(function () {
              // Сеть/сервер недоступны уже после 200 логина — сообщаем, не редиректим.
              showMessage("Сервис недоступен. Повторите вход позже.");
            });
          return;
        }
        // 401 и любой другой неуспех — один и тот же текст (NFR-7).
        errorEl.hidden = false;
        submitBtn.disabled = false;
      })
      .catch(function () {
        errorEl.hidden = false;
        submitBtn.disabled = false;
      });
  });
})();
