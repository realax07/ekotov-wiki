# Code Review: add-responsive-mobile — задача 2.2 [M], ПОВТОРНОЕ ревью после RETURN (fix major-1/2/3)

- **Ревьюер:** независимый code_reviewer-сабагент (не автор диффа)
- **Reviewer-Delegation:** deleg_8e784281
- **Дата:** 2026-10-08 UTC
- **Correlation:** 6a45c79b16c44f1f8c271ba72f692239
- **Ревьюемый коммит:** c7bbbd9764dbf09c82cb3ff2e74907343c3c2f84 (ветка feature/p14-2.2-ticket-modal, PR #122, НЕ мержен)
- **База сравнения с review-001:** 83a64eb0b7027cc95dc27d93addc644bee562744 — состояние ветки на момент review-001 (дифф 83a64eb..c7bbbd9 = ровно фикс-дельта major-1/2/3)
- **Reviewer-Delegation:** не ставится (повторное ревью по готовой истории review-001-2.2)

## Provenance

| Поле | Значение |
|---|---|
| Ревьюемый дифф | `git show c7bbbd9`: frontend/static/js/board/modal-shell.js (+15/−1: rect-проверка в initFocusScrollIntoView), frontend/static/js/board/task-form.js (+36/−2: import openTaskDetail; setViewReturnPending с matchMedia-guard; closeTaskForm сохраняет returnTaskId до сброса и перечитывает view) — итого **2 файла, +51/−3** |
| sha256 диффа `git diff 83a64eb c7bbbd9` | `195d1b51fc2a6331177db1c18722d8ea703456fdd1eef8603df29d5673b058aa` — ровно 2 файла, +51/−3; desktop-CSS (app.css, board.css) НЕ тронуты |
| sha256 frontend/static/js/board/modal-shell.js @c7bbbd9 | `00c9b72459e305a7527016b38db7ef761870630004fb3fed6d1f9b52c2d5f9e4` |
| sha256 frontend/static/js/board/task-form.js @c7bbbd9 | `2fae93438665c09f0937ed2be1288582d7efbdc82a42cd1e5b796c0ede198359` |
| Арбитры | openspec/changes/add-responsive-mobile/design.md §4, specs/board/spec.md (сценарий «Fullscreen-модалка на мобильном», ОВ-4), tasks.md 2.2, мокапы design/mobile-p14/04-ticket-modal-view.html, 05-ticket-modal-edit.html |
| Стенд ревьюера | worktree /tmp/rev22b/repo (c7bbbd9, detached; общий checkout /home/openclaw/ekotov-wiki НЕ переключался) — uvicorn app + uvicorn search (свободные порты, env DB_PATH+SECRET_KEY) + nginx :18445 по топологии REPORT-2.1 §1 (:18443 занят чужим стендом — не тронут); fresh tmp-БД, seed owner/wife + категории; Б-ветка; А-ветка — второй worktree /tmp/rev22a/repo @83a64eb, nginx :18446, отдельная fresh tmp-БД |
| ОтчетА/Б инструмент | собственный playwright-пробник ревьюера (не ассерты дева), chromium 375×812 touch/is_mobile + desktop 1280×1024 |

## Вердикт: **APPROVE**

Все 3 мажора review-001-2.2 устранены и независимо воспроизведены А/Б-методом
(А = 83a64eb, состояние на review-001; Б = c7bbbd9; одинаковые пробники, свежие БД):

1. **major-1 (комбобокс-дропдаун в edit-from-view)** — на А дропдаун после клика
   по «Теги» мертв в 10/10 проб (фокус-рендер открывает список, затем
   focusin→`scrollIntoView({block:"center"})` двигает форму, click доходит до
   document-обработчика «клик вне дропдауна» с target=#task-form → closeDropdown);
   на Б — открыт/виден/не накрыт/кликается **10/10**. Root cause почжен точно:
   rect-проверка «скроллить только когда поле вне вьюпорта».
2. **major-2 (повторное «Редактировать» мертво)** — на А после первого
   закрытия формы повторный клик по «Редактировать» не открывает форму
   (currentTaskId обнулен ПОСЛЕ restore; edit_dead 5/10 итераций, остальные
   циклы — та же смерть после каждого возврата); на Б — третий и последующие
   заходы живы, view после сабмита перечитан (fresh data, stale 0), повторное
   редактирование показывает сохраненное описание.
3. **major-3 (desktop Escape/«Отмена» уводили в view вместо доски, NFR-29)** —
   на Б desktop 1280: Escape (чистая форма) → доска, view скрыт; «Отмена»
   (грязная, confirm accept) → доска, view скрыт. matchMedia-guard ≤480px —
   корректная семантика (флаг бессмыслен >480px).

Regression: собственный дев-сьют задачи **6/6 passed**; board_assign **8/8**,
board_tasks **8/8**, r6_tag_combobox **12/12** — на одном и том же стенде Б.
Pre-existing фейл `test_combobox_three_tags_and_one_by_one_removal`
(TC-UIP-110, test_p12_ui_polish_r8) — вне скоупа 2.2 (см. ниже).

## А/Б-таблицы (одни и те же пробы ревьюера на А и Б)

### Major-1: комбобокс-дропдаун в edit-from-view, 375×812 (10 повторов)

| Проба (на каждом повторе) | А (83a64eb) | Б (c7bbbd9) |
|---|---|---|
| view → «Редактировать» → форма видна, view скрыт | ✅ первый цикл, далее форма мертва (edit_dead 5/10) | ✅ 10/10 |
| клик по #task-tags → фокус-рендер дропдауна (hidden=false) | ✅ открывается | ✅ открывается |
| итоговое состояние дропдауна: открыт+виден+не накрыт (elementFromPoint внутри popup) | ❌ **0/10** — закрыт document click-handler'ом: центр-скролл формы двигает input (y 535→342), click приходит с target=#task-form (не input) → closeDropdown | ✅ **10/10** (центр-скролла нет: rect-проверка видит поле во вьюпорте; click target=#task-tags) |
| клик по пункту списка проходит | ❌ 0/10 | ✅ 10/10 |
| scrollIntoView на focusin | безусловно `{block:"center"}` (трасса: `siv:task-tags {block:"center"}`) | только `siv:tag-opt-1 {block:"nearest"}` (докрутка активного пункта — безвредна) |

Механика на А подтверждена инструментированием (probe-диагностика ревьюера):
`SHOW via renderDropdown` → `focusin → scrollIntoView(center) → input уехал →
click вне input → closeDropdown` — ровно сценарий из комментария фикса.

### Major-2: повторное «Редактировать» + свежесть view после сабмита, 375×812

| Ассерт | А (83a64eb) | Б (c7bbbd9) |
|---|---|---|
| view → Редактировать → Escape (чистая) → view восстановлен | ✅ | ✅ |
| 2-й клик «Редактировать» из восстановленного view → форма | ❌ форма не открывается (guard currentTaskId===null; пробник упал на `expect(#task-form-overlay).to_be_visible`) | ✅ открывается |
| правка описания → «Сохранить» → view показывает СВЕЖИЕ данные | n/a (путь недостижим) | ✅ «обновленное описание R22» в view, stale-строки 0 |
| 3-й клик «Редактировать» → форма с сохраненными данными | ❌ | ✅ значение поля = сохраненное |
| Причина | closeTaskForm: restore ДО обнуления currentTaskId; перечитки нет | returnTaskId сохранен ДО сброса; openTaskDetail(returnTaskId) перечитывает и восстанавливает id |

### Major-3: desktop 1280×1024 — семантика закрытия формы (NFR-29)

| Ассерт | А (83a64eb) | Б (c7bbbd9) |
|---|---|---|
| Escape на чистой форме создания → форма скрыта | ✅ | ✅ |
| view-модалка ПОСЛЕ Escape | ❌ видима (флаг ставился безусловно) — desktop-баг review-001 | ✅ скрыта — на доске |
| «Отмена» на грязной форме (confirm accept) → view | ❌ видима | ✅ скрыта — на доске |
| Доска после закрытия | — | ✅ видима |

## Regression-пачка (стенд Б, одна команда на сьют, ≤60 c каждый)

| Набор | Результат |
|---|---|
| tests/web/test_p14_22_ticket_modal_fullscreen.py (свой сьют задачи, 6 тестов) | ✅ **6 passed** |
| tests/web/test_board_assign_ui.py | ✅ **8 passed** |
| tests/web/test_board_tasks_ui.py | ✅ **8 passed** |
| tests/web/test_r6_tag_combobox_ui.py | ✅ **12 passed** |
| test_p12_ui_polish_r8.py::test_combobox_three_tags_and_one_by_one_removal (TC-UIP-110) | ⚠️ фейл — по заявлению дева воспроизведен им на **чистом main (f361da3)**; ревьюером самостоятельный прогон этого теста не выполнялся (подтвержден только факт известного красного статуса в tests/web/.pytest_cache/lastfailed). Pre-existing вне скоупа 2.2 — не считается против 2.2 |

## Дифф-гигиена

- `git show --stat c7bbbd9` — ровно 2 файла: modal-shell.js (+15/−1), task-form.js
  (+36/−2) = **+51/−3**; других файлов нет.
- desktop-CSS НЕ тронут: app.css и board.css в c7bbbd9 отсутствуют вовсе
  (правки CSS — в 83a64eb, до review-001; фикc-дельта 83a64eb..c7bbbd9 —
  только JS). NFR-29 desktop-ветки не задеваются по построению.
- Новый импорт task-form.js → task-detail.js: цикла нет — task-detail.js
  импортирует task-form ТОЛЬКО динамически (loadEditFormModule, comment в
  диффе подтвержден кодом); статический граф form→detail→(dynamic)form
  безопасен.
- setViewReturnPending: `value=true` без media-матча теперь молча
  игнорируется — единственный вызывающий (task-detail.js «Редактировать»)
  на desktop получает прежнюю семантику «форма закрылась навсегда».
  `value=false` работает безусловно — сброс флага не потерян.
- Общий checkout /home/openclaw/ekotov-wiki не переключался (остался на
  feature/p14-2.2-ticket-modal @c7bbbd9); ревьюер работал в detached-worktree
  /tmp/rev22b (Б) и /tmp/rev22a (А).

## Соответствие арбитрам

| Арбитр | Сверка |
|---|---|
| design.md §4 (модалки, scrollIntoView) | фикс-комментарий в коде дословно описывает прежний дефект; поведение Б соответствует «фокус → scrollIntoView только при невидимости поля» |
| specs/board «Fullscreen-модалка» (ОВ-4) | возврат в просмотр при закрытии формы из view сохранен на мобильном (probe major-2: Escape → view восстановлен 10/10) |
| tasks.md 2.2 | все 3 замечания review-001 закрыты в зоне задачи, anti-scope (desktop-CSS) не нарушен |
| мокапы 04/05 | DOM/композиция не менялись (только JS-логика) — противоречий нет |

## Что НЕ проверено (честно)

- Реальное iOS/Android-железо: пробы — синтетический touch (is_mobile,
  375×812); поведение скролла «клавиатура перекрывает поле» на живом
  устройстве — приемка 5.2 (Заказчик).
- Полный web-регресс (~170 тестов) не гонялся — объем повторного ревью
  ограничен фикс-диффом + чек-лист ПМ (4 сьюта 34 passed + 1 pre-existing).
- r8_tag_ledger_leak и p14_41_lightbox_swipe смежные сьюты не прогонялись
  (task-form.js touch — только closeTaskForm-путь, дифф не трогает леджер;
  лайтбокс — вне зоны).
- Прогон дев-сьютов выполнен на Б-стенде ревьюера (:18445), не на стенде
  дева; числа совпадают с заявленными.
- Мутационные пробы (обратное внесение бага на Б) не проводились — А-ветка
  уже служит «негативным контролем» тех же проб.

## Границы

Ревьюер код не правил, push/merge не выполнял, коммитов в репо нет (зона
записи — только этот файл, untracked). Стенды погашены (uvicorn ×4, nginx
:18445/:18446 — порты свободны, проверено ss), worktrees /tmp/rev22b и
/tmp/rev22a удалены (git worktree list чист). Общий checkout остался на
feature/p14-2.2-ticket-modal @c7bbbd9 — не переключался.
