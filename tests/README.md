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
