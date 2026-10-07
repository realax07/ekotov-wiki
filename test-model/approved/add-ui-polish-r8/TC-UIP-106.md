# TC-UIP-106 — Кнопка настроек: active/focus-visible не смещают текст (bbox-замер в трех состояниях)

- **Change:** add-ui-polish-r8
- **Источник:** navigation Requirement «Навигация через сайдбар» / FR-96 (P12 п.1: нажатие кнопки настроек НЕ смещает текст; состояния на токенах V3); design §1 группа H (причина — изменение ширины/бордера в active/focus; border без изменения ширины, transform запрет); CHK-P12-6
- **Тип:** позитивный / НФТ | **Приоритет:** Must
- **Маркер:** new — кейс с замером bbox в трех состояниях (прецедент геометрии TC-nav-006, `regression/navigation/TC-nav-006.md`); revalidate: TC-nav-006 (test_settings_link_position_bottom_left_near_logout — порог +32px может мигать при svg-иконках 2.4)
- **Предусловия:** nginx-стенд :18443; пользователь owner авторизован; открыта любая страница функционала; сайдбар развернут (viewport ≥ порога сворачивания)
- **Шаги:**
  1. База: `link = page.get_by_role("link", name="Настройки")` (роль зафиксировать в протоколе); `box0 = link.bounding_box()`.
  2. Активное нажатие: `page.mouse.move(cx, cy)` в центр кнопки → `mouse.down()` (active-состояние, без release) → `box1 = link.bounding_box()` → `mouse.up()`.
  3. Keyboard-focus: `link.focus()` (focus-visible-состояние) → `box2 = link.bounding_box()`; зафиксировать computed outline/focus-ring.
  4. Сверка: `box0 == box1 == box2` (x, y, width, height — допуск ±0.5px); текст кнопки не сместился ни в одном состоянии.
  5. Стили: active/focus-состояния — на токенах V3; ширина/бордер НЕ меняются между состояниями, transform отсутствует (группа H design.md).
  6. Прогнать revalidate: TC-nav-006 (позиция у «Выйти», порог +32px — эвристический; при флаппе зафиксировать bbox в REPORT-3.1).
- **Ожидаемый результат:** шаг 4 — bbox текста кнопки «Настройки» идентичен до / во время active-нажатия / при focus-visible (смещения нет, геометрия стабильна); шаг 5 — состояния на токенах V3, без transform и смены ширины; шаг 6 — TC-nav-006 зелен (или флапп задокументирован с числами bbox — не считается падением дельты без доказательства).
