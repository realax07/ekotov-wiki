# Review 004 — Design-валидация add-ui-polish-r8 (задача 3.1(г))

Reviewer-Delegation: deleg-8216bcb4532a415e
Gate correlation: 8216bcb4532a415e8bd3920296a05bde
Дата: 2026-10-07. Ревьюер: design_validator (независимая ось «соответствие дизайну»).
База: main @ 3fd0d53. Зоны: 2.1 (.btn-action), 2.2 (view-модалка, FR-90/91), 2.4 (сайдбар-иконки FR-94, favicon FR-95), 2.6 (masonry FR-98).

## Метод

Computed-styles сверка (getComputedStyle через Playwright/headless Chromium) реализованного UI на стенде против значений утвержденных мокапов:

- `design/polish-ticket-modal.html` (модалка тикета, утвержден 2026-10-06) — эталон шапки/секций/типографики;
- `design/polish-gallery-grid-variants.html`, вариант В (masonry, утвержден) + `design/gallery-grid.html` (карточка/бейджи);
- `design/REPORT-1.1-polish.md` (favicon V3, дизайн-§3) — favicon сверен URL-decoded diff'ом data-URI;
- токены — `frontend/static/css/app.css :root` (design README: «токены дословно из app.css» — app.css старше мокапа при расхождении значений soft-токенов).

Дефектные классы: «интерактивный элемент без единого CSS-правила», «цвет вне палитры V3», токен-литералы вне var(--…).

Стенд (поднят по tests/README.md, погашен после): uvicorn `app.main:app` :8123 (tmp-БД `/tmp/dv-r8.db`: схема + seed owner/wife + `migrate_r4`; `EKOTOV_WIKI_AVATARS_DIR=/tmp/dv-r8-avatars`) + nginx-подобный контур :8125 — `/static/*` из `frontend/static` с корректным mime (`application/javascript`/`text/css`, проверено curl до прогона), остальное — reverse proxy на app. Продовая топология «статика отдельно от app» соблюдена; data-задачи `Проверка TLS-сертификата…` (priority high, tags, due) + комментарий созданы через API стенда.

## Сверка: мокап-блок → реализация → вердикт

### (1) Модалка тикета — design/polish-ticket-modal.html

