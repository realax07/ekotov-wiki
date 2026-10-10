#!/usr/bin/env bash
# ============================================================
# ekotov-wiki — деплой v3: МАТРИЦА СЕРВИСОВ (compose), P12 ЭТАП B.
# Change: add-microservices-full, задача 1.4 (FR-70/71/72 паритет);
# Design: openspec/changes/add-microservices-full/design.md §5/§6/§8;
# Runbook: deploy/RUNBOOK.md §7.
#
# Заменяет v2 (двухсервисную схему app+frontend задачи 1.6
# add-containerization; v2-логика сохранена там, где матрица ее не меняет).
#
# Запуск (Заказчик, из-под root, каталог — корень клона с целевым коммитом):
#   sudo RELEASE_TAG=<метка> bash deploy/deploy.sh
# Dry-run (ничего не меняет — ОБЯЗАТЕЛЕН до первой боевой выкатки):
#   DRY_RUN=1 RELEASE_TAG=<метка> bash deploy/deploy.sh
# Тестовый стенд (тот же скрипт, другой compose-файл/порт):
#   DRY_RUN=1 COMPOSE_FILE=deploy/compose.test.yaml PROJECT=wiki-test \
#   SMOKE_URL=https://127.0.0.1:8443 RELEASE_TAG=<метка> bash deploy/deploy.sh
#
# МАТРИЦА СЕРВИСОВ (design §6): SERVICES="app frontend search backup",
# теги образов ekotov-wiki/<name>:<RELEASE_TAG> (latest ЗАПРЕЩЕН — FR-72).
#
# Шаги (design §6): предусловия → бэкап (ДО ВСЕХ; вызывает МОДУЛЬ
# services/backup/backup.py — from backup import run_backup, один код с
# sidecar, БЕЗ дубля — design §5; релизный бэкап остается в деплое:
# wiki-pre-*/avatars-pre-*, sidecar-retention их не трогает) → build ВСЕХ
# образы матрицы → one-shot миграция ЯДРА (СТРОГО до up; search/backup —
# читатели, миграций не требуют — design §6) → up app → healthy →
# up search backup → healthy → up nginx → healthy → смоук-матрица:
# health app, health search, поиск через nginx (маршрутизация + X-Service:
# search), статика (+ smoke_static.py), аватары, 502=0 (502>0 — FAIL),
# «образы контейнеров = релизные теги» → docker image prune -f.
# Останов на любой ошибке (set -euo pipefail).
#
# Откат (design §8): тегом КАЖДОГО сервиса — по умолчанию совместимая пара
# (app+search) катится одним RELEASE_TAG; горячий фикс одного сервиса —
# его тегом точечно (RUNBOOK §7.6).
# ============================================================
set -euo pipefail

# --- Параметры (переопределяются env) --------------------------------------
RELEASE_TAG="${RELEASE_TAG:-}"                    # МЕТКА РЕЛИЗА: ekotov-wiki/<name>:<RELEASE_TAG>
SERVICES="${SERVICES:-app frontend search images backup}"  # МАТРИЦА (design §6 + images с add-gallery-service) — менять осознанно
SRC_DIR="${SRC_DIR:-/opt/ekotov-wiki}"            # клона с целевым коммитом (контекст сборки)
BACKUP_DIR="${BACKUP_DIR:-/var/backups/ekotov-wiki}"
COMPOSE_DIR="${COMPOSE_DIR:-${SRC_DIR}/deploy}"   # где deploy/.env с SECRET_KEY
COMPOSE_FILE="${COMPOSE_FILE:-deploy/compose.yaml}"  # путь ОТНОСИТЕЛЬНО корня клона (или абсолютный)
PROJECT="${PROJECT:-ekotov-wiki}"                 # имя compose-проекта
DB_PATH_IN_CONTAINER="${DB_PATH_IN_CONTAINER:-/data/wiki.db}"
AVATARS_DIR_IN_CONTAINER="${AVATARS_DIR_IN_CONTAINER:-/data/avatars}"
IMAGES_DIR_IN_CONTAINER="${IMAGES_DIR_IN_CONTAINER:-/data/images}"  # J38: том галереи в релизный бэкап
EXPECTED_COMMIT="${EXPECTED_COMMIT:-}"            # пусто = самовычисление из HEAD клона (урок 5b)
MIGRATE_MODULE="${MIGRATE_MODULE:-}"              # напр. app.migrate_r4; пусто = шаг пропускается
SMOKE_URL="${SMOKE_URL:-https://127.0.0.1:10443}" # база смоука (тестовый стенд: https://127.0.0.1:8443)
DRY_RUN="${DRY_RUN:-0}"

