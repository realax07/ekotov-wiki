# Impact-анализ QA: change form-f1 (H5)

> Дата: 2026-11-23 | Ветка: `feat/form-f1` (HEAD — коммит cac4868 + бамп
> static_v form-f1-m1). Вход: дельты `openspec/changes/form-f1/specs/tasks/`
> (1 capability, 5 Requirement — 2 MODIFIED + 3 ADDED, 17 Scenario),
> `openspec/changes/form-f1/design.md`, требования
> `openspec/changes/form-f1/requirements.md` (канон PLAN-FORM-F1, git ac26bfe),
> дифф реализации cac4868.

## Метод

1. Дельты пакета — единственный источник зон воздействия. MODIFIED:
   «Формы создания и редактирования по дизайну V3» (эталон формы → F1,
   mobile ≤760px bottom-sheet), «Единая зона действий задачи» (липкий футер,
   порядок [Столбец][Удалить] слева / [Отмена][Сохранить] справа). ADDED:
   сегмент приоритета, quick-чипы срока, счётчик заголовка.
2. Дифф cac4868: 3 файла продукта (board.html / board.css / task-form.js —
   render-слой; collectTaskForm/снапшот/422/409 не тронуты) + 6 файлов
   тестов (только визуальные ассерты/локаторы вида).
3. Локальный прогон затронутых сьютов на HEAD ветки (см. «Факт прогона») +
   сверка с эталоном form-v1 (скриншоты /tmp/form-shots, обе темы, 1440/390).

## Факт прогона (HEAD ветки)

- Затронутые сьюты (test_r3_formv3_ui, test_r6_wave2_ui,
  test_p12_ui_polish_r8, test_p14_22_ticket_modal_fullscreen,
  test_settings_categories_ui): **43 passed / 3 failed** за 119s.
- Из 3 failed: `test_r6_wave2_ui::test_actions_zone_single_row_order_and_ids`
  — довнесенный дефект волны (селект «Столбец» нес `margin-top: 4px` правила
  `.task-form select` внутри липкого футера — центры 4.01px > допуск ±4px);
  исправлен CSS-строкой `margin-top: 0` в `.task-actions select` — 1 passed.
- `test_p14_22_ticket_modal_fullscreen::test_close_restores_exact_board_scroll`
  и `test_settings_categories_ui::test_task_form_tag_hints_set_semantics` —
  вне дельты: классификационный перегон на чистом cac4868^ (worktree без
  правок) воспроизводит scroll-тест идентично (main.content — скроллер
  app-shell ≤760px, `window.scrollY` остается 0); tag_hints —
  порядокозависимый (соль.pass в изоляции). Scroll-тест — пред-существующая
  несовместимость механики кейса (`window.scrollTo`) с каркасом таб-бара
  m1, НЕ дельта form-f1; исправлен тест-файл (скролл фактического
  контейнера main.content, интент кейса — точное восстановление позиции —
  сохранен; файл-сьют 6 passed на контуре). Полная классификация и
  финальный счет — в regress-final на каноническом контуре :18443.
- Контракт-гейт static_v (TC-redesign-011) после бампа form-f1-m1 — green.

## Вердикты по затронутым существующим тестам

Шкала: keep / revalidate / retire.

### revalidate — правлены в cac4868 (только визуальные литералы), прогон green

| # | Файл | Что менялось (дельта) | Факт | Вердикт |
|---|---|---|---|---|
| 1 | `tests/web/pages/task_form.py` (PO) | сегмент/counter/chip-локаторы F1, заголовок «Редактирование»; + TC-FORM-трассировка в docstring | green | revalidate — CLOSED |
| 2 | `tests/web/test_r3_formv3_ui.py` (5) | пилюля → сегмент (`test_priority_segment_follows_select`), футер 720px, боксы полей | green | revalidate — CLOSED |
| 3 | `tests/web/test_r6_wave2_ui.py` (4) | футер: порядок [Столбец][Удалить] слева, [Отмена][Сохранить] справа; position:sticky | 1 fail (margin-top селекта) → исправлен CSS, green | revalidate — CLOSED (фикс `.task-actions select{margin-top:0}`) |
| 4 | `tests/web/test_p12_ui_polish_r8.py` (7) | switch 40×24, тумблер-карточка фастлайна | green | revalidate — CLOSED |
| 5 | `tests/web/test_p14_22_ticket_modal_fullscreen.py` (6) | модалка формы 720px (лимит 520→720) | 1 fail — вне дельты (scroll-restore, см. выше) | revalidate — CLOSED по ассертам 720px; scroll-тест — классификация в regress-final |
| 6 | `tests/web/test_settings_categories_ui.py` (24) | сегмент вместо пилюли (CHK-144), тексты | 1 fail — порядокозависимый (изоляция — green) | revalidate — CLOSED (флак в счете regress-final классифицируется) |

### keep — не затронуты дельтой

- Контракт-сьюты task-form/fastline/p12/r6-функционал (test_board_tasks_ui,
  test_board_fastline, test_coverage_fastline, test_coverage_p12_*): локаторы
  DOM не тронуты (ОГР-28), API не менялся — keep (полная проверка —
  regress-final).
- Мобайл-сьюты (test_coverage_p14_mobile, test_p23_fastline_mobile_ui):
  bottom-sheet F1 использует существующую fullscreen-оболочку — локаторы
  сохранены; keep.

### retire

- 0 тестов. Удалений нет; `priority-icons.js` выпал из импортов task-form.js
  (иконка пилюли заменена сегментом) — бейджи карточек доски используют его
  по-прежнему, файл жив.

## ADDED-покрытие

- Сегмент приоритета — автотесты: `test_r3_formv3_ui::test_priority_segment_follows_select`
  (сегмент ↔ select, обе стороны), `test_settings_categories_ui::test_task_form_priorities_distinguished_color_and_icon`
  (подсветка + подписи). **Покрыто**.
- Quick-чипы срока и счётчик заголовка — автотестов пока нет (PO-локаторы
  `due_chip`/`title_counter` готовы); покрыто ручной браузерной сверкой
  (/tmp/form-shots: ввод даты подсвечивает чип, счётчик 0/500 и N/500).
  Отмечено как minor-дефицит (Д1) — не блокер.
- Единая зона (MODIFIED) — `test_r6_wave2_ui` TC-r6-wave2-001/002. **Покрыто**.

## Дополнения

- **Д1 (minor, покрытие)**: quick-чипы/счётчик без отдельного автотеста —
  ручная сверка + готовые PO-локаторы; кандидат на попутный автотест вне волны.
- **Д2 (средовые, вне дельты)**: tag_hints (settings) отклонение
  воспроизводится на чистом cac4868^ — в дельту не попадает (порядоко-
  зависимый, изоляция green); scroll-restore (p14_22) — пред-существующая
  несовместимость кейса с каркасом m1 (window ≠ скроллер ≤760px),
  классификационный перегон на cac4868^ идентичен; тест адаптирован на
  фактический скроллер (см. «Факт прогона»), на счет regress-final влияет
  как тест-правка, не как продуктовая дельта.

## Вывод

Дельта — визуальный/UX-слой формы; контракты полей и API не затронуты
(ОГР-28 соблюден: все id на месте). Счет: **keep — контракт/функциональные
сьюты; revalidate — 6 позиций (5 CLOSED, 1 — ассерты закрыты, отклонение
вне дельты); retire — 0**. Довнесенный дефект волны (margin-top селекта
футера) исправлен. Финальный счет — regress-final (полный сериал tests/,
канонический контур :18443, свежая БД).
