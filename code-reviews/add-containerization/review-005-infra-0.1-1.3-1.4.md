# Ревью задач 0.1 / 1.3 / 1.4 (инфраструктура: Docker, compose прод/стенд)

- **Change:** add-containerization; 0.1 — окружение VPS; 1.3 — deploy/compose.yaml (PR #16); 1.4 — deploy/compose.test.yaml (PR #16)
- **Дата:** 2026-10-03

## Проверено (факты)

- **0.1:** docker 29.8.2 + compose plugin v5.6.0 на VPS (`docker compose version`); версии зафиксированы в RUNBOOK; `openclaw` в группе docker.
- **1.3 (compose.yaml):** именованный том `wiki-data` (БД + avatars); TLS bind-mount ro с хоста; SECRET_KEY только из deploy/.env (NFR-5, gitignore подтвержден); mem_limit nginx 64m / app 512m (FR-73); logging json-file 10m×3; публикует только nginx, `${NGINX_PORT:-10443}:10443` (design §6); restart unless-stopped; healthcheck urllib без curl; depends_on service_healthy. Боевой прогон: переключение 2.4, стек healthy.
- **1.4 (compose.test.yaml):** tmp-том БД (данные исчезают при down), порт 8443, TEST_SECRET_KEY-дефолт; использован всеми прогонами: репетиции миграций 2.1 (три конфигурации), регресс e2e 2.2 (8 passed), CI e2e-job (green на PR #18).

Нюанс маунта аватаров (том:/data/avatars:ro) найден в бою (2.3) и закрыт 7065a71 — файл фикса в этом пакете, а не в 1.3-диффе PR #16; поведение после фикса проверено загрузкой и отдачей аватаров (200).

## Соответствие спеке/дизайну

tasks 0.1/1.3/1.4, design §1/§3/§6, FR-64…67/73/74, NFR-10/11 — соответствуют.

## Вердикт: approve
