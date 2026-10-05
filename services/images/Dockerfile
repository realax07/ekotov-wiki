# Образ images-сервиса ekotov-wiki/images (change add-gallery-service,
# задачи 1.2/1.3; design §3/§4: паритет services/search/Dockerfile —
# python:3.12-slim, deps слоями, uvicorn 1 воркер :8379, healthcheck без
# curl, данных в образе нет).
#
# Контекст сборки — корень репозитория (compose: context: ..,
# dockerfile: services/images/Dockerfile):
#   docker build -f services/images/Dockerfile -t ekotov-wiki/images:local .
#
# Тегирование: ekotov-wiki/images:<release>; latest ЗАПРЕЩЕН (FR-72).

FROM python:3.12-slim

LABEL org.opencontainers.image.title="ekotov-wiki/images" \
      org.opencontainers.image.description="Images-сервис галереи ekotov-wiki (FastAPI, uvicorn 1 воркер, :8379; RW-профиль таблиц gallery + том изображений)"

# Слой deps: версии-пины синхронны backend/requirements.txt (fastapi,
# uvicorn[standard], Pillow, python-multipart — эскалация E1 из REPORT-1.2),
# обновлять синхронно с ним. НАМЕРЕННО НЕ ставим jinja2/bcrypt/pytest/
# requests/playwright из backend/requirements.txt: сервису нужны только
# рантайм-зависимости роутеров изображений (импорты services/images/app/*:
# fastapi + multipart-парсинг загрузки + Pillow превью).
RUN python -m pip install --no-cache-dir \
    fastapi==0.141.1 \
    "uvicorn[standard]==0.53.0" \
    Pillow==12.3.0 \
    python-multipart==0.0.32

# Код сервиса — пакет app (uvicorn app.main:app; импорты внутри — from app.*,
# поэтому WORKDIR /srv и каталог /srv/app — та же схема, что в монолите/search).
COPY services/images/app/ /srv/app/

# Данных в образе НЕТ: БД приходит томом wiki-data:/data:rw (таблицы gallery +
# SELECT users), файлы изображений — томом images-data:/data/images (RW).

# Запуск НЕ от root (uid 10001 — вне диапазона пользователей образа).
# Пишет в named volumes — владелец томов приводится deploy-скриптом/при
# первом старте (том images-data новый, пустой).
USER 10001

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Порт НЕ публикуется: nginx (задача 1.4) ходит на images:8379 внутри
# compose-сети (design §1). EXPOSE — документация образа.
EXPOSE 8379

# Healthcheck через urllib — curl в python:3.12-slim отсутствует (design §3).
# /api/health не читает БД (exempt middleware) — health 200 и на пустом томе.
# Каноничные значения интервалов/лимитов — в deploy/compose.yaml (healthcheck
# у сервиса images); здесь те же числа, синхронизировать при изменении.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8379/api/health', timeout=5).status == 200 else 1)"]

# 1 воркер — паритет search/app (VPS 3.9 GB; design §3/§7). Пути БД и тома —
# только из окружения (EKOTOV_WIKI_DB_PATH, EKOTOV_WIKI_IMAGES_DIR — задает
# compose; дефолты кода /data/wiki.db, /data/images).
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8379", "--workers", "1", "--log-level", "warning"]
