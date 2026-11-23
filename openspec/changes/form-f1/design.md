# Design: form-f1 — архитектура формы «Быстрый поток» (эталон form-v1)

## Принцип: контракты сохранены, меняется только рендер

Единственный источник правды для значений полей — существующие нативные
элементы формы. Визуальные компоненты F1 — отображение поверх них:

| Компонент F1 | Нативный элемент (источник истины) | Контракт |
|---|---|---|
| Сегмент приоритета `#task-priority-segment` (3 × `.seg[data-priority-value]`) | нативный select `#task-priority` — скрытый (`opacity: 0`, во всю ширину поля, `z-index` поверх не нужен: сегмент под ним) | value/collectTaskForm/e2e `select_option` не тронуты (FR-34, ОГР-28) |
| Quick-чипы срока `#task-due-chips` (3 × `.qchip[data-due-quick]`) | нативный date-инпут `#task-due-date` | name/date-формат ISO, коллект не тронут |
| Счётчик `#title-counter` | input `#task-title` (maxlength=500) | только отображение `N/500` |
| Липкий футер (position: sticky) | `#task-move-select`, `#task-form-submit`, `#task-form-cancel`, `#task-delete-button` (в `#task-actions`) | id-контракт DOM не изменен (ОГР-28, FR-63) |

## Синхронизация (task-form.js, только render-слой)

- `renderPrioritySegment()` — единственная функция состояния сегмента:
  `.is-checked`/`aria-pressed` по value селекта. Клик по `.seg` пишет value в
  select (источник истины) и перерисовывает сегмент; programmatic-записи
  (`fillTaskForm`, `setPriorityLock`) вызывают рендер явно; `change` селекта —
  тоже. Пустой value («—», создание) — ни одна кнопка не подсвечена
  (mockup-дефолт «средний» НЕ переносится: менял бы payload, priority: null
  легален). Disabled-селект (fast line закрепила приоритет, FR-27) дизаблит
  кнопки сегмента — инвариант disabled.
- `renderDueChips()` — подсветка `.is-checked` по совпадению даты чипа
  (`quickChipDate(0|1|7)`) со значением `#task-due-date`; ручной ввод/календарь
  перерисовывают чипы через listeners `input`/`change`. Дата вне быстрых
  значений — ни один чип не подсвечен.
- `updateTitleCounter()` — на `input` названия и в `fillTaskForm`.
- collectTaskForm / снапшот «грязной» формы / 422 / 409 — НЕ тронуты (дифф
  cac4868 не содержит правок этих функций).

## Ошибки и валидация — прежние

Инлайн-ошибки — существующие слоты: `#task-form-error` (422/409/сеть) и
`#task-category-error` (жесткая валидация категории). Красная рамка поля —
CSS-класс на существующем `.field`-боксе. Новой суммы ошибок нет (PLAN §Состав).

## Верстка (board.html + board.css)

- Десктоп-модалка 720px (эталон create.html/edit.html); поля — боксы на
  `--color-raised` (эталон `.input`), фокус-кольцо канона A.
- Категория + исполнитель в одну строку (`.f1-duo`), ≤760px — столбиком.
- Фастлайн — тумблер-карточка (switch 40×24) с подписью гейта; 409 «fast line
  занята» — в `#task-form-error` как раньше.
- Подсказка под названием — НЕЙТРАЛЬНЫЙ цвет (правка дефекта мокапа: красный →
  muted).
- Липкий футер: слева [Столбец ▾][Удалить] (edit; «Удалить» внутри режимной
  части `#task-actions` — в создании блок скрыт), справа [Отмена][Сохранить].
- Мобильный ≤760px — bottom-sheet по эталону: грейб, поля стёком, липкий
  футер, тач-таргеты ≥44px, font-size полей ≥16px (NFR-24), title 18px.
- Заголовок режима редактирования — «Редактирование» (эталон edit.html).

## Стилевая дисциплина

Компоненты F1 — только на `var(--*)` канона A (обе темы, dark + light);
rgba/hex-литералов вне токенов нет (гейт дизайна); анимации — через
`prefers-reduced-motion`. `static_v` бампится (`form-f1-m1`,
backend/app/pages.py — единственная точка, гейт IR-03).

## Селекторы / data-атрибуты (стабильные)

`#task-priority-segment`, `.seg[data-priority-value="low|medium|high"]`,
`#title-counter`, `#task-due-chips`, `.qchip[data-due-quick="today|tomorrow|week"]`,
`.f1-native`, `.f1-duo`, `.is-checked`, `aria-pressed`. Контракт-тесты цепляются
по ним (tests/web/pages/task_form.py: `segment_loc`, `seg_loc`, `checked_seg`,
`counter_loc`, `due_chip_loc`).

## Тесты

Контракт-тесты task-form/fastline/p12/r6 — локаторы не менялись; правлены
только визуальные ассерты (6 файлов, cac4868). Прогон формы + fastline +
мобильные сьюты перед regress-final (полный сериал tests/ на контуре :18443).
