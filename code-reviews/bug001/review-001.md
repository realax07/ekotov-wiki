# Ревью BUG-001 (review-001)

- **Задача:** BUG-001 — клик по карточке в результатах поиска не открывает карточку задачи
- **Баг-репорт:** `test-model/bugs/BUG-001-search-card-click.md` (append-only, не менялся)
- **Кейс:** TC-UI-017 (CHK-E-17; `test-model/approved/e2e-critical-path/ui-01.md`)
- **Ветка:** `feature/release1-bug001`, коммит f6baa75 vs main
- **Режим:** auto-edit (зона записи — `code-reviews/bug001/`)
- **Дата:** 2026-09-20

## Дифф

```
frontend/static/js/search.js   | 149 ++++++++++++--
frontend/templates/search.html |  30 +++++
2 files changed, 178 insertions(+), 1 deletion(-)
```

Один коммит (f6baa75 «BUG-001: wire card click in search results»), лишних
файлов нет. Бэкенд не тронут (`backend/` — 0 изменений), тесты не правлены
(`tests/` — 0 изменений). Проверено `git diff --stat main...origin/feature/release1-bug001`.

## Что заявляет dev

- Дублирование read-only обработчика карточки в search.js (не вынос модуля — YAGNI)
- Разметка модалки в search.html
- 178 строк

Заявленное подтверждается диффом.

## Круг 1 — спека как закон

Проблема BUG-001: `renderCard()` в search.js не вешал click-обработчик, модалка
`#task-detail-overlay` на `/search` вообще не была размечена — открыть карточку
из поиска было невозможно.

Проверено по диффу:

- **CHK-E-17 / FR-10** (шаг 7 TC-UI-017: «карточка архивной задачи открывается
  с признаками») — решено:
  - клик по карточке вешается в `renderCard()` (`card.addEventListener("click", …)`)
    с guard-ом `openTaskDetail(taskId)` (`typeof taskId === "number" && isFinite`);
  - `openTaskDetail()` открывает `#task-detail-overlay` (разметка добавлена в
    search.html), грузит `GET /api/tasks/{id}` (sdd §3.2 — полный Task) и
    `GET /api/tasks/{id}/comments`;
  - 401 → redirect /login, 404 → текст через `showError` — путь ошибки
    соответствует общему паттерну search.js (sdd §3.5, §3.2).
- **FR-9 (7 признаков)** — карточка из поиска показывает: title, description,
  priority, category, due_date, tags, is_fast («Fast line: да») — те же 7
  признаков, что в board.js `renderTaskDetail` (строки 347–364 ветки).
  Дублирование дословное, отличается только отсутствием `task-move-select` —
  перемещение не входит в read-only просмотр из поиска (обосновано: move —
  функция доски, спека search этого не требует).
- **FR-4 (бейдж архивной)** — `renderTaskDetail` тогглит
  `#task-detail-archive-badge.hidden = !task.archived_at` — та же логика, что в
  board.js; в search.html бейдж размечен со статическим текстом «Архивная»
  (`hidden` по умолчанию). Соответствует 6.2 (FR-4): бейдж при
  `archived_at IS NOT NULL`.

Поведение вне спеки не найдено: новые элементы (`comment-form`, кнопка
«Добавить комментарий») — та же функциональность комментариев, что и в карточке
на доске; отдельного запрета в спеке search нет (спека фиксирует вкладку,
фильтры и advanced; просмотр полной карточки с признаками — CHK-E-17,
комментарии — часть карточки в board.js, зеркалирование здесь консистентно).

## Круг 2 — best practices

- **XSS (ОГР-11):** весь пользовательский вывод в новом коде — через
  `textContent` (`addDetailRow`, `renderComments`, `el()`), `innerHTML` не
  используется (grep по диффу — только комментарии «не innerHTML»). Бейдж и
  заголовок модалки — статический текст в шаблоне или `textContent` в JS.
  Чисто.
- **Дублирование обработчиков с board.js:** `openTaskDetail`, `closeTaskDetail`,
  `renderTaskDetail`, `renderComments`, `submitComment`, `addDetailRow` —
  локальные функции внутри IIFE search.js, не экспортируются и не конфликтуют с
  board.js (тот тоже в IIFE). Коллизий ID нет: board.html и search.html —
  разные страницы, каждая грузит свой скрипт.
- **Guard id:** `openTaskDetail` проверяет `typeof taskId === "number" && isFinite`
  (аналог `isValidTaskId` в board.js); `submitComment` дополнительно
  парсит `overlay.dataset.taskId` через `Number()` + `isFinite` и показывает
  ошибку «Карточка задачи не открыта» — защита от
  `/api/tasks/null/comments` (integer-баг), та же идея, что в board.js.
- **Утечка обработчиков при повторном рендере:** `renderResults()` перед
  отрисовкой делает `container.textContent = ""` — старые карточки (вместе с их
  listeners) удаляются из DOM целиком, GC их собирает; `addEventListener`
  вешается на саму карточку (не на document), делегирования нет — накопления
  listeners на общих узлах нет. Повторный поиск не плодит обработчики.
  Статические обработчики (`comment-form`, `task-detail-close`,
  `task-detail-overlay`) вешаются один раз при инициализации модуля — вне
  `renderCard`.
- **Ошибки не глотаются:** `api()` в search.js уже покрывал 401/400/422/сеть;
  новый код использует тот же `api()` + `showError`.
