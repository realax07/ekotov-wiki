# Образ weather-сервиса ekotov-wiki/weather (change weather-service,
# задача 3.1; design §2: копия схемы services/images/Dockerfile, python:3.12-slim,
# deps слоями, uvicorn 1 воркер :8381, healthcheck без curl, данных в образе нет).
#
# Контекст сборки — корень репозитория (compose: context: ..,
# dockerfile: services/weather/Dockerfile):
#   docker build -f services/weather/Dockerfile -t ekotov-wiki/weather:local .
#
# Тегирование: ekotov-wiki/weather:<release>; latest ЗАПРЕЩЕН (FR-72).

FROM python:3.12-slim

LABEL org.opencontainers.image.title="ekotov-wiki/weather" \
      org.opencontainers.image.description="Weather-сервис ekotov-wiki (FastAPI, uvicorn 1 воркер, :8381; БД нет — кэш-файл в томе weather-cache, провайдер Open-Meteo)"

# Слой deps: версии-пины fastapi/uvicorn синхронны backend/requirements.txt
# (обновлять синхронно с ним); httpx — асинхронный клиент провайдера
# (design §3, задача 3.2; пин — версия в venv wiki на момент пакета).
# НАМЕРЕННО НЕ ставим jinja2/bcrypt/pytest/requests/playwright — сервису
# нужны только рантайм-зависимости (без системных бинарей: ffmpeg и пр.
# не нужны — design §2, отличие от video).
RUN python -m pip install --no-cache-dir \
    fastapi==0.141.1 \
    "uvicorn[standard]==0.53.0" \
    httpx==0.28.1

# Код сервиса — пакет app (uvicorn app.main:app; импорты внутри — from app.*,
# поэтому WORKDIR /srv и каталог /srv/app — та же схема, что в монолите/search).
COPY services/weather/app/ /srv/app/

# Данных в образе НЕТ: БД приходит томом wiki-data:/data:ro (только SELECT
# sessions), кэш — томом weather-cache:/data/cache (RW — ЕДИНСТВЕННЫЙ
# RW-маунт сервиса, design §2).

# Запуск НЕ от root (uid 10001 — вне диапазона пользователей образа).
# Том weather-cache приводится к владельцу при первом старте (пустой том
# наследует владельца образа каталога /data/cache).
USER 10001

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Порт НЕ публикуется: nginx ходит на weather:8381 внутри compose-сети
# (design §1). EXPOSE — документация образа.
EXPOSE 8381

# Healthcheck через urllib — curl в python:3.12-slim отсутствует (design §2).
# /api/health не читает БД и не ходит к провайдеру (exempt middleware) —
# health 200 и на пустом томе.
# Каноничные значения интервалов/лимитов — в deploy/compose.yaml (healthcheck
# у сервиса weather); здесь те же числа, синхронизировать при изменении.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8381/api/health', timeout=5).status == 200 else 1)"]

# 1 воркер — паритет search/images/video (VPS 3.9 GB; design §2). Путь кэша —
# только из окружения (EKOTOV_WEATHER_CACHE_PATH — задает compose; дефолт
# кода /data/cache/weather.json).
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8381", "--workers", "1", "--log-level", "warning"]
