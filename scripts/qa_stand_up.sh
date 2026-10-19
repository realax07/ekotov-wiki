#!/usr/bin/env bash
# ============================================================================
# scripts/qa_stand_up.sh — канонический стенд QA-регресса (P16, в репо).
#
# Поднимает канонический контур (см. tests/README.md): nginx → ядро app +
# search + images + video + weather (uvicorn, venv wiki), паритет прод-топологии
# services/frontend/nginx. Логи/pid/тома — $STAND_DIR. Полный env прогона
# (EKOTOV_WIKI_BASE_URL/DB_PATH/AVATARS_DIR/IMAGES_DIR) — tests/README.md.
#
# ПРЕДЫСТОРИЯ: стенд жил вне репо в /tmp/vh9-stand (reset.sh/launch.sh/
# nginx.conf); этот скрипт — его канонизированная версия с параметризацией
# портов/путей. Название vh9 — артефакт истории, не смысл.
#
# Использование:
#   bash scripts/qa_stand_up.sh            # reset + up + health (полный цикл)
#   bash scripts/qa_stand_up.sh reset      # стоп + чистая БД/тома + схема/seed + up + health
#   bash scripts/qa_stand_up.sh up         # рендер nginx-конфа + старт сервисов (БД не трогает)
#   bash scripts/qa_stand_up.sh health     # только проверка здоровья контура
#   bash scripts/qa_stand_up.sh stop       # стоп всех сервисов стенда
#
# Параметры (env, значения по умолчанию):
#   REPO=/home/openclaw/ekotov-wiki     корень клона
#   PY=/home/openclaw/venvs/wiki/bin/python  интерпретатор venv wiki
#   STAND_DIR=/tmp/qa-stand             каталог стенда (логи/pid/тома/nginx-конф)
#   APP_PORT=8080 SEARCH_PORT=8378 IMAGES_PORT=8379 VIDEO_PORT=8380
#   WEATHER_PORT=8381 NGINX_PORT=18443  порты контура (занятые → взять соседние)
#   FFMPEG_DIR=/home/openclaw/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin
#   SECRET_KEY=qa-stand-test-secret-key
#   QA_STAND_CONF=deploy/qa-stand-nginx.conf   шаблон (относительно REPO)
#
# Второй контур параллельно с чужим (порт 18443 занят другим стендом) — не
# воевать за порт, поднять свой: STAND_DIR=/tmp/qa-stand2 NGINX_PORT=18445
# APP_PORT=18080 ... bash scripts/qa_stand_up.sh
# ============================================================================
set -euo pipefail

REPO="${REPO:-/home/openclaw/ekotov-wiki}"
PY="${PY:-/home/openclaw/venvs/wiki/bin/python}"
STAND_DIR="${STAND_DIR:-/tmp/qa-stand}"
APP_PORT="${APP_PORT:-8080}"
SEARCH_PORT="${SEARCH_PORT:-8378}"
IMAGES_PORT="${IMAGES_PORT:-8379}"
VIDEO_PORT="${VIDEO_PORT:-8380}"
WEATHER_PORT="${WEATHER_PORT:-8381}"
NGINX_PORT="${NGINX_PORT:-18443}"
FFMPEG_DIR="${FFMPEG_DIR:-/home/openclaw/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin}"
SECRET_KEY="${SECRET_KEY:-qa-stand-test-secret-key}"
QA_STAND_CONF="${QA_STAND_CONF:-deploy/qa-stand-nginx.conf}"

log()  { echo -e "\n\033[1;34m==> $*\033[0m"; }
ok()   { echo -e "\033[1;32m[OK]\033[0m $*"; }
fail() { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; exit 1; }

