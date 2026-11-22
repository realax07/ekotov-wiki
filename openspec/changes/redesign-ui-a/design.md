# Design: redesign-ui-a

> **Канонический источник СА** — docs/sa/sdd-redesign-ui-a.md (Волна 2). Копия в пакете — контракт 2 flow_check.

# sdd-redesign-ui-a.md — СА-фаза редизайна UI направления A «Доска и поток» (ekotov-wiki)

> Статус: **ЧЕРНОВИК Волны 2 (СА) — PLAN-REDESIGN-UI-A.md, Флоу 1** | Автор: sa-агент (glm-5.3) | Дата: 2026-11-21
>
> **Входные документы:** `docs/ba/requirements-redesign-ui-a.md` (b337fcc), `design-forge/a/tokens.css` (канон токенов, сгенерирован deal.mjs), `design-context/GUIDE.md` + `design-context/assets/tokens.css`, эталонные мокапы `design-forge/a/*` и `design-forge/extra/*` (утверждены, APPROVED.md), `openspec/specs/` (требования «Пульта» FR-123…126, FR-128…132, NFR-41/42), текущий CSS `frontend/static/css/{app,board,gallery,wiki}.css`, `base.html`, `app.js`.
>
> **Ограничения наследуются из БА (§4 requirements):** ОГР-28 (селекторы DOM не менять), API не трогается, XSS-правило, одна разметка — обе темы (литералы цветов в прод-CSS вне токен-блока запрещены), NFR-23/24/43/44 не ослабляются, функциональные сьюты §3.3 — без правок.

---

## 1. CSS-архитектура

### 1.1 Источник токенов и расхождение с design-context

