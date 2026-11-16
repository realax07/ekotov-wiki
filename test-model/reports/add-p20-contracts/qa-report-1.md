# QA-отчет add-p20-contracts — QA-контур Флоу 1 (qa-case-author + qa-automation)

- **Дата:** 2026-11-16
- **Ветка:** pipeline/p20-qa (worktree /tmp/p20-qa-wt, от main 9667fd5)
- **Вход:** openspec/changes/add-p20-contracts (FR-133…FR-141, NFR-45/46, ОГР-29…31); dev-волны 0–7 слиты, code-review-004 approve.

## 1. Инвентаризация покрытия FR-133…141 существующими TC

| FR | Требование | Покрытие (TC → тест-файлы) | Оценка |
|---|---|---|---|
| FR-133 | Контракт search — эталон формата | TC-openapi-201…214 (tests/api/test_openapi_search_service.py + services/search/tests), 215/216 (ОВ-7 Error/$ref) | полное |
| FR-134 | Контракт images | TC-gal-106/107/108 (path/methods 1:1, ОВ-7) + 109–112 (helper, happy-path каждой схемы, типовые ошибки, drift-ловушка) — services/images/tests | полное |
| FR-135 | Контракт video | TC-vid-110/111/112 (path/methods, ОВ-7) + 113/114 (схемы happy-path/ошибок) — services/video/tests | полное |
| FR-136 | Контракт weather | TC-weather-042/043 (path 1:1, ОВ-7, Open-Meteo вне спеки) + 044–046 (схемы) — services/weather/tests | полное |
| FR-137 | Единый формат (OpenAPI 3.x, 1:1 живой схеме, error-схемы) | сумма четырех контрактных сьютов выше | полное |
| FR-138 | Схемная валидация по спеке (jsonschema draft-07) | TC-openapi-217…219, TC-gal-109…112, TC-vid-113…115, TC-weather-044…046 (helper `contract_helpers.py` ×4) | полное |
| FR-139 | Карта вызовов map.md §8 | факт-чек задачи 6.1 (разовый) + arch-review-002; **механического гейта не было → пробел** | **добрано TC-p20-001** |
| FR-140 | CI-гейт дрейфа IR-08…IR-12 | TC-P20-001…016 (tests/unit/test_impact_rules_p20*.py: декларативность, DENY/green кейсы, CLI) | полное |
| FR-141 | nginx-контракт | TC-API-001…004 (tests/api/test_nginx_routes_contract.py) | полное |
| NFR-45 | Совместимость (без правок ассертов поведения) | факт-фиксация: code-review-004 (196 green append-only), подтверждено regress-final (все существующие сьюты зелеными) | зафиксировано |
| NFR-46 | Стоимость (экспорт, гейт ≤30s, сьюты ≤ +20%) | факт-фиксация: tasks.md 5.5 (46.6→46.1с), TC-P20-016; подтверждено М-заметками regress-final (гейт 0.25s, +0.4%) | зафиксировано |

## 2. Добавленное (только реальные пробелы)

1. **TC-p20-001** (FR-139) — `test-model/approved/p20-contracts/TC-p20-001.md`: карта §8 содержит все 5 имен контрактов + Retry-After; каждый repo-путь, упомянутый в §8, существует (0 MISSING). Автотест `tests/unit/test_p20_map_contracts.py` (2 теста, маркеры в docstring, без стенда). Ревью кейса — `test-model/reviews/add-p20-contracts/review-001.md` (вердикт «Одобрить»; ревью выполнено в той же QA-делегации — отдельный qa_case_reviewer не диспетчировался, механическая перепроверка критерия приложена).
2. **Фикс трассировки:** дубль TC-ID **TC-vid-112** (два разных теста: ОВ-7 error-схемы в test_openapi_contract.py и юнит helper'а волны 5 в test_videos_service.py). Юнит волны 5 переименован в **TC-vid-115** (номер свободен, ссылки ревью не ломаются: code-review-001 цитирует 112 в контексте ОВ-7, code-review-003 — диапазон 112…114, где под 112 подразумевался юнит — теперь однозначно 115).

Искусственных кейсов не заводилось: NFR-45/46 уже зафиксированы факт-заметками tasks.md и TC-P20-013/016; ОВ-6 (ядро в гейте) покрыто TC-P20-010 (shape IR-12) + движок гейта behavioral на video (TC-P20-011/012).

## 3. Regress-final — факт

Полная серия на HEAD 50b19602bee6 (стенд qa_stand_up.sh, nginx :18443, health OK):

| Набор | Результат |
|---|---|
| tests/web (полная серия) | **437 passed, 3 skipped** — 18:21 |
| tests/unit | **72 passed** (вкл. 2 новых TC-p20-001) |
| tests/api | **329 passed, 11 skipped, 2 xfailed** |
| tests/integration | пусто (только README) |
| services/*/tests ×4 | **17/111/42/26 passed** (196, = code-review-004) |

Итог 1008 passed / 0 failed. Базлайн main (tests-джоба зеленая): расхождений нет, pre-existing фейлов нет, флаков нет — изолированный перепрогон не потребовался. Артефакт: `test-model/regress/add-p20-contracts/regress-final.md`.

## 4. М-заметки (NFR-46)

- Гейт дрейфа: **0.25s** (порог ≤30s).
- Сервисные сьюты: **46.30s** против базлайна волны 5 46.1s → **+0.4%** (порог ≤20%).

## 5. Гейты

- `flow_check.py` — **OK** (порядок артефактов соответствует флоу).
- `pr_validate.py` локально — **OK** (docs:docs); CI flow+e2e+tests — по PR.
