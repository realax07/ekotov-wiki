# Review 4.5 — Форма создания/карточка задачи в UI

- **Коммит:** d4b380f (`task 4.5: task forms & card UI`)
- **Ревьюер:** code_reviewer (изолированная сессия)
- **Арбитры:** sdd.md §3.2/§3.3, specs/tasks/spec.md (дельта), requirements.md FR-5/FR-7/FR-9, design.md §8
- **Дата:** 2026-09-17

## Вердикт: **return**

Один major (сломанный рендер `error.details` ветки 422 — пользователь видит `[object Object]`)
и два minor. Функциональный объем задачи выполнен полностью; return — из-за major,
approve с открытым major запрещен.

## Масштаб дифа

- `frontend/static/js/board.js` (+450), `frontend/templates/board.html` (+97),
  `frontend/static/css/board.css` (+119), `tasks.md` (чекбокс 4.5 → [x]).
- **API не изменен**: `git diff d4b380f~1 d4b380f -- backend/` пуст (0 строк) — подтверждено.
- Статика в app не смонтирована (design §8, nginx) — `grep StaticFiles|mount backend/app/` пуст.

## Независимая проверка (TestClient, свой смоук вне репозитория)

- GET /board без сессии → **302 /login**; с сессией → **200**.
- Все 27 ID формы/модала в HTML: `create-task-button`, `task-form(-overlay/-heading/-error/-submit/-cancel)`,
  `task-title/description/priority/category/due-date/tags/is-fast`, `task-detail-overlay/-title/-error/-attrs`,
  `task-move-select`, `task-edit-button`, `task-delete-button`, `task-detail-close`,
  `task-comments-list`, `comment-form`, `comment-body`, `comment-error`, `board-error` — **отсутствующих нет**.
- Живой цикл API: POST /api/tasks (title=`<script>alert(1)</script>`) → 201;
  POST comments (`<img src=x onerror=…>`) → 201; GET /api/board → keys `todo/in_progress/done_note`, 1 задача;
  PATCH с `is_fast` → **422** (extra=forbid, сервер отклоняет — board.js его в PATCH и не шлет);
  PATCH без → 200; DELETE → 204; анонимный GET /api/board → 401.
- Тела 422 сервера (проверено фактически): `details` — **массив** объектов pydantic
  (`[{"type":…, "loc":…, "msg":…}]`), не словарь. Это ключевой факт для замечания №1.
- `node --check board.js` — OK.
- grep XSS: присваиваний `innerHTML`/`insertAdjacentHTML`/`document.write`/`eval` в
  `frontend/static/js/` **нет** — только упоминания в комментариях (строки 20, 299, 329).

## Круг 1 — спека как закон

- «Создание только с названием» — форма шлет 7-элементный payload (6 признаков + is_fast),
  пустые уходят null/[] — сценарий покрыт.
- «Негативный: создание без названия» — UI-валидация **до** fetch (board.js:265-269) + серверный
  422; сообщение пользователю показывается. Покрыт.
- «Создание с заполненными признаками», «Просмотр/редактирование признаков», «Комментарии»,
  «Изменение названия», «Удаление с подтверждением» (window.confirm, board.js:405) — покрыты.
- FR-9 = 7 признаков: название, описание, приоритет, категория, срок, теги — в форме (6);
  комментарии — в карточке (Scenario «Комментарии к задаче» требует их в карточке, не в форме
  создания). Соответствует спеке; заголовок dev-отчета «7 полей формы» — неточность формулировки,
  не дефект.
- is_fast: в payload только при `currentTaskId === null` (board.js:254-256); в режиме
  редактирования чекбокс скрыт и принудительно unchecked — ОГР-5/sdd §3.2 соблюдены дважды
  (UI + серверный extra=forbid, проверено живым 422).
- 409 не обрабатывается specially — корректно: зона 5.1, общий обработчик ошибок.
- Поведения вне спеки нет.

## Круг 2 — best practices

