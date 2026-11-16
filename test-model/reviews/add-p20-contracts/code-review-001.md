# code-review-001 — add-p20-contracts: dev-дифф волн 0–4 (IR-сужения + контракты search/video/images/weather)

- **Дата:** 2026-11-16
- **Объект:** дифф волн 0–4 пакета add-p20-contracts — `7e615bf..main` (слитые PR #291 + #292: 6642a64 волна 0, d4a1745 волна 1, 4315a3c волны 2–4; коммиты docs-ревизий tasks #293 в дифф зон не добавляют). Изолированный клон `/tmp/p20-cr-wt`, ветка `pipeline/p20-code-review`.
- **Роль:** code-reviewer (Флоу 1, стадия code_review; независимое ревью, dev-дифф не правился)
- **Арбитры:** `openspec/changes/add-p20-contracts/{tasks.md, design.md §1/§2/§5, specs/contracts/spec.md}`, arch-review-002 (approved), ОГР-29/ОГР-31, NFR-45
- **Метод:** круг 1 — спека как закон (tasks 0.1–4.3, критерии приемки механически); круг 2 — практики (guard'ы, детерминизм, секреты, изоляция); круг 3 — integration (сверка контрактов с живыми декораторами сервисов программно, якоря↔контракты, прогон тестов). Прогоны: venv `~/venvs/wiki`, env в /tmp, worktree /tmp/p20-cr-wt.

## Проверено (с фактами прогонов)

**Волна 0 (сужения IR-01/IR-07):**
- `scripts/impact_rules.json` валиден; IR-01 `when` → `^services/[^/]+/openapi\.json$`, IR-07 `when` → `^contracts/openapi\.json$` — точно по design §5; `require` и `content_when` IR-07 не тронуты (guard консервируется).
- Ослабления guard'ов нет: IR-02…IR-06 не менялись (дифф — 2 правила, только `when[].path`); TC-P20-002 подтверждает DENY IR-01 на `M services/search/openapi.json` без ядерного контракта.
- `tests/unit/test_impact_rules_p20.py` (TC-P20-001…009): **9 passed**. Маркеры TC в docstring-литералах — правило 6 соблюдено; CLI-симуляции 006–008 через `PR_CHANGED_FILES`-конвенцию соответствуют критериям приемки tasks 0.1/0.2; TC-P20-009 (чистый HEAD) green.

**Волна 1 (search-контракт полным охватом):**
- `export_openapi_search.py`: фильтрация по префиксам упразднена, вход — прямая вставка сессии (без bcrypt-логина), anon `/openapi.json` → 401 контролируется; `services/search/app` в диффе не меняется (ОГР-29 соблюдено).
- Контракт = живой сервис 1:1: 5 path-items (`/api/search`, `/api/search/advanced`, `/api/suggestions`, `/api/suggestions/users`, `/api/health`) — сверено с кодом и якорем; якорь `services/search/openapi.yaml` синхронен.
- Path-ассерты синхронно: TC-openapi-201/202 **passed** (локальный прогон `tests/api/test_openapi_search_service.py`); `services/search/tests` — **12 passed**. TC-openapi-203 локально падает ожидаемо (нужен маршрутизированный nginx-стенд, skip-логика рассчитана на него) — в CI PR #291/#292 зелен; не дефект диффа.

**Волны 2–4 (video/images/weather):**
- Детерминизм: все 4 экспорт-скрипта запущены в worktree повторно → `git diff --exit-code -- contracts/` **пуст** (критерии 1.1/2.1/3.1/4.1 подтверждены живым прогоном, не по-наитию).
- Охват = живым декораторам (программная сверка контракт↔`@router`-декораторы): video 10 path-items / 14 операций, images 8 / 11, weather 2 / 2, search 5 / 5 — расхождений нет; все 4 контракта — валидный OpenAPI 3.1.0.
- ОВ-7 ($ref) для video/images/weather: `components.schemas.Error` без `additionalProperties:false` (ОВ-1б); $ref на 401/422: video ×19, images ×19, weather ×2 (401 + 503 `weather_unavailable` — сверено с `routes.py:77`). Internal-пометка authcheck присутствует и аннотируется скриптом, не руками (TC-vid-112).
- Честность аннотаций сверена с кодом обработчиков: video 409 «video/preview is not ready» = `videos.py` `status_code=409`; 403 «not your comment» = `social.py`; images — 409 у реакций отсутствует и в коде `gallery.py` (только 201/403/404/422/500), ассерт отсутствия 409 в тесте (TC-gal-108) соответствует скорректированному критерию 3.2 (решение ПМ от 2026-11-16); weather — в спеке нет упоминаний Open-Meteo, `days` minItems=maxItems=7, null-метрики типизированы `["number","null"]`.
- Контрактные тесты: `services/video/tests -k contract` **3 passed** (TC-vid-110/111/112), `services/images/tests` **4 passed** (TC-gal-106/107/108), `services/weather/tests` **3 passed** (TC-weather-003 сохранен, +042/043).
- Якоря video/images/weather содержат точные списки путей контрактов (программная сверка — все пути присутствуют).

**Инфраструктура ревью:** `flow_check` на worktree — **OK**; CI flow+e2e PR #291/#292 зелен (слияния состоялись).

## Замечания

| # | Файл / место | Серьезность | Дефект | Рекомендация |
|---|---|---|---|---|
| Д-1 | `contracts/openapi-search.json` + `scripts/export_openapi_search.py` (волна 1) | **major** | ОВ-7 для search-контракта не выполнен: `components.schemas.Error` в файле нет; 422-ответы ссылаются на FastAPI-заготовку `HTTPValidationError` (`{"detail":[…]}`), тогда как фактическое тело 422 сервиса — `{"error":"validation error","details":…}` (`services/search/app/main.py:43–54`, обработчик `RequestValidationError`, sdd §3); 401 middleware (`{"error":"unauthorized"}`) в спеке не декларирован вовсе. Критерий design §2 «$ref/схема Error присутствует в файле» для search не достигнут (из 5 спек ОВ-7 сейчас нет у search и ядра; ядро — вне волн 0–4, search — артефакт волны 1 в данном диффе). Осязаемый риск: волна 5 (helper `validate_response`, «отсутствие маршрута/статуса в спеке = ошибка теста») даст ложный дрейф-сигнал на 401/422 search и схемная валидация реальных тел разойдется со спекой. tasks 1.1/1.2 шаг аннотирования не содержат — расхождение design §2 ↔ tasks волны 1, не покрытое ни одной следующей волной (5–7 контракты не трогают) | Добавить в `export_openapi_search.py` пост-экспорт шаг аннотирования по образцу `export_openapi_video.py` (Error+$ref: 401 middleware, 422 validation-handler; фильтрацию путей не возвращать — ОГР-29/Н-2 санкционируют аннотирование скриптом), переэкспортировать контракт, синхронно прогнать TC-openapi-201…210 и тесты `services/search`. Точечная правка в границах зон волны 1. ОВ-7 для ядерного `contracts/openapi.json` — зафиксировать ПМу отдельной задачей (вне данного возврата) |
| Д-2 | `scripts/impact_rules.json`, блок IR-07 | minor | Переиндентация неизмененных строк (`title`/`when` сдвинуты на пробел) — шум в диффе guard-файла, содержимого не касается (JSON валиден, ассерты проходят) | Не переформатировать незатронутые строки guard-файла при точечных правках |
| Д-3 | `services/{video,images,weather}/openapi.yaml` | info | Якоря 21/20/16 строк против design §1 «якорь 10–14 строк» — отклонение вынужденное (точный список 14 путей + шапка не влезает в 14 строк; критерий приемки «якорь содержит все path-items» приоритетен) | Считать оценку «10–14 строк» в design §1 прикидкой под search; править не требуется — отметить при случае касания design |

Blocker не обнаружены: guard'ы не ослаблены (дифф — только сужения `when` по design §5, оба guard-сценария TC-P20-002/004/005 подтверждены прогоном), секретов нет (тестовые значения без секретности, NFR-7), код сервисов и ядра не меняется (ОГР-29 — в диффе из кода только BUG-029-файлы вне зон P20).

**Вне скоупа, зафиксировано:** диапазон `7e615bf..HEAD` содержит артефакты BUG-029 (`backend/app/pages.py`, `frontend/static/js/gallery.js`, `tests/web/*`, `test-model/approved/bug-029/`, `reviews/bug-029/review-001.md`) — собственный пакет со своим review-001, к волнам 0–4 P20 не относится и здесь не ревьюился.

## Что НЕ проверено (честно)

- Ядерный `contracts/openapi.json` (в диффе отсутствует; его ОВ-7-состояние зафиксировано в Д-1 как задача ПМ, не дефект волн 0–4).
- End-to-end nginx-стык `/_video_auth` → authcheck (проверена только пометка internal в спеке и коде сервиса).
- Полный регресс-сьют и web-эшелоны — прогонялись выборочно (перечислено выше); CI-прогоны приняты по факту зеленых merge PR #291/#292.
- Схемная валидация payloads (волна 5) и гейт IR-08…IR-12 (волна 7) — следующие волны, вне объекта ревью.

## Вердикт: Вернуть (return)

**Вернуть dev'у по одному major-замечанию Д-1** (ОВ-7 для search-контракта: аннотирование в экспорт-скрипт + переэкспорт + синхронный прогон ассертов). Волны 0, 2, 3, 4 — приняты без замечаний по существу; Д-2/Д-3 не блокируют и в повторное ревью не возвращаются. Повторное ревью — по диффу исправления Д-1 (append-only история ревью).

Reviewer-Delegation: code-reviewer (Флоу 1, стадия code_review; изолированный клон /tmp/p20-cr-wt, ветка pipeline/p20-code-review; venv ~/venvs/wiki, env в /tmp)
