# services/search — сервис поиска

> Статус: **в работе, ЭТАП B** (задача 1.1 пакета `add-microservices-full`; контракт заморожен в ЭТАПЕ A — задача 0.1) | Источники: `docs/ba/architecture-services-plan.md` §1.2, design пакета §2.

## Назначение

Выделение поискового домена из монолита: `backend/app/search.py` + `backend/app/suggestions.py` (роутеры переносятся как есть) — `/api/search`, `/api/search/advanced`, `/api/suggestions`, `/api/suggestions/users`.

## Запуск (план)

- Порт: **8378**, uvicorn 1 воркер (задача 1.2 — Dockerfile).
- Healthcheck: `/api/health`.
- OpenAPI-схема: `openapi_url` включен, сессионный запрет схемы без сессии — паттерн ядра.

## Профиль данных

SQLite **только RO**: тот же том данных, mount `ro` (том `wiki-data:/data:ro`). Сервис не мигрирует схему и не пишет в общую БД — инварианты монолита не нарушаются (plan §1.2, безопасные профили данных, НЕ механический разрез с общим RW SQLite).

## Контракт

Заморожен в `contracts/openapi-search.json` (задача 0.1, коммит 9c63971); `openapi.yaml` здесь — указатель на него. Ровно пути: `/api/search`, `/api/search/advanced`, `/api/suggestions`, `/api/suggestions/users`. В `contracts/openapi.json` монолита маршруты помечены `deprecated: true` до переключения nginx (задача 1.3).

## Структура

```
services/search/
├── app/          # код сервиса (задача 1.1: main, row_schema, db-слой)
├── tests/        # юнит/контрактные тесты сервиса
├── openapi.yaml  # указатель на contracts/openapi-search.json
└── README.md
```

## Статус работ

- 0.1 [x] контракт заморожен (`contracts/openapi-search.json`).
- 0.2 [x] каркас каталога (этот каталог).
- 1.1 [ ] перенос кода роутеров + мини-main (порт 8378) + db-слой.
- 1.2 [ ] Dockerfile + compose.
- 1.3 [ ] nginx-маршрутизация `/api/search*`, `/api/suggestions` → search:8378.

## Историческая оценка (план P11, до решения о переходе)

**M**: код изолирован, но общая БД → границы без транзакционности (компенсируется read-only профилем).
