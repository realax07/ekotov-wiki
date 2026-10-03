# Ревью задачи 1.2: Dockerfile frontend-образа

- **Change:** add-containerization (ЭТАП 1), диф 1.2 в коммите 5ccf644 (dev-p11-services)
- **Дата:** 2026-10-03

## Проверено (факты)

services/frontend/Dockerfile + nginx/ekotov-wiki.conf: nginx-unprivileged stable-alpine, upstream app:8377 через переменную + resolver 127.0.0.11 valid=10s против stale-DNS 502 (закрытие review-001 M-4), статика в образе, TLS bind-mount ro; security-заголовки паритет прод (NFR-7)

## Соответствие спеке/дизайну

Источник: tasks.md 1.2, design.md, spec deploy (FR-64..FR-69). Замечаний нет.

## Вердикт: approve