- XSS: весь пользовательский вывод (title, description, category, due_date, теги, комментарии,
  созданные через TestClient с `<script>`/`<img onerror>`) рендерится через `createElement` +
  `textContent` (`el()` board.js:29-38; detail board.js:305-314; comments board.js:320-333).
  `classList.add("task-priority-" + priority)` — приоритет ограничен Literal на сервере,
  приемлемо. Разметка шаблона пользовательских данных не содержит.
- fetch: единая обертка `api()` — credentials same-origin, 204, catch сетевых ошибок; после
  каждой мутации refreshBoard. кроме замечаний №1-2 ниже — корректно.
- Секретов нет; CSS без expression/url(); чтаемость в норме.

## Круг 3 — integration-точки

- Контракты sdd §3.2 соблюдены клиентом: POST/PATCH/DELETE/move/comments — пути и методы дословно.
- GET /api/board: рендер только todo/in_progress + done_note — согласовано с §3.3 и 4.3.
- Каскадное удаление комментариев (FK) не задето; 4.4 move — select шлет `{status}` из
  допустимых трех значений.

## Замечания

| # | Серьезность | Файл/строка | Замечание | Рекомендация |
|---|---|---|---|---|
| 1 | major | frontend/static/js/board.js:84-91 (`handleApiError`) | Ветка 422 рассчитана на `details`-**объект**, но сервер (проверено TestClient) возвращает `details` **массивом** объектов pydantic. `Object.keys([err])` → `"0"`, `String({type,…})` → `"[object Object]"`: пользователь на любой серверный 422 видит «validation error. 0: [object Object]» вместо деталей. Заявленное в шапке файла и dev-отчете «422 → показ error.details» фактически не работает. UI-валидация title перехватывает частый случай, но 422 от сервера достижима (напр., рассинхрон валидаций). | Обработать массив: `if (Array.isArray(details)) details.forEach(d => parts.push((d.loc ? d.loc.join(".") + ": " : "") + (d.msg \|\| "")))`, оставив ветку объекта как fallback. Добавить в смоук проверку текста 422-сообщения. |
| 2 | minor | frontend/static/js/board.js:64-70 (`parseBody`) | `try/catch` вокруг `response.json()` не ловит async-отказ: не-JSON тело ошибки (HTML 502 от nginx и т.п.) отклоняет промис, уходит в общий `.catch` и показывается как «Сетевая ошибка» при реально полученном HTTP-статусе — вводит в заблуждение. | Вернуть из parseBody `response.json().catch(() => null)` и в ветке `!response.ok` при `body === null` показывать «Ошибка запроса (HTTP N)» без попытки разбора details. |
| 3 | minor | frontend/static/js/board.js:326 (`renderComments`) | Метка комментария склеивает `comment.id`/`comment.created_at` без защиты от undefined: отсутствие поля даст «id 5 · undefined» в UI. Поля гарантированы схемой, поэтому только косметика/робастность. | Рендерить метку из отфильтрованных непустых частей либо не выводить метку вовсе (id/дата — внутренние детали, спека их отображение не требует). |

## Проверено лично

- Смоук TestClient (свой, вне репо): 302/200 /board, все 27 ID, POST/PATCH/DELETE/move-контракт,
  401/404/422 тела, XSS-данные в БД и ответах API, extra=forbid на is_fast в PATCH.
- board.js построчно: все 9 fetch-точек (board, GET task, POST, PATCH, DELETE, move, comments
  GET/POST), ветки 401/422/сеть/204, UI-валидация title и comment до fetch, is_fast-логика.
- grep + node --check; диф: backend не тронут; tasks.md — только чекбокс 4.5.
- Сверка 7 признаков FR-9 и сценариев дельты tasks (включая негативные).

## Не проверено

- Реальный браузер (клики/фокус/оверлеи) — только TestClient-рендер и статический анализ JS;
  behavior-проверка DOM-событий вне инструментария ревью.
- board.css визуально (подсветка fast line — зона 5.2).
- Нагрузка/NFR (8.x), конкурентные запросы — вне задачи.
