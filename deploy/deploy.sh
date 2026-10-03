#!/usr/bin/env bash
# ============================================================
# ekotov-wiki — деплой v2: контейнерный (compose), P11 ЭТАП 1.
# Change: add-containerization, задача 1.6 (FR-70/71/72, NFR-9/11);
# Runbook: deploy/RUNBOOK.md §7; Design: openspec §6.
#
# Заменяет rsync/pip/systemd-схему (сохранена как deploy/deploy-v1-systemd.sh —
# откат на systemd, ЭТАП 2 / RUNBOOK §7.6).
#
# Запуск (Заказчик, из-под root, каталог — корень клона с целевым коммитом):
#   sudo bash deploy/deploy.sh
# Dry-run (ничего не меняет — ОБЯЗАТЕЛЕН до первой боевой выкатки):
#   DRY_RUN=1 bash deploy/deploy.sh
# Тестовый стенд (тот же скрипт, другой compose-файл/порт):
#   DRY_RUN=1 COMPOSE_FILE=deploy/compose.test.yaml PROJECT=wiki-test \
#   APP_IMAGE=ekotov-wiki/app:local FRONTEND_IMAGE=ekotov-wiki/frontend:local \
#   SMOKE_URL=https://127.0.0.1:8443 bash deploy/deploy.sh
#
# Шаги: предусловия → бэкап (БД python sqlite3 .backup через docker exec,
# аватары tar тома — БЕЗ остановки) → build образов <release> → one-shot
# миграция (СТРОГО до up) → up → смоук (health/login/static/avatars + «nginx
# не отдает 502 после up нового app» — stale-DNS, design §1; fallback —
# docker compose restart nginx) → docker image prune -f.
# Останов на любой ошибке (set -euo pipefail).
#
# latest ЗАПРЕЩЕН (FR-72): без RELEASE_TAG или с RELEASE_TAG=latest скрипт падает.
# ============================================================
set -euo pipefail

# --- Параметры (переопределяются env) --------------------------------------
RELEASE_TAG="${RELEASE_TAG:-}"                    # МЕТКА РЕЛИЗА: ekotov-wiki/{app,frontend}:<RELEASE_TAG>
APP_IMAGE_BASE="${APP_IMAGE_BASE:-ekotov-wiki/app}"
FRONTEND_IMAGE_BASE="${FRONTEND_IMAGE_BASE:-ekotov-wiki/frontend}"
SRC_DIR="${SRC_DIR:-/opt/ekotov-wiki}"            # клона с целевым коммитом (контекст сборки)
BACKUP_DIR="${BACKUP_DIR:-/var/backups/ekotov-wiki}"
COMPOSE_DIR="${COMPOSE_DIR:-${SRC_DIR}/deploy}"   # где лежит compose.yaml (и deploy/.env с SECRET_KEY)
COMPOSE_FILE="${COMPOSE_FILE:-deploy/compose.yaml}"  # путь ОТНОСИТЕЛЬНО корня клона (или абсолютный)
PROJECT="${PROJECT:-ekotov-wiki}"                 # имя compose-проекта
DB_PATH_IN_CONTAINER="${DB_PATH_IN_CONTAINER:-/data/wiki.db}"
AVATARS_DIR_IN_CONTAINER="${AVATARS_DIR_IN_CONTAINER:-/data/avatars}"
EXPECTED_COMMIT="${EXPECTED_COMMIT:-}"            # пусто = самовычисление из HEAD клона (урок 5b)
MIGRATE_MODULE="${MIGRATE_MODULE:-}"              # напр. app.migrate_r4; пусто = шаг пропускается
SMOKE_URL="${SMOKE_URL:-https://127.0.0.1:10443}" # база смоука (тестовый стенд: https://127.0.0.1:8443)
HEALTH_URL="${HEALTH_URL:-}"                      # direct health, пусто = через nginx (контейнеры держат 10443 внутри)
DRY_RUN="${DRY_RUN:-0}"

TARGET_LABEL="${RELEASE_TAG}"
STAMP="$(date +%F-%H%M)"
DB_BACKUP="${BACKUP_DIR}/wiki-pre-${TARGET_LABEL}-${STAMP}.db"
AVATARS_BACKUP="${BACKUP_DIR}/avatars-pre-${TARGET_LABEL}-${STAMP}.tar"

APP_IMAGE="${APP_IMAGE_BASE}:${RELEASE_TAG}"
FRONTEND_IMAGE="${FRONTEND_IMAGE_BASE}:${RELEASE_TAG}"

