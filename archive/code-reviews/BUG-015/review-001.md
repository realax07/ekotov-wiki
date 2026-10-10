# Ревью 001 (код-ревью Флоу 2): BUG-015 — старый dl#task-detail-attrs скрыт (sr-only), attr-grid — единственный видимый носитель признаков

- **Reviewer-Delegation:** внешняя (correlation f694efca7b0d4a8c8decade29f6d68d9, code_review; независимое ревью, сессия dev finished)
- **Ревьюируемый фикс:** PR #91, HEAD `0096ed4` (`fix/bug-015-hide-legacy-attrs`, поверх origin/main `774b7c1`); дельта `git diff origin/main...0096ed4` = 2 файла: `frontend/static/css/board.css` (+19/−1), `tests/web/test_bug013_attrs_padding.py` (+29/−0). PR ОТКРЫТ, НЕ смержен (по постановке)
- **Provenance SHA:** `0096ed423a81ee2e7514d31a825f6693f33b6d43` (worktree /home/openclaw/ekotov-wiki @ 0096ed4, `git status` чист до и после мутаций; проверено до и после мутационной пробы); sha256 файлов диффа: board.css `95765b6a929709c8db56fa4a23532e7a8da2da6295605e097e890a094fbaa509`, test_bug013_attrs_padding.py `f89d00d4ee300cbae27f4c09ab245a1438bdb608c3cc8bf11df2eabdf5999c05`
- **Карточка:** `test-model/bugs/BUG-015-old-attrs-dl-visible.md`; отчет фикс-цикла `/home/openclaw/.hermes/state/reports/bug015-fixcycle-1.md`; мокап-арбитр `design/polish-ticket-modal.html`
- **Зона ревьюера:** только `code-reviews/BUG-015/review-001.md`; все прогоны — `env -u DB_PATH -u EKOTOV_WIKI_BASE_URL -u PYTHONPATH`, venv /home/openclaw/venvs/wiki; дерево репо не изменено (мутация CSS применена и возвращена `git checkout --`, остаточного диффа нет)
- **Дата:** 2026-10-08
- **Метод:** (1) чтение отчета цикла, карточки, мокапа; (2) разбор диффа (2 файла, построчно); (3) независимая проверка ключевого риска (TC-UI-009 vs sr-only) — чтение ассерта + прогон + собственный Playwright-пробник с репликой предиката видимости Playwright; (4) визуальная негативная проба в реальном браузере (скриншот + bounding box); (5) верификация на автостенде по матрице ТЗ; (6) мутационная проверка дословно

---

## Вердикт: **APPROVE**

Оба вопроса ТЗ с пометкой «проверь/разберись» разрешены в пользу фикса: противоречия нет — sr-only сохраняет видимость по определению Playwright, и тест это подтверждает прогоном, а не обходом. Дискриминативность ассертов доказана мутацией (красный на `position == "absolute"` при снятии sr-only).

## Проверка 1 (ключевой риск ТЗ-а): expect(attrs).to_be_visible() при sr-only — почему проходит

**Разобрано, противоречия нет.**

Ассерт TC-UI-009 (tests/web/test_board_tasks_ui.py:150): `attrs = board_page.locator("#task-detail-attrs"); expect(attrs).to_be_visible()` плюс `expect(attrs.get_by_text(value, exact=True)).to_be_visible()` по всем 5 значениям.

Предикат видимости Playwright (Locator Assertions, to_be_visible): элемент считается видимым при **непустом bounding box** И `visibility` не `hidden` (документация Playwright: "Element is considered visible when it has non-empty bounding box and does not have visibility:hidden computed style"; вырожденные случаи — zero-size или `display:none` — не visible; при этом элемент с ненулевым box, обрезанный родителем/`clip` за пределы себя, **остается visible** — Playwright не проверяет, попадает ли box в viewport или в отрисовываемую область).

