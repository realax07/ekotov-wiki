# Review form-f1-001: ревью диффа cac4868 (форма F1 «Быстрый поток»)

- Ревьюер: code-reviewer (самостоятельная проверка диффа; отчет Dev-агента
  по форме не прикладывался — источники: дифф cac4868 построчно, эталон
  design-forge/extra/form-v1, PLAN-FORM-F1).
- Дата: 2026-11-23. Ветка `feat/form-f1`.
- Объем: frontend/templates/board.html (+225 строк дельты), board.css
  (+503/-…), frontend/static/js/board/task-form.js (+157/-…), 6 тест-файлов.

## Контракты (ОГР-28) — сохранены

- Все id/name на месте: `#task-form-overlay`, `#task-title`,
  `#task-priority` (нативный select, скрытый `.f1-native`: opacity:0 во всю
  ширину — bounding box непустой, e2e `select_option` жив), `#task-category`,
  `#task-assigned`, `#task-due-date`, `is_fast`, `#task-form-error`,
  `#task-category-error`, `#task-form-submit/cancel`, `#task-delete-button`,
  `#task-move-select`, `#task-actions`, `#task-form-heading`.
- `collectTaskForm`, снапшот «грязной» формы, обработка 422/409 — диффом
  не тронуты (проверено чтением дельты task-form.js: изменения только
  render-функции и listeners).

## Найдено и исправлено

1. **Дефект волны (исправлен в этой ветке):** `#task-move-select` в липком
   футере наследовал `margin-top: var(--space-05)` правила
   `.task-form select` — селект смещен на 4px вниз относительно кнопок
   (`test_r6_wave2_ui::test_actions_zone_single_row_order_and_ids` red,
   центры 4.01 > ±4px). Фикс: `margin-top: 0` в `.task-actions select`
   (board.css). Тест green.

## Замечания (без действий)

- `priority-icons.js` выпал из импортов task-form.js (пилюля → сегмент) —
  корректно: бейджи карточек доски импортируют его независимо.
- Сегмент: пустой value («—», создание) сознательно не подсвечивает
  «Средний» — комментарий в коде фиксирует мотив (payload `priority: null`
  легален); соответствует дельте ADDED.
- Кнопки сегмента/чипов — `type="button"` (submit-риск снят), вложенных
  форм нет (комментарий в board.html «вложенные формы в HTML запрещены» —
  проверено по разметке).

## Вердикт: approve

approve — контракты сохранены, найденный дефект футера исправлен в ветке.
