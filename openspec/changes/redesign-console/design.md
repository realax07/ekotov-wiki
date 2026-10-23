# Design: redesign-console

## Источник правды по визуалу

Утвержденные Заказчиком мокапы (PR #242, базлайн b5a1475, фиксация —
design/redesign-pro/README.md § «Утверждение направления (2026-10-23)»):

- `design/redesign-pro/tokens-console.html` — ЕДИНЫЙ ИСТОЧНИК токенов (значения
  переносятся в `app.css :root` дословно, без «улучшений»).
- `design/redesign-pro/board-console.html` — эталон каркаса, доски, фастлайна,
  wiki-фрагмента, мобильной раскладки, доступности.

После переноса прод-источником токенов становится `frontend/static/css/app.css`
(J47 сохраняет смысл: один прод-источник); design/tokens.html V3 архивируется
вместе с пакетом.

## Приемы техноязыка «Пульт» (итерация 2, high-tech / mission-control)

1. **HUD-уголки** — класс-паттерн `.hud::after`: 8 градиентных отрезков 12×1px /
   1×12px по углам панели, цвет `--hc` (по умолчанию `--p-border-2`, на
   фастлайне — янтарь). Применяется к панелям: фастлайн, колонки, спойлер,
   карточки-панели login/settings.
2. **Glow** — тонкое свечение ТОЛЬКО на сигнале и активе: `--glow-amber`
   (фастлайн, кнопка «Новая задача» hover, fast-карточка), `--glow-cyan`
   (активный пункт навигации, открытый спойлер, focus-ring). Неон/декор — запрещен.
3. **Фоновая микро-сетка** — `--texture-grid` (1px линии, ячейка 32px, кратна
   8px-сетке) на фоне страницы; глубина — ступенями фона 000→300, тени минимальны.
4. **LED-статусы** — точки 6–8px с box-shadow свечением: бренд (teal), колонки
   (t500 ожидает / amber в работе + blink / teal выполнено), readout заголовка,
   статусы строк таблицы, fastline-mark (blink 2s step-end).
5. **Микро-лейблы** — mono 10–11px, uppercase, `--tracking-micro` (.14em):
   SYS/FST/CODE-метки (`.micro`, `.fastline-mark`, `.col-head .code`, `.wiki .path`,
   `.brand-sub`).
6. **Терминальные readouts** — mono-строка состояния в pagehead («SYS NOM · дата ·
   ACT N · DONE N»), T-отсчет фастлайна, uptime-колонки таблиц, счетчики колонок.
7. **Роли акцентов** — amber #f0b45c = сигнальный цвет ФАСТЛАЙНА (единственный);
   cyan #4fd8eb = ТОЛЬКО актив/фокус (aria-current, focus-ring, selection, open
   spoiler); teal/coral/violet — только статусы/приоритеты; градиенты — только
   на данных (трек отсчета фастлайна amber→cyan).

## Технические решения

### D1. Токены (деталь реализации дельты design-tokens)

- Блок `:root` `app.css` заменяется на снимок `tokens-console.html`: примитивы
  `--p-*` консольные, семантические имена сохраняются (`--color-bg-page`,
  `--color-accent`, `--fastline`, `--priority-*`…), аддитивно добавляются
  `--accent-cyan`, `--glow-amber`, `--glow-cyan`, `--grid-line`, `--texture-grid`,
  `--font-family-data`, `--tracking-caps`, `--tracking-micro`, `--focus-ring` (cyan),
  `--speed-fast: 140ms`, `--speed-modal: 200ms`, `color-scheme: dark`.
- Запрещено: новые hex-значения вне токенов во всех CSS фронта; наследуемые
  из V3 примитивы `--p-paper-*`, `--p-ink-*`, `--p-clay-*`, `--p-blue-*`,
  `--p-red-*`, `--p-olive-*`, `--p-amber-700` — удаляются НЕ в 1.1, а в конце
  ЭТАПА 2 (задача 2.7): в 1.1 они сохраняются под новым блоком как
  deprecated-алиасы с исходными V3-значениями (комментарий «deprecated,
  удалить в 2.7»), т.к. board.css/wiki.css/gallery.css мигрируют только
  в волнах 2.2/2.3/2.5 — без алиасов промежуточные сборки сломаны
  (var() без значения). Гейт 1.1 — grep по app.css: 0 вхождений V3-примитивов
  ВНЕ блока deprecated-алиасов; финальный контракт «ни один селектор фронта
  не ссылается на отсутствующий токен» проверяется full-tree grep-ом
  (`frontend/static/css/**` + `frontend/templates/**`) в задаче 2.7.
- V3-подсветка `<mark>` wiki-дерева получает новый токен (amber-подложка
  на dark: фон `--p-amber-900`, текст `--p-amber-400`).

### D2. Каркас и DOM-хуки (ОГР-28)

- Раскладка `.layout` = grid 232px + 1fr; сайдбар = 9 пунктов (Доска, Wiki,
  Галерея, Видео, Погода, Поиск, Игры в основной группе; Настройки, Профиль —
  в футере сайдбара), inline-SVG 16px `stroke="currentColor"`, бренд с LED,
  kbd-подсказки в футере. Блок kbd-подсказок — декоративный (`aria-hidden`),
  перечисляет ТОЛЬКО хоткеи, реально обрабатываемые глобальным JS на базлайне;
  глобальных обработчиков `n`/`/`/`f` в JS нет, «новые функции» — out of
  scope (proposal), поэтому подсказки к ним не отображаются: появление
  хоткеев — отдельный change-пакет (до него kbd-футер не рендерится либо
  пуст). Ложный аффорданс в проде запрещен.
