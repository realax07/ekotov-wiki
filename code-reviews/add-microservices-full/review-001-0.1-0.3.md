# Ревью ЭТАПА A — пакет add-microservices-full (задачи 0.1 / 0.2 / 0.3)

Reviewer-Delegation: deleg-arch-rev-001

- Дата: 2026-10-04
- Ревьюируемые коммиты: `9c63971` (0.1, контракт), `a9e530b` (0.1, deprecated), `e776e59` (0.2, каркас сервисов), `0299bef` (0.3, тест-гейт), `b1f9636` (чекбоксы tasks.md)
- Ревьюируемые задачи: 0.1, 0.2, 0.3 (ЭТАП A)
- Авторы изменений: deleg_2566f48e / deleg_441015f9 (не я — независимое ревью)
- Метод: собственные команды (git show / программная сверка JSON / повторный запуск экспорта / чтение кода теста). Прогон контрактного теста выполнен (файловый, без стенда).

---

## Задача 0.1 — заморозка контракта поиска

### Что проверено (факты)

1. **Состав контракта.** `contracts/openapi-search.json`: ровно 4 пути — `/api/search` (GET), `/api/search/advanced` (POST), `/api/suggestions` (GET), `/api/suggestions/users` (GET); `openapi: "3.1.0"`, 4 операции. Подтверждено разбором JSON.
2. **Валидность OpenAPI.** `openapi-spec-validator.validate()` → `VALID (OpenAPI 3.1.0)`. Структурная сверка (info/paths/operationId/responses на каждой операции) — без ошибок.
3. **Детерминизм (прогнан дважды самостоятельно, venv проекта):**
   - до прогона: `sha256 = 79704d9ded12a22d06af7ded221be14cc17e3f29a13c34ad8d95625e48cf9a1a`;
   - прогон 1 `python scripts/export_openapi_search.py` → OK, 4 путей; прогон 2 → sha256 идентичен; `git diff --exit-code -- contracts/openapi-search.json` пуст.
   - Скрипт поднимает монолит (uvicorn, temp-БД, seed owner), контролирует FR-68 (схема не отдается без сессии — явная проверка 302/307/401), фильтрует paths по префиксам `/api/search`, `/api/suggestions`, пишет `sort_keys=True, indent=2` + `\n` — формат стабилен.
