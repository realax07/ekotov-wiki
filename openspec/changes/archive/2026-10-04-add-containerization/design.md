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

- Комpose-сеть внутренняя; `ports:` только у nginx — published-порт вынесен в env: `${NGINX_PORT:-10443}:10443` (дефолт 10443 = целевое состояние FR-65). `app` портов наружу не публикует — паритет localhost-only :8377 (FR-65, план §5).
- nginx-конфиг `deploy/nginx-ekotov-wiki-10443.conf` переносится в образ `services/frontend/nginx/` почти без изменений (S, план §1.2): меняются upstream (`proxy_pass http://app:8377` — DNS compose-сети вместо localhost) и пути статики.
- Статика и templates — В образе nginx (сборка копирует из `frontend/`), аватары — в томе (nginx отдает `/avatars/` через том ro). Статика в образе = кеш-бастинг `?v=` продолжает работать без изменений URL (план §1.2).
- Health: существующий `GET /api/health` (exempt, sdd §3.1a) — formalized healthcheck compose у app **без curl** (его в python:3.12-slim нет): `python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8377/api/health',timeout=5).status==200 else 1)"` (интервал 30s); nginx `depends_on: app: condition: service_healthy`. `restart: unless-stopped` на обоих.
- Stale-DNS nginx→app (отказовой режим compose): при пересоздании только app-контейнера (`up -d` с новым образом) nginx НЕ пересоздается и держит закешированный на старте IP upstream → 502. Обработка: в nginx-конфиг образа — `resolver 127.0.0.11 valid=10s` + переменная в `proxy_pass` (`set $upstream http://app:8377; proxy_pass $upstream;`); либо, если конфиг-переменные не применяются, явный шаг `docker compose restart nginx` после `up` в deploy.sh v2 (tasks 1.6). Проверка сценария «up нового образа app → nginx не 502» — в смоуке 1.6.

- Проверка паритета (FR-64): смоук контейнерного стенда сверяет коды ответов всех маршрутов монолита с systemd-эталоном: API — `GET /api/auth/me`, `GET /api/board`, `GET+POST /api/categories`, `GET /api/profile`, `PUT /api/profile`, `POST /api/profile/avatar`, `POST /api/profile/password`, `GET /api/search`, `POST /api/search/advanced`, `GET /api/suggestions`, `GET /api/suggestions/users`, `GET /api/users`, `POST /api/tasks` (создание), `POST /api/auth/login`, `POST /api/auth/logout` (плюс exempt `GET /api/health`); страницы — `GET /board`, `GET /search`, `GET /settings`, `GET /settings/profile`, `GET /wiki` (без сессии — редирект на login), `GET /login`. Параметризованные маршруты (перемещение задачи и т.п.) покрываются web-сьютом против стенда (tasks 2.2).

## 2. Образы

- `services/app/Dockerfile`: python:3.12-slim, копия `backend/` → `pip install -r requirements.txt` (пины сохранены — Pillow, python-multipart), CMD uvicorn 1 воркер, порты 8377. Пользовательские данные в образ НЕ попадают (FR-66).
- `services/frontend/Dockerfile`: nginx:stable-alpine, копия конфига + `frontend/static/` + `frontend/templates/` (Jinja2-шаблоны рендерит app — шаблоны нужны в app-образе; в nginx — только статика; уточнение против черновика структуры плана §2.2: шаблоны остаются в app-образе).
- Тегирование: `ekotov-wiki/app:<release>` / `ekotov-wiki/frontend:<release>`; `latest` не используется (FR-72). ЭТАП 1 — сборка на VPS из клона (ОВ-2=(а) допустим); registry — ЭТАП 2+. Принятый риск (план ОВ-2): сборка двух образов на VPS 3.9 GB идет параллельно с живым продом — выполняется вне часов пик, образы собираются последовательно (tasks 1.1→1.2); после релиза — `docker image prune -f` (каждый деплой оставляет dangling-слои; диск 49G/37% — запас есть, но контролируется), команда фиксируется в RUNBOOK (раздел 1.6).

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
- Middleware: exempt-список НЕ расширяется, middleware НЕ меняется. Без сессии схема не раскрывается публично: фактически middleware (ветка страниц — `backend/app/middleware.py`) отвечает на `/openapi.json` редиректом на login (302 → /login) — это и есть фиксируемое поведение (вариант 401 недостижим без правки middleware и не требуется); CI — fetch под тестовой сессией. Это дополнение к спеке auth (exempt-список исчерпывающий), а не изменение exempt-правила.
- Экспорт: скрипт `scripts/export_openapi.py` (app client под тестовой сессией → `contracts/openapi.json`). Несовместимый дифф зафиксированной схемы — материал для gate ЭТАПА 2 (в этом пакете gate не строится — одно изменение инфры в шаге, tasks 0.3).

