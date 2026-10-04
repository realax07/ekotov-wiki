# Образ sidecar-бэкапа ekotov-wiki/backup (change add-microservices-full,
# tasks 1.2; design §5: python:3.12-slim, cron-цикл средствами python,
# USER non-root, healthcheck процесса, данных в образе нет).
#
# Контекст сборки — корень репозитория (compose: context: ..,
# dockerfile: services/backup/Dockerfile):
#   docker build -f services/backup/Dockerfile -t ekotov-wiki/backup:local .
#
# Тегирование: ekotov-wiki/backup:<release>; latest ЗАПРЕЩЕН (FR-72).
#
# Deps НЕ нужны: backup.py — только stdlib (sqlite3, tarfile) — слой deps
# отсутствует осознанно.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="ekotov-wiki/backup" \
      org.opencontainers.image.description="Sidecar-бэкап ekotov-wiki (sqlite3 .backup + tar avatars, retention 14 дней, design §5)"

COPY services/backup/backup.py /srv/backup.py

# Каталог бэкапов — bind /var/backups/ekotov-wiki (compose). Владелец — uid
# 10001: bind-каталог на хосте создается root'ом (mkdir в Dockerfile имеет
# owner root) — заранее chown'им, иначе non-root не запишет бэкап
# (compose не выставляет :O у bind'ов — так же, как в боевой схеме).
RUN mkdir -p /backups /data && chown 10001:10001 /backups /data

# Запуск НЕ от root (uid 10001 — вне диапазона пользователей образа).
USER 10001

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Healthcheck ПРОЦЕССА (design §5): живой python-цикл печатает heartbeat
# (epoch, services/backup/backup.py::_heartbeat). stale-heartbeat (> 2
# интервала) = деградация — рестарт контейнера.
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os,sys,time; p=os.environ.get('BACKUP_HEARTBEAT_PATH','/tmp/backup-heartbeat'); sys.exit(0 if os.path.exists(p) and time.time()-float(open(p).read().strip()) < 2*int(os.environ.get('BACKUP_INTERVAL_SEC','86400')) else 1)"]

# Данных в образе НЕТ: БД/аватары — том wiki-data:ro (compose); каталог
# бэкапов — bind /var/backups/ekotov-wiki (compose).
# python -m backup = цикл sidecar; одноразовый вызов из deploy.sh (задача
# 1.4) — «python -c 'from backup import run_backup; run_backup()'» (один код).
CMD ["python", "-m", "backup"]
