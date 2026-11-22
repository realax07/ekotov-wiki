/* Мобильная версия V1 «Таб-бар» (redesign-ui-a, мобайл-волна; эталон
 * design-forge/extra/mobile-v1/board.html §sheet-more): механика шторки
 * «Ещё» ≤760px — новый файл, функциональный JS (app.js, board/, wiki/)
 * НЕ тронут (ОГР-28).
 *
 * Обязанности:
 * 1. Шторка «Ещё»: открыть (#more-button), закрыть (крестик #more-close,
 *    подложка #tabbar-backdrop, Escape); aria-expanded на кнопке.
 * 2. Тумблер темы (#theme-switch-mobile) — та же семантика, что у
 *    #theme-toggle сайдбара (app.js): flip data-theme="light" на <html>,
 *    localStorage "theme" = "light"/"dark" (delete = темная), aria-pressed
 *    сайдбарного тумблера синхронизируется. Начальное состояние чекбокса —
 *    по data-theme (инициализатор anti-FOUC в base.html).
 * 3. «Выйти» (#logout-button-mobile) — тот же запрос, что app.js
 *    (#logout-button): POST /api/auth/logout с сессионной кукой, затем
 *    redirect на /login.
 *
 * Все элементы есть на каждой странице (base.html); на desktop шторка
 * скрыта CSS — подписки безвредны. ОГР-8: без внешних библиотек. */
(function () {
  "use strict";

  var sheet = document.getElementById("more-sheet");
  var openButton = document.getElementById("more-button");
  var closeButton = document.getElementById("more-close");
  var backdrop = document.getElementById("tabbar-backdrop");

  function openSheet() {
    sheet.hidden = false;
    backdrop.hidden = false;
    openButton.setAttribute("aria-expanded", "true");
    closeButton.focus();
  }

  function closeSheet() {
    sheet.hidden = true;
    backdrop.hidden = true;
    openButton.setAttribute("aria-expanded", "false");
  }

  if (openButton && sheet && backdrop && closeButton) {
    openButton.addEventListener("click", openSheet);
    closeButton.addEventListener("click", closeSheet);
    backdrop.addEventListener("click", closeSheet);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !sheet.hidden) closeSheet();
    });
  }

  /* Тема — семантика app.js #theme-toggle (светлая = data-theme="light"). */
  var themeSwitch = document.getElementById("theme-switch-mobile");
  var sidebarToggle = document.getElementById("theme-toggle");

  function syncThemeSwitch() {
    if (themeSwitch) {
      themeSwitch.checked =
        document.documentElement.getAttribute("data-theme") === "light";
    }
  }

  syncThemeSwitch();

  if (themeSwitch) {
    themeSwitch.addEventListener("change", function () {
      var root = document.documentElement;
      if (themeSwitch.checked) {
        root.setAttribute("data-theme", "light");
        try { localStorage.setItem("theme", "light"); } catch (e) { /* приватный режим */ }
      } else {
        root.removeAttribute("data-theme");
        try { localStorage.setItem("theme", "dark"); } catch (e) { /* приватный режим */ }
      }
      if (sidebarToggle) {
        sidebarToggle.setAttribute(
          "aria-pressed",
          String(themeSwitch.checked)
        );
      }
    });
  }

  /* Выход — POST /api/auth/logout, затем /login (sdd.md §3.1; как app.js). */
  var logoutButton = document.getElementById("logout-button-mobile");
  if (logoutButton) {
    logoutButton.addEventListener("click", function () {
      fetch("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin",
      }).finally(function () {
        window.location.href = "/login";
      });
    });
  }
})();
