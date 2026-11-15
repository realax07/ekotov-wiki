# PLAN-TD-CLOSEOUT.md — закрытие техдолга TD-1..TD-5 (решение Заказчика 2026-11-15 «давай техдолг закроем и пойдем по новым»)

Источник: PRODUCT_BACKLOG.md Блок TD (аудит Kimi K3.1, 2026-10-31) + пересечение с P22/P24/P25.
После закрытия — переход на новые: P21 → P10 → P20.

## Пакеты и флоу

### TD-A. Достоверный бэкап (TD-1) — Флоу 4 (обслуживание, devops+dev)
- services/backup/backup.py: медиа-каталог в бэкап (инвентарь+hash-манифест), WAL-safe копия БД (sqlite backup API/VACUUM INTO, не файл-копия живой БД), restore-скрипт + restore-тест (подъем на чистом volume → smoke).
- RUNBOOK: раздел «Бэкап/Restore».
- Приемка: restore-тест зеленый; бэкап содержит media; запуск не блокирует работу сервисов.
- Зоны: services/backup/**, docs/ops/** (RUNBOOK), tests/.

### TD-B. Идемпотентный PUT реакций (TD-5) — Флоу 2 (багфикс, dev+QA)
- backend/app: повторный PUT реакции при ретрае не снимает голос (идемпотентность по ключу user+target).
- TC-кейс + автотест; regress-final обязателен.
- Зоны: backend/app/**, tests/**.

### TD-C. Docker socket + периметр game-portal (TD-2 + TD-3) — Флоу 4 (devops/ops)
- deploy/compose.yaml: netdata без docker.sock (ограничение доступа/сокет-прокси — решение по месту, минимум прав).
- game-portal в периметр: RUNBOOK §9 актуализация (подъем/обновление ПМ-ом, состояния, откаты), фиксация «контейнер вне compose — осознанно».
- Зоны: deploy/compose.yaml, docs/ops/** (RUNBOOK), docs/**.

### TD-D. Релизный контур deploy.sh (TD-4 + P22 + P24 + P25) — Флоу 4 (devops)
- deploy.sh: video в матрицу (SERVICES, *_IMAGE, dockerfile_for, шаг 5/8) — P19-паттерн; P22 закрыть как дубль P24.
- worktree как SRC_DIR: проверка git-работоспособности (git rev-parse) вместо [ -d .git ].
- Честные health: video/netdata healthcheck отражает готовность, не «живость процесса».
- Зоны: deploy/**, docs/ops/** (RUNBOOK).

## Порядок
1. Волна 1 параллельно (зоны не пересекаются): TD-A, TD-B, TD-C.
2. Волна 2 после слияния волны 1: TD-D (deploy.sh + RUNBOOK, чтобы не конфликтовать по докам).
3. Каждый пакет — отдельная ветка pipeline/td-*, PR с каноническим маркером, CI green, ПМ верифицирует дифф до merge.

## Критерии закрытия
TD-1..TD-5 закрыты в PRODUCT_BACKLOG.md с релизными ссылками; прод здоров (7/7 + video/netdata health). Затем P21 (запросить у Заказчика актуальный список дефектов после «Пульт 2.0») → P10 → P20.
