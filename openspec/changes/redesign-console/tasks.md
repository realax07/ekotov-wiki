# tasks.md — redesign-console

Флоу 1 (СА → [design] → dev-волны → полный QA-контур → regress). Дизайн-фаза
ЗАВЕРШЕНА И УТВЕРЖДЕНА Заказчиком ДО пакета (базлайн PR #242, коммиты b5a1475 +
a2685ee; design/redesign-pro/README.md §Утверждение) — новых мокапов не требуется,
[design]-этап только фиксирует токены. Правило: 1 задача = 1 сабагент +
независимый code_reviewer; ворота — `openspec validate --all --strict` green;
DOM-хуки сохранять (ОГР-28); токен-дисциплина (hex вне :root запрещен).
Трассировка: задача → FR-118…FR-127 / NFR-41…44 → Requirement дельт.
Параллельные волны — маркером [P], зоны не пересекаются.

## ЭТАП 0. Конвейер

- [x] 0.1 [docs] sa: create_change — пакет `redesign-console` (proposal,
  research, design, impact, tasks, дельты по 12 capability; validate strict
  PASS — после фикс-раунда по review-architecture.md F1–F8, см. REPORT-0.1).
  Текущая задача. (Отчет — REPORT-0.1.md пакета)

## ЭТАП 1. [design] Фиксация токенов

- [ ] 1.1 [design] [S] Фиксация токенов «Пульт» как прод-источника: перенести
  блок `:root` из `design/redesign-pro/tokens-console.html` (дословно, без
  правки значений) в `frontend/static/css/app.css` (замена V3-блока);
  `color-scheme: dark`; семантические имена сохранены (design §D1).
  V3-примитивы (`--p-paper-*`, `--p-ink-*`, `--p-clay-*`, `--p-blue-*`,
  `--p-red-*`, `--p-olive-*`, `--p-amber-700`) НЕ удалять в этой задаче:
  сохранить под новым блоком как deprecated-алиасы с исходными V3-значениями
  (комментарий «deprecated, удалить в 2.7») — board.css/wiki.css/gallery.css
  мигрируют только в волнах 2.2/2.3/2.5, без алиасов сайт в промежутке сломан.
  Проверка: скрипт контраста ≥ 4.5:1 на всех парах (REPORT); grep по
  `frontend/static/css/app.css` на V3-примитивы = 0 вхождений ВНЕ блока
  deprecated-алиасов (full-tree grep — гейт 2.7, design §D1).
  (FR-118, FR-119, FR-120)