# Теги матрицы: базовое имя + по-сервисный оверрайд (горячий фикс одного
# сервиса — design §6/§8; compose-переменные APP_IMAGE/FRONTEND_IMAGE/
# SEARCH_IMAGE/BACKUP_IMAGE — имена СИНХРОННЫ deploy/compose.yaml*).
TARGET_LABEL="${RELEASE_TAG}"
APP_IMAGE="${APP_IMAGE:-ekotov-wiki/app:${RELEASE_TAG}}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-ekotov-wiki/frontend:${RELEASE_TAG}}"
SEARCH_IMAGE="${SEARCH_IMAGE:-ekotov-wiki/search:${RELEASE_TAG}}"
BACKUP_IMAGE="${BACKUP_IMAGE:-ekotov-wiki/backup:${RELEASE_TAG}}"
IMAGES_IMAGE="${IMAGES_IMAGE:-ekotov-wiki/images:${RELEASE_TAG}}"

# Карта сервис → Dockerfile (контекст сборки — корень клона; так же делают
# compose-файлы). Нейминг compose-сервисов: frontend-образ носит сервис
# nginx — учесть в матрице и в проверке образов (функция image_for).
dockerfile_for() {
  case "$1" in
    app)      echo "services/app/Dockerfile" ;;
    frontend) echo "services/frontend/Dockerfile" ;;
    search)   echo "services/search/Dockerfile" ;;
    images)   echo "services/images/Dockerfile" ;;
    backup)   echo "services/backup/Dockerfile" ;;
    *)        return 1 ;;
  esac
}
image_for() {  # образ контейнера compose-сервиса
  case "$1" in
    app)      echo "${APP_IMAGE}" ;;
    frontend) echo "${FRONTEND_IMAGE}" ;;   # compose-сервис nginx
    nginx)    echo "${FRONTEND_IMAGE}" ;;
    search)   echo "${SEARCH_IMAGE}" ;;
    images)   echo "${IMAGES_IMAGE}" ;;
    backup)   echo "${BACKUP_IMAGE}" ;;
    *)        return 1 ;;
  esac
}

STAMP="$(date +%F-%H%M)"
DB_BACKUP="${BACKUP_DIR}/wiki-pre-${TARGET_LABEL}-${STAMP}.db"
IMAGES_BACKUP="${BACKUP_DIR}/images-pre-${TARGET_LABEL}-${STAMP}.tar.gz"  # J38: images-data в релизный контур (RUNBOOK §5)
AVATARS_BACKUP="${BACKUP_DIR}/avatars-pre-${TARGET_LABEL}-${STAMP}.tar"

log()  { echo -e "\n\033[1;34m==> $*\033[0m"; }
ok()   { echo -e "\033[1;32m[OK]\033[0m $*"; }
fail() { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; exit 1; }
# run: печатает команду и НЕ выполняет (мутации в dry-run).
run()  { if [ "${DRY_RUN}" = "1" ]; then echo "   [DRY-RUN] $*"; else "$@"; fi; }

# --- Валидация релизного тега (FR-72: latest ЗАПРЕЩЕН) -----------------------
case "${RELEASE_TAG}" in
  ""|latest|Latest|LATEST|:latest)
    fail "RELEASE_TAG не задан или равен 'latest' — тег latest ЗАПРЕЩЕН (FR-72, tasks 1.4). Задай релизную метку, например: RELEASE_TAG=p12-r1 bash $0" ;;
esac
case "${RELEASE_TAG}" in
  *[!A-Za-z0-9._-]*)
    fail "RELEASE_TAG='${RELEASE_TAG}' содержит недопустимые символы (разрешены A-Za-z0-9._-) — иначе docker отвергнет тег." ;;
esac

# --- 1/8 Предусловия ---------------------------------------------------------
log "1/8 Предусловия (матрица: ${SERVICES})"
for tool in docker curl git python3 tar; do
  command -v "$tool" >/dev/null || fail "Нет утилиты: $tool"
done
docker compose version >/dev/null || fail "Нет compose plugin"
[ -d "${SRC_DIR}/.git" ] || fail "Нет клона с целевым коммитом: ${SRC_DIR}"
for svc in ${SERVICES}; do
  [ -f "${SRC_DIR}/$(dockerfile_for "${svc}")" ] || fail "Нет $(dockerfile_for "${svc}") в ${SRC_DIR}"
