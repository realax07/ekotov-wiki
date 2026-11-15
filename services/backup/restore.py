"""Restore из бэкапов ekotov-wiki (TD-A «Достоверный бэкап», PLAN-TD-CLOSEOUT).

Симметрия к services/backup/backup.py:
  wiki-daily-*.db     — консистентная копия SQLite (sqlite3 .backup, WAL-safe)
  avatars-daily-*.tar — медиа-каталог + hash-манифест _manifest.json
  images-daily-*.tar / videos-daily-*.tar — аналогично, свои тома

Восстановление:
  - БД: атомарная файл-копия в назначение (копия УЖЕ консистентна — снята
    через sqlite backup API, а не из живого WAL) + PRAGMA integrity_check;
  - медиа: распаковка tar в чистый каталог + побайтовая сверка sha256 по
    манифесту (файл лишний/не хватает/хеш не сошелся — restore падает).

Вызов (CLI):
  python restore.py --db-backup /backups/wiki-daily-XXX.db --db-dest /data/wiki.db
  python restore.py --media-backup /backups/images-daily-XXX.tar --media-dest /data/images
  python restore.py --verify-only --db-backup ... --media-backup ...   # только проверка

Код возврата: 0 — OK; 1 — ошибка проверки (манифест/integrity); 2 — usage.
Restore-тест TD-A: tests/test_backup_restore.py (чистый tmp-volume → smoke).
Процедура на проде: docs/ops/backup-restore.md (RUNBOOK «Бэкап/Restore»).
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile

from backup import (  # тот же каталог /srv в образе; WORKDIR=/srv
    MANIFEST_FORMAT,
    MANIFEST_NAME,
    _sha256_file,
)


def read_media_manifest(media_tar: str) -> dict:
    """Читает _manifest.json из медиа-tar; формат не тот — ValueError."""
    with tarfile.open(media_tar, "r") as tar:
        try:
            fh = tar.extractfile(MANIFEST_NAME)
        except KeyError:
            fh = None
        if fh is None:
            raise ValueError(
                f"{media_tar}: нет {MANIFEST_NAME} — tar без манифеста "
                "(старый формат до TD-A) восстановлению по хешам не подлежит"
            )
        manifest = json.loads(fh.read().decode())
    if manifest.get("format") != MANIFEST_FORMAT:
        raise ValueError(
            f"{media_tar}: формат манифеста {manifest.get('format')!r} ≠ "
            f"{MANIFEST_FORMAT!r}"
        )
    return manifest


def verify_media_tar(media_tar: str) -> dict:
    """Проверка tar БЕЗ распаковки: манифест читается, имена членов tar
    соответствуют манифесту (лишние/недостающие — ошибка)."""
    manifest = read_media_manifest(media_tar)
    expected = {e["path"] for e in manifest["files"]} | {MANIFEST_NAME}
    with tarfile.open(media_tar, "r") as tar:
        members = {m.name for m in tar.getmembers() if m.isfile()}
    missing = sorted(expected - members)
    extra = sorted(members - expected)
    if missing or extra:
        raise ValueError(
            f"{media_tar}: расхождение tar ↔ манифест; нет: {missing}; "
            f"лишние: {extra}"
        )
    return manifest


def restore_media(media_tar: str, dest_dir: str) -> dict:
    """Распаковка медиа-tar в ЧИСТЫЙ каталог + сверка sha256 каждого файла.

    dest_dir не должен существовать (restore на чистый volume) — защита от
    смешивания старых и восстановленных файлов. Возвращает сводку манифеста.
    """
    manifest = verify_media_tar(media_tar)
    if os.path.exists(dest_dir):
        raise FileExistsError(
            f"Каталог назначения уже существует: {dest_dir} — restore "
            "выполняется на чистый volume/каталог (см. docs/ops/backup-restore.md)"
        )
    # Распаковка во временный каталог рядом с назначением → атомарный rename:
    # сбой сверки не оставляет «полувосстановленный» каталог.
    parent = os.path.dirname(os.path.abspath(dest_dir)) or "."
    os.makedirs(parent, exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix=".restore-", dir=parent)
    try:
        with tarfile.open(media_tar, "r") as tar:
            for member in tar.getmembers():
                if member.isfile() and member.name != MANIFEST_NAME:
                    tar.extract(member, tmp_dir, set_attrs=False)
        for entry in manifest["files"]:
            path = os.path.join(tmp_dir, *entry["path"].split("/"))
            if not os.path.isfile(path):
                raise ValueError(f"после распаковки нет файла: {entry['path']}")
            size = os.path.getsize(path)
            if size != entry["size"]:
                raise ValueError(
                    f"{entry['path']}: размер {size} ≠ {entry['size']} в манифесте"
                )
            digest = _sha256_file(path)
            if digest != entry["sha256"]:
                raise ValueError(
                    f"{entry['path']}: sha256 {digest} ≠ {entry['sha256']} "
                    "(файл в tar поврежден)"
                )
        os.rename(tmp_dir, dest_dir)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    print(
        f"[restore] медиа {dest_dir}: {manifest['total_files']} файлов, "
        f"{manifest['total_bytes']} bytes, sha256 сверены — OK",
        flush=True,
    )
    return manifest


def restore_db(db_backup: str, db_dest: str) -> str:
    """Копия бэкапа БД в назначение (атомарно) + PRAGMA integrity_check.

    Назначение не должно существовать (не затираем живую БД по опечатке —
    остановка app и осознанный restore по RUNBOOK)."""
    if os.path.exists(db_dest):
        raise FileExistsError(
            f"Файл БД назначения уже существует: {db_dest} — restore "
            "выполняется на чистый volume при остановленных писателях "
            "(см. docs/ops/backup-restore.md)"
        )
    parent = os.path.dirname(os.path.abspath(db_dest)) or "."
    os.makedirs(parent, exist_ok=True)
    tmp_path = db_dest + ".restore-tmp"
    shutil.copyfile(db_backup, tmp_path)
    conn = sqlite3.connect(tmp_path)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    finally:
        conn.close()
    if row is None or row[0] != "ok":
        os.remove(tmp_path)
        raise ValueError(f"{db_backup}: integrity_check → {row!r}, не 'ok'")
    os.replace(tmp_path, db_dest)
    print(
        f"[restore] БД: {db_dest} ({os.path.getsize(db_dest)} bytes), "
        "integrity_check = ok",
        flush=True,
    )
    return db_dest


def smoke_query(db_path: str, query: str = "SELECT count(*) FROM sqlite_master") -> list:
    """Smoke-запрос после restore (RUNBOOK: убедиться, что БД читается)."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return conn.execute(query).fetchall()
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Restore ekotov-wiki из бэкапа (backup.py, TD-A)"
    )
    parser.add_argument("--db-backup", help="wiki-daily-*.db для восстановления БД")
    parser.add_argument("--db-dest", help="путь восстановленной БД (напр. /data/wiki.db)")
    parser.add_argument(
        "--media-backup", action="append", default=[],
        help="медиа-tar (avatars/images/videos-daily-*.tar); флаг можно повторять"
    )
    parser.add_argument(
        "--media-dest", action="append", default=[],
        help="каталог назначения для предыдущего --media-backup (1:1 по порядку)"
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="только проверить целостность (без записи в назначения)"
    )
    parser.add_argument(
        "--smoke",
        default="SELECT count(*) FROM sqlite_master",
        help="smoke-запрос к восстановленной БД (дефолт: count(sqlite_master))",
    )
    args = parser.parse_args(argv)

    if not args.verify_only and len(args.media_backup) != len(args.media_dest):
        parser.error("--media-dest должен идти 1:1 за каждым --media-backup")
    if not (args.db_backup or args.media_backup):
        parser.error("укажите --db-backup и/или --media-backup")
    if args.db_backup and not args.verify_only and not args.db_dest:
        parser.error("--db-backup без --verify-only требует --db-dest")
    if args.verify_only and (args.db_dest or args.media_dest):
        parser.error("--verify-only не пишет в назначения: без --db-dest/--media-dest")

    try:
        if args.db_backup:
            if args.verify_only:
                conn = sqlite3.connect(f"file:{args.db_backup}?mode=ro", uri=True)
                try:
                    row = conn.execute("PRAGMA integrity_check").fetchone()
                finally:
                    conn.close()
                if row is None or row[0] != "ok":
                    raise ValueError(f"{args.db_backup}: integrity_check → {row!r}")
                print(f"[restore] verify БД {args.db_backup}: integrity ok", flush=True)
            else:
                restore_db(args.db_backup, args.db_dest)
                rows = smoke_query(args.db_dest, args.smoke)
                print(f"[restore] smoke-запрос: {rows!r}", flush=True)
        for i, media_tar in enumerate(args.media_backup):
            dest = None if args.verify_only else args.media_dest[i]
            if args.verify_only:
                manifest = verify_media_tar(media_tar)
                print(
                    f"[restore] verify {media_tar}: {manifest['total_files']} "
                    "файлов, манифест/tar согласованы",
                    flush=True,
                )
            else:
                restore_media(media_tar, dest)
    except (ValueError, FileExistsError, tarfile.TarError, sqlite3.Error) as exc:
        print(f"[restore] ОШИБКА: {exc}", file=sys.stderr, flush=True)
        return 1
    print("[restore] OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
