# TC-form-001: Сегмент приоритета синхронизирует нативный select

- **Change:** form-f1
- **Источник:** tasks ADDED — «Сегмент приоритета поверх нативного select (F1)» / Scenario: «Клик по кнопке сегмента синхронизирует select», «Select — источник истины (e2e select_option)», «Пустой приоритет — ничего не подсвечено», «Disabled-инвариант FR-27»
- **Тип:** функциональный UX | **Приоритет:** Must
- **Среда/предусловия:** автостенд conftest (uvicorn app + search), коммит cac4868; Playwright (chromium); контракт fast-line disabled-кейса
- **Шаги:**
  1. Открыть форму создания на /board (автотест `tests/web/test_r3_formv3_ui.py::test_priority_segment_follows_select`, PO `tests/web/pages/task_form.py::TaskForm.priority_seg_button/priority_checked_seg`).
  2. Проверить пустой value: ни одна `.seg` не имеет `.is-checked`; клик «Высокий» (`data-priority-value="high"`) → `#task-priority` value=high, кнопка `.is-checked` + `aria-pressed="true"`.
  3. Программно `select_option("low")` на `#task-priority` → подсветка переходит на «Низкий» (select — источник истины, e2e-контракт select_option жив).
  4. Включить fast-line тумблер (приоритет закреплен, селект disabled) → кнопки сегмента disabled, клик не меняет value; выключить → разблокированы.
- **Ожидаемый результат:** сегмент — только отображение; select — единственный источник значения; payload собирается из селекта как прежде; disabled-инвариант FR-27 соблюден. Автопрогон green на HEAD ветки.
- **Тестовые данные:** сид owner/wife; эталон `design-forge/extra/form-v1/create.html` (.segment).
