# Автотесты add-kanban-core (tests/)

pytest + requests набор по 80 approved-кейсам `test-model/approved/add-kanban-core/`
(7 файлов кейсов: auth 17, board 10, fastline 12, tasks 16, archive 9, search 11,
navigation 5). Правила: 1 кейс = 1 тест минимум, ID кейса (TC-…) — в docstring,
маркеры приоритета MoSCoW из кейса, изоляция и детерминизм (скилл test-automation).

## Запуск

```bash
# 1. Приложение запущено (локально: из backend/, см. deploy/README.md):
DB_PATH=/tmp/app.db SECRET_KEY=<hex> uvicorn app.main:app --host 127.0.0.1 --port 8080
# 2. Схема + seed-пользователи (идемпотентно):
DB_PATH=... SECRET_KEY=... python -m app.db && python -m app.seed_users

# 3. Прогон (из корня репозитория):
EKOTOV_WIKI_BASE_URL=http://127.0.0.1:8080 \
EKOTOV_WIKI_DB_PATH=/tmp/app.db \
python -m pytest tests/ -q
```

Вход теста:
- `EKOTOV_WIKI_BASE_URL` — корень приложения (дефолт `http://127.0.0.1:8080`).
  VPS: домен из deploy/README.md (там же запросы идут
  по https — Secure-кука отправляется штатно).
- `EKOTOV_WIKI_DB_PATH` — путь SQLite-БД приложения. Нужен ТОЛЬКО кейсам с
  прямой правкой/чтением БД (смещение done_at, истечение сессии, bcrypt-осмотр):
  без переменной эти тесты `skip`, остальные проходят.
- `EKOTOV_WIKI_OWNER_PASSWORD` / `EKOTOV_WIKI_WIFE_PASSWORD` — пароли seed-пользователей
  (дефолты — тестовые значения локального прогона; на VPS задать явно).

Стек: `pytest`, `requests` (добавлены в `backend/requirements.txt`).

## Маркеры

| Маркер | Смысл |
|---|---|
| `api` | API-тест (requests) — весь набор |
| `must` / `should` / `could` | приоритет MoSCoW из одобренного кейса |
| `manual` | НФТ-процедура: автоматизация нецелесообразна, шаги в docstring |
| `web_ui` | UI-часть кейса: скоуп tests/web (браузер), здесь skip |

Выбор: `pytest tests/ -m must`, `-m "not manual"` и т.п. (`pytest.ini` регистрирует маркеры).

## Особенности окружения

- **Secure-кука по http.** Продукт ставит куку `session` с `Secure` (sdd §3.1).
  requests не отправляет Secure-куку по http, браузеры же для localhost
  (trustworthy origin) — отправляют. `LocalhostSession` (conftest) повторяет
  браузерное поведение для http://localhost / 127.0.0.1; на https-развертывании
  работает штатная механика.
- **Прямые операции с БД** (TC-board-005, TC-arch-002/003/007, TC-tasks-009,
  TC-auth-002/017) — через `EKOTOV_WIKI_DB_PATH`; эмуляция прошедшего МСК-дня —
  вариант Б кейсов (допустимая замена, отмечена в docstring каждого теста).
- **Изоляция:** все тестовые задачи имеют префикс `QAT-` и удаляются в teardown
  (фикстуры `api`/`cleanup_task`); сессии авторизации — function-scope.
- **Детерминизм:** sleep нет; готовность сервера — poll `/api/health` с таймаутом.

## НФТ-кейсы: решение по автоматизации

- **CHK-17 (TC-auth-017), осмотр БД** — `@pytest.mark.manual` + автоматизируемая
  часть `test_owner_password_hash_is_bcrypt` ($2b$, длина ≥60) при заданном
  DB_PATH. `grep` по бинарному файлу БД и `git check-ignore` зависят от
  окружения развертывания — ручная процедура (docstring теста).
- **CHK-55 (TC-tasks-015), CHK-56 (TC-tasks-016), рестарт** —
  `@pytest.mark.manual`: тест не может безопасно перезапускать процесс сервиса
  (systemctl/uvicorn) из pytest-сессии; процедуры в docstring (снимки до/после,
  poll health ≤60 с, diff пуст).
