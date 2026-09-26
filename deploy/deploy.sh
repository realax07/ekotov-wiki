#!/usr/bin/env bash
# ============================================================
# ekotov-wiki — канонический деплой (E9), замена ~/deploy-r2.sh.
# Runbook: deploy/RUNBOOK.md (того же каталога).
#
# Источник кода: локальный клон /home/openclaw/ekotov-wiki (main),
# прод /opt/ekotov-wiki — файловая копия БЕЗ .git → обновление rsync.
#
# Запуск: sudo bash deploy/deploy.sh        (Заказчик, из-под root;
#         шаги приложения — от wiki через sudo -u wiki)
# Dry-run (ничего не меняет): DRY_RUN=1 bash deploy/deploy.sh
#
# Шаги: предусловия → бэкап БД → rsync → pip → схема app.db → рестарт → смоук.
# Останов на любой ошибке (set -euo pipefail); до рестарта прод продолжает
# работать старой версией — прерванный деплой безопасен.
# ============================================================
set -euo pipefail

# --- Параметры (переопределяются env) --------------------------------------
APP_DIR="${APP_DIR:-/opt/ekotov-wiki}"
SRC_DIR="${SRC_DIR:-/home/openclaw/ekotov-wiki}"
DB_PATH="${DB_PATH:-/var/lib/ekotov-wiki/wiki.db}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/ekotov-wiki}"
SERVICE="${SERVICE:-ekotov-wiki}"
PROD_URL="${PROD_URL:-https://127.0.0.1:10443}"
PORT="${PORT:-8377}"
# Целевой коммит main в клоне — обновлять перед каждым деплоем!
EXPECTED_COMMIT="${EXPECTED_COMMIT:-0cc9d6b}"
# Метка цели деплоя для имени бэкапа (конвенция: wiki-pre-<цель>-<дата>-<время>.db)
TARGET_LABEL="${TARGET_LABEL:-deploy}"
DRY_RUN="${DRY_RUN:-0}"

BACKUP_FILE="${BACKUP_DIR}/wiki-pre-${TARGET_LABEL}-$(date +%F-%H%M).db"

log()  { echo -e "\n\033[1;34m==> $*\033[0m"; }
ok()   { echo -e "\033[1;32m[OK]\033[0m $*"; }
fail() { echo -e "\033[1;31m[FAIL]\033[0m $*" >&2; exit 1; }
run()  { if [ "$DRY_RUN" = "1" ]; then echo "   [DRY-RUN] $*"; else "$@"; fi; }

# --- 1/6 Предусловия --------------------------------------------------------
log "1/6 Предусловия"
for tool in rsync sqlite3 curl git systemctl python3; do
  command -v "$tool" >/dev/null || fail "Нет утилиты: $tool"
done
id wiki >/dev/null 2>&1 || fail "Нет пользователя wiki"
[ -d "$APP_DIR" ] || fail "Нет каталога $APP_DIR"
[ -d "$SRC_DIR/.git" ] || fail "Нет локального клона $SRC_DIR (или это не git)"
[ -f "$DB_PATH" ] || fail "Нет БД $DB_PATH"
[ -f "$APP_DIR/.env" ] || fail "Нет $APP_DIR/.env (EnvironmentFile сервиса)"
[ -x "$APP_DIR/backend/.venv/bin/python" ] || fail "Нет venv $APP_DIR/backend/.venv"
[ -f "$APP_DIR/backend/requirements.txt" ] || fail "Нет requirements.txt"

CURRENT=$(git -C "$SRC_DIR" rev-parse --short HEAD)
[ "$CURRENT" = "$EXPECTED_COMMIT" ] || fail "Клон на $CURRENT, ожидался EXPECTED_COMMIT=$EXPECTED_COMMIT. Сначала синхронизируй клон/обнови EXPECTED_COMMIT."
ok "Клон на целевом коммите $CURRENT"

# sudo доступен? (скрипт запускается root'ом, но проверим на всякий случай)
if ! sudo -n true 2>/dev/null; then
  [ "$(id -u)" = "0" ] || echo "   (sudo запросит пароль — это нормально)"
fi

# --- 2/6 Бэкап БД ------------------------------------------------------------
log "2/6 Бэкап БД → $BACKUP_FILE"
run mkdir -p "$BACKUP_DIR"
if [ "$DRY_RUN" != "1" ]; then
  sudo chown wiki:wiki "$BACKUP_DIR" 2>/dev/null || true
  sudo -u wiki sqlite3 "$DB_PATH" ".backup ${BACKUP_FILE}" \
    || fail "Бэкап не создан — деплой прерван, БД не тронута."
  [ -s "$BACKUP_FILE" ] || fail "Файл бэкапа пуст"
  ok "Бэкап: $(sudo -u wiki du -h "$BACKUP_FILE" | cut -f1)"
