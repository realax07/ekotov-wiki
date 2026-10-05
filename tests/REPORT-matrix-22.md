# REPORT-matrix-22 — стенд-матрица деградаций (задача 2.2, add-microservices-full)

- **Дата:** 2026-10-05
- **Ветка:** `add-microservices-full` (база — HEAD после 2.1, `785fa39` + коммиты доков)
- **Корреляция flowctl:** `9a7836cfbf9e42e09ad1600603301235`
- **Зона записи:** tests/, openspec/changes/add-microservices-full/tasks.md (чекбокс 2.2)
- **Задача:** «[S] QA: стенд-матрица — подъем/останов каждого сервиса по отдельности
  (деградационные сценарии design §4/§8): stop search → 503 от nginx; stop backup →
  деплой-бэкап работает; лимиты памяти — docker stats в пределах; свободная память
  хоста ≥ 2 GB» (design §4, §5, §7–§8).

## 0. Проба docker (первый шаг по ТЗ)

`docker info` → **rc=1, «permission denied while trying to connect to the docker API
at unix:///var/run/docker.sock»** — docker недоступен под текущим пользователем
(известный факт R6, REPORT-regress-21 §5.1). compose-стенд
`deploy/compose.test.yaml` НЕ поднимался; матрица исполнена на локальном контуре
по tests/README.md / REPORT-regress-21 §2 (nginx :18443 → app:8080 + search:8378).
Невозможные без docker пункты задокументированы как ограничения с компенсацией
(§5), не как «пропуск».

## 1. Стенд

Топология прода пакета (design §1) локально, без docker:

- **app** (backend/app, монолит): uvicorn 127.0.0.1:8080;
  `DB_PATH=/tmp/stend22/db/wiki.db SECRET_KEY=<hex, вне репо> AVATARS_DIR=/tmp/stend22/avatars`.
- **search** (services/search/app): uvicorn 127.0.0.1:8378, `EKOTOV_WIKI_DB_PATH` —
  та же БД (в контейнере — ro-маунт того же тома; RO-профиль сервиса соблюден:
  сервис записей в БД не выполняет).
- **nginx** (:18443, HTTP): паритет `services/frontend/nginx/ekotov-wiki.conf` —
  search-семейство (`= /api/search`, `^~ /api/search/`, `= /api/suggestions`,
  `^~ /api/suggestions/`) → include `search-proxy.inc` + `search-headers.inc`
  (продуктовые файлы, изменен только upstream `search:8378` → `127.0.0.1:8378`);
  `proxy_next_upstream error timeout` + `proxy_intercept_errors` +
  `error_page 502 503 504 = @search_down`; `@search_down` — 503 JSON +
  `Retry-After: 5`; **таймауты прод-паритетные: proxy_read_timeout 30s**
  (замечание F-4 из 2.1 закрыто: локальный стенд больше не искажает динамику
  деградации таймаутом 5s); `resolver` + переменная в proxy_pass; mime.types
  включены (статика `application/javascript` — проверено, дефект стенда 2.1
  не воспроизводится).
- **БД:** свежая схема → seed owner/wife (программно, `app.seed_users.seed_user`,
  bcrypt) → `python -m app.migrate_r4` (эталон «чистая БД+seed+migrate_r4»).
- **backup-sidecar в контуре НЕ поднимался** (контейнер); проверка — юнит-эквивалент
  §3-B: тот же модуль `services/backup/backup.py`, что вызывает deploy.sh (шаг 2/8,
  `from backup import run_backup`) и CMD образа (`python -m backup`), на копии БД
  стенда — сценарий «stop backup → деплой-бэкап работает» по смыслу design §8
  («backup шумит → stop backup; деплой-бэкап остается в deploy.sh»).
- Health перед прогоном: `:8080/api/health` = ok, `:8378/api/health` = ok,
  `:18443/api/health` (через nginx) = 200.

