# Архитектурная карта ekotov-wiki («как есть»)

Статус: актуальна на 2026-10-12 (сверка с кодом origin/main `92e3c69`; предыдущая ревизия 2026-10-05, коммит `44426bf`, эпоха 2.5 — за интервал ~387 коммитов). Прод: релиз **p15-wiki-7** (= текущий origin/main по коду), compose-проект `ekotov-wiki-par`, **6 контейнеров**: app (:8377) + frontend/nginx (:10443) + search (:8378) + images (:8379) + backup (sidecar) + netdata (sidecar). Матричный стек P11: nginx маршрутизирует `/api/search*` и `/api/suggestions*` на search:8378 (`X-Service: search`), `/api/images*` на images:8379 (`X-Service: images`) — управляемая 503-деградация (@search_down / @images_down) при недоступном сервисе; search читает общую БД в ro-профиле, images — первый RW-писатель после ядра (только таблицы gallery + SELECT users); netdata-дашборд :19999 слушает ВНУТРИ compose-сети, наружу только через nginx `/netdata/` с basic auth; бэкап — compose-sidecar (суточный цикл, retention 14 дней) + релизный бэкап deploy.sh через ТОТ ЖЕ модуль `services/backup/backup.py`. systemd-прод остановлен ранее и остается чекпоинтом v1-отката. Детали эксплуатации — `deploy/RUNBOOK.md`; инструменты — `deploy/deploy.sh` (RELEASE_TAG, one-shot миграция до up), `deploy/2.3-par.sh`, `deploy/2.4-switch.sh`.
Задача выполнена по Флоу 1 (ПМ-проход docs-части: зоны architecture/**/sdd.md вне политики роли dev — DENY машины, задокументирован в release-log). Артефакт только фиксирует факты и решения; задачи сюда не входят.
Источники: код `backend/app/`, `frontend/`, `services/{app,frontend,search,images,backup}/`; `deploy/compose.yaml`, `deploy/deploy.sh`, `services/frontend/nginx/`; `contracts/openapi-search.json`; спеки `openspec/specs/*/spec.md`; `backend/requirements.txt`; архив `openspec/changes/archive/`.

## 1. Компоненты и границы

### 1.1 Приложение (uvicorn, один процесс)

