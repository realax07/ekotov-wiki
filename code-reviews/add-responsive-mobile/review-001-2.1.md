# Review 001 — задача 2.1 [M]: свайп-колонки доски ≤480px (PR #123)

- **Ревьюер:** code_reviewer (subagent, независимое ревью)
- **Reviewer-Delegation:** deleg_31fcd044
- **Correlation:** 7c1a2e5d94b34f60a8d3e21c5b709f14
- **Объект:** PR #123, ветка `pipeline/p14-21-review`, коммит `caab198`, дифф от `570b190` (5 файлов, +806: board.css +146, board-dots.js +243 (новый), board-init.js +33, cards.js +31, dev-смоук +353)
- **Спека-арбитр:** openspec/changes/add-responsive-mobile/{design.md §3, specs/board/spec.md MODIFIED «Канбан-доска на мобильном» (FR-62, NFR-26, FR-101), tasks.md 2.1}; мокап design/mobile-p14/03-board-swipe.html (утв.)
- **Стенд:** временный worktree /tmp/review-123-21 от caab198 (общий checkout не тронут)
- **Статус:** ЗАВЕРШЕНО (вердикт — §7)

---

## 1. Соответствие спеке (design §3, board spec MODIFIED)

Проверки по тексту диффа:

- [x] **Свайп-контейнер со snap**: `.board` @≤480px — `flex; flex-wrap: nowrap; overflow-x: auto; scroll-snap-type: x mandatory`; колонка `flex: 0 0 82vw; scroll-snap-align: start` — 82vw в коридоре 80–85vw design §3, зафиксировано по мокапу 03. ✔
- [x] **Страница без X-скролла (NFR-26)**: `.content, main { overflow-x: hidden }` в мобильной ветке; движение по X ограничено `.board`. Комментарий с санкцией ОВ-3 на уточнение FR-62 в CSS присутствует. ✔
- [x] **Dots follow + tap→колонка**: board-dots.js — scroll-listener (passive) + rAF-дедуп + таймер-хвост 120мс (fallback для отсутствия scrollend); активная точка = ближайшая колонка по snap-координатам; тап → `board.scrollTo({left: target, behavior: smooth|auto})`. `aria-current` синхронизируется. ✔
- [x] **reduced-motion (ОГР-17)**: tap-scroll `behavior:"auto"` при `prefers-reduced-motion` (JS) + `@media (prefers-reduced-motion: reduce)` в CSS: `scroll-behavior: auto`, transitions отключены. Функциональность (переход к колонке) сохраняется. ✔
- [x] **quick-done ≥44px**: кнопка `.task-quick-done` `min-height: 44px`, width 100%; точки 44×44 (визуально 8px ::before) — таб-паттерн по мокапу. ✔
- [x] **quick-done не открывает view-модалку**: `event.stopPropagation()` в click-обработчике кнопки до вызова card-handler (cards.js). ✔
- [x] **Тач-DnD НЕ реализован (anti-scope)**: в диффе нет touch-обработчиков DnD; `initCardDragAndDrop` не менялся. ✔
- [x] **Desktop ≥1024 без изменений (NFR-29)**: все CSS-правила внутри `@media (max-width:480px)` (кроме `.task-quick-done { display:none }` вне ветки — кнопка скрыта на desktop); dots строятся только при `matchMedia "(max-width:480px)"` и скрываются при выходе из ветки (hidden + CSS). ✔
- [x] **Degradation**: без scroll-snap поддержки — обычный h-скролл (design §3) — CSS не ломается, JS не завязан на snap. ✔

## 2. Гигиена (зоны, импорты, desktop-ветки)

