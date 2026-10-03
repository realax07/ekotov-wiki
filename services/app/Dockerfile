# Образ монолита ekotov-wiki/app (change add-containerization, tasks 1.1;
# design §2: python:3.12-slim, deps слоями, uvicorn 1 воркер, healthcheck
# без curl, данных в образе нет — FR-64/66/73).
#
# Контекст сборки — корень репозитория (compose: context: ..,
# dockerfile: services/app/Dockerfile):
#   docker build -f services/app/Dockerfile -t ekotov-wiki/app:local .
#
# Тегирование: ekotov-wiki/app:<release>; latest ЗАПРЕЩЕН (FR-72).

FROM python:3.12-slim

LABEL org.opencontainers.image.title="ekotov-wiki/app" \
      org.opencontainers.image.description="FastAPI-монолит ekotov-wiki (uvicorn, 1 воркер, :8377)"

# Слой deps: requirements.txt копируется отдельно — кеш слоя не сбрасывается
# при изменениях кода (пины сохранены: Pillow, python-multipart — design §2).
COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Код монолита — как есть (контейнеризация без изменения логики, план §1.2).
COPY backend/app/ /srv/app/

# Шаблоны Jinja2: app ищет их относительно backend/app (pages.py:
# parents[2]/frontend/templates = <корень>/frontend/templates). Корень кода
# в образе — /srv, поэтому frontend/ кладем рядом с app/ (/srv/frontend).
COPY frontend/templates/ /srv/frontend/templates/

# Запуск НЕ от root (uid 10001 — вне диапазона пользователей образа).
USER 10001

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Порты наружу НЕ публикуем (только EXCELLENT-dokументация для docker build):
# nginx ходит на app:8377 внутри compose-сети (design §1).
EXPOSE 8377

# Healthcheck через urllib — curl в python:3.12-slim отсутствует (design §1).
# Интервал/лимиты — compose (healthcheck у сервиса, deploy/).
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8377/api/health', timeout=5).status == 200 else 1)"]

# 1 воркер — FR-73 (VPS 3.9 GB; резерв хосту >= 2 GB). SECRET_KEY, DB_PATH,
# AVATARS_DIR — только из окружения (app/config.py: дефолтов нет, NFR-5).
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8377", "--workers", "1", "--log-level", "warning"]
