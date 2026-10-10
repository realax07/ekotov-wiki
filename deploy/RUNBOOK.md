# RUNBOOK — прод-окружение ekotov-wiki

Актуально **по факту на 2026-10-05** (задача 2.5, change `add-microservices-full`;
источники — протоколы приемки `code-reviews/add-microservices-full/acceptance-protocol-2.3.md`
и `acceptance-protocol-2.4.md`, `deploy/2.3-par.sh`, `deploy/2.4-switch.sh`,
`deploy/deploy.sh` v3, `deploy/compose.yaml`). Перед каждым деплоем — перепроверить
раздел §1.3 «Быстрая проверка фактов»: окружение может измениться.

---

## 1. Текущее состояние

### 1.1 Прод = матричный стек p12-rc1 (с 2026-10-05 13:35 UTC)

```
Заказчик (браузер)
   │  https://194.58.34.122:10443  (TLS self-signed до 2028-12-22)
   ▼
frontend: nginx-контейнер, :10443 (compose-проект ekotov-wiki-par)
   ├── /api/search, /api/search/*, /api/suggestions*  → search:8378
   │     (заголовок ответа X-Service: search; search недоступен → управляемый 503)
   ├── /static/, /avatars/  → из тома (ro)
   └── остальное            → app:8377 (uvicorn)
                                 ▼
        named volume ekotov-wiki-par_wiki-data (wiki.db + avatars/)
           ├── app:            маунт rw (единственный писатель, миграции — тоже он)
           ├── search:         маунт :ro — read-only-профиль (§2.3)
           ├── backup:         маунт :ro + bind /var/backups/ekotov-wiki
           └── nginx(frontend): маунт :ro (только отдача /data/avatars/)
```

Факты:

| Факт | Значение | Проверка |
|---|---|---|
| Релиз в бою | `p12-rc1`, 4 образа `ekotov-wiki/{app,frontend,search,backup}:p12-rc1` | `docker compose -p ekotov-wiki-par ps; docker images --format '{{.Repository}}:{{.Tag}}' \| grep p12` |
| Compose-проект прода | `ekotov-wiki-par`, project-directory `deploy/` (поднят `2.3-par.sh`, опубликован на 10443 `2.4-switch.sh`) | `docker compose -p ekotov-wiki-par ls` |
| Порт | `10443` (публикует ТОЛЬКО nginx-контейнер) | `ss -tln \| grep 10443` |
| Том данных | `ekotov-wiki-par_wiki-data` | `docker volume ls \| grep ekotov-wiki-par` |
| Поиск | `/api/search*`, `/api/suggestions*` → search:8378; ответ без сессии — 401 от search (контракт sdd §3.5), с сессией — 200; маркер маршрутизации — заголовок `X-Service: search` | `curl -sk -D - -o /dev/null 'https://127.0.0.1:10443/api/search?q=' \| grep -iE 'HTTP\|x-service'` |
| Деградация поиска | `docker compose -p ekotov-wiki-par stop search` → nginx отвечает управляемым **503** (не 502, не таймаут); возврат — `start search` | `curl -sk -o /dev/null -w '%{http_code}\n' 'https://127.0.0.1:10443/api/search?q='` |
| Вторая среда :10444 | после 2.4 НЕ обслуживается: nginx-контейнер проекта перепубликован с 10444 на 10443 (пересоздание, §4.3) — у проекта один nginx с одним публикуемым портом. Вторую среду при нужде поднимать ОТДЕЛЬНЫМ compose-проектом (свой том), НЕ повтором `2.3-par.sh full` — тот бьет в продовый проект `ekotov-wiki-par` | `ss -tln \| grep 10444` (пусто = свободен); `docker ps --format '{{.Names}} {{.Ports}}'` |
| systemd-юнит `ekotov-wiki` | **inactive, enabled** (НЕ disable) — исторический резерв отката на v1-схему (§8). Active-юнит = конфликт двух конкурирующих стеков на одной БД | `systemctl is-active ekotov-wiki` → `inactive` |
| Секреты | `deploy/.env` (SECRET_KEY), 0600; в репозиторий не попадает | `sudo ls -la deploy/.env` |
| Клон-источник | `/home/openclaw/ekotov-wiki` (НЕ /opt, как в v1-эпоху); build образов — из клона с целевым коммитом | `git -C /home/openclaw/ekotov-wiki log --oneline -1` |

Наблюдение после перехода (2.4, пауза эксплуатации ОВ-1=а, 1–2 недели, до ~2026-10-19):
прод считается стабильным на матрице; откат на двухсервисный стек —
`deploy/2.4-switch.sh rollback` (§4.3). По окончании паузы — решение Заказчика
о погашении параллели и статусе резерва.