- [x] **desktop-ветки CSS не тронуты**: весь дифф board.css — чисто аддитивный (+146 строк в конце файла: комментарий + `.task-quick-done{display:none}` вне media + один `@media (max-width:480px)` блок); существующие правила (в т.ч. прежняя 480px-ветка формы FR-62 выше по файлу) не изменялись. ✔
- [x] **JS-дельты в зоне board/**: cards.js (quick-done builder + setQuickDoneHandler), board-init.js (setQuickDoneHandler-инъекция + initBoardDots()), новый board-dots.js — все в `frontend/static/js/board/*`, зона tasks.md 2.1 соблюдена. Вне зоны: только тест. ✔
- [x] **Нет циклов импортов**: board-dots.js не имеет импортов вообще (self-contained, глобальный scope через export-функцию); cards.js импортирует dom/api/state/priority-icons/card-tooltip (как прежде); board-init.js → cards, board-dots, dom, modal-shell, task-detail. handler-инъекция setQuickDoneHandler повторяет паттерн setCardClickHandler (разрыв цикла cards ↔ task-form) — новых ребер циклов нет. ✔
- [x] **`node --check` синтаксис**: см. §4 (прогон E2E — JS исполнен браузером, ошибок консоли в пробах нет). ✔
- [x] **API-вызов quick-done**: тот же POST /api/tasks/{id}/move {status:"done"}, что и DnD/селект (ОГР-14); ошибка → #board-error + refreshBoard. ✔

Замечания (не блокирующие):

- **[minor] double-guard quick-done на desktop**: CSS `.task-quick-done { display:none }` вне media гарантирует desktop-невидимость даже если DOM-кнопка есть — плюс условие построения в cards.js; двойная защита, ок.
- **[minor] board-init.js: новый `import { showBoardError, hideError } from "./dom.js"`** — dom.js уже в графах импортов cards.js, нового ребра между модулями верхнего уровня не появляется.

## 3. Regression на собственном стенде ревьюера

Стенд: worktree /tmp/review-123-21 @ caab198 (общий checkout НЕ переключался);
app uvicorn 127.0.0.1:18080 + search uvicorn 127.0.0.1:18378 (fresh tmp-БД /tmp/rev21/app.db,
seed owner/wife + категории) + http.server :18801 (статика) + nginx :18443 по топологии
REPORT-2.1 §1 (search-семейство, /static/ → статика; конфиг /tmp/rev21/nginx-qa.conf).
Base URL стенда: http://127.0.0.1:18443; playwright headless chromium 375×812 touch/is_mobile.
Secure-кука: тесты сбрасывают secure=False после login (паттерн LocalhostSession) — подтверждено.

### 3.1 Dev-смоук задачи (реальный touch через CDP Input.dispatchTouchEvent)

`tests/web/dev_smoke_p14_21_board_swipe.py` — **4 passed** (11.75s), повторные прогоны
**4 passed** (11.04s), **4 passed** (10.92s) — стабилен 3/3 прогонов. Покрывает:
snap-styles (overflow-x auto, snap mandatory, 82vw±2 на 375px), NFR-26 (page scrollWidth ≤
innerWidth), dots 3шт + aria-current follow, свайп реальным touch → snap-оседание ±2px,
tap по точке → scroll к колонке, quick-done ≥44px + tap → переезд в done (API-проверка),
reduced-motion (scroll-behavior auto, прыжок <200ms), desktop 1280 (overflowX visible,
dots hidden, quick-done невидим, колонки равные).

### 3.2 Смежные семейства (тот же стенд, чистая tmp-БД)

| Набор | Результат |
|---|---|
| test_p14_22_ticket_modal_fullscreen.py + test_board_tasks_ui.py + test_board_assign_ui.py | ✅ **21 passed** (59.2s) |
| dev_smoke + те же три семейства одной командой (чистая БД) | ✅ **25 passed ×3** (68.2/68.8/68.8s) — детерминированно |
| Примечание | на замусоренной БД (30+ задач → колонка >10000px высотой) dev-смоук падал по свайпу; после чистки БД — стабильно green; к диффу отношения не имеет (высота колонки вне вьюпорта — ограничение тестовых данных, см. «Что НЕ проверено») |

## 4. Мутационная проверка

| Мутация | Результат |
|---|---|
| 1. `scroll-snap-type: x mandatory` → `none` в board.css | ✅ **1 failed** (test_board_swipe_snap_and_dots_follow — snap-ассерт красный); восстановление → **byte-identical** (sha256 board.css `7cd92adb…` = caab198), `git diff --quiet` |
| 2. Вызов `initBoardDots()` удален из board-init.js | ✅ **2 failed** (dots follow + reduced-motion) — ассерты красные; восстановление → **byte-identical** (board-init `758c5a50…`), дерево чистое |
| 3. `event.stopPropagation()` удален из quick-done (cards.js) | ✅ **независимый пробник ревьюера**: без stopPropagation тап по «Выполнено» открывает view-модалку (`#task-detail-overlay` = **VISIBLE**), с оригиналом — `hidden`; на мутации ассерты дева «модалка не открыта» были бы красные (в смоуке прямой ассерт на модалку отсутствует — зафиксировано как minor, см. ниже); восстановление → **byte-identical** (cards.js `c0e60a42…`), `node --check` всех трех JS — OK |

Финальный прогон после всех мутаций: 25/25 ×3 — следов мутаций нет.

## 5. Разбор dnd-флейка (test_r3_dnd_ui): **flaky-фон, НЕ регресс диффа**

Факт: `test_dnd_success_after_409_hides_board_error` флейчит на стенде и **изолированно**,
и **в связке** (dnd+board_tasks+board_assign), на **caab198 И на родителе 570b190** (без
диффа 2.1). Замеры:

| Серия | caab198 | 570b190 (без диффа) |
|---|---|---|
| изолированно, N прогонов | ~5 фейлов на 45 (≈11%) | 1 фейл на 10 |
| в связке (dnd+tasks+assign) | 4 фейла на 11 прогонов | — |

Отказ один и тот же: `dnd_helpers.py:57` (`dnd_start` → `card.evaluate("el =>
el.closest('.board-column').dataset.status")`) — `TypeError: Cannot read properties of
null (reading 'dataset')`. Root cause, воспроизведен пробником ревьюера
(/tmp/rev21/probe5.py, **11 попаданий на 30 итераций**): тест в окне между
`card.get_attribute("data-task-id")` и `card.evaluate(...)` держит ссылку на DOM-элемент,
который отрывается асинхронным `refreshBoard()` (renderBoard чистит `[data-cards]` через
`textContent = ""`), приходящим от предыдущего действия (409-перевод шага 1 / создание
«очистки» через UI-форму). Playwright Locator резолвится заново, но между двумя
последовательными evaluate перерисовка успевает оторвать элемент → `closest()` на detached
узле → null. Это **гонка тестовой механики** (два чтения DOM без общей транзакции), не
продуктовый дефект: между get_attribute и closest элемент может легально перерисоваться.

Дифф 2.1 в цепочке не участвует: cards.js-дельта (quick-done builder) не добавляет
перерисовок (renderBoard не менялся); board-dots.js слушает только scroll и не
перерисовывает карточки; на родителе 570b190 фейл воспроизводится тем же трейсбеком.
Продукт-код корректен: перерисовка из серверного источника правды — штатное поведение.

**Вердикт по флейку: flaky-фон (тестовая гонка dnd_helpers + async refreshBoard),
существует до диффа; регрессом PR #123 не является.** Рекомендация (вне скоупа этого
ревью, отдельной задачей в тест-инфраструктуру): в `dnd_start` читать taskId и
from_status одним `evaluate` (атомарно), либо re-resolve карточку после
`expect(...to_be_visible())` с ожиданием стабильности DOM (два кадра).

## 6. Что НЕ проверено (честно)

- **Реальное железо**: свайпы — реальный touch-инпут через CDP
  `Input.dispatchTouchEvent` (не синтетические TouchEvent) в headless chromium
  375×812 is_mobile; приемка «вживую» — 5.2 (Заказчик).
- **iOS Safari**: scrollend/overscroll-поведение и инерция — только chromium;
  board-dots.js дублирует финальную синхронизацию таймер-хвостом 120мс именно для
  отсутствующего scrollend (старый WebKit) — по коду корректно.
- **Свайп на колонке с очень длинным списком** (колонка выше вьюпорта): на
  замусоренной БД свайп, начатый на карточке, не листал контейнер в headless
  (touch-цель выше вьюпорта). На данных нормального размера (1–3 задачи) свайп
  по карточке листает колонки (scrollLeft 0→316 — пробник ревьюера). Потенциальный
  UX-кейс «палец на карточке длинного столбца» фиксирую наблюдением, продукт-бага
  в рамках спеки (375×812, сценарии спеки) не усматриваю.
- **Прямого ассерта «view-модалка НЕ открылась» в dev-смоуке нет** — поведение
  stopPropagation проверено моим пробником (см. мутацию 3). [minor] деву стоит
  добавить такой ассерт в смоук.

## Вердикт: **APPROVE**

**APPROVE**

Спецификация (design §3, board spec MODIFIED, tasks.md 2.1, мокап 03) выполнена
полностью: свайп-колонки со scroll-snap (82vw), страница без X-скролла (NFR-26),
dots follow + tap→колонка с reduced-motion (ОГР-17), quick-done ≥44px с тача без
открытия view-модалки, тач-DnD не реализован (anti-scope), desktop ≥1024 без
изменений (NFR-29). Гигиена: дифф чисто аддитивный, зоны соблюдены, циклов
импортов нет, `node --check` OK. Regression: 25/25 смежных тестов ×3, dev-смоук
4/4 ×3+ (на чистой БД), мутационная — ассерты живые, восстановления byte-identical.
Dnd-флейк — тестовая гонка до диффа, продуктом не вызван.

Minor (не блокируют, деву — по желанию в следующих задачах волны):
1. Добавить в dev-смоук ассерт «тап по quick-done НЕ открывает view-модалку».
2. [инфра, вне 2.1] Починить гонку в dnd_helpers (атомарное чтение taskId+from_status).

---

## Provenance (реверифицируемо)

| Артефакт | Значение |
|---|---|
| Коммит | caab198f81a1175e3df8f5410694a52c84d7dc36 (дифф 570b190..caab198: 5 файлов +806) |
| sha256 диффа (git diff 570b190 caab198) | `d07fca87e6c92a12a558ebecfc40f9aaef0cb1a38f77d64f47925ade276830b1` |
| sha256 board.css | `7cd92adba9c91c23f29a091ec769b2241806b1e0adef5df5682a2e27665d10ef` |
| sha256 board-dots.js | `e44ab0c1d9e44197f120a2df48febb597250a6365c7d8402da245d8d37a46723` |
| sha256 cards.js | `c0e60a429d0bf291750b3029731f907cc0ac25c0a8fb66ccb16234ab42ac5205` |
| sha256 board-init.js | `758c5a503828a403455224e7071eaaaf87ab57d2662870b8aa71eb370ce77b90` |
| sha256 dev_smoke_p14_21 | `53c725c485ad2e3798a340647c2cb40074ba41952663d7e7aa5135c8587d9326` |
| Арбитры | openspec/changes/add-responsive-mobile/design.md §3, specs/board/spec.md MODIFIED «Канбан-доска на мобильном» (FR-62, FR-101, NFR-26, NFR-23), tasks.md 2.1, мокап design/mobile-p14/03-board-swipe.html (утв.) |
| Стенд ревьюера | worktree /tmp/review-123-21 @ caab198 (общий checkout НЕ переключался); uvicorn app :18080 + uvicorn search :18378 (fresh tmp-БД /tmp/rev21/app.db, seed owner/wife + категории) + http.server :18801 (статика) + nginx :18443 по топологии REPORT-2.1 §1; chromium 375×812 touch/is_mobile + 1280×800 |
| Флейк-диагностика | /tmp/rev21/probe5.py (гонка 11/30), базовые прогоны на worktree /tmp/review-123-base @ 570b190 |