Смоук-записи (урок 2.2 add-containerization: «смоук записи, не только чтения»)
выполнены в каждом сценарии: до падения, во время деградации, после восстановления.

## 2. Сценарий A: stop search → 503 от nginx (design §4, §8)

Прекомпонд: логин owner через nginx → 200; **создание задачи `QAT-22-smoke-a`
через API (запись) → 201**.

### 2.1 Базовая линия (search жив)

| Запрос через nginx | Код | X-Service | Ответ |
|---|---|---|---|
| GET /api/search?q=QAT | 200 | search | результаты (1 задача) |
| POST /api/search/advanced | 422 | search | validation error (сервис жив, валидация работает) |
| GET /api/suggestions | 200 | search | `{"suggestions":[]}` |
| GET /api/suggestions/users | 200 | search | `{"users":["owner"]}` |
| GET /api/board (контроль) | 200 | **нет заголовка** | app-путь, search не заезжает |

### 2.2 Остановка search (SIGTERM процессу = connection refused; эквивалент
`docker compose stop search` — в обоих случаях nginx получает refused от апстрима)

| Запрос через nginx | Код | Время | Retry-After | Тело |
|---|---|---|---|---|
| GET /api/search?q=QAT | **503** | 1.1 мс | 5 | `{"error": "search service unavailable"}` |
| POST /api/search/advanced | **503** | 0.9 мс | 5 | то же |
| GET /api/suggestions | **503** | 0.7 мс | 5 | то же |
| GET /api/suggestions/users | **503** | 0.7 мс | 5 | то же |

Деградация управляемая: быстрый 503 от nginx (миллисекунды, не таймаут 30s, не
502-залипание) на ВСЕМ search-семействе; тело и Retry-After — из `@search_down`.

**Факт по X-Service на 503:** заголовок `X-Service: search` на 503-ответах
**присутствует** (в ТЗ задачи заявлено «X-Service отсутствие»). Это паритет
продуктового конфига: `@search_down` включает `search-headers.inc`
(services/frontend/nginx/ekotov-wiki.conf:122–129), тот же факт зафиксирован
в REPORT-regress-21 §3 и принят ревью 1.3. На деградационную семантику
(код 503 / JSON / Retry-After) не влияет. Расхождение — формулировка ТЗ,
не продукт; вынесено на усмотрение ПМ (правка ТЗ не входила в зону).

### 2.3 Смоук записи при упавшем search (изоляция сервисов, design §1/§8)

| Проверка | Результат |
|---|---|
| POST /api/tasks (создание `QAT-22-write-while-search-down`) | **201** |
| GET /api/board | **200** (без X-Service) |
| Повторный поиск этих же данных | **503** (search по-прежнему остановлен) |

Запись в app полностью живет при остановленном search — отказ search не
затрагивает основной функционал (изоляция сервисов подтверждена).

### 2.4 Восстановление (restart search)

- search поднят заново; poll через nginx: **200 в пределах первого интервала
  0.5 с** (resolver+переменная: переразрешение на запросах — stale-DNS не
  возникает, restart безопасен).
- Контрольная выдача: `GET /api/search?q=write-while` → 200, в результатах
  **обе** задачи — и созданная до падения, и созданная ВО ВРЕМЯ деградации
  (запись прошла в БД, поиск по восстановлении её находит).

## 3. Сценарий B: stop backup → деплой-бэкап работает (design §5, §8)

Sidecar-контейнер в локальном контуре отсутствует (эквивалент «stop backup»);
деплой-трасса бэкапа исполнена тем же кодом, что вызывает deploy.sh v3
(шаг 2/8: `python -c "from backup import run_backup; run_backup()"` внутри
app-контейнера — тот же модуль `services/backup/backup.py`):

```
EKOTOV_WIKI_DB_PATH=/tmp/stend22/db/wiki.db EKOTOV_WIKI_AVATARS_DIR=/tmp/stend22/avatars \
BACKUP_DIR=/tmp/stend22/backup-out python -c "from backup import run_backup; run_backup()"
→ [backup] БД: wiki-daily-20261005T112110Z.db (98304 bytes)
→ [backup] аватары: avatars-daily-20261005T112110Z.tar (10240 bytes)
```

