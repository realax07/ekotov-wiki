#!/usr/bin/env bash
# ============================================================
# deploy-r3-testfix.sh — «всё в одном» для Заказчика.
# Деплой ekotov-wiki с текущего HEAD main (testfix Р3 + review-004 APPROVE).
#
# Запуск В СЕРВЕРНОМ ТЕРМИНАЛЕ (обязательно sudo -E, из-под openclaw):
#   cd /home/openclaw/ekotov-wiki && sudo -E bash deploy/deploy-r3-testfix.sh
#
# EXPECTED_COMMIT вычисляется из HEAD клона на лету — коммит обёртки
# сам себе не ломает. Внутри — канонический deploy.sh: сверка клона,
# бэкап БД → rsync → pip → схема → рестарт → смоук health/страница/CSS/статика.
# При любой ошибке — стоп до изменений; прод продолжает работать старой версией.
# ============================================================
set -euo pipefail
SRC=/home/openclaw/ekotov-wiki
cd "$SRC"
HEAD=$(git -C "$SRC" -c safe.directory="$SRC" rev-parse --short HEAD)
exec env EXPECTED_COMMIT="$HEAD" TARGET_LABEL=r3-testfix bash deploy/deploy.sh
