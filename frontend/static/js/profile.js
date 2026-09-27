/* Блок профиля внизу сайдбара (tasks.md 1.2, add-r3-visual-foundation;
 * FR-33, ОГР-13, Д-7; sdd.md §3.1-бис, §3.6; дельта navigation —
 * Requirement «Профиль текущего пользователя внизу сайдбара»).
 *
 * ES-модуль (требование ТЗ): подключается в base.html c type="module" —
 * все страницы функционала (board, search, wiki, settings) наследуют
 * base.html, поэтому блок заводится один раз и доступен везде.
 *
 * Данные — GET /api/auth/me (sdd.md §3.1-бис): 200 {"user": "<login>"}
 * → заполнить кружок (первая буква логина, верхний регистр) и подпись
 * (логин целиком, Д-7); 401 {"error": "unauthorized"} → блок не
 * отображается (middleware и так перенаправит страницу на /login).
 * Аватарки-файлы и смена пароля отсутствуют (ОГР-13, Won't) — блок
 * статичен: никаких действий, только отображение.
 *
 * Кружок — один акцентный цвет V3 (--color-accent), решение dev-задачи
 * в рамках design.md §3 («один акцентный цвет — решение dev-задачи»).
 * XSS-дисциплина: только createElement + textContent.
 */
"use strict";

const PROFILE_CONTAINER_ID = "sidebar-profile";

export function firstLetterUpper(login) {
  return login.charAt(0).toUpperCase();
}

function fillProfile(container, login) {
  const badge = document.createElement("span");
  badge.className = "profile-badge";
  badge.setAttribute("aria-hidden", "true");
  badge.textContent = firstLetterUpper(login);

  const name = document.createElement("span");
  name.className = "profile-name";
  name.textContent = login;

  container.replaceChildren(badge, name);
  container.classList.add("profile-filled");
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
    const login = body && typeof body.user === "string" ? body.user : "";
    if (login) {
      fillProfile(container, login);
    }
  } catch {
    /* сеть/сервер — блок не отображается */
  }
}

loadProfile();