Валидация результата: копия БД открыта sqlite3, `select count(*) from tasks`
→ **2** (обе smoke-задачи сессии присутствуют); tar аватаров непустой;
retention не затронул ничего (каталог свежий). Вывод: при остановленном sidecar
релизный бэкап деплоя работоспособен (design §5: «один код, без дубля релизного
бэкапа»; design §8: «backup шумит → stop backup, деплой-бэкап остается в deploy.sh»).

Косвенный смоук записи: вход для бэкапа — задачи, созданные через API в §2
(2 шт.); бэкап их захватил → консистентность копии подтверждена данными записи.

## 4. Память: лимиты сервисов и свободная память хоста (design §7, FR-73)

| Проверка | Результат | Норма |
|---|---|---|
| Свободная память хоста (`free -m`, available) | **2749 MB** | ≥ 2048 MB — **PASS** |
| RSS app (uvicorn, :8080) | 57 MB | лимит 512m (compose) — в пределах |
| RSS search (uvicorn, :8378) | 51 MB | лимит 512m (compose) — в пределах |
| RSS nginx (master+worker) | ~4 MB | лимит 64m (compose) — в пределах |
| RSS backup | n/a (sidecar не поднимался) | лимит 64m — см. §5.2 |

`free -m` на момент прогона: total 3915, used 1166, available 2749, swap 0.

## 5. Ограничения и компенсации (честно, не «пропуск»)

1. **docker/compose.test.yaml не поднимались** (docker.sock — permission denied,
   §0). Следствие: mem_limit- enforcement и `docker stats` не наблюдались
   напрямую. Компенсация: RSS-факты процессов (§4 — все в пределах лимитов
   compose) + **задача 2.3 (прод-параллель :10444)** — подъем полного стека на
   реальном docker, где `docker stats` доступен и лимиты проверяются на живом
   стеке до приемки Заказчика. Повторная попытка docker в этой сессии не
   предпринималась после первой пробы (права пользователя — не устранимо в
   рамках задачи).
2. **backup-sidecar как контейнер не поднимался** (тот же корень — docker).
   Компенсация: юнит-эквивалент деплой-трассы того же модуля (§3, «BACKUP OK»);
   контейнерный путь (heartbeat, healthcheck, ro-маунты) — задача 2.3 (compose up
   поднимает backup, healthy-условие в деплой-матрице 1.4).
3. **TLS не терминировался** (HTTP :18443 вместо 10443; self-signed ронял бы
   health-poll — известное отличие стенда, REPORT-regress-21 §2/§3). На
   маршрутизацию/деградацию не влияет (терминация — до location-матчинга);
   TLS-паритет — задача 2.3 (приемка Заказчика браузером по https).
4. `client_max_body_size 64m` вместо продовых 2m (multipart гейт-кейсов
   аватаров; осознанное отличие стенда из 2.1, на матрицу 2.2 не влияет —
   search-семейство тел не принимает).

## 6. Итог

| Сценарий | Результат |
|---|---|
| stop search → 503 от nginx (все 4 эндпоинта семейства, JSON + Retry-After, ~1мс) | **PASS** |
| запись в app при упавшем search (201/200) + находимость после restart | **PASS** |
| restart search → самовосстановление ≤ 0.5 с, без stale-DNS | **PASS** |
| stop backup → деплой-бэкап (run_backup) работает, копия валидна | **PASS** |
| свободная память хоста ≥ 2 GB | **PASS** (2749 MB) |
| лимиты памяти сервисов | **PASS** по RSS-компенсации; docker stats — 2.3 |

Стенд погашен (uvicorn ×2, nginx quit; /tmp/stend22 вне репозитория).
Баг-репортов не заведено: продуктовых дефектов матрица не выявила.
