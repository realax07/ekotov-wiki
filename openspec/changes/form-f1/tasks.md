# tasks.md: form-f1

> Флоу 2 (правки формы + QA). Реализация — коммит cac4868, ветка `feat/form-f1`.
> Чек-лист закрывается при слиянии/архивации пакета (конвенция пакета:
> флажки — жизненный цикл до архива, статус выполнения — пометка «ВЫПОЛНЕНО»).

## Подготовка пакета

- [ ] 1.1 Верстка формы F1 по эталону design-forge/extra/form-v1 (board.html + board.css): сегмент, чипы, счётчик, липкий футер, bottom-sheet ≤760px — ВЫПОЛНЕНО (cac4868)
- [ ] 1.2 task-form.js: renderPrioritySegment / updateTitleCounter / renderDueChips — render-слой; collectTaskForm/снапшот/422/409 не тронуты — ВЫПОЛНЕНО (cac4868)
- [ ] 1.3 Правка визуальных ассертов 6 тест-файлов (task_form PO, p12_ui_polish_r8, p14_22_fullscreen, r3_formv3, r6_wave2, settings_categories) — только литералы/локаторы вида, контракт-тесты без правок — ВЫПОЛНЕНО (cac4868)
- [ ] 1.4 Бамп static_v → form-f1-m1 (backend/app/pages.py) + синхронизация литерала TC-redesign-011 (гейт IR-03) — ВЫПОЛНЕНО
- [ ] 1.5 Браузерная сверка с эталоном: обе темы, 1440 и 390 (скриншоты /tmp/form-shots) — ВЫПОЛНЕНО

## Пакет и QA

- [ ] 2.1 openspec/changes/form-f1/: proposal/design/tasks/requirements + дельты specs/tasks (2 MODIFIED + 3 ADDED); openspec validate --all --strict — green — ВЫПОЛНЕНО
- [ ] 2.2 test-model/impact/form-f1.md (H5) — ВЫПОЛНЕНО
- [ ] 2.3 test-model/approved/form-f1/ — кейсы TC-form-001…005 с трассировкой на автотесты — ВЫПОЛНЕНО
- [ ] 2.4 test-model/reviews/form-f1/review-001.md (ревью кейсов + диффа cac4868, docs/review/review-form-f1-001.md) — ВЫПОЛНЕНО
- [ ] 2.5 regress-final: полный сериал tests/ на каноническом контуре :18443 (flowctl regress --change form-f1 --final, свежая БД) — выполняется перед мержем

## Слияние и архивация

- [ ] 3.1 Слить тела дельт в мастер-спеку tasks и перенести пакет в changes/archive/ одним PR-мержом (контракт 7)
- [ ] 3.2 После архивации: openspec show form-f1 --json --deltas-only сверить со списком сценариев мастера