- **CHK-59 (TC-arch-003), граница полуночи МСК** — реализован вариант Б
  (эмуляция смещением done_at — допустимая замена по кейсу): `test_msk_midnight_boundary_done_2358_archives_next_day`.
  Вариант А (живое ожидание 23:58 МСК + 10 мин) — ручная процедура: ожидание
  полуночи в автотесте нарушило бы детерминизм и скорость прогона.
- **CHK-56/55 производительность** — NFR-2/NFR-1 (1000+ задач, ≤2 с) — кейсов в
  approved-наборе нет (вне скоупа; tasks.md 8.2 закрывается отдельной проверкой).

## UI-части кейсов (скоуп tests/web, вне API-набора)

Кейсы с браузерными шагами (переходы по сайдбару, форма, drag-n-drop, DOM/CSS
fast line) покрыты API-частью здесь; UI-проверки отмечены `@pytest.mark.web_ui`
со skip или упомянуты в docstring. Полный список UI-остатка: TC-auth-009/010/011
(частично), TC-board-001/003/007 (браузерная часть), TC-fast-001/005/012,
TC-tasks-005/011 (диалог подтверждения), TC-search-001/005/006/007 (UI-половина),
TC-arch-004/008/009 (бейджи), TC-nav-001…005 (клики по сайдбару) — tests/web,
отдельный playwright-набор.

## Матрица трассировки: 80 кейсов → тесты

| Домен | Кейсы | Тестов (модуль) | Примечание |
|---|---|---|---|
| auth | TC-auth-001…016 (16) | 16 + 1 параметризация×3 (TC-auth-009) | test_auth.py |
| auth | TC-auth-017 (1, НФТ) | manual-процедура + 1 автотест ($2b$) | test_auth.py |
| board | TC-board-001…010 (10) | 10 | test_board.py |
| fastline | TC-fast-002/003/004/006/007/008/009/010/011 (9) | 9 | test_fastline.py |
| fastline | TC-fast-001/012 (2, UI) | 2 × web_ui-skip (скоуп tests/web) | test_fastline.py |
| fastline | TC-fast-005 (1, UI-негатив) | web_ui (скоуп tests/web): создание второй fast через UI-форму | test_fastline.py |
| tasks | TC-tasks-001…014 (14) | 14 | test_tasks.py |
| tasks | TC-tasks-015/016 (2, НФТ-рестарт) | 2 × manual | test_tasks.py |
| archive | TC-arch-001…009 (9) | 9 (003 — вариант Б) | test_archive.py |
| search | TC-search-001…011 (11) | 11 | test_search.py |
| navigation | TC-nav-001…005 (5) | 5 (API-часть; UI — tests/web) | test_navigation.py |
| **Итого** | **80 кейсов** | **82 теста** (77 проходят, 5 skip: 2 рестарт-НФТ, 1 bcrypt-БД, 2 UI-fastline) | |

Чексумма кейсов: auth 17 + board 10 + fastline 12 + tasks 16 + archive 9 + search 11 + navigation 5 = 80.
Кейс CHK-35 (fastline) отсутствует в approved (отложен: DS-1) — теста нет и не требуется.

## Прогон (эталон, локально)

```
EKOTOV_WIKI_BASE_URL=http://127.0.0.1:8080 EKOTOV_WIKI_DB_PATH=/tmp/app.db \
python -m pytest tests/ -q
→ 77 passed, 5 skipped, 0 failed   (~31 c)
Без EKOTOV_WIKI_DB_PATH → 60 passed, 22 skipped (БД-кейсы пропущены).
```

Падение теста при верном коде теста = кандидат в дефекты продукта →
баг-репорт в `test-model/bugs/` (формат: BUG-N: кейс, ожидание, факт, окружение).

---

# API-сьют Релиза 2: add-r2-categories-settings (tests/api, файлы test_r2-*)

pytest + requests по 33 approved-кейсам `test-model/approved/add-r2-categories-settings/`:
TC-cat-001…015 (категории), TC-migr-001…006 (миграция), TC-fast2-001…012
(fast×priority), TC-env-001…002 (seed/cleanup справочника). Правила те же:
1 кейс = 1 тест, TC-ID в docstring, маркеры MoSCoW, изоляция `QAT-*`.

## Seed справочника и cleanup (TC-env-001/002)

- `r2_seed_categories` (session-scope, `conftest.py`): ДО любого прогона
  создает в справочнике `Дом`, `Работа`, `Личное` (идемпотентно, 409 = уже
  есть); ПОСЛЕ сессии убирает `QAT-*`-хвосты упавших тестов (справочник
  общесистемный, ОГР-7; cleanup задач категорий не убирает — тесты сами
  переводят задачи на `Дом` перед удалением своих категорий).
