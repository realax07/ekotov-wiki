# TC-vis-103 — Плавное перемещение карточки по пресету В (без «телепорта»)

- **CHK:** CHK-166
- **Change:** add-r3-visual-foundation
- **Источник:** board: «Визуальные эффекты доски поверх токенов V3» (FR-32, пресет В «Выразительный», ОВ-20); Сценарий «Плавное перемещение карточки по пресету»
- **Тип:** поз. | **Приоритет:** Must
- **Среда/предусловия:** web-стенд tests/web; вход owner; задача «QAT-vis-move» в «Ожидает». Механика DnD — dispatchEvent с DataTransfer (урок architect-ревью).
- **Шаги:**
  1. dragstart/dragover/drop на `[data-status="in_progress"]` (как TC-dnd-101); во время dragover зафиксировать computed style столбца: `background`, `outline`.
  2. Автожидание: карточка в `[data-status="in_progress"] [data-cards]`; затем прочитать computed style карточки: `animation-name`, `animation-duration`, `animation-fill-mode`. (Computed значения `animation-name/duration` читаемы в любой фазе, пока класс с анимацией применен, — срочность чтения не требуется, гонки «успеть за 320 мс» нет.)
- **Ожидаемый результат:** при dragover столбец-приемник подсвечен (background = заливка `--p-clay-050`, outline 2px dashed `--p-clay-600` — класс `drop-target`); после drop карточка отрисовывается с анимацией `v-in` (animation-name `v-in`, duration ~0.32s, fill-mode `backwards`) — видимое перемещение, не мгновенный «телепорт».
- **Тестовые данные:** задача `QAT-vis-move`; классы `drop-target`/`preset-v`; keyframes `v-in`.