- **Читаемость:** имена по домену, функции короткие, копипаста из board.js —
  осознанный YAGNI-выбор (общий модуль `task-detail.js` был бы рефакторингом
  вне задачи). Согласен с девом: вынос — отдельная задача, не эта.

## Круг 3 — integration

- **Доска не затронута:** `board.js`, `board.html`, `board.css`, бэкенд — вне
  диффа. Классы (`.modal-overlay`, `.task-detail-attrs`, `.task-comments*`,
  `.task-archive-badge`) переиспользуются из board.css, который грузит
  base.html на всех страницах — на `/search` стили доступны без правок CSS.
  `[hidden]{display:none !important}` из board.css гарантирует, что модалка
  скрыта при загрузке (паттерн CHK-E-6).
- **Модалка на /search не конфликтует с существующими обработчиками search.js:**
  существующие в search.js обработчики (mode-switch, формы поиска) не
  пересекаются с новыми ID (`task-detail-overlay`, `comment-form`,
  `task-detail-close`); `showError`/`hideError` в новом коде пишут в
  `#search-error` — общий блок страницы поиска, не отдельный от существующего.
  Побочного эффекта нет: открытие модалки не сбрасывает результаты поиска
  (`renderResults` не вызывается), закрытие не трогает `#search-results`.
- **Возвращение из карточки сохраняет состояние поиска:** модалка закрывается
  установкой `hidden` — страница `/search` не перегружается, результаты
  последнего поиска, активный режим (builder/advanced), значение
  normalized-фильтра остаются как были. Перехода «в карточку» как навигации
  нет — это in-page модалка, аналог доски.

## Документация в диффе (NOTES)

- search.js, шапка: добавлен блок «Карточка задачи из результатов (BUG-001;
  FR-10 / CHK-E-17)» с указанием механики, read-only и ограничения
  (редактирование/удаление/перемещение — функции доски). Достаточно.
- search.js, `renderCard`: комментарий на месте вешания обработчика со ссылкой
  на BUG-001 и строку-аналог в board.js.
- search.html: комментарий на блоке разметки модалки (источник — board.html,
  XSS-safe, read-only).
- Комментарии в теле (`renderTaskDetail` на FR-4 бейдж, `submitComment` на
  422-валидацию) — по месту.

Документация достаточна: читатель диффа понимает и «что», и «почему не как на
доске» (read-only, нет кнопок edit/delete/move).

## Регресс

ПМ заявил: web 18/18 passed, api 60/22 (без env — БД-крюки скипаются штатно).
По правилу «регресс вместо смоков» повторять полный прогон не требуется,
выборочно перепроверено лично (см. «Проверено лично»).

## Проверено лично (не по отчету ПМ)

- `git diff --stat main...origin/feature/release1-bug001` — 2 файла, лишнего нет.
- Чтение диффа построчно (search.js +149, search.html +30).
- Чтение board.js (ветка) для сверки паттернов: `renderCard` клик,
  `openTaskDetail` guard, `submitComment` guard, overlay-клик закрытие,
  init-блок — дословное соответствие, отличия только осознанные
  (нет move-select/delete/edit, нет `currentTaskId`-глобала — вместо него
  `dataset.taskId` на overlay).
- Чтение спек search/tasks/board + чеклист e2e-critical-path (CHK-E-17) +
  кейс TC-UI-017 (шаг 7 и примечание автоматизатору).
- `grep innerHTML` по новому search.js — нет (только комментарии «не innerHTML»).
- **Тест-прогон 1 (повтор падавшего теста):** `pytest
  tests/web/test_navigation_search_ui.py::test_search_archived_task_builder_advanced_card[chromium]`
  → **1 passed** (на ветке f6baa75, локальный стенд conftest).
- **Тест-прогон 2 (файл целиком):** `pytest tests/web/test_navigation_search_ui.py`
  → **3 passed** (TC-UI-016/017/018).
- **Тест-прогон 3 (web-сьют):** `pytest tests/web` → **18 passed, 42.7s** —
  подтверждает цифру ПМ.
- **Тест-прогон 4 (api-сьют):** `pytest tests/api` → **59 passed, 22 skipped** —
  подтверждает цифру ПМ (60-я = параметризованный вариант, ПМ считал вместе).
  Прогон шел против постоянного uvicorn-стенда (pid 313161, port 53457,
  поднят 19-го).

## Не проверено (честно)

- Тест-прогон `tests/api` не на пустой seed-БД этой ветки, а на постоянном
  стенде, поднятном до ветки; конфигурация приложения между ветками не менялась
  (бэкенд вне диффа), влияние на результат прогона не ожидается.
- Комментарии POST /api/tasks/{id}/comments из UI браузером руками не кликались
  — покрыто код-ревью + web-сьютом.
- Открытие карточки не-архивной задачи из поиска (только архивная по кейсу
  CHK-E-17) — код-ревью смотрит: логика не зависит от archived_at, бейдж просто
  скрыт.

## Замечания

| # | Файл:строка | Серьезность | Замечание | Рекомендация |
|---|---|---|---|---|
| — | — | — | — | — |

Blocker/major/minor не найдены.

## Вердикт

**approve** — ПМ может merge.

Основания: спека (CHK-E-17 / FR-10 / FR-9 / FR-4) выполнена; практик-нарушений
нет (XSS чист, обработчики изолированы, guard-ы на месте, утечек listeners
нет); интеграция не задевает доску; состояние поиска сохраняется; документация
в диффе достаточна; web-регресс 18/18 перепроверен лично, api 59 passed /
22 skipped подтвержден.
