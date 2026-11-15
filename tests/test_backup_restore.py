"""TD-A «Достоверный бэкап» (PLAN-TD-CLOSEOUT, TD-1) — tests backup.py + restore.py.

Трассировка (обслуживание TD-A, план вместо change-пакета):
  TC-TD1-001 — WAL-safe копия БД (sqlite backup API, WAL-хвост в копии);
  TC-TD1-002 — медиа-бэкап: инвентарь+hash-манифест (sha256, вложенность);
  TC-TD1-003 — пропуск отсутствующего тома (не блокирует запуск);
  TC-TD1-004 — restore-раундтрип на чистый volume → integrity + smoke;
  TC-TD1-005 — детект поврежденного tar / отказ писать в существующий каталог;
  TC-TD1-006 — retention daily-префиксов (релизные не трогаются);
  TC-TD1-007 — CLI restore.py (раундтрип, verify-only, коды ошибок).

Проверяется план-приемка TD-A:
  - медиа-каталоги (avatars/images/videos) попадают в бэкап с
    инвентарь+hash-манифестом (_manifest.json, sha256 каждого файла);
  - копия БД WAL-safe: sqlite3 .backup (sqlite backup API, НЕ файл-копия
    живой БД) — данные, живущие в WAL-хвосте на момент бэкапа, в копию входят;
  - restore на чистый volume → integrity_check + smoke-запрос + сверка
    sha256 восстановленных файлов с манифестом;
  - поврежденный tar/файл restore не пропускает (hash mismatch / расхождение
    tar ↔ манифест);
  - отсутствующий медиа-каталог (том не смонтирован) — цикл «пропускает»,
    запуск бэкапа не блокирует работу сервисов;
  - retention: новые префиксы images-daily-*/videos-daily-* чистятся,
    чужие (релизные wiki-pre-*) не трогаются.

Прогон (без стенда, stdlib-модули сервиса):
  /home/openclaw/venvs/wiki/bin/python -m pytest tests/test_backup_restore.py -v
"""

import json
import os
import sqlite3
import sys
import tarfile
from pathlib import Path

import pytest

SERVICES_BACKUP_DIR = (
    Path(__file__).resolve().parent.parent / "services" / "backup"
)
sys.path.insert(0, str(SERVICES_BACKUP_DIR))

import backup as backup_mod  # noqa: E402
import restore as restore_mod  # noqa: E402


# --- фикстуры ---------------------------------------------------------------

@pytest.fixture()
def volume(tmp_path):
    """«Том данных» tmp: БД в WAL + avatars + images; videos НЕ создаем
    (том не смонтирован в backup-контейнер — паритет текущего compose).
    Соединение НЕ закрывается до конца теста: чистый close сделал бы
    checkpoint и стер -wal — а нам нужен живой писатель с хвостом в WAL
    (как прод: app пишет, WAL не залит в main на момент бэкапа)."""
    vol = tmp_path / "volume"
    (vol / "avatars").mkdir(parents=True)
    (vol / "images").mkdir(parents=True)
    db_path = vol / "wiki.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")  # хвост остается в -wal
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.executemany("INSERT INTO t (v) VALUES (?)", [(f"row-{i}",) for i in range(5)])
    conn.commit()
    # медиа: вложенность + бинарник (нужен нетривиальный sha256)
    (vol / "avatars" / "u1.png").write_bytes(b"\x89PNG fake avatar bytes")
    (vol / "avatars" / "sub").mkdir()
    (vol / "avatars" / "sub" / "u2.png").write_bytes(b"\x89PNG nested avatar")
    (vol / "images" / "orig.jpg").write_bytes(os.urandom(1024))
    (vol / "images" / "thumb.jpg").write_bytes(os.urandom(128))
    yield vol
    conn.close()


# --- БД: WAL-safe копия ------------------------------------------------------

def test_backup_db_includes_wal_tail(volume, tmp_path):
    """sqlite backup API: данные из WAL-хвоста (не checkpoint'нуты) в копии."""
    db_path = str(volume / "wiki.db")
    dest = str(tmp_path / "wiki-daily-x.db")
    assert os.path.getsize(db_path + "-wal") > 0, "предусловие: хвост в -wal"
    backup_mod.backup_database(db_path, dest)
    # integrity + строки, жившие в WAL
    conn = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT count(*) FROM t").fetchone()[0] == 5
    finally:
        conn.close()


def test_backup_db_rejects_existing_dest(volume, tmp_path):
    dest = str(tmp_path / "wiki-daily-x.db")
    Path(dest).write_text("не пустой")
    with pytest.raises(FileExistsError):
        backup_mod.backup_database(str(volume / "wiki.db"), dest)
    assert Path(dest).read_text() == "не пустой"  # чужой файл не затерт


