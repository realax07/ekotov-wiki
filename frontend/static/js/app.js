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
 *
 * redesign-ui-a (§1.6 sdd; ОВ-2): переключатель темы — делегат на
 * #theme-toggle: flip data-theme="light" на <html>, запись localStorage
 * ("theme" = "light"/"dark"), синхронизация aria-pressed (в т.ч. начальная —
 * по факту атрибута при загрузке: сервер тему не знает). Начальную тему
 * ставит инлайн-инициализатор в head (анти-FOUC). Явный выбор пользователя
 * приоритетен: слушателя prefers-color-scheme change нет. Блокировка
 * localStorage (private mode) — try/catch, тема живет до перезагрузки.
 */
(function () {
  "use strict";

  /* --- Переключатель темы (redesign-ui-a §1.6). --- */
  var themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    var syncThemePressed = function () {
      themeToggle.setAttribute(
        "aria-pressed",
        String(document.documentElement.getAttribute("data-theme") === "light")
      );
    };
    syncThemePressed();
    themeToggle.addEventListener("click", function () {
      var root = document.documentElement;
      var light = root.getAttribute("data-theme") === "light";
      if (light) {
        root.removeAttribute("data-theme");
      } else {
        root.setAttribute("data-theme", "light");
      }
      try {
        localStorage.setItem("theme", light ? "dark" : "light");
      } catch (e) {
        /* private mode: тема живет до перезагрузки, ошибка молчит */
      }
      syncThemePressed();
    });
  }

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
