# Review-001: независимое ревью кейсов TC-form-001…005 (form-f1)

- Ревьюер: qa_case_reviewer (контракт 5; НЕ автор кейсов).
- Дата: 2026-11-23. Ветка `feat/form-f1`, HEAD cac4868 (+ бамп static_v
  form-f1-m1 и CSS-фикс `.task-actions select{margin-top:0}`).
- Партия (5 кейсов, одна партия):
  `test-model/approved/form-f1/TC-form-001.md` … `TC-form-005.md`.
- Источники сверки: дельты `openspec/changes/form-f1/specs/tasks/spec.md`
  (1 capability, 5 Requirement — 2 MODIFIED + 3 ADDED, 17 Scenario),
  дифф реализации cac4868 (собственная проверка построчно), план
  PLAN-FORM-F1 (requirements.md пакета), канон-отчет Dev-ревью
  `docs/review/review-form-f1-001.md`, локальный прогон затронутых сьютов
  (43 passed / 3 failed — разбор в impact), скриншоты /tmp/form-shots
  (обе темы, 1440/390).

## Метод

Файл за файлом: трассировка (Requirement/Scenario существуют в дельтах и
совпадают дословно), полнота шагов, однозначность ожидаемого результата,
отсутствие выдуманного поведения, проверяемость существующим автотестом
(сверка имени тест-функции/файла/PO-метода с фактическим HEAD).

## Сводная проверка трассировки

- Раскладка: 1 кейс = 1 Requirement дельты (5/5); все 17 Scenario отнесены:
  TC-001 — 4, TC-002 — 2, TC-003 — 2, TC-004 — 6, TC-005 — 12 сценариев
  MODIFIED «Формы…V3» (частично дублируются с TC-004 по зоне футера —
  отнесены обоим Requirement корректно).
- MODIFIED-заголовки дословно совпадают с мастером (grep);
  «Единая зона действий задачи» и «Формы создания и редактирования по
  дизайну V3» — полный перенос блоков мастера, правки только в THEN.
- Имена автотестов сверены с HEAD: `test_priority_segment_follows_select`,
  `test_task_form_priorities_distinguished_color_and_icon`,
  `test_actions_zone_single_row_order_and_ids`,
  `test_desktop_modals_unchanged`, `test_form_fields_v3_tokens_and_focus_ring`,
  `test_edit_form_matches_v3_and_shows_fast_row`,
  `test_all_form_interactive_elements_styled` — существуют; PO-методы
  `priority_seg_button/priority_checked_seg/title_counter/due_chip` — в
  `tests/web/pages/task_form.py` (строки сверены).

## Замечания (по ходу ревью)

### TC-form-002, TC-form-003 — minor (частичное ручное покрытие)

Quick-чипы и счётчик не имеют отдельных автотестов — кейсы честно помечают
шаги как ручную браузерную сверку (/tmp/form-shots подтверждает: чипы и
«0/500» видны на 390px-скриншоте); PO-локаторы `due_chip`/`title_counter`
готовы. Отражено в impact (Д1) как задокументированный дефицит. Не блокер:
требования закрыты на приемочном уровне, автотесты — кандидат вне волны.

### TC-form-004 — observation (зависимость от фикса волны)

Ожидаемый результат «центры ±4px» выполняется только с CSS-фиксом
`.task-actions select { margin-top: 0 }` (довнесенный дефект cac4868:
селект футера наследовал margin-top 4px правила `.task-form select`;
без фикса тест red 4.01px). Кейс не ссылается на фикс явно — читателю
следует знать: ассерт зелен пост-фикс. Рекомендация отражена в impact
(revalidate №3 CLOSED). Исправлений в кейсе не требуется.

### TC-form-005 — observation (скролл-тест вне дельты)

Шаг 1 опирается на `test_desktop_modals_unchanged` (ассерт 720px — green);
файловый сосед `test_close_restores_exact_board_scroll` красный на ЧИСТОМ
cac4868^ (классификационный перегон: `main.content` — скроллер app-shell
≤760px, window.scrollY ≠ меняться) — к дельте form-f1 отношения не имеет,
в кейс не входит; классификация — в impact Д2 и regress-final.

## Что проверено и не вызвало замечаний

- Значения и id во всех кейсах — из дельт и фактического DOM (дифф
  cac4868: `#task-priority-segment`, `.qchip[data-due-quick]`,
  `#title-counter`, `.task-actions`, `#task-due-date` — сверены с
  board.html HEAD); выдуманных селекторов нет.
- Порядок футера в TC-004 (`[Столбец][Удалить]` слева / `[Отмена][Сохранить]`
  справа) совпадает с эталоном edit.html и фактическим THEN дельты.
- Тач/шрифт-инварианты (NFR-23/24) отнесены к существующим мобильным
  ассертам, а не выдуманы.
- Обращение с известными средовыми :18443-кейсами — корректно: live-часть
  закрывается на каноническом контуре regress-final (impact Д2).

## Итог

Замечания: 0 blocker / 0 major / 2 minor (TC-form-002, TC-form-003 —
ручное покрытие) + 2 observation (TC-form-004 фикс волны, TC-form-005
вне-дельтовый сосед). Все minor не искажают трассировку; исправлений в
кейсах не требуется.

## Вердикт: approve

одобрить
