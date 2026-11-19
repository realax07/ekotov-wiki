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
| frontend | `ekotov-wiki/frontend:<tag>` | 10443 (публикует `${NGINX_PORT}`) | 64m | том :ro + images-data :ro + videos-data :ro + серт хоста :ro | nginx: TLS, статика, avatars, /images/ и /videos/ из томов, маршрутизация app/search/images/video |
| search | `ekotov-wiki/search:<tag>` | 8378 | 512m | том **:ro** | поиск+suggestions (роутеры как в монолите, контракт `contracts/openapi-search.json`) |
| backup | `ekotov-wiki/backup:<tag>` | — | 64m | том :ro + images-data :ro + videos-data :ro + bind `/var/backups/ekotov-wiki` (uid 10001) | sidecar-бэкапы БД+медиа (TD-A/TD-D), cron-цикл 86400s, retention 14 дней; env `EKOTOV_WIKI_IMAGES_DIR`/`EKOTOV_WIKI_VIDEOS_DIR` |
| images | `ekotov-wiki/images:<tag>` | 8379 | 128m | том **rw** (БД) + images-data **rw** | галерея (add-gallery-service): upload/валидация JPEG/PNG/GIF/WebP ≤10МБ (magic-байты), превью Pillow ≤800px, реакции/комментарии; пишет ТОЛЬКО таблицы gallery; файлы — в images-data (design §2, FR-79) |
| video | `ekotov-wiki/video:<tag>` | 8380 | 512m | том **rw** videos-data | видеохостинг (P11, video-1): upload ≤500МБ любой формат → ffmpeg-конвертация mp4+превью (фон-воркер, статусы uploaded/converting/ready/error), playback, комментарии/реакции/категории; пишет ТОЛЬКО таблицы video_*; ffmpeg статический В ОБРАЗЕ (pin johnvansickle 7.0.2 + SHA256; fallback BtbN n8.1 со своим SHA256 — дрейф версии ffmpeg в fallback) |

Теги: только релизные `<RELEASE_TAG>`; **latest ЗАПРЕЩЕН** (FR-72, deploy.sh падает).
`depends_on`: nginx → app (service_healthy); search/backup/images → app БЕЗ condition
(читают/пишут БД независимо; на пустом томе search вернет 500 на запросах, `/api/health`
при этом 200 — схему создает app при первом старте; images требует users — FK
images.uploaded_by; video требует users аналогично). Все сервисы работают под **uid 10001** — владелец данных томов
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

- `location = /api/videos`, `location ^~ /api/videos/`, `location ^~ /videos/`
  → video :8380 (api напрямую; файлы playback из тома videos-data) с
  `auth_request /_video_auth` → video `/api/videos/authcheck` (NFR-36: доступ
  только авторизованный); `error_page 502 503 504 → @videos_down` — управляемый
  503 JSON + X-Service: video (stop video → wiki/search/login работают, §6).

## 3. Деплой (deploy/deploy.sh v3 — матрица)

Запускает **Заказчик из-под root** из клона `/home/openclaw/ekotov-wiki` с целевым коммитом:

```bash
sudo -E DRY_RUN=1 RELEASE_TAG=<метка> bash deploy/deploy.sh   # ОБЯЗАТЕЛЬНЫЙ первый прогон
# (dry-run требует deploy/.env с SECRET_KEY — гейт compose config рендерит env
# из него; без .env упадет на гейте, stderr compose будет в сообщении)
sudo -E RELEASE_TAG=<метка> bash deploy/deploy.sh             # боевой
# миграционный релиз: + MIGRATE_MODULE=app.migrate_rN
# видео-релиз: video В МАТРИЦЕ деплоя (TD-D, P19-паттерн weather — образ
# собирается и поднимается deploy.sh); миграции — MIGRATE_MODULE=app.migrate_wiki
# (ядро, шов скрипта) + app.migrate_video ОТДЕЛЬНОЙ командой (deploy.sh про
# video-схему по-прежнему не знает): python -m app.migrate_video
```

Матрица: `SERVICES="app frontend search images video backup weather"` (env-оверрайд —
осознанно), теги `ekotov-wiki/<name>:<RELEASE_TAG>`, по-сервисный оверрайд
`APP_IMAGE`/`FRONTEND_IMAGE`/`SEARCH_IMAGE`/`IMAGES_IMAGE`/`VIDEO_IMAGE`/`BACKUP_IMAGE`/`WEATHER_IMAGE`
(горячий фикс одного сервиса).

SRC_DIR может указывать на **git-worktree** (TD-D): проверка репозитория —
`git rev-parse --git-dir`, не `[ -d .git ]` (в worktree `.git` — файл-ссылка).
Канон для релизов с волны PLAN-TD-CLOSEOUT: отдельный worktree от origin/main,
деплой из него — основной клон не отрывается от main.

