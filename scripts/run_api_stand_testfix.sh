#!/usr/bin/env bash
# Подъем API-стенда ekotov-wiki для прогона tests/api (tests/README.md).
set -euo pipefail
cd /home/openclaw/ekotov-wiki-worktrees/sess-testfix-r3/backend
export DB_PATH="${DB_PATH:-/home/openclaw/.hermes/cache/scratch/ekotov-api-testfix/app.db}"
export SECRET_KEY="${SECRET_KEY:-qa-testfix-r3-secret-key-0123456789abcdef}"
mkdir -p "$(dirname "$DB_PATH")"
rm -f "$DB_PATH"
python -m app.db
# seed_users читает пароли через getpass из STDIN (пароль + повтор на учетку);
# значения тестовые (tests/README.md), в продукт не попадают.
printf 'QaOwner_Pass_1!\nQaOwner_Pass_1!\nQaWife_Pass_2!\nQaWife_Pass_2!\n' | python -m app.seed_users
exec python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-38465}"
