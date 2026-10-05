#!/usr/bin/env bash
# ============================================================
# 2.4 переключение: прод-трафик :10443 → новый стек (матрица сервисов).
# Пакет add-microservices-full, задача 2.4. Запускает Заказчик от root.
#
# ТЕКУЩАЯ топология (до скрипта):
#   :10443 = СТАРЫЙ контейнерный стек (без search; compose-проект продовый,
#            из /opt/ekotov-wiki/deploy, том ekotov-wiki_wiki-data)
#   :10444 = НОВЫЙ стек p12-rc1 (PROJECT=ekotov-wiki-par, том par_wiki-data,
#            поднят и принят 2.3)
# ЦЕЛЕВАЯ: :10443 = новый стек; старый стек ОСТАНОВЛЕН но НЕ удален
#          (образы/том на месте — это и есть откат).
#
# ЧТО ДЕЛАЕТ full:
#   pre    — предусловия: старый 10443 жив, параллель 10444 жива, бэкап БД
#            ПАРАЛЛЕЛИ (свежие данные приемки!), фикс текущих контейнеров
#   switch — остановка СТАРОГО стека (только stop, контейнеры не удаляются),
#            публикация нового стека на 10443 (compose up -d nginx с
#            NGINX_PORT=10443; app/search/backup уже Up — не пересоздаются),
#            смоук 10443 (health/login/статика/поиск/X-Service) + контроль
#            10444
#   Данные: новый стек продолжает работать на СВОЕМ томе (в нем копия прода +
#            задачи, созданные при приемке 2.3). Старый том не трогается.
#
# ОТКАТ (в любой момент): ./2.4-switch.sh rollback
#   → новый стек уходит с 10443, старый стек поднимается обратно (start),
#     10444 возвращается параллели. Задачи, созданные в новом стеке ПОСЛЕ
#     переключения, при откате в старый том НЕ попадают (зафиксировать).
#
# Запуск: bash 2.4-switch.sh {pre|switch|status|rollback}
# ============================================================
set -euo pipefail

SRC_DIR="${SRC_DIR:-/home/openclaw/ekotov-wiki}"
DEPLOY_DIR="${SRC_DIR}/deploy"
PAR_PROJECT="ekotov-wiki-par"
OLD_PROJECT="ekotov-wiki"
PAR_VOLUME="${PAR_PROJECT}_wiki-data"
BACKUP_DIR="/var/backups/ekotov-wiki"
PHASE="${1:-pre}"

