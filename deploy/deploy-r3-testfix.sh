#!/usr/bin/env bash
# ============================================================
# deploy-r3-testfix.sh — «всё в одном» для Заказчика.
# Деплой ekotov-wiki на коммит e6f5b42 (testfix Р3 + review-004 APPROVE).
#
# Запуск В СЕРВЕРНОМ ТЕРМИНАЛЕ (обязательно sudo -E, из-под openclaw):
#   cd /home/openclaw/ekotov-wiki && sudo -E bash deploy/deploy-r3-testfix.sh
#
# Внутри: EXPECTED_COMMIT зафиксирован, дальше — канонический deploy.sh
# (бэкап БД → rsync → pip → схема → рестарт → смоук health/страница/CSS/статика).
# При любой ошибке — стоп до изменений; прод продолжает работать старой версией.
# ============================================================
set -euo pipefail
cd /home/openclaw/ekotov-wiki
exec env EXPECTED_COMMIT=e6f5b42 TARGET_LABEL=r3-testfix bash deploy/deploy.sh
