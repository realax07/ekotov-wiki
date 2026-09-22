# Impact-анализ: change add-r2-categories-settings

> Роль: QA impact-аналитик (первый боевой запуск роли по H5 — первый пакет с
> MODIFIED-дельтой) | Дата: 2026-09-22 | Режим: auto-edit
> Вход: дельты `openspec/changes/add-r2-categories-settings/specs/` (7 файлов),
> `test-model/regression/manifest.md`, трассировка TC-ID по docstring тестов
> `tests/api/` + `tests/web/`, предыдущий прецедент `test-model/impact/add-suggestions.md`.
>
> **Характер дельты:**
> - MODIFIED — 1 шт.: fastline «Назначение задачи на fast line вручную при
>   создании» (fast ⇒ priority=high автоматически; fast с priority≠high, включая
>   null, — 422; поле приоритета в UI-форме fast-задачи заблокировано).
> - ADDED — categories (справочник + управление), settings (страница, общность,
>   состав), navigation (раздел «Настройки»), tasks (автодополнение тегов, крестик
>   формы, визуал приоритетов/ошибок), search (селект-поля из фактических данных).
> - REMOVED — нет.

## 0. Резюме

**Счет вердиктов: keep — 102, revalidate — 7, retire — 0** (по всему набору:
102 API-теста + 21 web-тест = 123; полный перечень — §1–2). Retire нет:
MODIFIED-дельта ужесточает поведение, не удаляет его. Все revalidate — web-сьюит +
pending_update, исключить из релизного прогона до обновления кейсов (вход в
чеклист qa_checklist).

## 1. MODIFIED fastline — семантическая сверка по тестам

### 1.1 tests/api/test_fastline.py (TC-fast-001…012)

Ни один тест не создает fast-задачу с priority≠high: все API-создания fast —
`create_ok(..., is_fast=True)` без priority (TC-fast-002/009/010/011) или с
неявным null через фикстуру `fast_occupied` (TC-fast-006/007). Прямых конфликтов
с новой валидацией нет.

| Тест | Кейс | Вердикт | Обоснование |
|---|---|---|---|
| `test_second_fast_via_api_409_not_created` | TC-fast-006 | **keep** | 409 «fast line occupied» дельтой не изменен; создание fast без priority → приоритет high → 422-ветка не срабатывает. Тело 409 и «задача не создана» остаются валидными ассертами |
| `test_repeated_fast_requests_409_reproducible` | TC-fast-007 | **keep** | Аналогично TC-fast-006: воспроизводимость 409 не затронута; контроль «активная ровно одна» валиден |
| `test_regular_create_ok_after_fast_rejection` | TC-fast-008 | **keep** | Обычная задача без priority → priority=null остается валидной (ограничение только для fast; сценарий «Обычная задача с любым приоритетом не ограничена») |
| `test_new_fast_after_previous_done` | TC-fast-009 | **keep** | Создание fast без priority после освобождения линии: 201 + is_fast=true валидны; под новой спекой сервер дополнительно ставит priority=high — ассертов, противоречащих этому, нет. Рекомендация (не вердикт): добавить assert `priority == "high"` при обновлении |
| `test_new_fast_after_previous_deleted` | TC-fast-010 | **keep** | Аналогично TC-fast-009 (удаление освобождает линию — поведение не менялось); та же рекомендация по ассерту приоритета |
| `test_regular_tasks_do_not_block_fast_line` | TC-fast-011 | **keep** | Обычные задачи (todo/in_progress) не блокируют fast line — дельтой не затронуто |
| `test_fast_line_no_autoassign_on_move_or_patch` | TC-fast-004 | **keep** | «Система MUST НЕ назначать на fast line автоматически» сохранено в новой редакции; PATCH priority=high у обычной задачи легален (ограничение — только fast) |
| `test_regular_task_without_fast_flag` | TC-fast-003 | **keep** | Обычная задача без fast: is_fast=false — без изменений |
| `test_fast_create_is_fast_true_todo` | TC-fast-002 | **keep** | Создание fast без priority: is_fast=true, status=todo, на линии — валидно; приоритет тест не ассертит. Рекомендация: дополнить ассертом `priority == "high"` (новое контрактное поведение) |
| `test_fast_line_visual_highlight` | TC-fast-001 (UI-stub) | **keep** | Skip-заглушка скоупа tests/web; подсветка линии дельтой не изменена |
| `test_fast_task_visual_priority` | TC-fast-012 (UI-stub) | **keep** | Skip-заглушка; «fast независимо от priority обычных» сохранено. Примечание: при реализации визуала приоритетов (tasks-дельта FR-28/29) заглушку реализовывать совместно с новыми UI-кейсам приоритетов |