- `category_directory`: хелпер `/api/categories` + track/untrack фабрика
  гарантированного удаления QAT-категорий в teardown.
- `r2_fast_line`: вход «активных fast нет» (негативы fast×priority) с
  восстановлением доски после теста.

## Миграционный контур (TC-migr-*, TC-fast2-010)

Фикстура `migr_temp_db` копирует БД стенда во временный файл (очищенным
справочником — предусловие кейсов), туда же пишутся данные «до внедрения»,
запускается `python -m app.migrate_categories` (sdd r2 §5) subprocess'ом;
рабочий стенд не затрагивается. Требует `EKOTOV_WIKI_DB_PATH` (иначе skip).
TC-migr-006 проверяет негатив NFR-8: расхождение → exit 1 + FAIL в stdout.

## Метки regression (G5)

- `keep` — все тесты test_categories/test_fast2/test_env;
- `candidate-archive` — все тесты test_migration + test_fast2::test_migration_normalizes_fast_priority
  (TC-migr-001…006, TC-fast2-010 — разовые проверки внедрения, impact §3 п.2).

## Известные отклонения

- **BUG-002** (`test-model/bugs/BUG-002-fast-explicit-null-priority-201.md`):
  TC-fast2-004 — явный `priority: null` при is_fast=true дает 201
  (priority=high), а не 422 из кейса; create_task не различает null и
  отсутствие поля. Тест `test_fast_explicit_null_priority_422` помечен
  `xfail(strict)` — при исправлении продукта сработает XPASS-сигнал.
- TC-cat-008: тела 422 каркасной валидации pydantic —
  `{"error": "validation error", ...}` (формат каркаса), статус и отказ
  соответствуют кейсу; зафиксировано в docstring теста.
- UI-остатки кейсов (select'ы форм, страница /settings, блокировка поля
  приоритета — TC-cat-001/002/003/004, TC-fast2-003) — скоуп tests/web,
  помечены `web_ui` + skip (см. матрицу ниже).

## Матрица трассировки: 33 кейса → тесты

| Кейсы | Тесты | Файл | Метка |
|---|---|---|---|
| TC-cat-001 (UI) | test_category_form_field_is_select_from_directory (web_ui-skip; API-шаг 1 — seed) | test_categories.py | keep |
| TC-cat-002 (UI) | test_category_filter_field_is_select_from_directory (web_ui-skip) | test_categories.py | keep |
| TC-cat-003 (UI+API) | test_category_outside_directory_not_selectable_anywhere (API-шаг 1; UI — tests/web) | test_categories.py | keep |
| TC-cat-004 (API+UI) | test_category_create_201_visible_in_directory (UI-шаги — tests/web) | test_categories.py | keep |
| TC-cat-005 | test_category_rename_applies_to_all_tasks | test_categories.py | keep |
| TC-cat-006 | test_category_delete_in_use_blocked_409 | test_categories.py | keep |
| TC-cat-007 | test_category_delete_unused_ok | test_categories.py | keep |
| TC-cat-008 | test_category_empty_name_rejected_422 | test_categories.py | keep |
| TC-cat-009 | test_category_duplicate_409_post_and_patch_case_sensitive | test_categories.py | keep |
| TC-cat-010 | test_category_patch_delete_missing_id_404 | test_categories.py | keep |
| TC-cat-011 | test_categories_get_401_without_session_and_200_sorted | test_categories.py | keep |
| TC-cat-012 | test_task_create_with_unknown_category_422_not_created | test_categories.py | keep |
| TC-cat-013 | test_task_patch_with_unknown_category_422_value_untouched | test_categories.py | keep |
| TC-cat-014 | test_validation_follows_current_directory | test_categories.py | keep |
| TC-cat-015 | test_empty_category_is_allowed | test_categories.py | keep |
| TC-migr-001 | test_migration_unique_values_become_categories_1to1 | test_migration.py | candidate-archive |
| TC-migr-002 | test_migration_tasks_keep_category_values | test_migration.py | candidate-archive |
| TC-migr-003 | test_migration_empty_values_create_no_records | test_migration.py | candidate-archive |
| TC-migr-004 | test_migration_all_nonempty_categories_valid | test_migration.py | candidate-archive |
| TC-migr-005 | test_migration_zero_loss_snapshot_verification | test_migration.py | candidate-archive |
| TC-migr-006 | test_migration_mismatch_fails_verification | test_migration.py | candidate-archive |
| TC-fast2-001 | test_fast_create_priority_auto_high | test_fast2.py | keep |
| TC-fast2-002 | test_regular_task_keeps_chosen_priority | test_fast2.py | keep |
| TC-fast2-003 (UI) | test_fast_priority_field_locked_in_form (web_ui-skip) | test_fast2.py | keep |
| TC-fast2-004 | test_fast_explicit_null_priority_422 (xfail strict — BUG-002) | test_fast2.py | keep |
| TC-fast2-005 | test_fast_priority_low_422 | test_fast2.py | keep |
| TC-fast2-006 | test_fast_priority_medium_422 | test_fast2.py | keep |
| TC-fast2-007 | test_forged_client_request_rejected_by_server | test_fast2.py | keep |
| TC-fast2-008 | test_fast_without_priority_key_gets_high | test_fast2.py | keep |
| TC-fast2-009 | test_regular_task_any_priority_unrestricted | test_fast2.py | keep |
| TC-fast2-010 | test_migration_normalizes_fast_priority | test_fast2.py | candidate-archive |
| TC-fast2-011 | test_patch_cases_regular_high_ok_fast_medium_rejected | test_fast2.py | keep |
| TC-fast2-012 | test_second_fast_with_invalid_priority_order_fixed | test_fast2.py | keep |
| TC-env-001 | test_seed_directory_present_before_any_run + фикстура r2_seed_categories | test_env.py | keep |
| TC-env-002 | test_directory_isolation_and_cleanup + teardown фикстуры | test_env.py | keep |

