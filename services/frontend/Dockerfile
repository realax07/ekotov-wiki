# nginx-образ ekotov-wiki/frontend (change add-containerization, tasks 1.2;
# design §1–2: nginx:stable-alpine, конфиг с upstream app:8377 + resolver
# против stale-DNS, статика в образе, avatars — том ro, TLS — bind-mount ro).
#
# Контекст сборки — корень репозитория (compose: context: ..,
# dockerfile: services/frontend/Dockerfile):
#   docker build -f services/frontend/Dockerfile -t ekotov-wiki/frontend:local .
#
# Тегирование: ekotov-wiki/frontend:<release>; latest ЗАПРЕЩЕН (FR-72).

FROM nginxinc/nginx-unprivileged:stable-alpine

LABEL org.opencontainers.image.title="ekotov-wiki/frontend" \
      org.opencontainers.image.description="nginx: статика + TLS + reverse proxy на app:8377"

# Статика — В образе (кеш-бастинг ?v= работает без изменения URL, design §2);
# templates НЕ копируются — Jinja2 рендерит app-образ.
COPY frontend/static/ /srv/static/

# Конфиг образа: база deploy/nginx-ekotov-wiki-10443.conf, upstream — DNS
# compose-сети (app:8377) + resolver против stale-DNS (design §1); с задачи
# 1.3 (add-microservices-full) — маршрутизация /api/search* и
# /api/suggestions на search:8378 (X-Service, 503-деградация).
COPY services/frontend/nginx/ekotov-wiki.conf services/frontend/nginx/search-proxy.inc services/frontend/nginx/search-headers.inc /etc/nginx/conf.d/

# 10443 — внутренний порт (публикуемый задает compose: ${NGINX_PORT:-10443}:10443).
EXPOSE 10443

# Базовый образ уже non-root (uid 101, nginx); TLS-ключ читается группой nginx
# (bind-mount ro — права хоста, см. RUNBOOK). Healthcheck через wget — curl в
# alpine-образе отсутствует; интервалы — compose (deploy/).
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD ["wget", "-q", "--spider", "--no-check-certificate", "https://127.0.0.1:10443/api/health"]

# nginx.conf образа ожидает pid/tmp в /tmp (unprivileged) — задано базовым
# образом; конфиг-dump на старте не нужен (nginx -g daemon off; по умолчанию).
CMD ["nginx", "-g", "daemon off;"]