Порядок шагов (set -euo pipefail, останов на первой ошибке):
предусловия (+ подготовка bind-каталога бэкапов: `mkdir -p` + idempotent
`chown 10001:10001 /var/backups/ekotov-wiki` — образ backup под ЧИСЛОВЫМ uid 10001) →
**бэкап ДО ВСЕХ изменений** (модуль `services/backup/backup.py::run_backup` — тот же
код, что у sidecar; `wiki-pre-<release>-<дата>-<время>.db` + `avatars-pre-*.tar` +
`images-pre-*.tar.gz` через staging `release-staging/` и mv в релизные имена) →
build ВСЕХ образов матрицы → one-shot миграция ядра (до up!) → `up -d app` → healthy →
`up -d search images backup video weather` → все healthy (каждый — свой healthcheck:
app/search/images/video/weather по `/api/health`, backup по heartbeat,
docker-socket-proxy по wget /_ping, netdata по /api/v1/info) → `up -d nginx` →
healthy → смоук-матрица → `docker image prune -f`.

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
| Деплой-трасса | `/var/backups/ekotov-wiki/wiki-pre-<release>-<дата>-<время>.db`, `avatars-pre-*.tar`, `images-pre-*.tar.gz` | deploy.sh перед всеми изменениями; модуль `run_backup`; релизные файлы sidecar-retention НЕ трогает |
| Sidecar-ретеншн | `wiki-daily-*`, `avatars-daily-*`, `images-daily-*`, `videos-daily-*` (суточный цикл 86400s, retention 14 дней) | контейнер backup; страхует МЕЖДУ релизами. Медиа-тома (images-data/videos-data) в backup-контейнере с TD-A/TD-D (ro-маунты + env `EKOTOV_WIKI_IMAGES_DIR`/`EKOTOV_WIKI_VIDEOS_DIR`) — полный контур БД+медиа, см. `docs/ops/backup-restore.md` |
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
| Видео = 503 (управляемый, X-Service: video) | деградация: video остановлен/недоступен; wiki/search/login работают | `docker compose -p ekotov-wiki-par start video`; смоук-критерий изоляции отказа |
| Видео = 500 на пустом томе | схема video_* не создана | `python -m app.migrate_video` (идемпотентен) — схемы video создает МИГРАЦИЯ, не app |
| nginx не поднимается после видео-релиза: «no such dir /data/videos» | каталог videos/ отсутствует в ro-маунте wiki-data (гэп deploy.sh при первом видео-релизе) | ДО up nginx: `mkdir /data/videos` в томе wiki-data (через app-контейнер) + `docker volume create videos-data` + chown 10001:10001; инцидент video-1 (простой ~3 мин) |
| upload видео 502/422 у всех клиентов | лимит тела nginx | client_max_body_size 520m только в video-локациях (добавлено) |

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

## 7. Сервис «Погода» (weather:8381, с релиза weather-1)

