# requirements-redesign-ui-a.md — ТЗ редизайна UI по направлению A «Доска и поток» (ekotov-wiki)

> Статус: **ЧЕРНОВИК Волны 1 (БА) — PLAN-REDESIGN-UI-A.md, Флоу 1** | Автор: ba-агент (glm-5.3) | Дата: 2026-11-21
>
> **Источник.** `PLAN-REDESIGN-UI-A.md` (направление A утверждено Заказчиком: бордо/золото, тёмная база, PT Serif / Golos Text / JetBrains Mono, радиусы 10/18/28); эталоны `design-forge/a/{board,task,kit}.html` + `design-forge/a/tokens.css` (46 CSS-переменных + светлая тема `:root[data-theme="light"]`); дизайн-контекст `design-context/GUIDE.md` (+ `foundations.md`, `parts/`, `compositions/`, `assets/tokens.css`); мокапы экстра-разделов `design-forge/extra/{wiki,gallery,video}/` (утверждены — `APPROVED.md`).
>
> **Суть объема.** Рестайлинг страниц board / task (модалки) / wiki / gallery / video + каркаса base через CSS-токены направления A. **DOM/классы/id/data-атрибуты существующих страниц сохраняются (ОГР-28), функционал JS не трогается, API не трогается.** Единственный новый элемент каркаса — переключатель темы (см. §2.7).
>
> **Характер работ — что НЕ входит.** Контент мокапов (тексты задач «BUG-031…», «Переработать дизайн канбан-доски», статьи, фото) в прод не переносится — это примеры. Топбар мокапа с переключателем досок «Разработка / Контент / Инфра» не переносится (доска одна). Карточка задачи мокапа — отдельная страница; в проде остается read-only модалка `#task-detail-overlay` (мокап задает визуальный язык: meta-таблица, комментарии, деструктив в подвале).

---

## 1. Сохраняемый функционал (полный список FR)

Весь функционал ниже **сохраняется без изменений логики и контрактов**. Рестайлинг затрагивает только визуальный слой (CSS-токены). Источники: комментарии шаблонов, `openspec/specs/*`, код `frontend/static/js/board/*`.

### 1.1 Доска и карточка задачи