**Итог по test_fastline.py: 11/11 keep.** Набор не проверяет ни одного
отклоняемого комбинации — ложного пожара от ужесточения не будет. Но набор и НЕ
покрывает новое негативное поведение (см. §3, п.1) — это требование на новые
TC, не revalidate.

### 1.2 tests/web — тесты, проводящие fast-задачи через UI-форму

Форма создания — прямой носитель измененного поведения (поле приоритета
заблокировано и показывает high при отмеченном fast line).

| Тест | Файл | Кейс | Вердикт | Обоснование |
|---|---|---|---|---|
| `test_fast_task_create_and_highlight` | tests/web/test_fastline_ui.py | TC-UI-010 | **keep** | Создает fast с `priority="high"` ДО отметки fast line (порядок в helper `create_task_via_ui`: select_option → check) — заблокированное поле не мешает; предмет теста (подсветка has-fast/task-card-fast, первая карточка) дельтой не изменен. Наблюдение: если реализация при отметке fast сбрасывает/блокирует поле иначе — helper переиспользуется многими тестами; при падении на select_option пересмотреть вердикт |
| `test_second_fast_task_rejected` | tests/web/test_fastline_ui.py | TC-UI-011 | **revalidate** (pending_update) | Отмечает fast line БЕЗ выбора приоритета и ждет 409 «fast line занята». Поведение формы изменилось: поле приоритета блокируется с high; если реализация шлет priority=null/пусто и сервер отвечает 422 по новой валидации — тест упадет до 409. Зависит от нереализованной механики формы → сомнение → безопасный дефолт revalidate |
| `test_final_path_autoarchive_and_fast_release` | tests/web/test_navigation_search_ui.py | TC-UI-018 | **revalidate** (pending_update) | Три создания fast через UI без выбора приоритета («Fast-первая», «Fast-финал», «Fast-новая») — та же зависимость от новой механики блокировки поля; шаги 7–8 ждут 201 и «fast line занята» = 0. Проверить после реализации формы |

## 2. ADDED-дельты — существующие тесты затронутых областей

### 2.1 Справочник категорий → поле категории становится выбором из списка

Ключевое следствие: все места ввода категории (форма задачи, фильтр-конструктор)
из input/datalist становятся select из справочника (categories: «поле … MUST
работать как выбор из списка значений справочника»; search: селект-поля из
фактических данных). Плюс серверная жесткая валидация категории (tasks: «отклонение
по жесткой валидации», FR-21) — задачи с категорией вне справочника отклоняются.

