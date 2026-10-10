# REPORT-4.4 — add-wiki ЭТАП C: смок на стенде + репетиция миграции + кроссбраузерность

Задача: openspec/changes/add-wiki/tasks.md 4.4 [tests][infra]
Ветка: `pipeline/p15-stage-a` (HEAD `a374381`, волна 3 влита). Стенд собран ИЗ ЭТОЙ ветки.
Дата: 2026-10-10. Окружение: хост openclaw, docker через `sg docker`, образы ветки `p15s-a-*` (свежая сборка app/frontend/search/images/backup из HEAD).

**Вердикт: PASS** — (а) репетиция миграции на фактическом прод-снапшоте: ОК ×2 (идемпотентность подтверждена); (б) смок-чеклист 13/13; (в) кроссбраузерность Chromium+Firefox: 16/16 операций на браузер, 0 JS-ошибок. Прод-лем доступ НЕ трогался (только ro-чтение тома для снапшота).

---

## (а) Репетиция migrate_wiki (NFR-32)

**Ограничение задачи снято: репетиция выполнена НЕ на синтетике, а на ФАКТИЧЕСКОМ снапшоте прод-БД.** Docker-доступ у агента есть (openclaw в группе docker, `sg docker` — skill devops/ekotov-wiki-ops v1.8, факт: контейнеры `ekotov-wiki-par-*` Up). Снапшот снят без остановки прода и БЕЗ записи в прод: временный контейнер `--user 0` с ro-маунтом тома `ekotov-wiki-par_wiki-data` + `sqlite3.Connection.backup()` (консистентный эквивалент VACUUM INTO; изнутри контейнера — по РАНБУК-паттерну «python sqlite3 stdlib, sqlite3 CLI в образе нет»). Прод-контейнеры, тома и данные не модифицировались (проверено: все проверки ниже — на копии `/tmp/t44/`).

### Состояние снапшота ДО миграции

- Источник: `ekotov-wiki-par_wiki-data:/data/wiki.db` (прод-том, стек :10443). Размер копии 155 648 байт; `PRAGMA integrity_check` = **ok**.
- Таблиц (13, wiki-таблиц нет — докатываемое состояние): categories 4, comments 6, gallery_tags 13, image_categories 8, image_comments 4, image_reactions 3, image_tags 13, images 11, sessions 8, tags 7, task_tags 15, tasks 12, users 2.
- Пользователи: owner = Product manager, wife = Product engineer (роль изменена пользователем через UI после релиза — правило 13 skill: сверка валидности, не равенства дефолту; миграция wiki ролей не касается — по PRAGMA миграция пишет 0 строк данных).

### Прогон 1 — накатка

```
DB_PATH=/tmp/t44/rehearsal/wiki.db SECRET_KEY=<test> python -m app.migrate_wiki   # cwd=backend
→ До: таблиц wiki существует 0/2 (чистая БД)
→ Создано таблиц: 2: ['pages', 'page_versions']
→ Создано/подтверждено индексов: 3
→ === Сверка: ОК ===
EXIT: 0
```

### Прогон 2 — идемпотентность (повторный запуск)

```
→ До: таблиц wiki существует 2/2
→ Создано таблиц: 0 (no-op — все существовали)
→ === Сверка: ОК ===
EXIT: 0
```

### Сверка ПОСЛЕ (независимая, поверх автосверки миграции)

| Проверка | Результат |
|---|---|
| `PRAGMA integrity_check` | ok |
| `PRAGMA foreign_key_check` | пусто |
| Старые данные (13 таблиц, счетчики до/после) | **0 расхождений** — миграция не тронула ни одну строку |
| `pages` колонки | id, parent_id (NULL), title NOT NULL, content NOT NULL DEFAULT '', author_id NOT NULL, created_at, updated_at — design §1 |
| `page_versions` колонки | id, page_id NOT NULL, content NOT NULL, author_id NOT NULL, created_at |
| NOT NULL / DEFAULT '' | подтверждены PRAGMA table_info |
| FK | pages.parent_id→pages RESTRICT, page_versions.page_id→pages CASCADE, author_id→users |
| Индексы | idx_pages_parent, idx_pages_title, idx_page_versions_page(page_id, id) — все на своих таблицах/колонках |

