/* Вход (tasks.md 2.3; sdd.md §3.1, §1): submit → POST /api/auth/login (JSON).
 *
 * 200 → редирект на страницу доски (первая страница функционала, sdd.md §3.6);
 * 401 → единый текст «Неверный логин или пароль» — причина (несуществующий
 * логин / неверный пароль) не раскрывается (NFR-7, дельта auth).
 */
(function () {
  "use strict";

  var form = document.getElementById("login-form");
  var errorEl = document.getElementById("login-error");
  var submitBtn = document.getElementById("login-submit");

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
          // Успешный вход — на доску (sdd.md §3.6).
          window.location.href = "/board";
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
