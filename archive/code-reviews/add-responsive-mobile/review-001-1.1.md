# Code Review: add-responsive-mobile — задача 1.1 [M] (каркас и drawer)

- **Ревьюер:** независимый code_reviewer-сабагент (не автор диффа)
- **Дата:** 2026-10-08 16:00 UTC
- **Correlation:** c40c585bdead403587ec019a6174b2b6
- **Делегация дева:** deleg_6640109e (отчет /home/openclaw/.hermes/state/reports/p14-11-dev.md)
- **Reviewer-Delegation:** deleg_063f4658

## Provenance

| Поле | Значение |
|---|---|
| Ревьюемый код | 76f4213e664b56181fbef24a673a2d4a17174f54 (ветка feature/p14-1.1-frame-drawer, PR #106, НЕ мержен) |
| Голова ветки на момент ревью | 0259c926d427e3a5dcc54278019871a01230a69b ([docs] чекбокс 1.1 → [ ]; код 1.1 — только 76f4213) |
| База диффа | a7208e9 (origin/main, PR #105) |
| sha256 frontend/static/css/app.css | c3369479e146cf34e67ee00fc21d7efc408baf5b694175823b756076c4fc6682 (= 76f4213) |
| sha256 frontend/static/js/app.js | 85b7d6795d11f1e1826a82a6cc41247f74c38b0397698d3783c115cc8d8fb06a (= 76f4213) |
| sha256 frontend/templates/base.html | 0ae37cf0b0b34f0a57b2de66b9325877e2471f3e1487659710032e7b67628aba (= 76f4213) |
| sha256 диффа (git diff 76f4213^ 76f4213) | 502d300c0fe6d5399828432713567655a3cd0046ed1b8ce7a7ff4b0a452d7116 |
| Арбитры | openspec/changes/add-responsive-mobile/design.md §1–§2, specs/navigation/spec.md, tasks.md 1.1, мокапы design/mobile-p14/01–02 (утв. decision 2026-10-08-p14-mockups-approve) |

## Вердикт: **APPROVE**

Blocker/major не найдено. Все Scenario задачи 1.1 из specs/navigation/spec.md (Requirements
«Мобильная навигация — бургер и drawer», «Индикация активного раздела на мобильном» — в части,
не относящейся к 1.2) реализованы и независимо воспроизведены ревьюером на собственном стенде.

## Замечания

### minor

| # | Файл:место | Серьезность | Суть | Рекомендация |
|---|---|---|---|---|
| 1 | frontend/static/css/app.css (768px-ветка: `.mobile-header` без z-index при `.sidebar` z310) | minor | При ОТКРЫТОМ drawer pointer-тап по бургеру физически накрыт панелью (elementFromPoint в центре бургера → `.nav-item`), т.е. «закрытие повторным нажатием бургера» кликом недоступно; работает Esc/подложка/пункт и клавиатура (фокус уже на бургере → Enter/Space закрывают — воспроизведено). Это ДОЗАПОЛНЕНИЕ утв. мокапа 02 (шапка без z-index, панель поверх), а не отклонение от спеки: спек-закрытие «повторным бургером» доступно клавиатурно, а на таче пользователь закрывает подложкой/пунктом. | Волна-хвост или задача 1.2: `z-index` шапке на время открытого drawer (напр. `body.sidebar-open .mobile-header { z-index: 320 }`) — или явное решение design_validator'а «мокап важнее» с фиксацией в design.md. Не блокирует 1.1. |
| 2 | frontend/static/js/app.js (document-level keydown Esc) | minor | Esc-листенер вешается на document всегда (даже на desktop); фильтр `isOpen()` делает его no-op, вреда нет — фиксация для истории. | Ничего не делать; опционально guard `if (!burger) return` уже есть — достаточно. |
| 3 | frontend/static/css/app.css (480px-ветка дублирует min-height 44px из 768px-ветки) | minor | Тач-таргеты уже гарантированы 768px-веткой на всем ≤768px диапазоне; 480px-ветка дублирует то же правило без изменения значения. Безвредно, соответствует трактовке design §1 («≤480px-хвосты»). | Оставить как есть (защита от будущих переопределений) либо унести в комментарий. |

Замечаний уровня blocker/major нет.

## Первый круг — спека как закон (specs/navigation/spec.md, design §1–§2, tasks.md 1.1)

| Scenario | Реализация | Проверка ревьюера |
|---|---|---|
| Открытие drawer по бургеру (375×812) | класс `sidebar-open` на body, панель min(78vw,300px)=292.5px, подложка rgba(61,54,48,.45) z300, панель z310 | ✅ воспроизведено: 40/40 ассертов, drawer 292.5px, фокус на «Доска», все 6 пунктов in-viewport/кликабельны/44px, «Выйти» 44px, бургер 44×44 |
| Закрытие drawer (пункт/подложка/повторный бургер/Esc) | app.js: closeDrawer по всем 4 путям, aria-expanded синхронно, фокус → бургер | ✅ Esc ✓, подложка ✓, пункт (переход /search + класс снят) ✓, повторный бургер ✓ клавиатурно (см. minor-1 про pointer-тап) |
| Навигация не дублируется | `.sidebar` единственный DOM-источник; CSS-трансформация | ✅ один `.sidebar-nav` в DOM на 375px |
| Сцена занимает всю ширину | `body.app-shell { flex-direction: column }` + fixed сайдбар | ✅ нет X-скролла на /board, /search, /wiki, /gallery, /settings, /login (scrollWidth ≤ 375) |
| Desktop-вид не меняется (>768px) | мобильные элементы скрыты правилом ДО media-веток | ✅ 1280×1024: бургер/header/подложка display:none; sidebar sticky 200px, content от x=200; класс sidebar-open на desktop не двигает сайдбар |
| Активный пункт в drawer подсвечен (.active) | существующий стиль | ✅ на /search пункт «Поиск» терракотовый .active (заголовок в шапке — зона 1.2, из 1.1 не следует) |
| FR-99: DOM переиспользован, модальность, safe-area, тач-таргеты | см. выше | ✅ |
| NFR-28: viewport без user-scalable/maximum-scale + viewport-fit=cover | base.html | ✅ `width=device-width, initial-scale=1, viewport-fit=cover` |

Вне спеки не уходил: права только в 3 файлах зоны + tasks.md; CSS-дифф чисто аддитивный
(+147, ни одного измененного desktop-правила — сверено построчно по диффу 76f4213^..76f4213).

## Второй круг — best practices

- **ОГР-8:** ванильный JS, без библиотек — ✅ (node --check OK).
- **Изоляция:** logout и drawer в одном IIFE, ранний return устранен — logout больше не блокирует
  остальной JS при отсутствии кнопки; слушатели на конкретных элементах, document-level только Esc — ✅.
- **Ошибки не глотаются:** `.catch` logout возвращает кнопку в active — сохранено — ✅.
- **Инъекции/секреты:** новых вводов/выводов нет; DOM-мутации только classList/aria — ✅.
- **Доступность:** aria-expanded/aria-controls/aria-label на бургере, фокус на первый пункт при
  открытии и возврат на бургер при закрытии (воспроизведено), role="presentation" на подложке — ✅.
- **prefers-reduced-motion:** `transition: none` на .sidebar (ОГР-17) — ✅ (в коде; поведение не
  эмулировалось в браузере — см. «Не проверено»).

## Третий круг — integration-точки (регресс)

| Набор | Результат |
|---|---|
| test_navigation_search_ui.py + test_p12_nav_icons_favicon_r8.py (9p по отчету дева) | ✅ 9 passed, 1 skipped (p12n004 — skip по дизайну автостенда), + 1 flaky-error favicon-теста при прогоне всем пакетом; изолированно — passed (артефакт route-cleanup сьюта, не диффа) |
| test_auth_ui.py + test_r3_vis_ui.py | ✅ 10 passed |
| test_qa21_netdata_sidebar_ui.py + test_p12_ui_polish_r8.py | 12 passed, 1 failed — `test_combobox_three_tags_and_one_by_one_removal` (TimeoutError); **пред-существующий**: воспроизведен ревьюером на чистом main a7208e9 в отдельном worktree — тот же TimeoutError. Не от диффа. |
| Мутационная (дословно, независимо) | `document.body.classList.add("sidebar-open")` → комментарий в openDrawer: `AssertionError: МУТАЦИЯ ПОЙМАНА: класс не поставлен: {'open': False, 'transform': 'matrix(1, 0, 0, 1, -292.5, 0)'}` + `MUTATED_EXIT=1`; восстановление (byte-identical, git diff quiet) → `TOGGLE-ASSERT GREEN: {"open": true, "transform": "none"}` |
| Tab-порядок 375px (доп. проверка ревьюера) | бургер → 6 пунктов → logout → профиль → контент: скрытый off-canvas сайдбар не ловит фокус-ловушку, порядок логичен |

## Соответствие мокапам 01/02 (сверка фактических скриншотов ревьюера, /tmp/review-1-1/)

- **01 закрыт:** темная шапка ink-900 с бургером, контент на всю ширину, сайдбар скрыт — совпадает.
- **02 открыт:** панель 292.5px (min(78vw,300px)) поверх затемнения rgba(61,54,48,.45), активный
  пункт терракотовый .active, footer-зона Мониторинг/Настройки/Выйти/профиль — совпадает.
  Отличие от мокапа: у мокапа 02 в шапке есть заголовок раздела — это осознанно НЕ в зоне 1.1
  (задача 1.2, комментарий в base.html) — не расхождение.
- **Desktop 1280:** прежний вид (sidebar sticky 200px, без мобильных элементов) — совпадает.

## Что НЕ проверено (честно)

- **design_validator-сверка** «pixel-consistent» — вне роли code_reviewer (волна 5.1в).
- **p12n004** (sidebar footer + длинная галерея на внешнем nginx-стенде) — skip по дизайну
  автостенда; эскалация дева ой :18443/:10443 остается у оркестратора.
- **prefers-reduced-motion** в живом браузере (только код-ревью правила ОГР-17).
- **Реальные touch-события** (эмуляция Playwright has_touch/is_mobile, не железо); приемка
  «вживую» — 5.2.
- **Безопасность на уровне middleware/auth** — не в зоне диффа (не менялся).
- Мутационная проверка прогнана только на toggle-пути openDrawer (ключевой ассерт задачи);
  close-пути прикрыты 40-ассертным прогоном выше.

## Границы

Запись только в этот файл. Код не правился (мутация — временная, восстановлена byte-identical,
git status чист). Стенд ревьюера (uvicorn :58063 + http.server :34269) погашен. Merge не
выполнялся. Provenance-запись (gate_runner record-review) — за ПМ.
