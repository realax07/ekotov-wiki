# services/frontend — nginx-образ (ЭТАП 1, change add-containerization)

> Статус: РЕАЛИЗУЕТСЯ (tasks 1.2) | Источник: `openspec/changes/add-containerization/design.md` §1–2 | Конфиг-база: `deploy/nginx-ekotov-wiki-10443.conf`.

## Назначение

Образ `ekotov-wiki/frontend:<release>` (nginx:stable-alpine):

- статика `frontend/static/` — в образе (кеш-бастинг `?v=` продолжает работать,
  design §2); templates в образ НЕ копируются — Jinja2 рендерит app;
- TLS self-signed — bind-mount `/etc/nginx/ssl/ekotov-wiki.{crt,key}` (ro), FR-74;
- `/avatars/` — named volume `wiki-data` (ro), FR-66;
- proxy `/` → `app:8377` c `resolver 127.0.0.11 valid=10s` + переменная в
  `proxy_pass` — против stale-DNS 502 при пересоздании app (design §1);
- публикуемый порт — только у nginx (`${NGINX_PORT:-10443}:10443` в compose).

## Содержимое

```
services/frontend/
├── Dockerfile
└── nginx/
    └── ekotov-wiki.conf   # база: deploy/nginx-ekotov-wiki-10443.conf
```

Композиция (compose-файлы, порты, тома, лимиты) — в `deploy/` (зона devops).

## Что здесь НЕ решается

- Сборка/публикация образов — `deploy/deploy.sh` v2 (tasks 1.6);
- паритет портов стенда — `deploy/compose.test.yaml` (8443);
- прод-конфиг хостового nginx (systemd-период) — `deploy/nginx-ekotov-wiki.conf`.
