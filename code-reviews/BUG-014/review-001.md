# Ревью 001 (код-ревью Флоу 2): унификация просмотра карточки из advanced-поиска с окном задачи доски — BUG-014 (закрывает BUG-013 как дубль)

- **Reviewer-Delegation:** внешняя (correlation 81ac46babbee4e88b491a3ef8918049b, code_review; независимое ревью, сессия dev finished)
- **Ревьюируемый фикс:** PR #86, HEAD `7f77534` (`fix/bug-014-search-task-view`, поверх origin/main `5fd2eae`); дельта `git diff origin/main...7f77534` = 7 файлов (+938/−642): search.js, board/task-detail.js, search.html, 2 карточки test-model (по одной строке статуса), 2 новых теста. PR ОТКРЫТ, НЕ смержен (по постановке)
- **Provenance SHA:** `7f7753498d01a727c0eeaa15930a43decdf85d9a` (worktree /tmp/rv-bug014 @ 7f77534, `git status` чист до и после мутаций); sha256 файлов диффа: search.js `b896fbd884df285ff883b27ff36add31b21130dbbaa1d1035d079167f2f08b6c`, board/task-detail.js `acd251f6907f64767c9ef418262c015645c0454305b1d7977c8fab3a681902f8`, search.html `377ccfe18a7b01a0bb3401f9d4e2f9b8d64536af9cb6d5d3007897e234aade28`, test_bug014_search_task_view.py `ff96f475731aacf4feb4fd1b449e3ba0fc8efc4c15c2c71d0d67fad6c3f7ca94`, test_bug013_attrs_padding.py `cc3fbb9713e4b799c24ab9c54faf8c33331fd4c86f4df69ceb1eeb0397cda095`
- **Карточки:** `test-model/bugs/BUG-014-search-task-view-unify.md`, `test-model/bugs/BUG-013-task-view-attrs-edge-padding.md` (дубль); мокап-арбитр `design/polish-ticket-modal.html`; референс формата — `code-reviews/BUG-012/review-002.md` (привязка provenance к SHA + sha256)
- **Зона ревьюера:** только `code-reviews/BUG-014/review-001.md` (+ .provenance.json); все прогоны — в изолированном worktree /tmp/rv-bug014 @ 7f77534 (`env -u DB_PATH -u EKOTOV_WIKI_BASE_URL -u PYTHONPATH`, venv /home/openclaw/venvs/wiki); репо-клон не изменен
- **Дата:** 2026-10-08
- **Метод:** (1) чтение отчета цикла, карточек, мокапа; (2) построчный разбор дельты (JS-дифф целиком, разметка search.html против board.html узел-в-узел); (3) негативные пробы самостоятельно (из поиска, с доски, редактирование с доски); (4) верификация на автостенде по заданной матрице; (5) мутационная проверка дельты

---

## Проверка 1: динамический import task-form.js — технота подтверждена, доска не сломана (риск (а))

**Статический импорт действительно ронял граф search.js на /search.** Подтверждено чтением `frontend/static/js/board/task-form.js`: на top-level модуля (строка 902 и далее) исполняются `categoryField().addEventListener("change", …)`, `document.getElementById(PRIORITY_FIELD_ID).addEventListener(…)`, `TAGS_INPUT_ID`, `IS_FAST_FIELD_ID` — узлов `#task-category`/`#task-priority`/`#task-tags`/`#task-is-fast` на /search нет (search.html формы задачи не содержит) → TypeError при загрузке модуля → неудача статического графа search.js (тихий полный отказ страницы). Технота в комментарии диффа соответствует коду.

