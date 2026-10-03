# Design: add-containerization (ЭТАП 0+1 плана P11)

## Context

ТЗ `requirements.md` r1 (УТВЕРЖДЕН, FR-64…FR-74, NFR-9…NFR-11). Нормативный план: `docs/ba/architecture-services-plan.md` §1–6, §8 (решения Заказчика + факты VPS). Решение: `decisions/2026-10-03-p11-containerization.md`. Фактура плана сверена с кодом (main `eae7bfc`); факты VPS проверены 2026-10-03 (§8). Этот design не дублирует план — фиксирует техрешения виртуализации, отсылая к разделам плана, и закрывает детали, которых план не задал.

## 1. Контейнерная топология (ЭТАП 1)

```
браузер ──HTTPS :10443──> [nginx-контейнер]  ──/static/*, /avatars/* (из образа/тома)
                            │  TLS: mount /etc/nginx/ssl/ekotov-wiki.{crt,key} (ro)
                            └─proxy / → app:8377
                        [app-контейнер: uvicorn, 1 воркер, порты не публикуются]
                            └─ SQLite wiki.db + avatars/ → named volume wiki-data (RW)
```

- Комpose-сеть внутренняя; `ports:` только у nginx (`10443:10443`). `app` портов наружу не публикует — паритет localhost-only :8377 (FR-65, план §5).
- nginx-конфиг `deploy/nginx-ekotov-wiki-10443.conf` переносится в образ `services/frontend/nginx/` почти без изменений (S, план §1.2): меняются upstream (`proxy_pass http://app:8377` — DNS compose-сети вместо localhost) и пути статики.
- Статика и templates — В образе nginx (сборка копирует из `frontend/`), аватары — в томе (nginx отдает `/avatars/` через том ro). Статика в образе = кеш-бастинг `?v=` продолжает работать без изменений URL (план §1.2).
- Health: существующий `GET /api/health` (exempt, sdd §3.1a) — formalized healthcheck compose: `healthcheck` у app (curl /api/health, интервал 30s), nginx `depends_on: app: condition: service_healthy`. `restart: unless-stopped` на обоих.

## 2. Образы

- `services/app/Dockerfile`: python:3.12-slim, копия `backend/` → `pip install -r requirements.txt` (пины сохранены — Pillow, python-multipart), CMD uvicorn 1 воркер, порты 8377. Пользовательские данные в образ НЕ попадают (FR-66).
- `services/frontend/Dockerfile`: nginx:stable-alpine, копия конфига + `frontend/static/` + `frontend/templates/` (Jinja2-шаблоны рендерит app — шаблоны нужны в app-образе; в nginx — только статика; уточнение против черновика структуры плана §2.2: шаблоны остаются в app-образе).
- Тегирование: `ekotov-wiki/app:<release>` / `ekotov-wiki/frontend:<release>`; `latest` не используется (FR-72). ЭТАП 1 — сборка на VPS из клона (ОВ-2=(а) допустим); registry — ЭТАП 2+.

## 3. Тома, env, лимиты

| Что | Решение |
|---|---|
| Данные | named volume `wiki-data`: `wiki.db` + `avatars/` (RW для app, ro-маунт для nginx `/avatars/`) — FR-66 |
| TLS | bind-mount `/etc/nginx/ssl/ekotov-wiki.{crt,key}` → nginx, ro — FR-74 (перевыпуск не нужен до 2028-12-22) |
| env app | `SECRET_KEY`, `DB_PATH=/data/wiki.db`, `AVATARS_DIR=/data/avatars` (постановка П11 п.2); `.env` вне git, паритет с EnvironmentFile systemd-юнита |
| Лимиты | `mem_limit`: nginx 64m, app 512m — FR-73; воркеров 1; резерв хосту ≥ 2 GB (VPS 3.9 GB total) |
| Логи | `logging: json-file`, `max-size: 10m`, `max-file: 3` на каждый контейнер — NFR-11 |
| Стенд | `deploy/compose.test.yaml`: тот же образ, tmp-том БД, seeded-юзер, порт 8443 (иначе, чем прод 10443) — FR-67/NFR-10 |