done
[ -f "${SRC_DIR}/services/backup/backup.py" ] || fail "Нет services/backup/backup.py (модуль релизного бэкапа, design §5)"
[ -f "${SRC_DIR}/${COMPOSE_FILE}" ] || fail "Нет compose-файла ${SRC_DIR}/${COMPOSE_FILE}"
if [ "${DRY_RUN}" != "1" ]; then
  # .env с SECRET_KEY обязателен только у продового compose (стенд — TEST_SECRET_KEY-дефолт)
  case "${COMPOSE_FILE}" in
    *compose.test.yaml*) : ;;
    *) [ -f "${COMPOSE_DIR}/.env" ] || fail "Нет ${COMPOSE_DIR}/.env с SECRET_KEY (RUNBOOK §7.1 п.3) — боевой up невозможен" ;;
  esac
fi

# 1.2-a (review-004-1.2): права на bind-каталог бэкапов для sidecar. Образ
# backup работает под USER 10001 — проверяем/ставим ЧИСЛОВОЙ uid 10001:10001
# (имя wiki на хосте может иметь другой uid). Idempotent: владелец уже 10001 —
# не трогаем. Только продовый compose-файл (стенд пишет в deploy/backups-test,
# compose.test.yaml). mkdir -p здесь (не только в 2/8): stat/chown ниже требуют
# существования каталога уже в предусловиях.
case "${COMPOSE_FILE}" in
  *compose.test.yaml*) : ;;
  *)
    run mkdir -p "${BACKUP_DIR}"
    if [ "${DRY_RUN}" = "1" ]; then
      echo "   [DRY-RUN] stat -c %u ${BACKUP_DIR}   # dry-run: проверка прав НЕ выполнялась (будет при реальном прогоне; если владелец не 10001 — chown 10001:10001)"
    elif [ "$(stat -c %u "${BACKUP_DIR}" 2>/dev/null)" = "10001" ]; then
      ok "BACKUP_DIR ${BACKUP_DIR}: владелец уже 10001 — sidecar-бэкап запишет"
    else
      run chown 10001:10001 "${BACKUP_DIR}" \
        || fail "Не удалось chown 10001:10001 ${BACKUP_DIR} — sidecar-бэкап (uid 10001) не сможет писать (1.2-a, review-004-1.2)"
      ok "BACKUP_DIR ${BACKUP_DIR}: владелец приведен к 10001:10001"
    fi
    ;;
esac

COMPOSE="docker compose -f ${COMPOSE_FILE} -p ${PROJECT} ${COMPOSE_EXTRA:-}"
# ОГРАНИЧЕНИЕ (nit 1.4-d, review-001): ${COMPOSE} сознательно НЕ квочен —
# слова команды получаются разбиением; пути COMPOSE_FILE/PROJECT/COMPOSE_EXTRA
# с пробелами сломают разбиение. Для зафиксированных прод/стенд-путей
# (/opt/ekotov-wiki, deploy/compose.yaml, wiki-test) не актуально.
# COMPOSE_EXTRA: дополнительные -f (override) — тестовые прогоны, напр. self-signed
# серты во временном каталоге вместо хостовых /etc/nginx/ssl. В бою пусто.
# CONTEXT_DIR: каталог, из которого резолвится относительный COMPOSE_FILE
# (compose -f интерпретирует относительный путь от текущего каталога).
CONTEXT_DIR="${SRC_DIR}"

CURRENT=$(git -C "${SRC_DIR}" -c safe.directory="${SRC_DIR}" rev-parse --short HEAD)
if [ -z "${EXPECTED_COMMIT}" ]; then
  EXPECTED_COMMIT="${CURRENT}"
  ok "EXPECTED_COMMIT не задан — самовычислен из HEAD клона: ${EXPECTED_COMMIT} (урок 5b)"
fi
[ "${CURRENT}" = "${EXPECTED_COMMIT}" ] || fail "Клон на ${CURRENT}, ожидался EXPECTED_COMMIT=${EXPECTED_COMMIT}. Синхронизируй клон."
ok "Клон на целевом коммите ${CURRENT}"

# docker socket доступен? (если нет — fail сразу, а не посреди деплоя)
docker info >/dev/null 2>&1 || fail "docker недоступен (права на сокет). Проверь группу docker или запусти из-под root."