## 5. e2e-сьют (FR-69, план §4)

- `e2e/` в корне монорепо; playwright, хелперы/фикстуры переиспользованы из `tests/web` (та же база).
- Против `deploy/compose.test.yaml`: проверяются заголовки кеша статики (`expires 7d`), gzip, security-заголовки — то, что web-стенд на `http.server` не эмулирует (architecture/map.md §6.1, класс DEF-002/003).
- Прод-смоук НЕ заменяется: RUNBOOK §4.4 + `scripts/smoke_static.py` проверяют живой TLS и конфиг хоста, которых в стенде нет.

## 6. Деплой и миграции (план §5–6)

- `deploy/deploy.sh` — эволюция, не rewrite: шаги rsync/pip/схема заменяются `docker compose build/up`; миграция-шаг и смоук остаются (FR-71). **Бэкап при named volume** (метод зафиксирован до реализации, урок Р4): БД — `sqlite3 .backup` через `docker exec` в контейнер `app` (`docker exec <app> python -c "import sqlite3; sqlite3.connect('/data/wiki.db').backup(sqlite3.connect('/data/backup/wiki.db'))"`) — python:3.12-slim не содержит sqlite3 CLI, но содержит модуль `sqlite3` в python; альтернатива — one-shot-контейнер с тем же образом (`docker compose run --rm app python -c …`) или хостовой `sqlite3 .backup` по пути тома `/var/lib/docker/volumes/<project>_wiki-data/_data/wiki.db` (root; путь стабилен, но выбирается exec-метод как основной). Аватары — tar каталога `/data/avatars` тома тем же exec/one-shot-контейнером. Бэкап выполняется без остановки сервиса.
- Миграции: `docker compose run --rm app python -m app.migrate_rN` — one-shot из того же образа, строго до `up` нового app; идемпотентность обязательна (FR-70, урок Р4 2026-09-30); репетиция на копии прод-БД со старой схемой — три конфигурации (старая / смигрированная / свежая с данными пользователей).
- Первый контейнерный деплой — переходная схема портов (закрытие коллизии 10443 с хостовым nginx, NFR-9): **фаза 1 (параллельная проверка, tasks 2.3)** — контейнерный стек поднимается с `NGINX_PORT=10444` (контейнерный nginx публикует `10444:10443`), хостовой nginx продолжает держать 10443 и обслуживать прод — коллизии порта нет, systemd-прод не тронут; **фаза 2 (переключение, tasks 2.4)** — операция переключения состоит из двух действий одного шага: (1) освобождается 10443 — отключается сайт хостового nginx (`rm sites-enabled/…` + `systemctl reload nginx`, либо `systemctl stop nginx`) и (2) публикуется 10443 контейнером — `NGINX_PORT=10443 docker compose up -d` (compose пересоздает только nginx-контейнер). Разрыв между действиями — секунды; systemd-юнит остановлен, но не удален (чекпоинт отката NFR-9 — возврат: `NGINX_PORT=10444 docker compose up -d` (или `stop`) + возврат sites-enabled + `systemctl start/reload nginx`).
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