| Тест | Файл | Кейс | Вердикт | Обоснование |
|---|---|---|---|---|
| `test_tag_hints_datalist_bound_and_filled` | tests/web/test_search_suggestions_ui.py | TC-UI-SUGG-001 | **revalidate** (pending_update) | Ассерт `#search-category` имеет атрибут `list="tag-hints"` (строки 58–61) — при превращении поля категории в select атрибута list не будет: тест падает. Вход от ревью подтвержден кодом. Требование кейсу: категория — select из справочника, теги — datalist; проверку разделить по полям |
| `test_tag_hints_set_semantics_and_order` | tests/web/test_search_suggestions_ui.py | TC-UI-SUGG-002 | **revalidate** (pending_update) | Создает задачу с категорией `QAT-UI-Общее` вне справочника (без seed → 422 на setup) и ожидает категорию в datalist подсказок. Источник категории для подсказок после внедрения справочника спекой прямо не определен (search-дельта: «для категории — справочник», подсказки тегов — из задач). Двойное сомнение (среда + источник) → revalidate |
| `test_free_input_does_not_change_suggestions_source` | tests/web/test_search_suggestions_ui.py | TC-sugg-007 | **revalidate** (pending_update) | Свободный ввод в поле «Категория» фильтра с ожиданием, что ввод принят (строки 143–148). Новая спека прямо запрещает произвольный текст в поле категории («не допускает ввод произвольного текста») — семантический конфликт со сценарием 7 старой спеки для категории. Часть про «Теги» остается валидной; кейс требует расщепления: теги — keep-семантика, категория — новая (select, свободный ввод невозможен) |
| `test_all_attributes_create_view_edit` | tests/web/test_board_tasks_ui.py | TC-UI-009 | **revalidate** (pending_update) | Вход от ревью подтвержден кодом: (а) ассерты текста приоритета `get_by_text("high"/"medium", exact=True)` в карточке и бейджа на карточке доски (строки 145–169) — с бейджами «Высокий/Средний» падают; (б) `get_by_label("Категория").fill("Работа")` (строка 152) — при select вместо input падает. Требование кейсу: локализованные бейджи приоритетов (FR-28/29) + выбор категории из справочника |
| `test_search_archived_task_builder_advanced_card` | tests/web/test_navigation_search_ui.py | TC-UI-017 | **revalidate** (pending_update) | `page.get_by_label("Категория").fill("Дом")` на фильтре-конструкторе (строка 104) — при select-поле категории fill() падает; плюс задача с категорией «Дом» требует seed справочника. Шаги advanced/архива не затронуты — обновить только способ ввода категории |
| `test_create_task_title_only` | tests/web/test_board_tasks_ui.py | TC-UI-007 | **keep** | Признаки пустые; ассерт отсутствия текстов «Описание/Приоритет/Категория…» не зависит от типа поля категории |
| `test_modals_hidden_on_board_load` | tests/web/test_board_tasks_ui.py | TC-UI-006 | **keep** | REGRESSION-маркер 2026-09-19(a); модалки и перекрытие не затронуты дельтой |
| `test_create_task_without_title_rejected` | tests/web/test_board_tasks_ui.py | TC-UI-008 | **keep** | required-валидация названия; POST не уходит — категория не участвует |
| `test_move_between_columns_and_quick_done` | tests/web/test_board_tasks_ui.py | TC-UI-012 | **keep** | Перемещения по столбцам, признаков нет |
| `test_move_without_selected_card_no_request` | tests/web/test_board_tasks_ui.py | TC-UI-013 | **keep** | REGRESSION 2026-09-19(c); guard move — вне зоны дельты |
| `test_add_comment_persists` | tests/web/test_board_tasks_ui.py | TC-UI-014 | **keep** | Комментарии; priority="high" задается select_option у обычной задачи — легально |
| `test_comment_submit_without_card_no_request` | tests/web/test_board_tasks_ui.py | TC-UI-015 | **keep** | REGRESSION 2026-09-19(b); guard комментариев — вне зоны дельты |
| `test_sidebar_all_pages_and_wiki_stub` | tests/web/test_navigation_search_ui.py | TC-UI-016 | **keep** | Ассерты существования ссылок Доска/Поиск/Wiki; добавление раздела «Настройки» существованию не противоречит (появление раздела — новое тестовое требование, §3 п.4) |
| `test_search_page_*`, `test_filter_*`, `test_switch_builder_*` (весь test_search.py) | tests/api/test_search.py | TC-search-001…011 | **keep** | `GET /api/search` дельтой не изменяется (search-дельта — только селект-поля UI из данных). Фильтр category как параметр API остается. СРЕДА: фикстура `search_fixtures` создает категории «Дом»/«Работа» — см. §4 |
| `test_archived_task_found_by_search_card_opens` | tests/api/test_archive.py | TC-arch-008 | **keep** | Чтение признаков архивной задачи; категория «Дом» — seed-зависимость (§4), семантика не изменилась. Остальные TC-arch-001…007/009 категорий/fast не касаются — keep |
| весь test_board.py | tests/api/test_board.py | TC-board-001…010 | **keep** | Столбцы/move/404 — дельтой не затронуты (priority=high только в 404-патче TC-board-010, легален) |
| весь test_auth.py | tests/api/test_auth.py | TC-auth-001…018 (18 тестов) | **keep** | Сессии/вход — вне зоны. Негатив «настройки без сессии → редирект» — НОВОЕ покрытие (§3 п.3), не изменение существующего |
| весь test_navigation.py | tests/api/test_navigation.py | TC-nav-001…005 | **keep** | Существующие разделы сайдбара сохраняются; «Настройки» — добавление (§3 п.4) |
| весь test_suggestions.py + test_suggestions_gap.py | tests/api | TC-API-SUGG-001…005, TC-sugg-006/008/009 (8 тестов) | **keep** | Дельта не содержит MODIFIED Requirement домена suggestions; подсказки тегов остаются из значений задач. Эскалация-наблюдение для ПМ: если при реализации /api/suggestions переведут категории на справочник — эти тесты потребуют внепланового revalidate (сейчас оснований по спеке нет) |
| весь test_tasks.py | tests/api/test_tasks.py | TC-tasks-001…016 | **keep** | Приоритеты у обычных задач (high/medium/low→medium, null-дефолты) ограничение fast не задевают; is_fast=false-ассерты валидны. Категории «Дом/Работа/Личное» — seed-зависимость (§4), семантика кейсов не изменилась. TC-tasks-015/016 — ручные НФТ-процедуры, skip |
| весь test_auth_ui.py | tests/web/test_auth_ui.py | — | **keep** | Вход/выход UI — вне зоны дельты |

