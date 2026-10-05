# Design: add-microservices-full

Версия: r1 (2026-10-03). Источники: план P11 `docs/ba/architecture-services-plan.md` §1.2–§3, §8; proposal этого пакета; боевой опыт add-containerization (deploy/RUNBOOK §7, docs/containerization-deploy-lessons.md фабрики).

## §1. Целевая топология

```
Браузер ── https://194.58.34.122:10443 ── nginx [frontend-контейнер]
   ├── /static/          → из образа frontend (как сейчас)
   ├── /avatars/         → том wiki-data ro (как сейчас)
   ├── /api/search*      → proxy_pass http://search:8378   (НОВОЕ)
   ├── /api/suggestions  → proxy_pass http://search:8378   (НОВОЕ)
   └── остальное (/ и /api/*) → proxy_pass http://app:8377
                              ├── app [ядро: auth, tasks, board, categories,
                              │        comments, profile, users, страницы Jinja2]
                              │     └── SQLite RW → том wiki-data (/data)
                              └── search [search + suggestions, uvicorn :8378]
                                    └── SQLite RO → тот же том, маунт ro

backup [sidecar, cron] → том ro → /var/backups/ekotov-wiki (bind хоста)
```

- Порты внутри compose-сети: app 8377 (не публикуется), search 8378 (не публикуется).
- Для браузера URL не меняются: маршрутизацию делает nginx по location.
- resolver 127.0.0.11 + переменная в proxy_pass — на всех proxy-локациях
  (анти-stale-DNS, урок design add-containerization §1).

## §2. Границы search-сервиса

- Код: `backend/app/search.py` + `backend/app/suggestions.py` →
  `services/search/app/` (собственный мини-main: FastAPI, include обоих
  роутеров, /api/health на 8378, openapi_url="/openapi.json" — контракт
  сервиса, схема не публикуется без сессии тем же middleware-паттерном).
- Зависимости: `app.db.get_connection` (копия db-слоя в сервис — общий модуль
  НЕ шарится между образами; дублирование 30 строк осознанное, план §1.2
  «механический перенос»), `TASK_COLUMNS`/`_row_to_task` из tasks.py —
  копируются в `services/search/app/row_schema.py` с комментарием-трассировкой
  на источник; расхождение ловит контрактный тест (§4).
- Доступ: маунт `wiki-data:/data:ro` — файловая гарантия read-only; DB_PATH
  тот же /data/wiki.db.
- Что НЕ входит: страницы /search Jinja2 (рендерит app; search.html грузится
  как раньше, ее JS зовет те же URL — nginx разруливает).

## §3. Контракт до кода (план §3)

1. Заморозка: `scripts/export_openapi_search.py` поднимает search-сервис
   локально (тестовая сессия) → `contracts/openapi-search.json` коммитом
   ДО выделения; `/api/search*` + `/api/suggestions` в контракте app-схемы
   помечаются deprecated → удаляются из app-схемы тем же PR, что включает
   search-сервис (дифф схемы = план перехода).
2. Потребители: search.js (браузер) — URL не меняются, контрактные тесты
   потребителя = существующие api-тесты поиска, прогнанные против стенда
   с сервисом (набор тот же — маршрут прозрачен).

## §4. Контрактный CI-gate

- Тест `tests/api/test_openapi_search_service.py`: экспорт search-сервиса =
  зафиксированный `contracts/openapi-search.json` (пустой git-дифф);
  ядро не содержит маршрутов /api/search* (grep + 404/405 проверка);
  nginx-маршрутизация: на стенде /api/search через 8443 отвечает 200 и
  заголовок сервиса (search добавляет `X-Service: search`).
- Деградационный тест: остановленный search-контейнер → /api/search на
  стенде отдает 503 от nginx (не таймаут, не 502-залипание) —
  `proxy_next_upstream` + `error_page 502 503 504` в конфиге.

## §5. Backup-service

- `services/backup/`: алярм-контейнер на базе python:3.12-slim с cron
  (или loop `while true; sleep 86400`): sqlite3 .backup тома + tar avatars →
  bind `/var/backups/ekotov-wiki` (как deploy.sh), retention 14 дней.
- deploy.sh: шаг 2/7 (бэкап) вызывает ТОТ ЖЕ модуль/скрипт (без дубля кода),
  cron-расписание — страховка между деплоями. Релизный бэкап остается
  обязательным шагом деплоя (урок Р4), sidecar — между релизами.

## §6. Deploy.sh v3: матрица сервисов

- Конфиг матрицы в шапке: `SERVICES="app frontend search backup"`,
  теги `ekotov-wiki/<name>:<RELEASE_TAG>`.
- Порядок: бэкап (до всех) → build всех → миграция (ядро; читатели
  search/backup не требуют миграций — схема одна) → up app → healthy →
  up search/backup → healthy → смоук-матрица: health app, health search,
  поиск через nginx 200 + X-Service, статика, аватары, 502=0.
- Откат: тегами каждого сервиса; совместимая пара (app+search) — один
  RELEASE_TAG по умолчанию; раздельный тег допускается при горячем фиксе
  одного сервиса (RUNBOOK).
- DRY_RUN — как в v2, на всю матрицу.

## §7. Ресурсы (VPS 3.9 GB)

| Сервис | mem_limit |
|---|---|
| app | 512m |
| frontend | 64m |
| search | 512m |
| backup | 64m (пик при tar) |
| **резерв хосту** | **≥ 2.7 GB** (системда-хвосты, бэкапы, page cache) |

Uvicorn 1 воркер везде. Наблюдение — ежедневная проверка паузы эксплуатации
(map.md §1.3): свободная память хоста, 502 в логах, healthcheck-рестарты.

## §8. Откаты (матрица, план §8 п.3)

| Отказ | Откат |
|---|---|
| search тормозит/течет | `docker compose stop search` + nginx location /api/search → app (запасной конфиг в образе frontend, включается env-флагом) + объединенный тег app с возвращенными роутерами (коммит-заготовка держится веткой) |
| backup шумит | stop backup (деплой-бэкап остается в deploy.sh) |
| Том/БД | как add-containerization: предыдущий RELEASE_TAG + бэкап |

## §9. Этапы (внутри пакета)

- **ЭТАП A (контракт):** заморозка openapi-search.json + каркас services/search
  (0.1∥0.2 → 0.3 экспорт, 0.4 каркас backup)
- **ЭТАП B (выделение):** 1.1 код search-сервиса → 1.2 Dockerfile+compose →
  1.3 nginx-маршрутизация → 1.4 deploy.sh v3 матрица → 1.5 backup-sidecar
- **ЭТАП C (проверка и переход):** 2.1 регресс полный (api+web+e2e) →
  2.2 стенд-матрица → 2.3 прод-параллель (:10444, приемка Заказчика) →
  2.4 переключение → 2.5 доки (map/sdd/RUNBOOK)

Ворота: openspec validate --strict на каждом шаге; правило конвейера:
1 задача = 1 dev-сабагент + независимый ревьюер; ops-задачи — по протоколу
приемки (ai-factory 0518e06).

## §10. Осознанные не-цели

- auth не выделяется (план §1.2: L, не рекомендован).
- Событийной шины нет (план §1.3).
- Отдельная БД для search — нет (RO того же тома; разнесение схем = отдельный
  будущий пакет при реальной необходимости).
- Pact/брокер контрактных тестов — нет (план §3: выигрывает при 5+ сервисах).