sr-only-паттерн фикса (`position:absolute; width/height:1px; margin:-1px; overflow:hidden; clip:rect(0 0 0 0)`) дает dl bounding box 1×1px с `visibility: visible; display: block` — предикат выполнен: **элемент «visible» для Playwright, хотя визуально на экране не отображается** (1px-бокс, полностью обрезанный clip'ом, ничего не рисует). Проверено самостоятельно (проверка 3): собственный пробник на живом стенде дал `playwrightVisibleReplica = true` (реплика предиката: `!!(r.width && r.height) && visibility !== "hidden" && display !== "none"`) при фактической отрисовке нулевой площади.

Следствия:
- **TC-UI-009 green без правки теста — корректно, а не случайность.** Тест при sr-only проверяет контракт ДАННЫХ (текст attrs в DOM, значения читаемы), а не визуальную презентацию — и именно это его назначение (комментарий в тесте: «attrs показывает сырые значения задачи — контракт утвержденного e2e»). Требование «без правки теста» из карточки выполнено честно.
- **Пограничность осознана:** `to_be_visible` на sr-only-элементе — слабый визуальный ассерт (он теперь «passes forever» для этого элемента). Но это допустимо: визуальную сторону взял на себя расширенный TC-view-110 (box ≤ 1×1, clip), и семантика двух тестов разнесена — TC-UI-009 = данные, TC-view-110 = презентация. Замечание фиксирую как наблюдение (не блокер): будущему ревьюеру TC-UI-009 не следует читать его ассерт видимости как «пользователь видит dl».
- Прогон: TC-UI-009 изолированно **1 passed** (см. проверку 5) — на ветке с фиксом, без правки теста.

## Проверка 2 (ТЗ-б): один фикс покрывает оба окна

Да, подтверждено независимо:
- класс `.task-view-attrs` встречается ровно в двух шаблонах: `frontend/templates/board.html:260` и `frontend/templates/search.html:154` (grep по frontend/ — других вхождений в HTML/JS нет; оба — `<dl id="task-detail-attrs" class="task-view-attrs">`, ОГР-28 id сохранен);
- board.css подключается в `frontend/templates/base.html:24` — общий для доски и поиска (search.html собственных CSS-подключений к task-view не имеет);
- живая проба из окна поиска (проверка 3б): box 0.98×0.99px, `position: absolute`, содержимое в DOM — паттерн действует во втором окне.

## Проверка 3: негативная проба ревьюера (живой браузер, реальный рендер)

Стенд поднят по топологии tests/web/conftest.py (uvicorn app :N + uvicorn search :N + http.server static :N + Playwright-маршрутизация «роль nginx» — точные команды conftest, временная seed-БД). Задача со всеми признаками заведена через API (те же значения, что TC-UI-009). Пробник: /tmp/bug015-probe/pw_probe.py (сценарий удален из репо-зоны, артефакты — в /tmp).

**3а. Окно доски** (клик карточки «Полная» → view-модалка):
- `#task-detail-attrs`: computed `display: block; visibility: visible; position: absolute; clip: rect(0px, 0px, 0px, 0px); overflow: hidden`; bounding box **1×1px** (x=321, y=500);
- все 16 дочерних dt/dd: ширина ровно 1px (0.99–1px в разных прогонах, погрешность округления) — **на экране не отрисовывается ничего**; содержимое DOM сохранено: 16 рядов, `textContent.length = 132`, сэмпл «ОписаниеПроверка признаков e2eПриоритетhighКатегорияДомСрок2026-09-30СтатусОжидаетТеги…» — контракт TC-UI-009/ОГР-28 (ровно значения задачи) соблюден;
- `.attr-grid`: ВИДИМ (`gridVisible: true`), box 572×99px — единственный видимый носитель признаков;
- скриншот модалки (board-view-modal.png) просмотрен ревьюером: признаков старого dl на экране нет — Описание/Признаки(attr-grid)/Теги/Люди/Комментарии, по мокапу; дубликата, прижатого к краю, нет.

**3б. Окно поиска:** advanced → `priority = "high"` → «Найти» → клик карточки: box 0.98×0.99px, `position: absolute`. Паттерн работает во втором окне (плюс 5 passed сьюта BUG-014/navigation, проверка 5).

## Проверка 4: доступность (ТЗ-в) — паттерн корректен

- Паттерн дословно совпадает с существующим `.visually-hidden` (board.css, aria-live-узел NFR-18) — консистентность внутри кодовой базы;
- **НЕ display:none / hidden-атрибут:** computed `display: block; visibility: visible` подтверждены и ассертом TC-view-110 (`display != "none"`), и пробником — содержимое остается в accessibility tree, скринридер озвучивает признаки, гет-тексты Playwright читают;
- это стандартный HTML5 Boilerplate/W3C visually-hidden паттерн (clip:rect(0 0 0 0) + 1px-box): скрытие чисто визуальное, доступность не нарушена;
- `white-space: nowrap; border: 0; padding: 0; margin: -1px` — гигиенические детали паттерна на месте (nowrap исключает перенос 1px-ширины, margin компенсирует ghost-отступ).

## Проверка 5: верификация на автостенде (env -u DB_PATH -u EKOTOV_WIKI_BASE_URL -u PYTHONPATH, venv wiki)

| Сьют | Результат ревьюера | Отчет цикла |
|---|---|---|
| TC-view-110 (tests/web/test_bug013_attrs_padding.py) | **1 passed** | 1 passed ✔ |
| TC-UI-009 (test_board_tasks_ui.py::test_all_attributes_create_view_edit) изолированно | **1 passed** | 1 passed ✔ |
| view_modal (test_view_modal_r4.py) | **9 passed** | 9 passed ✔ |
| board_tasks (test_board_tasks_ui.py) | **8 passed** | 8 passed ✔ |
| поиск (test_bug014_search_task_view.py + test_navigation_search_ui.py) | **5 passed** | 5 passed ✔ |

Все дроби воспроизведены ревьюером независимо. Данные цифры в отчете цикла соответствуют действительности.

## Проверка 6 (ТЗ-г): мутационная проверка — дискриминирует, дословно

- **Мутация:** блок sr-only `.task-view-attrs { position:absolute; … border:0; }` заменен на исходный `.task-view-attrs { margin: 10px 0; }` (dl снова видимый статическим блоком). Git diff зафиксирован (1 insertion, 11 deletions).
- **Результат:** TC-view-110 **FAILED** — `AssertionError: {'position': 'static', 'width': 635, 'height': 398.1, 'clip': 'auto', …}` на ассерте `bug015["position"] == "absolute"` (test_bug013_attrs_padding.py:104, `test_view_attrs_padding_matches_mockup[chromium]`). Первым срабатывает позиционный ассерт; за ним в цепочке стоят box ≤ 1×1 и clip — ассерты сработали бы и по отдельности (измерения мутанта: width 635px, clip auto). Красный подтвержден: **тест дискриминирует дефект BUG-015**.
- **Возврат:** `git checkout -- frontend/static/css/board.css` → дерево чистое (`git status --short` пуст), HEAD остался `0096ed4` → повторный прогон TC-view-110 **1 passed**. sha256 board.css после возврата — исходный (в шапке ревью).
- Отчет цикла называет тот же ассерт первым красным — совпадает с независимым воспроизведением.

## Проверка 7: границы зоны (ТЗ-г) — соблюдены

`git diff --name-only origin/main...0096ed4` — ровно 2 файла: `frontend/static/css/board.css`, `tests/web/test_bug013_attrs_padding.py`. task-detail.js (контрактный рендер) не тронут; TC-UI-009 не правлен; шаблоны не тронуты; ничего вне заявленной зоны. Карточка BUG-015 в ветку вошла через приемочный коммит b3f33b6 (сторона main), в диффе PR отсутствует — корректно.

Отчет цикла точен, включая честную фиксацию вынужденного rebase (a8dff23 → 774b7c1) и force-with-lease пуша собственной ветки — отклонение задокументировано автором, риск нулевой.

## Замечания (не блокеры)

1. **Наблюдение (документирующее):** после фикса `expect(attrs).to_be_visible()` в TC-UI-009 навсегда green при любом состоянии экрана — предикат Playwright не различает sr-only и видимый элемент. Семантика ассерта — «данные в DOM», что соответствует цели теста; визуальную сторону держит TC-view-110. Если однажды контракт ОГР-28 переведут на attr-grid (зачистка носителя), править оба теста согласованно.
2. **Микро:** в новом ассерте TC-view-110 `gridVisible` вычисляется через `offsetWidth || offsetHeight` — корректно для данного случая; толерантность `width <= 1` пропускает субпиксельные вариации (0.98–1.0 в прогонах) — норма для device pixel ratio, не дефект.

## Итог

Фикс минимальный, корректный, в зоне; контракт TC-UI-009/ОГР-28 сохранен; оба окна покрыты одним CSS-изменением; доступность соблюдена (sr-only, не display:none); тесты дискриминативны (мутация красная дословно воспроизведена); автостендовая матрица зеленая независимо. **APPROVE** — к мержу (мерж не выполнялся, по постановке).