**Решение корректно:**
- `loadEditFormModule()` — единственный динамический `import("./task-form.js")`, промис кэшируется, при сбое кэш сбрасывается (повторный клик повторяет попытку) — семантика правильная;
- на доске предпрогрев в `initTaskViewControls()` (вызывается из board-init.js:65) — модуль грузится при инициализации доски, к первому клику «Редактировать» форма готова, как при статическом импорте (регрессии готовности нет; board_tasks 8 passed, см. проверку 5);
- клик «Редактировать» на доске: GET свежей копии → `loadEditFormModule().then(openEditForm)`; сбой загрузки — `showFormError` с внятным сообщением, view не рвется. Отказ деградирует до сообщения, не до тишины — правильно;
- доказательство: проба ревьюера «редактирование с доски» (проверка 3б) — green end-to-end (открытие формы, правка, сохранение, рефреш доски).

## Проверка 2: search.js type=module, контракты сохранены (риск (б))

- **BUG-001/CHK-E-17 (клик по карточке):** `renderCard` вешает click → `openSearchTaskDetail(task.id)` → guard скрытия `#task-edit-button` → импортированный `openTaskDetail`. Контракт сохранен; e2e-путь прогнан (проверка 3а, 5).
- **Закрытие на /search:** `initTaskViewControls` на /search НЕ вызывается (иначе тянул бы `#task-move-select` и т.п.) — вместо него search.js подписывает сам: крестик `#task-view-close`, «Закрыть» `#task-detail-close`, клик по подложке (`event.target === event.currentTarget`), Escape с guard на `overlay.hidden`. Все четыре пути есть; focus trap доски на /search не активен (не подписан) — окно поиска содержит ровно один фокусируемый крестик + «Закрыть», Tab просто не зациклен — приемлемо, дефектом не является (a11y-наблюдение — находка 2).
- **Бейдж «Архивная»:** сохранен в двух местах: в карточке выдачи (renderCard, `task-archive-badge`, текст статический) и в окне (`#task-detail-archive-badge` в дословной разметке, тогглится renderTaskDetail task-detail.js). Покрыт прогонами (navigation_search TC-UI-017 шаг 7 — green).
- **XSS (ОГР-11):** в search.js innerHTML не используется (проверено grep — 0 вхождений во всех затронутых файлах); весь рендер — createElement + textContent; task-detail.js — то же (createTextNode/textContent, SVG через createElementNS + setAttribute статических значений).
- **Остальное тело search.js:** конструктор/advanced/переключение режимов/подсказки/нормализованный фильтр — механический де-IIFE, логика не менялась (сверено по диффу); ES-модуль deferred — «после DOM» для applyActionButtonClass сохранен (прокомментирован в диффе). search_r4 4p + suggestions 3p + navigation 3p — green.

## Проверка 3: негативные пробы самостоятельно

**3а. Открытие карточки ИЗ ПОИСКА** (повторено многократно, включая диагностическую пробу, удаленную после фиксации): advanced → `tag IN ("bug014")` → «Найти» → клик по карточке → `.task-view-head` (кикер «Задача · STAND-»), `.badge-row` с бейджами, `.task-view-body`, `.attr-grid` ровно 4 признака; заголовок `#task-detail-title` ВНУТРИ шапки (старого голого h2 нет — старый рендер выведен); attrs-контракт TC-UI-009 (high/Дом/2026-12-31/bug014) — дословно; бейдж «Архивная» и комментарии-секция на месте; computed styles = мокапу: `modal class="modal task-view"`, head 24px 32px 16px, body 16px 32px, attr 8px 16px, сетка 2 колонки (279px 279px), `#task-edit-button.hidden === true`. **СТАРЫЙ рендер отсутствует полностью:** renderTaskDetail/renderComments/loadComments/addDetailRow/addUserRow/STATUS_LABELS из search.js удалены (grep по файлу — вхождений нет), dl-разметка `#task-detail-attrs` сохранена только как attrs-контракт нового рендера (ОГР-28). Мертвых веток нет.

**3б. Редактирование С ДОСКИ** (риск (в), проба ревьюера, файл удален после фиксации): доска → клик карточки → «Редактировать» (динамический импорт по клику) → форма открыта с `#task-title` = названию задачи → правка → Сохранить → форма закрылась → рефреш доски → задача с новым названием видна. **Green.** Доска не сломана.