else
  echo "   [DRY-RUN] sudo -u wiki sqlite3 $DB_PATH \".backup $BACKUP_FILE\""
fi

# --- 3/6 Код (rsync из клона) + зависимости ---------------------------------
log "3/6 rsync кода $SRC_DIR/ → $APP_DIR/"
run sudo rsync -a --delete --itemize-changes \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude 'backend/.venv/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache/' \
  --exclude '.ruff_cache/' \
  "$SRC_DIR/" "$APP_DIR/"
run sudo chown -R wiki:wiki "$APP_DIR"
[ "$DRY_RUN" = "1" ] || { [ -f "$APP_DIR/.env" ] || fail ".env пропал из $APP_DIR — останов."; }

log "3b/6 Зависимости backend (pip install, идемпотентно)"
if [ "$DRY_RUN" = "1" ]; then
  echo "   [DRY-RUN] sudo -u wiki $APP_DIR/backend/.venv/bin/pip install -q -r $APP_DIR/backend/requirements.txt"
else
  sudo -u wiki "$APP_DIR/backend/.venv/bin/pip" install -q -r "$APP_DIR/backend/requirements.txt" \
    || fail "pip install не прошел"
  ok "Зависимости соответствуют requirements.txt"
fi

# --- 4/6 Схема БД (идемпотентно; СТРОГО из cwd=backend, от wiki) -------------
log "4/6 Схема БД (python -m app.db из cwd=backend)"
if [ "$DRY_RUN" = "1" ]; then
  echo "   [DRY-RUN] ( cd $APP_DIR/backend && sudo -u wiki env DB_PATH=$DB_PATH SECRET_KEY=[REDACTED] .venv/bin/python -m app.db )"
else
  ( cd "$APP_DIR/backend" && sudo -u wiki env DB_PATH="$DB_PATH" SECRET_KEY="x" \
      .venv/bin/python -m app.db ) \
    || fail "Схема не применилась — БД в исходном состоянии, можно повторять после устранения причины. Бэкап: $BACKUP_FILE"
  ok "Схема применена"
fi

# --- 5/6 Рестарт сервиса ------------------------------------------------------
log "5/6 Рестарт $SERVICE"
run sudo systemctl restart "$SERVICE"
if [ "$DRY_RUN" != "1" ]; then
  sleep 2
  systemctl is-active --quiet "$SERVICE" || fail "Сервис не поднялся — journalctl -u $SERVICE -n 50"
  ok "Сервис активен"
fi

# --- 6/6 Смоук (обязателен, урок E10) ----------------------------------------
log "6/6 Смоук: health + страница + CSS через прод-URL"
if [ "$DRY_RUN" = "1" ]; then
  echo "   [DRY-RUN] curl -s http://127.0.0.1:$PORT/api/health"
  echo "   [DRY-RUN] curl -k $PROD_URL/login        (ожидаем 200)"
  echo "   [DRY-RUN] curl -k $PROD_URL/static/css/app.css   (ожидаем 200)"
  echo -e "\n\033[1;33m[DRY-RUN] Ничего не изменено. Для реального деплоя: sudo bash $0\033[0m"
  exit 0
fi

HEALTH=$(curl -s --max-time 5 "http://127.0.0.1:$PORT/api/health" || true)
echo "$HEALTH" | grep -q '"ok"' || fail "Health: '$HEALTH' — uvicorn не отвечает корректно"
ok "Health: $HEALTH"

PAGE=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "$PROD_URL/login" || true)
[ "$PAGE" = "200" ] || fail "Страница /login через прод-URL: $PAGE (ожидался 200)"
ok "Страница через прод-URL: 200"

CSS=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "$PROD_URL/static/css/app.css" || true)
[ "$CSS" = "200" ] || fail "Статика через прод-URL: $CSS (ожидался 200)"
ok "CSS через прод-URL: 200"

echo -e "\n\033[1;32m============================================"
echo "ДЕПЛОЙ $TARGET_LABEL ЗАВЕРШЕН УСПЕШНО"
echo "============================================\033[0m"
echo "Коммит:      $CURRENT"
echo "Бэкап БД:    $BACKUP_FILE"
echo ""
echo "Ручной смоук в браузере: логин → доска; если релиз трогал статику —"
echo "проверь static_v в backend/app/pages.py (кеш-бастинг)."
echo ""
echo "Откат (см. deploy/RUNBOOK.md §4.3): код — rsync из снапшота, данные — $BACKUP_FILE"
