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
 *
 * Tooltip (3.2, FR-43, ОГР-17, ОВ-25): при наведении/фокусе на блоке
 * показывается всплывашка — аватар (или кружок-фоллбек), display_name
 * (или логин, Д-10), логин, роль, bio (пустое bio — блок не показывается);
 * показ с задержкой 300мс (не мешает клику), скрытие по mouseleave/
 * blur/Escape; при prefers-reduced-motion — без анимации (TC-vis-105).
 * Механика — общий модуль tooltip.js (переиспользуется карточками 5.1).
 */
"use strict";

const PROFILE_CONTAINER_ID = "sidebar-profile";
const SETTINGS_PROFILE_URL = "/settings/profile";

/* Ссылка «Мониторинг» (1.4, FR-78, дельта navigation; change
 * add-netdata-monitoring): константа — XSS-дисциплина (href не
 * собирается из данных ответа, design §3). Дашборд Netdata за nginx
 * basic auth (design §2); до поднятия контейнера (задача 1.2/1.3)
 * /netdata/ отвечает 404/401 — норма, ссылка видна owner. */
const NETDATA_URL = "/netdata/";
/* Роль owner («Product manager» = owner-логин, бэкфилл ОВ-21): только
 * ей создается пункт (design §2; скрытие — удобство, НЕ защита). */
const NETDATA_ALLOWED_ROLE = "Product manager";

export function firstLetterUpper(login) {
  return login.charAt(0).toUpperCase();
}

/* Пункт «Мониторинг» (1.4, FR-78): <a href="/netdata/" target="_blank"
 * rel="noopener"> с иконкой-пульсом (утвержденный мокап 1.1а
 * design/netdata-sidebar-mockup.html, иконка design/netdata-icon.svg —
 * inline-SVG 16px, stroke="currentColor" → токенная окраска) и текстом;
 * вставляется в sidebar-footer ПЕРЕД «Настройки». Без промпт-карточки
 * и без маркера внешней ссылки (решение Заказчика 2026-10-05,
 * decision 2026-10-05-netdata-mockup-approval). XSS-дисциплина:
 * только createElement + textContent, href — константа. */
function buildMonitoringItem() {
  const link = document.createElement("a");
  link.className = "nav-item nav-item-monitoring";
  link.href = NETDATA_URL;
  link.target = "_blank";
  link.rel = "noopener";

  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("class", "nav-icon");
  icon.setAttribute("aria-hidden", "true");

  const pulse = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  pulse.setAttribute("points", "2.5 12 7 12 10 5.5 14 18.5 17 12 21.5 12");
  pulse.setAttribute("fill", "none");
  pulse.setAttribute("stroke", "currentColor");
  pulse.setAttribute("stroke-width", "2");
  pulse.setAttribute("stroke-linecap", "round");
  pulse.setAttribute("stroke-linejoin", "round");
  icon.appendChild(pulse);

  const label = document.createElement("span");
  label.className = "nav-label";
  label.textContent = "Мониторинг";

  link.append(icon, label);
  return link;
}

/* Пункт создается при заполненном блоке профиля (успешный /api/auth/me)
 * и только для роли «Product manager» (owner); позиция — перед
 * «Настройки» (мокап 1.1а). До ответа/при 401/другой роли пункт не
 * создается — паттерн блока профиля (design §2, §3). */
function insertMonitoringItem(me) {
  if (me.role !== NETDATA_ALLOWED_ROLE) {
    return;
  }
  const footer = document.querySelector(".sidebar-footer");
  if (!footer || footer.querySelector(".nav-item-monitoring")) {
    return;
  }
  const settingsLink = footer.querySelector(".nav-item-settings");
  const item = buildMonitoringItem();
  if (settingsLink) {
    footer.insertBefore(item, settingsLink);
  } else {
    footer.insertBefore(item, footer.firstChild);
  }
}

/* Контент tooltip профиля (3.2, ОВ-25): аватар (или кружок-фоллбек),
 * display_name (или логин, Д-10), логин, роль, bio. Пустое bio —
 * блок bio не показывается (ОВ-25). XSS-дисциплина: только
 * createElement + textContent (URL аватара — через свойство src). */
function buildProfileTooltipContent(me) {
  const login = me.user;

  const wrap = document.createElement("div");
  wrap.className = "tooltip-profile";

  const head = document.createElement("div");
  head.className = "tooltip-profile-head";

  const avatarUrl = typeof me.avatar_url === "string" ? me.avatar_url : null;
  const name = document.createElement("span");
  name.className = "tooltip-profile-name";
  name.textContent = me.display_name || login; /* Д-10 */

  if (avatarUrl) {
    const avatar = document.createElement("img");
    avatar.className = "tooltip-profile-avatar";
    avatar.src = avatarUrl;
    avatar.alt = "";
    head.appendChild(avatar);
  } else {
    const badge = document.createElement("span");
    badge.className = "tooltip-profile-badge";
    badge.setAttribute("aria-hidden", "true");
    badge.textContent = firstLetterUpper(login);
    head.appendChild(badge);
  }
  head.appendChild(name);

  const loginLine = document.createElement("span");
  loginLine.className = "tooltip-profile-login";
  loginLine.textContent = login;

  wrap.append(head, loginLine);

  const role = typeof me.role === "string" ? me.role : "";
  if (role) {
    const roleLine = document.createElement("span");
    roleLine.className = "tooltip-profile-role";
    roleLine.textContent = role;
    wrap.appendChild(roleLine);
  }

  const bio = typeof me.bio === "string" ? me.bio : "";
  if (bio) {
    const bioLine = document.createElement("p");
    bioLine.className = "tooltip-profile-bio";
    bioLine.textContent = bio;
    wrap.appendChild(bioLine);
  }

  return wrap;
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

  /* Tooltip профиля (3.2, FR-43, ОГР-17): показ по hover/focus с задержкой
   * ~300мс — всплывашка не мешает клику по блоку (клик → настройки);
   * скрытие по mouseleave/focusout/Escape — механика attach() единого
   * модуля tooltip.js. */
  attachProfileTooltip(container, me);
}

function attachProfileTooltip(container, me) {
  import("./tooltip.js")
    .then(function (tooltip) {
      tooltip.attach(container, function () {
        return buildProfileTooltipContent(me);
      }, { delay: 300 });
    })
    .catch(function () {
      /* модуль недоступен — блок профиля работает без всплывашки */
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
      /* 1.4 (FR-78): после успешного /api/auth/me — при роли owner. */
      insertMonitoringItem(body);
    }
  } catch {
    /* сеть/сервер — блок не отображается */
  }
}

loadProfile();