- СОХРАНЯЮТСЯ: классы-хуки `.nav-item`, `.nav-item-<page>` (вкл.
  `.nav-item-monitoring`, `.nav-item-settings`), `.sidebar`, `.sidebar-footer`,
  `.sidebar-backdrop`, `.burger`, класс `sidebar-open` на `<body>`,
  id `#sidebar`, `#burger-button`, aria-атрибуты (`aria-current="page"`,
  `aria-expanded`, `aria-controls`), все DOM-id форм и модалок. Меняются
  ТОЛЬКО стили и декоративная разметка (LED-точки, kbd-футер — новые элементы
  aria-hidden).
- ПОЛНЫЙ список JS-хуков, на которых держится фронтовый JS (grep
  querySelector/getElementById/classList/closest по `frontend/static/js/`,
  базлайн), — переименование любого из них запрещено (ОГР-28):
  - каркас/сайдбар: `.nav-item*`, `.sidebar-backdrop`, `.sidebar-footer`,
    `#sidebar`, `#burger-button`, класс `sidebar-open`;
  - доска/фастлайн: `.task-card`, `.task-card-fast`, `.task-card-*`
    (users/assigned/unassigned/creator/header/title/meta), `.board-column`,
    `.board-column-title`, `.board-dots`, `#board`, `.fastline-column`
    (+ `data-fastline-stage`), `#fastline`, `.fast-row`, `.col-target`,
    `has-fast`, `.dragover`, `.drop-target`, `.drop-forbidden`,
    `#fastline-add-button`, `#fastline-blocked-hint`;
  - wiki/rich: `.wiki-layout`, `.wiki-content`, `.wiki-breadcrumb`,
    `.breadcrumb a`, `aside.wiki-tree`, `#wiki-search`,
    `#wiki-search-results`, `.wiki-toolbar .wiki-create`, `.spoiler-title`,
    `.spoiler-title-input`, `.spoiler-body`, `.codeblock-head`,
    `.codeblock-nums`, `[data-block]` (spoiler/code/tabs), `.tab-add`,
    `.tab-close`, `.tab-rename`, `.rich-active`, `.rich-compact`,
    `#wiki-article`, `#wiki-editor`, `#wiki-history*`;
  - галерея: `.g-card`, `.g-card-title`, `#gallery-grid`, `#lightbox-overlay`,
    `lb-*` (id контролов лайтбокса);
  - видео: `.v-card`, `.v-card-title`, `video-*`/`player-*` id-хуки;
  - поиск/настройки/прочее: `.result-item`, `.filter-count`, `.category-name`,
    `.category-actions`, `.option`, `.option-add`, `.tbl-col-ops`,
    `.tbl-row-ops`, `.img-pick-item`, `.img-disk-pane`, `.task-view-head`,
    `.task-view-body`.
- Проверка волн 2.2/2.3 (и каждой dev-волны): после правки шаблонов/CSS все
  перечисленные JS-селекторы зоны резолвятся (прогон grep-селекторов по
  итогам волны) — нецветовые тесты это ловят лишь частично, явный чек
  обязателен.
- Активный пункт: `aria-current="page"` → фон bg2 + cyan-рамка 45% + cyan-LED
  справа; иконка cyan.

### D3. Фастлайн

- Сигнальный канал: рамка amber + подложка `--p-amber-900` + `--glow-amber` +
  HUD-уголки amber; FST-микро-лейбл с LED-blink; задача + человекочитаемый
  комментарий (small, t600); T-отсчет до срока mono справа; трек отсчета —
  полоса 2px с градиентом amber→cyan (доля = прошедшая часть окна до срока).
  Поведение (одна fast-задача, перенос, комментарий) — без изменений (спека
  fastline).

### D4. Favicon

- Перекраска существующего inline SVG data-URI (base.html): фон `#0e1621`,
  документ `#f0b45c`, детали `#172335`; cache-маркер `?v=` внутри data-URI —
  бамп (правило base.html: ЛЮБОЕ изменение иконки = бамп маркера).

### D5. static_v

- `backend/app/pages.py`: `templates.env.globals["static_v"] = "redesign-1"`
  (единственная правка бэкенда; комментарий-историю бампов сохранить-продолжить).

### D6. Тесты

- Сломавшиеся V3-ассерты правятся на значения «Пульта» (смонтированы в
  impact.md; задача 3.4). Свойства проверок (цвет из токена; AA; токен-дисциплина)
  не меняются. Новые автотесты — TC-redesign-NNN по дельтам (кейсы ДО кода:
  qa_author + qa_case_reviewer).
- Контраст: программная проверка всех текстовых пар ≥ 4.5:1 при переносе
  токенов и в QA (прецедент README redesign-pro: 20/20 пар).

### D7. Доступность

- `:focus-visible` → `--focus-ring` (двойное кольцо bg0+cyan + glow);
  `::selection` cyan; `prefers-reduced-motion: reduce` отключает blink/transition;
  skip-link первым элементом body («К основному содержимому»), видимый при фокусе;
  hit-targets ≥ 44px на тач-размерах (мобильная раскладка).