log()  { echo -e "\n\033[1;34m==> $*\033[0m"; }
ok()   { echo -e "\033[1;32m[OK]\033[0m $*"; }
fail() { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; exit 1; }
# run: печатает команду и НЕ выполняет (мутации в dry-run); runq — выполняет
# (только идемпотентные/чтение шаги: версия docker, факты смоука).
run()  { if [ "$DRY_RUN" = "1" ]; then echo "   [DRY-RUN] $*"; else "$@"; fi; }

# --- Валидация релизного тега (FR-72: latest ЗАПРЕЩЕН) -----------------------
case "${RELEASE_TAG}" in
  ""|latest| Latest|LATEST|:latest)
    fail "RELEASE_TAG не задан или равен 'latest' — тег latest ЗАПРЕЩЕН (FR-72, tasks 1.6). Задай релизную метку, например: RELEASE_TAG=p11-r1 bash $0" ;;
esac
case "${RELEASE_TAG}" in
  *[!A-Za-z0-9._-]*)
    fail "RELEASE_TAG='${RELEASE_TAG}' содержит недопустимые символы (разрешены A-Za-z0-9._-) — иначе docker отвергнет тег." ;;
esac

# --- 1/7 Предусловия ---------------------------------------------------------
log "1/7 Предусловия"
for tool in docker curl git python3 tar; do
  command -v "$tool" >/dev/null || fail "Нет утилиты: $tool"
done
docker compose version >/dev/null || fail "Нет compose plugin"
[ -d "${SRC_DIR}/.git" ] || fail "Нет клона с целевым коммитом: ${SRC_DIR}"
[ -f "${SRC_DIR}/services/app/Dockerfile" ] || fail "Нет services/app/Dockerfile в ${SRC_DIR}"
[ -f "${SRC_DIR}/services/frontend/Dockerfile" ] || fail "Нет services/frontend/Dockerfile в ${SRC_DIR}"
[ -f "${SRC_DIR}/${COMPOSE_FILE}" ] || fail "Нет compose-файла ${SRC_DIR}/${COMPOSE_FILE}"
if [ "${DRY_RUN}" != "1" ]; then
  # .env с SECRET_KEY обязателен только у продового compose (стенд — TEST_SECRET_KEY-дефолт)
  case "${COMPOSE_FILE}" in
    *compose.test.yaml*) : ;;
    *) [ -f "${COMPOSE_DIR}/.env" ] || fail "Нет ${COMPOSE_DIR}/.env с SECRET_KEY (RUNBOOK §7.1 п.3) — боевой up невозможен" ;;
  esac
fi

COMPOSE="docker compose -f ${COMPOSE_FILE} -p ${PROJECT}"
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

# --- 2/7 Бэкап (named volume, БЕЗ остановки; design §6) ----------------------
# Метод: docker exec в КОНТЕЙНЕР app — python-модуль sqlite3 .backup
# (sqlite3 CLI в python:3.12-slim ОТСУТСТВУЕТ). БД и аватары — из тома wiki-data.
log "2/7 Бэкап до деплоя (БД + аватары) → ${BACKUP_DIR}"
run mkdir -p "${BACKUP_DIR}"

APP_CID="$(${COMPOSE} ps -q app 2>/dev/null || true)"
if [ -z "${APP_CID}" ] && [ "${DRY_RUN}" != "1" ]; then
  fail "Контейнер app не найден (${COMPOSE} ps -q app пуст) — бэкап из контейнера невозможен. Подними стек: cd ${COMPOSE_DIR} && ${COMPOSE} up -d (первый up — по RUNBOOK §7.3), затем повтори деплой."
fi

if [ "${DRY_RUN}" = "1" ]; then
  echo "   [DRY-RUN] ${COMPOSE} exec -T app python -c 'import sqlite3; sqlite3.connect(\"${DB_PATH_IN_CONTAINER}\").backup(sqlite3.connect(\"/tmp/backup.db\"))'"
  echo "   [DRY-RUN] ${COMPOSE} cp app:/tmp/backup.db ${DB_BACKUP}  # вынос из контейнера (том ro от root недоступен напрямую)"
  echo "   [DRY-RUN] ${COMPOSE} exec -T app tar -cf - -C ${AVATARS_DIR_IN_CONTAINER} . > ${AVATARS_BACKUP}"
else
  # БД: консистентная копия .backup (WAL-safe) во временный файл КОНТЕЙНЕРА
  # (uid 10001 пишет только в /tmp), затем вынос compose cp — том снаружи
  # (/var/lib/docker/volumes) требует root, exec-метод работает от текущего юзера.
  ${COMPOSE} exec -T app python - <<'PYEOF' || fail "Бэкап БД не создан (sqlite3 .backup упал) — деплой прерван, БД не тронута."
