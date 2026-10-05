# Отчет фикс-цикла review-004-1.2 (образы search/backup + compose)

Ветка: `add-microservices-full`. Корреляция flowctl: `756bade82bf24b56975cbfe3d4e4178b`.
Зона записи: `deploy/compose.yaml`, `deploy/compose.test.yaml`, `services/backup/**`,
`deploy/RUNBOOK.md`, `deploy/README.md`, `deploy/deploy.sh` — ничего вне зоны не менялось.

## Что сделано (по находкам)

### 1.2-a (major) — запись sidecar-бэкапа в прод-bind

Три части:

1. **`deploy/deploy.sh`, шаг 1/8 (предусловия)** — добавлен блок (только продовый
   compose-файл; `*compose.test.yaml*` пропускается — стенд пишет в
   `deploy/backups-test`):
   - `run mkdir -p "${BACKUP_DIR}"` — перенесен сюда из шага 2/8 (в 2/8
     удален, оставлен комментарий о переносе; дубля нет);
   - idempotent-проверка владельца: `stat -c %u` — если уже `10001`, каталог
     НЕ трогается (ветка `ok`); иначе `run chown 10001:10001` с `fail` при
     неудаче (sidecar-образ работает под `USER 10001`, числовой uid — не имя
     `wiki`, чей uid на хосте = 999). В DRY_RUN ветка печатает план stat/chown.
   Комментарии — только отдельными строками, внутри backslash-продолжений
   комментариев нет (регресс blocker 1.4-f не воспроизводится).
2. **`deploy/compose.yaml` (volumes backup)** — комментарий переписан: убрана
   ложная ссылка «deploy.sh уже делает это в шаге 2/7»; зафиксировано
   числовое требование `10001:10001` и что deploy.sh приводит права в шаге 1/8.
3. **`deploy/RUNBOOK.md`** — §5 (таблица отказов, строка «Бэкап не создался»):
   `chown wiki:wiki` → `chown 10001:10001` + указание на шаг 1/8 deploy.sh;
   §7.6 (описание шагов скрипта): добавлено, что предусловия включают
   `mkdir -p` + idempotent `chown 10001:10001` bind-каталога.
   **`deploy/README.md`** — раздел «Бэкап»: `chown wiki:wiki
   /var/backups/ekotov-wiki` → `chown 10001:10001` с обоснованием (uid образа
   10001; имя wiki на хосте может иметь другой uid) и указанием, что
   deploy.sh делает это в шаге 1/8.

   Прочие вхождения `chown wiki:wiki` в RUNBOOK/README (`/var/lib/ekotov-wiki*`,
   `/opt/ekotov-wiki`, avatars systemd-схемы) — легитимны (systemd-схема, юнит
   работает под пользователем `wiki`), к контейнерному bind-каталогу бэкапов
   отношения не имеют и не тронуты.

### 1.2-b (minor) — ложный комментарий в `services/backup/Dockerfile`

Комментарий HEALTHCHECK переформулирован: stale-heartbeat (> 2 интервалов) =
деградация → контейнер помечается **unhealthy**; Docker restart policy на
unhealthy НЕ реагирует — рестартует только при падении процесса
(`restart: unless-stopped` в compose); гейт деплоя — `wait_healthy` в deploy.sh
(шаг 5/8).

### 1.2-c (minor) — противоречивый комментарий тома в compose.yaml

`volumes.wiki-data`: «Бэкап — docker exec python sqlite3 .backup (design §6...)»
→ «Бэкап — сервис backup (sidecar, design §5): суточный цикл внутри контейнера
+ релизный бэкап в deploy.sh (шаг 2/8), оба — один модуль
services/backup/backup.py».

### 1.2-d (minor) — первый тик на пустом томе (`services/backup/backup.py`)

Выбран вариант **retry** (рекомендация ревью). В `main()`:
- env `BACKUP_FIRST_TICK_RETRIES` (дефолт 5) × `BACKUP_FIRST_TICK_RETRY_SEC`
  (дефолт 30s) = до 2.5 мин на первый старт app;
- первый цикл (до первого успеха) ретраится с печатью каждой попытки;
- при исчерпании — честный `SystemExit` (ненулевой код): контейнер падает,
  `restart: unless-stopped` поднимает снова (к тому моменту БД обычно создана);
- после первого успеха — прежний суточный ритм, ошибки последующих тиков
  (как раньше) процесс не убивают.

### 1.2-e (nit) — предусловие в шапке `deploy/compose.test.yaml`

Добавлено: перед первым `up` — `mkdir -p deploy/backups-test && chown
10001:10001 deploy/backups-test`, иначе backup не сможет писать и останется
unhealthy.

## Верификация (факты)

1. `bash -n deploy/deploy.sh` — OK (SYNTAX_OK).
2. **DRY_RUN=1 полный прогон** `RELEASE_TAG=p12-r1-fix12`, продовой compose:
   EXIT=0, `_green`-финал `[DRY-RUN] Ничего не изменено...` напечатан.
   Шаг 1/8 показывает новую ветку: `[DRY-RUN] mkdir -p /var/backups/ekotov-wiki`
   + `[DRY-RUN] stat -c %u ...  # владелец уже 10001 — не трогаем; иначе chown
   10001:10001`. Шаг 2/8 без повторного mkdir (перенесен в 1/8). Docker на
   машине доступен под `sg docker` (сокет root:docker) — прогон выполнен
   `sg docker -c 'bash deploy/deploy.sh'`.
3. **YAML-парсинг обоих compose** (`yaml.safe_load`): оба валидны, сервисы
   `app, backup, nginx, search` на месте.
4. `python3 -m py_compile services/backup/backup.py` — OK.
5. **Реплики логики `main()`** (python, подмененный run_backup):
   - первый тик: 2 падения → успех на 3-й попытке (ретраи работают, цикл
     продолжается);
   - исчерпание ретраев → `SystemExit` поднят;
   - ошибка последующего тика → процесс живет (поток жив).
6. **Grep-сверка**: в `deploy/compose.yaml`, `deploy/compose.test.yaml`,
   `deploy/deploy.sh`, `services/backup/` не осталось ссылок «шаг 2/7» и
   `chown wiki:wiki` на каталог бэкапов; в RUNBOOK/README все оставшиеся
   `chown wiki:wiki` относятся к systemd-схеме (`/var/lib/ekotov-wiki*`,
   `/opt`) — вне зоны находки.

## Известные ограничения

- Живой прогон backup-контейнера (ретраи в бою) не выполнялся — docker на
  машине разработки доступен только под `sg docker`, полный стенд в этом
  цикле не поднимался; логика ретраев покрыта репликами (п.5).
- `BACKUP_FIRST_TICK_*` env не добавлены в compose — работают дефолты 5×30s;
  оверрайд возможен через `environment` при необходимости.
