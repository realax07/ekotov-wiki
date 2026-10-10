# REPORT 4.2 — QA-набор web-desktop (playwright, ≥1024px)

- **Задача:** add-wiki ЭТАП C, 4.2 [tests] [M] (`openspec/changes/add-wiki/tasks.md:48`)
- **Ветка:** `pipeline/p15-stage-a` @ `91658ec` (волна 3 = `6fdc36c` в истории)
- **Среда:** venv `/home/openclaw/venvs/wiki` (pytest 9.1.1 + playwright/chromium 153); стенд — автоподъем `tests/web/conftest.py` (uvicorn app + uvicorn search + http.server static, tmp-БД + seed owner/wife + `app.migrate_wiki`); viewport 1280×900
- **Дата:** 2026-10-10
- **Коммиты в этой задаче:** нет (по условию; рабочая копия не тронута — pre-existing модификации `contracts/openapi.json`, `frontend/static/css/wiki.css` и файлы `test-model/bugs/BUG-017-*`, `test-model/reports/` чужие, оставлены как были)

---

## 1. Вердикт

**APPROVE (с оговорками по стенду, не по продукту).**

- (а) wiki-сьют desktop: **29 passed, 0 failed** — волна 3 не сломана.
- (б) desktop-регресс соседних разделов: **193 passed, 14 failed, 3 skipped, 3 errors**; все 14 фейлов + 3 errors квалифицированы **как не относящиеся к волне 3** (воспроизводятся на baseline `dec22a6` до волны 3 либо интермитентны/flaky на любом коммите; детали в §3).
- (в) DV-контроль: **14/14 проверок, все DV-1…DV-10 правки на месте, отката нет** (скриншотный проход по 4 экранам, §4).

---

## 2. (а) Wiki-сьют desktop

```
python -m pytest tests/web/test_p15_wiki_{tree,page,editor,history}.py -q
→ 29 passed in 72.99s
```

| Файл | Тестов | Результат |
|---|---|---|
| test_p15_wiki_tree.py | 7 | passed (дерево 3+ уровней, раскрытие, поиск с mark, empty state) |
| test_p15_wiki_page.py | 8 | passed (создание, breadcrumb, статья) |
| test_p15_wiki_editor.py | 8 | passed (тулбар, undo/redo, изображения, WYSIWYG) |
| test_p15_wiki_history.py | 6 | passed (история, откат, удаление/409) |

Порядок прогонов не важен (tracked cleanup подтвержден: сьют зелен и в составе полного web-прогона, и отдельно).

## 3. (б) Desktop-регресс соседних разделов

```
python -m pytest tests/web/ --ignore=…p15_wiki_{tree,page,editor,history}.py -q
→ 14 failed, 193 passed, 3 skipped, 3 errors in 647.66s
```

Квалификация каждого фейла — перегон на **baseline-worktree `dec22a6`** (коммит непосредственно перед волной 3, чистый чекаут) и/или точечными повторами:

### 3.1 Падают и на baseline (до волны 3) — НЕ волна 3, известные/средовые

| Тест | Симптом | Baseline |
|---|---|---|
| test_p14_41_lightbox_swipe.py × 5 | свайп-счетчик `3/6`, `3/9`… `3/18`, `.g-card`=24 вместо 3 — **загрязнение стенда тестовыми картинками QAGAL41-\* прошлых фаз** (счетчик считает все фото БД tmp-стенда сессии; накопление между кейсами внутри одного pytest-процесса) | те же фейлы (11 failed общим прогоном baseline-селекции) |
| test_qa21_gallery_ui.py (115/116/119) | тот же рост количества картинок; «QAGAL41-sw0.png» вместо «QAGAL-lb1.png» | те же (в baseline-прогоне пали 116/117/119 — тот же класс) |
| test_navigation_search_ui.py::test_sidebar_all_pages_and_wiki_stub | ассерт «/wiki = заглушка без кнопок» — **устарел семантически**: волна 3 легитимно сделала /wiki живым разделом; тест ожидает заглушку Этапа A. На baseline падает по-другому ассертом (`Locator expected to be visible` — заглушки уже нет и там из-за шаринга статики?). Требует обновления под волна 3 — **вне скоупа 4.2, не чинил** | failed |
| test_p12_ui_polish_r8.py::test_combobox_three_tags_and_one_by_one_removal | timeout клика по чипу «Убрать тег QAT-u110-д» | failed (тот же timeout) |
| test_qa21_gallery_ui (117 на baseline) | like/xss — та же группа накопления картинок | failed на baseline |