| # | Функционал | Якорь в коде / спеке | Статус при рестайлинге |
|---|---|---|---|
| F-01 | Канбан-доска из `GET /api/board`; рендер карточек клиентом (ES-модули `board/`, точка входа `board-init.js`) | `board.html`, openspec `board` «Отображение канбан-доски» | не меняется |
| F-02 | Три неизменяемых столбца «Ожидает / В работе / Выполнено» (ОГР-3); селекторы `[data-status="todo|in_progress|done"]` | `board.html` `#column-*` | не меняется (ОГР-28) |
| F-03 | Столбец «Выполнено» — задачи done **сегодня по МСК**; рендер тем же циклом `cards.js` по `data-cards` | openspec `board` | не меняется |
| F-04 | **Drag&drop**: перенос карточек между столбцами (`POST /{id}/move`, один POST на перенос); визуальные состояния `drop-target` (столбец-приемник), `drag-ghost`, `drop-forbidden`; hover-подъем −4px с микро-масштабом (пресет В `preset-v`); анимация появления карточек `v-in`; `prefers-reduced-motion` отключает анимации, функцию сохраняет | `cards.js`, `test_r3_vis_ui.py`, `test_r3_dnd_ui.py` | классы-состояния не меняются; их вид переписывается токенами A |
| F-05 | Быстрое действие «Выполнено» на карточке (`task-quick-done`) — тач-путь переноса в done | `cards.js`, `dev_smoke_p14_21_board_swipe.py` | не меняется |
| F-06 | **fastline-гейт (P23)**: зона FASTLINE над канбаном, 3 столбца-этапа = существующий `status` (`data-fastline-stage`, НЕ `data-status`); не более одной fast-задачи в активных статусах; кнопка `#fastline-add-button` — гейт (disabled + чип `#fastline-blocked-hint` при занятой зоне, ставит `cards.js` из последнего `GET /api/board`); 409 «fast line занята» → текст в `#task-form-error`; в edit-форме чекбокс fast заблокирован чипом `#task-is-fast-gate`; fast-задачи ТОЛЬКО в зоне, обычные ТОЛЬКО в канбане (разделение по `is_fast`); цветовая кодировка DnD/блокировки; пустые столбцы зоны — без подсказок (ОВ-3); мобильная укладка ≤480px — свайп-паттерн канбана (82vw, scroll-snap) | openspec `fastline`, `p23-fastline`; `board.html` `#fastline` | не меняется; янтарная сигнализация зоны переокрашивается на золото A (`--color-accent` — семантика «фастлайн = золотая линия штаба» мокапа совпадает) |
| F-07 | Форма создания/редактирования задачи `#task-form` (7 признаков): title обязателен (UI-валидация до отправки, `maxlength=500`), description (авто-высота, `auto-textarea.js`), priority (нативный select в пилюле `.priority-field-pill`, `:has(:checked)`; иконка `#task-priority-pill-icon` из `priority-icons.js`; fast→high lock + disabled), category (select из `GET /api/categories`), исполнитель (`GET /api/users`, nullable), due_date (`<input type="date">`), tags | `board.html`, `task-form.js` | не меняется |
| F-08 | **Валидация формы**: category 422 жесткой валидации → подсветка `field-invalid` + текст в `#task-category-error`; ошибки формы в `#task-form-error`; 422 лимитов и «fast line занята» — те же узлы | `task-form.js`, openspec `categories` | не меняется |
| F-09 | **Комментарии**: `GET/POST /api/tasks/{id}/comments` — в edit-форме (`#task-comments`, `#comment-form`, `#task-form-comments-list`) и в view-модалке (`#task-comments-list`); удаление своего — по факту API | `board-init.js`, `task-detail.js` | не меняется |
| F-10 | Категории/теги/сроки на карточке: `task-card-meta` (category, tags, due, просроченность — красным); приоритет — бейдж-пилюля `.task-priority-badge.priority-*` + SVG-иконка | `cards.js`, FR-9 | рендер не меняется; вид переписывается (теги — чипами A, срок — `t-due-over`-семантика `--color-danger`) |
| F-11 | Комбобокс подсказок тегов (FR-57…59): `#task-tag-combobox` role=listbox, подсветка совпадений, чипы `#task-tags-chips`, скрытый `#task-tag-hints` (совместимость r3/r4-тестов), aria-live | `tag-combobox.js` | не меняется; цвета подсветки — токены A |
| F-12 | Единая зона действий `#task-actions` (FR-63): `[Столбец ▾][Сохранить][Отмена] │ [Удалить]` (destructive после submit/cancel, `margin-left:auto`); создание — `[Создать][Отмена]`; Escape-закрытие (чистая — сразу, грязная — confirm); крестик `#task-form-close` 40×40 | `board.html`, `board-init.js` | не меняется |
| F-13 | Просмотр карточки — read-only модалка `#task-detail-overlay` (FR-47, ОГР-18): бейдж архивной `#task-detail-archive-badge`, `dl#task-detail-attrs` (рендер `task-detail.js`), комментарии, «Редактировать»/«Закрыть», закрытие Esc/клик-вне | `task-detail.js` | не меняется; вид модалки — по мокапу task.html (meta-строки, serif-заголовок, комментарии, деструктив) |
| F-14 | Счетчики шапки: readout (дата, ACT/DONE — заполняет `cards.js` из реальных данных, декоративен `aria-hidden`) и `data-col-count` колонок | `board.html`, `cards.js` | не меняется; вид — mono/tabular-nums A |

### 1.2 Wiki

| # | Функционал | Якорь | Статус |
|---|---|---|---|
| F-15 | Дерево страниц (`GET /api/wiki/pages`, `tree.js`, контейнер `.wiki-tree`), пустой state «Создать первую страницу» | openspec `wiki` | не меняется |
| F-16 | Поиск по разделу (`search.js`, `#wiki-search`, `#wiki-search-results`, подсветка `<mark>`) | openspec `wiki` | не меняется; цвет `<mark>` — токены A |
| F-17 | Статья: breadcrumb (`page.js`, `.wiki-breadcrumb`), actions, тело `#wiki-article`, 404/409-баннеры; контент просанитизирован сервером | openspec `wiki` | не меняется |
| F-18 | WYSIWYG-редактор (`editor.js`, `#wiki-editor`, ?edit=1/?create=1, meta-card, тулбар, contenteditable, диалоги ссылка/изображение) | openspec `wiki` | не меняется |
| F-19 | История версий и откат (`history.js`, `#wiki-history`, роут `/wiki/{id}/history`, layout ≤880px складывается) | openspec `wiki` | не меняется |
| F-20 | Rich-контент: спойлер (FR-118), блок кода с подсветкой (FR-119), табуляция (FR-120), H-заголовки-переключатель (FR-121), таблицы (FR-122), деградация без внешних зависимостей (NFR-39/40) | openspec `p12-rich-tools` | функционал не меняется; вид блоков — токены A |

### 1.3 Gallery