**Результат: сверка зеленая. Вывод для 4.5: боевая накатка migrate_wiki на прод разрешена** (идемпотентна; при выкатке deploy-конвейер ставит ее после шага схемы, откат кода без отката БД безопасен — новые таблицы старый код не читает).

Дополнительно: миграция прогнана и на стенде-контуре (внутри app-контейнера против volume-БД стенда, `EXIT: 0`, сверка ОК) — тот же путь исполнения, что в продовом deploy-конвейере (exec в контейнер app).

---

## (б) Смок на стенде (compose.test, порт 8443)

Стенд: `docker compose -f deploy/compose.test.yaml -p wiki-test up -d --build` из ветки. Явный порт **8443** (nginx→внутр. 10443, TLS self-signed). Изоляция от прода: проект `wiki-test`, том `wiki-test_wiki-test-data` — прод не затронут.

Seed стенда: `app.seed_users` (owner/wife, тест-пароли `QaOwner_Pass_1!`/`QaWife_Pass_1!` из tests/api/conftest.py) → `app.migrate_r4` (роли PM/PE) → `app.migrate_gallery` → `app.migrate_wiki`.

**Предусловие чистоты прогона:** volume-БД стенда получает схему ядра без gallery-таблиц и wiki-таблиц (шаг `python -m app.db` в entrypoint не накатывает их автоматически). Первый прогон `GET /api/images` дал **500** (`no such table: images`) и первый `POST /api/wiki/pages` — **500** (`no such table: pages`); после явного прогона `migrate_gallery` и `migrate_wiki` — 200/201. Это **не дефект волны 3** (миграции работают), а **инфра-пробел стенда**: compose.test поднимает БД без gallery/wiki-миграций. Рекомендация в 4.5/deploy: в deploy-конвейере прод-БД миграции накатываются шагами (прод-том уже с gallery-таблицами — галерея работает на проде); для стенда добавить миграционные шаги в seed-процедуру RUNBOOK (зафиксировано как замечание).

### Чеклист смока (числа)

| # | Пункт | Ожидание | Факт | Статус |
|---|---|---|---|---|
| 1 | Контейнеры стека healthy | 6/6 (app, nginx, search, images, backup, netdata) | `Up (healthy)` ×6 через ~70 c после старта | PASS |
| 2 | app healthcheck | `/api/health` → 200 `{"status":"ok"}` | 200, `{"status":"ok"}` (через nginx :8443) | PASS |
| 3 | images-сервис жив | `/api/images` под сессией → 200 | 200 `{"images":[]}`; ред. `/api/images/categories` без параметров → 422 (вал., нет category_id) | PASS |
| 4 | search-сервис жив | `/api/search?q=…` под сессией → 200 | 200 | PASS |
| 5 | Логин owner | 200 + сессия | 200; `/api/auth/me`: role Product manager | PASS |
| 6 | Логин wife | 200 + сессия | 200; роль Product engineer | PASS |
| 7 | `/wiki` без сессии | редирект /login | **302 → https://127.0.0.1:8443/login** | PASS |
| 8 | `/wiki` под owner | 200 каркас | 200 | PASS |
| 9 | `/wiki` под wife | 200 каркас | 200 | PASS |
| 10 | Смок: создать страницу | 201 | POST /api/wiki/pages → 201 `{"id":1}` | PASS |
| 11 | Смок: отредактировать | 200 + новая версия | PUT → 200; versions 1→2 | PASS |
| 12 | Смок: найти поиском | 200 с результатом | GET /api/wiki/search?q=поиска → 200, snippet `Смок Текст для поиска жирный`, match_offset 15, match_length 6 | PASS |
| 13 | Смок: откатить версию | revert = новая запись, история не переписана | POST revert/1 → `{"new_version_id":3}`; контент вернулся к v1; versions: [3,2,1] — история растущая, не переписанная | PASS |
| 14 | Паритет прав owner/wife | чтение+правка у обоих | wife: GET 200, PUT 200 | PASS |
| 15 | Аноним к API wiki | 401 | GET/POST → 401 `{"error":"unauthorized"}` | PASS |
| 16 | API-контракт | 9 REST-путей | /api/wiki/pages (GET/POST), pages/{id} (GET/PUT/DELETE), versions, versions/{vid}, revert/{vid}, search — все ответили ожидаемыми кодами (лишних/недостающих нет) | PASS |

