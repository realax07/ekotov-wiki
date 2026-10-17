"""Установка статических ffmpeg/ffprobe в образ (services/video/Dockerfile,
задача 1.2 video-hosting; design §2: pinned-релиз johnvansickle, версия +
SHA256 зафиксированы в Dockerfile и передаются аргументами; checksum
проверяется ДО распаковки; недоступность источника или несовпадение
checksum = fail fast сборки). Только stdlib — curl в slim нет, apt
запрещен (без apt/CDN-замен; ОГР-масштаб Dockerfile images-семейства).

Запуск ВНУТРИ сборки: python install_ffmpeg.py <url> <sha256> <version>
"""

import hashlib
import os
import sys
import tarfile
import urllib.request

TMP = "/tmp/ffmpeg-static.tar.xz"
DEST = "/usr/local/bin"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if len(sys.argv) != 4:
        fail("usage: install_ffmpeg.py <url> <sha256> <version>")
    url, want_sha, version = sys.argv[1], sys.argv[2], sys.argv[3]

    # Скачивание (HTTP-ошибка urllib = исключение = падение сборки).
    try:
        urllib.request.urlretrieve(url, TMP)
    except Exception as exc:  # noqa: BLE001 - fail fast сборки
        fail(f"download failed ({url}): {exc}")

    # SHA256 ДО распаковки (воспроизводимость, паритет пинам pip-слоя).
    digest = hashlib.sha256()
    with open(TMP, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    got_sha = digest.hexdigest()
    print(f"sha256 {got_sha}")
    if got_sha != want_sha:
        fail(f"SHA256 MISMATCH: got {got_sha}, expected {want_sha}")

    # Распаковка только ffmpeg/ffprobe из корня архива (xz — модуль lzma).
    prefix = f"ffmpeg-{version}-amd64-static/"
    with tarfile.open(TMP, "r:xz") as tar:
        for name in ("ffmpeg", "ffprobe"):
            member = tar.getmember(prefix + name)
            member.name = name
            tar.extract(member, DEST)
            os.chmod(os.path.join(DEST, name), 0o755)
    os.remove(TMP)
    print(f"installed ffmpeg/ffprobe {version} -> {DEST}")


if __name__ == "__main__":
    main()
