# REPORT — задача 1.4 add-netdata-monitoring (ссылка «Мониторинг» в сайдбаре)

Делегация: deleg-6ef078ed69c34454, correlation_id 6ef078ed69c34454a0e790dd827c806e.
Роль: dev, зона frontend/static/**. Ветка: add-netdata-monitoring (коммит локальный, без push).

## Что реализовано

Ссылка «Мониторинг» в sidebar-footer СТРОГО по утвержденному мокапу 1.1а
(design/netdata-sidebar-mockup.html, решение Заказчика 2026-10-05: БЕЗ
промпт-карточки — клик открывает /netdata/ напрямую; БЕЗ маркера внешней
ссылки; иконка-пульс из design/netdata-icon.svg):

- `frontend/static/js/profile.js` — после успешного fetch `/api/auth/me`
  при `me.role === 'Product manager'` создается пункт
  `<a href="/netdata/" target="_blank" rel="noopener">` (классы
  `nav-item nav-item-monitoring`) с inline-SVG иконкой-пульсом 16px
  (stroke="currentColor" — токенная окраска) и текстом «Мониторинг»;
  вставка ПЕРЕД «Настройки» (insertBefore относительно .nav-item-settings;
  «Настройки» — первый элемент footer, поэтому пункт становится первым
  ребенком footer — порядок [Мониторинг, Настройки, Выйти, профиль],
  подтвержден DOM-пробой). До ответа / 401 / другая роль — пункт не
  создается (паттерн блока профиля). XSS-дисциплина: createElement(NS) +
  textContent, href — константа NETDATA_URL, innerHTML не используется.
  Повторная вставка защищена (querySelector до insert).
- `frontend/static/css/app.css` — блок .nav-item-monitoring: только токены
  V3 (—space-1, —p-paper-050, —focus-ring, —color-accent), состояния
  default / hover (вуаль rgba(255,253,249,0.08), как у .nav-item) /
  focus-visible (inset —focus-ring) / active (—color-accent). Сырых
  hex-значений в блоке нет (rgba-вуаль — значение каркаса .nav-item,
  унаследовано от существующего паттерна).

Шаблоны (base.html) НЕ тронуты — design §3. RAM-контекст: /netdata/ сейчас
404 — норма (контейнер появится задачей 1.2/1.3, проверка перехода — 2.1).

## Измененные файлы

1. `frontend/static/js/profile.js` (+72 строки)
2. `frontend/static/css/app.css` (+41 строка)

## Верификация

Смоук playwright (стенд как tests/web/conftest.py: uvicorn + static +
временная БД, seed owner=«Product manager» / wife=«Product engineer»),
29/29 PASS:

- Позитив (owner): пункт виден на /board и /search; href=/netdata/,
  target=_blank, rel=noopener; класс nav-item nav-item-monitoring;
  следующий сосед — .nav-item-settings («Настройки»); иконка polyline
  points 2.5 12 … 21.5 12 (мокап/иконка 1.1), stroke=currentColor,
  aria-hidden; текст «Мониторинг»; .ext-hint (маркер внешней ссылки)
  ОТСУТСТВУЕТ; JS-ошибок нет.
- Негатив (wife, «Product engineer»): пункта нет, блок профиля при этом
  заполнен (раздельность условий).
- Негатив (аноним): на /login и после редиректа /board→/login пункта и
  блока нет.
- Негатив (401 /api/auth/me route-перехват): ни блока профиля, ни пункта,
  JS молчит.
- Регресс сайдбара: разделы Доска/Поиск/Wiki/Настройки открываются, блок
  профиля заполнен, tooltip работает.
- CSS-проверки: 4 состояния присутствуют, токены, без сырых hex.

Регресс существующих web-тестов: test_r3_profile_ui + test_tooltip_r4 +
test_r5_profile_card_ui — 20 passed. test_navigation_search_ui +
test_auth_ui: 2 failed (test_search_archived_task_builder_advanced_card,
test_final_path_autoarchive_and_fast_release) — воспроизводятся на чистом
HEAD add-netdata-monitoring БЕЗ правок задачи («Ошибка запроса (HTTP 404)»
в поиске; бэкенд/тесты вне зоны frontend/static/**) — pre-existing, не
регресс 1.4, эскалируется оркестратору отдельно.

## Ворота и границы

- Дифф строго frontend/static/** (2 файла + этот REPORT).
- tasks.md чекбокс 1.4 НЕ отмечал: openspec/** вне зоны, и J10 — задача
  закрывается только после code-review approve (отметить ПМ при приемке).
- Коммит локальный, push НЕТ (политика: push — оркестратор).
- openspec validate / flow_check в моей сессии не запускались как ворота
  записи (не зона dev), рекомендация ПМ: прогнать на приемке.

## Вопросы/эскалации

1. Два pre-existing падения в test_navigation_search_ui.py (детали выше) —
   не связано с 1.4, требует отдельного разбора (возможно, зависит от
   окружения/порядка тестов).
2. Параллельная сессия ui_designer (gallery) оставила untracked
   design/gallery-*.html в общем дереве — не трогал (чужая зона).
