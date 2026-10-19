"""Тесты ретраев скачивания в install_ffmpeg.py (CI-флейк: johnvansickle.com
рвет соединение, Errno 104 → сборка video падала 3× подряд).

Проверяется (задача «ретраи скачивания ffmpeg»):
- невалидный/недоступный URL → ровно ATTEMPTS попыток → fail fast (exit 1);
- backoff 10/20/40 c между попытками;
- частичный файл прошлой попытки удаляется ПЕРЕД следующей;
- успех на N-й попытке не требует третьей;
- SHA256-mismatch по-прежнему fail fast (не ретраится).
"""

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

# install_ffmpeg.py лежит рядом с tests/ (корень сервиса), не в пакете.
_SPEC = importlib.util.spec_from_file_location(
    "install_ffmpeg", Path(__file__).resolve().parent.parent / "install_ffmpeg.py"
)
assert _SPEC is not None and _SPEC.loader is not None  # статический импорт
inst = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(inst)


class _Resp:
    """Минимальный контекст-менеджер-ответ (urlopen-совместимый)."""

    def __init__(self, data: bytes = b""):
        self._data = data

    def read(self, n):
        out, self._data = self._data, b""
        return out

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture()
def tmp_target(tmp_path, monkeypatch):
    """TMP модуля переносим в tmp-каталог теста (не трогаем системный /tmp)."""
    monkeypatch.setattr(inst, "TMP", str(tmp_path / "ffmpeg-static.tar.xz"))


def test_invalid_url_three_attempts_then_fail(tmp_target, monkeypatch, capsys):
    """Невалидный URL → ровно 3 попытки (backoff 10/20) → exit 1."""
    calls = []

    def always_fails(url, timeout=None):
        calls.append(url)
        raise OSError("Errno 104 Connection reset by peer")

    monkeypatch.setattr(inst.urllib.request, "urlopen", always_fails)
    monkeypatch.setattr(inst.time, "sleep", lambda s: calls.append(f"sleep:{s}"))
    monkeypatch.setattr(
        sys, "argv", ["install_ffmpeg.py", "http://127.0.0.1:1/x.tar.xz", "0" * 64, "7.0.2"]
    )
    with pytest.raises(SystemExit) as ei:
        inst.main()
    assert ei.value.code == 1
    assert inst.ATTEMPTS == 3
    assert [c for c in calls if not str(c).startswith("sleep")] == [
        "http://127.0.0.1:1/x.tar.xz"
    ] * 3  # urlopen — ровно 3 раза
    assert [c for c in calls if str(c).startswith("sleep")] == ["sleep:10", "sleep:20"]
    assert "download failed after 3 attempts" in capsys.readouterr().err


def test_real_unreachable_url_fails_after_three_attempts(tmp_target, monkeypatch):
    """Реальный недоступный URL (порт закрыт, refus мгновенный): 3 попытки,
    потом fail. Без мока urlopen; подменен только sleep (иначе 70 c)."""
    monkeypatch.setattr(inst.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        sys, "argv", ["install_ffmpeg.py", "http://127.0.0.1:9/x.tar.xz", "0" * 64, "7.0.2"]
    )
    with pytest.raises(SystemExit) as ei:
        inst.main()
    assert ei.value.code == 1
    assert not Path(inst.TMP).exists()


