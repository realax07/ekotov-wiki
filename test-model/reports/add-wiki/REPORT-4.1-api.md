# REPORT-4.1-api — QA: набор api (add-wiki, ЭТАП C, задача 4.1)

- **Change:** add-wiki | **Роль:** qa_automation (делегация-раннер набора api) | **Дата:** 2026-10-10
- **Ветка:** `pipeline/p15-stage-a`, HEAD `91658ec` (волна 3 wiki-фронтенда 6fdc36c влита) | **Коммиты в ходе задачи:** нет (прогон + REPORT)
- **Полный текст задачи:** `openspec/changes/add-wiki/tasks.md` строка 4.1 (пункты а/б/в)
- **Вердикт:** **PASSED** (набор api зеленый: п.а — 0 failed, п.б — полный регресс 274 passed / 0 failed, п.в — все цели NFR-30 достигнуты с запасом ≥3×)

---

## §1. Стенд

Прод-топология пакета воспроизведена процессами (прецедент `tests/REPORT-regress-21.md` §2; docker не используется — прод-стек контейнеров на хосте не затронут):

- **app** (монолит `backend/app`): uvicorn 127.0.0.1:8093 (через nginx) + 127.0.0.1:8080 (ядро-миную-nginx для `EKOTOV_WIKI_CORE_URL`); `DB_PATH=/tmp/qa41_app.db`, `SECRET_KEY=<hex>`, `AVATARS_DIR=/tmp/qa41_avatars`.
- **search** (`services/search/app`): uvicorn 127.0.0.1:8378, `EKOTOV_WIKI_DB_PATH` (ro-профиль).
- **images** (`services/images/app`): uvicorn 127.0.0.1:8379, `EKOTOV_WIKI_DB_PATH` + `EKOTOV_WIKI_IMAGES_DIR=/tmp/qa41_images_vol`.
- **nginx** :18443 (HTTP) — паритет `services/frontend/nginx/ekotov-wiki.conf` без docker: search-семейство (`= /api/search`, `^~ /api/search/`, `= /api/suggestions`, `^~ /api/suggestions/`, X-Service: search), images-семейство (`= /api/images`, `^~ /api/images/`, X-Service: images, `client_max_body_size 12m`, `@images_down`), `/images/` + `/avatars/` + `/static/` (mime.types подключен — урок regress-21), остальное → app.
- **Отличие стенда от образа** (не продукт, тот же прием что regress-21): server-level `client_max_body_size` поднят 2m→**64m** — multipart-тела avatar-гейт-кейсов (2 097 322 байта и ~27 МБ) иначе режутся nginx 413 до валидации app; прод-лимит «исходник ≤ 2 МиБ» обеспечивает `MAX_AVATAR_BYTES` в app, что и проверяют кейсы.
- **БД (порядок критичен, tests/README.md):** `python -m app.db` (схема) → seed owner/wife (программно `app.seed_users.seed_user`, bcrypt; пароли — тестовые дефолты сьюта `QaOwner_Pass_1!`/`QaWife_Pass_2!` через env) → `python -m app.migrate_r4` (роли PM/PE) → `python -m app.migrate_gallery` (6 таблиц) → `python -m app.migrate_wiki` (2 таблицы + 3 индекса, сверка ОК) → seed категорий «Дом», «Работа», «Личное».
- **Health до прогона:** `:8093/api/health`, `:8080/api/health`, `:8378/api/health`, `:8379/api/health`, `:18443/api/health` (через nginx) = `{"status":"ok"}`; X-Service: search на `/api/search` через nginx — подтвержден.
- Интерпретатор: `/home/openclaw/venvs/wiki/bin/python` (pytest 9.1.1, requests, PIL; проектный `.venv` тоже рабочий — прогон шел на wiki-venv).
- Стенд погашен после прогона (uvicorn ×4, nginx -s quit); БД `/tmp/qa41_app.db` оставлена с перф-корпусом (см. §4) — временный файл, вне репо.

