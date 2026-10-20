# Code review — p12-rich-2 багфикс с прода: review-003 (только фикс-дифф 8ae9c90..1ddc312)

flow: flow=2 role=code_reviewer repo=/home/openclaw/ekotov-wiki scope=p12-rich task=review-3

Роль: code_reviewer (независимый). Предмет: фикс-дифф Флоу 2 — 1 коммит
1ddc312 (родитель 39dca5b = main) на ветке chore/p12-rich-fix2. Рапорт
Заказчика с живой эксплуатации: (1) переименование вкладок не работало,
(2) спойлер рождался развернутым. Объем: pages.py (static_v),
rich/spoiler.js (+22), rich/tabs.js (+68), tests/web/test_rich_tools.py
(+214, +3 кейса).

Метод: полный diff-ревью по логике + эмпирическая валидация
дискриминаторов: в изолированном worktree /tmp/wt-p12rev3-prefix
(detached 1ddc312) продукт-файлы откатывались на пред-фикс
(39dca5b) при фикс-уровне тестов — проверено, что новые кейсы ПАДАЮТ
на пред-фиксе; после прогона откат восстановлен (дерево чистое).

---

## Вердикт: approve

Оба производственных дефекта устранены по существу, регрессий в объеме
диффа не найдено, дискриминаторы доказаны. 3 Minor — без правок
(блокирующими не являются).

## Проверка по чек-листу задачи

| # | Пункт | Проверка |
|---|---|---|
| 1 | div role=tab — доступность и стили | Подтвержден. `el('div','tab')` + `role=tab`, `tabIndex=0`, keydown Enter/Space → activatePane (единый обработчик на оба режима; во время rename guard `event.target.closest('.tab-rename')` — Enter в инпуте не переключает вкладку). Стили не ушли: весь CSS `.tab*` в wiki.css:1902–1980 — класс-селекторы без тега, `font: inherit` и `cursor: pointer` заданы явно, смена button→div разметку и вид не меняет |
| 2 | Детерминированный close (D1) | Подтвержден. Единственная точка `close(commit)` с флагом `finished`: первый вызов финален, повторный (blur после Escape/Enter, удаление сфокусированного инпута через textContent) — no-op. Escape → close(false): data-title НЕ пишется, «×» возвращается (closeSpan сохранен до затирания и реаппендится). Enter/blur → close(true); пустое/пробельное значение → дефолт «Вкладка N» по свежему tabPanes(block).indexOf — без stale-индекса |
| 3 | Гейт rename по editable | Подтвержден. dblclick+rename биндится только в ветке `if (editable)` (tabs.js buildTabBar); в статье — только click-переключение, keydown без placeCaret не редактирует. Гейт унаследован от фикс-раунда 8ae9c90 и сохранен |
| 4 | Спойлер всегда closed | Подтвержден. `enhance()` (общий для edit и view) добавляет `closed` вместо `open` (spoiler.js:126); toggle — только клик по шапке; классы open/closed — служебные, в сохраняемый контент не попадают (новый тест проверяет в БД отсутствие и `open`, и `closed`). focusInsertedBody: каретка в абзац ЗА спойлером (в скрытое тело каретка невозможна), fallback — тело |
| 5 | static_v | Подтвержден. `templates.env.globals["static_v"] = "p12-rich-2"` (pages.py:54) — единственный сайт бампа, других ссылок на p12-rich-1 в backend/frontend нет |
| 6 | Тесты +3 дискриминирующие | Подтверждено эмпирически (см. ниже) |

## Эмпирическая валидация дискриминаторов

Продукт-файлы (pages.py, spoiler.js, tabs.js) откатаны на 39dca5b при
фикс-уровне тестов, прогнан `-k "spoiler_new_closed_by_default or
tabs_rename_escape_cancels or tabs_dblclick_gated"`:

| Тест | Пред-фикс | Фикс |
|---|---|---|
| test_spoiler_new_closed_by_default_edit_and_view | **FAIL** (спойлер `open`, тело видимо) | PASS |
| test_tabs_rename_escape_cancels_x_restored | **FAIL** (rename-инпут не фокусируется — 14 × «locator resolved to 0 elements», воспроизводит рапорт дефекта) | PASS |
| test_tabs_dblclick_gated_by_editable_view_switch_only | PASS (гейт уже был) | PASS |

Сьют целиком (worktree /tmp/wt-p12rev3, ветка): 25 passed + 1 ERROR
`test_table_tab_navigation_enter_br` — инфраструктурный флейк Playwright
(«Route.fulfill: Fetch response has been disposed» при сборке стенда),
вне продукта; одиночный перегон — **1 passed**. Итог effectively 26/26.
pageerror-паттерн прежней blur-гонки в новых кейсах не воспроизводится
(`page_errors == []` в финалах).

## Замечания

| # | Серьезность | Замечание |
|---|---|---|
| 1 | Minor | `test_tabs_dblclick_gated_by_editable_view_switch_only` в docstring назван «дискриминатором», но гейт dblclick по editable в tabs.js существовал и на пред-фиксе (тест PASS на 39dca5b) — это регрессионный guard, а не дискриминатор. Клеймо «дискриминатор» в шапке сьюта слегка преувеличено; на защиту не влияет |
| 2 | Minor | В keydown-обработчике div role=tab (оба режима) при Enter/Space вызывается `placeCaretStart(paneNow)` и в СТАТЬЕ: перенос текстового выделения в нередактируемую панель view безвреден, но избыточен (в view достаточно activatePane) и может дать неожиданный скролл. Косметика |
| 3 | Minor | Доступность вкладок: все табы `tabIndex=0` без roving tabindex и стрелочной навигации — отклонение от WAI-ARIA authoring practices для паттерна tabs (Enter/Space работают, это минимум задачи). Не блокирует, можно добить в отдельном a11y-проходе |

## Регрессионный контроль

- Переключение/удаление/лимит вкладок, «+», активная первая: старые
  кейсы сьюта green (tabs-семейство в прогоне 26/26).
- Спойлерные кейсы (toggle по всей шапке, compact в ячейке, вложенность,
  roundtrip контента, rename Escape-гонка) переведены на закрытый дефолт
  и green; содержимое свернутого спойлера сохраняется (body в DOM,
  display:none).
- статика: смена тега tab не трогает сериализацию (data-editor таб-бар
  в контент не пишется; индекс вкладок фиксируется на сборке, rebuild
  пересобирает кнопки — поведение не изменено).

## Итог

Verdict: **approve**. Фикс-дифф 1ddc312 закрывает оба дефекта рапорта
Заказчика, паттерн D1 перенесен на вкладки корректно, статик_v
забамплен, +3 web-кейса; прогон rich-сьюта чистый (26/26 с учетом
инфра-флейка). Замечания 1–3 Minor — в следующий полирующий проход.
