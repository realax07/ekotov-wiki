# services/frontend — nginx-образ (ЭТАП 1, change add-containerization; задача 1.3 add-microservices-full)

> Статус: РЕАЛИЗУЕТСЯ (tasks 1.2; 1.3 add-microservices-full — маршрутизация search) | Источник: `openspec/changes/add-containerization/design.md` §1–2, `openspec/changes/add-microservices-full/design.md` §1/§4 | Конфиг-база: `deploy/nginx-ekotov-wiki-10443.conf`.

## Назначение

Образ `ekotov-wiki/frontend:<release>` (nginx:stable-alpine):

- статика `frontend/static/` — в образе (кеш-бастинг `?v=` продолжает работать,
  design §2); templates в образ НЕ копируются — Jinja2 рендерит app;
- TLS self-signed — bind-mount `/etc/nginx/ssl/ekotov-wiki.{crt,key}` (ro), FR-74;
- `/avatars/` — named volume `wiki-data` (ro), FR-66;
- proxy `/` → `app:8377` c `resolver 127.0.0.11 valid=10s` + переменная в
  `proxy_pass` — против stale-DNS 502 при пересоздании app (design §1);
- маршрутизация search-семейства (задача 1.3, design §1/§4):
  `location = /api/search`, `location ^~ /api/search/` (→ `/api/search/advanced`),
  `location = /api/suggestions`, `location ^~ /api/suggestions/` (→
  `/api/suggestions/users`) → `search:8378` — тоже через переменную + resolver
  (старт nginx без search-контейнера безопасен). На search-ответах —
  `X-Service: search` (search-headers.inc); остановленный search → управляемый
  503 с JSON-телом и `Retry-After` (`proxy_next_upstream` +
  `proxy_intercept_errors` + `error_page 502 503 504 = @search_down`,
  search-proxy.inc) — не 502 и не таймаут;
- публикуемый порт — только у nginx (`${NGINX_PORT:-10443}:10443` в compose).

## Содержимое

```
services/frontend/
├── Dockerfile
└── nginx/
    ├── ekotov-wiki.conf      # база: deploy/nginx-ekotov-wiki-10443.conf + локации search
    ├── search-proxy.inc      # proxy_pass search:8378 (переменная) + 503-деградация
    └── search-headers.inc    # X-Service: search + security-заголовки
```

Композиция (compose-файлы, порты, тома, лимиты) — в `deploy/` (зона devops).

## Что здесь НЕ решается

- Сборка/публикация образов — `deploy/deploy.sh` v2 (tasks 1.6);
- паритет портов стенда — `deploy/compose.test.yaml` (8443);
- прод-конфиг хостового nginx (systemd-период) — `deploy/nginx-ekotov-wiki.conf`.
