# Релизный журнал R6 — add-microservices-full (верхнеуровневый лог передач)

Формат: `[время UTC] КТО → КОМУ: ЧТО (артефакт/вердикт)`. Append-only.
Полные детали — в гейт-репортах (`~/.hermes/state/gate-reports/`) и review-файлах.

---

## Этап 0. Решение и подготовка

- **[2026-10-03, вечер] Заказчик → ПМ (main):** директива — «следующий релиз — полный переход на микросервисы (в контейнерах)»; доделать и подготовить план перехода всех сервисов.
- **[2026-10-03, вечер] ПМ → ПМ (артефакт):** пакет `add-microservices-full` создан (proposal/design/tasks/specs; search :8378 + backup sidecar, auth не выделяется), strict-валидация.
- **[2026-10-04 ~11:35] Заказчик → ПМ:** «погнали» (старт: архивация add-containerization + ЭТАП A).

## Этап 0.5. Архивация (ПМ solo, гейты strict)

- **[11:44] ПМ → openspec/master-specs:** дельта deploy (12 сценариев) слита в `openspec/specs/deploy/spec.md`, Purpose написан; `add-containerization` → `archive/2026-10-04-add-containerization`. Strict 13/13.
- **[11:46] ПМ → себе (урок):** flow_check I3 падал после архивации (покрытие маршрутов жило в архивном пакете) → фикс: корневое покрытие (sdd + master-specs) всегда; фабрика PR #27, wiki синхронно.

## ЭТАП A. Контракт и каркас (Флоу 1)

### Подготовка ворот (ПМ → state machine, 5 попыток prepare)

- **[11:49] flowctl → ПМ: DENY** — `implement` вне графа Флоу 1 → выбрано `create_change`.
- **[11:50] flowctl → ПМ: DENY** — нет решения Заказчика → создан `decisions/2026-10-04-microservices-full.md` (дословные цитаты).
- **[11:51] flowctl → ПМ: DENY ×2** — запись не машиночитаема; scope не словарь → блок `decision-record/1` по формату P0.4.
- **[11:51] flowctl → ПМ: DENY** — зона SA не покрывает contracts/ → политика зон проектной копии приведена к реальной структуре wiki (sa: +contracts/**; dev: backend/frontend/services вместо шаблонного src/**).
- **[11:52] ПМ → flowctl: ALLOW** — корреляция `751bf741`, зоны [contracts, export_openapi_search.py].

### Задача 0.1 — заморозка контракта поиска

- **[11:52] ПМ → SA (deleg_2566f48e):** ТЗ — скрипт экспорта + замороженный контракт + deprecated-пометки.
- **[11:56] SA → ПМ:** выполнено — `scripts/export_openapi_search.py`, `contracts/openapi-search.json` (sha256 `79704d9d…`), `openapi.json` deprecated ×4; strict 13/13.
- **[11:57] ПМ (верификация) → gate:** факты подтверждены; отчет `task-0.1-report.md`.
- **[11:57] gate → ПМ: returned** (flow_check/openspec/pm_bounds PASS; pr_validate SKIPPED — нет PR; замечание OUT_OF_ZONE: отчет писал ПМ, не СА — урок).

### Задачи 0.2 + 0.3 — каркас сервисов и тест-гейт

- **[11:59] ПМ → flowctl: ALLOW** (корреляция `01af7088`) — после снятия зомби-резерва `tests/**` (утренний пилот в needs_attention закрыт админски с журналом).
- **[11:59] ПМ → dev (deleg_441015f9):** ТЗ — каркас services/search|backup, тест-гейт xfail, чекбоксы.
- **[12:17] dev → ПМ:** выполнено — `e776e59` (каркас), `0299bef` (тест-гейт), `b1f9636` (чекбоксы 0.1–0.3); pytest 1 passed/1 xfail; strict 13/13.
- **[12:26] ПМ (верификация) → gate:** тест у ПМ падал (нет стенда) → поднят стенд по tests/README → PASSED/XFAIL подтверждены; стенд погашен.
- **[12:26] gate → ПМ: returned, overall FAIL** — flow_check: 3 закрытых задачи без code-review (J10) — машина требует ревью (штатно).

### Ревью review-001 (независимый ревьюер)

- **[12:27] ПМ → code_reviewer (deleg_8775daa4):** ТЗ — проверка 0.1/0.2/0.3 по фактам.
- **[12:34] code_reviewer → ПМ: request_changes** — review-001 (`a5987fc`): 1 major (тесты без TC-трассировки — flow_check rule 6 красный), 2 minor (xfail-reason → 1.5 вместо 1.3 — ошибка исходного tasks.md; design §9 устарел), 3 nit. 0.1 и 0.2 — чисто, детерминизм и границы зон подтверждены независимо.

### Фикс-цикл (в работе)

- **[12:37] ПМ → dev (deleg_c08daa6c):** ТЗ-фикс — TC-openapi-201/202 в docstring, xfail-reason → 1.5. Design §9 и nit'ы — сознательно не в этом круге (design → SA далее).

---

**Открыто:** фикс-цикл 0.3 (dev работает) → re-review → закрытие ЭТАПА A → развилка Заказчика на ЭТАП B.