def test_partial_file_removed_before_retry(tmp_path, monkeypatch):
    """Частичный файл от сорванной попытки удален перед следующей."""
    monkeypatch.setattr(inst, "TMP", str(tmp_path / "ffmpeg-static.tar.xz"))
    partial_seen = []
    attempts = {"n": 0}

    def first_writes_partial_then_fails(url, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            Path(inst.TMP).write_bytes(b"partial-junk")
            raise OSError("Errno 104 Connection reset by peer")
        partial_seen.append(Path(inst.TMP).exists())
        raise OSError("stop after check")

    monkeypatch.setattr(inst.urllib.request, "urlopen", first_writes_partial_then_fails)
    monkeypatch.setattr(inst.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        sys, "argv", ["install_ffmpeg.py", "http://127.0.0.1:1/x.tar.xz", "0" * 64, "7.0.2"]
    )
    with pytest.raises(SystemExit) as ei:
        inst.main()
    assert ei.value.code == 1
    assert partial_seen == [False, False]  # на 2-й и 3-й попытке частичного файла нет


def test_success_on_second_attempt(tmp_target, monkeypatch):
    """Обрыв на 1-й попытке → успех на 2-й: urlopen вызван 2 раза,
    backoff 10 c, полный файл записан в TMP."""
    payload = b"tar-bytes"
    good_sha = hashlib.sha256(payload).hexdigest()
    calls = []
    attempts = {"n": 0}

    def flaky_urlopen(url, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise OSError("Errno 104 Connection reset by peer")
        return _Resp(payload)

    monkeypatch.setattr(inst.urllib.request, "urlopen", flaky_urlopen)
    monkeypatch.setattr(inst.time, "sleep", lambda s: calls.append(f"sleep:{s}"))
    monkeypatch.setattr(
        sys, "argv", ["install_ffmpeg.py", "http://127.0.0.1:1/x.tar.xz", good_sha, "7.0.2"]
    )
    # download пройдет (2-я попытка), упадет распаковка не-tar.xz —
    # исключение tarfile, НЕ SystemExit; число попыток уже зафиксировано.
    with pytest.raises(Exception) as ei:  # noqa: PT011 - tarfile.ReadError
        inst.main()
    assert not isinstance(ei.value, SystemExit)
    assert attempts["n"] == 2
    assert calls == ["sleep:10"]
    assert Path(inst.TMP).read_bytes() == payload


def test_sha_mismatch_still_fails_fast(tmp_target, monkeypatch, capsys):
    """Битый/чужой файл (sha не сошелся) → exit 1, без ретраев скачивания."""
    calls = []
    monkeypatch.setattr(inst.urllib.request, "urlopen", lambda url, timeout=None: _Resp(b"x"))
    monkeypatch.setattr(inst.time, "sleep", lambda s: calls.append(s))
    monkeypatch.setattr(
        sys, "argv", ["install_ffmpeg.py", "http://127.0.0.1:1/x.tar.xz", "f" * 64, "7.0.2"]
    )
    with pytest.raises(SystemExit) as ei:
        inst.main()
    assert ei.value.code == 1
    assert calls == []  # ни одной задержки — sha-проверка не ретраится
    assert "SHA256 MISMATCH" in capsys.readouterr().err


def test_fallback_used_after_primary_exhausted(tmp_target, monkeypatch, capsys):
    """Первичный источник недоступен (3 попытки) → fallback скачивает."""
    import hashlib

    payload = b"tar-bytes-fallback"
    fb_sha = hashlib.sha256(payload).hexdigest()
    attempts = []

    def primary_dead_fallback_ok(url, timeout=None):
        attempts.append(url)
        if "johnvansickle" in url:
            raise OSError("Errno 104 Connection reset by peer")
        return _Resp(payload)

    monkeypatch.setattr(inst.urllib.request, "urlopen", primary_dead_fallback_ok)
    monkeypatch.setattr(inst.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "install_ffmpeg.py",
            "http://johnvansickle.invalid/x.tar.xz",
            "0" * 64,
            "7.0.2",
            "http://github.invalid/btbn.tar.xz",
            fb_sha,
        ],
    )
    # Скачивание через fallback пройдет, упадет распаковка (не tar.xz) —
    # не SystemExit; главное: primary 3 попытки, fallback 1.
    with pytest.raises(Exception) as ei:  # noqa: PT011 - tarfile.ReadError
        inst.main()
    assert not isinstance(ei.value, SystemExit)
    assert attempts.count("http://johnvansickle.invalid/x.tar.xz") == inst.ATTEMPTS
    assert attempts.count("http://github.invalid/btbn.tar.xz") == 1
    assert "fallback" in capsys.readouterr().err


def test_both_sources_exhausted_fails(tmp_target, monkeypatch):
    """Оба источника недоступны → exit 1 после ATTEMPTS x 2 попыток."""
    attempts = []

    def always_dead(url, timeout=None):
        attempts.append(url)
        raise OSError("Errno 104 Connection reset by peer")

    monkeypatch.setattr(inst.urllib.request, "urlopen", always_dead)
    monkeypatch.setattr(inst.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "install_ffmpeg.py",
            "http://127.0.0.1:1/x.tar.xz",
            "0" * 64,
            "7.0.2",
            "http://127.0.0.1:2/x.tar.xz",
            "0" * 64,
        ],
    )
    with pytest.raises(SystemExit) as ei:
        inst.main()
    assert ei.value.code == 1
    assert len(attempts) == 2 * inst.ATTEMPTS


def test_bin_regex_understands_both_layouts():
    """Распаковка: корень архива (johnvansickle) и bin/ (BtbN); вложенные
    или не-топовые пути не матчатся."""
    assert inst.BIN_RE.match("ffmpeg-7.0.2-amd64-static/ffmpeg").group(1) == "ffmpeg"
    assert inst.BIN_RE.match("ffmpeg-n8.1-linux64-gpl-8.1/bin/ffprobe").group(1) == "ffprobe"
    assert inst.BIN_RE.match("a/b/ffmpeg") is None
    assert inst.BIN_RE.match("ffmpeg-7.0.2-amd64-static/ffmpeg.exe") is None

