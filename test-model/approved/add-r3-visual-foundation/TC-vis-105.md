# TC-vis-105 — prefers-reduced-motion отключает анимации, функциональность сохранена

- **CHK:** CHK-168
- **Change:** add-r3-visual-foundation
- **Источник:** board: «Визуальные эффекты доски поверх токенов V3» (FR-32); Сценарий «Уменьшение движения отключает анимации»
- **Тип:** НФТ | **Приоритет:** Must
- **Среда/предусловия:** web-стенд tests/web; контекст Playwright с эмуляцией `prefers-reduced-motion: reduce`; вход owner; задача «QAT-vis-rm» в «Ожидает». Механика DnD — dispatchEvent с DataTransfer.
- **Шаги:**
  1. Прочитать computed style карточки: `animation-name`, `transition-duration`.
  2. DnD карточки в «В работе» (dragstart/dragover/drop); во время dragover прочитать computed style столбца (`transition-duration`), после drop — класс карточки.
  3. Дождаться карточки в `[data-status="in_progress"]`.
  4. Повторить dragstart с проверкой `drag-ghost`-трансформации: computed `transform` у карточки с классом `drag-ghost`.
- **Ожидаемый результат:** animation-name = `none`, transition-duration = `0s` (animation/transition отключены `!important`-правилами); подсветка drop-target применяется мгновенно (без перехода), но ПРИМЕНЯЕТСЯ (функциональность сохранена); drag-призрак теряет наклон (transform `none`), полупрозрачность (opacity) остается; drop выполнен — задача в «В работе».
- **Тестовые данные:** задача `QAT-vis-rm`; медиа-фича `(prefers-reduced-motion: reduce)`.
