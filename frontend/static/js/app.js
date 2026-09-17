/* Каркас интерфейса (tasks.md 3.1): кнопка «Выйти» в сайдбаре.
 *
 * POST /api/auth/logout (sdd.md §3.1) с сессионной кукой (credentials
 * same-origin); успех → redirect на /login. Неуспех (401 — сессия уже
 * истекла/удалена) → тоже на /login: middleware сам перенаправит страницы
 * на форму входа; никаких раскрытий причин здесь не требуется.
 */
(function () {
  "use strict";

  var button = document.getElementById("logout-button");
  if (!button) {
    return;
  }

  button.addEventListener("click", function () {
    button.disabled = true;
    fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
    })
      .then(function () {
        window.location.href = "/login";
      })
      .catch(function () {
        button.disabled = false;
      });
  });
})();