import sqlite3
sqlite3.connect("/data/wiki.db").backup(sqlite3.connect("/tmp/.deploy-backup.db"))
PYEOF
  ${COMPOSE} cp app:/tmp/.deploy-backup.db "${DB_BACKUP}" || fail "Бэкап БД не вынесен из контейнера"
  ${COMPOSE} exec -T app rm -f /tmp/.deploy-backup.db
  [ -s "${DB_BACKUP}" ] || fail "Файл бэкапа БД пуст: ${DB_BACKUP}"
  ok "Бэкап БД: $(du -h "${DB_BACKUP}" | cut -f1) — ${DB_BACKUP}"

  # Аватары: tar каталога /data/avatars (тот же exec-метод, поток в файл хоста).
  # Каталог может отсутствовать (пустой том / первый деплой) — тогда пустой tar.
  if ! ${COMPOSE} exec -T app tar -cf - -C "${AVATARS_DIR_IN_CONTAINER}" . > "${AVATARS_BACKUP}" 2>/dev/null; then
    ${COMPOSE} exec -T app sh -c "mkdir -p ${AVATARS_DIR_IN_CONTAINER} && tar -cf - -C ${AVATARS_DIR_IN_CONTAINER} ." > "${AVATARS_BACKUP}" \
      || fail "Бэкап аватаров (tar) не создан — деплой прерван."
  fi
  ok "Бэкап аватаров: $(du -h "${AVATARS_BACKUP}" | cut -f1) — ${AVATARS_BACKUP}"
fi

# --- 3/7 Сборка образов с релизным тегом -------------------------------------
log "3/7 Сборка образов: ${APP_IMAGE}, ${FRONTEND_IMAGE} (latest запрещен, FR-72)"
run docker build -f "${SRC_DIR}/services/app/Dockerfile"      -t "${APP_IMAGE}"      "${SRC_DIR}"
run docker build -f "${SRC_DIR}/services/frontend/Dockerfile" -t "${FRONTEND_IMAGE}" "${SRC_DIR}"
ok "Образы собраны с релизным тегом (после сборки проверить: docker image ls | grep ekotov-wiki)"

# --- 4/7 One-shot миграция — СТРОГО до up (FR-70; tasks 2.1: активируется после репетиции) ---
if [ -n "${MIGRATE_MODULE}" ]; then
  log "4/7 One-shot миграция: ${COMPOSE} run --rm app python -m ${MIGRATE_MODULE} (до up)"
  if [ "${DRY_RUN}" = "1" ]; then
    echo "   [DRY-RUN] ${COMPOSE} run --rm --no-deps -e DB_PATH=${DB_PATH_IN_CONTAINER} -e SECRET_KEY=[REDACTED] app python -m ${MIGRATE_MODULE}"
  else
    ${COMPOSE} run --rm --no-deps -e DB_PATH="${DB_PATH_IN_CONTAINER}" -e SECRET_KEY="x" app \
      python -m "${MIGRATE_MODULE}" \
      || fail "Миграция ${MIGRATE_MODULE} не прошла — деплой прерван ДО up (старый контейнер продолжает работать). БД восстанови из ${DB_BACKUP}."
    ok "Миграция ${MIGRATE_MODULE} применена"
  fi
else
  log "4/7 Миграция: MIGRATE_MODULE не задан — шаг пропущен (миграционные релизы: MIGRATE_MODULE=app.migrate_rN)"
fi

# --- 5/7 Подъем нового стека --------------------------------------------------
log "5/7 Up нового стека (${APP_IMAGE} / ${FRONTEND_IMAGE})"
run env APP_IMAGE="${APP_IMAGE}" FRONTEND_IMAGE="${FRONTEND_IMAGE}" ${COMPOSE} up -d
if [ "${DRY_RUN}" != "1" ]; then
  # Ждем health (compose healthcheck app: interval 30s, start_period 15s).
  for i in $(seq 1 12); do
    ST="$(${COMPOSE} ps --format '{{.Service}} {{.Health}}' 2>/dev/null | awk '$1=="app"{print $2}')"
    [ "${ST}" = "healthy" ] && break
    sleep 5
  done
  [ "${ST:-}" = "healthy" ] || fail "app не стал healthy за 60s: ${COMPOSE} ps; логи: docker compose logs app"
  ok "Стек поднят: app healthy"
fi