- [ ] 1.2 [design] [S] Эскиз favicon «Пульта» (перекраска существующего
  inline-SVG data-URI в base.html: bg #0e1621, документ #f0b45c, детали
  #172335; бамп cache-маркера `?v=` внутри data-URI — design §D4).
  Проверка: favicon отрисовывается, маркер изменен. (FR-118; design §D4)

## ЭТАП 2. [dev] Волны по экранам (static_v бамп в волне 2.1; после 1.1)

- [ ] 2.1 [M] Dev: волна каркаса — base.html + app.css: grid-раскладка 232px+1fr,
  сайдбар «Пульта» (9 пунктов: 7 в основной группе + Настройки/Профиль в
  футере, LED-бренд, kbd-футер — декоративный aria-hidden, только реально
  действующие хоткеи (design §D2), aria-current cyan-паттерн), skip-link,
  focus-visible/selection/reduced-motion глобально, favicon из 1.2, бамп
  `static_v` → `redesign-1` в `backend/app/pages.py:57` (единственная правка
  бэкенда). Границы: `frontend/templates/base.html`,
  `frontend/static/css/app.css`, `backend/app/pages.py` (1 строка).
  Проверка: smoke — все разделы открываются в темной теме, таб-порядок со
  skip-link, `?v=redesign-1` во всех static-ссылках. (FR-118…FR-120,
  NFR-42…44; navigation MODIFIED/ADDED)
- [ ] 2.2 [P] [M] Dev: волна доски + фастлайна (параллельно 2.3/2.4; зоны
  board.*) — колонки с HUD/LED/mono-счетчиками, карточки bg2/hover bg3,
  приоритет-бейджи, fast-карточка «▲», pagehead с readout, янтарная кнопка
  «Новая задача», фастлайн-панель (glow-amber, FST-лейбл, T-отсчет, трек
  amber→cyan), fastline-блоки форм создания/редактирования на токенах.
 Границы: `frontend/templates/board.html`,
 `frontend/static/css/board.css`, `frontend/static/js/board/**` (только
 декор/трек отсчета). Проверка: нецветовые тесты доски и fastline зеленые;
 все JS-селекторы доски/фастлайна (design §D2: `.task-card*`,
 `.board-column*`, `.fastline-column`, `.fast-row`, `#fastline`, …)
 резолвятся после правки шаблонов;
 цветовые правятся в 4.4. (FR-122; board, fastline дельты)
- [ ] 2.3 [P] [M] Dev: волна wiki (+rich-контент) — страница статьи (breadcrumb
  микро-лейбл, разделитель-трек, h2 teal-полоса, h3, спойлер cyan-glow,
  код-блок, таблица с LED-статусами), дерево с янтарной подсветкой, редактор/
  история на общих токенах. Границы: `frontend/templates/wiki.html`,
  `frontend/static/css/wiki.css`, `frontend/static/js/wiki/**` (только
  декор). Проверка: test_rich_tools, p15-серия нецветовые — зеленые; все
  JS-селекторы wiki/rich-зоны (design §D2) резолвятся после правки шаблонов.
  (FR-123, FR-124; wiki дельты)
- [ ] 2.4 [P] [S] Dev: волна login + settings/profile — панель login с
  HUD-уголками/янтарной кнопкой/coral-ошибкой; карточки настроек, таблица
  категорий, профиль + кроп на dark. Границы: `frontend/templates/login.html`,
  `profile-settings.html`, `settings.html`, `frontend/static/css/login.css`,
  `profile-settings.css`, `settings.css`. Проверка: test_auth_ui,
  test_settings_categories_ui, test_r5_crop_ui нецветовые — зеленые.
  (auth, settings дельты)
- [ ] 2.5 [P] [S] Dev: волна галерея + видео + погода — плитки/лайтбокс,
  видео-карточки с LED-статусами, погода-readout. Границы:
  `frontend/templates/gallery.html`, `video.html`, `weather.html`,
  `frontend/static/css/gallery.css`, `frontend/static/js/gallery.js`,
  `video.js`. Проверка: нецветовые тесты трех разделов — зеленые.
  (FR-125…FR-127; gallery, video-ui, weather-ui дельты)
- [ ] 2.6 [P] [S] Dev: волна поиск — вкладка результатов (янтарная инверсия
  подсветки), фильтр-конструктор (dark-select'ы, кнопки «Пульта»), чипы.
  Границы: `frontend/templates/search.html`,
  `frontend/static/css/search.css`, `frontend/static/js/search.js`.
  Проверка: test_search_r4_ui, test_search_suggestions_ui нецветовые —
  зеленые; BUG-014 computed-ассерт зеленый на новых токенах. (search дельты)
- [ ] 2.7 [S] Dev: мобильная раскладка (≤860px) — сайдбар наверх, nav-строка,
  kbd скрыт, hit-targets ≥44px, доска/фастлайн/кнопки в столбец (мокап
  @media-блок); финальный проход по всем волнам на 860px; УДАЛЕНИЕ
  deprecated-алиасов V3 из `:root` app.css (заложены в 1.1) + full-tree grep
  `frontend/static/css/**` и `frontend/templates/**` на
  `--p-paper-|--p-ink-|--p-clay-|--p-blue-|--p-red-|--p-olive-|--p-amber-700`
  = 0 вхождений (финальный контракт design §D1; токен-дисциплина: нет hex вне
  токенов). Границы: только
  `@media`-секции CSS из волн 2.1–2.6 + блок алиасов app.css. Проверка:
  web-mobile прогон
  (p23_fastline_mobile_ui и мобильные ассерты) зеленый. (FR-121, NFR-44)

## ЭТАП 3. [tests] ПОЛНЫЙ QA-контур (обязателен: заявка «Qa и вадидацию не забудь»; J39/H5)

- [ ] 3.1 [tests] [S] qa_impact_analysis: актуализировать impact.md по
  фактическому диффу волн 2.1–2.7 — MODIFIED-дельты покрывают весь фронт;
  сверить список сломающихся тестов (8 файлов из impact.md) с реальным прогоном
  web-набора; зафиксировать REPORT-impact (дополнения, если найдены новые
  сломавшиеся). (impact.md; H5)
- [ ] 3.2 [tests] [S] qa_checklist: чеклист QA по дельтам — по каждому
  Requirement/Scenario дельт пункт проверки (12 capability, 25 Requirement,
  105 Scenario, статус-таблица J23). Выход: `openspec/changes/redesign-console/qa/checklist.md`.
- [ ] 3.3 [tests] [M] qa_author + qa_case_reviewer: кейсы ИЗ ДЕЛЬТ спеки (не
  из кода) — TC-redesign-001…NNN на каждый Scenario (каждый Scenario дельты
  имеет кейс; Must-сценарии — автотест или скриптовый прогон с REPORT);
  независимый qa_case_reviewer ревьюит до автоматизации. Выход:
  `openspec/changes/redesign-console/qa/cases/` (new/ → approved/).
- [ ] 3.4 [tests] [M] qa_automation: автоматизация кейсов TC-redesign-NNN в
  `tests/web/test_redesign_console_ui.py` (+ точечно p15/p23-файлы) —
  токен-ассерты (цвета из токенов «Пульта»), контраст-скрипт, focus-visible,
  reduced-motion, skip-link, HUD/LED-дисциплина, mobile-брейкпоинт; ПРАВКА
  сломавшихся V3-ассертов строго по impact.md §«Сломающиеся тесты»
  (8 файлов: qa21_netdata_sidebar, r6_tag_combobox, board_fastline,
  p12_ui_polish_r8, p15_wiki_tree, r5_profile_card, r3_vis,
  p12_nav_icons_favicon — новые значения токенов, свойства проверок без
  изменений; ни один не удаляется/skip). Проверка: полный web-набор зеленый.
- [ ] 3.5 [tests] [S] Независимый аудит покрытия (прецедент add-wiki): сверка
  «каждый Scenario дельты ↔ кейс ↔ автотест/прогон» + REPORT-coverage до
  regress-final.

## ЭТАП 4. [devops] Релиз

- [ ] 4.1 [ops] regress-final: прогон всех наборов по порядку api →
  web-desktop → web-mobile → смок на сборке с `static_v=redesign-1`; падение
  набора = баг-репорт и стоп; проверка кеш-инвалидации статики (нет ?v=stale).
- [ ] 4.2 [ops] Прод-выкатка + живая приемка Заказчика (заявка «Qa и вадидацию
  не забудь»; протокол приемки обязателен). После приемки — archive пакета
  (`openspec archive redesign-console`, слияние дельт в master-specs,
  design/tokens.html V3 → archive).