| # | Функционал | Якорь | Статус |
|---|---|---|---|
| F-21 | Сетка из `GET /api/images` (created_at DESC); masonry-ритм при разнопропорциональных (брейкпоинты 880/1280; 480→2, 900→3, 1400→4 колонки) | openspec `gallery`, `gallery.js` | не меняется |
| F-22 | Фильтры категория (ИМЯ, Э-2)/тег, комбинируются, пустые = все; сброс `#filter-reset`; счетчик `#filter-count` | `gallery.html`, `gallery.js` | не меняется |
| F-23 | **Загрузка** (`#upload-button` → `#upload-overlay`): multipart (file, category?, tags?), dropzone (`#upload-dropzone`), превью файла (`#file-row`), новая категория (`__new__`), чипы тегов; ошибки 422 (тип JPEG/PNG/GIF/WebP, ≤10 МБ) в `#upload-error`; прогресс `#upload-progress` | openspec `gallery` «Лимиты загрузки» | не меняется |
| F-24 | **Лайтбокс** (`#lightbox-overlay`, FR-83): role=dialog + aria-modal, ←/→ кнопки + клавиатура (ArrowLeft/Right, Esc), счетчик, focus trap + возврат фокуса, свайп ≥50px на мобильном | `gallery.js`, `test_p14_41_lightbox_swipe.py` | не меняется |
| F-25 | Лайк/дизлайк — один голос пользователя (`my_reaction` подсветка «мой голос»), `aria-pressed` | openspec `gallery` | не меняется; подсветка — золото A |
| F-26 | Скачивание оригинала (`<a download>` на `/images/<filename>`), комментарии (список/добавление/удаление своего), inline-переименование (FR-97: Enter/✓, Esc-отмена) | `gallery.js` | не меняется |

### 1.4 Video

| # | Функционал | Якорь | Статус |
|---|---|---|---|
| F-27 | Список: `#video-grid`, фильтры (поиск-подстрока, категория, сортировка), пустые состояния (`#video-empty`, `#video-search-empty`) | `video.html`, openspec `video-ui` | не меняется |
| F-28 | Загрузка: `#video-upload-view`, dropzone (любой видеоформат, ≤500 МБ), прогресс `#upload-progressbar`, заметка конвертации `#convert-note`, категория (общий справочник с «Галереей») | openspec `video-service` | не меняется |
| F-29 | Плеер: `#video-player-view`, `#player-card`, статус (`#player-status`, CONV статусы), детали (`dl.details-list`), реакции (`#like-button`/`#dislike-button`), комментарии (`#comments-card`), переименование, удаление с confirm (`#delete-overlay`) | openspec `video-ui` | не меняется |

### 1.5 Каркас (base.html)