# --- 2/8 Бэкап ДО ВСЕХ (модуль services/backup/backup.py; design §5/§6) ------
# ОДИН код с sidecar: из работающего контейнера app (том wiki-data смонтирован
# у него) вызывается from backup import run_backup — тот же модуль, что крутит
# cron-цикл backup-контейнера. Модуль копируется в /tmp КОНТЕЙНЕРА (в образе
# app его нет), пишет во временный каталог контейнера, вынос — tar-потоком
# (том снаружи /var/lib/docker/volumes требует root) в STAGING-каталог хоста.
# Затем на хосте mv свежевынесенных файлов в релизные имена
# wiki-pre-*/avatars-pre-* — sidecar-retention (design §5) их НЕ трогает:
# релизный бэкап остается в деплое навсегда, sidecar страхует МЕЖДУ релизами.
RELEASE_STAGING="${RELEASE_STAGING:-${BACKUP_DIR}/release-staging}"
log "2/8 Бэкап до деплоя (БД + аватары, модуль backup.run_backup) → ${BACKUP_DIR}"
# mkdir -p BACKUP_DIR выполнен в шаге 1/8 (вместе с chown 10001:10001 — 1.2-a):
# здесь повторно не делаем (idempotent-оверрайд не нужен, каталог уже есть).

APP_CID="$(${COMPOSE} ps -q app 2>/dev/null || true)"
if [ -z "${APP_CID}" ] && [ "${DRY_RUN}" != "1" ]; then
  fail "Контейнер app не найден (${COMPOSE} ps -q app пуст) — бэкап из контейнера невозможен. Подними стек: cd ${COMPOSE_DIR} && ${COMPOSE} up -d (первый up — по RUNBOOK §7.3/§7.6), затем повтори деплой."
fi

if [ "${DRY_RUN}" = "1" ]; then
  echo "   [DRY-RUN] ${COMPOSE} exec -T app sh -c 'cat > /tmp/backup.py' < ${SRC_DIR}/services/backup/backup.py"
  echo "   [DRY-RUN] ${COMPOSE} exec -T -e BACKUP_DIR=/tmp/.deploy-bk -e EKOTOV_WIKI_DB_PATH=${DB_PATH_IN_CONTAINER} -e EKOTOV_WIKI_AVATARS_DIR=${AVATARS_DIR_IN_CONTAINER} app python -c 'import sys; sys.path.insert(0,\"/tmp\"); from backup import run_backup; run_backup()'"
  echo "   [DRY-RUN] ${COMPOSE} exec -T app tar -cf - -C /tmp/.deploy-bk . | tar -x --strip-components=1 --touch --no-same-owner --no-same-permissions -f - -C ${RELEASE_STAGING}   # вынос из контейнера в staging (метаданные './' недоступны юзеру хоста — фикс p15-tar-fix)"
  echo "   [DRY-RUN] ${COMPOSE} exec -T app rm -rf /tmp/.deploy-bk /tmp/backup.py"
  echo "   [DRY-RUN] mv ${RELEASE_STAGING}/wiki-daily-*.db → ${DB_BACKUP}; ${RELEASE_STAGING}/avatars-daily-*.tar → ${AVATARS_BACKUP}  # релизные имена (staging: суточная история sidecar в ${BACKUP_DIR} не тронута); sidecar-retention их не трогает"
  echo "   [DRY-RUN] ${COMPOSE} exec -T images tar -czf - -C /data images | cat > ${IMAGES_BACKUP}  # J38: том галереи (оригинал+превью) в релизный контур"
  echo "   [DRY-RUN] rmdir ${RELEASE_STAGING} 2>/dev/null || true   # staging пуст после mv (суточная история sidecar в ${BACKUP_DIR} НЕ тронута)"
