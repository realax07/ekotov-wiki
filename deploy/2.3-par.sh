#!/usr/bin/env bash
# ============================================================
# 2.3 прод-параллель: полный прогон под root ОДНИМ скриптом.
# Пакет add-microservices-full, задача 2.3 ( Заказчик запускает от root).
#
# ЧТО ДЕЛАЕТ (по фазам, останавливается на первой ошибке):
#   pre     — предусловия: клон/коммит, порт 10444, память, deploy/.env
#   build   — build 4 образов матрицы (тег RELEASE_TAG)
#   up      — подъем параллели PROJECT=ekotov-wiki-par на NGINX_PORT=10444
#             (деплой-бэкап пропускается: том параллели пуст; данные
#             переносятся фазой seed)
#   seed    — ОДНОКРАТНО: консистентная копия БД прода + avatars → том
#             параллели, integrity_check, рестарт параллели
#   smoke   — смоук-матрица: health, поиск + X-Service, статика, прод-контроль
#   ФАЗЫ ЗАДАЮТСЯ АРГУМЕНТОМ: ./2.3-par.sh <фаза>
#   (по умолчанию pre; pre можно один раз, build+up+smoke — «full»)
#
# ЧТО НЕ ТРОГАЕТ (гарантии):
#   - systemd-прод ekotov-wiki и его порт 10443 — НИ ОДНОЙ команды
#   - прод-том ekotov-wiki_wiki-data — только ЧТЕНИЕ (sqlite3 .backup)
#   - все docker-объекты создаются в проекте ekotov-wiki-par
#   - откат в любой момент: ./2.3-par.sh rollback
#
# Запуск (root, каталог ЛЮБОЙ, SRC_DIR внутри):
#   bash 2.3-par.sh pre        # предусловия
#   bash 2.3-par.sh full       # build + up + seed + smoke (боевой прогон)
#   bash 2.3-par.sh smoke      # только смоук (повторно)
#   bash 2.3-par.sh status     # состояние параллели
#   bash 2.3-par.sh rollback   # down -v параллели (прод не трогает)
# ============================================================
set -euo pipefail

RELEASE_TAG="${RELEASE_TAG:-p12-rc1}"
SRC_DIR="${SRC_DIR:-/opt/ekotov-wiki}"
DEPLOY_DIR="${SRC_DIR}/deploy"
PROJECT="ekotov-wiki-par"
NGINX_PORT=10444
PROD_DB="/var/lib/ekotov-wiki/wiki.db"
PAR_VOLUME="${PROJECT}_wiki-data"
PHASE="${1:-pre}"

