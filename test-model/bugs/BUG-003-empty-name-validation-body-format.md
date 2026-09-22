# BUG-003 — 422-тело валидации имени категории: каркас FastAPI отвечает "validation error" вместо sdd "validation"

- **Кейс:** TC-cat-008 (CHK-90/91), approved/add-r2-categories-settings
- **Приоритет:** Should | **Окружение:** локальный стенд `http://127.0.0.1:8099`, main (40feb35), uvicorn + SQLite /tmp/g8fix_app.db
- **Создан:** qa_automation_agent, 2026-09-22 (return-фикс по G8, review-002-tests замечание №1)

## Ожидание (кейс, sdd r2 §3.1)

`POST /api/categories` с `name=""` и `name="   "` → HTTP **422**, тело дословно:

```json
{"error": "validation", "details": {...}}
```

справочник не изменился. Формат ошибок валидации корневой sdd §3:
`{"error": "<сообщение>", "details": {...}}`.

## Факт

→ HTTP 422 (статус и отказ совпадают), но тело каркасное:

```json
{"error": "validation error", "details": [{"type": "value_error", "loc": ["body", "name"], "msg": "Value error, name must not be empty", "input": "", "ctx": {"error": {}}}]}
```

- `error` = `"validation error"` вместо `"validation"` (подстрочное совпадение маскировало расхождение);
- `details` — список ошибок pydantic вместо объектной структуры `{...}` из sdd.

Воспроизводится 2/2 прогонов, для обоих значений (`""` и `"   "`).

## Анализ (корень)

`RequestValidationError` handler — `install_error_handlers` в `backend/app/main.py`
(перенос из app/tasks.py:533): возвращает `"error": "validation error"` и
`jsonable_encoder(exc.errors())` (список). Дословные 422-тела sdd (`"validation"`,
details-объект) сейчас собираются вручную только там, где валидация императивная
(FR-21/FR-27 в app/tasks.py); pydantic-отказы идут через каркасный хендлер —
форматы расходятся.

## Варианты решения (на усмотрение dev/СА)

1. Хендлер `RequestValidationError` отвечает sdd-форматом:
   `{"error": "validation", "details": {...объектная структура...}}` —
   единый формат 422 для всех точек входа.
2. CA-решение: легализовать каркасный формат в sdd/кейсе — тогда правится
   спека/кейс, не код. Решение за СА/Заказчиком, не за автоматизатором.

## Статус

Расхождение тела, не поведения (отказ 422 работает). Тесты `tests/api/test_r2_categories.py`:
`test_category_empty_name_rejected_422` и `test_category_empty_name_422_sdd_body` —
xfail(strict=True, reason="…BUG-003"): при исправлении продукта появится XPASS
и уронит strict — сигнал снять метку (дисциплина BUG-002/TC-fast2-004).
