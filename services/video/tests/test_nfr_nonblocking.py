"""NFR-37/приемка куска B: фоновая конвертация не блокирует сервис
(approved-кейсы TC-vid-008, TC-vid-017, TC-vid-039).

Механика: ffmpeg — скрипт-заглушка, ждущая файла-релиза (конвертация
«идет» контролируемо долго, без реального кодирования); пока воркер
занят, измеряются:
- p95 из 20× GET /api/videos — порог < 500 мс (NFR-37, TC-vid-017/039);
- 5× загрузка малого файла — каждая < 5 с (TC-vid-008/014), p95
  фиксируется в REPORT (порог NFR-37 — < 500 мс, TC-vid-039 шаг 3).

Конвенция services/video/tests: in-process TestClient, временные БД и
том, без сети. Живая замена на стенде (файл ~300 МБ, docker stats) —
test-model/reports/REPORT-video-coverage-matrix.md (TC-vid-037/039).

Запуск (из services/video/): python3 -m pytest tests/test_nfr_nonblocking.py -v
"""

import os
import queue
import shutil
import sqlite3
import threading
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app import converter
from app.main import app
from app.middleware import SESSION_COOKIE_NAME

from tests.test_videos_service import SCHEMA_SQL

# Порог NFR-37 (TC-vid-017 шаг 1 / TC-vid-039 шаг 4): p95 списка < 500 мс.
P95_LIST_BUDGET_S = 0.5
# Порог загрузки при идущей конвертации (TC-vid-008 шаг 2 / 017 шаг 2): < 5 с.
UPLOAD_BUDGET_S = 5.0


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "wiki.db")
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO users (id, login, password_hash, display_name)"
            " VALUES (1, 'owner', 'x', 'Owner')"
        )
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at)"
            " VALUES ('test-token-1', 1, ?, ?)",
            (
                datetime_now_iso(),
                datetime_now_iso(+1),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("EKOTOV_WIKI_DB_PATH", path)
    return path


def datetime_now_iso(days=0):
    from datetime import datetime, timedelta, timezone

    return (
        datetime.now(timezone.utc) + timedelta(days=days)
    ).isoformat()


@pytest.fixture()
def videos_dir(tmp_path, monkeypatch):
    d = str(tmp_path / "videos-data")
    os.makedirs(d, exist_ok=True)
    monkeypatch.setenv("EKOTOV_WIKI_VIDEOS_DIR", d)
    return d


@pytest.fixture()
def client(db_path, videos_dir):
    with TestClient(app) as c:
        c.cookies.set(SESSION_COOKIE_NAME, "test-token-1")
        yield c


@pytest.fixture(autouse=True)
def _no_worker_leak():
    """Гигиена (паритет test_converter): воркер после теста остановлен,
    очередь пуста — живой поток не обслуживает соседние модули."""
    yield
    while True:
        try:
            converter._queue.get_nowait()
            converter._queue.task_done()
        except queue.Empty:
            break
    converter.stop_worker()


@pytest.fixture()
def slow_conversion(tmp_path, monkeypatch, db_path, videos_dir):
    """Записи «uploaded» в очереди + ffmpeg-заглушка, ждущая релиза:
    worker обслуживает ровно одну «долгую конвертацию», пока тест меряет.
    Возврат: (release_path, video_id)."""
    d = tmp_path / "stubs"
    d.mkdir()
    started = d / "ffmpeg.started"
    release = d / "ffmpeg.release"
    stub = d / "slow.sh"
    stub.write_text(
        "#!/bin/sh\n"
        'touch "$SLOW_FLAG"\n'
        'while [ ! -e "$RELEASE_FLAG" ]; do :; done\n'
        'src=""; prev=""; for a in "$@"; do [ "$prev" = "-i" ] && src="$a"; prev="$a"; done\n'
        'last=""; for a in "$@"; do last="$a"; done\n'
        'case "$last" in\n'
        "  *.jpg) printf '\\xff\\xd8\\xff\\xe0fake-jpeg' > \"$last\" ;;\n"
        '  *) cp "$src" "$last" ;;\n'
        "esac\n"
    )
    stub.chmod(0o755)

    monkeypatch.setenv("SLOW_FLAG", str(started))
    monkeypatch.setenv("RELEASE_FLAG", str(release))
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", str(stub))
    monkeypatch.delenv("EKOTOV_WIKI_CONVERTER", raising=False)

    from app import storage

    video_id = uuid.uuid4().hex
    storage.create_video_dir(video_id)
    with open(storage.original_path(video_id, "mkv"), "wb") as f:
        f.write(b"fixture-original-bytes")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO video_videos (id, filename, status, size_bytes, mime,"
            " uploaded_by, created_at, convert_attempts)"
            " VALUES (?, 'video_500mb.mkv', 'uploaded', 21,"
            " 'video/x-matroska', 1, ?, 0)",
            (video_id, datetime_now_iso()),
        )
        conn.commit()
    finally:
        conn.close()

    assert converter.start_worker() is not None
    # Конвертация «идет», как только ffmpeg-заглушка стартовала.
    deadline = time.monotonic() + 10
    while not started.exists():
        assert time.monotonic() < deadline, "ffmpeg-заглушка не стартовала"
        threading.Event().wait(0.02)
    return str(release), video_id


def _p95(samples):
    ordered = sorted(samples)
    # nearest-rank p95
    idx = max(0, round(0.95 * len(ordered) + 0.5) - 1)
    return ordered[idx]


def test_nfr37_list_p95_during_conversion(client, slow_conversion):
    """TC-vid-017 шаг 1 + TC-vid-039 шаг 2/4 (NFR-37): пока идет
    конвертация, 20× GET /api/videos — все отвечают, p95 < 500 мс;
    ни один запрос не ждал завершения конвертации."""
    release, video_id = slow_conversion
    try:
        samples = []
        for _ in range(20):
            t0 = time.monotonic()
            resp = client.get("/api/videos")
            samples.append(time.monotonic() - t0)
            assert resp.status_code == 200
            item = next(v for v in resp.json()["videos"] if v["id"] == video_id)
            assert item["status"] == "converting"  # конвертация еще идет

        p95 = _p95(samples)
        assert p95 < P95_LIST_BUDGET_S, (p95, max(samples))
    finally:
        with open(release, "w") as f:
            f.write("go")
    converter._queue.join()
    print(f"\nNFR-37 (unit): p95 20× GET /api/videos = {p95 * 1000:.1f} мс "
          f"(порог < 500 мс); max = {max(samples) * 1000:.1f} мс")


def test_nfr37_uploads_during_conversion(client, slow_conversion):
    """TC-vid-008 + TC-vid-017 шаг 2 + TC-vid-039 шаг 3 (NFR-37): пока
    идет конвертация, 5× загрузка малого файла — каждая < 5 с, все 201;
    p95 загрузок фиксируется (порог < 500 мс), статусы в списке
    независимые."""
    release, converting_id = slow_conversion
    small = b"small-mp4-bytes" * 350 * 1024  # ~5 МБ
    try:
        samples = []
        ids = []
        for n in range(5):
            t0 = time.monotonic()
            resp = client.post(
                "/api/videos",
                files={"file": (f"small_{n}.mp4", small, "video/mp4")},
            )
            elapsed = time.monotonic() - t0
            samples.append(elapsed)
            assert resp.status_code == 201, resp.text
            ids.append(resp.json()["id"])
            assert elapsed < UPLOAD_BUDGET_S, (n, elapsed)

        p95 = _p95(samples)
        assert p95 < P95_LIST_BUDGET_S, (p95, max(samples))
    finally:
        with open(release, "w") as f:
            f.write("go")
    converter._queue.join()

    items = {v["id"]: v for v in client.get("/api/videos").json()["videos"]}
    assert converting_id in items
    assert items[converting_id]["status"] == "ready"
    for video_id in ids:
        assert items[video_id]["status"] in ("uploaded", "converting", "ready")
    print(f"\nNFR-37 (unit): p95 5× upload 5 МБ при конвертации = "
          f"{p95 * 1000:.1f} мс (порог < 500 мс); max = "
          f"{max(samples) * 1000:.1f} мс")