else
  run mkdir -p "${RELEASE_STAGING}"
  ${COMPOSE} exec -T app sh -c 'cat > /tmp/backup.py' < "${SRC_DIR}/services/backup/backup.py" \
    || fail "Модуль backup.py не скопирован в контейнер app"
  ${COMPOSE} exec -T -e BACKUP_DIR=/tmp/.deploy-bk \
    -e EKOTOV_WIKI_DB_PATH="${DB_PATH_IN_CONTAINER}" \
    -e EKOTOV_WIKI_AVATARS_DIR="${AVATARS_DIR_IN_CONTAINER}" \
    -e BACKUP_RETENTION_DAYS=36500 \
    app python -c "import sys; sys.path.insert(0, '/tmp'); from backup import run_backup; run_backup()" \
    || fail "Релизный бэкап не создан (backup.run_backup упал) — деплой прерван, БД не тронута."
  # nit 1.4-e: 36500 ~ 100 лет — чтобы prune внутри временного /tmp/.deploy-bk
  # контейнера гарантированно ничего не удалил (retention на хосте ведет sidecar).
  # Комментарий ДОЛЖЕН стоять ВНЕ backslash-продолжения: bash обрывает команду
  # на комментарии внутри продолжения (ловится только живым прогоном, не bash -n
  # и не DRY_RUN — регресс review-002-1.4, blocker 1.4-f).
  # Вынос из контейнера (фикс p15-tar-fix): распаковка идет на ХОСТЕ от
  # пользователя хоста (не root, не 10001-владелец staging) — GNU tar при
  # дефолтных флагах восстанавливает метаданные корневого члена './'
  # (chown/chmod/utime на СУЩЕСТВУЮЩИЙ каталог staging) и падает
  # «Operation not permitted» (прецедент: 2 живых прогона p15-wiki-1).
  # --strip-components=1 срезает корневой член './' целиком (файлы ложатся
  # прямо в staging), --touch/--no-same-owner/--no-same-permissions снимают
  # остальные попытки метаданных. Проверено репликой tar-пайпа против
  # боевого staging: без флагов exit 2 (utime+chmod на '.'), с флагами
  # exit 0 дважды (в т.ч. повторный прогон по существующим файлам).
  # ЗАМЕЧАНИЕ: даже с флагами staging обязан существовать и быть доступным
  # на запись пользователю хоста (mkdir -p выше от его имени; mode 0700
  # от 10001 сделал бы его недоступным — см. эскалацию в PR).
  ${COMPOSE} exec -T app tar -cf - -C /tmp/.deploy-bk . | \
    tar -x --strip-components=1 --touch --no-same-owner --no-same-permissions -f - -C "${RELEASE_STAGING}" \
    || fail "Бэкап не вынесен из контейнера (tar-поток в ${RELEASE_STAGING})"
  ${COMPOSE} exec -T app rm -rf /tmp/.deploy-bk /tmp/backup.py \
    || ok "cleanup временных файлов контейнера не удался (не критично)"
  # Релизные имена поверх служебных daily-* модуля (run_backup имена не
  # параметризует — переименовываем на хосте; sidecar-retention считает
  # wiki-pre-*/avatars-pre-* чужими и никогда не удаляет). Вынос шел в
  # STAGING (1.4-a, review-001): mv только свежевынесенных файлов, суточная
  # история sidecar в ${BACKUP_DIR} НЕ затрагивается.
  moved=0
  for f in "${RELEASE_STAGING}"/wiki-daily-*.db; do
    [ -e "${f}" ] && mv -f "${f}" "${DB_BACKUP}" && moved=$((moved + 1))
  done
  [ "${moved}" -eq 1 ] || fail "В ${RELEASE_STAGING} не найден свежевынесенный бэкап БД (wiki-daily-*.db: ${moved} шт.) — вынос из контейнера не сработал."
  moved=0
  for f in "${RELEASE_STAGING}"/avatars-daily-*.tar; do
    [ -e "${f}" ] && mv -f "${f}" "${AVATARS_BACKUP}" && moved=$((moved + 1))
  done
  [ "${moved}" -eq 1 ] || fail "В ${RELEASE_STAGING} не найден свежевынесенный tar аватаров (avatars-daily-*.tar: ${moved} шт.) — вынос из контейнера не сработал."
  rmdir "${RELEASE_STAGING}" 2>/dev/null || ok "staging ${RELEASE_STAGING} не пуст после mv (остатки не мешают — retention их не трогает)"
  [ -s "${DB_BACKUP}" ] || fail "Файл бэкапа БД пуст или отсутствует: ${DB_BACKUP}"
  ok "Бэкап БД: $(du -h "${DB_BACKUP}" | cut -f1) — ${DB_BACKUP} (история sidecar в ${BACKUP_DIR} не тронута)"
  [ -s "${AVATARS_BACKUP}" ] || fail "Файл бэкапа аватаров отсутствует: ${AVATARS_BACKUP}"
  ok "Бэкап аватаров: $(du -h "${AVATARS_BACKUP}" | cut -f1) — ${AVATARS_BACKUP}"
  # J38: том галереи images-data (оригинал + превью) в релизный контур.
  # RUNBOOK §5: до этого бэкап покрывал только БД+avatars — картинки P14-галереи
  # перед накаткой не сохранялись. tar из images-контейнера (uid 10001, файлы читает).
  IMAGES_CID="$(${COMPOSE} ps -q images 2>/dev/null || true)"
  if [ -n "${IMAGES_CID}" ]; then
    ${COMPOSE} exec -T images tar -czf - -C /data images | cat > "${IMAGES_BACKUP}" \
      || fail "Бэкап images-data не создан (tar из images-контейнера упал) — деплой прерван."
    [ -s "${IMAGES_BACKUP}" ] || fail "Файл бэкапа галереи пуст: ${IMAGES_BACKUP}"
    ok "Бэкап галереи: $(du -h "${IMAGES_BACKUP}" | cut -f1) — ${IMAGES_BACKUP}"
  else
    fail "Контейнер images не найден (${COMPOSE} ps -q images пуст), а images в матрице — бэкап галереи невозможен. Подними стек и повтори."
  fi
