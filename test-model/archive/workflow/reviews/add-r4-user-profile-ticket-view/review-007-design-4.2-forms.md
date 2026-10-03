# review-007-design — task 4.2 (02b63fe), закрытие DEF-005 — статическая сверка с мокапом V3

Дата: 2026-09-30. Ревьюер: design_validator (E13). Охват: формы задачи (create/edit, board.html + board.css) vs design/form-style-v3.html. Стенд не поднимался (статическая сверка по контракту задачи 4.2).

## 1. Токены (:root app.css vs :root мокапа)

Все примитивы/семантика/spacing/геометрия/тени/типографика/фокус-кольцо совпадают дословно:
paper-050/100/200, ink-900/600, clay-600/050, red-700/050, olive/amber/blue-700,
bg-surface #fffdf9, priority-*, --radius-field 6px, --radius-card 10px,
--shadow-modal 0 16px 40px rgba(61,54,48,.18), --shadow-soft, --font-family(display),
font-size 14/13/11, --focus-ring 0 0 0 3px rgba(168,67,44,.35), speed-fast/modal.

Дополнения app.css относительно мокапа (расширение, не противоречие):
--p-clay-700 #93391f (hover акцента — мокап .btn-primary:hover хардкодит тот же #93391f,
здесь выведен в токен --color-accent-hover: корректнее мокапа);
--p-blue-050 #eef2f6 / --p-blue-200 #c9d6e2 (мокап хардкодит их в .fast-row);
--priority-*-soft (мокап хардкодит #f6ebe8/#f4ecdf/#eff1e4);
--status-success (вне охвата форм).

**Расхождений токенов не найдено.**

## 2. Сверка зон формы

| Зона | Статус | Примечание |
|---|---|---|
| Заголовок формы | OK | h2 22px Georgia 400 (мокап .modal-title — идентично); место под крестик 40px |
| Поля (нижняя линия) | OK | border-bottom 2px, border-radius 0, padding как мокап; hover → border-strong; focus-visible → accent + 0 1px 0 accent; textarea сверх мокапа (мокап покрывает только text/select/date) — консистентно с приемом |
| Чипы тегов | OK | .chips/.chip: bg-subtle, 999px, 3px 10px, 12px — дословно мокап; крестик: hover → text-primary (мокап hover не задает — авторское, не противоречит), focus-visible → focus-ring + border-radius 50% — как мокап |
| Приоритет (пилюля) | OK с нюансом | реальзовано как select в .priority-field-pill (мокап — три radio+pill). Пилюля: border-default/999px/bg-surface, hover→border-strong, focus→accent+focus-ring, цвет по :has(:checked) — цвета priority-* и soft-фоны совпадают с мокапом; SVG ↓/=/↑ 14px currentColor; disabled opacity .45 — как мокап. Компромисс осознанный (контракт task-form.js/e2e), задокументирован в CSS; расхождение структуры (select vs radio-group) — minor, не противоречит визуальному эталону |
| Fast line | OK | .fast-row: blue-050/blue-200, radius-field, 13px; чекбокс 16px accent-color blue-700 — дословно мокап. focus-visible чекбокса: у мокапа — на самом чекбоксе (focus-ring), в реализации — focus-within на label (task-form-checkbox); визуальный результат эквивалентен (кольцо вокруг ряда), minor |
| Кнопки | OK | первичная: accent/white/shadow-soft, hover clay-700 — как мокап (токен вместо хардкода); вторичные (включая #task-delete-button — дельта 4.2): transparent + border-strong, hover bg-subtle, focus-visible focus-ring, geometry .btn (padding 10px 24px, 999px) — дословно .btn-secondary мокапа. Покрытие #task-delete-button — в общем и hover-, и focus-visible-селекторах: подтверждено (board.css 493-520) |
| Подсказки | OK | .hint 12px secondary — как мокап; .req — color: status-error — как мокап; .field-error/.form-error — color status-error (мокап .error-text 12px flex — здесь block; текст/цвет те же, minor) |

## 3. Негативный чеклист DEF-004 — все интерактивные элементы форм (templates/board.html)

| Элемент | Селектор V3 | hover | focus-visible | Статус |
|---|---|---|---|---|
| #task-form-close (.modal-close) | .modal-close | bg-subtle | focus-ring | OK |
| #task-title (text) | .task-form input[type=text] | border-strong | accent+подчерк | OK |
| #task-description (textarea) | .task-form textarea | border-strong | accent+подчерк | OK |
| #task-priority (select) | .priority-field-pill select | pill hover | pill focus-within ring | OK |
| #task-category (select) | .task-form select | border-strong | accent+подчерк | OK |
| #task-due-date (date) | .task-form input[type=date] | border-strong | accent+подчерк | OK |
| #task-tags (text) | .task-form input[type=text] | border-strong | accent+подчерк | OK |
| #task-is-fast (checkbox) | .task-form-checkbox input | accent-color | focus-within ring | OK |
| .chip button (динамич., task-form.js) | .task-form .chip button | color swap | ring + 50% | OK |
| #task-move-select (select, edit) | .task-form select | border-strong | accent+подчерк | OK |
| #task-delete-button | вторичный контур (4.2) | bg-subtle | focus-ring | OK — дельта 02b63fe подтверждена |
| #task-form-submit | первичная | accent-hover | ring (через .form-actions button) | OK |
| #task-form-cancel | вторичный контур | bg-subtle | ring (через .form-actions button) | OK |
| #comment-body (textarea) | .task-comments textarea | border-strong | accent+подчерк | OK |
| #comment-form submit | вторичный контур | bg-subtle | ring | OK |

Все 15 интерактивных элементов форм покрыты не-дефолтными стилями V3 с hover/focus-visible. DEF-005 закрыт.

## 4. Элементы ВНЕ форм с дефолтным оформлением

- **#task-detail-close («Закрыть», view-модалка, board.html:207)** — не входит ни в один селектор вторичных кнопок (#task-form-cancel, #task-delete-button, #task-detail-actions button, .comment-form/.task-comments submit). Не покрыт никаким CSS-правилом → браузерные дефолты (серый фон, прямой угол, дефолтный border). Тот же урок DEF-004/FR-48, что и #task-delete-button до 4.2. **major.**
- **#task-edit-button** имеет class="btn btn-primary", но **классы .btn/.btn-primary нигде в CSS не определены** (подтверждено grep: определения отсутствуют; comment в board.css 468 признает это для #create-task-button, которому стили даны по id). Кнопка «Редактировать» рендерится с браузерными дефолтами. **major.** Прим.: на search.html тот же #task-detail-close; outside scope r4-forms, но тот же дефект.
- Селектор `#task-detail-actions button` — мертвый код: элемента #task-detail-actions нет в разметке (остался от прежнего окна деталей). Не дефект вида, но к очистке (info).

## 5. Вердикт

**deviations** — 2 major (интерактивные элементы вне форм с дефолтным оформлением:
#task-detail-close; #task-edit-button с несуществующими классами .btn/.btn-primary),
3 minor (select вместо radio-group приоритета — осознанный компромисс, задокументирован;
focus чекбокса fast через focus-within на label, а не на чекбоксе; .field-error block vs
.error-text flex — визуально эквивалентно). Формы задачи (охват задачи 4.2) — consistent:
дельта 02b63fe корректна, токены идентичны, все 15 контролов форм покрыты V3.
Major-находки — вне охвата задачи 4.2 (view-модалка/кнопки вне форм), эскалация ПМ/деву.
