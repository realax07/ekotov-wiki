# Change ID

`form-f1`

## Why

Заказчик утвердил вариант F1 «Быстрый поток» из `design-forge/extra/form-v1/`
(create.html + edit.html — десктоп-модалка 720px + мобильный bottom-sheet).
Форма создания/редактирования задачи переверстана по мокапу (канон PLAN-FORM-F1,
git ac26bfe), контракты полей и логика отправки/валидации (422 категория, 409
фастлайн) сохранены дословно — меняется только рендер/синхронизация. Реализация:
коммит cac4868 на ветке `feat/form-f1`.

## What Changes

| Capability | Тип дельты | Requirement (заголовок НЕ меняется — машинное слияние по заголовку) | Суть |
|---|---|---|---|
| `tasks` | MODIFIED ×1 | Формы создания и редактирования по дизайну V3 | эталон формы — мокап F1 (form-v1): боксы полей на raised, модалка 720px, mobile bottom-sheet ≤760px; токены канона A/V3 сохранены |
| `tasks` | MODIFIED ×1 | Единая зона действий задачи | липкий футер: [Столбец][Удалить] слева (edit), [Отмена][Сохранить] справа; id-контракт DOM не изменен (ОГР-28) |
| `tasks` | ADDED ×1 | Сегмент приоритета поверх нативного select (F1) | сегмент из 3 кнопок синхронизирует скрытый select #task-priority (источник истины); disabled-инвариант FR-27 |
| `tasks` | ADDED ×1 | Quick-чипы срока (F1) | «Сегодня/Завтра/+7 дней» пишут дату в нативный #task-due-date; дата — источник истины |
| `tasks` | ADDED ×1 | Счётчик длины заголовка (F1) | #title-counter 0/500 у названия, автофокус; только отображение |

Сопровождающее техническое изменение: бамп `static_v` → `form-f1-m1`
(backend/app/pages.py, гейт IR-03 — дифф трогает templates/static).

Сквозная нумерация: номера FR не переиспользуются, новые требования в ADDED без
номеров — конфликтов нет.

## Impact

- Код: `frontend/templates/board.html`, `frontend/static/css/board.css`,
  `frontend/static/js/board/task-form.js`, `backend/app/pages.py` (static_v).
  API, бэкенд-логика, openapi-контракты — без изменений. Комментарии (живают в
  карточке просмотра) не затронуты.
- Тесты: правлены только визуальные ассерты 6 файлов (cac4868: task_form PO,
  test_p12_ui_polish_r8, test_p14_22_ticket_modal_fullscreen, test_r3_formv3_ui,
  test_r6_wave2_ui, test_settings_categories_ui); контракт-тесты task-form /
  fastline / p12 / r6 и мобайл-сьюты — без правок логики.
- Спеки: дельты этого пакета (2 MODIFIED + 3 ADDED в `tasks`); остальной объем
  (доска, фастлайн, валидация) спецификацией не затрагивается.
- Тест-модель: `test-model/impact/form-f1.md`, approved-кейсы
  `test-model/approved/form-f1/`, ревью `test-model/reviews/form-f1/`,
  regress-final `test-model/regress/form-f1/` (полный сериал tests/ на
  каноническом контуре :18443).
