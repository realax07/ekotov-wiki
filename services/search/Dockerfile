# Образ search-сервиса ekotov-wiki/search (change add-microservices-full,
# tasks 1.2; design §1/§2/§7: python:3.12-slim, deps слоями, uvicorn 1 воркер
# :8378, healthcheck без curl, данных в образе нет — паритет services/app).
#
# Контекст сборки — корень репозитория (compose: context: ..,
# dockerfile: services/search/Dockerfile):
#   docker build -f services/search/Dockerfile -t ekotov-wiki/search:local .
#
# Тегирование: ekotov-wiki/search:<release>; latest ЗАПРЕЩЕН (FR-72).

FROM python:3.12-slim

LABEL org.opencontainers.image.title="ekotov-wiki/search" \
      org.opencontainers.image.description="Search-сервис ekotov-wiki (uvicorn, 1 воркер, :8378; БД только ro)"

# Слой deps: версии-пины синхронны backend/requirements.txt (fastapi,
# uvicorn[standard]) — обновлять синхронно с ним. НАМЕРЕННО НЕ ставим
# playwright/pytest/Pillow/python-multipart из backend/requirements.txt:
# сервису нужны только рантайм-зависимости роутеров поиска (импорты
# services/search/app/*: fastapi, starlette — транзитивно fastapi, uvicorn).
RUN python -m pip install --no-cache-dir \
    fastapi==0.141.1 \
    "uvicorn[standard]==0.53.0"

# Код сервиса — пакет app (uvicorn app.main:app; импорты внутри — from app.*,
# поэтому WORKDIR /srv и каталог /srv/app — та же схема, что в монолите).
COPY services/search/app/ /srv/app/

# Данных в образе НЕТ: БД приходит томом wiki-data:/data:ro (ro-маунт —
# файловая гарантия read-only, design §2); avatars сервису не нужны.

# Запуск НЕ от root (uid 10001 — вне диапазона пользователей образа).
USER 10001

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Порт НЕ публикуется: nginx (задача 1.3) ходит на search:8378 внутри
# compose-сети (design §1). EXPOSE — документация образа.
EXPOSE 8378

# Healthcheck через urllib — curl в python:3.12-slim отсутствует (design §1).
# /api/health не читает БД (exempt middleware) — health 200 и на пустом томе.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8378/api/health', timeout=5).status == 200 else 1)"]

# 1 воркер — FR-73 паритет (VPS 3.9 GB; design §7). Путь БД — только из
# окружения (EKOTOV_WIKI_DB_PATH, задает compose; дефолт кода /data/wiki.db).
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8378", "--workers", "1", "--log-level", "warning"]