port_busy() { ss -tln 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${1}$"; }

# --- сервисы стенда: имя:порт:pid-файл (единый список для stop/health) ------
services_spec() {
  cat <<EOF
app ${APP_PORT}
search ${SEARCH_PORT}
images ${IMAGES_PORT}
video ${VIDEO_PORT}
weather ${WEATHER_PORT}
EOF
}

stop_all() {
  local f p want
  # m4 (review-001): pid-файл удаляем ПОСЛЕ kill (иначе stale-файл переживает
  # stop и повторный stop/up стреляет kill по переиспользованному pid); kill
  # только СВОЕМУ процессу — /proc/$p/cmdline сверяем с ожидаемым портом
  # (uvicorn) / nginx-конфом (nginx).
  for f in app search images video weather; do
    [ -f "${STAND_DIR}/${f}.pid" ] || continue
    p="$(cat "${STAND_DIR}/${f}.pid" 2>/dev/null || true)"
    want="$(services_spec | awk -v n="${f}" '$1==n{print $2}')"
    if [ -n "${p}" ] && tr '\0' ' ' < "/proc/${p}/cmdline" 2>/dev/null | grep -q -- "--port ${want}"; then
      kill "${p}" 2>/dev/null || true
    fi
    rm -f "${STAND_DIR}/${f}.pid"
  done
  if [ -f "${STAND_DIR}/nginx.pid" ]; then
    p="$(cat "${STAND_DIR}/nginx.pid" 2>/dev/null || true)"
    if [ -n "${p}" ] && tr '\0' ' ' < "/proc/${p}/cmdline" 2>/dev/null | grep -q "nginx.*${STAND_DIR}/nginx.conf"; then
      kill "${p}" 2>/dev/null || true
    fi
    rm -f "${STAND_DIR}/nginx.pid"
  fi
  sleep 2
  # Добить осиротевшие процессы портов контура (анкер $: cmdline кончается
  # портом; без анкера паттерн с хвостовым пробелом не матчит uvicorn).
  pkill -f "uvicorn app.main:app --host 127.0.0.1 --port ${APP_PORT}$" 2>/dev/null || true
  pkill -f "uvicorn app.main:app --host 127.0.0.1 --port ${SEARCH_PORT}$" 2>/dev/null || true
  pkill -f "uvicorn app.main:app --host 127.0.0.1 --port ${IMAGES_PORT}$" 2>/dev/null || true
  pkill -f "uvicorn app.main:app --host 127.0.0.1 --port ${VIDEO_PORT}$" 2>/dev/null || true
  pkill -f "uvicorn app.main:app --host 127.0.0.1 --port ${WEATHER_PORT}$" 2>/dev/null || true
  ok "Стенд ${STAND_DIR} остановлен"
}

render_nginx_conf() {
  [ -f "${REPO}/${QA_STAND_CONF}" ] || fail "Нет шаблона ${REPO}/${QA_STAND_CONF}"
  command -v nginx >/dev/null || fail "Нет nginx в PATH"
  # m5 (review-001): & и | в значении экранируем — sed-делемитер | не должен
  # порезать/сломать подстановку путей REPO/STAND_DIR с спецсимволами.
  sed_escape() { printf '%s' "${1}" | sed -e 's/[&|\\]/\\&/g'; }
  sed -e "s|@APP_PORT@|${APP_PORT}|g" \
      -e "s|@SEARCH_PORT@|${SEARCH_PORT}|g" \
      -e "s|@IMAGES_PORT@|${IMAGES_PORT}|g" \
      -e "s|@VIDEO_PORT@|${VIDEO_PORT}|g" \
      -e "s|@WEATHER_PORT@|${WEATHER_PORT}|g" \
      -e "s|@NGINX_PORT@|${NGINX_PORT}|g" \
      -e "s|@STAND_DIR@|$(sed_escape "${STAND_DIR}")|g" \
      -e "s|@REPO@|$(sed_escape "${REPO}")|g" \
      "${REPO}/${QA_STAND_CONF}" > "${STAND_DIR}/nginx.conf"
  nginx -t -c "${STAND_DIR}/nginx.conf" >/dev/null 2>&1 || {
    nginx -t -c "${STAND_DIR}/nginx.conf"; fail "Рендер nginx-конфа не прошел nginx -t"; }
  ok "nginx-конф отрендерен: ${STAND_DIR}/nginx.conf (:${NGINX_PORT})"
}

start_service() { # $1=имя $2=порт $3=catalog(from REPO) $4...=env VAR=VAL
  local name="$1" port="$2" dir="$3"; shift 3
  #Pid-файл пишет САМ процесс (bash -c: $$ -> exec): $! обертки ловит pid
  # env/setsid, а setsid может форкнуться — тогда убитый по pid-файлу wrapper
  # оставляет живого сироту на порту (ловится только живым прогоном).
  ( cd "${REPO}/${dir}" && \
    env "$@" setsid bash -c "echo \$\$ > '${STAND_DIR}/${name}.pid'; exec '${PY}' -m uvicorn app.main:app --host 127.0.0.1 --port '${port}'" \
      > "${STAND_DIR}/${name}.log" 2>&1 < /dev/null & )
}

start_all() {
  local p
  # Занятость портов: чужой (даже с мертвыми бэкендами) — не перебивать.
  for p in "${APP_PORT}" "${SEARCH_PORT}" "${IMAGES_PORT}" "${VIDEO_PORT}" "${WEATHER_PORT}" "${NGINX_PORT}"; do
    if port_busy "${p}"; then
      fail "Порт ${p} занят — не воевать за порт: подними контур на соседних (APP_PORT/.../NGINX_PORT) или погаси чужой стенд"
    fi
  done
  render_nginx_conf

  start_service app    "${APP_PORT}"     backend \
    "DB_PATH=${STAND_DIR}/app.db" "SECRET_KEY=${SECRET_KEY}" \
    "AVATARS_DIR=${STAND_DIR}/avatars" "EKOTOV_WIKI_DB_PATH=${STAND_DIR}/app.db"
  start_service search "${SEARCH_PORT}"  services/search \
    "EKOTOV_WIKI_DB_PATH=${STAND_DIR}/app.db"
  start_service images "${IMAGES_PORT}"  services/images \
    "EKOTOV_WIKI_DB_PATH=${STAND_DIR}/app.db" "EKOTOV_WIKI_IMAGES_DIR=${STAND_DIR}/images-data"
  start_service video  "${VIDEO_PORT}"   services/video \
    "EKOTOV_WIKI_DB_PATH=${STAND_DIR}/app.db" "EKOTOV_WIKI_VIDEOS_DIR=${STAND_DIR}/videos-data" \
    "PATH=${FFMPEG_DIR}:${PATH}"
  start_service weather "${WEATHER_PORT}" services/weather \
    "EKOTOV_WIKI_DB_PATH=${STAND_DIR}/app.db" "EKOTOV_WEATHER_CACHE_PATH=${STAND_DIR}/weather-cache/weather.json"

  nginx -c "${STAND_DIR}/nginx.conf"
  ok "Сервисы и nginx запущены (pid-файлы в ${STAND_DIR})"
}

wait_health() { # $1=url $2=секунды-бюджет
  local i code
  for i in $(seq 1 "${2:-15}"); do
    # M1 (review-001): -f + сверка кода 200 — ЛЮБОЙ HTTP-ответ здоровьем не
    # считается (чужой/стейл nginx с мертвыми бэкендами отвечает 502 — это FAIL).
    code="$(curl -sf -m 3 -o /dev/null -w '%{http_code}' "${1}" 2>/dev/null || true)"
    [ "${code}" = "200" ] && return 0
    sleep 1
  done
  return 1
}

health_all() {
  local rc=0 name port url
  while read -r name port; do
    url="http://127.0.0.1:${port}/api/health"
    if wait_health "${url}" 15; then ok "${name}: ${url} — жив"; else echo "[FAIL] ${name}: ${url}"; rc=1; fi
  done < <(services_spec)
  if wait_health "http://127.0.0.1:${NGINX_PORT}/api/health" 15; then
    ok "nginx: http://127.0.0.1:${NGINX_PORT}/api/health — жив"
  else
    echo "[FAIL] nginx: http://127.0.0.1:${NGINX_PORT}/api/health"; rc=1
  fi
  return "${rc}"
}

reset_all() {
  [ -x "${PY}" ] || fail "Нет интерпретатора ${PY} (venv wiki)"
  mkdir -p "${STAND_DIR}"/{avatars,images-data,videos-data,weather-cache}
  stop_all
  rm -f "${STAND_DIR}/app.db"
  rm -rf "${STAND_DIR}/avatars" "${STAND_DIR}/images-data" "${STAND_DIR}/videos-data" "${STAND_DIR}/weather-cache"
  mkdir -p "${STAND_DIR}"/{avatars,images-data,videos-data,weather-cache}

  log "Схема + миграции + seed (${STAND_DIR}/app.db)"
  ( cd "${REPO}/backend" && \
    DB_PATH="${STAND_DIR}/app.db" SECRET_KEY="${SECRET_KEY}" "${PY}" -m app.db && \
    DB_PATH="${STAND_DIR}/app.db" SECRET_KEY="${SECRET_KEY}" "${PY}" -m app.migrate_categories && \
    DB_PATH="${STAND_DIR}/app.db" SECRET_KEY="${SECRET_KEY}" "${PY}" -m app.migrate_gallery && \
    DB_PATH="${STAND_DIR}/app.db" SECRET_KEY="${SECRET_KEY}" "${PY}" -m app.migrate_wiki && \
    DB_PATH="${STAND_DIR}/app.db" SECRET_KEY="${SECRET_KEY}" "${PY}" -m app.migrate_video && \
    DB_PATH="${STAND_DIR}/app.db" SECRET_KEY="${SECRET_KEY}" "${PY}" -c "
from app.seed_users import seed_user
print(seed_user('owner', 'Product manager', 'QaOwner_Pass_1!'))
print(seed_user('wife', 'Product engineer', 'QaWife_Pass_2!'))
" && \
    DB_PATH="${STAND_DIR}/app.db" SECRET_KEY="${SECRET_KEY}" "${PY}" -m app.migrate_r4 && \
    DB_PATH="${STAND_DIR}/app.db" STAND_DIR="${STAND_DIR}" "${PY}" -c "
import os, sqlite3
conn = sqlite3.connect(os.path.join(os.environ['STAND_DIR'], 'app.db'))
conn.executemany('INSERT INTO image_categories (name) VALUES (?)', [('Дом',), ('Работа',), ('Личное',)])
conn.commit(); conn.close()
print('categories seeded')
" ) || fail "Схема/seed стенда не поднялись — смотри вывод выше"

  log "Старт контура"
  start_all
  sleep 2
  health_all || fail "Контур неполон — смотри ${STAND_DIR}/*.log"
  echo
  echo "Прогон тестов (env по tests/README.md):"
  echo "  export EKOTOV_WIKI_BASE_URL=http://127.0.0.1:${NGINX_PORT}"
  echo "  export EKOTOV_WIKI_DB_PATH=${STAND_DIR}/app.db"
  echo "  export EKOTOV_WIKI_AVATARS_DIR=${STAND_DIR}/avatars"
  echo "  export EKOTOV_WIKI_IMAGES_DIR=${STAND_DIR}/images-data"
}

case "${1:-reset}" in
  reset)  reset_all ;;
  up)     mkdir -p "${STAND_DIR}"; start_all; sleep 2; health_all || fail "Контур неполон — смотри ${STAND_DIR}/*.log" ;;
  health) health_all ;;
  stop)   stop_all ;;
  *) echo "usage: $0 [reset|up|health|stop]" >&2; exit 2 ;;
esac