fi

# --- 3/8 Сборка ВСЕХ образов матрицы с релизными тегами -----------------------
log "3/8 Сборка образов матрицы (${SERVICES}) — теги <base>:<release>, latest запрещен (FR-72)"
for svc in ${SERVICES}; do
  run docker build -f "${SRC_DIR}/$(dockerfile_for "${svc}")" -t "$(image_for "${svc}")" "${SRC_DIR}"
done
ok "Образы собраны (после сборки проверить: docker image ls | grep ekotov-wiki)"

# --- 4/8 One-shot миграция ЯДРА — СТРОГО до up (design §6: search/backup —
#     читатели одной схемы, миграции им не нужны) ------------------------------
if [ -n "${MIGRATE_MODULE}" ]; then
  log "4/8 One-shot миграция ядра: ${COMPOSE} run --rm app python -m ${MIGRATE_MODULE} (до up)"
  if [ "${DRY_RUN}" = "1" ]; then
    echo "   [DRY-RUN] ${COMPOSE} run --rm --no-deps -e DB_PATH=${DB_PATH_IN_CONTAINER} -e SECRET_KEY=[REDACTED] app python -m ${MIGRATE_MODULE}"
  else
    env APP_IMAGE="${APP_IMAGE}" FRONTEND_IMAGE="${FRONTEND_IMAGE}" SEARCH_IMAGE="${SEARCH_IMAGE}" BACKUP_IMAGE="${BACKUP_IMAGE}" IMAGES_IMAGE="${IMAGES_IMAGE}" \
      ${COMPOSE} run --rm --no-deps -e DB_PATH="${DB_PATH_IN_CONTAINER}" -e SECRET_KEY="x" app \
      python -m "${MIGRATE_MODULE}" \
      || fail "Миграция ${MIGRATE_MODULE} не прошла — деплой прерван ДО up (старый контейнер продолжает работать). БД восстанови из ${DB_BACKUP}."
    ok "Миграция ${MIGRATE_MODULE} применена"
  fi
else
  log "4/8 Миграция: MIGRATE_MODULE не задан — шаг пропущен (миграционные релизы: MIGRATE_MODULE=app.migrate_rN)"
fi

# --- 5/8 Подъем матрицы ПОСЛЕДОВАТЕЛЬНО (design §6): app → healthy →
#     search+backup → healthy → nginx ------------------------------------------
# wait_healthy: compose healthcheck сервиса (ps --format Health).
wait_healthy() { # $1 = compose-сервис, $2 = число попыток (x5s)
  local svc="$1" i st=""
  for i in $(seq 1 "${2:-12}"); do
    st="$(${COMPOSE} ps --format '{{.Service}} {{.Health}}' 2>/dev/null | awk -v s="${svc}" '$1==s{print $2}')"
    [ "${st}" = "healthy" ] && return 0
    sleep 5
  done
  return 1
}

log "5/8 Up матрицы: app → healthy → search+backup → healthy → nginx"
run env APP_IMAGE="${APP_IMAGE}" FRONTEND_IMAGE="${FRONTEND_IMAGE}" SEARCH_IMAGE="${SEARCH_IMAGE}" BACKUP_IMAGE="${BACKUP_IMAGE}" IMAGES_IMAGE="${IMAGES_IMAGE}" \
  ${COMPOSE} up -d app
if [ "${DRY_RUN}" != "1" ]; then
  wait_healthy app 12 || fail "app не стал healthy за 60s: ${COMPOSE} ps; логи: docker compose logs app"
  ok "app healthy (${APP_IMAGE})"
fi

run env APP_IMAGE="${APP_IMAGE}" FRONTEND_IMAGE="${FRONTEND_IMAGE}" SEARCH_IMAGE="${SEARCH_IMAGE}" BACKUP_IMAGE="${BACKUP_IMAGE}" IMAGES_IMAGE="${IMAGES_IMAGE}" \
  ${COMPOSE} up -d search images backup
if [ "${DRY_RUN}" != "1" ]; then
  wait_healthy search 12 || fail "search не стал healthy за 60s: ${COMPOSE} ps; логи: docker compose logs search"
  ok "search healthy (${SEARCH_IMAGE})"
  # J38: images в матрице подъема (зависит от app: схема БД на пустом томе).
  wait_healthy images 12 || fail "images не стал healthy за 60s: ${COMPOSE} ps; логи: docker compose logs images"
  ok "images healthy (${IMAGES_IMAGE})"
  # backup: health по heartbeat (interval 60s, start_period 30s) — запас выше.
  wait_healthy backup 24 || fail "backup не стал healthy за 120s: ${COMPOSE} ps; логи: docker compose logs backup"
  ok "backup healthy (${BACKUP_IMAGE}) — sidecar поднят, релизный бэкап (шаг 2/8) остался в ${BACKUP_DIR}"
