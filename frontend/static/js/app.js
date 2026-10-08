/* Каркас интерфейса (tasks.md 3.1): кнопка «Выйти» в сайдбаре.
 *
 * POST /api/auth/logout (sdd.md §3.1) с сессионной кукой (credentials
 * same-origin); успех → redirect на /login. Неуспех (401 — сессия уже
 * истекла/удалена) → тоже на /login: middleware сам перенаправит страницы
 * на форму входа; никаких раскрытий причин здесь не требуется.
 *
 * 1.1 add-responsive-mobile (FR-99, design §2): мобильный drawer — toggle
 * класса sidebar-open на <body> (≤768px; desktop-ветка CSS молчит).
 * Закрытие: клик по пункту, клик по подложке, Esc, повторный бургер.
 * Фокус-менеджмент минимальный: при открытии — на первый пункт drawer,
 * при закрытии — возврат на бургер. Без внешних библиотек (ОГР-8).
 */
(function () {
  "use strict";

  var button = document.getElementById("logout-button");
  if (button) {
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
  }

  var burger = document.getElementById("burger-button");
  var sidebar = document.getElementById("sidebar");
  var backdrop = document.querySelector(".sidebar-backdrop");
  if (!burger || !sidebar || !backdrop) {
    return;
  }

  function isOpen() {
    return document.body.classList.contains("sidebar-open");
  }

  function openDrawer() {
    document.body.classList.add("sidebar-open");
    burger.setAttribute("aria-expanded", "true");
    var first = sidebar.querySelector(".nav-item");
    if (first) {
      first.focus();
    }
  }

  function closeDrawer() {
    if (!isOpen()) {
      return;
    }
    document.body.classList.remove("sidebar-open");
    burger.setAttribute("aria-expanded", "false");
    burger.focus();
  }

  burger.addEventListener("click", function () {
    if (isOpen()) {
      closeDrawer();
    } else {
      openDrawer();
    }
  });

  if (backdrop) {
    backdrop.addEventListener("click", closeDrawer);
  }

  // Закрытие по клику по пункту (переход — навигация, класс не важен после).
  sidebar.addEventListener("click", function (event) {
    var item = event.target.closest(".nav-item");
    if (item && isOpen()) {
      closeDrawer();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && isOpen()) {
      closeDrawer();
    }
  });
})();
