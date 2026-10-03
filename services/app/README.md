# services/app — ядро (монолит, ЭТАП 1)

> Статус: ЗАГЛУШКА (перенос в ЭТАПЕ 1) | Источник: `docs/ba/architecture-services-plan.md` §1.2, §2.2 | Границы определит архитектор-сабагент.

## Назначение

Ядро системы — текущий FastAPI-монолит `backend/app/` (11 роутеров, ~27 HTTP-маршрутов + страницы Jinja2): auth, tasks, board, categories, tasks, comments, profile, users, suggestions.

## Перенос (ЭТАП 1)

Контейнеризация монолита **как есть**, без изменения кода:

```
services/app/
├── app/           # пакет (из backend/app/)
├── tests/         # api-сьют переезжает сюда (ЭТАП 1)
├── Dockerfile
└── openapi.yaml   # экспорт /openapi.json (включить схему в main.py, §3 плана)
```

Рядом — `services/frontend/` (nginx-образ: статика + reverse proxy, конфиг из `deploy/nginx-*.conf`).

## Данные и контракт

- SQLite RW через именованный том `wiki-data` (файл БД и `avatars/` остаются вне rsync-корня).
- Контракт: весь `/api/*` — OpenAPI-схема как контракт + CI-gate на дифф (план §3, вариант А).
- Все транзакционные инварианты (fast line + priority-lock и т.п.) остаются в одном процессе — потому и «монолит в контейнере», а не разбор на сервисы.

---

## Контейнеризация (tasks 1.1, change add-containerization)

Образ `ekotov-wiki/app:<release>` — `services/app/Dockerfile` (python:3.12-slim):

- deps слоями из `backend/requirements.txt` (пины сохранены — Pillow,
  python-multipart);
- uvicorn, 1 воркер, порт 8377; порты наружу НЕ публикуются (паритет
  localhost-only, FR-65);
- healthcheck `GET /api/health` через `python -c urllib` — curl в slim
  отсутствует (design §1);
- запуск НЕ от root (uid 10001); пользовательских данных (SQLite, аватары)
  в образе НЕТ — named volume `wiki-data` (FR-66);
- `mem_limit: 512m` и лимиты — compose-сторона (`deploy/`), не здесь.