# --- медиа: инвентарь + hash-манифест ----------------------------------------

def test_media_manifest_inventory_and_hashes(volume, tmp_path):
    tar_path = str(tmp_path / "images-daily-x.tar")
    assert backup_mod.backup_media_dir(str(volume / "images"), tar_path)
    manifest = restore_mod.read_media_manifest(tar_path)
    assert manifest["format"] == backup_mod.MANIFEST_FORMAT
    paths = {e["path"] for e in manifest["files"]}
    assert paths == {"orig.jpg", "thumb.jpg"}
    for entry in manifest["files"]:
        src = volume / "images" / entry["path"]
        assert entry["size"] == src.stat().st_size
        import hashlib
        assert entry["sha256"] == hashlib.sha256(src.read_bytes()).hexdigest()
    assert manifest["total_files"] == len(manifest["files"])
    assert restore_mod.verify_media_tar(tar_path)["total_files"] == 2


def test_media_nested_dirs_in_manifest(volume, tmp_path):
    tar_path = str(tmp_path / "avatars-daily-x.tar")
    backup_mod.backup_avatars(str(volume / "avatars"), tar_path)
    manifest = restore_mod.read_media_manifest(tar_path)
    assert {e["path"] for e in manifest["files"]} == {
        "u1.png",
        "sub/u2.png",
    }


def test_missing_media_dir_is_skipped_not_fatal(tmp_path):
    """Том images не смонтирован → None + нет файла; цикл не падает."""
    tar_path = str(tmp_path / "images-daily-x.tar")
    assert backup_mod.backup_media_dir(str(tmp_path / "no-such-dir"), tar_path) is None
    assert not os.path.exists(tar_path)


def test_run_backup_full_cycle(volume, tmp_path):
    """Полный цикл: БД + avatars + images (есть) + videos (нет → пропуск)."""
    backup_dir = tmp_path / "backups"
    created = backup_mod.run_backup(
        db_path=str(volume / "wiki.db"),
        avatars_dir=str(volume / "avatars"),
        images_dir=str(volume / "images"),
        videos_dir=str(volume / "videos"),  # не смонтирован
        backup_dir=str(backup_dir),
    )
    names = sorted(os.path.basename(p) for p in created)
    assert len([n for n in names if n.startswith("wiki-daily-")]) == 1
    assert len([n for n in names if n.startswith("avatars-daily-")]) == 1
    assert len([n for n in names if n.startswith("images-daily-")]) == 1
    assert not [n for n in names if n.startswith("videos-daily-")]


# --- restore: чистый volume → smoke ------------------------------------------

def test_restore_roundtrip_fresh_volume(volume, tmp_path):
    backup_dir = tmp_path / "backups"
    created = backup_mod.run_backup(
        db_path=str(volume / "wiki.db"),
        avatars_dir=str(volume / "avatars"),
        images_dir=str(volume / "images"),
        videos_dir=str(volume / "videos"),
        backup_dir=str(backup_dir),
    )
    db_src = next(p for p in created if "wiki-daily-" in p)
    img_src = next(p for p in created if "images-daily-" in p)
    ava_src = next(p for p in created if "avatars-daily-" in p)

    fresh = tmp_path / "fresh-volume"  # «чистый volume»
    restore_mod.restore_db(db_src, str(fresh / "wiki.db"))
    restore_mod.restore_media(img_src, str(fresh / "images"))
    restore_mod.restore_media(ava_src, str(fresh / "avatars"))

    # smoke-запрос к восстановленной БД
    rows = restore_mod.smoke_query(str(fresh / "wiki.db"), "SELECT count(*) FROM t")
    assert rows == [(5,)]
    # восстановленные медиа байт-в-байт и по манифесту
    assert (fresh / "images" / "orig.jpg").read_bytes() == (
        volume / "images" / "orig.jpg"
    ).read_bytes()
    for entry in json.loads(
        tarfile.open(img_src).extractfile(backup_mod.MANIFEST_NAME).read()
    )["files"]:
        f = fresh / "images" / entry["path"]
        assert f.stat().st_size == entry["size"]
        import hashlib
        assert hashlib.sha256(f.read_bytes()).hexdigest() == entry["sha256"]


def test_restore_refuses_existing_dest(volume, tmp_path):
    tar_path = str(tmp_path / "images-daily-x.tar")
    backup_mod.backup_media_dir(str(volume / "images"), tar_path)
    dest = tmp_path / "images"
    dest.mkdir()
    (dest / "stale.txt").write_text("old data")
    with pytest.raises(FileExistsError):
        restore_mod.restore_media(tar_path, str(dest))
    assert (dest / "stale.txt").exists()  # старые данные не тронуты