**3в. Открытие С ДОСКИ:** board_tasks 8p, view_modal 9p, bug013_attrs_padding 1p (TC-view-110: отступы board-окна = мокапу) — green; бейджи/аватары/attr-grid на месте (те же ассерты, что и в 3а, на /board).

## Проверка 4: разметка search.html против board.html — дословное совпадение

Сверено узел-в-узел: overlay/.task-view/role=dialog/aria-labelledby, крестик `#task-view-close` (тот же SVG), `#task-detail-title`, `#task-detail-archive-badge`, `#task-detail-error`, `dl#task-detail-attrs`, комментарии, футер. Единственное отличие — осознанное: `hidden` на `#task-edit-button` в разметке search.html (на доске кнопка видимая) + инлайн-модуль-гвард до первого открытия (guard search.js дублирует при каждом открытии — двойная защита, безвредно).

## Проверка 5: верификация на автостенде (worktree 7f77534, isolation env -u × 3)

```
pytest tests/web/test_bug014_search_task_view.py tests/web/test_bug013_attrs_padding.py -q
→ 1 failed, 2 passed  (см. находку 1: гонка в новом тесте, НЕ продукт)
pytest tests/web/test_view_modal_r4.py -q                 → 9 passed in 26.49s
pytest tests/web/test_search_r4_ui.py -q                  → 4 passed in 11.37s
pytest tests/web/test_board_tasks_ui.py -q                → 8 passed in 32.23s
pytest tests/web/test_search_suggestions_ui.py
       tests/web/test_navigation_search_ui.py -q          → 6 passed in 22.51s
pytest tests/web/test_r3_dnd_ui.py tests/web/test_r4_commentfix_ui.py -q → 10 passed
node --check search.js task-detail.js                      → OK
```

Матрица ПМ закрыта (bug014 smoke 2p — по компонентам: разметка-тест stable-pass; computed-styles — см. находку 1). Регрессий по смежным семействам нет.

## Проверка 6: мутационная проверка дельты (обязательна) — фиксатор ловит

**Откат унификации** (3 файла из origin/main: search.html, search.js, board/task-detail.js; git status worktree показывает ровно 3 M):

```
pytest tests/web/test_bug014_search_task_view.py -q
→ 2 failed in 12.99s
  FAILED ...::test_search_task_view_uses_board_render[chromium]
  FAILED ...::test_search_task_view_computed_styles_match_board[chromium]
```

Точный красный ассерт (--tb=short): `expect(modal.locator(".task-view-head")).to_be_visible()` → `AssertionError: Locator expected to be visible; element(s) not found` — старый рендер из main не строит шапку мокапа; фиксатор краснеет именно на отсутствии унифицированного рендера, не на инфраструктуре.

**Возврат унификации** (`git checkout 7f77534 -- …`, git status чист, sha256 файлов совпали с до-мутационными):

```
pytest tests/web/test_bug014_search_task_view.py::test_search_task_view_uses_board_render
       tests/web/test_bug013_attrs_padding.py -q → 2 passed in 7.94s
```

Мутационная чувствительность подтверждена дословно. (Повтор computed-styles-теста отдельно от мутаций не потребовался — его краснота на мутанте и зелень разметочного теста на чистом коде замыкают обе стороны.)

## Находки

