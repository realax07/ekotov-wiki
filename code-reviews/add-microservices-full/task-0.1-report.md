# Отчет: задача 0.1 — заморозка контракта поиска (ЭТАП A, add-microservices-full)

- **Делегация:** deleg_2566f48e (платформа) / deleg-751bf7418d0d4972 (flowctl)
- **Роль:** SA (системный аналитик), Флоу 1, зоны: contracts/, scripts/export_openapi_search.py
- **Статус:** завершена, рабочее дерево чисто

## Артефакты

| Файл | Коммит | Что |
|---|---|---|
| `scripts/export_openapi_search.py` | 9c63971 | Экспорт OpenAPI-схемы поиска из монолита (по образцу export_openapi.py): тестовая сессия, фильтрация до `/api/search*` + `/api/suggestions` |
| `contracts/openapi-search.json` | 9c63971 | Замороженный контракт: 4 пути / 6 операций (search GET, search/advanced POST, suggestions GET, suggestions/users GET) |
| `contracts/openapi.json` | a9e530b | Те же 4 API-пути: `deprecated: true` + аннотация «Переезд в search-сервис» |

## Верификация (факты)

1. **Детерминизм:** повторный прогон экспорта — sha256 `79704d9ded12a22d06af7ded221be14cc17e3f29a13c34ad8d95625e48cf9a1a` идентичен до/после, git-дифф пуст.
2. **Точечность диффа:** программная сверка contracts/openapi.json против HEAD — изменены только deprecated/description на 4 путях поиска; components и остальные пути бит-в-бит.
3. **strict:** `openspec validate --all --strict` → 13 passed, 0 failed.
4. **Зона:** только contracts/** и новый скрипт; export_openapi.py и backend не тронуты.
5. `/search` (HTML-страница каркаса, FR-13) корректно НЕ помечена deprecated — переезжает API, не страница.

## Отклонения от design §3

Нет. Замечания: deprecated выставлен на уровне операций (FastAPI не дает path-level флага); components в openapi-search.json оставлены для самодостаточности контракта.