def test_restore_detects_corrupted_media(volume, tmp_path):
    """Файл в tar подменен → restore падает на сверке sha256, каталог не
    оставляет «полувосстановленным»."""
    tar_path = tmp_path / "images-daily-x.tar"
    backup_mod.backup_media_dir(str(volume / "images"), str(tar_path))
    # пересобираем tar с ПОДМЕНЕННЫМ содержимым файла, манифест — исходный
    manifest = restore_mod.read_media_manifest(str(tar_path))
    evil = tmp_path / "evil.tar"
    with tarfile.open(tar_path) as src, tarfile.open(evil, "w") as dst:
        for m in src.getmembers():
            fh = src.extractfile(m)
            payload = fh.read()
            if m.name == "thumb.jpg":
                payload = b"CORRUPTED" + payload
            dst.addfile(m, __import__("io").BytesIO(payload))
    assert restore_mod.verify_media_tar(str(evil)) == manifest  # имена сходятся
    dest = tmp_path / "images-restored"
    with pytest.raises(ValueError, match="sha256"):
        restore_mod.restore_media(str(evil), str(dest))
    assert not dest.exists()  # атомарность: чистый каталог не создан


def test_restore_rejects_tar_without_manifest(tmp_path):
    plain = tmp_path / "plain.tar"
    with tarfile.open(plain, "w") as tar:
        info = tarfile.TarInfo("file.txt")
        payload = b"no manifest inside"
        info.size = len(payload)
        tar.addfile(info, __import__("io").BytesIO(payload))
    with pytest.raises(ValueError, match="манифест"):
        restore_mod.read_media_manifest(str(plain))


# --- retention ---------------------------------------------------------------

def test_retention_covers_media_prefixes_and_spares_release(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old = 1_000_000_000  # глубоко в прошлом
    names = {
        "wiki-daily-old.db": True,
        "avatars-daily-old.tar": True,
        "images-daily-old.tar": True,
        "videos-daily-old.tar": True,
        "wiki-pre-rel.db": False,      # релизный — deploy.sh, не трогать
        "avatars-pre-rel.tar": False,
        "unrelated.txt": False,
    }
    for name, is_old in names.items():
        p = backup_dir / name
        p.write_text("x")
        if is_old:
            os.utime(p, (old, old))
    removed = backup_mod.prune_old_backups(str(backup_dir), retention_days=14)
    assert sorted(removed) == sorted(
        n for n, is_old in names.items() if is_old
    )
    for name, is_old in names.items():
        assert (backup_dir / name).exists() is not is_old


# --- CLI restore.py ----------------------------------------------------------

def test_restore_cli_roundtrip(volume, tmp_path, capsys):
    """Полный CLI-цикл как в RUNBOOK: backup → restore на чистый volume."""
    backup_dir = tmp_path / "backups"
    created = backup_mod.run_backup(
        db_path=str(volume / "wiki.db"),
        avatars_dir=str(volume / "avatars"),
        images_dir=str(volume / "images"),
        videos_dir=str(volume / "videos"),
        backup_dir=str(backup_dir),
    )
    db_src = next(p for p in created if "wiki-daily-" in p)
    ava_src = next(p for p in created if "avatars-daily-" in p)
    fresh = tmp_path / "fresh"
    rc = restore_mod.main(
        [
            "--db-backup", db_src,
            "--db-dest", str(fresh / "wiki.db"),
            "--media-backup", ava_src,
            "--media-dest", str(fresh / "avatars"),
            "--smoke", "SELECT count(*) FROM t",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "integrity_check = ok" in out
    assert "smoke-запрос: [(5,)]" in out
    assert (fresh / "avatars" / "u1.png").read_bytes() == b"\x89PNG fake avatar bytes"


def test_restore_cli_verify_only_and_errors(volume, tmp_path, capsys):
    tar_path = str(tmp_path / "images-daily-x.tar")
    backup_mod.backup_media_dir(str(volume / "images"), tar_path)
    assert restore_mod.main(["--verify-only", "--media-backup", tar_path]) == 0
    # media-dest при verify-only — usage-ошибка (не пишет в назначения)
    with pytest.raises(SystemExit) as exc:
        restore_mod.main(["--verify-only", "--media-backup", tar_path,
                          "--media-dest", str(tmp_path / "x")])
    assert exc.value.code == 2
    # битый манифест-формат → код 1
    plain = tmp_path / "plain.tar"
    with tarfile.open(plain, "w") as tar:
        info = tarfile.TarInfo("a.txt")
        info.size = 1
        tar.addfile(info, __import__("io").BytesIO(b"x"))
    assert restore_mod.main(["--verify-only", "--media-backup", str(plain)]) == 1