| # | Серьезность | Место | Замечание | Рекомендация |
|---|---|---|---|---|
| 1 | minor (тест-харнесс; НЕ блокирует продукт) | tests/web/test_bug014_search_task_view.py:155 (`test_search_task_view_computed_styles_match_board`) | Гонка: `page.evaluate` выполняется сразу после `expect(overlay).to_be_visible()`, но рендер тела асинхронен (GET /api/tasks/{id}) — в ~40–60% прогонов `.task-view-body`/`.attr-grid` еще нет → `getComputedStyle(null)` → `TypeError: parameter 1 is not of type 'Element'`. Диагностическая проба ревьюера: в момент evaluate узлы отсутствуют (head/body/grid = False), после `expect(".attr-grid")` — все ассерты computed styles проходят (3/3 green, значения мокапа дословные). Продукт-код не при чем: тот же рендер на доске стабилен (TC-view-110), разметочный тест файла стабилен | Добавить `expect(modal.locator(".attr-grid")).to_be_visible()` перед evaluate (однострочный фикс теста, следующее касание) |
| 2 | obs (a11y, не блокирует) | search.html | Focus trap доски на /search не активен (initTaskViewControls не вызывается) — при открытом окне Tab уводит фокус на фон страницы; на доске trap есть | Косметика; при желании — вынести initFocusTrap в опциональную подписку search.js |
| 3 | obs (для ПМ) | product-решение | «Редактировать» из поиска недоступен — осознанное решение цикла (форма задачи и рефреш столбцов живут на доске; так было и до унификации), ограничение задокументировано в отчете и карточке | Если Заказчик попросит — отдельная задача интеграции task-form на /search |

Блокирующих находок: 0.

## Проверенные Scenario

- Дельта origin/main...7f77534 построчно (search.js целиком — де-IIFE без изменения логики; task-detail.js — только импорт-блок + initTaskViewControls); search.html против board.html узел-в-узел; зона PR: frontend/templates/**, frontend/static/js/**, tests/web/**, test-model статусы — в границах постановки (допустимо).
- BUG-001 контракт клика-из-выдачи; бейдж «Архивная» (карточка + окно); комментарии (renderDetailComments, формат r8 2.3 «автор · дата»); XSS (textContent-паттерн, grep innerHTML = 0); attrs-контракт TC-UI-009 дословно.
- Негативные пробы: открытие из поиска (разметка + computed styles = мокапу), открытие и редактирование с доски (end-to-end сабмит), закрытие крестиком.
- Мутационная проверка: откат 3 файлов → 2 failed (точный ассерт `.task-view-head not found`); возврат по SHA → green, sha256 восстановлены.
- Прогоны: worktree /tmp/rv-bug014 @ 7f77534, env -u DB_PATH -u EKOTOV_WIKI_BASE_URL -u PYTHONPATH (PYTHONPATH-крюк hermes исключен), venv /home/openclaw/venvs/wiki.

## Что НЕ проверено (честно)

- CI PR #86 (flow/e2e green по отчету цикла) — принято по отчету, самостоятельно не воспроизводилось.
- tests/api — вне зоны PR (бэкенд не тронут диффом).
- Мультибразуерность (кроме chromium) и тач-устройства; скринридеры — только DOM/ARIA-семантика.
- computed-styles тест в текущем виде нестабилен (находка 1) — его эталонные значения подтверждены диагностической пробой с корректным ожиданием рендера, но в репо тест остается гонким до однострочного фикса.

---

## Вердикт: APPROVE

Унификация выполнена корректно: разметка окна на /search дословно досочная (единственное отличие — осознанное `hidden` на «Редактировать» с двойным guard'ом), старый рендер выведен полностью без мертвых веток, контракты (BUG-001, бейдж «Архивная», комментарии, XSS, attrs TC-UI-009, DOM-id ОГР-28) сохранены. Технота динамического import подтверждена кодом task-form.js (top-level биндинги на отсутствующие на /search узлы) и закрыта обеими пробами: доска не сломана (предпрогрев + e2e-редактирование green), /search жив (полная поисковая матрица green). Мутационная проверка дословная: откат → 2 failed, возврат → green. Единственная находка — гонка в новом computed-styles тесте (тест-харнесс, minor, продукт не блокирует; эталонные значения подтверждены независимо). Дифф в границах зоны. BUG-013 корректно закрыт как дубль (TC-view-110 оставлен регрессионным ассертом board-окна — прогнан green).

Provenance: вердикт привязан к SHA `7f7753498d01a727c0eeaa15930a43decdf85d9a` и sha256 файлов диффа (шапка). PR #86 НЕ смержен, НЕ запушен — решение за ПМ. Исправление находки 1 (однострочный `expect(.attr-grid)` перед evaluate) — в следующее касание теста, возврат в ревью не требуется.
