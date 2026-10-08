# BUG-014: просмотр карточки из advanced-поиска — старый рендер, не унифицирован с окном задачи

- **ID:** BUG-014
- **Статус:** ОТКРЫТ (2026-10-08, приемка Заказчика r8-polish, п.2)
- **Дата:** 2026-10-08
- **Окружение:** прод r8-polish (main 7e00a1b); advanced-поиск (search.html/search.js).
- **Severity:** major (несоответствие приемке: «Просмотр карточки из advanced поиска остался старым. Нужно одинаковый сделать»)
- **Автотест:** отсутствует (после унификации — smoke открытия карточки из поиска)

## Жалоба Заказчика (приемка r8-polish, п.2)

«Просмотр карточки из advanced поиска остался старым. Нужно одинаковый сделать».

## Факты ПМ

- Дубль реализации: frontend/static/js/search.js (renderTaskDetail: старый
  dl-список #task-detail-attrs, board.css:1312+) + СОБСТВЕННАЯ разметка overlay
  в frontend/templates/search.html:134; против нового
  frontend/static/js/board/task-detail.js (ES-модуль: бейджи, аватары, attr-grid,
  экспорт openTaskDetail/closeTaskDetail/initTaskViewControls) + разметка
  board.html:247.
- Результат: из доски карточка открывается в новом оформлении, из advanced-поиска —
  в старом. Заказчику нужен ОДИНАКОВЫЙ просмотр.

## Направление решения (за сабагентом, не догма)

Унифицировать на board/task-detail.js (мокап-арбитр polish-ticket-modal.html):
search.html получает ту же разметку overlay (task-view), search.js вызывает
экспортируемый openTaskDetail (import из board/task-detail.js — ОГР-8: без внешних
файлов/библиотек, свои модули допустимы; проверить подключение type=module).
Старый рендер/разметку search.js/search.html — вывести из эксплуатации.
Зоны: frontend/templates/**, frontend/static/js/**.

## Критерий закрытия

Карточка из advanced-поиска открывается визуально идентично окну из доски
(та же разметка task-view, computed styles совпадают по ключевым селекторам).
Смоук: открытие карточки из поиска green; смежные поисковые тесты не деградировали.