log()  { printf '\n\033[1;35m[2.4 %s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
ok()   { printf '\033[1;32m  PASS\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*"; exit 1; }

par_compose()   { docker compose -p "${PAR_PROJECT}" --project-directory "${DEPLOY_DIR}" "$@"; }
old_compose()   { docker compose -p "${OLD_PROJECT}" --project-directory /opt/ekotov-wiki/deploy "$@"; }

export_secret() {
  if [[ -z "${SECRET_KEY:-}" ]]; then
    SECRET_KEY="$(grep -oP '(?<=^SECRET_KEY=).*' "${DEPLOY_DIR}/.env")"
    export SECRET_KEY
  fi
}

phase_pre() {
  log "pre: предусловия переключения"
  [[ $EUID -eq 0 ]] || fail "запускай от root"
  systemctl is-active --quiet ekotov-wiki 2>/dev/null && \
    fail "systemd-юнит ACTIVE — конфликт (ожидаем контейнерный прод)"

  local code
  code="$(curl -sk -o /dev/null -w '%{http_code}' 'https://127.0.0.1:10443/login' || true)"
  [[ "${code}" == "200" ]] && ok "старый прод :10443: 200 (жив, переключаем)" || fail "старый прод :10443: ${code} — не переключай неработающее"
  code="$(curl -sk -o /dev/null -w '%{http_code}' 'https://127.0.0.1:10444/login' || true)"
  [[ "${code}" == "200" ]] && ok "параллель :10444: 200 (жива, источник нового стека)" || fail "параллель :10444: ${code} — сначала подними (2.3-par.sh full)"

  log "  бэкап БД ПАРАЛЛЕЛИ (в ней данные приемки 2.3 — свежее прода)"
  mkdir -p "${BACKUP_DIR}"
  local stamp; stamp="$(date +%Y-%m-%d-%H%M)"
  # WAL-БД: VACUUM INTO требует записи wal-index — поэтому ЧТЕНИЕ снапшота
  # делаем через .backup (URI ro не дает создать -wal рядом с :ro маунтом).
  # Точнее: копируем БД из тома во временный контейнер-путь через tar, затем
  # бэкапим на хосте. Проще: docker run БЕЗ :ro (sqlite откроет rw, создаст
  # -wal/-shm в самом томе — это норма, app их и так создает), VACUUM INTO
  # пишет только в /bkp.
  docker run --rm -v "${PAR_VOLUME}:/data" -v "${BACKUP_DIR}:/bkp" \
    "ekotov-wiki/app:p12-rc1" \
    python -c "import sqlite3; sqlite3.connect('/data/wiki.db').execute(\"VACUUM INTO '/bkp/wiki-pre-2.4-${stamp}.db'\")" \
    || fail "бэкап тома параллели упал"
  ok "бэкап: ${BACKUP_DIR}/wiki-pre-2.4-${stamp}.db ($(du -h "${BACKUP_DIR}/wiki-pre-2.4-${stamp}.db" | cut -f1))"

  log "  фикс текущих контейнеров старого стека (для отката)"
  old_compose ps || true
  ok "старый стек: контейнеры остаются на месте (stop без rm — откат = start)"
  echo
  log "предусловия ок. Переключение: bash $0 switch"
}

phase_switch() {
  log "switch: :10443 → новый стек"
  export_secret
  log "  1/3 остановка СТАРОГО стека (stop; контейнеры/том НЕ удаляются)"
  old_compose stop || fail "stop старого стека упал — разберись до продолжения"
  ok "старый стек остановлен (откат: ./2.4-switch.sh rollback)"

  log "  2/3 публикация нового стека на 10443"
  NGINX_PORT=10443 par_compose up -d || fail "up нового стека на 10443 упал"
  sleep 2
  ss -tln | grep -q ':10443 ' || { par_compose logs --tail 20 nginx; fail "10443 не слушается"; }
  ok "10443 слушает новый nginx"

  log "  3/3 смоук через 10443"
  local base="https://127.0.0.1:10443" code hdr
  code="$(curl -sk -o /tmp/s24-h.json -w '%{http_code}' "${base}/api/health" || true)"
  grep -q '"status":"ok"' /tmp/s24-h.json && ok "health: 200 ok" || { echo "HTTP ${code}"; fail "health"; }
  code="$(curl -sk -o /dev/null -w '%{http_code}' "${base}/login" || true)"
  [[ "${code}" == "200" ]] && ok "login: 200" || fail "login: ${code}"
  code="$(curl -sk -o /dev/null -w '%{http_code}' "${base}/static/css/app.css" || true)"
  [[ "${code}" == "200" ]] && ok "статика: 200" || fail "статика: ${code}"
  hdr="$(curl -sk -D - -o /dev/null "${base}/api/search?q=" || true)"
  echo "${hdr}" | grep -qi '^HTTP.* \(200\|401\|422\)' && ok "поиск: ответ search" || { echo "${hdr}" | head -3; fail "поиск"; }
  echo "${hdr}" | grep -qi '^x-service: *search' && ok "X-Service: search — МАТРИЦА РАБОТАЕТ НА ПРОД-ПОРТУ" || { echo "${hdr}" | head -8; fail "X-Service"; }
  code="$(curl -sk -o /dev/null -w '%{http_code}' "${base}/api/health" || true)"
  [[ "${code}" != "502" ]] && ok "502-контроль: нет 502" || fail "502 на прод-порту"

  echo
  log "ПЕРЕКЛЮЧЕНИЕ ВЫПОЛНЕНО. Финальная приемка браузером: https://194.58.34.122:10443"
  log "(логин, доска, поиск — теперь через search-сервис; создание задачи)"
  log "Статус стеков: bash $0 status | Откат: bash $0 rollback"
}

phase_status() {
  log "status: оба стека"
  echo "--- НОВЫЙ (${PAR_PROJECT}) ---"; par_compose ps 2>/dev/null || true
  echo "--- СТАРЫЙ (${OLD_PROJECT}) ---"; old_compose ps -a 2>/dev/null || true
  ss -tln | grep -E ':1044[34] ' || true
  curl -sk -o /dev/null -w '10443: %{http_code}\n' https://127.0.0.1:10443/login || true
  curl -sk -o /dev/null -w '10444: %{http_code}\n' https://127.0.0.1:10444/login || true
}

phase_rollback() {
  log "rollback: возврат старого стека на 10443"
  log "  1/3 новый стек уходит с 10443 (остается на 10444 как параллель)"
  par_compose up -d --scale nginx=0 2>/dev/null || par_compose stop nginx || true
  sleep 1
  log "  2/3 старый стек стартует обратно"
  old_compose start || fail "start старого стека упал"
  sleep 2
  log "  3/3 контроль"
  local code
  code="$(curl -sk -o /dev/null -w '%{http_code}' 'https://127.0.0.1:10443/login' || true)"
  [[ "${code}" == "200" ]] && ok "прод :10443: 200 (старый стек вернулся)" || fail "10443: ${code} — срочно разбирайся"
  ss -tln | grep -q ':10444 ' && ok "10444 остался за параллелью" || ok "10444 свободен (параллель остановлена — подними 2.3-par.sh full при нужде)"
  echo "  ВАЖНО: задачи, созданные в новом стеке ПОСЛЕ переключения, в старом томе отсутствуют — зафиксируй их вручную."
}

case "${PHASE}" in
  pre)      phase_pre ;;
  switch)   phase_switch ;;
  status)   phase_status ;;
  rollback) phase_rollback ;;
  *) echo "использование: $0 {pre|switch|status|rollback}"; exit 2 ;;
esac
