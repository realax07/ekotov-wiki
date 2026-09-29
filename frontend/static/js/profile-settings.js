/* Страница настроек пользователя /settings/profile (tasks.md 3.1 пакета
 * add-r4-user-profile-ticket-view; FR-39…FR-42, ОВ-21, Д-10, Д-11;
 * design §4, sdd §3.1a-кватер; дельта settings).
 *
 * ES-модуль (конвенция profile.js). Потребляет API задач 2.1–2.3:
 * - GET  /api/profile          → предзаполнение формы (Scenario
 *   «Открытие страницы настроек пользователя»: данные своего профиля);
 * - PUT  /api/profile          → сохранение ТРЕХ полей разом (PUT заменяет
 *   состав — minor M-1 review-003: шлем display_name, role и bio всегда);
 * - POST /api/profile/password → смена пароля (ошибка 422
 *   invalid current password — на странице; Д-11: сессия не трогается);
 * - POST /api/profile/avatar   → multipart-загрузка (422-тексты API
 *   «invalid file type»/«file too large» показываются как есть;
 *   превью после успешной загрузки из avatar_url).
 *
 * GET /api/users здесь НЕ используется (источник select исполнителя,
 * задача 5.1) — роль берется из двух значений ОВ-21 статичной разметкой
 * select (свободный ввод невозможен, Scenario «Роль — только выбор из
 * справочника»).
 *
 * 401 (сессия истекла между загрузкой и действием): fetch редиректу
 * middleware не подлежит → переход на /login сами (паттерн settings.js).
 * Все пользовательские строки — только textContent (XSS-дисциплина).
 */
"use strict";

/* Д-10: пустой display_name → null (пустые значения — null, sdd
 * §3.1a-кватер); в полях формы показывается пусто, имя подменяет логин
 * в блоке профиля (обрабатывает profile.js). */
function emptyToNull(value) {
  return value === "" ? null : value;
}

function showMessage(errorEl, successEl, text) {
  errorEl.textContent = text;
  errorEl.hidden = false;
  successEl.hidden = true;
}

function showSuccess(errorEl, successEl, text) {
  successEl.textContent = text;
  successEl.hidden = false;
  errorEl.hidden = true;
}

/* fetch c обработкой 401: JSON-тело или {} (тело может отсутствовать). */
async function requestJson(url, options) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
  });
  if (response.status === 401) {
    window.location.href = "/login";
    return new Promise(function () {}); // не резолвим — идет переход
  }
  const data = await response.json().catch(() => ({}));
  return { status: response.status, data };
}

/* --- Форма профиля ------------------------------------------------------- */

function initProfileForm() {
  const form = document.getElementById("profile-form");
  const nameInput = document.getElementById("profile-display-name");
  const roleSelect = document.getElementById("profile-role");
  const bioInput = document.getElementById("profile-bio");
  const errorEl = document.getElementById("profile-error");
  const successEl = document.getElementById("profile-success");

  // Предзаполнение из GET /api/profile (свой профиль, FR-39).
  requestJson("/api/profile", { method: "GET" }).then(function (result) {
    if (result.status !== 200) {
      showMessage(errorEl, successEl, "Не удалось загрузить профиль");
      return;
    }
    const profile = result.data;
    nameInput.value = profile.display_name || "";
    // Роль может быть NULL (профиль не заполнялся) — оставляем первое
    // значение справочника выбранным по умолчанию.
    if (profile.role) {
      roleSelect.value = profile.role;
    }
    bioInput.value = profile.bio || "";
    // Сигнал готовности формы (автожидание web-тестов; конвенция
    // #board data-loaded из board.js).
    form.setAttribute("data-loaded", "true");
  });

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    // PUT заменяет состав — шлем ВСЕ три поля (minor M-1 review-003).
    const payload = {
      display_name: emptyToNull(nameInput.value.trim()),
      role: roleSelect.value,
      bio: emptyToNull(bioInput.value.trim()),
    };
    try {
      const result = await requestJson("/api/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (result.status === 200) {
        showSuccess(errorEl, successEl, "Профиль сохранен");
        return;
      }
      if (result.status === 422) {
        const details = result.data && result.data.details;
        if (details && details.role) {
          showMessage(errorEl, successEl, "Роль вне справочника");
        } else {
          showMessage(
            errorEl,
            successEl,
            (result.data && result.data.error) || "Проверьте значения полей"
          );
        }
        return;
      }
      showMessage(errorEl, successEl, "Не удалось сохранить профиль");
    } catch {
      showMessage(errorEl, successEl, "Не удалось сохранить профиль");
    }
  });
}

/* --- Смена пароля -------------------------------------------------------- */

function initPasswordForm() {
  const form = document.getElementById("password-form");
  const currentInput = document.getElementById("password-current");
  const newInput = document.getElementById("password-new");
  const errorEl = document.getElementById("password-error");
  const successEl = document.getElementById("password-success");

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    try {
      const result = await requestJson("/api/profile/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: currentInput.value,
          new_password: newInput.value,
        }),
      });
      if (result.status === 200) {
        // Д-11: сессия не трогается — остаемся на странице.
        showSuccess(errorEl, successEl, "Пароль изменен");
        form.reset();
        return;
      }
      if (result.status === 422) {
        const error = result.data && result.data.error;
        showMessage(
          errorEl,
          successEl,
          error === "invalid current password"
            ? "Неверный текущий пароль"
            : error === "empty new password"
              ? "Новый пароль не может быть пустым"
              : "Не удалось сменить пароль"
        );
        return;
      }
      showMessage(errorEl, successEl, "Не удалось сменить пароль");
    } catch {
      showMessage(errorEl, successEl, "Не удалось сменить пароль");
    }
  });
}

/* --- Аватар -------------------------------------------------------------- */

function initAvatarForm() {
  const form = document.getElementById("avatar-form");
  const fileInput = document.getElementById("avatar-file");
  const errorEl = document.getElementById("avatar-error");
  const successEl = document.getElementById("avatar-success");
  const preview = document.getElementById("avatar-preview");

  function showPreview(avatarUrl) {
    if (!avatarUrl) {
      return;
    }
    preview.src = avatarUrl;
    preview.hidden = false;
  }

  // Аватар уже есть (GET /api/profile → avatar_url) — показываем превью.
  requestJson("/api/profile", { method: "GET" }).then(function (result) {
    if (result.status === 200) {
      showPreview(result.data.avatar_url);
    }
  });

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (!fileInput.files || !fileInput.files.length) {
      showMessage(errorEl, successEl, "Выберите файл");
      return;
    }
    const body = new FormData();
    body.append("file", fileInput.files[0]);
    try {
      const result = await requestJson("/api/profile/avatar", {
        method: "POST",
        body: body,
      });
      if (result.status === 200) {
        showSuccess(errorEl, successEl, "Аватар загружен");
        // Превью по URL из ответа API (?v= — кеш-бастинг, ОГР-16).
        showPreview(result.data.avatar_url);
        return;
      }
      if (result.status === 422) {
        // Тексты 422 от API — как есть (design §4: показ ошибки из ответа).
        const error = result.data && result.data.error;
        showMessage(
          errorEl,
          successEl,
          error === "file too large"
            ? "Файл слишком большой (максимум 2 МБ)"
            : "Недопустимый тип файла (только png/jpg)"
        );
        return;
      }
      showMessage(errorEl, successEl, "Не удалось загрузить аватар");
    } catch {
      showMessage(errorEl, successEl, "Не удалось загрузить аватар");
    }
  });
}

initProfileForm();
initPasswordForm();
initAvatarForm();