Примечание к isolation: часть ранних прогонов этой сессии попала на параллельную активность другого агента (baseline-прогоны web-сьюта из `/tmp/ew-baseline` против того же порта nginx — QAGAL41-хвосты в галерее, статус-коды 409/500-загрязнение). Все числа ниже — с ФИНАЛЬНОГО прогона на чистой БД без параллельного шума (`/tmp/qa41_regression_RUN2.log`).

## §2. Пункт (а): wiki-сьют + sanitizer

| Сьют | Прогон | Результат |
|---|---|---|
| `tests/api/test_wiki_api.py` (27 тестов) | venv wiki, стенд :8093 | **27 passed, 0 failed** |
| `tests/api/test_sanitize.py` (16 функций, 1 параметризация → 35 проверок) | чистые юниты (`app.sanitize`, без БД) | **35 passed, 0 failed** |
| Совместно | | **62 passed** (~4.3 с) |

Покрытие по пунктам задачи 4.1(а) (тесты `test_wiki_api.py`):

- **CRUD и валидации:** пустой/отсутствующий title → 422; несуществующий parent_id → 422; GET несуществующей → 404; PUT несуществующей → 404; DELETE с дочерними → 409; DELETE листа удаляет и версии (RESTRICT/CASCADE живы); `can_delete` лист vs родитель; breadcrumb-цепочка глубокой страницы.
- **Версии на каждое сохранение:** PUT создает запись версии + бамп updated_at; **сохранение только заголовка** (`test_update_title_only_keeps_content`) — контент не тронут, версия записана.
- **Откат:** `test_revert_creates_new_version_not_rewrite` — revert = НОВАЯ запись версии; история V1–V3 не переписана; revert чужой версии / несуществующей страницы → 404.
- **LIKE-поиск:** заголовок и текст; нет совпадений; LIMIT 20; **не по версиям**; **экранирование `%`/`_`/`\`** (`test_search_escapes_like_wildcards`, ESCAPE-паттерн сервера); сниппет — **plain-текст без HTML-тегов** (`test_search_snippet_plain_text_no_tags`, DV-1).
- **Sanitizer-негативы/позитивы** (`test_sanitize.py` + сквозные `test_create_sanitizes_content`/`test_revert_sanitizes_stored_content`): `<script>`/`<style>` с содержимым вырезаны; `onclick`/on*-атрибуты сняты; `javascript:`-href вырезан; `iframe`; вложенная мутация `<scr<script>ipt>`; whitelist-разметка тулбара (H1–H3, B/I/U, ul/ol, цитата, код-блок, ссылка, таблица, изображение) проходит без искажений; URL-фильтр http/https/относительные.
- **Права:** `test_all_endpoints_require_session` — 401 аноним на все 9 API-методов; **паритет owner/wife** — смоук на стенде (жена читает 200, правит страницу владельца 200 с записью своей версии author_id=2, создает 201; владелец откатывает её версию 200, история 3 записи, ничего не потеряно).
- **Редиректы страниц без сессии:** `GET /wiki` и `GET /wiki/{id}` анонимно → **302 → /login** (middleware; в api-сьюте покрыто `tests/api/test_navigation.py::test_wiki_page_scaffold_no_todo_stub` — 5/5 passed).

## §3. Пункт (б): полный регресс ядра

Прогон `tests/api` ЦЕЛИКОМ, кроме известных фоновых файлов (см. §5): `--ignore=tests/api/test_search.py --ignore=tests/api/test_search_r4.py`.

**Итог: 274 passed, 11 skipped, 2 xfailed, 0 failed, 0 errors (~116 с).**

Состав skip (10+1 по составу, не env): 2 × manual-рестарт НФТ (TC-tasks-015/016), 1 × bcrypt-БД НФТ, 6 × UI/web_ui-skip (categories 3, fastline 2, fast2 1), 1 × docker-зависимый инфра-шаг (TC-GAL-106 шаг 5) — ожидаемые по tests/README.md. Оба xfailed — BUG-003 (empty-name validation body format), стабильны.

Зоны ядра, подтвержденные зелеными (миграция wiki существующее не сломала):

| Зона | Файлы | Результат |
|---|---|---|
| Доска + задачи + fastline + архив | test_board, test_tasks, test_fastline, test_fast2, test_archive | 0 failed |
| auth + sessions + /me | test_auth, test_auth_me, test_authme_r3 | 0 failed |
| Категории/настройки | test_categories, test_env | 0 failed |
| Галерея-API (сервис images через nginx) | test_qa21_gallery_api/infra | 0 failed |
| Профиль + аватары Р4/Р5 + гэпы | test_profile_r4, test_avatar_r4/r5, test_gaps_r4/r5 | 0 failed |
| OpenAPI-контракт | test_openapi_r11 (после перегенерации `contracts/openapi.json` — волна 3 добавила `/wiki/{page_id}/history`; экспорт script'ом, см. §6) | 0 failed |
| suggestions (сервис search) | test_suggestions* | 0 failed |

Наблюдение в ходе прогонов (не дефект, задокументировано): первый полный прогон поймал `test_openapi_r11::test_openapi_with_session_200_and_matches_contract` — `contracts/openapi.json` не содержал путь `/wiki/{page_id}/history` (роут добавлен волной 3, экспорт контракта не перегенерировали). Исправление: `python scripts/export_openapi.py` (30 путей) → тест зеленый. Изменение `contracts/openapi.json` НЕ закоммичено (граница задачи — прогон; перегенерацию фиксирует dev-цикл).

## §4. Пункт (в): перф-чек NFR-30

**Корпус (сеялка `/tmp/qa41_perf_seed.py`):** прямые sqlite INSERT — **1000 страниц** (500 корней + цепочки до глубины 4, content ~1.7 КБ HTML) + **10 000 версий** (по первым 200 страницам), датированные offset-aware ISO (`datetime.now(timezone.utc) − N·sec`). Сид: 1.3 с.

**Замеры:** `requests` через nginx-стенд :18443, **20 повторов на операцию**, p95 = 95-й перцентиль. Два круга — значения стабильны. Скрипт использует LocalhostSession-прием conftest (Secure-кука по http localhost).

| Операция | Эндпоинт | p95 (круг 1) | p95 (круг 2) | Цель NFR-30 | Вердикт |
|---|---|---|---|---|---|
| Открытие страницы | GET /api/wiki/pages/{id} | 30.1 мс | 26.2 мс | < 300 мс | OK (×10 запас) |
| Открытие (глубокая, breadcrumbs) | GET /api/wiki/pages/{deep_id} | 29.8 мс | 37.8 мс | < 300 мс | OK |
| Дерево (плоский список) | GET /api/wiki/pages | 70.0 мс | 41.8 мс | < 300 мс | OK (×4 запас) |
| Версия read-only | GET /api/wiki/pages/{id}/versions/{vid} | 31.1 мс | 86.5 мс | < 300 мс | OK |
| Версии (список, 50 у страницы-лидера) | GET /api/wiki/pages/{id}/versions | 20.0 мс | 24.4 мс | < 300 мс | OK |
| Поиск: частотное слово (контент) | GET /api/wiki/search?q=латентный | 69.2 мс | 67.3 мс | < 500 мс | OK (×7 запас) |
| Поиск: нет совпадений | GET /api/wiki/search?q=…-xyzzy | 109.8 мс | 76.7 мс | < 500 мс | OK (worst-case полный скан) |
| Поиск: префикс заголовка | GET /api/wiki/search?q=QAPERF-страница-00 | 48.5 мс | 54.4 мс | < 500 мс | OK |
| Поиск: экранирование %_ | GET /api/wiki/search?q=100%25_ | 76.3 мс | 32.3 мс | < 500 мс | OK |

**Итог NFR-30: ВСЕ ЦЕЛИ ДОСТИГНУТЫ.** Худшая операция — поиск «нет совпадений» ~110 мс p95 (полный LIKE-скан 1000 страниц), 4.5× запас до цели 500 мс; дерево 70 мс p95 на 1000 узлов — 4× запас. Замеры в json: `/tmp/qa41_perf.json` (вне репо).

## §5. Квалификация фоновых падений test_search* (известный фон)

- Файлы: `tests/api/test_search.py` (11 кейсов) и `tests/api/test_search_r4.py` (3 кейса) — **исключены из прогонов**, как предписано задачей и деlegацией.
- Причина — **не регресс волны 3 и не миграция wiki**: search-маршруты отрезаны от монолита коммитом `f0fe4ec` (задача 1.5 пакета add-microservices-full; `backend/app/search.py`/`suggestions.py` удалены, источник истины — `services/search/`). Часть кейсов этих файлов ходит напрямую на `/api/search*` монолита (404) — это **известный фон на ЛЮБОМ коммите после отрезки** (зафиксировано в делегации: «9 failed + 7 errors на любой базе»).
- В справочнике тестов на монолите search-семейство легитимно проверяется против nginx-стенда (search-сервис поднят, X-Service: search): test_suggestions* / test_suggestions_r6 / test_suggestions_gap / часть test_openapi_search_service — **зеленые** в прогоне §3. «Хвост» test_search* — кейсы, не переключенные на маршрутизированный стенд, вне скоупа 4.1 (чинить не по этой задаче; кандидат — отдельная тех-задача на migrate кейсов к `EKOTOV_WIKI_BASE_URL`=nginx).
- Контрольный факт: сам тест-гейт отрезки `test_openapi_search_service.py::test_core_has_no_search_routes` — **passed** в прогоне §3 (монолит содержит 0 search-маршрутов).

## §6. Побочные находки и границы

1. **contracts/openapi.json разошелся с живой схемой** (волна 3 добавила `/wiki/{page_id}/history`, экспорт не перегенерировали) — обнаружено регресс-тестом `test_openapi_r11`, снято перегенерацией на месте. Правка контракта в worktree НЕ закоммичена — передать dev-циклу на фиксацию (1 файл).
2. **Ранние «красные» прогоны этой сессии** (16f/16e → 5f → 3f → 1f по итерациям) — целиком дефекты среды, не продукта: (а) пароль seed не совпадал с дефолтами conftest; (б) `AVATARS_DIR` не был задан → 500 на avatar-upload (Permission denied `/var/lib/...`); (в) отсутствовали search/images-сервисы и nginx-маршрутизация (404 галереи/suggestions); (г) параллельный чужой web-прогон против того же стенда (QAGAL41-хвосты → strict-фейлы подсчета). Воспроизведения на финальном чистом прогоне нет.
3. В worktree уже находились чужие незакоммиченные правки (`frontend/static/css/wiki.css` +6 строк BUG-017, `test-model/bugs/BUG-017-…`) от делегации 4.3 — не тронуты, в прогон не вмешались.
4. Перф-корпус остался в `/tmp/qa41_app.db` (pages=1000, page_versions=10000) — не мешает прод-БД, может быть удален.

## §7. Вывод

- **(а)** wiki-сьют: **62 passed / 0 failed** (27 API + 35 sanitize-проверок) — CRUD/версии/откат/поиск/санитизация/права/редиректы соответствуют design §3–§6 и FR-107–116, NFR-31.
- **(б)** полный регресс ядра: **274 passed / 11 skipped / 2 xfailed / 0 failed** — миграция wiki существующую функциональность не сломала.
- **(в)** NFR-30 на корпусе 1000 страниц / 10 000 версий: p95 всех операций **в 3–10 раз лучше целей** (открытие/дерево/версии ≤ 70 мс при лимите 300 мс; поиск ≤ 110 мс при лимите 500 мс).
- **Вердикт: набор api — PASSED.** Набор web-desktop (4.2) может стартовать; вфиксировать перед ним: коммит перегенерированного `contracts/openapi.json` (§6.1).