Итого: 33 кейса → 35 тестовых функций (каждому кейсу — минимум один тест;
UI-шаги смешанных кейсов помечены web_ui-skip со ссылкой на tests/web).

## Прогон (эталон, локально; R2)

```
EKOTOV_WIKI_BASE_URL=http://127.0.0.1:8099 EKOTOV_WIKI_DB_PATH=/tmp/r2qa_app.db \
python -m pytest tests/api -q
→ 115 passed, 9 skipped, 1 xfailed (BUG-002), 0 failed
До R2-сьюта (на main): 9 failed + 8 errors — предсуществующие падения
фикстур без seed справочника (test_tasks/test_search/test_suggestions*,
test_archive); закрываются session-scope seed фикстурой r2.
```

Падение теста при верном коде теста = кандидат в дефекты продукта →
баг-репорт в `test-model/bugs/`.

---

# Web-сьют E2E-G1 (tests/web, Playwright)

Playwright-сьют по 18 approved-кейсам критического пути
`test-model/approved/e2e-critical-path/ui-01.md` (TC-UI-001…018, CHK-E-1…18,
все Must). Regression-кейсы продовых дефектов 2026-09-19 — TC-UI-006/013/015.

## Структура

```
tests/web/
├── conftest.py                    # стенд (uvicorn+static+временная БД+seed), браузер, хелперы
├── test_auth_ui.py                # TC-UI-001…005 (auth: редиректы, вход, ошибка, сессия, выход)
├── test_board_tasks_ui.py         # TC-UI-006…009, 012…015 (доска, задачи, комментарии, 2 регрессии)
├── test_fastline_ui.py            # TC-UI-010, 011 (fast line)
└── test_navigation_search_ui.py   # TC-UI-016, 017, 018 (навигация, поиск, финал пути)
```

Правила сьюта: 1 кейс = 1 тест, `TC-UI-…` в docstring, маркеры
`e2e`+`web`+`must` (по приоритету кейса), селекторы — рольные/семантические из
кейсов (ID-локаторы `#task-form-overlay`/`#task-detail-overlay` — только для
скрытых модалок без ARIA-роли, соглашение п.3 кейсов), автожидания `expect`,
`time.sleep` = 0.

## Тестовый стенд (фикстура `web_server`, сессия)

Сьют поднимает стенд сам — прод и API-сьют не затрагиваются:
- uvicorn `app.main:app` на свободном порту + `python -m http.server` на
  соседнем (докрут `frontend/static`) — воспроизведение продовой топологии
  «nginx раздает статику → proxy на app» (design §8; в app статика не
  смонтирована, review 2.3-002); Playwright-маршрут перебрасывает `/static/*`
  на static-сервер, куки работают (единый origin страниц);