Канон — **`design-forge/a/tokens.css`** (46 переменных, dark `:root` + светлая `:root[data-theme="light"]`). Сверка с `design-context/assets/tokens.css` (wd-scan-снимок): **значения идентичны**, расхождения только в комментариях и ОДНОЙ утрате — в light-блоке wd-scan-снимка отсутствует `--color-accent-2` (#c4505c, одинаков в обеих темах). Берем forge-версию целиком; design-context используется как справочник вычисленных стилей (parts/, compositions/) и для `verify.mjs`-сверки, не как источник токенов.

### 1.2 Физическая точка интеграции

Токены A переносятся **в `:root`-блок `frontend/static/css/app.css`** (прецедент: пакет redesign-console — «токены перенесены в :root ДОСЛОВНО»; отдельный файл не заводится — один HTTP-запрос, hex-gate тесты смотрят в app.css, порядок каскада не меняется). Светлая тема — **вторым блоком `:root[data-theme="light"]`** сразу после dark-блока.

**Шрифты — self-host, НЕ Google Fonts @import.** Мокап подключает PT Serif/Golos/JetBrains Mono через Google-Fonts `@import`, но ОГР-8 («без внешних зависимостей») и NFR-39/40 (wiki деградирует без внешних ресурсов) это запрещают для прода. Решение: woff2-файлы из `design-context/assets/fonts/` (18 шт., OFL) копируются в `frontend/static/fonts/`, подключаются `@font-face` в app.css с `font-display: swap` и unicode-range (кириллица+латиница). Нужные начертания: PT Serif 400/700, Golos Text 400/500/600, JetBrains Mono 400/600. **Уточнение (фикс по code-review major-2):** подключенные woff2 Golos Text и JetBrains Mono — variable fonts (ось `wght` 400–900 и 400–800 соответственно, сверено fontTools `fvar`); в app.css дескрипторы объявлены диапазонами `font-weight: 400 900` / `400 800`, поэтому требуемые 500/600 рендерятся нативно из wght-оси — синтетический bold не возникает, новые woff2-файлы не нужны. Соответствие файлов-хешей семействам dev определяет по метаданным woff2 в Волне 3.1; fallback-стек — из токенов A (`Georgia/system-ui/ui-monospace`). Проверка офлайна: сеть отключена — шрифты отдаются статикой.

### 1.3 Маппинг «токены A → существующие переменные app.css»

Правило БА: одна разметка — обе темы, литералы цвета сломают одну из них → все производные тона выражаются `color-mix()` от канон-токенов, **ни одного нового hex** вне токен-блока. Сверка имен: совпадающие имена — переназначение значений (маппинг), отсутствующие в app.css — добавить, «пультовские» эффект-токены без семантики в A — удалить вместе с местами использования.

**Маппинг поверхностей** (семантика мокапа: `--color-bg` страница < `--color-surface` панели/колонки < `--color-raised` карточки — `design-forge/a/board.html` .col/.task-card):

| Переменная app.css | Значение «Пульт» | Становится (направление A) | Тип |
|---|---|---|---|
| `--color-bg-page` | `var(--p-bg-000)` #0e1621 | `var(--color-bg)` #1e0f14 | замена |
| `--color-bg-subtle` (панели: сайдбар, колонки, шапка) | `var(--p-bg-100)` #172335 | `var(--color-surface)` #2a161d | замена |
| `--color-bg-surface` (карточки, плитки, поля) | `var(--p-bg-200)` #1d2b40 | `var(--color-raised)` #371f28 | замена |
| hover-ступень (`--p-bg-300`) | #26354d | токен удаляется; hover — граница/заголовок (см. FR-132), фон не меняется | замена |
| `--color-text-primary` | `--p-text-900` #e7edf4 | `var(--color-text)` #f7ece4 | замена |
| `--color-text-secondary` | `--p-text-600` #a7b7c8 | `var(--color-muted)` #c6ad9f | замена |
| `--color-text-muted` | `--p-text-500` #8496a8 | `color-mix(in srgb, var(--color-muted) 85%, var(--color-bg))` | замена (derived) |
| `--color-text-on-accent` | #0e1621 литерал | `var(--color-on-accent)` #1e0f14 | замена |
| `--color-accent` | `--p-amber-400` #f0b45c | `var(--color-accent)` #d6a85c (золото) | замена |
| `--color-accent-hover` | #f6c17a литерал | `color-mix(in srgb, var(--color-accent) 90%, var(--color-text))` | замена (derived) |
| `--color-accent-soft` | `--p-amber-900` #3a2c12 | `var(--color-warning-soft)` #4e3124 | замена |
| `--color-focus` | `--p-cyan-300` #4fd8eb | `var(--color-accent)` #d6a85c | замена |
| `--fastline` / `--fastline-tint` | янтарь / янтарная подложка | `var(--color-accent)` / `color-mix(in srgb, var(--color-accent) 8%, var(--color-surface))` | замена |
| `--status-error` / `--status-success` | coral / teal | `var(--color-danger)` #e9817f / `var(--color-success)` #5ad88e | замена |
| `--priority-high` | coral | `var(--color-accent-2)` #c4505c (бордо, кромка 2.1 БА) | замена |
| `--priority-medium` | violet | `var(--color-warning)` #f0aa42 | замена |
| `--priority-low` | teal | `var(--color-border)` #3d2229 | замена |
| `--priority-*-soft`, `--status-error-bg` | color-mix 12% coral/violet/teal | color-mix 12% accent-2/warning/border — паттерн сохраняется | замена |
| `--radius-field` | 6px | `var(--radius-sm)` 10px | замена |
| `--radius-card` | 8px | `var(--radius-md)` 18px | замена |
| `--shadow-soft` / `--shadow-modal` | rgba-литералы | `var(--shadow-1)` / `var(--shadow-2)` из tokens.css | замена |
| `--font-family` | системный sans | стек Golos Text (self-host + fallback) | замена |
| `--font-family-display` | системный sans | стек PT Serif | замена |
| `--font-family-data` | ui-monospace стек | стек JetBrains Mono | замена |
| `--focus-ring` | bg-000+cyan кольцо | `0 0 0 2px var(--color-bg), 0 0 0 4px var(--color-accent), 0 0 12px color-mix(in srgb, var(--color-accent) 30%, transparent)` | замена |
| `--speed-fast` | 140ms | `var(--dur)` 160ms; добавить `--ease: cubic-bezier(.2,.7,.2,1)` из tokens.css | замена+add |
| `--speed-modal` | 200ms | 200ms (без изменений) | нет |

**Добавить (нет в app.css):** полный A-набор `--color-bg/surface/raised/text/muted/border/accent/on-accent/accent-2/link/success(-soft)/warning(-soft)/danger(-soft)/on-danger`, `--font-display/body/ui/mono`, `--radius-pill` (999px — для пилюль приоритета вместо литералов), `--ease`. Уровни текста/отступов tokens.css (`--text-*`, `--space-1…6`) **не переносятся** — см. 1.5.

**Удалить вместе с местами использования (декор «Пульта», отсутствующий в A):** `--texture-grid`, `--grid-line` (микро-сетка), `--glow-amber`, `--glow-cyan`, `--accent-cyan`, `--cyan-border`, `--led-glow-*` (LED-точки остаются статичными цветами: mute `--color-muted` / работа `--color-warning` / готово `--color-success`, маппинг 2.2 БА), `--fastline-track` → `color-mix(in srgb, var(--color-accent) 16%, transparent)` (заменить, не удалять — используется треком отсчета), `--overlay` → `color-mix(in srgb, var(--color-bg) 65%, transparent)`. HUD-уголки (linear-gradient-корнеры) в board.css/app.css удаляются; класс `hud` в DOM **сохраняется** (ОГР-28) как нейтральная обертка без визуальных правил. `--tracking-caps/.06em`/`--tracking-micro/.14em` сохраняются в `:root` (используются страницами вне объема); в объеме A капс-лейблы применяются только там, где мокап их задает.

### 1.4 Слоистая структура :root и светлый дефолт

Сейчас app.css — темный дефолт без светлой темы. Разруливание:

1. **`:root`** = токены A dark (канон 1.2) + переименованные legacy-слои. **Примитивы `--p-*` «Пульта» сохраняются в `:root` как legacy-слой** — на них до сих пор ссылаются CSS страниц вне объема (`login.css`, `settings.css`, `search.css`, `profile-settings.css`, weather-стили). Значения `--p-*` не меняются.
2. **Каркасные семантические токены** (таблица 1.3) переключаются на значения A. Следствие, принимаемое осознанно: страницы вне объема наследуют палитру каркаса (фон/текст/акцент/фокус) через семантический слой, свои «пультовские» декор-эффекты (HUD, cyan-глоу) сохраняют до отдельного пакета миграции — визуальный гибрид, зафиксированный в решении ОВ-4 (§3).
3. **`:root[data-theme="light"]`** = light-блок tokens.css (все 17 цветовых переменных; `--color-accent-2` включить явно — wd-scan-снимок его потерял) + `color-scheme: light` + переопределение derived-токенов (`--color-text-muted`, `--color-accent-hover`, `--fastline-tint`, `--overlay`, `--focus-ring` — все на color-mix, пересчитываются автоматически). `--p-*` в light-теме не переопределяются (известный хвост: страницы вне объема в light частично темные — вне объема, в ассерты не брать).

Правило токен-дисциплины продлевается: **новые hex вне токен-блока app.css запрещены** в обоих CSS-файлах тем; ассерт-гейт `test_qa21_gallery_design.py` («не-литералы») сохраняется как регулятор.

### 1.5 Конфликт space-шкал — осознанное решение

Шкалы не совместимы: app.css `--space-05/1/2/3/4/6` = 4/8/16/24/32/48px, tokens.css A `--space-1…6` = 4/8/16/24/40/64px, имена пересекаются с разными значениями. **Шкала A НЕ переносится**: существующие `--space-*` остаются (8px-сетка, на ней завязаны пороги тестов bug013/014 и кратность 8 в test_p12_ui_polish_r8). Dev в объеме A использует существующие имена; 32px-литералы модалок сохраняются (решение ОВ-6, §3). Аналогично шкала `--text-*` A не переносится — действующие `--font-size-*` сохраняются (смена глобальных кеглей сломает пороги высот textarea/тултипов без выгоды); меняется только **семейство** шрифтов (1.3) и serif на заголовках (2.3 БА: `--font-family-display` → h1.page-title, h3.task-card-title, .brand-name, .fastline-title, wiki/gallery/video h1, .lb-title, #player-title).

### 1.6 Переключатель темы (точки правки)

**base.html (точка вставки — решение ОВ-5, §3):** кнопка первым элементом `.sidebar-footer`, ДО «Настройки»:

```html
<button type="button" id="theme-toggle" class="theme-toggle" aria-pressed="false" aria-label="Переключить светлую и темную тему">
  <svg class="theme-icon theme-icon-moon" viewBox="0 0 24 24" aria-hidden="true">…луна, stroke=currentColor…</svg>
  <svg class="theme-icon theme-icon-sun"  viewBox="0 0 24 24" aria-hidden="true">…солнце…</svg>
</button>
```

Единый узел для десктопа и мобильного drawer (≤860px drawer и есть сайдбар — кнопка доступна там же; нового элемента в mobile-header нет). Обе иконки inline-SVG (ОГР-8), показ управляется CSS: `:root[data-theme="light"] .theme-icon-moon{display:none}` и наоборот — JS иконку не меняет. Стиль: 44×44 (NFR-23), `color: var(--color-muted)`, hover `--color-text`, `:focus-visible` — общий `--focus-ring`.

**base.html `<head>`, инлайн-скрипт ДО `<link rel="stylesheet">`** (анти-FOUC; app.js грузится в конце body — поздно для темы):

```html
<script>
(function(){try{var t=localStorage.getItem("theme");
if(t==="light"||(!t&&window.matchMedia&&window.matchMedia("(prefers-color-scheme: light)").matches)){document.documentElement.setAttribute("data-theme","light");}}catch(e){}})();
</script>
```

**app.js (добавление, существующий код не трогается):** делегат на `#theme-toggle` — flip `data-theme` на `<html>`, запись `localStorage("theme")` = `"light"`/`"dark"`, синхронизация `aria-pressed` (в т.ч. начальная — при загрузке по факту атрибута, т.к. сервер тему не знает). Слушателя `prefers-color-scheme` change — нет: явный выбор пользователя (даже «dark») приоритетен над системной сменой. Блокировка localStorage (private mode) — try/catch, тема живет до перезагрузки, ошибка молчит.

**Персистность — решение ОВ-2: localStorage, не серверный профиль** (§3).

### 1.7 Файлы и зоны правки (сводка)

| Файл | Правка |
|---|---|
| `frontend/static/css/app.css` | `:root` (таблица 1.3 + legacy `--p-*`), новый `:root[data-theme="light"]`, `@font-face`, body-фон без микро-сетки, тумблер `.theme-toggle`, каркасные эффекты (skip-link/selection/фокус — на новые токены) |
| `frontend/static/css/board.css` | доска/колонки/карточки/кромки приоритета/LED/fastline/dnd-состояния (`drop-target`→бордо, `drop-forbidden`, `drag-ghost`)/формы/модалки (task+detail)/pagehead-readout — все на семантические токены; HUD-уголки удалить |
| `frontend/static/css/gallery.css` | сетка/плитки/лайтбокс/загрузка/реакции — токены A; подсветка «мой голос» — золото |
| `frontend/static/css/wiki.css` | дерево/статья/редактор/история/rich-блоки/`<mark>` — токены A |
| `frontend/static/css/login.css, settings.css, search.css, profile-settings.css` | **НЕ правятся** (вне объема) |
| `frontend/templates/base.html` | инлайн-инициализатор темы, кнопка `#theme-toggle`, favicon A (ОВ-1), комментарий-хвост |
| `frontend/static/js/app.js` | только toggle-блок (1.6) |
| `backend/app/pages.py` | бамп `static_v` → `redesign-a` (содержимое статики меняется при тех же путях — прецедент `redesign-1`) |

video-страница стилей отдельным файлом не имеет (видимо, из app/board-токенов) — dev сверяет по `design-forge/extra/video/` и при необходимости точечные правила в app.css.

---

## 2. Openspec-дельта

### 2.1 Формат и правила (по практике репо, пакет redesign-console как шаблон)

Пакет: `openspec/changes/redesign-ui-a/` с `proposal.md`, `tasks.md`, `specs/<capability>/spec.md`. Черновик подготовлен в **`docs/sa/openspec-delta/`** (та же структура — переносится в openspec/changes Волной 5/архивации, не раньше: пока пакет активен, CI-ворота flow_check сверяют дельты по заголовкам).

Жесткие правила (из experience репо):
- **Заголовки MODIFIED-requirements остаются ДОСЛОВНЫМИ** (включая «„Пульт“» в тексте заголовка): слияние при архивации машинное, по заголовку. Переименование «…на токенах «Пульт»…» → «…направления A…» = красные ворота контракта 7. Меняются только тела и THEN-части сценариев.
- **MODIFIED = полная замена блока**: все существующие сценарии requirement переносятся в дельту дословно (порядок: прежние → правки THEN), иначе архивация откажется «молча выкинуть» сценарий.
- Каждый requirement несет ≥1 `#### Scenario:` с `- **GIVEN/WHEN/THEN**` (в репо — русские шапки GIVEN/WHEN/THEN как в мастере).
- Требование ≤ ~500 символов или сплит по границе прозоры с переносом сценария (WARNING strict-валидатора валит CI на specs/**).
- Перед превращением черновика в пакет: `openspec validate --all --strict` green; после слияния — сверка `openspec show redesign-ui-a --json --deltas-only` с мастером.
- Новые маршруты API не вводятся — I3-проверке ловить нечего; dnd/move-пути не меняются.

### 2.2 Состав дельты — минимальный набор (по объему задачи)

| Capability | Тип | Requirement (заголовок literal) | Что меняется |
|---|---|---|---|
| `board` | MODIFIED | «Визуальные эффекты доски на токенах „Пульт“ (FR-132)» | эффекты доски на токенах A: hover — золото на заголовке/границе вместо bg3-ступени и `--p-border-2`; HUD/сетка удалены; fast-карточка — золотой сигнал; бордо вне кромок high не используется |
| `gallery` | MODIFIED | «Сетка галереи и лайтбокс в стиле „Пульт“ (FR-125)» | плитка/лайтбокс на A-токенах, radius-md, чипы, золотые первичные действия, gold-лайк; сценарий «Тесты галереи без цветовых правок» — без изменений |
| `video-ui` | MODIFIED | «Экран „Видео“ в стиле „Пульт“ (FR-126)» | панели surface, mono, LED-статусы (success/warning/danger), золотые действия |
| `wiki` | MODIFIED ×2 | «Отображение rich-контента в стиле „Пульт“ (FR-123)», «Визуальный стиль страниц Wiki „Пульт“ (FR-124)» | h2 — serif с бордовой inset-полосой (вместо teal), спойлер — золотая сигнализация (вместо HUD+cyan), код-блок/таблица на A; дерево — surface+золото, `<mark>` — warning-soft |
| `accessibility` | MODIFIED ×2 | «Контраст WCAG 2.1 AA на токенах „Пульт“ (NFR-41)», «Фокус с клавиатуры — cyan-фокус-ринг (NFR-42)» | контраст AA **в обеих темах** (dark + `data-theme="light"`), программная проверка сохраняется; focus-ring — золото вместо cyan; `::selection` — золото |

Сценарии: у NFR-41 и NFR-42 добавляется смысловое условие «обе темы» в THEN существующих сценариев; **новые сценарии не вводятся** — число сценариев в спеках сохраняется (перестраховка от счетчиков покрытия).

### 2.3 Сопровождающие дельты (вне минимального списка, логически обязательны)

Мастер-спека `design-tokens` (FR-128 «Единый источник дизайн-токенов „Пульт“», FR-129 «Роли акцентов — янтарь сигнал, cyan актив/фокус», FR-130 «Техноязык — HUD, LED, микро-лейблы, сетка») дословно требует tokens-console.html как источник, cyan-роль и HUD/сетку. Без MODIFIED этих требований мастер-спека становится ложной сразу после Волны 3. Включены в черновик как **обязательные сопровождающие**: FR-128 — источник правды = `design-forge/a/tokens.css` + `:root` app.css, `color-scheme` по теме, старые значения «Пульта» заменены, сценарий static_v-бампа обновлен (`redesign-a`); FR-129 — роли: золото сигнал/актив/фокус, бордо — high-приоритет/danger-кромки; FR-130 — HUD/микро-сетка удалены, LED-точки и mono-readout сохранены как статусы.

Плюс **ADDED** в `navigation`: «Переключатель темы в каркасе» — новый каркасный элемент обязан иметь требование (кнопка в sidebar-footer, aria-pressed, localStorage, prefers-color-scheme fallback, инлайн-инициализация без FOUC, обе темы AA). В минимальный список задачи не входит — помечено в proposal как решение СА, выносимое на утверждение ПМ/Заказчика вместе с пакетом.

### 2.4 Порядок архивации

Все дельты — MODIFIED/ADDED по независимым спекам, взаимных зависимостей архивации нет (пакет один). Архивация — `openspec archive redesign-ui-a --yes` ОДНИМ PR с уже слитыми в мастер телами (git mv-путь, правило «сначала дельты в master, потом mv — или одним коммитом»). У спек-новичков нет — все capability существуют, TBD-Purpose-риска нет.

---

## 3. Решения по 6 открытым вопросам БА

| # | Вопрос | Решение | Обоснование (одной строкой) |
|---|---|---|---|
| ОВ-1 | favicon: оставить/перекрасить | **Перекрасить** в палитру A: фон #1e0f14, документ #d6a85c (золото), детали #2a161d; мотив прежний (лист с загнутым углом); бамп `cache:v=2`→`v=3`; ассерт `test_p12_nav_icons_favicon_r8` (#f0b45c) правится на #d6a85c | Favicon — часть каркаса, виден на всех страницах в обеих темах, янтарь «Пульта» будет диссонировать с бордо-интерфейсом; политика кеш-маркера существует и обязательна |
| ОВ-2 | Персистность темы: localStorage или серверный профиль | **localStorage**, ключ `theme`, значения `light`/`dark`; без сервера; fallback `prefers-color-scheme: light` только при отсутствии записи | Серверный профиль требует правки API/БД (запрещено объемом), а тема — per-device настройка, для 2 пользователей серверный профиль выгоды не дает |
| ОВ-5 | Точка вставки toggle | **`.sidebar-footer`, первым элементом перед «Настройки»**, id=`theme-toggle`, 44×44, aria-pressed, на ≤860px доступен внутри drawer | Единственный каркасный узел, видимый на всех страницах без нового топбара; в drawer'е это та же навигационная зона, дубликат в mobile-header плодил бы два фокус-стопа |
| ОВ-4 | `test_redesign_console.py`: страницы вне объема (settings/weather/login) — скип или правка | **Скип запрещен; правка ассертов**: страницы вне объема остаются на текущем CSS, но наследуют каркасную палитру через семантический слой → ассерты для них переводятся на семантические/вычисляемые значения (getComputedStyle от var) и на неизменность их DOM/«пультовского» декора; hex-gate TC-032 переписывается на whitelist A | Скип теряет покрытие каркаса (сайдбар/тема видны отовсюду), а «внести в объем» без решения Заказчика нельзя — правка ожиданий фиксирует фактическое состояние честно |
| ОВ-3 | Подпись «Выполнено сегодня · N» — точный текст | **НЕ добавлять** узел; если Заказчик отдельно решит добавить — литеральный текст «Выполнено сегодня · N» (N = число done-задач дня, источник как `data-col-count`), новым узлом в `.col-head` done-колонки через cards.js вне данного пакета | Семантика мокапа уже покрыта заголовком «Выполнено» + mono-счетчиком столбца + readout DONE; новый узел = правка cards.js/DOM — риск ОГР-28 и порогов без визуальной выгоды |
| ОВ-6 | Отступы 32px модалок vs пороги test_bug013/014 | **Сохранить текущие паддинги** (`body 16px 32px`, `head 24px 32px 16px`, `.attr 8px 16px`); шкала space A не переносится (§1.5); тесты bug013/014 НЕ правятся | Пороги — действующий контракт на стабильную геометрию; 32px не противоречит 8px-сетке, смена «ради шкалы A» — риск без выгоды |

Дополнительно (решения СА, не ОВ): класс `hud` сохраняется в DOM без визуальных правил (§1.3); `preset-v` остается контейнером доски; `pagehead`/`readout` сохраняются с mono/tabular-nums; подпись бренда «SYS · NOM» не меняется (DOM вне объема).

---

## 4. План правки тестов (Волна 4: 12 файлов / 114 тестов)

**Железное правило:** правится ТОЛЬКО литерал ожидаемого значения (палитра/шрифт/радиус/тень/тайминг). Локаторы, семантика, пороги, методология (getComputedStyle-снапшоты, контраст-скрипт, reduced-motion, skip-link) — без изменений. Сьюты §3.3 БА не открываются вовсе. Точные computed-значения derived-токенов (color-mix) переснимаются после Волны 3 — в таблице канон-значения токенов A.

**Пометка (фикс по code-review minor-5):** в `test_redesign_console.py:128-145` и `test_qa21_gallery_design.py:68-73` методология парсинга `:root` переписана на «первый `:root`-блок» — отклонение от «методология без изменений», но ВЫНУЖДЕННОЕ и КОРРЕКТНОЕ: с появлением light-блока `:root[data-theme="light"]` старый dict-парсинг по всему файлу вернул бы light-значения вместо dark-канона. Ассерт legacy `#f0b45c` (clay_var) сохранен.

Справочник новых значений: bg `rgb(30,15,20)` #1e0f14 · surface `rgb(42,22,29)` #2a161d · raised `rgb(55,31,40)` #371f28 · border `rgb(61,34,41)` #3d2229 · text `rgb(247,236,228)` #f7ece4 · muted `rgb(198,173,159)` #c6ad9f · accent/золото `rgb(214,168,92)` #d6a85c · accent-2/бордо `rgb(196,80,92)` #c4505c · warning `rgb(240,170,66)` #f0aa42 · warning-soft `rgb(78,49,36)` #4e3124 · success `rgb(90,216,142)` #5ad88e · danger `rgb(233,129,127)` #e9817f · радиусы 10/18/28 · шрифты PT Serif/Golos Text/JetBrains Mono · light-тема — значения light-блока tokens.css.

| Файл (тестов) | Ключевые замены «старое → новое» |
|---|---|
| `test_redesign_console.py` (36) | Палитра-снапшот: BG0 rgb(14,22,33)→rgb(30,15,20); BG1-3→surface/raised-маппинг 1.3; AMBER #f0b45c→#d6a85c; CYAN #4fd8eb→#d6a85c (фокус/актив); TEAL→success #5ad88e; CORAL→danger #e9817f / бордо #c4505c для high. HUD-уголки «≥8 linear-gradient»→«0 HUD-градиентов» (инверсия). LED: teal/amber→success/warning, blink сохраняется (reduced-motion — как прежде). Микро-сетка `--texture-grid 32px` (TC-010)→токен удален: ассерт на отсутствие + снапшот новых канон-токенов. caps-tracking 0.06/0.14em — переснять (сохранены в :root, но применение в объеме сузилось). focus-visible cyan→золото. Радиус 8px→10/18px по узлу. Сайдбар 232px+1fr — геометрия не меняется (ассерты остаются). Логин/settings/wiki/gallery/video/weather (TC-031/032): weather и settings — на семантические/неизменность-декора (ОВ-4), wiki/gallery/video — на токены A. Hex-gate whitelist v3→whitelist A-набора |
| `test_board_fastline.py` (9) | Фон зоны rgb(58,44,18) → computed `--fastline-tint` (color-mix золота 8% на surface) — переснять; «нет .fastline-count» — не меняется |
| `test_coverage_fastline.py` (13) | outline `drop-target` rgb-литерал → бордо `--color-accent-2` rgb(196,80,92); цвета направлений dnd → accent-2/accent |
| `test_qa21_gallery_design.py` (2) | Whitelist: `--p-amber-400/#f0b45c`→`--color-accent/#d6a85c`, `--p-amber-900`→`--color-warning-soft/#4e3124`; гейт «нет rgba/hex вне токенов» сохраняется |
| `test_qa21_netdata_sidebar_ui.py` (6) | Подпись #a7b7c8→#c6ad9f; hover bg2 #1d2b40→#2a161d; active bg3 #26354d→#371f28; focus cyan→#d6a85c; иконка 16px — не меняется |
| `test_r3_formv3_ui.py` (5) | Линия полей 2px — не меняется; focus-ring→золото; чипы radius→10px; пилюля `:has(:checked)` bg→бордо (high)/warning (mid)/border (low); «иконка display none/inline», тексты опций — не меняются |
| `test_r3_vis_ui.py` (5) | Hover accent заголовка→#d6a85c; empty-state dashed→`--color-border` rgb(61,34,41), min-height ≥48px — не меняется; тайминги: 140ms→160ms (`--speed-fast`←`--dur`), имена анимаций v-in/dnd/fill — не меняются. Пометка (фикс по code-review minor-3): в TC-vis-101 ассерт фона hover ИНВЕРТИРОВАН (`after_bg != before_bg` → `== before_bg`) и проверяемые токены переключены (`--p-border-2`/`--p-text-900` → `--color-accent`) — это не «только литерал», а след FR-132-дельты (ступень hover-фона удалена: «hover — граница/заголовок, фон не меняется»); исключение из железного правила признано и зафиксировано здесь |
| `test_r5_profile_card_ui.py` (7) | bg rgb(29,43,64)→rgb(42,22,29); radius 8px→18px; shadow rgba(0,0,0,.4)→`--shadow-1`; кнопка rgb(240,180,92)→rgb(214,168,92); поля 2px-линия, pill 999px — не меняются |
| `test_p12_ui_polish_r8.py` (7) | `.btn-action` радиус 6px→10px; кратность отступов 8px — не меняется; чекбокс 16px — не меняется |
| `test_p15_wiki_tree.py` (10) | `<mark>` bg rgb(58,44,18)→rgb(78,49,36) (`--color-warning-soft`); раскладка 280px+контент, ≤480px одна колонка — не меняется |
| `test_r6_tag_combobox_ui.py` (11) | Подсветка color rgb(240,180,92)→rgb(214,168,92); bg rgb(58,44,18)→rgb(78,49,36); поведение клавиатуры/aria/чипы — не меняются |
| `test_bug004_board_empty_state.py` (3) | dashed-border цвет→`--color-border`; класс `board-column-empty`, `::before`-контент, min-height 72px — не меняются |

Плюс точечные правки в смешанных сьютах §3.2 БА (только цветовые литералы, где они есть: `test_qa21_gallery_ui.py` hex-точки, `test_p12_nav_icons_favicon_r8.py` favicon #f0b45c→#d6a85c, `test_r6_wave2_ui.py` token-цвета) и **добавление** новых тестов переключателя темы (toggle, aria-pressed, localStorage-персистность, fallback, отсутствие FOUC-класса) — новые файлы, не правки существующих.

---

## 5. Порядок dev-волн (Волна 3)

Правило проверки каждой ступени: браузерная сверка с эталоном (`design-forge/a/` для каркаса/доски, `design-forge/extra/*` для wiki/gallery/video) **в обеих темах на 1440/768/390** + прогон затронутых функциональных сьютов §3.3 (должны остаться зелеными без правок — ранний сигнал регресса селекторов) + контраст-скрипт NFR-41 на обе темы.

1. **Каркас + токены** (приоритет по плану): app.css `:root` (A dark + light-блок + `@font-face` + legacy `--p-*`), body-фон, `.theme-toggle`; base.html (инлайн-инициализатор, кнопка, favicon A + cache:v=3); app.js toggle; бамп `static_v` → `redesign-a`. Проверка: обе темы переключаются без FOUC на доске (board.css еще старый — допустимо, board.css правится шагом 2 и на семантических токенах не рассыпается), skip-link/фокус/контраст, функциональные каркасные сьюты зеленые.
2. **Доска + фастлайн + модалки задач** (board.css): колонки-панели, карточки с кромкой приоритета (2.1), LED-точки, serif-заголовки, mono-счетчики, чипы, кнопки, fastlane (золото-кромка), dnd-состояния, форма и read-only модалка (meta-строки, деструктив в подвале). Проверка: эталон board.html/kit.html/task.html, F-01…F-14 функционально, drag&drop руками.
3. **Wiki** (wiki.css): дерево, статья, breadcrumb, редактор, история, rich-блоки (h2 serif+бордо-инсет, спойлер-золото, код-блок, таблицы, `<mark>`). Проверка: эталон extra/wiki, test_rich_tools зеленые без правок.
4. **Gallery** (gallery.css): сетка/masonry-ритм, плитки, фильтры, загрузка, лайтбокс, реакции-золото. Проверка: эталон extra/gallery, свайп/лайтбокс руками.
5. **Video**: список/фильтры/загрузка/плеер/реакции/комментарии. Проверка: эталон extra/video, статусы конвертации различимы.
6. **Хвост**: страницы вне объема — CSS не трогается; контрольный прогон их смоуков (auth/settings/weather) — зеленые, отклонения палитры каркаса зафиксированы для QA (ОВ-4).

После шага 6 — передача на Волну 4 (QA: правки ассертов по §4, regress-final).

---

## 6. Что НЕ входит и риски

- Контент мокапов, топбар «Разработка/Контент/Инфра», отдельная страница task — не переносятся (БА §0).
- Риски: (а) self-host-шрифты — неверное сопоставление woff2-хешей семействам проверяется визуально в 3.1 до продолжения; (б) color-mix-derived значения в старых браузерах — целевые браузеры проекта поддерживают (уже используется в `:root` «Пульта»); (в) гибридный вид страниц вне объема в светлой теме — известное ограничение, принято в ОВ-4, миграция отдельным пакетом.