fi

run env APP_IMAGE="${APP_IMAGE}" FRONTEND_IMAGE="${FRONTEND_IMAGE}" SEARCH_IMAGE="${SEARCH_IMAGE}" BACKUP_IMAGE="${BACKUP_IMAGE}" IMAGES_IMAGE="${IMAGES_IMAGE}" \
  ${COMPOSE} up -d nginx
if [ "${DRY_RUN}" != "1" ]; then
  wait_healthy nginx 12 || fail "nginx не стал healthy за 60s: ${COMPOSE} ps; логи: docker compose logs nginx"
  ok "nginx healthy (${FRONTEND_IMAGE})"
fi

# --- 6/8 Смоук-матрица (обязателен; design §6) --------------------------------
log "6/8 Смоук: health app + health search + поиск через nginx (X-Service) + статика + аватары + 502=0 + образы=теги"
if [ "${DRY_RUN}" = "1" ]; then
  echo "   [DRY-RUN] curl -sk ${SMOKE_URL}/api/health            # app: {\"status\":\"ok\"}, 200"
  echo "   [DRY-RUN] ${COMPOSE} exec -T search python -c 'urllib http://127.0.0.1:8378/api/health == 200'   # health search напрямую"
  echo "   [DRY-RUN] curl -sk -D - -o /dev/null '${SMOKE_URL}/api/search?q=smoke'   # через nginx: X-Service: search; код 200/401/422 от search (502/503 = FAIL)"
  echo "   [DRY-RUN] curl -sk -o /dev/null -w '%{http_code}' ${SMOKE_URL}/login                  # 200"
  echo "   [DRY-RUN] curl -sk -o /dev/null -w '%{http_code}' ${SMOKE_URL}/static/css/app.css     # 200"
  echo "   [DRY-RUN] curl -sk -o /dev/null -w '%{http_code}' ${SMOKE_URL}/avatars/               # 200/403/404 — НЕ 502"
  echo "   [DRY-RUN] docker logs \$(nginx) | grep -c ' 502 '   # 502 = 0 (stale-DNS контроль, design §1)"
  echo "   [DRY-RUN] ${COMPOSE} ps --format '{{.Service}} {{.Image}}'   # образы = релизные теги матрицы"
  echo "   [DRY-RUN] ${SRC_DIR}/scripts/smoke_static.py --repo ${SRC_DIR} --base ${SMOKE_URL} --insecure"
  echo -e "\n\033[1;33m[DRY-RUN] Ничего не изменено. Для боевого деплоя: sudo RELEASE_TAG=<метка> bash $0\033[0m"
  exit 0
fi

# 6.1 health app (через nginx — пользовательский путь)
H="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "${SMOKE_URL}/api/health" || true)"
[ "${H}" = "200" ] || fail "health app через nginx: ${H} (ожидался 200)"
ok "health app: 200"

# 6.2 health search (напрямую в контейнере: порт 8378 наружу не публикуется)
if ${COMPOSE} exec -T search python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8378/api/health', timeout=5).status == 200 else 1)"; then
  ok "health search: 200 (напрямую)"
else
  fail "health search не ответил 200 — смотри docker compose logs search"
fi

# 6.3 Поиск ЧЕРЕЗ NGINX: маршрутизация search-семейства (задача 1.3) +
# заголовок X-Service: search. Без сессии сервис ответит 401 (middleware),
# без параметра q — 422: ОБА кода = «ответил search», маршрутизация доказана
# заголовком X-Service (его ставит ТОЛЬКО search-локация nginx). 502/503/000 —
# провал (поиск не маршрутизируется / search недоступен).
_search_smoke() {
  local code xsvc
  code="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "${SMOKE_URL}/api/search?q=smoke" || true)"
  xsvc="$(curl -sk -D - -o /dev/null --max-time 5 "${SMOKE_URL}/api/search?q=smoke" 2>/dev/null | tr -d '\r' | awk 'tolower($1)=="x-service:"{print $2}')"
  case "${code}" in
    200|401|422) : ;;
    *) fail "поиск через nginx: ${code} (ожидался 200/401/422 от search; 502/503 = маршрутизация/search сломаны, design §4)" ;;
  esac
  [ "${xsvc}" = "search" ] || fail "поиск через nginx: нет заголовка X-Service: search (получено: '${xsvc}') — локация /api/search не задействована"
  ok "поиск через nginx: ${code} + X-Service: search (401/422 = search ответил без сессии/параметров — маршрутизация доказана)"
}
_search_smoke