4. **deprecated в contracts/openapi.json (a9e530b).** Программная сверка `a9e530b~1` vs `a9e530b`: топ-уровень и набор путей идентичны; изменены ровно 2 поля (`deprecated`, `description`) на ровно 4 search-путях; diff вне этих 4 путей — **NONE** (components и остальные пути бит-в-бит). На каждой из 4 операций: `deprecated: true` + аннотация «Переезд в search-сервис (пакет add-microservices-full)».
5. **HTML-страница /search НЕ помечена**: в openapi.json ровно 4 вхождения `deprecated: true` (строки 774/934/952/1006 — все на API-путях); `/search` (строка 1365, `search_page_search_get`) без deprecated — корректно, переезжает API, не страница (design §2 «Что НЕ входит»).
6. **Зона коммитов 0.1**: только `contracts/openapi-search.json`, `scripts/export_openapi_search.py` (9c63971, 2 files, +849) и `contracts/openapi.json` (a9e530b, 1 file). Соответствует зонам SA (012a298: contracts/**, export_openapi*).

### Находки

| # | Severity | Файл | Замечание |
|---|---|---|---|
| 0.1-a | nit | 9c63971 (commit message), task-0.1-report.md | «Заморожено 4 маршрута (6 операций)» — фактически операций **4** (по одной на путь; проверено разбором JSON). Отчет при этом сам перечисляет ровно 4 операции. Ошибка счета в текстах, не в артефактах. |
| 0.1-b | nit | design §3 vs scripts/export_openapi_search.py | Design §3: «поднимает search-сервис локально» — фактически скрипт поднимает **монолит** (app.main:app) и фильтрует paths. Обосновано в docstring (middleware регистрируется через http-слой), но формулировка design r1 не уточнена. |

---

## Задача 0.2 — каркас services/search и services/backup

### Что проверено (факты)

1. **Структура services/search/** (e776e59): `app/__init__.py`, `tests/__init__.py`, `openapi.yaml` (комментарий-указатель на `contracts/openapi-search.json`, пути перечислены дословно), `README.md` — порт **8378**, RO-профиль (`wiki-data:/data:ro`, без миграций схемы), healthcheck `/api/health`, статус «в работе, ЭТАП B».
2. **services/backup/README.md**: sidecar (вне цепочки запросов), cron-цикл в python-шедулере, bind **`/var/backups/ekotov-wiki`**, том данных ro, mem_limit 64m — соответствует design §5.
3. **services/README.md**: таблица статусов — `search/` и `backup/` «в работе (ЭТАП B)», `auth/` «не выделяется» с мотивировкой «безопасные профили данных… НЕ механический разрез с общим RW SQLite» — дословно соответствует tasks.md 0.2 и плану §1.2 / design §10.
4. **Код ядра не менялся**: дифф e776e59 — 6 файлов, все под `services/`. «Без изменения кода» выполнено.
5. Замечание об объеме: `services/search/README.md` в диффе «+38/-9» — файл существовал и до (кандидат ЭТАПА 2), дополнен, не переписан с потерей истории — допустимо.

### Находки

Существенных замечаний нет.

---

## Задача 0.3 — контрактный гейт tests/api/test_openapi_search_service.py

### Что проверено (факты)

1. **test_search_contract_is_frozen**: `paths == EXPECTED_PATHS` — множество **ровно** 4 путей (лишние/недостающие ловятся симметрично), проверка `openapi.startswith("3.")`, файл читается с диска. **Сети не требует** — только файловая система (подтверждено чтением кода; импорты — json/pathlib/pytest).
2. **test_core_has_no_search_routes**: `@pytest.mark.xfail(strict=True, reason=...)`; проверяет отсутствие `search_router`/`suggestions_router` в `backend/app/main.py`. Сейчас в main.py они есть (строки 17/18/42/43) → тест честно падает → xfail корректен. Снимается задачей 1.5 (tasks.md: «активация контрактного гейта (0.3): xfail снимается»).
3. **Живой прогон**: `.venv/bin/python -m pytest tests/api/test_openapi_search_service.py -v` → **1 passed, 1 xfailed in 0.12s** — совпадает с отчетом автора.
4. grep-проверка main.py — грубая (подстрока, не AST), но для гейта-заготовки достаточна и консервативна (false-positive только при упоминании имени в комментарии).

### Находки

| # | Severity | Файл | Замечание |
|---|---|---|---|
| 0.3-a | **major** | tests/api/test_openapi_search_service.py | **Нет TC-трассировки в docstring** — `python3 scripts/flow_check.py .` дает `FLOW-ERROR: tests/api/test_openapi_search_service.py: тесты без TC-трассировки в docstring (rule 6)`. Правило действует на каждый `tests/**/test_*.py` при наличии `def test_*` без `TC-…-NNN` в тексте. Ошибка введена коммитом 0299bef (на HEAD это единственная тестовая ошибка flow_check). Блокирует ворота пакета наравне с J10-покрытием. **Рекомендация:** добавить в module docstring ссылку на релевантный кейс test-model/regression/search/ (например, семейство TC-search-r4-1xx, контрактная база FR-10/11/12) — одна строка. |
| 0.3-b | minor | tests/api/test_openapi_search_service.py vs tasks.md | `reason` xfail — «Активируется задачей 1.3: выделение search-сервиса», а tasks.md назначает активацию гейта задаче **1.5** (1.3 — только nginx-маршрутизация; после 1.3 main.py еще импортирует роутеры). Функционально безопасно (strict-xfail на 1.3 честно остается xfail), но причина вводит в заблуждение при снятии маркера. Рекомендация: привести reason к «снимается задачей 1.5». |

---

## Трассировка tasks.md ↔ design.md

1. Все три задачи в tasks.md помечены `[x]` (b1f9636, дифф — только 3 чекбокса, ничего больше). ✓
2. 0.1 ↔ design §3 (контракт до кода, deprecated-аннотация, «экспорт = файл») — соответствует. Расхождение: design §3 говорит «поднимает search-сервис», реализация — монолит с фильтрацией (см. 0.1-b).
3. 0.2 ↔ design §2 (границы search, RO-профиль) и §5 (backup sidecar) — соответствует.
4. 0.3 ↔ design §4 (контрактный CI-gate) — соответствует частично: design §4 описывает также grep + «404/405 проверка» ядра и nginx-проверки (X-Service, 503-деградация) — это осознанно разложено на задачи 1.3/1.5/2.2, тест 0.3 — заготовка из двух инвариантов, как и сформулировано в tasks.md 0.3. Расхождение допустимое, поэтапное.
5. **tasks.md 0.3 внутренне противоречив**: в формулировке 0.3 — «активируется задачей 1.3», но активация гейта определена задачей 1.5 (см. 0.3-b). Отмечено как minor на тесте; источником является tasks.md — поправить желательно при следующей ревизии tasks.md.
6. **design §9 (карта этапов) не соответствует tasks.md**: §9 называет «0.4 каркас backup» и «1.5 backup-sidecar», тогда как в tasks.md каркас backup — в 0.2 (отдельной 0.4 нет), а 1.5 — активация контрактного гейта (backup в 1.2/1.4). Нумерация в design r1 устарела относительно tasks.md. minor.

## Границы зон (9c63971~1..b1f9636)

`git diff --name-only 9c63971~1..b1f9636`: только `contracts/**`, `scripts/export_openapi_search.py`, `services/**`, `tests/api/test_openapi_search_service.py`, `openspec/changes/add-microservices-full/tasks.md`. **Выхода за зоны задач нет.**

## Что НЕ проверено (честно)

- Живой стенд не поднимался (по ТЗ); nginx-маршрутизация, X-Service, 503-деградация — вне зоны ЭТАПА A.
- Валидация `openspec validate --all --strict` не повторялась (авторский отчет: 13/13; косвенно — flow_check не имеет замечаний к спекам пакета).
- Соответствие `components` контракта поиска самодостаточности на будущий мини-main (задача 1.1) — предмет ЭТАПА B.

---

## Сводка находок

- **major (1):** 0.3-a — тест-гейт без TC-трассировки, flow_check FAIL (rule 6), блокирует ворота пакета.
- minor (2): 0.3-b (reason xfail ссылается на 1.3 вместо 1.5; источник — tasks.md 0.3), трассировка-6 (design §9 устарел относительно нумерации tasks.md).
- nit (3): 0.1-a («6 операций» вместо 4 в commit message/отчете), 0.1-b (design §3 «search-сервис» vs монолит в скрипте).

## Вердикт: request_changes

Содержательно ЭТАП A выполнен точно по design (контракт валиден, детерминизм бит-в-бит подтвержден повторным прогоном, дифф openapi.json хирургический, зоны чисты) — но major 0.3-a оставляет `flow_check` красным на HEAD, что блокирует ворота пакета; требуется одна строка TC-трассировки в docstring теста (плюс по желанию миноры 0.3-b/трассировка-6).
