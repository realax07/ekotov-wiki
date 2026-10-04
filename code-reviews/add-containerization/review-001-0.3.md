# Ревью задачи 0.3: экспорт OpenAPI-контракта

- **Reviewer-Delegation:** deleg_ed4b95e1
- **Change:** add-containerization (ЭТАП 1), диф 0.3 в коммите 5ccf644 (dev-p11-services)
- **Дата:** 2026-10-03

## Проверено (факты)

scripts/export_openapi.py: поднятие app на свободном порту, логин seed, GET /openapi.json -> contracts/openapi.json (25 путей, 3.1.0); идемпотентность проверена повторным прогоном — git diff пустой

## Соответствие спеке/дизайну

Источник: tasks.md 0.3, design.md, spec deploy (FR-64..FR-69). Замечаний нет.

## Вердикт: approve
