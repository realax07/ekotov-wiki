# BUG-002 — POST /api/tasks: явный priority=null при is_fast=true не отклоняется (422), создается задача с priority=high (201)

- **Кейс:** TC-fast2-004 (CHK-130), approved/add-r2-categories-settings
- **Приоритет:** Must | **Окружение:** локальный стенд `http://127.0.0.1:8099`, ветка feature/r2-qa-api-tests (код = origin/main, 64cbf13), uvicorn + SQLite /tmp/r2qa_app.db
- **Создан:** qa_automation_agent, 2026-09-22 (автоматизация TC-fast2-001…012)

## Ожидание (кейс, sdd r2 §3.2)

`POST /api/tasks` с телом `{"title":"QAT-фаст-null","is_fast":true,"priority":null}`
→ HTTP **422**, тело `{"error": "validation", "details": {"priority": "fast requires high"}}`;
задача не создается. Случай «явный null» выписан в кейсе отдельно от «отсутствия поля»
(CHK-130 vs CHK-134, эскалация а): null = явное значение ≠ high → отклонение.

## Факт

→ HTTP **201**, задача создана с `priority="high"`, `is_fast=true`:

```json
{"id":1,"title":"QAT-probe-fn","priority":"high","is_fast":true,"status":"todo",...}
```

Воспроизводится 2/2 прогонов. Остальные негативы priority-lock работают:
`priority:"low"` → 422 дословно; `PATCH fast → priority:"medium"` → 422 дословно.

## Анализ (корень)

`backend/app/tasks.py`, `create_task` + `_priority_lock_422(body.is_fast, body.priority)`:
эндпоинт парсит тело в `TaskCreate` (priority: Priority | None = None) и читает
только `body.priority` — значение `None` в обоих случаях (явный null и отсутствие
поля). `model_fields_set` (единственный источник различия) не проверяется.
Проверка pydantic-модели подтверждает: `fields_set` различает пути
(`{'priority','title','is_fast'}` vs `{'title','is_fast'}`), но код это не использует.

## Варианты решения (на усмотрение dev/СА)

1. В `create_task`: `explicit_null = "priority" in body.model_fields_set and body.priority is None`
   → 422 при is_fast=true. Минимальный диф.
2. CA-решение: признать «явный null = отсутствие поля» (изменить кейс CHK-130) —
   тогда правится кейс, не код. Решение за СА/Заказчиком, не за автоматизатором.

## Статус

Тест `test_fast_explicit_null_priority_422` (tests/api/test_r2_fast2.py) красный —
это находка дефекта продукта, НЕ дефект теста. Тест не ослабляется.