- временная пустая SQLite-БД (tmp dir): схема (`python -m app.db`) + seed
  owner/wife с тестовыми паролями кейсов (bcrypt);
- `EKOTOV_WIKI_DB_PATH` выставляется на сессию — DB-крюки TC-UI-017/018
  (смещение done_at эмуляцией прошедшего МСК-дня, вариант Б) работают из
  коробки, skip-семантика не срабатывает;
- playwright: headless chromium, новый контекст на тест (чистые куки).

## Изоляция

- БД пустая на сессию; каждый тест создает свои предусловия сам (цепочки
  кейсов вида «создана в TC-UI-010» заменены setup-помощником в самом тесте);
- teardown: `web_cleanup_created` удаляет созданные тестом задачи через API
  (`DELETE /api/tasks/{id}`, физическое удаление — включая архивированные);
- Secure-кука по http: teardown-сессия повторяет браузерное поведение
  trustworthy origin (`LocalhostSession`, как в tests/api).

## Запуск

```bash
# 1. Зависимости (однократно; playwright уже в backend/requirements.txt):
pip install playwright
python -m playwright install chromium     # браузер (~115 МБ, ~/.cache/ms-playwright)

# 2. Прогон (стенд поднимается автоматически):
python -m pytest tests/web -q
#   эталон локально: 17 passed, 1 failed (BUG-001, см. ниже), ~45 c

# Прогон против внешнего стенда (например, прод-подобного) вместо автостенда:
EKOTOV_WIKI_BASE_URL=https://<host> EKOTOV_WIKI_DB_PATH=<путь БД> python -m pytest tests/web -q
# (без EKOTOV_WIKI_DB_PATH DB-крюк-кейсы TC-UI-017/018 skip — как в tests/api)

# Выбор наборов: -m web / -m e2e / -m must (маркеры в tests/web/conftest-модулях).
```

Примечание: плагин pytest-base-url (транзитивная зависимость pytest-playwright)
регистрирует pytest-опцию `--base-url`; чтобы не конфликтовать с ней, API-сьют
не объявляет собственную одноименную опцию — базовый URL везде через env
`EKOTOV_WIKI_BASE_URL` (совместный прогон `pytest tests/` работает).

Вход теста (все опциональны):
- `EKOTOV_WIKI_BASE_URL` — задан → внешний стенд, автоподъем отключен;
- `EKOTOV_WIKI_DB_PATH` — путь SQLite-БД (DB-крюки; на автостенде задается сам);
- `EKOTOV_WIKI_OWNER_PASSWORD` / `EKOTOV_WIKI_WIFE_PASSWORD` — переопределение
  тестовых паролей seed.

## Матрица кейс→тест (E2E-G1)

| CHK | TC | Тест | Примечание |
|---|---|---|---|
| CHK-E-1 | TC-UI-001 | test_auth_ui::test_unauthenticated_redirects_to_login | |
| CHK-E-2 | TC-UI-002 | test_auth_ui::test_owner_login_success_board_and_sidebar | |
| CHK-E-3 | TC-UI-003 | test_auth_ui::test_wrong_password_and_unknown_login_same_error | |
| CHK-E-4 | TC-UI-004 | test_auth_ui::test_session_survives_reload | |
| CHK-E-5 | TC-UI-005 | test_auth_ui::test_logout_invalidates_session | |
| CHK-E-6 | TC-UI-006 | test_board_tasks_ui::test_modals_hidden_on_board_load | REGRESSION 2026-09-19(a) |
| CHK-E-7 | TC-UI-007 | test_board_tasks_ui::test_create_task_title_only | |
| CHK-E-8 | TC-UI-008 | test_board_tasks_ui::test_create_task_without_title_rejected | |
| CHK-E-9 | TC-UI-009 | test_board_tasks_ui::test_all_attributes_create_view_edit | |
| CHK-E-10 | TC-UI-010 | test_fastline_ui::test_fast_task_create_and_highlight | скриншот в tests/web/artifacts/ |
| CHK-E-11 | TC-UI-011 | test_fastline_ui::test_second_fast_task_rejected | |
| CHK-E-12 | TC-UI-012 | test_board_tasks_ui::test_move_between_columns_and_quick_done | |
| CHK-E-13 | TC-UI-013 | test_board_tasks_ui::test_move_without_selected_card_no_request | REGRESSION 2026-09-19(c) |
| CHK-E-14 | TC-UI-014 | test_board_tasks_ui::test_add_comment_persists | |
| CHK-E-15 | TC-UI-015 | test_board_tasks_ui::test_comment_submit_without_card_no_request | REGRESSION 2026-09-19(b) |
| CHK-E-16 | TC-UI-016 | test_navigation_search_ui::test_sidebar_all_pages_and_wiki_stub | |
| CHK-E-17 | TC-UI-017 | test_navigation_search_ui::test_search_archived_task_builder_advanced_card | падение = BUG-001 |
| CHK-E-18 | TC-UI-018 | test_navigation_search_ui::test_final_path_autoarchive_and_fast_release | DB-крюк, вариант Б |

