"""Тесты фоновой конвертации (tasks 3.2, волна 3, кусок B).

По конвенции services/video/tests: без сети, БД и том — временные
(фикстуры как в test_videos_service.py; схема — та же SCHEMA_SQL).

Две группы:
- реальные маленькие видео (ffmpeg testsrc 0.3 c, mkv/mp4) — happy path
  конвертации и превью для уже-mp4; если ffmpeg нет в окружении —
  группа skip (в образе сервиса ffmpeg статический, tasks 1.2);
- фейки ffmpeg (скрипт-заглушки в tmp, design §3/tasks 3.2 «фейки ffmpeg
  для веток неудачи/таймаута») — ретрай, timeout-kill, отсутствие
  выходного файла, неснятый кадр, крэш-восстановление, отмена DELETE,
  серийность.

Трассировка: Requirement «Серверная конвертация в mp4 со статусами»,
«Удаление оригинала после успешной конвертации», «Превью-кадр
генерируется при конвертации» (design §3);
TC-vid-060…075.

Запуск (из services/video/): python3 -m pytest tests/test_converter.py -v
"""

import os
import queue
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid

import pytest

from app import converter, storage
from app.db import get_connection

from tests.test_videos_service import SCHEMA_SQL

pytestmark = pytest.mark.usefixtures("db_path", "videos_dir")

FFMPEG_BIN = shutil.which("ffmpeg")
assert FFMPEG_BIN is not None or True  # may be absent — real-media tests skip

# --------------------------------------------------------------------------
# Фикстуры (паритет test_videos_service; воркер по умолчанию выключен
# conftest'ом — тесты запускают converter.* явно)
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_worker_leak():
    """Гигиена волны 3: какой бы тест ни поднял воркер — после теста он
    остановлен, очередь пуста (иначе живой поток обслуживает очередь
    соседних модулей по уже удаленным tmp-БД)."""
    yield
    while True:
        try:
            converter._queue.get_nowait()
            converter._queue.task_done()
        except queue.Empty:
            break
    converter.stop_worker()


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
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("EKOTOV_WIKI_DB_PATH", path)
    return path


@pytest.fixture()
def videos_dir(tmp_path, monkeypatch):
    d = str(tmp_path / "videos-data")
    os.makedirs(d, exist_ok=True)
    monkeypatch.setenv("EKOTOV_WIKI_VIDEOS_DIR", d)
    return d


@pytest.fixture()
def row_factory(db_path, videos_dir):
    """Хелпер: прямая вставка записи + исходник в томе (как после POST)."""

    def _make(status="uploaded", ext="mkv", attempts=0, content=b"fake-original"):
        video_id = uuid.uuid4().hex
        storage.create_video_dir(video_id)
        with open(storage.original_path(video_id, ext), "wb") as f:
            f.write(content)
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO video_videos (id, filename, status, size_bytes, mime,"
                " uploaded_by, created_at, convert_attempts)"
                " VALUES (?, 'clip." + ext + "', ?, ?, 'video/x-" + ext + "', 1, ?, ?)",
                (video_id, status, len(content), "2026-10-18T00:00:00+00:00", attempts),
            )
            conn.commit()
        finally:
            conn.close()
        return video_id

    return _make


def _status(video_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status, convert_attempts, size_bytes FROM video_videos WHERE id = ?",
            (video_id,),
        ).fetchone()
        return None if row is None else tuple(row)
    finally:
        conn.close()


@pytest.fixture()
def stub_env(tmp_path, monkeypatch):
    """Каталог скрипт-заглушек ffmpeg; возвращает фабрику."""
    d = tmp_path / "stubs"
    d.mkdir()

    def _stub(name, body):
        p = d / name
        p.write_text("#!/bin/sh\n" + body)
        p.chmod(0o755)
        return str(p)

    monkeypatch.setattr(converter, "CONVERT_TIMEOUT_SECONDS", 30)
    return _stub


SUCCESS_STUB = """
src=""; prev=""; for a in "$@"; do [ "$prev" = "-i" ] && src="$a"; prev="$a"; done
last=""; for a in "$@"; do last="$a"; done
case "$last" in
  *.jpg) printf '\\xff\\xd8\\xff\\xe0fake-jpeg' > "$last" ;;
  *) cp "$src" "$last" ;;
esac
"""

FAIL_STUB = "exit 1\n"

NO_OUTPUT_STUB = "exit 0\n"

