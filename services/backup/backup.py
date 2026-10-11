"""Sidecar-бэкап ekotov-wiki (задача 1.2, add-microservices-full; design §5).

Cron-цикл средствами python (без системного cron): сразу при старте и далее
каждые BACKUP_INTERVAL_SEC (дефолт 86400 = сутки) — консистентная копия
SQLite (sqlite3 .backup, WAL-safe) + tar каталога аватаров → каталог бэкапов,
retention BACKUP_RETENTION_DAYS (дефолт 14) для СВОИХ файлов (wiki-daily-*,
avatars-daily-*; релизные wiki-pre-*/avatars-pre-* деплоя sidecar не трогает).

Тома (deploy/compose.yaml, сервис backup):
  /data     — wiki-data:ro (только чтение: БД + avatars/)
  /backups  — bind /var/backups/ekotov-wiki

Вызов (один код, без дубля релизного бэкапа — design §5):
  sidecar-цикл:      python -m backup                       (CMD образа)
  из deploy.sh 1.4:  python -c "from backup import run_backup; run_backup()"

Read-only SQLite: том смонтирован ro, БД живет в WAL-режиме. mode=ro на
проде p15 падает (нельзя создать -wal/-shm рядом — том без создания файлов),
тогда backup_database ретраит с mode=ro&immutable=1 (только main-файл БД;
риск отставания на WAL-хвост задокументирован в коде). На томах, где -shm
создается, mode=ro работает как раньше (sqlite >= 3.22, heap-memory
wal-index; в python:3.12-slim sqlite >= 3.40).
"""

import os
import sqlite3
import tarfile
import time
from datetime import datetime, timezone

# Путь БД — тот же env, что у search-сервиса (services/search/app/db.py);
# дефолты совпадают с маунтами compose.
DB_PATH = os.environ.get("EKOTOV_WIKI_DB_PATH", "/data/wiki.db")
AVATARS_DIR = os.environ.get("EKOTOV_WIKI_AVATARS_DIR", "/data/avatars")
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/backups")
INTERVAL_SEC = int(os.environ.get("BACKUP_INTERVAL_SEC", "86400"))
RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "14"))

# Heartbeat для healthcheck (успешный цикл — см. main/healthcheck образа).
HEARTBEAT_PATH = os.environ.get("BACKUP_HEARTBEAT_PATH", "/tmp/backup-heartbeat")

