# Proposal: redesign-ui-a (ЧЕРНОВИК Волны 2 — не активный пакет)

> Статус: черновик СА для `docs/sa/openspec-delta/`. В `openspec/changes/` переносится
> после утверждения ПМ/Заказчиком (Волна 5/архивация). Минимальный набор дельт задан
> объемом задачи (FR-123…126, FR-132, NFR-41/42); сопровождающие дельты design-tokens
> (FR-128…130) и ADDED navigation (переключатель темы) — решение СА (sdd-redesign-ui-a.md §2.3).

## Change ID

`redesign-ui-a`

## Why

Заказчик утвердил направление A «Доска и поток» (бордо/золото, тёмная база,
PT Serif / Golos Text / JetBrains Mono, радиусы 10/18/28; PLAN-REDESIGN-UI-A.md).
Мастер-спеки FR-123…126, FR-132, NFR-41/42, FR-128…130 фиксируют стиль «Пульт»
(янтарь/cyan, HUD-уголки, микро-сетка, tokens-console.html как источник) — после
рестайлинга они морально устаревают. Требуется визуальная дельта спек при полном
сохранении функционального поведения (DOM/селекторы — ОГР-28, API и JS-логика не
трогаются). БА-обоснование: docs/ba/requirements-redesign-ui-a.md (b337fcc).

## What Changes

| Capability | Тип дельты | Requirement (заголовок НЕ меняется — машинное слияние по заголовку) | Суть |
|---|---|---|---|
| `board` | MODIFIED ×1 | Визуальные эффекты доски на токенах «Пульт» (FR-132) | hover — золото на заголовке/границе вместо ступени bg3; HUD/сетка удалены; fast — золотой сигнал |
| `gallery` | MODIFIED ×1 | Сетка галереи и лайтбокс в стиле «Пульт» (FR-125) | плитки/лайтбокс на токенах A, radius-md, золотые первичные действия |
| `video-ui` | MODIFIED ×1 | Экран «Видео» в стиле «Пульт» (FR-126) | панели surface, LED-статусы success/warning/danger, золотые действия |
| `wiki` | MODIFIED ×2 | Отображение rich-контента в стиле «Пульт» (FR-123); Визуальный стиль страниц Wiki «Пульт» (FR-124) | h2 serif + бордовая inset-полоса; спойлер — золотая сигнализация; дерево — surface + золото; `<mark>` — warning-soft |
| `accessibility` | MODIFIED ×2 | Контраст WCAG 2.1 AA на токенах «Пульт» (NFR-41); Фокус с клавиатуры — cyan-фокус-ринг (NFR-42) | AA в ОБОИХ темах (dark + `data-theme="light"`); focus-ring — золото |
| `design-tokens` | MODIFIED ×3 (сопровождающая) | Единый источник дизайн-токенов «Пульт» (FR-128); Роли акцентов (FR-129); Техноязык (FR-130) | источник правды = design-forge/a/tokens.css через `:root` app.css + светлая тема; роли: золото/бордо; HUD и микро-сетка удалены, LED и mono сохранены |
| `navigation` | ADDED ×1 (сопровождающая) | Переключатель темы в каркасе | кнопка `#theme-toggle` в sidebar-footer, aria-pressed, localStorage + prefers-color-scheme fallback, инлайн-инициализация без FOUC |

Сопровождающие технические изменения: замена `:root` app.css на токены A (dark) +
новый блок `:root[data-theme="light"]`, self-host woff2-шрифтов (ОГР-8: без внешних
зависимостей; Google-Fonts @import мокапа в прод не переносится), favicon в палитре A
(бамп cache-маркера `v=2`→`v=3`), бамп `static_v` → `redesign-a` (backend/app/pages.py,
единственная точка). Существующие web-тесты с токен-ассертами «Пульта» ломаются —
инвентарь и план правок: docs/ba/requirements-redesign-ui-a.md §3 и
docs/sa/sdd-redesign-ui-a.md §4 (12 файлов / 114 тестов; правится только литерал значения).

Сквозная нумерация: новые требования не вводятся (только MODIFIED существующих + один
ADDED в navigation) — конфликтов номеров нет.

## Impact

- Код: `frontend/static/css/{app,board,gallery,wiki}.css`, `frontend/templates/base.html`,
  `frontend/static/js/app.js` (только toggle-блок), `frontend/static/fonts/` (новое),
  `backend/app/pages.py` (static_v). API, бэкенд-логика, openapi-контракты — без изменений.
- Тесты: план §4 sdd; функциональные сьюты (20 файлов / 103 теста) — должны остаться
  зелеными без правок.
- Спеки: дельты этого пакета; страницы вне объема (settings/login/search/weather/games)
  спецификациями A не накрываются — остаются на текущем CSS (решение ОВ-4, sdd §3).