| # | Функционал | Якорь | Статус |
|---|---|---|---|
| F-30 | Сайдбар-навигация (порядок: Доска, Поиск, Wiki, Галерея, Видео, Погода, Игры, Манчкин; «Настройки» + «Выйти» + профиль внизу), активный раздел `.active` + `aria-current` | `base.html`, openspec `navigation` | не меняется |
| F-31 | Мобильная навигация ≤860px: бургер (`#burger-button`), drawer + backdrop (класс `sidebar-open`), заголовок раздела в шапке; тач-таргеты ≥44px (NFR-23) | openspec `navigation` FR-99/FR-100/FR-131 | не меняется |
| F-32 | Skip-link (первый фокусируемый, `#main-content`), профиль из `GET /api/auth/me` (`profile.js`), логаут `POST /api/auth/logout` (`app.js`) | openspec `accessibility`, `auth` | не меняется |
| F-33 | Favicon (data-URI SVG, маркер кеша `<!--cache:v=2-->`) | `base.html` | **ОТКРЫТЫЙ ВОПРОС ОВ-1** — перекрашивать ли в палитру A (сейчас «Пульт»: #0e1621/#f0b45c); при изменении — бамп `cache:v` |

---

## 2. Маппинг «деталь мокапа A → существующий DOM»

Канон деталей: `design-forge/a/kit.html` (`data-part`), токены `design-forge/a/tokens.css`. Правило из `tokens.css`: **вёрстка тем одна, только переменные — литерал цвета сломает одну из тем** (актуально и для прод-CSS после рестайлинга).

| # | Деталь мокапа A | В мокапе | В текущем DOM | Что требуется |
|---|---|---|---|---|
| 2.1 | **Кромка приоритета** — `border-left: 3px` карточки: `.p-high` (`--color-accent-2`, бордо), `.p-mid` (`--color-warning`), `.p-low` (`--color-border`), `.p-fst` (`--color-accent`, золото) | `kit.html`/`board.html` `.task-card.p-*` | Классы **уже ставит `cards.js`** на `article.task-card`: `.task-priority-low/medium/high`, `.task-card-fast`. CSS-хука кромки в `board.css` НЕТ (сейчас приоритет — пилюля `.task-priority-badge.priority-*` + SVG-иконка) | Только CSS: правила `border-left: 3px` + окраска по существующим классам. DOM/JS не трогаются. Пилюлю/иконку сохранить (различимость без цвета, FR-29) |
| 2.2 | **LED-точка статуса** — `.dot.dot-wait/work/done` 10px в `.col-head` | `board.html` `.col-head` | Уже есть: `.col-led.col-led-wait/run/done` (столбцы канбана), `.brand-led` (сайдбар), `.readout-led` (pagehead), LED `::before` у `.fastline-title` — `board.html`/`base.html`, стили `board.css`/`app.css` | Только CSS-перекраска на токены A (палитра mute/warning/success); DOM-хуки готовы |
| 2.3 | **Serif-заголовок** — `.t-title` (PT Serif 700, 16px/1.35), hover → золото | `kit.html` | `h3.task-card-title` (рендер `cards.js`), `h1.page-title` (board), `h1` wiki/gallery, `.lb-title`, `#player-title`, `.brand-name`, `.fastline-title` | Только CSS: `font-family: var(--font-display)` на заголовках; хуки готовы |
| 2.4 | **Mono-счётчик** — `.count` (JetBrains Mono, tabular-nums) | `kit.html` `.col-head` | `span.col-count[data-col-count]`, `.col-code`, `.fastline-code`, `#readout-act`/`#readout-done`, `#readout-date` — `board.html`, значения заполняет `cards.js` | Только CSS: `--font-mono` + `font-variant-numeric: tabular-nums`; значения и id не меняются |
| 2.5 | **Чип** — `.chip` (pill, 24px, border, muted) | `kit.html` | `#task-tags-chips .chip` (рендер `task-form.js`), чипы тегов в `task-card-meta` (рендер `cards.js`), гейт-чипы `#fastline-blocked-hint` / `#task-is-fast-gate` (`task-form.js`), чипы загрузки галереи `#tags-chips`, пункты `#task-tag-combobox` | Только CSS; тексты/крестики чипов не меняются (textContent, XSS) |
| 2.6 | **Кнопка-действие** — `.btn.btn-primary` (фон `--color-accent`, `on-accent`, radius-sm, 44px, active translateY(1px)); варианты secondary/ghost/danger (бордовая обводка `--color-accent-2`) | `kit.html` | `#create-task-button` (`.btn.btn-primary`), `#fastline-add-button` (`.fastline-add`), `#upload-button`, `.wiki-create`, зона `.task-actions` (`#task-form-submit/cancel`, `#task-delete-button.btn-destructive`), `.upload-button`/`.send-btn`/`.react-btn` (gallery/video), `#lb-download.download-btn` | Только CSS: варианты A ложатся на существующие классы (`btn-primary`→золото, `btn-destructive`→danger, `fastline-add`→золото-признак). Радиусы 10px (sm) |
| 2.7 | **Переключатель темы** — `.theme-btn` (иконка луны 20px, 44×44, `aria-pressed`, toggle `data-theme="light"` на `<html>`) | `board.html`/`task.html`/`kit.html` topbar | **ОТСУТСТВУЕТ — НОВЫЙ ЭЛЕМЕНТ.** В `base.html` топбара нет; точка вставки — решение СА (кандидаты: рядом с брендом сайдбара / в `sidebar-footer` / в `mobile-header`) | NEW: кнопка в `base.html` + JS-toggle в `app.js` (`document.documentElement.dataset.theme`), `aria-pressed`, иконка inline-SVG (ОГР-8: без внешних файлов), состояние без localStorage (персистность — ОВ-2). Светлая палитра уже канонизирована в `design-forge/a/tokens.css` |
| 2.8 | Панель фастлайна — `.fastlane` (border-top 3px золото) | `board.html` мокапа | `#fastline.fastline.fastline-a.hud` — есть; семантика «золотая линия штаба» совпадает с направлением A | Только CSS |
| 2.9 | Колонки — `.col` (surface, radius-md 18px) | `board.html` мокапа | `.board-column.hud[data-status]`, `.fastline-column[data-fastline-stage]` — есть | Только CSS; HUD-уголки «Пульта» замещаются плоской панелью A |
| 2.10 | Мета-таблица карточки — `table.meta-card` (строковые сепараторы, th 12em) | `task.html` | `dl#task-detail-attrs` (`.task-view-attrs`, рендер `task-detail.js`) — другой элемент, тот же паттерн «строки с сепараторами» | Только CSS на существующие `dl/.attr`; DOM не менять (ОГР-28: пороги TC-form/bug013) |
| 2.11 | Разделитель секций — `.divider` с serif-подписью | `board.html` мокапа | `hr.board-sep` — есть | Только CSS |
| 2.12 | Подпись «Выполнено сегодня · N» | `board.html` мокапа (`.col-note`) | Подпись/счетчики done — через readout + колонку done; отдельного узла нет | **ОВ-3**: добавлять ли подпись (новый узел в колонке — согласовать с СА/QA) |

Классы-состояния, чью **видимую** обертку переписываем, а имена сохраняем дословно: `has-fast` (столбец), `task-card-fast`, `drop-target`, `drop-forbidden`, `drag-ghost`, `board-column-empty`, `field-invalid`, `preset-v` (остается контейнером доски), `hud` (замещается или переосмысляется — решение СА), `pagehead`/`readout`.

---

## 3. Инвентарь тестов с визуальными ассертами

Пройдены все `tests/web/*.py`: **59 файлов с тестами, 445 тест-функций** (без `conftest.py`, `dnd_helpers.py`, `pages/`, `tag-ledger-leak-sim.js`). Классификация по типу ассертов.

### 3.1 Токен-визуальные ассерты — ИЗМЕНЯТСЯ (12 файлов / 114 тестов)

| Файл | Тестов | Что ассертится (примеры) | Как меняется при рестайлинге A |
|---|---|---|---|
| `test_redesign_console.py` | 36 | **Главный визуальный сьют «Пульта»**: палитра-снапшот (BG0 `rgb(14,22,33)`, BG1-BG3, BORDER, AMBER, CYAN, TEAL, CORAL), HUD-уголки (≥8 `linear-gradient`), LED teal/amber blink+glow, микро-сетка 32px, mono `FONT_DATA`, caps-трекинг 0.06/0.14em, focus-visible cyan, контраст WCAG AA, radius 8px, fastline-трек/LED, сайдбар 232px+1fr, бренд/LED, логин/поиск/settings/wiki (breadcrumb mono 11px, rich-блоки inset teal 3px)/gallery (лайтбокс `56px` shadow)/video/weather (TC-031/032) в «Пульте», token-snapshot TC-010 (`--texture-grid 32px`), hex-gate TC-032 (whitelist v3-значений), мобильная ≤860px | **Переписываются почти все литералы** — весь сьют построен на палитре «Пульт». Структура/метод (getComputedStyle-снапшоты, контраст, reduced-motion, skip-link, семантика TC-007 «board_semantics_unchanged») сохраняются; значения — на токены A (`#1e0f14`, `#d6a85c`, `#c4505c`, PT Serif/Golos/JetBrains Mono, радиусы 10/18/28, light-тема). TC-032 (weather «не трогать») и TC-010 (снапшот токенов) — переписать на новые канон-значения. Крупнейшая единица работ QA-волны |
| `test_board_fastline.py` | 9 | Гейт/чип/dnd зоны — функционально; **визуально**: фон зоны `rgb(58,44,18)` (`--p-amber-900`), отсутствие `.fastline-count` | Фон зоны → `--color-surface` A; остальное — не меняется |
| `test_coverage_fastline.py` | 13 | Гейт/dnd — функционально; **визуально**: outline `drop-target` (rgb-литерал), направление-цвета | Цвета dnd-состояний → токены A (accent-2/accent) |
| `test_qa21_gallery_design.py` | 2 | Whitelist токенов «Пульт» в `app.css :root` (`--p-amber-400/#f0b45c` → `--color-accent`, `--p-amber-900` → `--color-accent-soft`), запрет rgba-литералов вне whitelist | Полная переписка на канон-токены A + аналогичный «не-литералы» гейт |
| `test_qa21_netdata_sidebar_ui.py` | 6 | Пункт мониторинга: подпись `#a7b7c8`, hover `bg2 #1d2b40`, active `bg3 #26354d`, focus-ring cyan `#4fd8eb`, иконка 16px | Цвета → токены A (muted/surface/raised, focus `--color-accent`); 16px иконка — не меняется |
| `test_r3_formv3_ui.py` | 5 | Форма V3: нижняя линия полей 2px, focus-ring, shadow полей, чипы (`border-radius`≠0, bg), пилюля приоритета — bg по `:has(:checked)`, иконка display none/inline | Оформление полей/чипов/пилюли — токены A (бордо/золото, радиус 10px); структурные ассерты (текст опций, «—» без иконки) — не меняются |
| `test_r3_vis_ui.py` | 5 | `preset-v`: hover-подъем и accent-цвет заголовка, empty-state (dashed 2px, min-height ≥48px, `::before`), анимации `v-in`/dnd (name/duration/fill, reduced-motion) | Цвета hover/empty → токены A; тайминги анимаций (`--dur 160ms`, `--ease`) могут сместиться — переснять; имена анимаций/классы — не меняются |
| `test_r5_profile_card_ui.py` | 7 | Карточка профиля: bg `rgb(29,43,64)` (bg-200), radius 8px, shadow `rgba(0,0,0,.4) 0 1px 2px`, кнопка янтарь `rgb(240,180,92)`, поля 2px-линия, radius 0px, pill 999px | Полная переписка: surface `#2a161d`, radius 18px, shadow `--shadow-1` A, акцент `#d6a85c` |
| `test_p12_ui_polish_r8.py` | 7 | `.fast-row` геометрия (8px-сетка, чекбокс 16px), `.btn-action` радиус 6px `var(--radius-field)`, hover/focus-единство, отступы кратны 8px | Радиус → 10px (`--radius-sm` A), отступы — кратность 4/8 сохраняется (space-шкала A 4/8/16/24/40/64); чекбокс 16px — не меняется |
| `test_p15_wiki_tree.py` | 10 | Раскладка 280px+контент (≤480px одна колонка) — **геометрия сохраняется**; визуально: bg `<mark>` `rgb(58,44,18)` | `<mark>` → `--color-warning-soft`/accent-soft A; раскладка — не меняется (решение 1200px сохраняется) |
| `test_r6_tag_combobox_ui.py` | 11 | Подсветка совпадений: color `rgb(240,180,92)` (`--color-accent`), bg `rgb(58,44,18)` (`--color-accent-soft`) | → золото `#d6a85c` / `--color-warning-soft`-аналог A; поведение (клавиатура, aria, чипы) — не меняется |
| `test_bug004_board_empty_state.py` | 3 | Пустой столбец: класс `board-column-empty`, dashed-border, `::before`-контент, min-height 72px зоны fastline | Вид dashed → токены A; классы/пороги — не меняются |

### 3.2 Смешанные (геометрия/адаптив сохраняется; точечные визуальные литералы) — 27 файлов / 228 тестов

| Файл | Тестов | Визуальная часть | Судьба |
|---|---|---|---|
| `test_coverage_p14_mobile.py` | 10 | Поля ≥16px (NFR-24), тач ≥44px (NFR-23), одна колонка 390px, свайп-снап доски | **Требования-константы не меняются**; проверять отсутствие регрессий раскладки после CSS |
| `test_coverage_uip.py` | 11 | Masonry-брейкпоинты 880/1280, badge-геометрия, «core web contracts» (перечень узлов `#task-tags-chips`, `.fast-row`, `#fastline-add-button`…) | Контракты узлов — не меняются (ОГР-28); masonry — не меняется |
| `test_p23_fastline_mobile_ui.py` | 4 | Свайп ≤480px (82vw/snap), тач ≥44px, `drop-target`/badge на мобильном | Геометрия — не меняется; цвета dnd — токены A |
| `dev_smoke_p14_21_board_swipe.py` | 4 | Снап/точки-индикаторы/reduced-motion instant scroll | Не меняется (смоук) |
| `test_p14_22_ticket_modal_fullscreen.py` | 6 | Fullscreen-модалка 390px (radius 0px), крестик ≥44px, поля ≥16px, restore scroll, десктоп-модалки без изменений | Не меняется (механика); размеры — те же константы |
| `test_bug013_attrs_padding.py` | 1 | Паддинги view-модалки: body `16px 32px`, `.attr` `8px 16px`, sr-only clip | **Риск**: отступы привязаны к порогам теста; при переходе на space-шкалу A (4/8/16/24) значения, вероятно, сохранятся (16/32=space-3+space-4×2? нет: 32px нет в шкале) — решить в СА: либо сохранить текущие паддинги, либо осознанно переписать тест |
| `test_bug014_search_task_view.py` | 2 | `headPadding 24px 32px 16px` совпадает с доской | Аналогично ОГР-риск: значение или тест |
| `test_r6_wave2_ui.py` | 4 | Зона действий: разделитель «Удалить» 1px, порядок, token-цвета | Разделитель — не меняется; цвета → токены A |
| `test_r4_commentfix_ui.py` | 4 | Комментарии под формой (не рядом), зазор кнопки ~8px | Геометрия — не меняется |
| `test_p12_nav_icons_favicon_r8.py` | 6 | Иконки inline-SVG 16px stroke currentColor (ОГР-8), порядок пунктов, favicon `#f0b45c` | Иконки/порядок — не меняются; **favicon — ОВ-1** (при перекраске — бамп кеш-маркера и правка ассерта) |
| `test_p12n004_sidebar_footer_long_gallery.py` | 1 | Footer сайдбара стабилен на длинной галерее (±1px) | Не меняется |
| `test_coverage_weather.py` | 16 | Погода: порядок пунктов, 7 карточек, раскладка | Погода — **вне объема** редизайна (страницы: board/task/wiki/gallery/video); TC-redesign-031/032 (в `test_redesign_console.py`) ее задевают — там и править |
| `test_p15_wiki_history.py` | 7 | Layout 2 колонки десктоп / 1 ≤880px | Не меняется |
| `test_p15_wiki_editor.py` | 11 | Редактор: тулбар/контент behavior, focus | Не меняется |
| `test_p12_gallery_rename_masonry_r8.py` | 4 | Masonry-геометрия, rename-инлайн, XSS | Не меняется |
| `test_p14_41_lightbox_swipe.py` | 7 | Свайп ≥50px, тап не листает, стрелки ≥1024px | Не меняется |
| `test_r5_crop_ui.py` | 19 | Кроп: клэмп, canvas→PNG 256, touch/pinch, клавиатура, reduced-motion | Не меняется (виджет не в объеме) |
| `test_r5_textarea_polish_ui.py` | 4 | Авто-высота textarea (старт ~2 строки ≤68px, потолок ~10) | Не меняется; высоты могут «поехать» от новых шрифтов — проверить, не ассерт ли жесткий |
| `test_r6_gaps_ui.py` | 2 | Форма 375px: одна колонка, дропдаун не шире вьюпорта | Не меняется |
| `test_qa21_gallery_ui.py` | 6 | Точки-цвета (hex) в UI галереи | Точечно → токены A |
| `test_tooltip_r4.py` | 8 | Тултип: reduced-motion opacity, одиночный инстанс | Не меняется |
| `test_games_nav.py` | 2 | Пункты «Игры»/«Манчкин»: порядок, inline-SVG (нет img/use) | Не меняется |
| `test_rich_tools.py` / `test_coverage_rich_tools.py` / `test_coverage_rich_tools_security.py` | 26/22/18 | Rich-блоки: рендер/деградация/безопасность (script off, `window.__qared_xss`) | Не меняются; визуал rich-блоков (h2 inset-полоса и т.п.) ассертится в `test_redesign_console.py` TC-034 — правится там |
| `test_settings_categories_ui.py` | 24 | Справочник категорий: CRUD, бейджи-счетчики | Не меняется (settings вне объема) |
| `test_settings_profile_r4.py` | 11 | Профиль: поля, роли | Не меняется |
| `test_r3_dnd_ui.py` | 6 | DnD: классы состояний, single POST | Классы — не меняются |
| `test_p12n004…`/`test_coverage_weather.py` уже перечислены | | | |

### 3.3 Функциональные ассерты — НЕ МЕНЯЮТСЯ (20 файлов / 103 теста)

`test_board_tasks_ui.py` (8; CRUD/валидация формы), `test_board_assign_ui.py` (7; исполнитель), `test_fastline_ui.py` (2), `test_assignu_r4_ui.py` (3), `test_auth_ui.py` (5), `test_p15_wiki_page.py` (6), `test_search_r4_ui.py` (4), `test_search_suggestions_ui.py` (3), `test_navigation_search_ui.py` (3), `test_video_ui.py` (4), `test_video_convert_ui.py` (3), `test_video_rename_ui.py` (3), `test_video_social_ui.py` (5), `test_video_wiki_isolation_ui.py` (1), `test_weather_ui.py` (5), `test_r3_profile_ui.py` (5), `test_r3_selects_ui.py` (8), `test_view_modal_r4.py` (9), `test_r8_tag_ledger_leak_ui.py` (1).

Эти сьюты должны остаться зелёными **без единой правки** — это критерий «функционал не тронут». Если краснеют — регресс рестайлинга, а не визуальная правка.

**Сводка воздействия: ~139 тестов из 445 (12 файлов с токен-ассертами + точечные цветовые литералы в смешанных) потребуют правки ожиданий; правится только ожидаемое значение (палитра/шрифт/радиус/тень), локаторы, семантика, пороги и методология — без изменений.**

---

## 4. Ограничения

- **ОГР-28 (селекторы).** Классы/id/data-атрибуты существующих страниц не меняются без крайней необходимости; приоритет — правка CSS-токенов. Критичный реестр стабильных селекторов (по ним живут тесты): `#board`, `[data-status]`, `#fastline`, `[data-fastline-stage]`, `[data-cards]`, `data-col-count`, `#create-task-button`, `#fastline-add-button`, `#fastline-blocked-hint`, `#task-is-fast-gate`, `#task-form*` (`#task-form-overlay`, `#task-form`, `#task-form-error`, `#task-title`, `#task-description`, `#task-priority`, `#task-category`, `#task-category-error`, `#task-assigned`, `#task-due-date`, `#task-tags`, `#task-tags-chips`, `#task-tag-combobox`, `#task-tag-hints`, `#task-form-submit/cancel/close`, `#task-delete-button`, `#task-move-select`, `#task-actions`), `#task-detail-*`, `#task-comments*`, `#comment-form`, `#comment-body`, `#task-priority-pill-icon`, классы `task-card`, `task-card-fast`, `task-priority-*`, `has-fast`, `drop-target`, `drag-ghost`, `drop-forbidden`, `board-column-empty`, `preset-v`, `pagehead`/`readout*`, `col-led*`, `col-code`, `col-count`, `lightbox`/`lb-*`, `upload-*`, `wiki-*` контейнеры, `video-*` контейнеры, `nav-item*`, `brand-led`, `skip-link`, `burger`. Рендер-классы из JS (`cards.js`, `task-form.js`, `tag-combobox.js`, `gallery.js`, wiki/video-модули) — тем более стабильны: JS не трогается (новые классы допустимы только если рендер физически не может выразить мокап — точка правки Волны 2, СА).
- **XSS-правило.** Пользовательские данные в HTML-разметку не входят — рендер только `createElement`+`textContent` (`dom.js`; паттерн board/search/gallery/wiki/video). Рестайлинг не вводит ни одного `innerHTML` с данными; чипы/подсветки combobox — существующие safe-хелперы.
- **API не трогается.** Ни один эндпоинт, payload, статус-код. `GET /api/board`, `/api/tasks*`, `/api/categories`, `/api/users`, `/api/suggestions*`, `/api/images*`, `/api/videos*`, `/api/wiki*`, `/api/auth/*` — без изменений.
- **Одна разметка — обе темы.** Светлая тема включается `data-theme="light"` на `<html>`, меняются только переменные: **литералы цветов в прод-CSS недопустимы** вне токен-файла (правило `design-forge/a/tokens.css`; ассерты-«не-литералы» `test_qa21_gallery_design.py` сохраняются как гейт).
- **Нефункциональные константы не ослабляются:** NFR-23 (тач ≥44px), NFR-24 (поля ≥16px), NFR-41 (контраст WCAG 2.1 AA **в обеих темах**), NFR-43 (`prefers-reduced-motion`), NFR-44 (skip-link), ОГР-8 (без внешних файлов: шрифты A подключаются Google-Fonts `@import` из токен-файла как в мокапе — точку подключения решить в СА с учетом ОГР-8/офлайн).
- **Открытые визуальные спецификации.** Часть openspec-спек фиксирует стиль «Пульт»: `board` FR-132, `gallery` FR-125, `video-ui` FR-126, `wiki` FR-123/FR-124, `accessibility` NFR-41/42 (cyan focus-ring). После редизайна эти требования морально устаревают — в Волне 2 (СА) заложить openspec-дельту (MODIFIED, только визуальные требования; API-спеки не затрагиваются), в Волне 4 — прогон.
- **Контент мокапов в прод не переносится** (тексты задач/статей — примеры); топбар с «досками» и отдельная страница task не переносятся (см. §0).
- **ОГР-соседи, не входящие в объем:** settings/profile/weather/games/login остаются на текущем стиле до отдельного решения (кроме каркасных последствий: сайдбар/тема видны отовсюду). При этом `test_redesign_console.py` ассертит и их — при правке сьюта не «отпустить» эти страницы в стиль A молча: либо зафиксировать их current-состояние в новых ассертах, либо внести в объем отдельным решением Заказчика (ОВ-4).

---

## 5. Критерии приёмки Волны 1 (БА)

1. Настоящий документ содержит: полный список сохраняемого функционала (§1), маппинг «деталь мокапа → DOM» с точными классами/узлами (§2), инвентарь всех тестов с визуальными ассертами и классификацией «изменится / не меняется» (§3), ограничения (§4) — и закоммичен в `feat/redesign-ui-a`.
2. Каждая ключевая деталь направления A (§2.1–2.7) имеет подтвержденный по коду якорь в существующем DOM; единственный обязательный новый элемент — переключатель темы (§2.7).
3. Открытые вопросы зафиксированы и переданы Заказчику/СА: ОВ-1 (favicon: перекрашивать/бамп кеша), ОВ-2 (персистность выбранной темы — localStorage/системная?), ОВ-3 (подпись «Выполнено сегодня · N» в колонке — новый узел?), ОВ-4 (судьба страниц вне объема в `test_redesign_console.py`: фиксировать current или включить в редизайн), ОВ-5 (точка вставки переключателя темы в `base.html`), ОВ-6 (отступы 32px в модалках: сохранить под пороги тестов или перейти на шкалу A с правкой порогов).
4. Ответы на ОВ закрыты до старта Волны 2 (СА); для «не меняется»-сьютов (§3.3) определен запрет на правки.
5. Документ сверен с мокапами `design-forge/a` (детали `data-part` kit.html покрыты §2) и с экстра-мокапами `design-forge/extra/*` (утверждены, `APPROVED.md`).