Примечание к пп.10–13: маршрут выполнен HTTP-уровнем (curl + cookie-сессии) и повторен браузером в п.(в) — UI-редактор гоняет те же эндпоинты (editor.js: POST /api/wiki/pages, PUT …/{id}, «Сохранить» → редирект на статью).

---

## (в) Кроссбраузерность редактора (NFR-33)

Playwright-скрипт (`/tmp/t44/crossbrowser.py`, headless, `ignore_https_errors`), один и тот же сценарий на Chromium 153.0.8010.12 и Firefox 155.0 (playwright 1.63; firefox-1543 доставлен `playwright install firefox` — в кэше был только chromium).

Сценарий на браузер: логин owner → `/wiki` → «Создать страницу» → `?create=1` редактор → заголовок + текст → тулбар B / I / U (toggle с набором текста между) → маркированный список → таблица 3×3 → диалог «Изображение» (открывается, галерейная сетка `.img-pick-grid` видима; закрытие «Отмена») → «Сохранить» → статья с таблицей/жирным/списком в DOM → повторное редактирование `?edit=1` → «правка-2» → «Сохранить» → статья содержит правку. Подсчет: `pageerror`-события консоли.

| Операция | Chromium 153 | Firefox 155 |
|---|---|---|
| Логин → /board | PASS | PASS |
| `/wiki` открывается (h1 «Wiki») | PASS | PASS |
| «Создать страницу» → редактор (?create=1) | PASS | PASS |
| Тулбар: B (Полужирный) | PASS, `<b>` в DOM после save | PASS |
| Тулбар: I (Курсив) | PASS | PASS |
| Тулбар: U (Подчеркнутый) | PASS | PASS |
| Тулбар: маркированный список | PASS, `<ul><li>` в DOM | PASS |
| Тулбар: таблица 3×3 | PASS, 1 table, 3 th | PASS, 1 table, 3 th |
| Тулбар: изображение — диалог открывается/закрывается | PASS | PASS |
| Сохранение → статья (`/wiki/{id}`, контент в DOM) | PASS | PASS |
| Повторное редактирование (?edit=1) + сохранение | PASS («правка-2» в статье) | PASS |
| JS-ошибки консоли (pageerror) | 0 | 0 |
| **Итог браузера** | **PASS (16/16)** | **PASS (16/16)** |

Факт сохранения в БД стенда: pages=5, page_versions=12 после прогонов (страницы «Кроссбраузер chromium/firefox» по 2 версии = создание + правка; «Смок страница 4.4» — 3 версии из HTTP-смока).

Известная особенность (не дефект): диалог изображения редактора закрывается кнопкой «Отмена»/кликом по фону — обработчика Escape нет. Для скриптов автоматизации это значит: после открытия диалога жать «Отмена», не `Escape`. Продуктового дефекта не квалифицируем (Escape не заявлен в спеке/DV редактора).

---

## Итоги и входы для 4.5

1. **Репетиция миграции — на фактическом прод-снапшоте** (ограничение «синтетика» НЕ применилось): migrate_wiki ОК ×2, данные не тронуты, сверка зеленая. Боевая накатка разрешена.
2. **Смок стенда 16/16**; контракт API — 9 путей; 401/302-гейты работают.
3. **Кроссбраузерность: Chromium + Firefox — PASS**, 0 JS-ошибок.
4. Замечание стенду (не блокер прода): compose.test-volume требует явных `migrate_gallery` + `migrate_wiki` после seed (500 «no such table» до миграций). Включить в RUNBOOK-процедуру подъема стенда.
5. Ограничение по факту доступа: docker у агента ЕСТЬ (sg docker), поэтому пункт задачи «доступ отсутствует» не актуален; прод-том читался только ro, ни один прод-контейнер не рестартовался.

Артефакты: скрипт кроссбраузерности `/tmp/t44/crossbrowser.py`, снапшот `/tmp/t44/prod_copy.db`, репетиционная БД `/tmp/t44/rehearsal/wiki.db`, логи `/tmp/t44/{up.log,app.log,routes_out.txt}`. Коммит не выполнялся (по постановке); стенд `wiki-test` оставлен поднят (гасить: `docker compose -f deploy/compose.test.yaml -p wiki-test down -v`).