## Известные падения (дефекты продукта, не теста)

- **BUG-001** (`test-model/bugs/BUG-001-search-card-click.md`): TC-UI-017
  шаг 7 — клик по карточке в результатах поиска не открывает карточку:
  `renderCard()` в `frontend/static/js/search.js` не вешает click-обработчик
  (в `board.js` — вешает, строка 199). FR-10/CHK-E-17 не выполняется.

## Зависимости

`playwright` добавлен в `backend/requirements.txt` (секция tests/) —
выбран основной файл, отдельного requirements-dev в репозитории нет.
Браузер ставится командой `python -m playwright install chromium`.

---

# Web/API-сьют QA-этапа 5: add-r3-visual-foundation (tests/api + tests/web)

pytest + playwright по 32 approved-кейсам
`test-model/approved/add-r3-visual-foundation/` (authme 3, dnd 6, formv3 5,
nav 5, sel 8, vis 5). Правила прежние: TC-ID в docstring, маркеры
`api`/`web` + `must`/`should`/`could`, изоляция `QAT-*`, автожидания,
`time.sleep` = 0 (точечные ожидания отыгрыша CSS-анимаций — по длительности
токена, не произвольные).

## Механика HTML5 DnD (урок architect-ревью)

Нативные mouse-события Playwright НЕ порождают HTML5 drag-сессию:
dragstart/dragover/drop/dragend возбуждаются `dispatchEvent` с общим
объектом `DataTransfer` — `tests/web/dnd_helpers.py` (`dnd_dispatch`).
Нюанс cards.js: `drag-ghost` ставится в `requestAnimationFrame` после
dragstart — класс читается после очередного кадра.

## Запуск

```bash
# API-сьют (стенд по tests/README, свободный порт + чистая БД + seed):
DB_PATH=/tmp/app.db SECRET_KEY=<hex> uvicorn app.main:app --host 127.0.0.1 --port <порт>
EKOTOV_WIKI_BASE_URL=http://127.0.0.1:<порт> EKOTOV_WIKI_DB_PATH=/tmp/app.db \
  python -m pytest tests/api -q
# Web-сьют (стенд поднимается сам: uvicorn + http.server, временная БД):
python -m pytest tests/web -q
# Селекция этапа 5: -m "r3" не вводился — файлы test_r3_* / test_authme_r3.py
```

## Матрица трассировки: 32 кейса → тесты

