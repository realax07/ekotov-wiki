"""Установка статических ffmpeg/ffprobe в образ (services/video/Dockerfile,
задача 1.2 video-hosting; design §2: pinned-релиз johnvansickle, версия +
SHA256 зафиксированы в Dockerfile и передаются аргументами; checksum
проверяется ДО распаковки; недоступность источника или несовпадение
checksum = fail fast сборки). Только stdlib — curl в slim нет, apt
запрещен (без apt/CDN-замен; ОГР-масштаб Dockerfile images-семейства).

Ретраи (CI-флейк 10.2026: johnvansickle.com рвет соединения, Errno 104 /
SSL EOF): 3 попытки на источник, backoff 10/20/40 c, частичный файл
удаляется перед попыткой. Опциональный fallback-источник (BtbN/FFmpeg-
Builds, github): только если ПЕРВИЧНЫЙ источник недоступен целиком
(исчерпаны ретраи) — не при несовпадении checksum (битый файл = fail
fast, тихая подмена источника запрещена). Fallback имеет СВОЙ пин
sha256 и версию (сборка BtbN another-release-line; см. Dockerfile).

Запуск ВНУТРИ сборки:
python install_ffmpeg.py <url> <sha256> <version> [fallback_url fallback_sha256]
"""

import hashlib
import os
import re
import sys
import tarfile
import time
import urllib.request

TMP = "/tmp/ffmpeg-static.tar.xz"
DEST = "/usr/local/bin"

# Ретраи скачивания: 3 попытки, backoff 10/20/40 c; между попытками
# частичный файл удаляется, чтобы следующая попытка не докачивала битый
# кусок. Константы уровня модуля — тесты замокают их (ноль задержки) и
# urlopen (подсчет попыток).
ATTEMPTS = 3
BACKOFF_SECONDS = (10, 20, 40)

# ffmpeg/ffprobe ищутся в корне архива (johnvansickle) или в bin/
# топ-уровневого каталога (BtbN-сборка).
BIN_RE = re.compile(r"^[^/]+/(?:bin/)?(ffmpeg|ffprobe)$")


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def _fetch_once(url: str) -> None:
    with urllib.request.urlopen(url, timeout=60) as resp, open(TMP, "wb") as f:
        while True:
            block = resp.read(1 << 20)
            if not block:
                break
            f.write(block)


def download(url: str, label: str) -> None:
    """Скачивание в TMP с ретраями; HTTP-ошибка/обрыв = исключение.

    Каждая попытка пишет в свежий TMP: перед (re)попыткой частичный файл
    удаляется. SHA256 ниже ловит битый файл, но ретраи — дешевле падения.
    """
    last_exc: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        if os.path.exists(TMP):
            os.remove(TMP)  # частичный файл прошлой попытки — в мусор
        try:
            _fetch_once(url)
            print(f"downloaded from {label} on attempt {attempt}/{ATTEMPTS}")
            return
        except Exception as exc:  # noqa: BLE001 - ретрай, после 3-й fail fast
            last_exc = exc
            print(f"attempt {attempt}/{ATTEMPTS} failed: {exc}", file=sys.stderr)
            if attempt < ATTEMPTS:
                delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS)) - 1]
                print(f"retrying in {delay}s...", file=sys.stderr)
                time.sleep(delay)
    fail(f"download failed after {ATTEMPTS} attempts ({url}): {last_exc}")


def verify_sha256(want_sha: str) -> None:
    """SHA256 ДО распаковки (воспроизводимость, паритет пинам pip-слоя);
    несовпадение = fail fast (не ретраится, не подменяется fallback'ом)."""
    digest = hashlib.sha256()
    with open(TMP, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    got_sha = digest.hexdigest()
    print(f"sha256 {got_sha}")
    if got_sha != want_sha:
        fail(f"SHA256 MISMATCH: got {got_sha}, expected {want_sha}")


def extract() -> None:
    """Распаковка только ffmpeg/ffprobe (xz — модуль lzma): из корня
    архива (johnvansickle: <prefix>/ffmpeg) или из bin/ топ-уровневого
    каталога (BtbN: <prefix>/bin/ffmpeg)."""
    found: dict[str, tarfile.TarInfo] = {}
    with tarfile.open(TMP, "r:xz") as tar:
        for member in tar.getmembers():
            m = BIN_RE.match(member.name)
            if m and m.group(1) not in found:
                found[m.group(1)] = member
        if set(found) != {"ffmpeg", "ffprobe"}:
            fail(f"archive missing ffmpeg/ffprobe members (found: {sorted(found)})")
        for name in ("ffmpeg", "ffprobe"):
            member = found[name]
            member.name = name
            tar.extract(member, DEST)  # noqa: DEPRECATED - pinned-тарболл, не юзерский архив
            os.chmod(os.path.join(DEST, name), 0o755)


def main() -> None:
    if len(sys.argv) not in (4, 6):
        fail(
            "usage: install_ffmpeg.py <url> <sha256> <version>"
            " [fallback_url fallback_sha256]"
        )
    url, want_sha, version = sys.argv[1], sys.argv[2], sys.argv[3]
    sources = [(url, want_sha, "primary")]
    if len(sys.argv) == 6:
        sources.append((sys.argv[4], sys.argv[5], "fallback"))

    for src_url, src_sha, label in sources:
        try:
            download(src_url, label)
        except SystemExit:
            # Последний источник в списке — падение уходит наружу
            # (fail fast); иначе пробуем следующий.
            if label == sources[-1][2]:
                raise
            print(f"{label} source unavailable, trying fallback...", file=sys.stderr)
            continue
        verify_sha256(src_sha)  # mismatch = fail fast (SystemExit, не ретрай)
        break

    extract()
    os.remove(TMP)
    print(f"installed ffmpeg/ffprobe {version} -> {DEST}")


if __name__ == "__main__":
    main()