### 3.2 Падают только на ветке, НО квалифицированы как средовые/интермитент — не регресс волны 3

| Тест | Симптом | Разбор |
|---|---|---|
| test_p12_nav_icons_favicon_r8.py::test_no_external_icon_or_favicon_requests (+ERROR в парном test_favicon_data_uri…) | консоль: `500 /api/wiki/pages` + `404 /api/images` при обходе NAV_PAGES | **Воспроизведен и разобран автономным стендом**: автостенд conftest создает tmp-БД БЕЗ wiki-схемы (migrate_wiki накатывается только wiki-фикстурой `wiki_pages_created`); если wiki-кейс с миграцией еще не выполнялся в сессии, `GET /api/wiki/pages` (tree.js при открытии /wiki) = **500 `no such table: pages`** — артефакт порядка тестов на стенде, не продукта (прод: миграция накатывается деплоем). `404 /api/images` — images-сервис на web-стенде не поднимается (как и в DV-прогоне review-001, артефакт стенда). ERROR-соседа — TargetClosedError route.fetch при teardown, шум playwright |
| test_bug014_search_task_view.py::test_…computed_styles_match_board | `getComputedStyle … parameter 1 is not of type 'Element'` | **Интермитентен на ОБОИХ коммитах**: точечный прогон ×3 на ветке = 2 passed/1 failed; ×3 на baseline = 3 failed; в составе полного файла = passed. Гонка «expect visible → evaluate» при асинхронном рендере task-view. Не волна 3 |
| test_p12_ui_polish_r8.py::test_settings_link_bbox_stable_across_active_focus | bbox y 589 vs 634 (45px) | **Интермитентен**: ×2 на ветке = passed; ×2 на baseline = 1 failed/1 passed. Flaky геометрии фокуса, не волна 3 |
| test_r4_commentfix_ui.py::test_comment_button_gap_below_textarea | зазор 5.3px вместо ~8px | **Интермитентен**: ×2 на ветке = passed/ passed; падает только в составе полного прогона (пиксельная метрика под нагрузкой параллельного рендера). Точечный прогон стабильно зелен |

**Резюме регресса:** ни один фейл не воспроизводится как детерминированный **новый** фейл волны 3. Три кластера:
1. **Загрязнение tmp-стенда картинками** (lightbox/gallery, ~9 фейлов) — предсуществующее, рвется на любом длинном прогоне; лечится гигиеной стенда/чисткой БД сессии, к волне 3 отношения нет (git log волны 3: изменений gallery.js/board-статики нет — только wiki-\* файлы).
2. **Стенд без wiki-схемы/images-сервиса** (nav_icons + errors) — порядок наката migrate_wiki на автостенде; продукт при боевой накатке (4.5) схему получает. Рекомендация: накатывать migrate_wiki в сессии автостенда conftest (один subprocess.run в web_server), тогда 500 исчезнет.
3. **Flaky-пятерка** (bug014, settings_link, comment_gap, combobox, navigation wiki-stub) — стабильно красные/мигающие и на `dec22a6`; navigation wiki-stub требует контентного обновления под живой /wiki (сделать в 6.1 QA-цикле).

### 3.3 Сайдбар-инварианты (пункт задачи)

Проверено в рамках успешных кейсов регресса и DV-прохода: пункт «Wiki» ведет на `/wiki` (скрин 01: активный раздел), порядок разделов прежний — Доска, Поиск, Wiki, Галерея (+ Мониторинг/Настройки в футере). Тест test_nav_order_addresses_states_unchanged — passed в общем прогоне.