| Кейсы | Тесты | Файл | Примечание |
|---|---|---|---|
| TC-authme-001 | test_me_parallel_sessions_keep_own_logins | tests/api/test_authme_r3.py | |
| TC-authme-002 | test_me_401_without_session_and_expired | tests/api/test_authme_r3.py | DB-крюк expire_session |
| TC-authme-003 | test_me_read_only_repeated_calls_stable | tests/api/test_authme_r3.py | |
| TC-dnd-101 | test_dnd_move_card_to_another_column | tests/web/test_r3_dnd_ui.py | BUG-003 (drop-target) |
| TC-dnd-102 | test_dnd_drop_outside_column_returns_card | tests/web/test_r3_dnd_ui.py | |
| TC-dnd-103 | test_dnd_fast_line_occupied_409_error_and_return | tests/web/test_r3_dnd_ui.py | BUG-003 |
| TC-dnd-104 | test_dnd_to_done_sets_done_at_no_archive | tests/web/test_r3_dnd_ui.py | |
| TC-dnd-105 | test_touch_tap_starts_no_drag_select_move_works | tests/web/test_r3_dnd_ui.py | has_touch-контекст |
| TC-dnd-106 | test_dnd_success_after_409_hides_board_error | tests/web/test_r3_dnd_ui.py | BUG-003 |
| TC-formv3-101 | test_form_fields_v3_tokens_and_focus_ring | tests/web/test_r3_formv3_ui.py | |
| TC-formv3-102 | test_selected_tags_rendered_as_chips | tests/web/test_r3_formv3_ui.py | |
| TC-formv3-103 | test_priority_pill_color_changes_and_inline_icon | tests/web/test_r3_formv3_ui.py | |
| TC-formv3-104 | test_edit_form_matches_v3_and_hides_fast_row | tests/web/test_r3_formv3_ui.py | |
| TC-formv3-105 | test_all_form_interactive_elements_styled | tests/web/test_r3_formv3_ui.py | |
| TC-nav-101 | test_profile_badge_and_login_on_all_pages | tests/web/test_r3_profile_ui.py | CHK-151+CHK-156 |
| TC-nav-102 | test_profile_shows_session_user_wife | tests/web/test_r3_profile_ui.py | |
| TC-nav-103 | test_profile_hidden_on_auth_me_401 | tests/web/test_r3_profile_ui.py | route 401 |
| TC-nav-104 | test_profile_block_has_no_extra_controls | tests/web/test_r3_profile_ui.py | |
| TC-nav-105 | test_profile_after_logout_and_sections_clickable | tests/web/test_r3_profile_ui.py | |
| TC-sel-101 | test_task_form_category_options_from_directory | tests/web/test_r3_selects_ui.py | |
| TC-sel-102 | test_sel_102_manual_customer_production_session | tests/web/test_r3_selects_ui.py | manual-skip: ЗАПРЕЩЕНА автоматизация (прод + сессия Заказчика) |
| TC-sel-103 | test_suggestions_401_silent_empty_datalist | tests/web/test_r3_selects_ui.py | |
| TC-sel-104 | test_search_filter_category_options_from_directory | tests/web/test_r3_selects_ui.py | |
| TC-sel-105 | test_category_directory_changes_reflected_in_both_selects | tests/web/test_r3_selects_ui.py | маркер serial |
| TC-sel-106 | test_datalists_show_task_tag_and_category_values | tests/web/test_r3_selects_ui.py | |
| TC-sel-107 | test_single_mechanism_two_endpoints | tests/web/test_r3_selects_ui.py | |
| TC-sel-108 | test_selects_not_empty_not_static | tests/web/test_r3_selects_ui.py | |
| TC-vis-101 | test_card_hover_transition_and_accent_title | tests/web/test_r3_vis_ui.py | |
| TC-vis-102 | test_empty_column_state_styled_and_cleared | tests/web/test_r3_vis_ui.py | |
| TC-vis-103 | test_card_move_animated_v_in | tests/web/test_r3_vis_ui.py | |
| TC-vis-104 | test_new_card_entrance_animation_v_in | tests/web/test_r3_vis_ui.py | |
| TC-vis-105 | test_reduced_motion_disables_animations_keeps_function | tests/web/test_r3_vis_ui.py | emulateMedia reduced-motion |

Итого: 32 кейса → 32 теста (31 автоматизировано + TC-sel-102 manual-skip).

## Известные падения (дефекты продукта, не теста)

- **BUG-003** (`test-model/bugs/BUG-003-dnd-drop-target-lost-todo-inprogress.md`):
  `onDragOver` в `frontend/static/js/board/cards.js` тоглит `drop-target`
  трижды на ОДНОМ столбце (по COLUMNS) — класс удерживается только на
  `done`. Падают TC-dnd-101/103/106 и TC-vis-105 (шаг «подсветка
  применяется»); функциональность переноса при этом работает.
- Тест `test_settings_contains_only_category_management` (TC-set-006,
  R2) скорректирован под R3: подстрока "profile" в HTML /settings теперь
  легальна (sidebar-profile на всех страницах функционала, FR-33);
  запрет профиля КАК РАЗДЕЛА настроек проверяется отсутствием
  управляющих элементов в main.

## Прогон (эталон, локально)

```
# tests/api (стенд на свободном порту, чистая БД + seed):
EKOTOV_WIKI_BASE_URL=http://127.0.0.1:<порт> EKOTOV_WIKI_DB_PATH=/tmp/app.db \
python -m pytest tests/api -q
# tests/web (автостенд):
python -m pytest tests/web -q
```

