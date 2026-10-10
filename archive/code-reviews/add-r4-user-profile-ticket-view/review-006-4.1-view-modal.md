# Review 006 — задача 4.1: view-модалка карточки read-only (feature/r4-view, 43cf293)

- **Ревьюер:** code_reviewer конвейера ai-factory
- **Масштаб:** `git diff 0e688c7..43cf293`, 14 файлов: `frontend/static/js/board/task-detail.js` (−106/+… переработан в view), `task-form.js` (+189: принятые действия), `board-init.js`, `search.js`, `frontend/static/css/board.css` (+71), `frontend/templates/board.html` / `search.html`, `tests/web/test_view_modal_r4.py` (new, 335 строк), адаптации conftest + 4 тест-файла, checkbox tasks.md 4.1 → [x]. Backend не задет (0 файлов).
- **Метод:** сверка диффа с дельтой specs/board ADDED «Просмотр карточки задачи — модальное окно read-only» (все 5 сценариев), design §6 (переосмысление openTaskDetail), FR-47, Д-9, ОГР-18, ОВ-24; статическое ревью без прогонов — числа из /tmp/r4_review/PROGRESS.md (web 103 passed/1 skip pre-existing; API 157/9/2 на scratch-стенде 8091 — эталон, дифф backend не задевает).

## Вердикт: APPROVE

Спецификация выполнена полностью, включая негативные сценарии (гвард hasOwnProperty — ряды assigned/creator не рисуются до 5.1, данные не выдумываются). XSS-гигиена соблюдена (все значения — textContent; разметка не содержит пользовательских данных). Д-9 реализован переиспользованием существующей task-form без копирования логики формы; механика move/delete/comments перенесена в неё дословно. Вне спеки ничего не добавлено; static_v не бампался (корректно — единый финальный бамп §6/C-5). Blocker/major 0, четыре minor + одно замечание о покрытии — не блокируют.

## Соответствие спеке (первый круг)

- **Сценарий 1 (клик → view со всеми данными, ввод/сохранение недоступны):** board.html:187-210 — modal без единого input/textarea/select; состав: название, описание, приоритет, категория, срок, статус, теги, fast, done_at, комментарии. TC-view-101 ассертом `count()==0` на поля ввода фиксирует read-only.
- **Сценарий 2 (отличие от форм, ОГР-18):** класс `.task-view` (board.css:629-684 — серифный заголовок, линии рядов, нет стилей полей), в DOM нет кнопок сохранения/удаления/селекта; TC-view-102 проверяет и класс, и точный набор кнопок `["Редактировать","Закрыть"]`.
- **Сценарий 3 (Д-9):** «Редактировать» (task-detail.js initTaskViewControls) → GET /api/tasks/{id} → openEditForm(task) — существующая форма, view закрывается; TC-view-103 проверяет заголовок «Редактирование задачи», заполненность полей и видимость блока действий.
- **Сценарий 4 (assigned/creator/комментарии):** гвард `Object.prototype.hasOwnProperty.call(task, …)` в task-detail.js:105-111 и search.js — ряды только при наличии полей в ответе API (появятся в 5.1); пустой assigned — `em.task-view-unassigned` «Unassigned» (ОВ-24). Комментарии — read-only список (`#task-comments-list` во view; `#task-form-comments-list` в форме), рендер общий через renderCommentsInto. TC-view-106 (route-фильтр добавляет поля) + TC-view-107 (негатив: без полей рядов нет вовсе).
- **Сценарий 5 (закрытие без изменения данных):** крестик `#task-view-close` (aria-label), «Закрыть», Escape (task-detail.js:171-181 — только когда форма не открыта), клик по подложке (унаследованный обработчик board-init.js:68-74). Данные не мутируются по построению — view ничего не постит.
- **FR-7 не деградировал:** перемещение/удаление/комментарии доступны в форме редактирования (task-actions + task-comments, скрыты в режиме создания — задач еще нет); регресс-тесты conftest move_via_card_select, test_r3_dnd/vis, test_board_tasks_ui адаптированы под новый путь карточка → «Редактировать».
- **Вложенные формы:** блок комментариев вынесен соседним элементом к `#task-form` с верным обоснованием в комментарии (HTML запрещает вложенные form) — корректное решение реальной проблемы подписки.