## 3. Новые тестовые требования дельты (вход для qa_checklist)

1. **fastline MODIFIED (FR-27, ОГР-10) — приоритет, новые негативы:**
   - API: fast + priority=low → 422; fast + priority=medium → 422; fast + priority=null → 422; fast-задача не создана (ни один существующий TC этого не покрывает).
   - API: fast без priority (поле не передано) → 201, priority="high" автоматически; дополнить ассертом TC-fast-002/009/010 (см. §1.1).
   - API: обычная задача + priority=low → 201 (ограничение только fast; частично прикрыто TC-fast-003/008 без priority — нужен явный low).
   - UI: поле приоритета в форме показывает «высокий» и заблокировано при отмеченном fast line (сценарий «Поле приоритета заблокировано»); разблокировка через клиент не меняет исход (серверная валидация).
2. **fastline: миграция существующих fast-задач** (сценарий «приводятся в соответствие») — разовая проверка внедрения, метка `candidate-archive` по правилам манифеста.
3. **categories:** выбор категории только из справочника (форма/фильтр/редактирование); негатив — значение вне справочника недоступно; создание категории в настройках; переименование с каскадом на все задачи; негатив — удаление используемой блокируется; удаление неиспользуемой.
4. **navigation:** раздел «Настройки» в сайдбаре внизу слева рядом с выходом; доступен со всех страниц; переход открывает настройки (в существующий TC-UI-016/TC-nav — не вмешиваться, новые TC).
5. **settings:** страница настроек авторизованным; негатив — без сессии редирект на вход; общность настроек для обоих пользователей (изменение одного видно другому; второй может менять; справочник един); состав — только категории (Won't: теги/профиль/пароль отсутствуют).
6. **tasks:** автодополнение тегов в форме задачи (подсказки/set-семантика/выбор/новое значение/негатив 401); крестик закрытия формы; визуал приоритетов цветом+иконкой (inline SVG) в форме и на карточке; подсветка невалидной категории; анимация формы.
7. **search:** селект-поля категории (форма + фильтр) заполняются из фактических данных/справочника; изменение данных отражается; негатив — статические/пустые списки (DEF-001).

## 4. Средовые требования прогона

1. **Seed справочника категорий — обязателен до любого прогона** (API и web):
   серверная жесткая валидация категории (FR-21) отклоняет задачи с категорией
   вне справочника, а фикстуры существующих тестов создают задачи с категориями:
   - `Дом`, `Работа`, `Личное` — test_tasks (TC-002/005/006), test_search
     (`search_fixtures`), test_archive (TC-arch-008), web TC-UI-009/TC-UI-017;
   - `QAT-*` — test_suggestions.py (`QAT-Категория-1`, `QAT-Общее`, `QAT-якорь`,
     `QAT-Кат-А/Б`), test_suggestions_gap.py (`QAT-SUGG-Кат-А`, `QAT-SUGG9-Кат`),
     test_search_suggestions_ui.py (`QAT-UI-Категория`, `QAT-UI-Общее`).
   Требование: seed-фикстура (conftest, session-scope) создает в справочнике
   `Дом`, `Работа`, `Личное` + соглашение об автосоздании категорий с префиксом
   `QAT-` (или расширяемый seed-список). Без seed падает setup 8+ тестов в 5
   файлах — это средовые отказы, не дефекты продукта.
2. **Изоляция справочника:** справочник общесистемный (FR-24) — тесты,
   переименовывающие/удаляющие категории, должны работать только с QAT-* или
   восстанавливать состояние; cleanup задач (существующий) категории из
   справочника не убирает — нужен cleanup категорий в фикстуре.
3. **Прецедент порядка валидации fast:** для web-кейсов TC-UI-011/018 — при
   реализации формы убедиться, что отмеченный fast line подставляет priority=high
   (иначе 422 до 409); зафиксировать ожидаемый порядок проверки (409 fast line
   vs 422 приоритет) для новых негативных TC — вопрос к dev/sdd, не к спеке.

## 5. Эскалации для ПМ (не решаются аналитиком)

1. **Расхождение в дельте fastline:** текст сценария «Негативный: … с приоритетом
   "low" (или "medium", **или NULL**) → 422» против входа оркестратора «fast без
   priority → high». Читается как: явный `priority=null` → 422, отсутствие поля →
   автоподстановка high. Требует фиксации в sdd/tasks до написания новых TC
   (иначе новый негативный TC на null невоспроизводим).
2. **Источник категории в /api/suggestions** после внедрения справочника
   не определен дельтой (значения задач vs справочник) — влияет на
   TC-API-SUGG/TC-UI-SUGG (сейчас keep по отсутствию MODIFIED-дельты домена).
3. **TC-sugg-007 vs новая спека категорий:** сценарий 7 спеки add-suggestions
   (свободный ввод легитимен) для поля категории противоречит новой спеке
   справочника. Конфликт спек разных пакетов — решение ПМ/Заказчика (вероятно:
   сценарий 7 сужается до поля «Теги»).

## 6. Итог

| Вердикт | Кол-во | Тесты |
|---|---|---|
| **keep** | 102 | tests/api — 88 тестов (test_fastline 11, test_tasks 16, test_search 11, test_board 10, test_archive 9, test_auth 18, test_navigation 5, test_suggestions 5, test_suggestions_gap 3 — свернуто по файлам в §1–2) + tests/web — 14 (TC-UI-006/007/008/012/013/014/015 из test_board_tasks_ui, TC-UI-010 из test_fastline_ui, TC-UI-016 из test_navigation_search_ui, test_auth_ui 5; всего web 21 − 7 revalidate = 14) |
| **revalidate** (pending_update, вне релизного прогона до обновления) | 7 | TC-UI-SUGG-001, TC-UI-SUGG-002, TC-sugg-007 (test_search_suggestions_ui.py); TC-UI-009 (test_board_tasks_ui.py); TC-UI-011 (test_fastline_ui.py); TC-UI-017, TC-UI-018 (test_navigation_search_ui.py) |
| **retire** | 0 | — |

Требования «обновить кейс X» по всем 7 revalidate — передать в чеклист
qa_checklist; обновление тестов — qa_automation через qa_case_reviewer (G8).