| Компонент | Файл(ы) | Ответственность |
|---|---|---|
| Точка входа | `backend/app/main.py` | Сборка FastAPI-приложения (`docs/redoc/openapi` отключены), подключение роутеров (auth, avatar, pages, profile, tasks, categories, comments, board, wiki, users), `GET /api/health`, `POST /api/auth/logout` (логаут — здесь, не в auth-роутере) |
| Конфиг | `backend/app/config.py` | Только env: `DB_PATH`, `SECRET_KEY` обязательны, дефолтов нет — их отсутствие = падение старта |
| Auth middleware | `backend/app/middleware.py` | Единая точка проверки сессии для API (401) и страниц (302 → `/login`); exempt: `POST /api/auth/login`, `GET /api/health`, `GET /login`; скользящий TTL 30 дней |
| Auth | `backend/app/auth.py` | `POST /api/auth/login`: bcrypt, dummy-хеш против раскрытия существования логина, токен 256 бит в таблицу `sessions` |
| Роутеры (routes) | `tasks.py` (778 стр., CRUD+move+priority-lock+error handlers), `board.py` (доска + ленивая автоархивация по МСК), `categories.py`, `comments.py`, `users.py` (read-only `GET /api/users`), `profile.py` (`GET/PUT /api/profile`, смена пароля), `avatar.py` (multipart-загрузка аватара: Pillow-валидация, ≤2 МБ, имя файла генерирует сервер), `wiki.py` (482 стр., `/api/wiki/*` — см. ниже), `pages.py` (168 стр., Jinja2-страницы: login, board, search, wiki, wiki/{id}, wiki/{id}/history, settings, settings/profile, gallery) | Вся бизнес-логика — серверная: priority-lock, жесткая валидация категории по справочнику, инварианты fast line |
| Wiki-домен | `backend/app/wiki.py` + `migrate_wiki.py` + `sanitize.py` | Страницы-дерево: плоский список (дерево строит клиент), CRUD, breadcrumb (лимит глубины 100 от циклов), версии (каждое сохранение = INSERT `page_versions`; revert = НОВАЯ версия, история не переписывается; DELETE 409 при дочерних, версии уходят по FK CASCADE). Поиск: `GET /api/wiki/search?q=` — LIKE %q% по title+content, регистронезависимость через `casefold`-функцию `wiki_nocase` (create_function; встроенная lower() sqlite не опускает кириллицу — возврат живой приемки p15-wiki-5), экранирование `%_\` ESCAPE, сниппет ±60 симв. с оффсетом (HTML `<mark>` ставит клиент), LIMIT 20. Санитизация — `sanitize.py` (whitelist-санитайзер на html.parser stdlib, bleach/lxml запрещены ОГР-8: whitelist тегов = тулбар редактора, атрибуты on*/style/class/id снимаются, URL-фильтр http/https/относительные, script/style вырезаются с содержимым) — применяется НА ЗАПИСИ (POST/PUT/revert); миграция `migrate_wiki.py`: таблицы `pages` (parent_id FK ON DELETE RESTRICT, NULL = корневая) + `page_versions` (FK CASCADE), идемпотентно, одна транзакция BEGIN IMMEDIATE, автосверка структуры |
| DB-слой | `backend/app/db.py` | Схема ядра (CREATE IF NOT EXISTS: users, sessions, tasks, categories, tags, task_tags, comments), per-connection `PRAGMA journal_mode=WAL` + `foreign_keys=ON`; отдельные one-shot скрипты внедрения (паттерн «рукопашная миграция», §6.2): `seed_users.py`, `migrate_categories.py`, `migrate_r4.py` (профиль + creator/assigned), `migrate_gallery.py` (таблицы gallery: images, image_categories, gallery_tags, image_tags, image_reactions, image_comments), `migrate_wiki.py`; в деплое — шаг `MIGRATE_MODULE=<module>` deploy.sh (строго до up) |
| Сервисный слой как отдельный модуль | отсутствует | Логика живет внутри роутеров; «services»-слоя нет — границы слоев: routes → sql inline → db.py (connection/schema) |

Поисково-suggestions-логика из монолита ВЫНЕСЕНА: `backend/app/search.py`/`suggestions.py` в репо больше не существуют — их место `services/search/app/{search,suggestions}.py` (отдельный uvicorn :8378, контракт `contracts/openapi-search.json`).

Границы приложения: приложение НЕ отдает статику (`StaticFiles`/`mount` в коде отсутствуют — перепроверено grep 2026-10-12) и НЕ терминирует TLS.

### 1.2 Фронтенд

Jinja2-шаблоны `frontend/templates/` (8 шт: base, login, board, search, wiki, settings, profile-settings, gallery) + ванильный JS `frontend/static/js/` (ES-модули):
- `board/*` — api, state, dom, cards, task-detail, task-form, priority-icons, tag-combobox, modal-shell, auto-textarea, card-tooltip, board-dots, board-init (13 модулей);
- `wiki/*` — tree.js (231, дерево из плоского списка), page.js (430), editor.js (1318, contenteditable + тулбар), search.js (137), history.js (600);
- `gallery.js` (1357) — галерея: загрузка, категории/теги, реакции, комментарии (через `/api/images*` → images-сервис);
- отдельные: login.js, search.js, settings.js, profile.js, profile-settings.js, avatar-crop.js, tooltip.js, app.js.

CSS `frontend/static/css/` (токены дизайна V3 в app.css) + responsive-слой пакета add-responsive-mobile (мобильные брейкпоинты, свайпы доски — smoke `tests/web/dev_smoke_p14_21_board_swipe.py`). UI = клиент REST API, в БД не лезет (ОГР-2). Шаблоны рендерит приложение (Jinja2Templates из `pages.py`), статику — nginx (§1.3).

### 1.3 Прод-топология (кратко; детали и процедуры — deploy/RUNBOOK.md, не дублируются)

**Прод — compose-матрица P11 из 6 контейнеров (`deploy/compose.yaml`, прод-проект `ekotov-wiki-par` — PROJECT env deploy.sh; дефолт в скрипте `ekotov-wiki`), релиз p15-wiki-7:**

```
Браузер ── https://194.58.34.122:10443 (TLS self-signed, том с хоста ro) ── nginx [контейнер frontend, :10443, mem 64m]
   ├── /static/            → из образа (expires 7d, public)
   ├── /avatars/           → alias /data/avatars/ (том wiki-data ro, expires 7d)
   ├── /images/            → alias /data/images/ (том images-data ro; файлы галереи отдаёт nginx, images-сервис в отдаче не участвует)
   ├── /api/search* /api/suggestions* → search:8378 (X-Service: search; 503 @search_down) [mem 512m, wiki-data ro, healthcheck /api/health]
   ├── /api/images*        → images:8379 (X-Service: images; 503 @images_down) [mem 128m, wiki-data rw + images-data, healthcheck /api/health]
   ├── /netdata/           → netdata:19999 (basic auth netdata.htpasswd, порт НЕ публикуется) [mem 256m, /proc /sys docker.sock — все ro, healthcheck curl /api/v1/info]
   └── /                   → proxy_pass http://app:8377 (compose-сеть; resolver 127.0.0.11 + переменная — anti stale-DNS)
           uvicorn [контейнер app, uid 10001, --workers 1, mem 512m, healthcheck /api/health]
             └── SQLite /data/wiki.db → named volume `wiki-data` (БД + avatars/)
           [контейнер backup, sidecar, mem 64m] wiki-data ro + bind /var/backups/ekotov-wiki (uid 10001);
             суточный цикл sqlite3 .backup + tar avatars, retention 14 дней
```

Порты внутренних сервисов (8377–8379, 19999) НЕ публикуются — наружу только nginx :10443 (FR-65). Тома: `wiki-data` (wiki.db + avatars/), `images-data` (файлы галереи: оригиналы + превью, FR-79 — вне БД; nginx и images маунтят одной глубиной — урок 404 avatars), bind-каталог бэкапов хоста. Healthchecks: app/search/images — urllib к своему /api/health; netdata — curl; backup — heartbeat-процесс (вне цепочки запросов). Лимиты памяти: 512+512+128+64+256+64 = 1.54 GB при VPS 3.9 GB (резерв хосту ≥ 2 GB).

Ключевое: деплой — `deploy/deploy.sh` (build тегов `<release>`, latest запрещен; бэкап БД+аватаров до каждого деплоя без остановки; one-shot миграция `MIGRATE_MODULE` строго до up; подъем последовательно app → healthy → search+backup → nginx; смоук, вкл. 502-контроль). Откат: предыдущий релизный тег одной командой; чекпоинт ЭТАПА 2 — systemd-схема (`deploy/deploy-v1-systemd.sh`, юнит остановлен 2026-10-03, `enabled` сохранен). Прочее (TLS-сертификат до 2028, htpasswd netdata — пароль отдельный от wiki-owner, смоук) — RUNBOOK.

### 1.4 Тестовый контур (не прод)

`tests/api` (pytest+requests, 288 тест-функций) и `tests/web` (playwright, 251 тест-функций; счет по `def test_` в репо 2026-10-12; параметры/маркеры могут менять собираемое число) против стенда: uvicorn + временная БД; web-стенд эмулирует роль nginx'а по статике вторым процессом `python -m http.server` (tests/web/conftest.py) — см. риск §6.1. Сервисные наборы: `services/search/tests` (12) и `services/images/tests` (34). Wiki-покрытие: `tests/api/test_wiki_api.py`, `tests/api/test_sanitize.py`, `tests/web/test_p15_wiki_{page,editor}.py`. Кроссбраузерная матрица в conftest не конфигурируется (Playwright/Chromium по умолчанию) — отдельная политика кроссбраузерности: требует проверки.

## 2. Потоки данных

**Основной запрос (API):**
```
Браузер (fetch, JSON) ──HTTPS──> nginx :10443 (TLS, security-заголовки, gzip)
  ──> uvicorn :8377 ── auth middleware (кука session → таблица sessions: валидация + скользящий TTL)
  ──> роутер (pydantic-валидация тела → серверные инварианты: priority-lock, категория по справочнику)
  ──> sqlite3 (параметризованный SQL; WAL; FK on) ──> JSON-ответ (200/401/404/409/422 по контрактам sdd §3)
```

**Маршрутизация на сервисы (nginx):** `/api/search*`, `/api/suggestions*` → search:8378 (read-only профиль БД: ro-маунт тома + код); `/api/images*` → images:8379 (RW только таблицы gallery + SELECT users, короткие транзакции, busy_timeout). Оба — с заголовком `X-Service` и управляемой 503-деградацией (error_page 502/503/504 → `@search_down`/`@images_down` → JSON 503), не 502-залипание.

**Страницы:** тот же путь, но на выходе Jinja2-рендер (base.html + страница, `?v={{ static_v }}` на статике; static_v = `p15-wiki-7`). Без сессии — 302 на `/login` (middleware).

**Статика:** `/static/*` перехватывает nginx (из образа), **до приложения не доходит** (допущение Д-а, §4). Кеш браузера 7 дней; инвалидация — только сменой URL через бамп `static_v` в `pages.py`.

**Wiki-потоки:** чтение — плоский `GET /api/wiki/pages`, дерево строит клиент (один запрос, NFR-30); страница + breadcrumb (сервер, лимит 100). Запись — content проходит `sanitize_html` ДО записи (в БД только чистый HTML); каждое сохранение = INSERT в `page_versions` (автор сессии); revert копирует контент версии в текущую + создает НОВУЮ версию — история append-only. Удаление: 409 при дочерних; иначе CASCADE версий. Поиск — casefold-нормализация обеих сторон LIKE (`wiki_nocase`), сниппет считает сервер по plain-тексту (теги срезаются `HTMLParser`), `<mark>` расставляет клиент по оффсету — сервер не вставляет HTML в API-ответ.

**Галерея/аватары:** аватар — POST `/api/profile/avatar` (app: multipart → Pillow-декодирование, ≤2 МБ, серверное имя `<user_id>.png` → `wiki-data/avatars/`, отдаёт nginx alias). Галерея — `/api/images*` → images-сервис (метаданные в общую БД, файлы → том `images-data`), отдача файлов — nginx alias `/images/` ro, images-сервис в отдаче не участвует.

**Данные (жизненный цикл задачи):** создание/правки — через tasks-роутер; перевод в done фиксирует `done_at`; ленивая автоархивация при чтении доски (задачи выполненные до начала текущего МСК-дня получают `archived_at`) — фоновой задачи/крона нет, время — фиксированный UTC+3 в коде (`msk_now_iso` из board.py — единый источник, использует и wiki.py). Категории хранятся у задач **по значению** (tasks.category TEXT), переименование в справочнике переносит значение UPDATE'ом всех задач в одной транзакции.

**Запись:** все мутирующие операции — короткие транзакции sqlite3 с commit в роутере; соединение открывается на запрос и закрывается (нет пула). Исключение по профилю записи: images-сервис — второй RW-клиент той же БД (таблицы gallery), sidecar backup — читатель (`sqlite3 .backup` + tar).

## 3. Внешние зависимости

Продуктовый код (`backend/app/`, `services/*/app/`) — импорты проверены по `backend/requirements.txt` (все запинены `==`):

| Зависимость | Версия | Где используется |
|---|---|---|
| fastapi (+starlette, pydantic) | 0.141.1 | все роутеры, middleware, сервисы search/images |
| uvicorn[standard] | 0.53.0 | сервер (app, search, images) |
| jinja2 | 3.1.6 | pages.py |
| bcrypt | 5.0.0 | auth.py, seed_users.py |
| Pillow | 12.3.0 | avatar.py (обработка аватара), images-сервис (превью) |
| python-multipart | 0.0.32 | avatar.py (multipart/form-data) |
| sqlite3, secrets, datetime, pathlib, re, html.parser, urllib и пр. | stdlib (Python 3.12 на проде, 3.11 в dev) | db, auth, wiki, sanitize и др. |

`requests` в продуктовом коде **не используется** — только в тестах (pytest 9.1.1, requests 2.34.2, playwright 1.63.0). Системные зависимости прода: nginx, sqlite3, rsync, docker compose, образ netdata/netdata:stable (RUNBOOK §2). Сетевых вызовов наружу приложение не делает; netdata — единственная внешняя телеметрия, отключена (DISABLE_TELEMETRY=1).

## 4. Архитектурные допущения (явный список)

Каждое — с пометкой «проверено на проде» (чтение конфигов/кода прода, RUNBOOK E9) или «НЕ проверено» (не верифицировалось боевой нагрузкой/эксплуатацией). Ревизия 2026-10-12: кодовые факты перепроверены grep/чтением по origin/main; боевая эксплуатация wiki/images-доменов после p15 — вне этого замера.

| # | Допущение | Пометка |
|---|---|---|
| Д-а | Статику отдаёт nginx (образ frontend: `/static/` из образа, `/avatars/`, `/images/` — alias), приложение не имеет StaticFiles/mount — статика до uvicorn не доходит | **Проверено на проде**: код (grep StaticFiles/mount — пусто, повторно 2026-10-12), nginx-конфиг образа `services/frontend/nginx/ekotov-wiki.conf`, смоук RUNBOOK §4.4. Нюанс DEF-002/003 (кеш браузера) остался в слое доставки/кеша, не в приложении |
| Д-б | SQLite (WAL) достаточен для односемейной нагрузки (2 пользователя, NFR-2) | **Частично проверено**: замер NFR-1 в R1; WAL включается кодом на каждом соединении (db.py). С P11 писателей в БД стало двое (app + images, плюс читатели search/backup) — конкурентность двух RW-клиентов под WAL в бою специально не замерялась; профиль images ограничен таблицами gallery (короткие транзакции, busy_timeout). **НЕ проверено**: поведение под многолетним объемом |
| Д-в | Сессии живут в БД (таблица sessions), не в памяти: рестарт любого сервиса сессии НЕ инвалидирует | **Проверено на проде по коду** (auth.py INSERT, middleware SELECT; in-memory кеша нет; search/images валидируют сессию тем же чтением БД — middleware продублирован в services/*/app/middleware.py) |
| Д-г | Self-signed TLS допустим (личный продукт, домена нет; HSTS включен, пользователь один раз принимает исключение) | **Проверено на проде**: сертификат CN=194.58.34.122, notAfter 2028-12-22; решение в шапке nginx-конфига |
| Д-д | Календарь доски — фиксированный UTC+3 (МСК) без учета TZ сервера/клиента; DST не вводится | Проверено в коде (board.py `msk_now_iso`, использует и wiki.py); **НЕ проверено** поведение при переезде пользователя |
| Д-е | Общая доска/wiki/галерея без разделения по владельцу; обе учетки видят всё; регистрации нет (seed); wiki-страницы — без ролей (решение 7, FR-115) | Проверено в коде (seed_users.py, отсутствие user_id-фильтров, docstring wiki.py); на проде — используется Заказчиком |
| Д-ж | `SECRET_KEY` фактически не используется механизмом сессий (токены — `secrets.token_urlsafe`, не подпись) — обязательность переменной задел на будущее | Проверено в коде (config.py требует; использования secret_key в коде не находится) |
| Д-з | Один процесс uvicorn (--workers 1) достаточен | Проверено (Dockerfile app `--workers 1`; compose без масштабирования); достаточность под нагрузкой НЕ проверена (наследует Д-б) |
| Д-и | Managed 503-деградация search/images приемлема UX-ом (галерея/поиск «деградируют», ядро доски — нет: доска не зависит от сервисов) | Проверено в конфиге nginx (@search_down/@images_down → JSON 503) и коде (доска/задачи не вызывают сервисы); пользовательский опыт 503 в бою — НЕ проверено специально |

## 5. Принятые решения (что / почему / источник)

| Решение | Почему | Источник |
|---|---|---|
| Серверная сессия (таблица sessions + кука HttpOnly/SameSite=Lax/Secure) вместо JWT | Явный механизм без фреймворковой «магии»; revocation тривиален (DELETE строки); TTL скользящий 30 дней; JWT дал бы невозможность отзыва и лишнюю криптографию для 2 пользователей | design.md §2 (архив add-kanban-core), sdd §3.1, код auth.py/middleware.py |
| FastAPI + Jinja2 SSR, ванильный JS — без SPA-фреймворка | «Несоразмерно личному проекту на 2 пользователей» (ОГР-1); REST API сохранен (ОГР-2), UI — тонкий клиент; FastAPI вместо Flask — готовые pydantic-контракты | sdd §1 (таблица стека) |
| SQLite WAL, файл вне репозитория | Прямое пожелание Заказчика (ОГР-1 «lite DB», NFR-5); для 2 пользователей серверная БД — лишняя сущность; ноль демонов, бэкап = копия файла | sdd §1, §5; ОГР-1/NFR-5 |
| Матричный переход P11: монолит → app+frontend+search+backup → +images+netdata; параллельный стенд :10444 с приемкой, затем переключение :10443 | Выделение сервисов без Big Bang: каждый сервис — отдельный образ/лимит/healthcheck; nginx — единая точка входа и маршрутизации (X-Service, 503-деградация); откад роллбэк тегом | add-microservices-full, add-gallery-service, add-netdata-monitoring (архив); compose.yaml, deploy.sh |
| Search — отдельный сервис с ФАЙЛОВОЙ гарантией read-only (маунт wiki-data :ro) | Поиск ничего не пишет в БД: ro-маунт сильнее кодовой дисциплины; на пустом томе честный 500/503 вместо порчи БД | add-microservices-full design §2; compose.yaml (search) |
| Images — выделенный сервис, первый RW-писатель после ядра; файлы галереи — отдельный том images-data, вне БД (FR-79) | Изоляция тяжелого (Pillow, файлы) от ядра доски; RW-профиль ограничен таблицами gallery кодом сервиса (ro-маунт невозможен — сервис пишет); отдачу файлов забирает nginx (alias ro) — сервис не в горячем пути отдачи | add-gallery-service design §1/§2/§4; compose.yaml (images) |
| Wiki-домен в монолите: собственный whitelist-санитайзер на html.parser stdlib (без bleach/lxml), версии append-only, дерево строит клиент | ОГР-8 (без внешних библиотек-санитайзеров); санитизация на записи — в БД только чистый HTML; revert = новая версия (история не переписывается, аудит сохранен); плоский список + клиентское дерево = один запрос (NFR-30); поиск — casefold + LIKE вместо FTS (кириллица, минимальная зависимость) | add-wiki design §2–§6; код wiki.py, sanitize.py, migrate_wiki.py |
| Backup — compose-sidecar (суточный цикл python: sqlite3 .backup + tar avatars, retention 14 дней); релизный бэкап deploy.sh вызывает ТОТ ЖЕ модуль `services/backup/backup.py` | Один код бэкапа — без дубля логики; sidecar вне цепочки запросов, профиль ro; каталог бэкапов — bind хоста с числовым uid 10001 | add-microservices-full (задача 1.2); compose.yaml (backup), deploy.sh шаг 2/8 |
| Netdata — sidecar с ro-маунтами (/proc, /sys, docker.sock), дашборд только внутри сети, наружу через nginx + basic auth (отдельный htpasswd) | Мониторинг не управляет контейнерами (сокет ro); порт 19999 не публикуется (паритет FR-65); телеметрия наружу отключена | add-netdata-monitoring design §2/§4; compose.yaml (netdata), nginx netdata-*.inc |
| Категории у задач — по значению (TEXT), без FK по id | Простота модели и поиска; целостность — серверной валидацией (422) + переносом значения при переименовании + отказом удаления используемой (409, Д-1) | sdd §3.7, §4; код categories.py, tasks.py |
| Priority-lock fast line — серверной валидацией (is_fast ⇒ priority='high' или NULL), не UI | Инвариант принадлежит домену, UI не граница доверия (ОГР-10, FR-27); единая точка — tasks-роутер | sdd §3.2/§3.4; код tasks.py `_priority_lock_422` |
| Кеш-бастинг через `?v={{ static_v }}` (глобал в pages.py, единый финальный бамп релиза) вместо переименования файлов | Хотфикс DEF-002/003: минимальное изменение, не трогает пути nginx; content-hash избыточен на текущем объеме | PRODUCT_BACKLOG DEF-002/003; код pages.py (`static_v = "p15-wiki-7"`) |
| Ленивая автоархивация при чтении доски (без крона) | «Задержка до первого чтения после полуночи неотличима от фоновой задачи» — минус один демон (ОГР-1); done_at+archived_at в схеме | sdd r5 §3.3; код board.py |

## 6. Технический долг / риски (наблюдения, не задачи)

1. **Расхождение тестовый стенд / прод.** Web-стенд эмулирует роль nginx'а по статике `python -m http.server` (tests/web/conftest.py): нет TLS, нет `expires`/security-заголовков и gzip, нет маршрутизации на search/images (X-Service, 503-деградация — deploy/compose.test.yaml частично закрывает, но не web-сьютом). Класс рисков nginx-слоя веб-сьютом не ловится — прецедент DEF-002/003. Смягчение: пост-деплойный смоук по прод-URL (RUNBOOK §4.4) + сервисные наборы services/*/tests.
2. **Нет миграционного фреймворка.** Изменения схемы — рукопашные one-shot скрипты (migrate_categories, migrate_r4, migrate_gallery, migrate_wiki) + рукопашная проверка колонки в db.py; порядок применения и точка запуска — ручной шаг `MIGRATE_MODULE` deploy.sh (строго до up). Дисциплина работает, но каждое следующее изменение схемы — снова ручной скрипт + согласование с деплоем; забытый MIGRATE_MODULE = релиз на несмигрированной БД.
3. **`static_v` — ручной бамп.** Сейчас это оформленная дисциплина (единый финальный бамп релиза, C-5 ревью; текущее значение `p15-wiki-7` синхронно релизу), но шаг по-прежнему человеко-зависимый: забыли бампнуть при релизе со статикой → до 7 дней старый JS/CSS (прецедент DEF-002). Скрипт деплоя этого не проверяет.
4. **Дрейф «документация ≠ прод» без регулярных синхронизаций карты.** Предыдущая ревизия карты замерла на эпохе 2.5 (2026-10-05) и ~387 коммитов отстала от кода — wiki/images/netdata/backup в ней отсутствовали; устранено настоящей актуализацией (2026-10-12). Прод сейчас = origin/main (p15-wiki-7), но механизма синхронизации карты нет — риск воспроизводится при следующем длинном интервале.
5. **Конкурентность RW после P11 не замерялась** (наследие Д-б): app и images пишут в одну БД; профиль images ограничен таблицами gallery, но наблюдений WAL/lock-конфликтов в бою нет.
6. **Снапшот отката устарел** (RUNBOOK §4.3): `~/ekotov-wiki-R1-snapshot` эпохи R1 — требует проверки/пересоздания при следующем деплое (в этой ревизии не проверялся).
7. **Зависимости запинены, но аудита уязвимостей нет** — requirements.txt с `==`, без dependabot/pip-audit; поверхность мала (нет внешних вызовов, 1 TLS-вход, netdata внутри сети).
8. **Logout-роутер живет в main.py**, а не в auth-роутере (комментарий в коде называет это намеренным) — контракт §3.1 разнесен по двум файлам.
9. **X-Forwarded-* не читаются приложением**: клиент всегда видит себя как 127.0.0.1; IP нигде не используется — риск нулевой, пока нет функций по IP/аудит.
10. **CSRF — только SameSite=Lax** (sdd §5, NFR-7 «CSRF-минимум»): без CSRF-токенов; допустимо при текущем профиле, пересмотреть при появлении публичных форм/интеграций.
11. **Wiki-поиск — линейный LIKE-скан с casefold** (python-функция на каждую строку сравнения): без FTS-индекса стоимость растет с объемом wiki; при личном объеме — норма, при росте — точка пересмотра (FTS5 или вынос в search-сервис).

## 7. Плановая дельта: video-hosting (пакет В РАБОТЕ, не «как есть»)

> Секция добавлена СА при ревью пакета (2026-10-17, ревью №1 —
> `openspec/changes/video-hosting/review-architecture.md`, verdict APPROVE).
> Это ПРОЕКТ топологии по change-пакету video-hosting (ветка
> pipeline/video-hosting): в проде пока ОТСУТСТВУЕТ. При архивации пакета
> (задача 5.3 tasks.md) сведения переводятся в тело карты (§1–§2), эта
> секция снимается.

**Новый 7-й контейнер `video`** (FastAPI, uvicorn 1 воркер :8380, статический
ffmpeg/ffprobe бинарь в образе — НЕ apt, паритет images: USER 10001, без
публикуемых портов, healthcheck, mem_limit 512m, depends_on [app]).

- **Владение данными:** таблица `video_videos` (метаданные: id/filename/
  status/size_bytes/mime/uploaded_by/created_at/convert_attempts) — владелец
  ровно один, сервис `video` (RW-своей-схемы + SELECT users); ядро НЕ пишет —
  первичное создание one-shot миграцией ядра `migrate_video` (MIGRATE_MODULE
  строго до up, паттерн migrate_gallery). Файлы — том `videos-data`
  (`<id>/original.<ext>`, `<id>/video.mp4`, `<id>/preview.jpg`): RW у video,
  ro-маунт у frontend. Вне БД и репозитория (FR-79-паттерн).
- **Шов с nginx:** `= /api/videos` + `^~ /api/videos/` → video:8380
  (X-Service: video, client_max_body_size 520m только upload, деградация
  `@videos_down` — быстрый JSON 503 при отказе, ядро не затронуто);
  `/videos/` — alias ro-маунта тома + **auth_request** `/_video_auth` →
  video:8380 `/api/videos/authcheck` (200/401 по cookie; 401 → /login,
  отказ subrequest → управляемая 503) — в отличие от публичного `/images/`,
  публичных ссылок на видео нет (ОВ-2).
- **Шов с app:** страница `/video` остается в ядре (сессия ядра, редирект
  на /login); app больше ничего: service-домен целиком у video.
- **Конвертация:** внутрипроцессный воркер (queue.Queue + 1 поток) +
  subprocess ffmpeg (nice 10, wall-clock timeout 30 мин, ровно 1 авторетрай,
  оригинал удаляется после успеха; крэш-восстановление на старте — re-enqueue
  `uploaded`+`converting`). Брокер не вводится (YAGNI).
- **Замечания к разделу:** том `videos-data` в бэкап-контур backup-sidecar
  НЕ входит (наблюдение O1 ревью №1 — решение за Заказчиком при приемке);
  третий RW-клиент SQLite (после app и images) — наследует риск Д-б/§6.5.
