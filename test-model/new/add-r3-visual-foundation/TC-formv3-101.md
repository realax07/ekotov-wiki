# TC-formv3-101 — Поля ввода формы оформлены по токенам V3, фокус-кольцо

- **CHK:** CHK-169
- **Change:** add-r3-visual-foundation
- **Источник:** tasks: «Формы создания и редактирования по дизайну V3» (FR-34, зона 2 — поля ввода); Сценарий «Поля ввода оформлены по токенам полей V3»
- **Тип:** поз. | **Приоритет:** Must
- **Среда/предусловия:** web-стенд tests/web; вход owner; открыта форма создания задачи.
- **Шаги:**
  1. Открыть форму «Создать задачу»; для `#task-title` (input), `#task-description` (textarea), `#task-due-date` (input date) прочитать computed: `border-radius`, `border-color`, `background-color`, `font-family`.
  2. `field.focus()` (или click) на `#task-title`; прочитать computed `box-shadow`.
  3. Повторить фокус для `#task-description`.
- **Ожидаемый результат:** у всех трех полей border-radius ненулевой (токен `--radius-*`), рамки/фон — проектные цвета (не дефолтные серые Chromium); при фокусе box-shadow содержит `var(--focus-ring)` (видимое фокус-кольцо, computed ≠ `none`).
- **Тестовые данные:** поля `#task-title`, `#task-description`, `#task-due-date`; токен `--focus-ring`.
