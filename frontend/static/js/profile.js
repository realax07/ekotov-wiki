/* Блок профиля внизу сайдбара (tasks.md 1.2 add-r3-visual-foundation;
 * FR-33, Д-7; дельта navigation — Requirement «Профиль текущего
 * пользователя внизу сайдбара», MODIFIED задачей 3.1 add-r4-user-profile-ticket-view).
 *
 * ES-модуль (требование ТЗ): подключается в base.html c type="module" —
 * все страницы функционала (board, search, wiki, settings, settings/profile)
 * наследуют base.html, поэтому блок заводится один раз и доступен везде.
 *
 * Данные — GET /api/auth/me (sdd.md §3.1-бис, расширенный состав r4):
 * 200 {"user", "display_name", "role", "bio", "avatar_url"} →
 * - подпись = display_name, если задан, иначе логин целиком (Д-10,
 *   Scenario «Подпись профиля — display_name, если задан»);
 * - аватар <img> вместо кружка при наличии avatar_url; NULL → кружок
 *   с первой буквой логина (fallback, FR-33/FR-42);
 * - блок кликабелен: клик открывает /settings/profile (FR-39, ОГР-15) —
 *   НЕ общий раздел /settings (ОГР-20);
 * 401 → блок не отображается (middleware и так перенаправит страницу
 * на /login).
 *
 * Кружок — один акцентный цвет V3 (--color-accent). XSS-дисциплина:
 * только createElement + textContent (URL аватара — через свойство src,
 * не разметку).
 */
"use strict";

const PROFILE_CONTAINER_ID = "sidebar-profile";
const SETTINGS_PROFILE_URL = "/settings/profile";

export function firstLetterUpper(login) {
  return login.charAt(0).toUpperCase();
}

function fillProfile(container, me) {
  const login = me.user;

  const badge = document.createElement("span");
  badge.className = "profile-badge";
  badge.setAttribute("aria-hidden", "true");
  badge.textContent = firstLetterUpper(login);

  const name = document.createElement("span");
  name.className = "profile-name";
  // Д-10: display_name, если задан, иначе логин целиком.
  name.textContent = me.display_name || login;

  // Аватар вместо кружка (FR-42, Scenario «Аватар отображается
  // в блоке профиля»); alt пуст — подпись рядом дублирует имя.
  const avatarUrl = typeof me.avatar_url === "string" ? me.avatar_url : null;
  const badgeOrAvatar = avatarUrl ? document.createElement("img") : badge;
  if (avatarUrl) {
    badgeOrAvatar.className = "profile-avatar";
    badgeOrAvatar.src = avatarUrl;
    badgeOrAvatar.alt = "";
  }

  container.replaceChildren(badgeOrAvatar, name);
  container.classList.add("profile-filled");

  // Клик по блоку → страница настроек пользователя (FR-39, ОГР-20):
  // блок становится ссылкой — доступность с клавиатуры (role=link +
  // tabindex) без вложенной интерактивной разметки.
  container.setAttribute("role", "link");
  container.setAttribute("tabindex", "0");
  // aria-label НЕ начинается с «Настройки» — иначе get_by_role("link",
  // name="Настройки") существующих web-тестов ловит и этот блок
  // (strict violation, регрессия TC-nav-006…008).
  container.setAttribute("aria-label", "Профиль: " + (me.display_name || login));
  const open = function () {
    window.location.href = SETTINGS_PROFILE_URL;
  };
  container.addEventListener("click", open);
  container.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      open();
    }
  });
}

async function loadProfile() {
  const container = document.getElementById(PROFILE_CONTAINER_ID);
  if (!container) {
    return;
  }
  try {
    const response = await fetch("/api/auth/me", {
      method: "GET",
      credentials: "same-origin",
    });
    if (!response.ok) {
      /* 401 и прочие неуспехи: блок не отображается (spec: негативный
       * сценарий «при 401 блок не отображается»). */
      return;
    }
    const body = await response.json().catch(() => null);
    if (body && typeof body.user === "string" && body.user) {
      fillProfile(container, body);
    }
  } catch {
    /* сеть/сервер — блок не отображается */
  }
}

loadProfile();