### 1.2 Приемка (артефакты)

- 2.3 прод-параллель: стек p12-rc1 на :10444 рядом с продом, seed прода,
  смоук-матрица + приемка браузером («Вроде все работает. Проверил», 2026-10-05) —
  `code-reviews/add-microservices-full/acceptance-protocol-2.3.md`.
- 2.4 переключение: бэкап тома параллели → старый стек stop (НЕ удален — это откат)
  → новый стек на :10443, смоук PASS (X-Service: search на прод-порту), приемка
  браузером («Вроде все норм работает. Ок», 2026-10-05) —
  `code-reviews/add-microservices-full/acceptance-protocol-2.4.md`.

### 1.3 Быстрая проверка фактов (прогон перед деплоем)

```bash
docker compose -p ekotov-wiki-par ps                     # 4 службы Up (app/search healthy)
ss -tln | grep -E '10443|10444'                          # прод; 10444 = параллель (если поднята)
systemctl is-active ekotov-wiki                          # inactive (норма)
curl -sk --max-time 5 https://127.0.0.1:10443/api/health # {"status":"ok"} (app через nginx)
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:10443/login           # 200
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:10443/static/css/app.css  # 200
curl -sk -D - -o /dev/null 'https://127.0.0.1:10443/api/search?q=' | grep -i 'x-service'  # search
ls -la /var/backups/ekotov-wiki/ /var/backups/ekotov-wiki/pre-2.4/ | tail -8
docker volume ls | grep ekotov-wiki-par
git -C /home/openclaw/ekotov-wiki log --oneline -1
```

## 2. Компоненты матрицы

### 2.1 Сервисы (deploy/compose.yaml)

| Сервис | Образ | Порт (внутр.) | mem_limit | Данные | Роль |
|---|---|---|---|---|---|
| app | `ekotov-wiki/app:<tag>` | 8377 | 512m | том **rw** | ядро: вся логика кроме поиска; ЕДИНСТВЕННЫЙ писатель БД; применяет схему idempotent'но при старте |
| frontend | `ekotov-wiki/frontend:<tag>` | 10443 (публикует `${NGINX_PORT}`) | 64m | том :ro + images-data :ro + серт хоста :ro | nginx: TLS, статика, avatars, /images/ из тома, маршрутизация app/search/images |
| search | `ekotov-wiki/search:<tag>` | 8378 | 512m | том **:ro** | поиск+suggestions (роутеры как в монолите, контракт `contracts/openapi-search.json`) |
| backup | `ekotov-wiki/backup:<tag>` | — | 64m | том :ro + bind `/var/backups/ekotov-wiki` (uid 10001) | sidecar-бэкапы, cron-цикл 86400s, retention 14 дней |
| images | `ekotov-wiki/images:<tag>` | 8379 | 128m | том **rw** (БД) + images-data **rw** | галерея (add-gallery-service): upload/валидация JPEG/PNG/GIF/WebP ≤10МБ (magic-байты), превью Pillow ≤800px, реакции/комментарии; пишет ТОЛЬКО таблицы gallery; файлы — в images-data (design §2, FR-79) |

Теги: только релизные `<RELEASE_TAG>`; **latest ЗАПРЕЩЕН** (FR-72, deploy.sh падает).
`depends_on`: nginx → app (service_healthy); search/backup/images → app БЕЗ condition
(читают/пишут БД независимо; на пустом томе search вернет 500 на запросах, `/api/health`
при этом 200 — схему создает app при первом старте; images требует users — FK
images.uploaded_by). Все сервисы работают под **uid 10001** — владелец данных томов
и bind-каталогов обязан быть 10001:10001 (новый том/каталог от root = PermissionError
на записи; фикс: `docker run --rm -v <том>:/data alpine chown -R 10001:10001 /data`).

### 2.2 Маршрутизация nginx (образ frontend, задачи 1.3 netdata / 1.4 gallery)

- `location = /api/search`, `location ^~ /api/search/`, `location = /api/suggestions`(+семейство)
  → `proxy_pass http://search:8378` через `resolver 127.0.0.11` + переменную
  (stale-DNS после пересоздания search-контейнера лечится переразрешением valid=10s).
- `location = /api/images`, `location ^~ /api/images/` → `http://images:8379`
  (та же resolver-схема, `images-proxy.inc`), `client_max_body_size 12m` на локациях
  (прод-лимит server 2m перебит — файл ≤10 МБ + multipart-обвязка, NFR-21);
  `location /images/` — alias в том images-data, expires 7d (паритет /avatars/).