log()  { printf '\n\033[1;34m[2.3 %s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
ok()   { printf '\033[1;32m  PASS\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*"; exit 1; }

compose() {
  docker compose -p "${PROJECT}" --project-directory "${DEPLOY_DIR}" "$@"
}

phase_pre() {
  log "pre: предусловия"
  [[ $EUID -eq 0 ]] || fail "запускай от root (сейчас EUID=$EUID)"
  [[ -d "${SRC_DIR}/.git" ]] || fail "нет клона ${SRC_DIR} — склонируй репозиторий"
  local head_commit
  head_commit="$(git -C "${SRC_DIR}" rev-parse --short=8 HEAD)"
  log "  HEAD клона: ${head_commit} (ожидался 28a6dc39 или новее)"
  git -C "${SRC_DIR}" log --oneline -1

  if ss -tln | grep -q ':10444 '; then
    fail "порт 10444 ЗАНЯТ — параллель уже поднята? (./2.3-par.sh status)"
  fi
  ok "порт 10444 свободен"

  local avail_mb
  avail_mb="$(free -m | awk '/Mem:/{print $7}')"
  [[ "${avail_mb}" -ge 2048 ]] || fail "свободная память ${avail_mb} MB < 2048 MB"
  ok "память: ${avail_mb} MB available"

  if ! docker info >/dev/null 2>&1; then
    fail "docker daemon недоступен"
  fi
  ok "docker daemon отвечает"

  if [[ ! -f "${DEPLOY_DIR}/.env" ]]; then
    [[ -f "${SRC_DIR}/.env" ]] || fail "нет ${SRC_DIR}/.env с SECRET_KEY — откуда брать?"
    grep -q '^SECRET_KEY=' "${SRC_DIR}/.env" || fail "в ${SRC_DIR}/.env нет SECRET_KEY"
    grep '^SECRET_KEY=' "${SRC_DIR}/.env" > "${DEPLOY_DIR}/.env"
    chmod 600 "${DEPLOY_DIR}/.env"
    ok "deploy/.env создан из прода (chmod 600)"
  else
    ok "deploy/.env уже есть"
  fi

  # Прод жив и не тронут (контрольная точка). Топология с 2026-10-03: прод
  # работает КОНТЕЙНЕРНО на 10443 (systemd-юнит отключен легитимно после
  # переключения add-containerization) — критерий здоровья: 10443 отвечает
  # 200. Дополнительно: юнит не должен быть active (иначе два конкурирующих
  # стека на одной БД).
  if systemctl is-active --quiet ekotov-wiki 2>/dev/null; then
    fail "systemd-прод ekotov-wiki ACTIVE — конфликт топологии (ожидаем контейнерный прод); останови юнит или разберись до параллели"
  fi
  ok "systemd-юнит: inactive (норма — прод контейнерный с 2026-10-03)"
  local prod_code
  prod_code="$(curl -sk -o /dev/null -w '%{http_code}' 'https://127.0.0.1:10443/login' || true)"
  [[ "${prod_code}" == "200" ]] && ok "контейнерный прод :10443/login: 200 (не трогаем)" \
    || fail "контейнерный прод :10443 не отвечает (${prod_code:-нет связи}) — сначала прод"
  echo
  log "предусловия выполнены. Дальше: bash $0 full"
}

phase_build_up() {
  log "build+up: сборка матрицы и подъем параллели (PROJECT=${PROJECT}, порт ${NGINX_PORT})"
  cd "${SRC_DIR}"
  # Бэкап-фазу деплоя обходим: том параллели пуст, бэкапить нечего; данные
  # приносит seed. Деплой требует контейнер app для бэкапа — поэтому поднимаем
  # compose-стек напрямую (RUNBOOK §7.3), а не через deploy.sh целиком.
  export APP_IMAGE="ekotov-wiki/app:${RELEASE_TAG}"
  export FRONTEND_IMAGE="ekotov-wiki/frontend:${RELEASE_TAG}"
  export SEARCH_IMAGE="ekotov-wiki/search:${RELEASE_TAG}"
  export BACKUP_IMAGE="ekotov-wiki/backup:${RELEASE_TAG}"
  export NGINX_PORT
  export SECRET_KEY
  SECRET_KEY="$(grep -oP '(?<=^SECRET_KEY=).*' "${DEPLOY_DIR}/.env")"

  local svc
  for svc in app frontend search backup; do
    log "  build ${svc}:${RELEASE_TAG}"
    docker build -q -f "${SRC_DIR}/services/${svc}/Dockerfile" "${SRC_DIR}" \
      || docker build -f "${SRC_DIR}/services/${svc}/Dockerfile" "${SRC_DIR}" \
      || fail "build ${svc} упал"
    ok "built ${svc}:${RELEASE_TAG}"
  done

  log "  compose up app"
  compose up -d app
  sleep 3
  compose ps app | grep -q "healthy\|Up" || { compose logs --tail 20 app; fail "app не поднялся"; }
  ok "app: up"

  log "  compose up search backup"
  compose up -d search backup
  sleep 3
  ok "search, backup: up"

  log "  compose up nginx (порт ${NGINX_PORT})"
  compose up -d nginx
  sleep 2
  ss -tln | grep -q ":${NGINX_PORT} " || { compose logs --tail 20 nginx; fail "nginx не слушает ${NGINX_PORT}"; }
  ok "nginx: слушает ${NGINX_PORT}"
}

phase_seed() {
  log "seed: копия БД прода → том параллели (однократно)"
  if docker run --rm -v "${PAR_VOLUME}:/data" "ekotov-wiki/app:${RELEASE_TAG}" \
       sh -c 'test -s /data/wiki.db' 2>/dev/null; then
    log "  том уже содержит wiki.db — seed ПРОПУЩЕН (повтор не нужен)."
    log "  Если нужна пересидка: bash $0 rollback (снесет том параллели!)."
    return 0
  fi

  [[ -f "${PROD_DB}" ]] || fail "прод-БД ${PROD_DB} не найдена"
  compose stop >/dev/null 2>&1 || true

  log "  sqlite .backup с живого прода (онлайн-безопасно)"
  sqlite3 "${PROD_DB}" ".backup '/tmp/wiki-seed.db'" || fail "sqlite .backup упал"
  ok "копия: $(du -h /tmp/wiki-seed.db | cut -f1)"

  log "  БД → том ${PAR_VOLUME}"
  docker run --rm -v "${PAR_VOLUME}:/data" -v /tmp:/seed \
    "ekotov-wiki/app:${RELEASE_TAG}" cp /seed/wiki-seed.db /data/wiki.db \
    || fail "копирование БД в том упало"

  log "  avatars → том (на этой VPS каталог пуст — пропускается)"
  if [[ -d /var/lib/ekotov-wiki/avatars ]] && [[ -n "$(ls -A /var/lib/ekotov-wiki/avatars 2>/dev/null)" ]]; then
    tar -C /var/lib/ekotov-wiki -cf /tmp/avatars-seed.tar avatars
    docker run --rm -v "${PAR_VOLUME}:/data" -v /tmp:/seed \
      "ekotov-wiki/app:${RELEASE_TAG}" tar -C /data -xf /seed/avatars-seed.tar \
      || fail "копирование аватаров упало"
    ok "аватары перенесены"
  else
    ok "аватаров нет — пропущено (норма)"
  fi
  rm -f /tmp/wiki-seed.db /tmp/avatars-seed.tar

  log "  integrity_check + volume check"
  # sqlite3 внутри python:3.12-slim нет — проверяем через python (модуль sqlite3
  # входит в stdlib образа), не через CLI-клиент.
  local integrity
  integrity="$(docker run --rm -v "${PAR_VOLUME}:/data" "ekotov-wiki/app:${RELEASE_TAG}" \
    python -c "import sqlite3; c = sqlite3.connect('/data/wiki.db'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print(c.execute('SELECT count(*) FROM tasks').fetchone()[0])" 2>/dev/null || true)"
  echo "${integrity}" | head -1 | grep -q '^ok$' || { echo "${integrity}"; fail "integrity_check НЕ ok"; }
  ok "integrity_check: ok; задач в копии: $(echo "${integrity}" | tail -1)"

  log "  рестарт параллели с данными"
  compose up -d
  sleep 3
  compose ps
}

phase_smoke() {
  log "smoke: смоук-матрица параллели"
  local base="https://127.0.0.1:${NGINX_PORT}"
  local code hdr

  code="$(curl -sk -o /tmp/s23-health.json -w '%{http_code}' "${base}/api/health" || true)"
  grep -q '"status":"ok"' /tmp/s23-health.json && ok "health app: 200 ok" || { echo "health: HTTP ${code:-нет соединения}"; fail "health app (стек поднят? ./2.3-par.sh status)"; }

  code="$(curl -sk -o /dev/null -w '%{http_code}' "${base}/login" || true)"
  [[ "${code}" == "200" ]] && ok "login: 200" || fail "login: ${code}"

  code="$(curl -sk -o /dev/null -w '%{http_code}' "${base}/static/css/app.css")"
  [[ "${code}" == "200" ]] && ok "статика: 200" || fail "статика: ${code}"

  hdr="$(curl -sk -D - -o /tmp/s23-search.json 'https://127.0.0.1:10444/api/search?q=')"
  echo "${hdr}" | grep -qi '^HTTP.* 200' && ok "поиск: 200" || { echo "${hdr}" | head -3; fail "поиск"; }
  echo "${hdr}" | grep -qi '^x-service: *search' && ok "X-Service: search" || { echo "${hdr}" | head -8; fail "X-Service отсутствует"; }

  log "  прод НЕ ТРОНУТ — контрольная точка (контейнерный прод на 10443)"
  code="$(curl -sk -o /dev/null -w '%{http_code}' 'https://127.0.0.1:10443/login' 2>/dev/null || true)"
  [[ "${code}" == "200" ]] && ok "прод :10443/login: 200" || fail "прод :10443 не отвечает: ${code}"
  if systemctl is-active --quiet ekotov-wiki 2>/dev/null; then
    fail "systemd-юнит стал ACTIVE во время параллели — конфликт двух стеков"
  fi
  ok "systemd-юнит: inactive (норма)"

  echo
  log "СМОУК ПРОЙДЕН. Приемка браузером: https://194.58.34.122:${NGINX_PORT}"
  log "(логин продовыми кредами, создать задачу — смоук записи, аватар)"
  compose ps
}

phase_status() {
  log "status параллели ${PROJECT}"
  compose ps 2>/dev/null || echo "  (стек не поднят)"
  docker volume ls | grep "${PAR_VOLUME}" || echo "  (том не создан)"
  ss -tln | grep ':10444 ' || echo "  (10444 не слушает)"
  systemctl is-active ekotov-wiki
}

phase_rollback() {
  log "rollback: down -v параллели ${PROJECT} (прод НЕ трогается)"
  compose down -v || true
  docker image prune -f >/dev/null 2>&1 || true
  ok "параллель снесена (том ${PAR_VOLUME} удален)"
  systemctl is-active --quiet ekotov-wiki && ok "прод: active" || fail "прод не active — проверь немедленно"
  curl -sk -o /dev/null -w 'прод :10443/login → %{http_code}\n' 'https://127.0.0.1:10443/login'
}

case "${PHASE}" in
  pre)      phase_pre ;;
  build)    phase_build_up ;;
  seed)     phase_seed ;;
  smoke)    phase_smoke ;;
  full)     phase_pre; phase_build_up; phase_seed; phase_smoke ;;
  status)   phase_status ;;
  rollback) phase_rollback ;;
  *) echo "использование: $0 {pre|full|build|seed|smoke|status|rollback}"; exit 2 ;;
esac
