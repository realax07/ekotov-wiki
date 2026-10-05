# tasks.md — add-microservices-full

Флоу-порядок: ЭТАП A (контракт) → ЭТАП B (выделение) → ЭТАП C (проверка и переход). Правило: 1 задача = 1 dev-сабагент + независимый ревьюер; ops-задачи — протокол приемки Заказчика (ai-factory 0518e06); ворота — `openspec validate --all --strict` green на каждом шаге.

## ЭТАП A. Контракт и каркас (S)

- [x] 0.1 [S] SA: заморозка контракта поиска — `contracts/openapi-search.json`: экспорт схемы маршрутов `/api/search*` + `/api/suggestions` из монолита (тестовая сессия, `scripts/export_openapi_search.py` по образцу export_openapi.py); проверка «экспорт = зафиксированный файл» на пустом диффе; в `contracts/openapi.json` (app) маршруты поиска помечены `deprecated: true` с аннотацией «переезд в search-сервис». Одно инфраизменение: только контракты+скрипт. (design §3; план §3)
- [x] 0.2 [P] [S] SA: каркас `services/search/` — каталог по структуре monorepo (app/, tests/, openapi.yaml, README), `services/backup/` (README), правка `services/README.md` (статусы: search — в работе, backup — в работе, auth — не выделяется, решение плана §1.2). Без изменения кода. (design §2; план §6)
- [x] 0.3 [S] Devops: тест-каркас контрактного гейта — `tests/api/test_openapi_search_service.py` (заготовка: «экспорт = файл» + «ядро не содержит маршрутов поиска» — падает до выделения, xfail с причиной; активируется задачей 1.3). (design §4; план §3)

## ЭТАП B. Выделение сервисов (M)

- [x] 1.1 [M] Dev: код `services/search/app/` — перенос `search.py` + `suggestions.py` (роутеры как есть), мини-main (FastAPI, healthcheck `/api/health` на 8378, openapi_url включен, сессионный запрет схемы без сессии — паттерн ядра), `row_schema.py` (копия TASK_COLUMNS/_row_to_task с трассировкой на `backend/app/tasks.py`), db-слой (get_connection, WAL, foreign_keys). Юнит-тесты сервиса (поиск по фикс. БД). Границы: только `services/search/`. (design §2; план §1.2)
- [ ] 1.2 [S] Devops: `services/search/Dockerfile` (python:3.12-slim, uvicorn 1 воркер :8378, healthcheck urllib, USER 10001, данных в образе нет) + `deploy/compose.yaml`: сервис search (mem_limit 512m, том `wiki-data:/data:ro`, depends_on app — НЕ service_healthy: search читает независимого), backup-сервис (`services/backup/`: python-slim, cron-цикл, mem_limit 64m, bind `/var/backups/ekotov-wiki`, том ro). Стенд `compose.test.yaml` — те же сервисы. (design §1, §5, §7; FR-73 паритет)
- [x] 1.3 [M] Devops: nginx-маршрутизация в образе frontend — `location /api/search`, `location /api/suggestions` → `proxy_pass http://search:8378` (resolver 127.0.0.11 + переменная), остальные → app; `X-Service` заголовок; 503-деградация при остановленном search (proxy_next_upstream + error_page). Проверка на стенде: поиск через 8443 = 200, X-Service: search; app без маршрутов поиска. (design §1, §4; FR-65 паритет)
- [x] 1.4 [M] Devops: `deploy/deploy.sh` v3 — матрица SERVICES (build всех, тег каждого), порядок: бэкап → build → миграция ядра → up app → healthy → up search/backup → healthy → смоук-матрица (health×2, поиск+X-Service через nginx, статика, аватары, 502=0, «образы = релизные теги»). DRY_RUN на всю матрицу. Релизный бэкап остается в деплое (sidecar — между релизами). (design §6; FR-70/71/72 паритет)
- [x] 1.5 [S] Dev: активация контрактного гейта (0.3): xfail снимается; «экспорт search = файл» green; «ядро без маршрутов поиска» green — `backend/app/main.py` минус search_router/suggestions_router, `backend/app/search.py`/`suggestions.py` остаются как источник истины для сервиса (импорт в main удален; файлы переносятся в services/search/app/ в 1.1, здесь удаляются из backend — git mv трассировка). Регресс api: search/suggestions-тесты против стенда с сервисом — green (URL те же). (design §2–§4)

## ЭТАП C. Проверка и переход (M)

- [ ] 2.1 [M] QA: полный регресс на коде пакета — api-сьют (весь, включая переезжающие search-тесты), web-сьют, e2e против стенда с матрицей сервисов; падения — баг-репортами в test-model/bugs/. (FR-64 паритет; tasks 2.2 образца add-containerization)
- [ ] 2.2 [S] QA: стенд-матрица — подъем/останов каждого сервиса по отдельности (деградационные сценарии design §4/§8): stop search → 503 от nginx; stop backup → деплой-бэкап работает; лимиты памяти — docker stats в пределах; свободная память хоста ≥ 2 GB. (design §7–§8)
- [ ] 2.3 [S] [ops] Devops + Заказчик: прод-параллель — полный стек на :10444 рядом с текущим контейнерным продом (:10443), приемка Заказчика браузером (поиск, доска, аватар-загрузка), systemd/текущий прод не тронуты, план отката — предыдущий тег. (NFR-9 паритет; урок 2.3 add-containerization: смоук записи, не только чтения)
- [ ] 2.4 [S] [ops] Devops + Заказчик: переключение — бэкап → up полного стека на :10443 → смоук-матрица → проход Заказчика. Откат: предыдущий RELEASE_TAG одного compose-up. (design §8; урок 2.4)
- [ ] 2.5 [S] [docs] SA: документация по факту — map.md (топология с search/backup), sdd.md r13 (сервисный разрез, границы, RO-профиль), RUNBOOK (матрица деплоя, откат по сервисам); пометка наблюдения после перехода. (паритет 2.5 add-containerization)

## Ворота и правила

- `openspec validate --all --strict` — green на каждом шаге; migration-шаг активируется только после репетиции на копии (урок Р4; репетиция НЕ нужна для search — он не мигрирует схему).
- Ops-задачи (2.3/2.4) — только с явным участием Заказчика; артефакт — протокол приемки (ai-factory 0518e06), не review-файл.
- Одно инфраизменение в шаге: 1.2 (compose) → 1.3 (nginx) → 1.4 (deploy.sh) — последовательно.

## Порядок архивации

Пакет `add-containerization` архивируется ПЕРЕД этим пакетом (его deploy-дельта создает master-спеку `deploy`, на которую ссылаются MODIFIED-дельты отсюда). INFO-предупреждение валидатора об archive — ожидаемо до тех пор.
