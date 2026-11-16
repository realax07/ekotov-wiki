# code-review-002 — add-p20-contracts: повторное ревью по возврату code-review-001 (Д-1, ОВ-7 search)

- **Дата:** 2026-11-16
- **Объект:** дифф исправления Д-1 — `origin/main...3749284` (PR #295, ветка `pipeline/p20-devfix`, коммит `3749284 fix(p20): ОВ-7 для search-контракта…`). Изолированный клон `/tmp/p20-cr2-wt` (clone -b pipeline/p20-devfix).
- **Роль:** code-reviewer (Флоу 1, стадия code_review; независимое ревью, дифф не правился; append-only история ревью)
- **Арбитры:** code-review-001 (замечание Д-1, major), design add-p20-contracts §2 (ОВ-7), sdd §3/§3.5, ОГР-29
- **Метод:** повторное ревью только по диффу исправления Д-1 (Д-2/Д-3 из review-001 не возвращались — вне объекта). Каждый пункт Д-1 проверен живым прогоном, не чтением глаз.

## Сверка Д-1 → исправление (пункт за пунктом)

| Требование Д-1 | Факт (прогон/программная сверка) |
|---|---|
| Аннотирование в `export_openapi_search.py` по образцу video (Error + $ref) | ✅ Функция `annotate()` после ассерта полноты путей: `components.schemas.Error` `{"type":"object","required":["error"],"properties":{"error":{"type":"string"}}}` — без `additionalProperties:false` (ОВ-1б соблюдено). ANNOTATIONS сняты с кода обработчиков, `/api/health` не аннотируется (exempt). |
| 401 middleware декларирован | ✅ 401 на всех 4 защищенных операциях (`/api/search`, `/api/search/advanced`, `/api/suggestions`, `/api/suggestions/users`) → `$ref #/components/schemas/Error`; форма соответствует `middleware.py:41` `{"error":"unauthorized"}`. |
| 422 = фактическая форма сервиса | ✅ HTTPValidationError заменен на Error-$ref на 3 операциях; форма совпадает с обработчиком `RequestValidationError` (`app/main.py:43–54`: `{"error":"validation error","details":…}`), включая семантический 422 unknown-user (`search.py _validate_user_logins`, та же форма sdd §3). |
| 400 advanced | ✅ `$ref` Error на `/api/search/advanced` POST — соответствует `search.py:784/800` `{"error":"filter syntax: …"}` (endpoint-форма sdd §3.5). |
| HTTPValidationError и его ссылки отсутствуют | ✅ Программная сверка `contracts/openapi-search.json`: schemas = `['Error']` единственная; упоминаний HTTPValidationError — 0 (3 упоминания «ValidationError» — только текст в description, не ссылки); программный обход всех 8 error-ответов — все `{“$ref”: “#/components/schemas/Error”}`, суммарно 8 (4×401 + 3×422 + 1×400), лишних error-статусов нет. |
| Переэкспорт контракта + якорь | ✅ Контракт переэкспортирован (дифф 116 строк); якорь `services/search/openapi.yaml` дополнен комментариями об ОВ-7 — только комментарии, пути не менялись. |
| Синхронный прогон ассертов/тестов | ✅ См. ниже — 14 passed, TC-openapi-215/216 среди них. |

## Проверено (факты прогонов)

- **Детерминизм:** повторный запуск `~/venvs/wiki/bin/python scripts/export_openapi_search.py` в клоне → exit 0, `git status --porcelain` и `git diff` **пусты** — закоммиченный контракт воспроизводится байт-в-байт (критерий «экспорт = зафиксированный дифф»). Ручные правки замороженного JSON вне скрипта отсутствуют (FR-137).
- **ОГР-29 (код сервиса не менялся):** `git diff origin/main...HEAD -- services/search/app` → **0 строк**; полный список файлов диффа — ровно 4: `scripts/export_openapi_search.py`, `contracts/openapi-search.json`, `services/search/openapi.yaml`, `services/search/tests/test_search_service.py`. Вне зон волны 1 выхода нет.
- **Тесты:** `pytest services/search/tests` (venv `~/venvs/wiki`) → **14 passed** (12 прежних + 2 новых). Точечно: TC-openapi-215/216 **passed**.
- **TC-openapi-215 реально ассертит:** в контракте `Error.required == ["error"]`, отсутствие `additionalProperties`, все 400/401/422 — строго `$ref Error` (`error_refs == 8`), `validation_refs == 0`, HTTPValidationError отсутствует в schemas. Ассерты падают при любом отклонении — не дымовые.
- **TC-openapi-216 реально ассертит:** фактические тела живого TestClient (401 middleware, 422 по типу query и семантический unknown-user, 422 suggestions-kind, 400 filter syntax, 422 query-не-строка) валидируются по контрактной Error-схеме — связывает контракт↔поведение по всем трем кодам.
- **Честность описаний:** тексты description в аннотациях соответствуют коду (sdd §3.5 для 400, main.py для 422, middleware для 401) — без выдуманных статусов; 200-схемы и пути не тронуты (контроль полноты 5 путей в скрипте сохранен).
- **Известная локальная особенность (не дефект):** `tests/api/test_openapi_search_service.py` локально error по прежней причине review-001 (TC-openapi-203 требует маршрутизированный nginx-стенд, ожидание 60s) — в CI зелен; поведение диффом не менялось.

## Замечания

Blocker/major/minor не обнаружены. Замечаний к исправлению нет — Д-1 закрыт полностью и в границах рекомендации (точечная правка, без возврата фильтрации путей; ОВ-7 ядерного `contracts/openapi.json` остался задачей ПМ вне этого возврата, как и зафиксировано в Д-1).

## Что НЕ проверено (честно)

- nginx-стенд TC-openapi-203 (см. выше; принято по факту зеленых merge PR #291/#292 и неизменности диффом).
- Схемная валидация payloads (волна 5) и гейты IR-08…IR-12 (волна 7) — следующие волны, вне объекта.
- Полный регресс и web-эшелоны — не прогонялись (изменения изолированы search-контрактом; CI после пуша — контроль).

## Вердикт: Одобрить (approve)

Д-1 (major, ОВ-7 для search-контракта) закрыт: аннотирование — шаг экспорт-скрипта, контракт переэкспортирован и детерминирован, HTTPValidationError устранен, 401/400/422 декларированы через $ref на Error, соответствующий фактическим телам сервиса; код сервиса не менялся (ОГР-29); TC-openapi-215/216 добавлены и реально ассертят, 14 passed. PR #295 может вливаться.

Reviewer-Delegation: code-reviewer (Флоу 1, стадия code_review; изолированный клон /tmp/p20-cr2-wt, ветка pipeline/p20-devfix; venv ~/venvs/wiki)
