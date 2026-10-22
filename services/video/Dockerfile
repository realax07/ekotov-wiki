# Образ video-сервиса ekotov-wiki/video (change video-hosting, задача 1.2;
# design §2: паритет services/images/Dockerfile — python:3.12-slim, deps
# слоями, uvicorn 1 воркер :8380, healthcheck без curl, данных в образе
# нет) с ДВУМЯ отличиями:
#   1. ffmpeg/ffprobe — СТАТИЧЕСКИЕ бинари в образе, НЕ apt (ограничение
#      ТЗ + дизайн §2/§9): pinned-релиз johnvansickle, версия и SHA256
#      зафиксированы здесь (воспроизводимость, паритет пинам pip-слоя),
#      checksum проверяется в RUN; внешний источник недоступен / checksum
#      не сошелся → сборка ЛОМАЕТСЯ (fail fast, тихой подмены на apt нет).
#   2. Конвертация — кусок B (tasks 3.1): бинари уже в образе, воркер
#      появится волной 3.
#
# Контекст сборки — корень репозитория (compose: context: ..,
# dockerfile: services/video/Dockerfile):
#   docker build -f services/video/Dockerfile -t ekotov-wiki/video:local .
#
# Тегирование: ekotov-wiki/video:<release>; latest ЗАПРЕЩЕН (FR-72).

FROM python:3.12-slim

LABEL org.opencontainers.image.title="ekotov-wiki/video" \
      org.opencontainers.image.description="Video-сервис ekotov-wiki (FastAPI, uvicorn 1 воркер, :8380; RW-профиль video_videos + том videos-data; статические ffmpeg/ffprobe)"

# --- Слой deps: версии-пины синхронны services/images/Dockerfile и
# backend/requirements.txt (fastapi, uvicorn[standard], python-multipart),
# обновлять синхронно. НАМЕРЕННО НЕ ставим Pillow/jinja2/bcrypt/pytest/
# requests/playwright: сервису нужны только рантайм-зависимости роутеров
# видео (импорты services/video/app/*: fastapi + multipart-парсинг
# загрузки; Pillow не нужен — превью-кадр снимает ffmpeg).
RUN python -m pip install --no-cache-dir \
    fastapi==0.141.1 \
    "uvicorn[standard]==0.53.0" \
    python-multipart==0.0.32

# --- Статические ffmpeg/ffprobe (design §2): pinned-релиз, «версия +
# SHA256» зафиксированы здесь, checksum сверяется ДО распаковки
# (install_ffmpeg.py — stdlib: в slim НЕТ curl и wget — проверено
# `command -v` в python:3.12-slim, apt запрещен; поэтому curl-флаги
# --retry/--retry-all-errors недоступны). Ретраи на двух уровнях:
#   1) install_ffmpeg.py — 3 попытки с backoff 10/20/40 c и чисткой
#      частичного файла (обрыв johnvansickle.com, Errno 104 в CI);
#   2) здесь — shell-цикл 5 попыток x 10 c (семантика
#      `curl --retry 5 --retry-delay 10 --retry-all-errors -fSL`).
# Fail fast сохранен: исчерпание ретраев или несовпадение checksum
# ломают сборку, тихой подмены источника нет.
# PRIMARY (с 2026-10-21): датированный иммутабельный релиз BtbN
# autobuild-2026-10-19-13-06 (n8.1.3-18, работает в проде с p12-rich-1).
# johnvansickle 7.0.2 (primary до 2026-10-21) ПОМЕНЯЛ содержимое тарбола
# без смены URL — пин abda8d77 больше не совпадает; оставлен fallback.
# FALLBACK (10.2026, CI-флейк Errno 104): johnvansickle.com недоступен из CI
# надолго → вторым источником отдается статическая сборка BtbN/FFmpeg-Builds
# (github, linux64-gpl; ffmpeg+ffprobe в bin/ топ-каталога — extract в
# install_ffmpeg.py понимает обе раскладки). Fallback включается ТОЛЬКО если
# первичный источник недоступен целиком (исчерпаны все ретраи); несовпадение
# checksum fallback НЕ маскирует (fail fast). Пины fallback: n8.1-сборка
# (7.0.2 у BtbN нет), sha256 снят с иммутабельного датированного релиза (пины latest
# дрейфовали трижды за сутки — 6f8133b2 прожил часы; решение 2026-10-20:
# датированный autobuild-релиз, ассеты которого НЕ перекатываются).
# Пины: URL+sha256 в RUNBOOK и здесь меняются ТОЛЬКО сознательной сменой
# релиза (новый sha снимается с файла вручную).
COPY services/video/install_ffmpeg.py /tmp/install_ffmpeg.py
RUN set -eux; \
    FFMPEG_VERSION="7.0.2"; \
    FFMPEG_SHA256="cc546852e535193e6d30a1f18cb90daa84e8ff320ceac6c6f5b514a1fba67079"; \
    FFMPEG_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-10-19-13-06/ffmpeg-n8.1.3-18-g46d899d7a0-linux64-gpl-8.1.tar.xz"; \
    FFMPEG_FALLBACK_SHA256="abda8d77ce8309141f83ab8edf0596834087c52467f6badf376a6a2a4c87cf67"; \
    FFMPEG_FALLBACK_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-7.0.2-amd64-static.tar.xz"; \
    attempt=1; max_attempts=5; \
    until python /tmp/install_ffmpeg.py "$FFMPEG_URL" "$FFMPEG_SHA256" "$FFMPEG_VERSION" "$FFMPEG_FALLBACK_URL" "$FFMPEG_FALLBACK_SHA256"; do \
        if [ "$attempt" -ge "$max_attempts" ]; then \
            echo "FAIL: ffmpeg download failed after ${max_attempts} shell-level attempts" >&2; \
            exit 1; \
        fi; \
        attempt=$((attempt + 1)); \
        echo "shell-level retry ${attempt}/${max_attempts} in 10s..." >&2; \
        sleep 10; \
    done; \
    rm -f /tmp/install_ffmpeg.py; \
    /usr/local/bin/ffmpeg -version | head -1

# Код сервиса — пакет app (uvicorn app.main:app; импорты внутри — from app.*,
# поэтому WORKDIR /srv и каталог /srv/app — та же схема, что в монолите/search/images).
COPY services/video/app/ /srv/app/

# Данных в образе НЕТ: БД приходит томом wiki-data:/data:rw (таблица
# video_videos + SELECT users), файлы видео — томом videos-data:/data/videos
# (RW; env задает compose, дефолты кода /data/wiki.db, /data/videos).

# Запуск НЕ от root (uid 10001 — вне диапазона пользователей образа).
# Пишет в named volumes — владелец томов приводится deploy-скриптом/при
# первом старте (том videos-data новый, пустой).
USER 10001

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Порт НЕ публикуется: nginx (задача 1.4) ходит на video:8380 внутри
# compose-сети (design §1). EXPOSE — документация образа.
EXPOSE 8380

# Healthcheck через urllib — curl в python:3.12-slim отсутствует (design §2).
# /api/health не читает БД (exempt middleware) — health 200 и на пустом томе.
# Каноничные значения интервалов/лимитов — в deploy/compose.yaml (healthcheck
# у сервиса video); здесь те же числа, синхронизировать при изменении.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8380/api/health', timeout=5).status == 200 else 1)"]

# 1 воркер — паритет images/search (VPS 3.9 GB; design §2/§10).
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8380", "--workers", "1", "--log-level", "warning"]