| Мокап-блок | Реализация (computed) | Вердикт |
|---|---|---|
| `.modal`: 640px, bg-surface, radius-card 10px, shadow-modal | `.task-view`: max-width 640px, `rgb(255,253,249)`, 10px, `rgba(61,54,48,0.18) 0 16px 40px` | OK |
| `.modal-overlay`: rgba(61,54,48,**0.45**), padding **32px** 16px | `rgba(61,54,48,0.4)`, `40px 16px` (board.css 4.5, до r8) | nit N-6 |
| `.modal-kicker`: micro 11px, secondary, uppercase, 0.06em, mb 4px | 11px, `rgb(107,97,88)`, uppercase, letter-spacing 0.66px, margin-bottom 4px, текст «Задача · STAND-1» | OK |
| `.modal-title`: Georgia, 22px/1.25 | Georgia, 22px, line-height 27.5px (1.25), weight 400 | OK |
| `.badge`: 11px/600, padding 3px 10px, radius 999px, gap 6px; `.badge-row` gap 8px | идентично; SVG-иконка 12×12, currentColor | OK |
| `.badge-priority-high`: `--priority-high` на `--priority-high-soft` | `#9c3524` на `#f6ebe8` (app.css soft-токен; мокап-значение #f8ecea — расхождение самих токенов, не реализации; app.css — источник) | OK |
| `.badge-status`: olive `#5f6f34` на `#eff1e4` | `rgb(95,111,52)` на `rgb(239,241,228)` | OK |
| `.badge-fast` (blue-050/700) | класс на токенах `.badge-fast`; в прогоне не показан (задача не fast — бейдж только по факту, данные не выдумываются) | OK (код) |
| `.section-label`: micro/secondary/uppercase/0.06em, margin 16/8 | идентично (0.66px, 16px 0 8px) | OK |
| `.attr-grid` 2 колонки, gap 8/16; `.attr`: bg-subtle, radius-field 6px, padding 8/16; dt micro, dd 13px/600 | `grid 1fr 1fr`, gap `8px 16px`; `rgb(243,237,228)`, 6px, `8px 16px`; dt 11px; dd 13px/600 | OK |
| `.tag-chip`: 11px/600, 3px 10px, 999px, bg-subtle + border | идентично + `1px solid rgb(233,225,212)` | OK |
| `.person-avatar` 28px круг, accent-фон (secondary — border-strong) | 28×28, 50%, `rgb(168,67,44)` (primary), secondary — `rgb(107,97,88)` | OK |
| `.comment-head`: baseline, gap 6px; author 13px/600; sep/date secondary micro | идентично; текст шапки «owner · 07.10.2026, 13:43» — Intl ru-RU «дд.мм.гггг, чч:мм» (FR-91) | OK |
| `.comment`: border, radius-field, padding 8/16, mb 8, bg-surface | идентично | OK |
| `.modal-foot`: gap **8px** (`--space-1`), padding 16/32/24, border-top, кнопка вправо | gap **16px**, margin-top **24px** — перекрыт дублем `.task-view-actions` (board.css:1200, задача 4.1) поверх r8-правила (:1151) | minor N-2 |
| `.btn-primary` (Редактировать): accent-фон, padding 8/24, 999px, hover accent-hover, focus-ring | `rgb(168,67,44)`, `8px 24px`, 999px, hover `rgb(147,57,31)`, focus `rgba(168,67,44,0.35) 0 0 0 3px` | OK |
| шапка: pad `24/32/16` ОДИН раз, разделитель один, контент в 32px от края | **задвоенный `.task-view-head`** (вложенный div тем же классом): паддинг 48px по вертикали, контент в 64px от края (kicker x=385 при modal x=320), двойная линия-разделитель (border-bottom на y=169.5 и y=186.5) | **major N-1** |
| бейдж приоритета: иконка-треугольник (fill), текст «Приоритет: высокий» | иконка — стрелка вверх 14×14 stroke (система FR-29, единая с карточками/формой), текст «Приоритет: Высокий» | nit N-4 |

### (2) Галерея — masonry, вариант В (FR-98)

| Мокап (`.variant-v .masonry`) | Реализация (computed, gallery.css) | Вердикт |
|---|---|---|
| `columns: 4 var(--space-4)`; 3 кол ≤1100px; 2 кол ≤780px | `column-count: 4`, `column-gap: 16px`; медиа-инверсия min-width: **4 @1400 / 3 @1000 / 2 @700** (измерено live) — брейкпоинты 880/1280 соответствуют утвержденному `gallery-grid.html` | OK |
| `.card`: inline-block, width 100%, `margin: 0 0 var(--space-2)`, `break-inside: avoid` | `inline-block`, 246px (колонка), `break-inside: avoid`, `margin-bottom 16px` | OK |
| `.thumb img { height: auto }` — естественная высота | `width: 100%; height: auto` (на инжектированных SVG-плитках height 0 — артефакт теста: svg без viewBox не дает intrinsic ratio; на растровых thumb механика штатная), thumb bg-subtle + border-bottom | OK (механика) |
| `.g-card` из gallery-grid.html: surface, border, radius-card, shadow-soft, без underline; hover: translateY(-2px) + clay-700 title | идентично; hover/focus-ring/active присутствуют | OK |
| `.g-card-title`: Georgia 15px/600 | Georgia, 15px, 600 | OK |
| цвет вне палитры V3 | hex вне `:root` в gallery.css/board.css — **0**; rgba-литералы — только тени/вуали из самих мокапов (`rgba(61,54,48,0.16)` и т.п.) | OK |

Пустая галерея (нет изображений на стенде): пустое состояние мокапом не регламентировано — не дефект (правило границ).

### (3) Сайдбар-иконки (FR-94) + favicon (FR-95)

| Эталон (Мониторинг `netdata-sidebar-mockup` / Галерея `gallery-grid.html`) | Реализация (computed) | Вердикт |
|---|---|---|
| иконка 16×16, flex-shrink 0, stroke=currentColor, viewBox 24 | **все 5 пунктов** (Доска/Поиск/Wiki/Галерея/Настройки): computed 16×16px, flex-shrink 0, окраска currentColor (`rgb(250,247,242)` = paper-050; active — терракота через `.active`) | OK |
| `.nav-item-gallery`: flex, align-items center, **gap 8px** | Галерея: flex/center/**8px**; Настройки: flex/8px (инлайн) | OK |
| эталонный стиль ряда (icon→текст с зазором 8px) | **Доска и Поиск: gap 0px** (display:block, текст вплотную к иконке, text x=36 при icon x=20 w=16); Wiki — аналогично. Рассинхрон с эталонными Галереей/Мониторингом | minor N-3 |
| favicon: data-URI мокапа дословно; терракотовый акцент V3 | data-URI в base.html **идентичен** мокапу URL-decoded (rect #faf7f2, лист #a8432c, загнутый угол #f7e8e4); рендерится (naturalWidth>0), canvas-сэмпл 32px содержит `168,67,44`; type=image/svg+xml | OK |
| design §3: `?v=`-маркер кеша | `?v=` на data:URI ломает XML (задокументировано в base.html с воспроизведением) — заменен инлайн-комментарием `<!--cache:v=1-->` внутри SVG; цель (инвалидация кеша при бампе) сохранена | nit N-5 (осознанное, задокументированное отклонение) |

### (4) Кнопки `.btn-action` (FR-93, 2.1)

| Эталон V3 (app.css `.btn-action`) | Реализация (computed, «Найти» #search-builder-submit) | Вердикт |
|---|---|---|
| padding `8px 24px` (--space-1/3), radius 999px, bg `--color-accent` clay-600, color on-accent, shadow-soft, inline-flex/center, nowrap | `8px 24px`, 999px, `rgb(168,67,44)` (`--p-clay-600`), `rgb(255,255,255)`, `rgba(61,54,48,0.08) 0 1px 3px`, inline-flex/center, nowrap, font 14px system-ui | OK |
| hover: `--color-accent-hover` | `rgb(147,57,31)` = `--p-clay-700` | OK |
| focus-visible: focus-ring | `rgba(168,67,44,0.35) 0 0 0 3px` (клавиатурный фокус) | OK |
| покрытие интерактивных элементов | `#search-builder-submit`, `#search-advanced-submit` — оба `.btn-action`; все проверенные контролы зон (edit/close/nav/logout) имеют токенные стили; элементов с браузерными дефолтами не найдено (DEF-004-класса нет) | OK |

## Находки

**Blocker** — нет.

**Major**
- **N-1. View-модалка: задвоенная шапка `.task-view-head`** (2.2, FR-90). `renderTaskDetail` (task-detail.js:383-390) создает внешний `.task-view-head`, а внутрь аппендит результат `buildViewHead(task)` — еще один div с тем же классом (task-detail.js:278). Computed: внешний/внутренний pad `24px 32px 16px` каждый → контент шапки в **64px** от края окна вместо 32px (мокап `.modal-head`), двойная border-bottom (две линии, y=169.5 и y=186.5). Ожидалось (мокап): один паддинг 24/32/16, один разделитель. Источник: design/polish-ticket-modal.html §шапка. Фикс — однострочный: не создавать вложенный div (филдить внешний блоками кикер/заголовок/бейдж-ряд напрямую).

**Minor**
- **N-2. Футер модалки перекрыт дублем правила** (2.2). `.task-view-actions` определен дважды в board.css: r8-блок :1151 (gap `--space-1`, margin-top 0 — по мокапу `.modal-foot`) и правило задачи 4.1 :1200 (gap `--space-2`, margin-top `--space-3`) — каскадно побеждает второе. Computed: gap 16px (мокап 8px), margin-top 24px (мокап: футер прилегает). Ослабляет соответствие мокапу; убрать/поглотить дубль.
- **N-3. Доска/Поиск/Wiki: иконка вплотную к тексту (gap 0)** (2.4, FR-94). Эталонный стиль ряда (Мониторинг/Галерея) — flex + gap 8px; у новых пунктов иконка инлайн в текстовой строке без зазора (computed text x=36 = правый край иконки). Внутри одного сайдбара два разных ритма «иконка-текст». Комментарий в base.html признает ограничение зоны записи (app.css не трогался) — но inline `style="display:flex;gap:var(--space-1)"` на трех `<a>` в base.html устранил бы без выхода из зоны.

**Nit**
- **N-4.** Иконка приоритета в бейдже — стрелка (система FR-29), в мокапе — треугольник; капитализация «Высокий» vs мокапного «высокий». Паттерн «цвет+SVG+текст» соблюден; консистентность с карточками перевешивает.
- **N-5.** Кеш-маркер favicon — `<!--cache:v=1-->` внутри SVG вместо `?v=` в URL (data:URI + query ломает XML — воспроизведено и задокументировано в base.html). Цель design §3 сохранена.
- **N-6.** `.modal-overlay`: rgba-альфа 0.4 и padding 40px — против мокапных 0.45 и 32px (правило 4.5, до r8; зрительно неотличимо, на 8px-сетке).

Токены: во всех r8-зонах значения — через var(--…); hex-литералов вне `:root` нет; rgba-литералы — только мокапные тени/подложки. Интерактивных элементов без CSS-правил не обнаружено.

Поведенческих прогонов не выполнял (не моя ось); попутно: stylesheets загружаются, pageerror в сессии нет.

## Вердикт: RETURN