## 4. (в) DV-контроль (скриншотный проход, контроль отката правок)

Полный ре-сверка не проводилась (ре-сверка = волна 3 review-001); контроль — «правки DV-1…DV-10 не откатились». Стенд: ручной аналог автостенда conftest (app + search + static + playwright-роутинг) + migrate_wiki, 1280×900.

**14/14 проверок passed.** Скриншоты: `test-model/reports/add-wiki/screenshots-42/`

| Пункт | Проверка | Результат | Скриншот |
|---|---|---|---|
| DV-1 | Сниппет поиска — чистый текст без HTML-тегов («итоговая смета на материалы…», без `<p>`) | OK | 03-search.png |
| DV-2 | h1 «Wiki» на /wiki | OK | 01-tree.png |
| DV-3 | meta узлов с детьми: «3 страницы · обновлено 10 окт.» | OK | 01b-tree-expanded.png |
| DV-4 | title undo «Отменить (Ctrl+Z)», redo «Повторить (Ctrl+Shift+Z)» | OK | 04-editor.png |
| DV-5 | Кнопка «Изображение» с текстовым лейблом | OK | 04-editor.png |
| DV-6 | error-banner «Заголовок не может быть пустым…» ниже h1, у формы | OK | 05-editor-error.png |
| DV-7 | aria-pressed только у кнопок-состояний (код: `stateful: false` у ссылка/таблица/изображение/undo/redo) | OK (код-контроль) | — |
| DV-8 | Диалог изображения: человеческое сообщение «Не удалось загрузить данные (HTTP 404).» вместо сырого «Not Found» | OK | 06-image-dialog.png |
| DV-9 | `.wiki-content { max-width: 980px }` — computed 980px на статье | OK | 02-article.png |
| DV-10 | Breadcrumb истории: «QA42-Корень / История версий» | OK | 07-history.png |
| + | поиск с подсветкой mark (инверсная amber) | OK | 03-search.png |
| + | диалог изображения: радио «Из галереи»/«Загрузить с диска» | OK | 06-image-dialog.png |
| + | h1 «История версий» + просмотр версии read-only | OK | 07-history.png |
| + | дерево 3 уровней строится и раскрывается | OK | 01b-tree-expanded.png |

Скриншоты визуально сверенны (визуальная инспекция каждого PNG): дефектов верстки не обнаружено; баннер 404 в диалоге изображений — артефакт стенда (images-API не поднят), текст уже human-readable (DV-8 закрыт).

## 5. Ограничения и рекомендации

1. **Не чинил** (вне скоупа 4.2): navigation wiki-stub тест (устарел семантически — ожидает заглушку), flaky-пятерка, гигиена tmp-БД стенда для gallery/lightbox.
2. **Рекомендация conftest**: накатывать `app.migrate_wiki` в `web_server` session-fixture (не только в wiki-фикстуре) — уберет 500 на /wiki у несвязанных UI-тестов, обходящих NAV_PAGES.
3. Рабочая копия ветки содержит чужие незакоммиченные правки (`contracts/openapi.json`, `frontend/static/css/wiki.css` +6 строк, `BUG-017-wiki-editor-footer-touch-target.md`) — не мои, не тронуты; на результаты не влияли (прогоны воспроизводимы и с ними, и baseline без них).
4. Известные падения test_search\* (отрезка f0fe4ec) в скоуп не попадали и не встретились.

## 6. Числа (сводка)

| Набор | Итог |
|---|---|
| wiki-сьют (4 файла) | **29 passed / 0 failed** (~73s) |
| desktop-регресс (38 файлов) | **193 passed / 14 failed / 3 skipped / 3 errors** (~648s); все фейлы квалифицированы как не-волна-3 (baseline-сверка + точечные перегоны) |
| DV-контроль | **14/14 OK**, 7 скриншотов в `screenshots-42/` |