# --- 6/7 Смоук (обязателен; RUNBOOK §7.5) ------------------------------------
log "6/7 Смоук: health + login + статика + avatars + stale-DNS (не 502)"
if [ "${DRY_RUN}" = "1" ]; then
  echo "   [DRY-RUN] curl -sk ${SMOKE_URL}/api/health            # {\"status\":\"ok\"}"
  echo "   [DRY-RUN] curl -sk -o /dev/null -w '%{http_code}' ${SMOKE_URL}/login                  # 200"
  echo "   [DRY-RUN] curl -sk -o /dev/null -w '%{http_code}' ${SMOKE_URL}/static/css/app.css     # 200"
  echo "   [DRY-RUN] curl -sk -o /dev/null -w '%{http_code}' ${SMOKE_URL}/avatars/               # 200/403/404 — НЕ 502"
  echo "   [DRY-RUN] ${COMPOSE} exec -T nginx sh -c 'wget -q --spider -T 5 http://app:8377/api/health'  # nginx→app жив (stale-DNS контроль, design §1)"
  echo "   [DRY-RUN] ${SRC_DIR}/scripts/smoke_static.py --repo ${SRC_DIR} --base ${SMOKE_URL} --insecure"
  echo -e "\n\033[1;33m[DRY-RUN] Ничего не изменено. Для боевого деплоя: sudo RELEASE_TAG=<метка> bash $0\033[0m"
  exit 0
fi

_code() { curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "$1" || true; }
H="$(_code "${SMOKE_URL}/api/health")"
[ "${H}" = "200" ] || fail "Health через nginx: ${H} (ожидался 200)"
ok "Health: 200"
P="$(_code "${SMOKE_URL}/login")"
[ "${P}" = "200" ] || fail "/login через nginx: ${P} (ожидался 200)"
ok "/login: 200"
S="$(_code "${SMOKE_URL}/static/css/app.css")"
[ "${S}" = "200" ] || fail "Статика через nginx: ${S} (ожидался 200 — статика из образа nginx)"
ok "/static/css/app.css: 200"
A="$(_code "${SMOKE_URL}/avatars/")"
case "${A}" in
  200|403|404) ok "/avatars/: ${A} (не 502)" ;;
  *) fail "/avatars/: ${A} (ожидалось 200/403/404)" ;;
esac

# stale-DNS контроль (design §1): после up НОВОГО образа app nginx не отдает 502.
# Прямой запрос nginx→app изНУТРИ nginx-контейнера — самый ранний детектор
# (app слушает HTTP 8377 — TLS терминирует только контейнерный nginx).
if ! ${COMPOSE} exec -T nginx sh -c 'wget -q --spider -T 5 http://app:8377/api/health'; then
  echo "   [WARN] nginx→app изнутри не ответил (возможен stale-DNS 502, design §1) — fallback: docker compose restart nginx"
  ${COMPOSE} restart nginx || fail "restart nginx не помог — смотри docker compose logs nginx"
  sleep 3
  ${COMPOSE} exec -T nginx sh -c 'wget -q --spider -T 5 http://app:8377/api/health' \
    || fail "После restart nginx проксирование app все еще сломано — дефект на resolver-конфиг (design §1)."
  ok "Проксирование восстановлено через restart nginx (fallback применен — заведи дефект на resolver-конфиг)"
else
  ok "nginx→app жив изнутри (stale-DNS не воспроизвелся — resolver+переменная работают)"
fi

NGINX_502="$(docker logs "$(${COMPOSE} ps -q nginx)" 2>&1 | grep -c ' 502 ' || true)"
if [ "${NGINX_502}" != "0" ]; then
  echo "   [WARN] в логах nginx ${NGINX_502}х 502 — проверь ${SMOKE_URL} браузером"
fi
ok "Логи nginx: 502 не обнаружено"

# 6b Полный смоук статики E10 — против контейнерного nginx (статика в образе)
if python3 "${SRC_DIR}/scripts/smoke_static.py" --repo "${SRC_DIR}" --base "${SMOKE_URL}" --insecure; then
  ok "Смоук статики (E10): все UI-ресурсы отдаются"
else
  fail "Смоук статики (E10): часть UI-ресурсов не отдается (класс DEF-002)"
fi

# --- 7/7 Гигиена dangling-образов (RUNBOOK §7.6, design §2) -------------------
log "7/7 docker image prune -f (dangling-слои после пересборки)"
run docker image prune -f

echo -e "\n\033[1;32m============================================"
echo "ДЕПЛОЙ ${TARGET_LABEL} ЗАВЕРШЕН УСПЕШНО (контейнерная схема)"
echo "============================================\033[0m"
echo "Коммит:        ${CURRENT}"
echo "Образы:        ${APP_IMAGE}, ${FRONTEND_IMAGE}"
echo "Бэкап БД:      ${DB_BACKUP}"
echo "Бэкап аватаров:${AVATARS_BACKUP}"
echo ""
echo "Ручной смоук в браузере: логин → доска; если релиз трогал статику —"
echo "static_v забамплен (кеш-бастинг). Откат: предыдущий RELEASE_TAG, при"
echo "несовместимой схеме — БД из ${DB_BACKUP} (RUNBOOK §7.6)."