## Безопасность / гигиена

Все пользовательские значения (title, description, приоритет, теги, логины, тела комментариев) — `textContent`/`el()`; innerHTML не используется. Логин в addUserRow — `String(login)` через textContent. Секретов нет. Guard от `/api/tasks/null/comments` сохранен (isValidTaskId + понятное сообщение, тест на отсутствие запроса сохранен).

## Прогоны (выполнены оркестратором, не повторялись)

- tests/web: **103 passed, 1 skipped** (skip pre-existing, скоуп API); playwright-flake test_navigation_search_ui изолированно зелёный (3 passed).
- tests/api (scratch, :8091, tmp-БД + migrate_r4): **157 passed, 9 skipped, 2 xfailed** — совпадает с эталоном; дифф backend не задевает (0 файлов).

## Замечания

| # | Файл/место | Серьезность | Замечание | Рекомендация |
|---|---|---|---|---|
| m-1 | frontend/templates/search.html:113 | minor | View-модалка поиска — `<div class="modal task-view">` без `role="dialog"`/`aria-labelledby`, в отличие от доски (board.html:188); крестика с aria-label в поиске нет вовсе (только «Закрыть» — спеке не противоречит, закрытие есть). Асимметрия a11y между двумя одинаковыми окнами. | Добавить `role="dialog" aria-labelledby="task-detail-title"` в search.html:113; можно вместе с задачей 5.1/DEF-005. |
| m-2 | frontend/static/js/search.js:231-248, task-detail.js:55-70 | minor | `addUserRow` + `STATUS_LABELS` продублированы в двух файлах (третьей копией к уже существовавшему дублю рендера комментариев) — при добавлении полей в 5.1 (например, display_name вместо логина) править синхронно в двух местах; рассинхрон даст разный вид карточки на доске и в поиске. | Вынести общий модуль (по образцу tooltip.js из 3.2) в рамках 5.1, когда поля действительно появятся. Сейчас — допустимо (search.js исторически автономен). |
| m-3 | frontend/static/js/board/task-form.js:325-327 | minor | `export function renderComments(list, comments) { renderCommentsInto(list, comments); }` — обертка без добавленной стоимости; достаточно `export { renderCommentsInto as renderComments }` или экспорта самой функции. | Упростить при следующем касании файла. |
| m-4 | frontend/static/js/board/task-form.js:280 | minor | Опечатка в комментарии, внесенная диффом: «молча не применятся» (было «не применится»). | Поправить в следующем коммите задачи 4.2 (тот же файл). |
| m-5 | tests/web/test_view_modal_r4.py | minor | Сценарий 5 «клик вне окна» покрыт косвенно: TC-view-104/105 проверяют Escape и крестик, клик по подложке — только унаследованным обработчиком board-init.js без прямого теста в новом файле. | Добавить TC-view-110 (клик по `.modal-overlay` вне `.modal` → overlay hidden) в 5.1 или при следующем касании. |

## Проверенные Scenario

board ADDED «Просмотр карточки задачи — модальное окно read-only»: сценарий 1 (TC-view-101), сценарий 2 (TC-view-102), сценарий 3 (TC-view-103), сценарий 4 (TC-view-106 + негатив TC-view-107), сценарий 5 (TC-view-104/105; клик-вне — см. m-5). Дополнительно: TC-view-108 (fast), TC-view-109 (регресс BUG-001 из поиска), адаптации regress-путей move/comment (test_board_tasks_ui, test_r3_dnd_ui, test_r3_vis_ui, conftest). Негативные пути (гвард без полей API, guard комментария без задачи) покрыты.

## Что НЕ проверено

- Прогоны не выполнялись этим ревью (запрещены задачей) — числа приняты из /tmp/r4_review/PROGRESS.md; изоляция test_navigation_search_ui подтверждена оркестратором.
- Визуальная часть ОГР-18 «по мокапу» статическим ревью не оценивается (пиксельная сверка — зона design_validator, E13; код дает класс .task-view на токенах V3, что спеке соответствует).
- Поведение Escape при открытом view поверх формы в кастомных последовательностях (Escape нормирован спекой только для view; форма — вне дельты, поведение сохранено прежним).