### 7.1 Матрица
- контейнер weather:8381, FastAPI 1 воркер, mem_limit 128m; БД НЕ имеет (единственное состояние — кэш-файл)
- том weather-cache → /cache (chown 10001:10001 ДО старта — как videos-data; /data у weather — ro-БД, вкладывать томы внутрь нельзя, инцидент PR #207)
- миграций НЕТ (MIGRATE_MODULE не трогается: app.migrate_wiki как обычно)
- образ без ffmpeg (тоньше видео), секретов нет (Open-Meteo без ключа, User-Agent в env)

### 7.2 Отказы
- провайдер недоступен + есть кэш → 200 stale:true + баннер UI (самовосстановится)
- пустой кэш + провайдер лежит → честный 503 weather_unavailable (UI «Повторить»)
- контейнер убит → nginx @weather_down 503 JSON + Retry-After (мс), остальные разделы живы
- nginx: только /api/weather* (weather-proxy.inc, $upstream_weather+resolver, intercept off); страница /weather — ядро (Jinja), деградации nginx для нее нет

### 7.3 Деплой
- WEATHER_IMAGE=ekotov-wiki/weather:${RELEASE_TAG} (в матрице deploy.sh с weather-1)
- P19: шаг 5/8 deploy.sh поднимает weather во второй волне (up -d search images backup weather, WEATHER_IMAGE в env) и проверяет по docker compose config, что weather резолвится в релизный тег (не :local); смоук 6.8 сверяет образ контейнера с тегом
- static_v бампится ПМ до диспетчеризации (R7)
- проверка после: GET /api/weather 200 stale-флаг, файл /cache/weather.json на томе, страница /weather под логином

## 9. game-portal (standalone-контейнер, P26; актуализировано TD-C 2026-11-15)

### 9.1 Матрица / «вне compose — осознанно»
- ВНЕ compose: внешний игровой хаб (github realax07/game-portal, Node, 7 игр: kosynka, durak, vice, munchkin, poker, tanks, evolution), поднимает ПМ отдельно — в матрице deploy.sh НЕ участвует. Это ОСОЗНАННОЕ решение, не недоработка (TD-C фиксация):
  - код — внешний апстрим-репозиторий со своими локальными патч-коммитами (HOST, GAME_HUB_PROXY), не собирается в образы релизных тегов;
  - НЕ добавлять его в SERVICES/<SVC>_IMAGE deploy.sh, в бэкап-контур и в зависимые матрицы — деплой-скрипт его не знает и не должен знать (up/down матрицы стек хаба не трогают);
  - обновление кода — git-циклом в клоне + recreate контейнера (§9.4), обновление НЕ через deploy.sh;
  - сервисное состояние игр (`.runtime`, `<svc>/.data`) — точечные rw-маунты поверх ro-бинда (§9.1.1); при введении НОВОГО каталога состояния — новый rw-маунт в recreate-команде (§9.4), ro всего бинда не снимать.
- сеть ekotov-wiki-par_default (compose-сеть проекта), порт 8080 ВНУТРИ сети (наружу не публикуется)
- код маунтится ro: /home/openclaw/game-portal → /srv

#### 9.1.1 Сервисное состояние (rw-маунты поверх ro)
- ro-маунт всего /srv; точечные rw-маунты ТОЛЬКО для каталогов, куда игры пишут: `game-hub/.runtime` (реестр spawn-сервисов) и `evolution/.data` — набор фиксирован в recreate-команде §9.2; при новой пишущей игре — НОВЫЙ rw-маунт туда же, ro всего бинда не снимать.
- busybox ps в alpine не знает `-p`; spawn-дети (services.mjs) живут в PID-namespace контейнера: рестарт контейнера пересоздает все бэкенд-игры, stale-пиды `.runtime/processes.json` отбрасываются сами (owned()).

### 9.2 Подъем / recreate (ПМ, вручную)
Единая recreate-команда (новый подъем — та же команда без `docker rm -f`; ОБНОВЛЕНИЕ/ОТКАТ — тоже она, меняется только состояние клона; набор игр/маунтов сверять с живым контейнером `docker inspect game-portal`, список ниже — факт P26-контура):
```
docker rm -f game-portal 2>/dev/null; \
docker run -d --name game-portal --restart unless-stopped \
  --network ekotov-wiki-par_default \
  -e HOST=0.0.0.0 -e GAME_HUB_PROXY=1 \
  -v /home/openclaw/game-portal:/srv:ro \
  -v /home/openclaw/game-portal/game-hub/.runtime:/srv/game-hub/.runtime \
  -v /home/openclaw/game-portal/evolution/.data:/srv/evolution/.data \
  node:26-alpine sh -c 'for s in kosynka durak vice munchkin poker tanks evolution; do node game-hub/services.mjs start "$s" || exit 1; done; exec node game-hub/server.mjs'
```
- `-e GAME_HUB_PROXY=1` обязателен: same-origin прокси бэкенд-игр за `/games/<id>/` (без него апстрим-редиректы на `localhost:<порт>` — мертвы на сервере).
- spawn-цикл сервисов — Cmd контейнера: по одному `node game-hub/services.mjs start <svc> || exit 1`, затем `exec node game-hub/server.mjs`. НЕ вызывать start без аргумента (он поднимает хаб сам — EADDRINUSE с exec). Проверка: `docker logs game-portal --tail 50` без EADDRINUSE/exit 1.

### 9.3 Состояния контейнера (ПМ-диагностика)
| Состояние | Как увидеть | Что это значит / действие |
|---|---|---|
| Up (норма) | `docker ps --filter name=game-portal` → `Up …` | `/games/` отвечает; смоук §9.5 |
| Restarting (цикл) | статус `Restarting (N) …` | см. `docker logs game-portal --tail 50`: чаще EADDRINUSE (двойной start хаба) или падение синтаксиса свежего кода → §9.4/§9.6 |
| Exited | `docker ps -a` → `Exited (N)` | `--restart unless-stopped` сам поднимет только при рестарте демона; после падения — recreate §9.2, не start вручную (Cmd-цикл должен стартовать СВЕЖИЙ код из клона) |
| Контейнера нет | `docker ps -a` пусто | подъем §9.2; nginx при этом отдаёт 502/504 на /games/* — остальные разделы живы (деградации @*_down для хаба НЕТ, он вне матрицы) |
- Живость хаба ≠ живость игр: `/games/api/games` должен вернуть все `available:true` — `false` у конкретной игры = умер spawn-сервис или GAME_HUB_DISABLE (см. `docker logs game-portal`).

### 9.4 Обновление из апстрима (ПМ, вручную)
```
git -C /home/openclaw/game-portal fetch origin
git -C /home/openclaw/game-portal merge origin/main   # ТОЛЬКО merge: ff-only уронит локальные патчи
git -C /home/openclaw/game-portal grep -nE 'HOST=|listen\(|GAME_HUB_PROXY' game-hub/server.mjs   # патч-строки живы
<recreate-команда §9.2>
```
- Локальные деплой-коммиты клона (HOST-патч в `server.listen`, GAME_HUB_PROXY) не существуют в апстриме — `git pull` (divergent) не использовать.
- Новая игра апстрима =merge + recreate + две строки инфры: id в regex-локацию nginx `services/frontend/nginx/ekotov-wiki.conf` ([ops]-PR, фронтенд-редеплой) и сервис в стартовый цикл контейнера. Игра вне regex попадает в strip-локацию: страница 200, но ассеты/API коллидят с корнем сайта — неиграбельна (проверяй ассет и api каждой игры, не только страницу).
- Верификация после обновления (§9.5) обязательна: страница 200 ≠ игра работает.

### 9.5 Откат (ПМ, вручную) и смоук
- Откат = код предыдущего коммита в клоне + recreate §9.2 (образ node:26-alpine не релизуется, «откат образа» к хабу неприменим):
```
git -C /home/openclaw/game-portal log --oneline -5          # выбрать последний известный хороший коммит
git -C /home/openclaw/game-portal checkout <hash>           # detached — осознанно, откат до починки
<recreate-команда §9.2>
git -C /home/openclaw/game-portal checkout main             # возврат на ветку перед следующим обновлением
```
- Смоук после любого recreate/обновления/отката (одной пачкой):
```
curl -sk https://127.0.0.1:10443/games/api/games | python3 -m json.tool   # все available:true
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:10443/games/   # 200
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:10443/games/<id>/   # 200, страница игры
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:10443/games/<id>/api/<health-эндпоинт>  # 200 (БАГ-5: нативный роутинг без среза)
```

### 9.6 Маршрутизация / отказы
- nginx (образ frontend): `= /games` → 301 `/games/`; `^~ /games/api/`, `^~ /games/previews/` и `/games/` (обычный префикс) → прокси game-portal:8080 со срезом префикса (games-proxy.inc: named capture + $upstream_games с resolver'ом — старт nginx БЕЗ поднятого контейнера безопасен, ошибка резолва только на запросе); regex `~ ^/games/(munchkin|vice|poker|tanks|durak|evolution)(/|$)` → прокси БЕЗ среза префикса (games-proxy-game.inc): хаб роутит страницы игр НАТИВНО — /games/<id>/… уходит как есть (БАГ-5, review-002). kosynka — игра без бэкенд-роутинга, в regex не входит (strip-локация). Новая игра хаба = добавление id в regex в ekotov-wiki.conf
- sub_filter абсолютных путей хаба (href="/ → href="/games/, src="/ → src="/games/, fetch('/api/ → fetch('/games/api/, "/previews/ → "/games/previews/ — JSON /api/games) на text/html + application/javascript + text/javascript + application/json, sub_filter_once off; Accept-Encoding "" — сжатое тело не субфильтится; X-Frame-Options SAMEORIGIN — хаб сам фреймит игры в iframe
- контейнер убит → 502/504 от nginx на /games/*; остальные разделы живы. Деградации @*_down для хаба НЕ заведено (вне матрицы)
- auth на прокси НЕТ (P26 ТЗ)

## 10. manchkin — standalone в отдельном разделе сайта (2026-11-16)

Отдельное развертывание манчкина (репо `realax07/manchkin`), НЕ связано с версией в составе game-portal (`/games/munchkin/`, §9) — свои пулы лобби (in-memory, restart теряет лобби).

- **Контейнер:** `manchkin`, сеть `ekotov-wiki-par_default`, БЕЗ published-портов; внутренний порт **8382** (HOST=0.0.0.0, PORT=8382); код ro-маунтом: `-v /home/openclaw/manchkin:/srv:ro`, рабочая каталог `/srv`, команда `node server.mjs`. Поднимает ПМ (как §9).
- **URI:** `/manchkin/` (nginx `^~` со срезом префикса → `manchkin:8382`, `manchkin-proxy.inc`); `/manchkin` → 301.
- **Обновление:** `git -C /home/openclaw/manchkin pull` → `docker restart manchkin` (lobbies теряются).
- **Recreate:**
  `docker rm -f manchkin && docker run -d --name manchkin --network ekotov-wiki-par_default --restart unless-stopped -w /srv -v /home/openclaw/manchkin:/srv:ro -e HOST=0.0.0.0 -e PORT=8382 node:26-alpine node server.mjs`
- **Смоук:** `curl -sk https://127.0.0.1:10443/manchkin/` → 200; `/manchkin/api/lobbies` → JSON; сайдбар «Манчкин» → 200.