# Миграционный сьют Релиза 4: add-r4-user-profile-ticket-view (tests/api/test_migration_r4.py)

9 кейсов миграции users/tasks (tasks 1.1; review-001-1.1): свежая БД/SCHEMA_SQL (2),
бэкфилл creator/assigned (FR-38/ОВ-23), роли (ОВ-21), снимок NFR-9, FK, идемпотентность
(no-op проверяется по состоянию БД, R-5а), ветка owner-отсутствует-при-пустых-tasks
(R-5б), негативы owner-удален и расхождение сверки. Прогон — на временных копиях БД в
tmp/scratch, прод не трогается.

Примечание (R-5в, review-001-1.1): сценарий «Вход работает после миграции» (NFR-9)
проверяется ЭКВИВАЛЕНТНО — равенством логинов/хешей паролей снимку «до»; реальный
логин после миграции не выполняется (хеши в тестовых фикстурах — плейсхолдеры, не
реальные bcrypt-значения). Допустимая замена, зафиксировано здесь.

# QA-контур 4.1 Релиза 5: add-r5-avatar-crop-compact-profile

## Гэпы API (tests/api/test_gaps_r5.py)

5 approved-кейсов `test-model/new/add-r5-avatar-crop-compact-profile/`
(чеклист `test-model/checklists/add-r5-avatar-crop-compact-profile.md`,
impact `test-model/impact/add-r5-avatar-crop-compact-profile.md` — пробелы
поверх существующих TC-ava-001…007 + TC-ava-r5-101/102 + web
TC-r5card-301…305 / TC-r5crop-401…415, которые не дублируются):

| Кейс | CHK | Тест | Гэп |
|---|---|---|---|
| TC-ava-r5-103 | CHK-R5-3 | test_normalization_jpeg_non_square_to_256_png | нормализация jpg-входа → 256×256 PNG (r5-101/102 — только png) |
| TC-ava-r5-104 | CHK-R5-6 | test_size_limit_boundary_exactly_2mb_accepted_plus_one_rejected | граница 2 МБ: ровно 2 097 152 байт принят; +1 байт → 422 file too large (TC-ava-005 ~27 МБ; web-тест — клиентская ветка) |
| TC-ava-r5-105 | CHK-R5-12 | test_wife_upload_does_not_touch_owner_avatar | изоляция: загрузка wife не меняет sha256/БД-строку owner (хвост CHK-R4-25 Р4 «косвенно») |
| TC-ava-r5-106 | CHK-R5-9 | test_pre_release_avatar_file_not_repainted | backward-compat ОГР-21/СЦ-13: файл «старого» аватара не перекрашивается при открытии профиля/me (web-часть — TC-r5crop-401) |
| TC-ava-r5-107 | CHK-R5-13 | test_exif_portrait_jpeg_accepted_and_normalized | EXIF Orientation=6 («портрет с телефона», design §7) → 200 + 256×256 PNG; ассерт на ориентацию пикселей не ставится (вариант А: EXIF — браузер, ОВ-СА-1) |

Среда: те же env, что для всего tests/api, ПЛЮС `EKOTOV_WIKI_AVATARS_DIR`
(обязателен — гигиена аватаров по файлам). Teardown каждого теста восстанавливает
avatar_path/avatar_updated_at = NULL и удаляет `<user_id>.png` (owner; кейс
изоляции — также wife).

Прогон (эталон, задача 4.1): api — avatar r4+r5+гэпы 16 passed; полный tests/api
187 passed, 9 skipped, 2 xfailed (стенд :8091, tmp-БД + seed + migrate_r4);
web Р5-зона (r5card + r5crop + settings_profile_r4) 33 passed.

## Чего НЕ автоматизировано в 4.1 (вне гэпов API)

- web-кейсы дельты уже покрыты существующими TC-r5card-301…305 и
  TC-r5crop-401…415 (5 гэпов чеклиста — все API-уровня; web-часть CHK-R5-9
  покрыта TC-r5crop-401).
- CHK-R5-32 (СЦ-14: static_v-бамп, nginx /avatars/, полный регресс) — слепые
  контуры impact §4: релизная дисциплина (задачи 4.3/4.4), смоук на проде.
- EXIF на реальном тач-устройстве — ручной смоук (эмуляция — TC-r5crop-406,
  API — TC-ava-r5-107).