# Свои префиксы имен (retention трогает только их; релизные backup'ы
# deploy.sh — wiki-pre-*/avatars-pre-* — не удаляет).
DB_PREFIX = "wiki-daily-"
AVATARS_PREFIX = "avatars-daily-"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_database(db_path: str, dest_path: str) -> str:
    """Консистентная копия SQLite: sqlite3 .backup (WAL-safe, как deploy.sh).

    Источник: сначала mode=ro; на проде p15 том не позволяет создать -wal/-shm
    рядом с БД — тогда ro-открытие/чтение падает и срабатывает retry с
    immutable=1 (см. комментарий ниже). Назначение не должно существовать
    (sqlite3.connect создает пустой файл — при ошибке чтения источника
    удаляем, чтобы не оставлять «пустой бэкап»).
    """
    if os.path.exists(dest_path):
        raise FileExistsError(f"Файл бэкапа уже существует: {dest_path}")

    def _attempt(immutable: bool) -> None:
        uri = f"file:{db_path}?mode=ro" + ("&immutable=1" if immutable else "")
        src = sqlite3.connect(uri, uri=True)
        try:
            dst = sqlite3.connect(dest_path)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

    # Read-only SQLite на проде (p15): wiki-data смонтирован так, что sqlite
    # не может создать -wal/-shm РЯДОМ с БД (touch в /data → Read-only file
    # system). mode=ro при этом падает (на живом контейнере проверено:
    # "unable to open database file" на connect; локально воспроизводится и
    # вариант "attempt to write a readonly database" уже на .backup —
    # ловим ОБА). Рабочий вариант — immutable=1: sqlite читает ТОЛЬКО
    # main-файл БД, ничего не создавая рядом.
    # Стратегия: сначала честный mode=ro (на деве/старых томах — видит WAL);
    # при одной из этих OperationalError — retry с immutable=1 и WARNING.
    # Риск (задокументирован): immutable НЕ читает WAL — записи, не попавшие
    # в main-файл (checkpoint), в бэкап не войдут.
    #   Релизный бэкап (deploy.sh): миграция выполняется ДО старта backup —
    #   на этот путь фикс не влияет. Живой sidecar-цикл (24ч): между тиками
    #   app пишет в WAL — суточный бэкап может отставать на незалитый
    #   WAL-хвост. Фундаментальное решение — дать backup rw-доступ к /data
    #   (убрать ':ro' с wiki-data маунта в deploy/compose.yaml) — за
    #   Заказчиком.
    try:
        try:
            _attempt(immutable=False)
        except sqlite3.OperationalError as exc:
            msg = str(exc)
            if (
                "unable to open database file" not in msg
                and "attempt to write a readonly database" not in msg
            ):
                raise
            print(
                f"[backup] WARNING: mode=ro не открыл {db_path} ({exc!r}) — "
                "retry с immutable=1: SQLite прочитает ТОЛЬКО main-файл БД, "
                "НЕ читая WAL; суточный бэкап может не включить последние "
                "записи из WAL (фундаментальное решение — rw-маунт /data для "
                "backup, см. deploy/compose.yaml)",
                flush=True,
            )
            if os.path.exists(dest_path):
                os.remove(dest_path)
            _attempt(immutable=True)
    except Exception:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise
    if not os.path.getsize(dest_path):
        os.remove(dest_path)
        raise RuntimeError(f"Бэкап БД пуст: {dest_path}")
    return dest_path


def backup_avatars(avatars_dir: str, dest_path: str) -> str:
    """tar каталога аватаров. Каталог может отсутствовать (пустой том /
    первый деплой) — тогда пустой tar, как в deploy.sh (шаг 2/7)."""
    with tarfile.open(dest_path, "w") as tar:
        if os.path.isdir(avatars_dir):
            for name in sorted(os.listdir(avatars_dir)):
                tar.add(os.path.join(avatars_dir, name))
    return dest_path