- Заголовок `X-Service: search|images` на семейственных локациях — маркер
  «ответ пришел от сервиса», критерий смоука.
- Деградация: `proxy_next_upstream` + `error_page` → `@search_down` / `@images_down` —
  остановленный сервис дает **управляемый 503** клиенту (не 502-залипание).
- `/netdata` — basic auth (htpasswd bind :ro, chmod 644 — воркер непривилегирован)
  → netdata:19999.
- Остальные URI — app:8377 (proxy_pass через ту же resolver-схему).

### 2.3 RO-профиль search (services/search/app/db.py — читать при разборе нюансов)

Search — read-only потребитель той же БД: маунт тома `:ro` (файловая гарантия) +
открытие соединения по URI `mode=ro` (никогда не пишет; foreign_keys=ON —
connection-level, файл не трогает; PRAGMA WAL ядра НЕ применяется — на ro-маунте
она равна записи в заголовок БД). WAL-нюанс:
- при живых `-wal/-shm` (app работает) `mode=ro` читает свежие данные, включая
  незачекпоинченные;
- если app закрыл все соединения, sqlite удаляет `-wal/-shm` → `mode=ro` падает,
  fallback `immutable=1` читает main-db (состояние последнего checkpoint'а) —
  новые задачи появляются после ближайшей транзакции app. Осознанный компромисс
  ПРОСТОЯ, не данных; при живом wal immutable не используется.
Схему search не мигрирует и не пишет. Тот же ro-принцип у backup (маунт :ro).

### 2.4 Миграции

Миграция ядра — **one-shot из образа app, СТРОГО ДО подъема app**:
`docker compose run --rm app python -m app.migrate_rN` (deploy.sh шаг 4/8;
MIGRATE_MODULE=app.migrate_rN при миграционных релизах). search/backup — читатели
той же схемы, миграций не требуют. Миграция — только после репетиции на копии.

## 3. Деплой (deploy/deploy.sh v3 — матрица)

Запускает **Заказчик из-под root** из клона `/home/openclaw/ekotov-wiki` с целевым коммитом:

```bash
sudo -E DRY_RUN=1 RELEASE_TAG=<метка> bash deploy/deploy.sh   # ОБЯЗАТЕЛЬНЫЙ первый прогон
sudo -E RELEASE_TAG=<метка> bash deploy/deploy.sh             # боевой
# миграционный релиз: + MIGRATE_MODULE=app.migrate_rN
```

Матрица: `SERVICES="app frontend search backup"` (env-оверрайд — осознанно),
теги `ekotov-wiki/<name>:<RELEASE_TAG>`, по-сервисный оверрайд
`APP_IMAGE`/`FRONTEND_IMAGE`/`SEARCH_IMAGE`/`BACKUP_IMAGE` (горячий фикс одного сервиса).

Порядок шагов (set -euo pipefail, останов на первой ошибке):
предусловия (+ подготовка bind-каталога бэкапов: `mkdir -p` + idempotent
`chown 10001:10001 /var/backups/ekotov-wiki` — образ backup под ЧИСЛОВЫМ uid 10001) →
**бэкап ДО ВСЕХ изменений** (модуль `services/backup/backup.py::run_backup` — тот же
код, что у sidecar; `wiki-pre-<release>-<дата>-<время>.db` + `avatars-pre-*.tar`
через staging `release-staging/` и mv в релизные имена) → build ВСЕХ образов матрицы →
one-shot миграция ядра (до up!) → `up -d app` → healthy → `up -d search backup` →
healthy → `up -d nginx` → healthy → смоук-матрица → `docker image prune -f`.

Смоук-матрица деплоя: health app 200; health search напрямую 200; поиск через nginx
200/401/422 + `X-Service: search` (502/503 = FAIL); /login 200; статика 200;
avatars 200/403/404 — не 502; 502=0 в логах nginx; образы контейнеров = релизные теги.

Стенд (репетиции/e2e): `docker compose -f deploy/compose.test.yaml -p wiki-test up -d --build`
(порт 8443, tmpfs — данные исчезают при down).

## 4. Откат

### 4.1 Основной: предыдущий RELEASE_TAG парой (app+search)

Схема и search-код катятся **одним тегом** (схема БД у них общая): повторный запуск
deploy.sh с предыдущей меткой. Совместимая пара — app+search; frontend/backup можно
не трогать, задав их `*_IMAGE` прежними тегами явно.

### 4.2 Точечный фикс одного сервиса

```bash
cd /home/openclaw/ekotov-wiki/deploy
sudo -E APP_IMAGE=ekotov-wiki/app:<hotfix-tag> \
     SEARCH_IMAGE=ekotov-wiki/search:<тот же тег> docker compose -p ekotov-wiki-par up -d
```
Остальные образы не пересоздаются. hotfix-тег — НЕ latest.

### 4.3 Rollback-режимы скриптов перехода (окно наблюдения после 2.4)

| Сценарий | Команда | Что происходит |
|---|---|---|
| Вернуть двухсервисный стек (допоенности контейнеры живы) | `sudo bash deploy/2.4-switch.sh rollback` | новый стек уходит с 10443 (nginx scale=0), старый стек `start` (его контейнеры stop без rm, том нетронут). **Задачи, созданные в новом стеке после переключения, в старом томе отсутствуют — зафиксировать вручную** |
| Погасить nginx второй среды (если поднималась на :10444) | `docker compose -p <проект-среды> stop nginx` (или `down` БЕЗ `-v`, если том еще нужен) | снимает только публикацию 10444; **НЕ выполнять `2.3-par.sh rollback` (down -v проекта `ekotov-wiki-par`): с 2026-10-05 этот проект — прод, его down -v снесет продовый том `ekotov-wiki-par_wiki-data`** (расхождение с acceptance-protocol-2.4 §«Откат», где указан 2.3-par.sh rollback — протокол писался до переключения, актуален только для окна до 2.4) |
| Статус обоих стеков | `sudo bash deploy/2.4-switch.sh status` | compose ps обоих проектов + порты + коды 10443/10444 |

Деградационные (без отката релиза): search тормозит/течет —
`docker compose -p ekotov-wiki-par stop search` (nginx отдает 503) + запасной конфиг
с роутерами в app (заготовка в ветке); backup шумит — `stop backup` (релизный бэкап
остается в deploy.sh).

### 4.4 Том/БД

Откат данных = предыдущий RELEASE_TAG (§4.1) + бэкап из
`/var/backups/ekotov-wiki/` (§5). Возврат на systemd/v1-схему целиком — аварийный
путь (§8): §4.3 rollback + восстановление БД §8.2, контейнерный стек `down`
(том сохранить до сверки данных).

## 5. Бэкапы

| Трасса | Файлы | Кто/когда |
|---|---|---|
| Деплой-трасса | `/var/backups/ekotov-wiki/wiki-pre-<release>-<дата>-<время>.db`, `avatars-pre-*.tar` | deploy.sh перед всеми изменениями; модуль `run_backup`; релизные файлы sidecar-retention НЕ трогает |
| Sidecar-ретеншн | `wiki-daily-*`, `avatars-daily-*` (суточный цикл 86400s, retention 14 дней) | контейнер backup; страхует МЕЖДУ релизами |
| Pre-2.4 (фиксация переключения) | `/var/backups/ekotov-wiki/pre-2.4/wiki-pre-2.4-<дата>-<время>.db` — консистентный снапшот тома параллели на момент переключения 2.4 (VACUUM INTO из образа app) | 2.4-switch.sh pre |
| Исторические (v1-эпоха) | `wiki-pre-<цель>-<дата>-<время>.db` в том же каталоге | сохранены |

Владелец bind-каталога — **числовой uid 10001** (имя `wiki:wiki` на хосте может
означать другой uid — deploy.sh приводит idempotent'но).

**Галерея (r7.1-gallery+):** файлы изображений живут в отдельном томе
`ekotov-wiki-par_images-data` (оригинал + превью `.jpg`, имена генерирует
сервис — в БД только метаданные). С J38 (2026-10-10) том images-data включен в релизный
контур: deploy.sh 2/8 пишет images-pre-<метка>-<stamp>.tar.gz рядом с БД/аватарами
(tar из images-контейнера). Вне деплоя — ручной снапшот: `docker run --rm
-v ekotov-wiki-par_images-data:/data -v /var/backups/ekotov-wiki:/backup alpine
tar czf /backup/images-pre-<метка>-$(date +%F).tar.gz -C /data .`.
Владелец тома — uid 10001 (как выше); свежесозданный docker-том от root = 500
на upload, фикс chown (§2.1).

## 6. Типовые отказы матрицы

| Симптом | Причина | Действие |
|---|---|---|
| Поиск через nginx = 502 | search не поднят / stale-DNS после пересоздания | `docker compose -p ekotov-wiki-par ps`; `docker compose -p ekotov-wiki-par up -d search`; нет — `restart nginx` (resolver 127.0.0.11 должен переразрешить) |
| Поиск = 503 | управляемая деградация: nginx не достучался до search (мог быть остановлен намеренно, §4.3) | `docker compose -p ekotov-wiki-par start search` |
| Поиск = 500, app жив | пустой том (схемы нет — search не создает) | схему создает app; проверить том/логи app |
| Поиск = 401 без сессии | НОРМА (контракт sdd §3.5: search требует сессию) | смоук-критерий: 200/401/422 от search + X-Service |
| Поиск временно показывает «не самые свежие» задачи | ro-профиль: wal удален при простое app, search читает checkpoint-состояние (§2.3) | не дефект; следующая транзакция app воссоздает wal |
| `compose up` — `port is already allocated` | 10443 занят другим стеком / висячий контейнер на 10444 | `docker ps -a`; для параллели — `NGINX_PORT=10444` |
| nginx 502 на `/` после выката app | stale-DNS app | должен лечиться resolver+переменная; иначе `restart nginx`, дефект |
| app не стартует: «обязательная переменная SECRET_KEY» | нет `deploy/.env` / запуск вне каталога deploy | создать .env (0600), запускать из `deploy/` |
| backup не пишет в /var/backups/ekotov-wiki | владелец не 10001 | `sudo chown 10001:10001 /var/backups/ekotov-wiki` (deploy.sh делает idempotent'но) |
| systemd-юнит вдруг ACTIVE | ручной старт поверх контейнерного прода — конфликт двух стеков на одной БД | `sudo systemctl stop ekotov-wiki`; юнит не disable |
| после ребута VPS стек не поднялся | docker.service не в автозапуске | `sudo systemctl enable docker`; далее `restart: unless-stopped` поднимет сам |
| диск растет после деплоев | dangling-образы | `docker image prune -f` (шаг deploy.sh) |

## 7. Границы

- Деплой/переключения запускает Заказчик (root); агент — подготовка, dry-run, пост-диагностика.
- Секреты (SECRET_KEY, содержимое `deploy/.env`) в репозиторий/артефакты не попадают — `[REDACTED]`.
- Публичный порт один — 10443; внутренние порты 8377/8378 наружу не публикуются.
- `latest` запрещен; теги релизные (`A-Za-z0-9._-`).

## 8. ИСТОРИЧЕСКОЕ: схема v1 (systemd/rsync, двухсервисная) — только для аварийного возврата

> До 2026-10-03 прод работал на v1-схеме (uvicorn systemd + host-nginx на 10443),
> с 2026-10-03 по 2026-10-05 — двухсервисный контейнерный стек (app+nginx, пакет
> add-containerization, проект `ekotov-wiki`). С 2026-10-05 прод — матричный стек (§1).
> Оба legacy-стека — РЕЗЕРВ, основной путь деплоя — §3. Подробные процедуры эпох —
> в git-истории этого файла (до задачи 2.5) и `deploy/deploy-v1-systemd.sh`.

### 8.1 systemd-юнит `ekotov-wiki` (резерв)

`inactive`, но **enabled** (НЕ disable) — сознательный резерв: `sudo systemctl start ekotov-wiki`
поднимает uvicorn (user wiki, `/opt/ekotov-wiki/backend/.venv`, 127.0.0.1:8377,
EnvironmentFile `/opt/ekotov-wiki/.env`). Условие применимости: контейнерный стек
остановлен (иначе два писателя одной БД). ExecStart и факты юнита —
`systemctl cat ekotov-wiki`. Код v1-деплоя: `deploy/deploy-v1-systemd.sh` (rsync
клона → /opt, pip, схема, рестарт) — сохранен, для v1-схемы, НЕ для матрицы.

### 8.2 Аварийный возврат на legacy (порядок)

1. Остановить матрицу: `cd deploy && docker compose -p ekotov-wiki-par down`
   (том сохранить до сверки данных; при возврате на двухсервисный стек вместо
   down — `2.4-switch.sh rollback`, §4.3 — он просто стартует старый стек).
2. БД: v1-схема читает `/var/lib/ekotov-wiki/wiki.db` (host-путь) — данные,
   созданные в контейнерах, туда НЕ попадали с 2026-10-03: перенос/сверка вручную
   из тома (docker run + sqlite .backup) перед стартом юнита.
3. `sudo systemctl start ekotov-wiki`; хост-nginx на 10443 (конфиг
   `/etc/nginx/sites-enabled/ekotov-wiki`) — проверить `ss -tln | grep 10443`.
4. Смоук v1: `curl -s http://127.0.0.1:8377/api/health`; страница через прод-URL.
   Поиск на v1 работает из монолита (маршруты там возвращены в эпохе до 1.5 —
   если возвращаться на код ДО выреза search-роутеров; иначе поиск будет 404 —
   фиксировать как известное ограничение возврата).