# 6.4 Страница логина (ядро)
P="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "${SMOKE_URL}/login" || true)"
[ "${P}" = "200" ] || fail "/login через nginx: ${P} (ожидался 200)"
ok "/login: 200"

# 6.5 Статика из образа nginx
S="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "${SMOKE_URL}/static/css/app.css" || true)"
[ "${S}" = "200" ] || fail "Статика через nginx: ${S} (ожидался 200 — статика из образа nginx)"
ok "/static/css/app.css: 200"

# 6.6 Аватары из тома (не 502)
A="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "${SMOKE_URL}/avatars/" || true)"
case "${A}" in
  200|403|404) ok "/avatars/: ${A} (не 502)" ;;
  *) fail "/avatars/: ${A} (ожидалось 200/403/404)" ;;
esac

# 6.7 502 = 0 в логах nginx (stale-DNS контроль, design §1; к 503 search-деградации
# это не относится — управляемый ответ error_page, не 502-залипание)
NGINX_502="$(docker logs "$(${COMPOSE} ps -q nginx)" 2>&1 | grep -c ' 502 ' || true)"
if [ "${NGINX_502}" != "0" ]; then
  fail "в логах nginx ${NGINX_502}х 502 (ожидалось 0 — stale-DNS контроль, design §1); 503 от остановленного search — не считается (управляемый error_page)"
fi
ok "Логи nginx: 502 не обнаружено"

# 6.8 Образы контейнеров = релизные теги матрицы (FR-72: latest запрещен)
_matrix_images() {
  local svc expected actual
  actual="$(${COMPOSE} ps --format '{{.Service}} {{.Image}}')"
  for svc in app nginx search images backup; do
    expected="$(image_for "${svc}")"
    echo "${actual}" | awk -v s="${svc}" '$1==s{print $2}' | grep -qx "${expected}" \
      || fail "Контейнер ${svc} работает на образе '$(echo "${actual}" | awk -v s="${svc}" '$1==s{print $2}')', ожидался релизный тег '${expected}'"
    case "${expected}" in
      *:latest|*:latest@*) fail "Образ ${svc} тегирован latest — ЗАПРЕЩЕНО (FR-72)" ;;
    esac
  done
}
_matrix_images
ok "Образы контейнеров = релизные теги: app=${APP_IMAGE} nginx=${FRONTEND_IMAGE} search=${SEARCH_IMAGE} backup=${BACKUP_IMAGE}"

# 6.9 Полный смоук статики E10 — против контейнерного nginx (статика в образе)
if python3 "${SRC_DIR}/scripts/smoke_static.py" --repo "${SRC_DIR}" --base "${SMOKE_URL}" --insecure; then
  ok "Смоук статики (E10): все UI-ресурсы отдаются"
else
  fail "Смоук статики (E10): часть UI-ресурсов не отдается (класс DEF-002)"
fi

# --- 7/8 Гигиена dangling-образов (RUNBOOK §7.6) -------------------------------
log "7/8 docker image prune -f (dangling-слои после пересборки; отказ prune не роняет успешный деплой)"
run docker image prune -f || echo " [WARN] image prune не прошел (гигиена, не влияет на деплой)"

# --- 8/8 Итог -------------------------------------------------------------------
echo -e "\n\033[1;32m============================================"
echo -e "ДЕПЛОЙ ${TARGET_LABEL} ЗАВЕРШЕН УСПЕШНО (матрица: ${SERVICES})"
echo -e "============================================\033[0m"
echo "Коммит:         ${CURRENT}"
echo "Образы:         app=${APP_IMAGE}"
echo "                nginx=${FRONTEND_IMAGE}"
echo "                search=${SEARCH_IMAGE}"
echo "                backup=${BACKUP_IMAGE}"
echo "Бэкап БД:       ${DB_BACKUP}"
echo "Бэкап аватаров: ${AVATARS_BACKUP}"
echo ""
echo "Ручной смоук в браузере: логин → доска → поиск. Откат (design §8):"
echo "предыдущим RELEASE_TAG целиком; горячий фикс одного сервиса — его тегом:"
echo "  APP_IMAGE=ekotov-wiki/app:<пред> SEARCH_IMAGE=ekotov-wiki/search:<пред> \\"
echo "  ${COMPOSE} up -d app search"
echo "Несовместимая схема — БД из ${DB_BACKUP} (RUNBOOK §7.6)."