## 4. Машинный контракт OpenAPI (FR-68, план §3 вариант А)

- `backend/app/main.py`: `openapi_url="/openapi.json"`, `docs_url=None, redoc_url=None` — единственная правка кода продукта в пакете.
- Middleware: exempt-список НЕ расширяется — `/openapi.json` под 401 без сессии (план §3: публично не раскрывать; CI — fetch под тестовой сессией). Это дополнение к спеке auth (exempt-список исчерпывающий), а не изменение exempt-правила.
- Экспорт: скрипт `scripts/export_openapi.py` (app client под тестовой сессией → `contracts/openapi.json`). Несовместимый дифф зафиксированной схемы — материал для gate ЭТАПА 2 (в этом пакете gate не строится — одно изменение инфры в шаге, tasks 0.3).

## 5. e2e-сьют (FR-69, план §4)

- `e2e/` в корне монорепо; playwright, хелперы/фикстуры переиспользованы из `tests/web` (та же база).
- Против `deploy/compose.test.yaml`: проверяются заголовки кеша статики (`expires 7d`), gzip, security-заголовки — то, что web-стенд на `http.server` не эмулирует (architecture/map.md §6.1, класс DEF-002/003).
- Прод-смоук НЕ заменяется: RUNBOOK §4.4 + `scripts/smoke_static.py` проверяют живой TLS и конфиг хоста, которых в стенде нет.

## 6. Деплой и миграции (план §5–6)

- `deploy/deploy.sh` — эволюция, не rewrite: шаги rsync/pip/схема заменяются `docker compose build/up`; бэкап БД (шаг 2 — без изменений, `sqlite3 .backup` + аватары), миграция-шаг и смоук остаются (FR-71).
- Миграции: `docker compose run --rm app python -m app.migrate_rN` — one-shot из того же образа, строго до `up` нового app; идемпотентность обязательна (FR-70, урок Р4 2026-09-30); репетиция на копии прод-БД со старой схемой — три конфигурации (старая / смигрированная / свежая с данными пользователей).
- Первый контейнерный деплой — параллельно с systemd на другом порту; переключение — один reload хостового nginx; systemd-юнит остановлен, но не удален (NFR-9, откат за минуты).
- Откат: предыдущий тег; несовместимая схема — возврат БД из пред-деплойного бэкапа парой «код+БД» (FR-72). RUNBOOK обновляется тем же пакетом.

## 7. Исследованные альтернативы (сводка плана §2–§3, решения зафиксированы §8)

| Вопрос | Выбрано | Альтернатива — почему нет |
|---|---|---|
| Топология | контейнеризация монолита как есть (ЭТАП 1) | сразу разбор на сервисы: границы без транзакционности на общей SQLite (инвариант fast line — одна транзакция `tasks.py`), нагрузка 2 пользователей не окупает |
| Репозиторий | монорепо, границы каталогами `services/` | полирепо: N×CI, синхронизация контрактов, сквозные тесты теряют атомарность (позиция Заказчика «кучу реп не хочу») |
| Контракты | OpenAPI-схема + CI-gate (ЭТАП 2) | pact-брокер избыточен при ≤2 сервисах; e2e отдельно — ловит поломку поздно (оставлен страховкой) |
| DevOps | compose, один файл прод + файл стенда | systemd поверх контейнеров — лишний слой; k8s — несоразмерно |
| TLS | в контейнерный nginx, сертификат томом (ОВ-3=б) | TLS на хостовом nginx — два nginx-слоя постоянно; сертификат действует до 2028 |
| Темп | пауза после ЭТАПА 1 (ОВ-1=а) | сразу ЭТАП 2 — первое изменение кода в новой инфре без недели эксплуатации |
