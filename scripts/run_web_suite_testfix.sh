#!/usr/bin/env bash
# Полный прогон web-сьюта с сохранением полного вывода (для анализа падений).
cd /home/openclaw/ekotov-wiki-worktrees/sess-testfix-r3
source /home/openclaw/venvs/wiki/bin/activate
python -m pytest tests/web -q 2>&1 | tee "$1" | tail -1