def prune_old_backups(backup_dir: str, retention_days: int) -> list[str]:
    """Удаляет СВОИ файлы (wiki-daily-*, avatars-daily-*) старше retention.

    Отсчет — по mtime. Чужие файлы каталога (релизные wiki-pre-* и пр.)
    не трогает — их жизненный цикл ведет deploy.sh.
    """
    cutoff = time.time() - retention_days * 86400
    removed: list[str] = []
    for name in sorted(os.listdir(backup_dir)):
        if name.startswith((DB_PREFIX, AVATARS_PREFIX)):
            path = os.path.join(backup_dir, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed.append(name)
            except OSError as exc:
                print(f"[backup] retention: пропущен {name}: {exc}", flush=True)
    return removed


def run_backup(
    db_path: str | None = None,
    avatars_dir: str | None = None,
    backup_dir: str | None = None,
) -> list[str]:
    """Один цикл бэкапа: БД + аватары + retention. Возвращает созданные файлы.

    Точка вызова для deploy.sh (задача 1.4, релизный бэкап — тот же код).
    """
    db_path = db_path or DB_PATH
    avatars_dir = avatars_dir or AVATARS_DIR
    backup_dir = backup_dir or BACKUP_DIR
    os.makedirs(backup_dir, exist_ok=True)
    stamp = _stamp()
    created: list[str] = []

    db_dest = os.path.join(backup_dir, f"{DB_PREFIX}{stamp}.db")
    backup_database(db_path, db_dest)
    created.append(db_dest)
    print(f"[backup] БД: {db_dest} ({os.path.getsize(db_dest)} bytes)", flush=True)

    avatars_dest = os.path.join(backup_dir, f"{AVATARS_PREFIX}{stamp}.tar")
    backup_avatars(avatars_dir, avatars_dest)
    created.append(avatars_dest)
    print(
        f"[backup] аватары: {avatars_dest} ({os.path.getsize(avatars_dest)} bytes)",
        flush=True,
    )

    removed = prune_old_backups(backup_dir, RETENTION_DAYS)
    if removed:
        print(f"[backup] retention {RETENTION_DAYS}d: удалено {removed}", flush=True)
    return created


# Первый тик на пустом томе (свежий хост, tasks 2.3/2.4): БД еще не создана
# (ее создает app при первом старте), run_backup упадет. Чтобы не ждать
# следующего тика INTERVAL_SEC (до суток без бэкапа), первый ЦИКЛ ретраится
# быстро: FIRST_TICK_RETRIES попыток с шагом FIRST_TICK_RETRY_SEC (5x30s =
# 2.5 мин на старт app). После первого УСПЕШНОГО цикла — обычный суточный
# ритм; ошибки последующих тиков ждут следующего интервала (как раньше).
FIRST_TICK_RETRIES = int(os.environ.get("BACKUP_FIRST_TICK_RETRIES", "5"))
FIRST_TICK_RETRY_SEC = int(os.environ.get("BACKUP_FIRST_TICK_RETRY_SEC", "30"))


def _heartbeat() -> None:
    with open(HEARTBEAT_PATH, "w") as fh:
        fh.write(str(int(time.time())))


def main() -> None:
    """Cron-цикл sidecar: бэкап сразу при старте, далее раз в INTERVAL_SEC.

    Первый цикл (до первого успеха) — быстрые ретраи: до
    BACKUP_FIRST_TICK_RETRIES попыток с паузой BACKUP_FIRST_TICK_RETRY_SEC
    (дефолт 5x30s = 2.5 мин) — на свежем хосте БД появляется с первым
    стартом app, и одиночный тик без ретраев падал бы с паузой до суток.
    Если ретраи исчерпаны — честный выход (ненулевой код): контейнер
    перезапустит restart: unless-stopped, к тому моменту БД обычно уже есть.
    """
    first_tick = True
    while True:
        if first_tick:
            for attempt in range(1, FIRST_TICK_RETRIES + 1):
                try:
                    run_backup()
                    _heartbeat()
                    first_tick = False
                    break
                except Exception as exc:
                    print(
                        f"[backup] первый тик {attempt}/{FIRST_TICK_RETRIES} "
                        f"не удался: {exc!r}"
                        + (f"; повтор через {FIRST_TICK_RETRY_SEC}s" if attempt < FIRST_TICK_RETRIES else ""),
                        flush=True,
                    )
                    if attempt < FIRST_TICK_RETRIES:
                        time.sleep(FIRST_TICK_RETRY_SEC)
            if first_tick:
                raise SystemExit(
                    f"[backup] первый тик не удался после "
                    f"{FIRST_TICK_RETRIES}x{FIRST_TICK_RETRY_SEC}s — выход; "
                    "restart: unless-stopped поднимет контейнер снова "
                    "(БД, вероятно, еще не создана app'ом на свежем хосте)"
                )
            # 1.2-g (review-005-1.2): первый цикл удался (сразу или через
            # ретраи) — пауза INTERVAL_SEC, как после обычного успеха, иначе
            # while уводит в else-ветку и run_backup() вызывается повторно
            # НЕМЕДЛЕННО (дубль-бэкап; секундный stamp тот же → ложный
            # FileExistsError в логах).
            time.sleep(INTERVAL_SEC)
        else:
            try:
                run_backup()
                _heartbeat()
            except Exception as exc:  # цикл живет: следующий суточный тик повторит
                print(f"[backup] ОШИБКА цикла: {exc!r}", flush=True)
            time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
