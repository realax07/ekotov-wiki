# REPORT-regress-21 — полный QA-регресс пакета add-microservices-full (задача 2.1)

- **Дата:** 2026-10-05
- **Ветка:** `add-microservices-full`, HEAD `785fa39` («ЭТАП B закрыт (flow_check
  OK); 2.1 QA-регресс запущен через ворота»; кодовая база = `54213db` + docs)
- **Корреляция flowctl:** `9ba2c5ec1030458f81c906b9150fa425`
- **Зона записи:** tests/, test-model/bugs/, openspec/.../tasks.md (чекбокс 2.1
  НЕ снимается — закрывает ПМ после ревью).

## 1. Итог по сьютам (точные числа)

| Сьют | Результат | Время |
|---|---|---|
| `tests/api` + `tests/test_walkthrough_probe.py` (212 тестов, маршрутизированный стенд) | **201 passed, 9 skipped, 2 xfailed, 0 failed, 0 errors** | 114 c |
| `services/search/tests/` (TestClient, без стенда) | **12 passed, 0 failed**, 1 warning (deprecation `ast.Str`) | 1.3 c |
| `pytest tests/` (совместный сбор api+web+probe) | **1 error на КОЛЛЕКЦИИ** → BUG-006 (pytest 8+ hard error на `pytest_plugins` в tests/web/conftest.py:47) | — |
| services/backup, services/auth | тестов в репозитории нет (backup-логика верифицируется репликацией `main()` — REPORT-fix-12g; auth не выделяется по плану §1.2) | — |

Состав skip в api-сьюте (проверено составом, не env): 2 × manual-рестарт НФТ
(TC-tasks-015/016), 1 × bcrypt-БД НФТ, UI-fastline/web_ui-skip, TC-sel-102
(manual-запрет автоматизации) — ожидаемые по tests/README.md. xfailed —
BUG-002 (strict; XPASS не зафиксирован).

Логи: `/tmp/pytest-api-final.log`, `/tmp/pytest-search.log` (вне репо).

## 2. Стенд

Прод-топология пакета воспроизведена локально БЕЗ docker (docker недоступен
под текущим юзером — см. §5):

- **app** (монолит, backend/app): uvicorn 127.0.0.1:8080;
  `DB_PATH=/tmp/app.db SECRET_KEY=<hex> AVATARS_DIR=/tmp/app-avatars`.
- **search** (services/search/app): uvicorn 127.0.0.1:8378 — тот же SQLite через
  `EKOTOV_WIKI_DB_PATH=/tmp/app.db` (RO-профиль сервиса: запись в БД сервисом
  не выполняется; в контейнере ro-маунт, локально — общий файл).
- **nginx** (:18443, HTTP): паритет `services/frontend/nginx/ekotov-wiki.conf` +
  `search-proxy.inc`/`search-headers.inc` — точные match'и `= /api/search`,
  `^~ /api/search/`, `= /api/suggestions`, `^~ /api/suggestions/` → search;
  остальное → app; X-Service только на search-семействе; 503-деградация через
  proxy_next_upstream + error_page @search_down.
- БД: свежая схема (`python -m app.db`) → seed owner/wife (программно,
  `app.seed_users.seed_user`, bcrypt) → **`python -m app.migrate_r4`**
  (обязателен: без него wife.role=NULL → TC-profile-002 красный; владелец
  `b87384c` подтверждает эталон «чистая БД+seed+migrate_r4»).
- Health перед прогоном: `:8080/api/health` = `{"status":"ok"}`,
  `:8378/api/health` = `{"status":"ok"}`, `:18443/api/health` (через nginx) = 200.

Стенд погашен после прогона (uvicorn ×2 + nginx -s quit).

## 3. Смоук-проверка маршрутизации (п.4 задачи, заменяет docker-стенд)

Проверено против локального nginx-контура (гейты задачи 1.3):

- `GET /api/search` авторизованно через nginx → **200, X-Service: search**;
  `/api/suggestions`, `/api/suggestions/users` — так же; `/api/board` → 200
  БЕЗ X-Service (не заехал search) — гейт TC-openapi-203 **green**
  (tests/api/test_openapi_search_service.py: 3 passed в общем прогоне).
- **Деградация:** SIGSTOP search-процесса → `/api/search` через nginx →
  **управляемый 503** `{"error": "search service unavailable"}` + `Retry-After: 5`
  + X-Service: search (паритет search-headers.inc в @search_down) — не 502,
  не клиентский таймаут; после SIGCONT — самовосстановление в 200.
- `app` содержит ровно 0 search-маршрутов (TC-openapi-202 green — гейт 1.5
  f0fe4ec); контракт заморожен (TC-openapi-201 green).
- Замеченное отличие стенда от образа (не продукт): nginx `client_max_body_size`
  поднят 2m→64m (multipart-тела гейт-кейсов аватаров — 2 097 322 и 27 МБ —
  иначе режутся 413 до валидации app; прод-лимит «исходник ≤ 2 MiB» обеспечивает
  `MAX_AVATAR_BYTES` в app, что и проверяют кейсы); TLS не терминировался
  (self-signed ронял штатный health-poll conftest; на семантику тестов не влияет).
- compose-стенд deploy/compose.test.yaml НЕ поднимался: docker недоступен
  под текущим пользователем (см. §5). Прод-parитет TLS/X-Service/limits
  образа остается на стенд-матрицу 2.2 / прод-параллель 2.3.

## 4. Баг-репорты

| Файл | Суть | Severity |
|---|---|---|
| `test-model/bugs/BUG-006-pytest-plugins-nonroot-conftest-collection-error.md` | `pytest tests/` падает на сборе: `pytest_plugins = ["pytest_playwright"]` в не-корневом tests/web/conftest.py:47 — hard error на pytest 8+; эталонная команда tests/README.md неисполнима; обход — покаталоговый запуск (использован здесь) | major |

Остальные падения первого прогона — артефакты стенда, а не продукта (устранены
в этой сессии, повторно green): отсутствие migrate_r4 (роли), AVATARS_DIR,
env-пароли vs дефолтные в тестах, QAT-хвосты справочника от прогона с
отрезанным search (teardown-поиск через 404), 413 nginx, отсутствие
search-сервиса на :8378. Новых продуктовых дефектов сверх известных
(BUG-001 web — вне api-скопа, BUG-002 xfail) регресс не выявил.

## 5. Ограничения

1. docker/`compose.test.yaml` — не проверялись (права); компенсация —
   nginx-контур §3 + задачa 2.2 (стенд-матрица) и 2.3 (прод-параллель).
2. web-сьют (playwright) в этой сессии не гонялся — вне делегированного
   скопа стенда; `pytest tests/` до исправления BUG-006 всё равно не собирается.
3. Стенды search/app в docker-профиле (ro-маунт тома, USER 10001, mem_limit)
   не воспроизводились — RO-инварианты покрыты юнит-сьютом сервиса
   (TC-211…214, включая immutable=1-fallback на ro-каталоге).
