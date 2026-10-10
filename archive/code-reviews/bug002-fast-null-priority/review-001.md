# Ревью BUG-002 — review-001 (feature/bug002-fast-null-priority, da782f5)

- **Ревьюер:** code_reviewer_agent (изолированная сессия)
- **Дата:** 2026-09-22
- **Объект:** ветка `feature/bug002-fast-null-priority`, HEAD `da782f5` (поверх cherry-pick `58fc2aa`)
- **Арбитраж:** sdd r2 §3.2; кейс TC-fast2-004 (CHK-130); баг-репорт `test-model/bugs/BUG-002-fast-explicit-null-priority-201.md`

## Вердикт: **APPROVE**

Открытых blocker/major нет. Все смоук-проверки и полный регресс — зеленые на независимом стенде.

## Замечания

| # | Серьезность | Файл/место | Замечание | Рекомендация |
|---|---|---|---|---|
| 1 | minor | backend/app/tasks.py:301 (`_explicit_null_priority_422(body) if body.is_fast else None`) | Проверка функции не обусловлена `is_fast` внутри самой функции (функция вернула бы 422 и для обычной задачи с явным null, если вызвать без условия). Условие вынесено на вызов — корректно, но хрупко к будущим вызовам. Поведения не нарушает (проверено смоуком №6: обычная задача с null → 201). | Можно перенести проверку `body.is_fast` в тело функции; в рамках задачи — не блокирует. |
| 2 | minor | openspec/changes/add-r2-categories-settings/tasks.md:23 | Правка tasks.md формулировкой «+ BUG-002 fix …» удлиняет уже закрытую задачу 4.2; трассировка FR-27/ОГР-10 сохранена, валидация проходит. Приемлемо, но смешивает историю задачи 4.2 с багфиксом Флоу 2. | В будущем для Флоу 2 достаточно ссылки на баг-репорт, без раздувания строки задачи. |

Замечания minor не препятствуют вливанию.

## Проверено (собственные прогоны)

Стенд: изолированный worktree `/tmp/rv-bug002` (HEAD = `da782f5`, сверено по md5 с origin-веткой), uvicorn на свободном порту 8077, копия БД `/tmp/rv-bug002-regress.db`, seed users owner/wife + категории «Дом/Работа/Личное».

### Смоук нового поведения (8/8 PASS, скрипт /tmp/rv-bug002-smoke.py)

1. явный `priority:null` + `is_fast:true` → **422 дословно** `{"error":"validation","details":{"priority":"fast requires high"}}` — PASS
2. отсутствие поля + `is_fast:true` → **201, priority="high"** (CHK-134 не сломан) — PASS
3. `priority:"low"` + fast → 422 дословно — PASS; `priority:"medium"` + fast → 422 дословно — PASS (priority-lock не регрессировал)
4. PATCH `priority:null` на fast-задаче → 422 дословно (PATCH не менялся, поведение сохранено) — PASS
5. явный null при занятой fast-линии → **422 до 409** (порядок CHK-138 соблюден: обе проверки в группе валидаций тела до `BEGIN IMMEDIATE`/`_fast_line_busy`) — PASS
6. явный `priority:null` у обычной задачи → **201** (null-семантика обычной задачи не задета) — PASS
7. контроль: 409 `{"error":"fast line occupied"}` при занятой линии остался — PASS

### Регресс-набор

`pytest tests/api` (EKOTOV_WIKI_BASE_URL=:8077, EKOTOV_WIKI_DB_PATH + R2QA_PYTHON заданы):
**116 passed / 0 failed / 0 xfailed, 9 skipped** (skip = фикстуры, требующие env/миграционного скрипта — вне скоупа).

Цель 116/0/0 достигнута.

### xfail снят

`tests/api/test_r2_fast2.py::test_fast_explicit_null_priority_422` — метки `@pytest.mark.xfail(strict=True)` в коде больше нет (осталось только упоминание в docstring, grep «xfail» по tests/api — 1 совпадение, docstring). Тест в общем прогоне зеленый без xpass/warnings-аномалий. Снятие корректное: тест не ослаблен, ассерты 422 + дословное тело + «задача не создана» сохранены дословно.

### Дифф-граница и cherry-pick

- Дифф `origin/feature/r2-qa-api-tests..origin/feature/bug002-fast-null-priority` — **3 файла** (в задаче заявлено 2: + правка чекбокса `openspec/changes/add-r2-categories-settings/tasks.md`, см. замечание 2):
  - `backend/app/tasks.py` (+22): helper `_explicit_null_priority_422` через `model_fields_set`, вызов в `create_task` после `_priority_lock_422`, до 409-ветки;
  - `tests/api/test_r2_fast2.py` (−12/+3... фактически снятие xfail-декоратора + обновление docstring);
  - `openspec/changes/add-r2-categories-settings/tasks.md` (чекбокс-комментарий).
- Cherry-pick `58fc2aa` vs существующий `71973fc` в origin/feature/r2-qa-api-tests: `git diff 71973fc 58fc2aa` **пуст** — содержимое деревьев идентично; коммитер/автор совпадают. Дубликат подтвержден, конфликтов нет.
- PATCH (`update_task`) не менялся: различение через `model_fields_set` на строке 394 — прежнее, диффом не затронут.

### Ворота

- `openspec validate --all --strict` → **9 passed, 0 failed**;
- `python scripts/flow_check.py /tmp/rv-bug002` → **OK**.

### Security-минимум (2-й круг)

Секретов в диффе нет (тестовые пароли — существующие seed-плейсхолдеры из conftest, в коде фикса отсутствуют); SQL в фиксе не добавляется; тело 422 — константа, без пользовательского интерполяционного вывода.

## Что НЕ проверено

- UI-часть (TC-fast2-003, блокировка поля в форме) — вне скоупа багфикса (backend-only), не проверялась.
- Смоук №7 (409) выполнен через API — гонка конкурентных fast-POST (BEGIN IMMEDIATE) на нагрузке не воспроизводилась; код гонки не менялся (дифф не затрагивает транзакционный блок).
- Параллельный прогон pytest с веб-сьюитом — не выполнялся (tests/web вне скоупа).

## Методическое замечание (не замечание к коду)

Первый прогон регресса дал ложные 2 failed: порт 8080 дефолтного `DEFAULT_BASE_URL` оказался занят сервером другой параллельной сессии (стенд `/tmp/rv-g8-api`, код БЕЗ фикса) — тесты ходили не в тот стенд. После переноса на свободный порт — 116/0. Рекомендация конвейеру: стенды регресса поднимать на явно заданных свободных портах, `DEFAULT_BASE_URL` 8080 в conftest — потенциальный источник перекрестного загрязнения прогонов.