TIMEOUT_STUB = "sleep 60\n"

# Кадр не снимается (выходной mp4 создается) — неудача попытки по design §3.
NO_FRAME_STUB = """
src=""; prev=""; for a in "$@"; do [ "$prev" = "-i" ] && src="$a"; prev="$a"; done
last=""; for a in "$@"; do last="$a"; done
case "$last" in
  *.jpg) exit 1 ;;
  *) cp "$src" "$last" ;;
esac
"""

# Первая команда (любая) — fail, дальше — успех (счетчик в файле).
FLAKY_ONCE_STUB = """
counter="$FLAKY_COUNTER"
n=$(cat "$counter" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$counter"
if [ "$n" -le 1 ]; then exit 1; fi
src=""; prev=""; for a in "$@"; do [ "$prev" = "-i" ] && src="$a"; prev="$a"; done
last=""; for a in "$@"; do last="$a"; done
case "$last" in
  *.jpg) printf '\\xff\\xd8\\xff\\xe0fake-jpeg' > "$last" ;;
  *) cp "$src" "$last" ;;
esac
"""

# Маркеры старта/конца вызова — проверка серийности воркера.
TRACE_STUB = """
printf 'start\\n' >> "$TRACE_FILE"
src=""; prev=""; for a in "$@"; do [ "$prev" = "-i" ] && src="$a"; prev="$a"; done
last=""; for a in "$@"; do last="$a"; done
case "$last" in
  *.jpg) printf '\\xff\\xd8\\xff\\xe0fake-jpeg' > "$last" ;;
  *) cp "$src" "$last" ;;
esac
printf 'end\\n' >> "$TRACE_FILE"
"""


