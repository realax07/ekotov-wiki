# add-ui-polish-r8 / 2.2 — сверка прод-модалки с утвержденным мокапом

Мокап: design/polish-ticket-modal.html (утвержден 2026-10-06, «По карточке
красиво»). Прод: board.html #task-detail-overlay + task-detail.js + board.css.
Разметку (board.html) волна 2.2 НЕ трогает (зона 2.4) — вся структура окна
строится task-detail.js при рендере.

| Блок мокапа | Класс мокапа | Реализация в проде | Класс прод |
|---|---|---|---|
| Оверлей | .modal-overlay (inset 0, rgba 0.45, flex-start) | есть, скрытие через hidden | .modal-overlay (existing, rgba 0.4) |
| Окно | .modal (max-width 640, radius-card, shadow-modal, modal-in) | .modal.task-view | max-width переопределен 640 в .task-view |
| Крестик | .modal-close (40×40, absolute) | #task-view-close | .modal-close (existing) |
| Кикер | .modal-kicker (micro, uppercase, tracking 0.06em) | рендерит task-detail.js в head | .task-view-kicker (новый, стили мокапа) |
| Название | .modal-title (Georgia display, 22px, lh 1.25) | #task-detail-title (id сохранен, ОГР-28) | .task-view h2 → стили мокапа |
| Бейджи | .badge-row > .badge (цвет+иконка+текст) | рендерит task-detail.js | .badge-row/.badge/.badge-priority-*/.badge-status/.badge-fast (новые) |
| Описание | .section-label + .modal-desc (lh 1.55) | #task-detail-attrs, ряд «Описание» | .task-view-desc (новый) |
| Признаки | .attr-grid (2 колонки, .attr карточки bg-subtle) | #task-detail-attrs (dl рендерится JS) | .task-view-attrs → гриды мокапа; dt/dd внутри .attr |
| Теги | .tag-chips > .tag-chip (пилюли) | рендерит task-detail.js | .task-view-tags/.tag-chip (новый) |
| Люди | .people-row > .person (аватар-инициалы 28px + имя + роль) | assigned/creator при наличии в ответе API | .task-view-people/.person/.person-avatar (новый) |
| Комментарии | .section-label «Комментарии · N» + .comment (.comment-head: автор bold · дата) | #task-comments-list, рендер task-detail.js | .task-view-comments-label; .comment-head/.comment-author/.comment-sep/.comment-date — классы мокапа (может добавить волна 2.3) |
| Футер | .modal-foot (justify-end, border-top) + .btn-primary | .task-view-actions (существующие кнопки) | .task-view-actions → стили футера мокапа; «Редактировать» — btn-primary-вид |

Read-only: ни одного input/textarea/select в #task-detail-overlay
(TC-view-102/101 продолжают это ассертить). Единственное действие —
«Редактировать» (Д-9). DOM-id не переименованы (ОГР-28):
task-detail-title, task-detail-archive-badge, task-detail-error,
task-detail-attrs, task-comments-list, task-edit-button, task-detail-close,
task-view-close — все на месте.