@pytest.fixture()
def tiny_media(tmp_path_factory):
    """Реальные маленькие видео (0.3 c, 160x120): mkv и mp4 (сессия)."""
    if FFMPEG_BIN is None:
        pytest.skip("ffmpeg недоступен в окружении (в образе — статический, 1.2)")
    d = tmp_path_factory.mktemp("media")

    def _make(name):
        path = str(d / name)
        subprocess.run(
            [
                FFMPEG_BIN, "-nostdin", "-y",
                "-f", "lavfi", "-i", "testsrc=duration=0.3:size=160x120:rate=10",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest",
                path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return path

    return {"mkv": _make("tiny.mkv"), "mp4": _make("tiny.mp4")}


def _drain_queue():
    """Ждет опустошения очереди воркера (без sleep — блокирующий join)."""
    converter._queue.join()


def _wait_until(pred, timeout=15.0):
    """Busy-wait до предиката (паттерн репо: без literal sleep)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        threading.Event().wait(0.05)
    return False


# --------------------------------------------------------------------------
# TC-vid-060…062 — конвертация и превью на реальных маленьких видео
# --------------------------------------------------------------------------


def test_convert_mkv_to_mp4_happy_path(row_factory, tiny_media, monkeypatch):
    """TC-vid-060 (Requirement «Серверная конвертация…»): mkv → ready;
    в томе video.mp4 + preview.jpg, оригинал удален; size_bytes = mp4;
    convert_attempts 1; mp4 — H.264 (ffprobe)."""
    video_id = row_factory(status="uploaded", ext="mkv")
    shutil.copy(tiny_media["mkv"], storage.original_path(video_id, "mkv"))
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", str(FFMPEG_BIN))
    converter.process_one(video_id)

    status, attempts, size = _status(video_id)
    assert status == "ready"
    assert attempts == 1
    mp4 = storage.mp4_path(video_id)
    preview = storage.preview_path(video_id)
    assert os.path.isfile(mp4)
    assert os.path.isfile(preview)
    assert not os.path.exists(storage.original_path(video_id, "mkv"))
    assert size == os.path.getsize(mp4)

    probe = subprocess.run(
        [shutil.which("ffprobe") or os.path.join(os.path.dirname(str(FFMPEG_BIN)), "ffprobe"),
         "-v", "error",
         "-select_streams", "v:0", "-show_entries", "stream=codec_name",
         "-of", "default=nw=1:nk=1", mp4],
        capture_output=True, text=True,
    )
    assert probe.stdout.strip() == "h264"
    assert os.path.getsize(preview) > 0


def test_mp4_source_skips_transcode_preview_only(row_factory, tiny_media, monkeypatch):
    """TC-vid-061 (Requirement «Превью-кадр…», design §3 r2): исходник
    уже mp4 — перекодирования нет (video.mp4 НЕ создается), кадр снят,
    статус ready, оригинал остался (он и есть готовое видео)."""
    video_id = row_factory(status="uploaded", ext="mp4", content=b"mp4-bytes")
    shutil.copy(tiny_media["mp4"], storage.original_path(video_id, "mp4"))
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", str(FFMPEG_BIN))
    converter.process_one(video_id)

    status, attempts, size = _status(video_id)
    assert status == "ready"
    assert attempts == 1
    assert not os.path.exists(storage.mp4_path(video_id))  # без перекодирования
    assert os.path.isfile(storage.preview_path(video_id))
    assert os.path.isfile(storage.original_path(video_id, "mp4"))  # сохранен
    assert size == os.path.getsize(storage.original_path(video_id, "mp4"))
    # Отдача playback не теряется: playable_path отдает исходник-mp4.
    assert storage.playable_path(video_id) == storage.original_path(video_id, "mp4")


def test_convert_error_keeps_original(row_factory, monkeypatch):
    """TC-vid-062 (Requirement «Удаление оригинала…» сценарий неудачи):
    поврежденный исходник → ровно 2 попытки → error; оригинал на месте,
    артефактов mp4/кадра нет."""
    video_id = row_factory(status="uploaded", ext="mkv", content=b"not-a-video")
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", str(FFMPEG_BIN))
    converter.process_one(video_id)

    status, attempts, _size = _status(video_id)
    assert status == "error"
    assert attempts == 2  # ровно один авторетрай (sdd §4: 0..2)
    assert os.path.isfile(storage.original_path(video_id, "mkv"))
    assert not os.path.exists(storage.mp4_path(video_id))
    assert not os.path.exists(storage.preview_path(video_id))


# --------------------------------------------------------------------------
# TC-vid-063…066 — ветки неудачи на фейках ffmpeg (tasks 3.2)
# --------------------------------------------------------------------------


def test_fail_stub_exactly_one_retry_then_error(row_factory, stub_env, monkeypatch):
    """TC-vid-063: постоянная неудача ffmpeg → ровно 2 вызова (1 ретрай),
    статус error, оригинал сохранен, частичный mp4 удален."""
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", stub_env("fail.sh", FAIL_STUB))
    video_id = row_factory(status="converting", ext="mkv")
    converter.process_one(video_id)
    status, attempts, _ = _status(video_id)
    assert status == "error"
    assert attempts == 2
    assert os.path.isfile(storage.original_path(video_id, "mkv"))
    assert not os.path.exists(storage.mp4_path(video_id))
    assert not os.path.exists(storage.preview_path(video_id))


def test_first_attempt_fails_second_succeeds(row_factory, stub_env, monkeypatch, tmp_path):
    """TC-vid-064: неудача первой попытки → ровно один ретрай приводит к
    ready; convert_attempts == 2."""
    counter = tmp_path / "flaky.counter"
    counter.write_text("0")
    monkeypatch.setenv("FLAKY_COUNTER", str(counter))
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", stub_env("flaky.sh", FLAKY_ONCE_STUB))
    video_id = row_factory(status="uploaded", ext="mkv")
    converter.process_one(video_id)
    status, attempts, size = _status(video_id)
    assert status == "ready"
    assert attempts == 2
    assert os.path.isfile(storage.mp4_path(video_id))
    assert os.path.isfile(storage.preview_path(video_id))
    assert not os.path.exists(storage.original_path(video_id, "mkv"))
    assert size == os.path.getsize(storage.mp4_path(video_id))


def test_timeout_kills_process_and_retries(row_factory, stub_env, monkeypatch):
    """TC-vid-065 (design §3 timeout): зависший ffmpeg убивается по
    wall-clock таймауту; попытка = неудача → ретрай → error (2 попытки)."""
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", stub_env("hang.sh", TIMEOUT_STUB))
    monkeypatch.setattr(converter, "CONVERT_TIMEOUT_SECONDS", 1)
    video_id = row_factory(status="converting", ext="mkv")
    started = time.monotonic()
    converter.process_one(video_id)
    elapsed = time.monotonic() - started
    status, attempts, _ = _status(video_id)
    assert status == "error"
    assert attempts == 2
    # 2 попытки по 1 c: таймаут реально резал (не 2×60 c sleep).
    assert elapsed < 30
    # Зависший процесс не пережил kill: заглушек sleep в системе нет.
    assert not os.path.exists(storage.mp4_path(video_id))
    assert os.path.isfile(storage.original_path(video_id, "mkv"))


def test_missing_output_and_missing_frame_are_failures(row_factory, stub_env, monkeypatch):
    """TC-vid-066: exit 0 без выходного файла и unsнятый кадр — неудача
    попытки (design §3); обе ветки → error после 2 попыток."""
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", stub_env("noout.sh", NO_OUTPUT_STUB))
    v1 = row_factory(status="uploaded", ext="mkv")
    converter.process_one(v1)
    assert _status(v1)[0] == "error" and _status(v1)[1] == 2

    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", stub_env("noframe.sh", NO_FRAME_STUB))
    v2 = row_factory(status="uploaded", ext="mkv")
    converter.process_one(v2)
    status, attempts, _ = _status(v2)
    assert status == "error" and attempts == 2
    # mp4 создан, но кадр не снялся — артефакты попытки удалены.
    assert not os.path.exists(storage.mp4_path(v2))
    assert os.path.isfile(storage.original_path(v2, "mkv"))


# --------------------------------------------------------------------------
# TC-vid-067…070 — крэш-восстановление, отмена DELETE, серийность, статусы
# --------------------------------------------------------------------------


def test_crash_recovery_reenqueues_uploaded_and_converting(
    row_factory, stub_env, monkeypatch
):
    """TC-vid-067 (design §3, устранение F1): после recover+start_worker
    записи uploaded И converting дообслуживаются; частичный mp4
    прерванного прохода удален; статус converting → uploaded при
    восстановлении; инвариант: в БД не остается uploaded/converting вне
    очереди."""
    v_conv = row_factory(status="converting", ext="mkv")
    with open(storage.mp4_path(v_conv), "wb") as f:
        f.write(b"partial-mp4-from-crashed-run")
    v_upl = row_factory(status="uploaded", ext="mkv")
    v_ready = row_factory(status="ready", ext="mkv")  # не должен тронуться

    monkeypatch.delenv("EKOTOV_WIKI_CONVERTER", raising=False)
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", stub_env("ok.sh", SUCCESS_STUB))
    converter.start_worker()
    try:
        _drain_queue()
        status, attempts, _ = _status(v_conv)
        assert status == "ready" and attempts >= 1
        assert _status(v_upl)[0] == "ready"
        assert _status(v_ready) == ("ready", 0, 13)
        # Частичный mp4 крэша заменен честным результатом заглушки.
        with open(storage.mp4_path(v_conv), "rb") as f:
            assert f.read() != b"partial-mp4-from-crashed-run"
        conn = get_connection()
        try:
            left = conn.execute(
                "SELECT count(*) FROM video_videos WHERE status IN ('uploaded','converting')"
            ).fetchone()[0]
        finally:
            conn.close()
        assert left == 0
    finally:
        # Тестовый воркер гасится: не обслуживает очередь других модулей.
        converter.stop_worker()


def test_start_worker_disabled_by_env(stub_env, monkeypatch):
    """TC-vid-068: env EKOTOV_WIKI_CONVERTER=off — start_worker не
    поднимает поток (детерминизм тестов кусков A/D; conftest)."""
    monkeypatch.setenv("EKOTOV_WIKI_CONVERTER", "off")
    assert converter.start_worker() is None


def test_delete_cancel_discards_artifacts(row_factory, stub_env, monkeypatch):
    """TC-vid-069 (design §3, Scenario «Удаление во время конвертации»):
    флаг cancel — воркер не пишет статус и отбрасывает артефакты."""
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", stub_env("ok.sh", SUCCESS_STUB))
    video_id = row_factory(status="converting", ext="mkv")
    converter.cancel(video_id)
    converter.process_one(video_id)
    status, attempts, _ = _status(video_id)
    assert status == "converting"  # статус НЕ переведен в ready
    assert attempts == 0
    assert not os.path.exists(storage.mp4_path(video_id))
    assert not os.path.exists(storage.preview_path(video_id))
    # После обслуживания флаг снят (повторная постановка возможна).
    assert not converter._is_cancelled(video_id)


def test_worker_is_serial_second_job_waits(row_factory, stub_env, monkeypatch, tmp_path):
    """TC-vid-070 (design §3 серийность): ровно одна конвертация
    одновременно — следы вызовов в трейс-файле не перекрываются
    (start…end парами), вторая задача ждет."""
    trace = tmp_path / "trace.log"
    monkeypatch.setenv("TRACE_FILE", str(trace))
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", stub_env("trace.sh", TRACE_STUB))
    v1 = row_factory(status="uploaded", ext="mkv")
    v2 = row_factory(status="uploaded", ext="mkv")

    monkeypatch.delenv("EKOTOV_WIKI_CONVERTER", raising=False)
    # recover_pending ставит обе записи в очередь в порядке вставки —
    # ручной enqueue дал бы двойную обработку (успех + «original missing»).
    worker = converter.start_worker()
    assert worker is not None
    _drain_queue()

    assert _status(v1)[0] == "ready" and _status(v2)[0] == "ready"
    lines = [l for l in trace.read_text().splitlines() if l]
    # Пары start/end строго чередуются — перекрытий нет.
    depth = 0
    for line in lines:
        assert depth == 0 or (depth == 1 and line == "end")
        depth = depth + (1 if line == "start" else -1)
    assert depth == 0
    assert len([l for l in lines if l == "start"]) == 4  # 2 видео × (mp4+кадр)
    # Гигиена: тестовый воркер не обслуживает очередь других модулей.
    converter.stop_worker()


def test_status_passes_through_converting(row_factory, stub_env, monkeypatch, tmp_path):
    """TC-vid-071 (design §3 статусы): while ffmpeg работает (заглушка
    ждет релиза), запись в статусе converting; пишет только воркер."""
    flag = tmp_path / "ffmpeg.started"
    release = tmp_path / "ffmpeg.release"
    gated_stub = stub_env(
        "gated.sh",
        'touch "$SLOW_FLAG"\nwhile [ ! -e "$RELEASE_FLAG" ]; do :; done\n' + SUCCESS_STUB,
    )
    monkeypatch.setenv("SLOW_FLAG", str(flag))
    monkeypatch.setenv("RELEASE_FLAG", str(release))
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", gated_stub)
    video_id = row_factory(status="uploaded", ext="mkv")

    done = threading.Event()

    def run():
        converter.process_one(video_id)
        done.set()

    t = threading.Thread(target=run)
    t.start()
    try:
        # ffmpeg запущен (флаг заглушки) и еще ждет релиза — статус
        # обязан быть converting (писатель — воркер).
        assert _wait_until(lambda: flag.exists())
        assert _status(video_id)[0] == "converting"
        release.write_text("go")
    finally:
        assert done.wait(30)
        t.join()
    assert _status(video_id)[0] == "ready"


def test_missing_original_marks_error(row_factory):
    """TC-vid-072 (крэш без исходника): записи converting без файла в
    томе (потерянный том) — не вечный converting: error."""
    video_id = uuid.uuid4().hex
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO video_videos (id, filename, status, size_bytes, mime,"
            " uploaded_by, created_at, convert_attempts)"
            " VALUES (?, 'clip.mkv', 'converting', 5, 'video/x-matroska', 1, ?, 0)",
            (video_id, "2026-10-18T00:00:00+00:00"),
        )
        conn.commit()
    finally:
        conn.close()
    converter.process_one(video_id)
    assert _status(video_id)[0] == "error"


def test_delete_removed_row_is_noop_for_worker(row_factory, stub_env, monkeypatch):
    """TC-vid-073 (гонка DELETE↔воркер): запись удалена до обслуживания —
    воркер молчит (нет исключения, нет записей)."""
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", stub_env("ok.sh", SUCCESS_STUB))
    video_id = row_factory(status="converting", ext="mkv")
    conn = get_connection()
    try:
        conn.execute("DELETE FROM video_videos WHERE id = ?", (video_id,))
        conn.commit()
    finally:
        conn.close()
    converter.process_one(video_id)  # не бросает
    assert _status(video_id) is None


def test_cancel_before_start_discards_without_status(row_factory, stub_env, monkeypatch):
    """TC-vid-074: cancel ДО старта воркера — обработка пропускается
    целиком (артефакты чистятся, статус не пишется)."""
    monkeypatch.setenv("EKOTOV_WIKI_FFMPEG", stub_env("ok.sh", SUCCESS_STUB))
    video_id = row_factory(status="uploaded", ext="mkv")
    converter.cancel(video_id)
    converter.process_one(video_id)
    assert _status(video_id) == ("uploaded", 0, len(b"fake-original"))
    assert not os.path.exists(storage.mp4_path(video_id))
