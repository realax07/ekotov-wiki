# Code review — p12-rich-tools dev-волны 1–5: review-001

flow: flow=1 role=code_reviewer repo=/home/openclaw/ekotov-wiki scope=p12-rich task=dev-review
<!-- Reviewer-Delegation: вписать ПМ из реестра делегаций (REVIEWER_META_RE) -->

Роль: code_reviewer (независимый, append-only). Ревьюируемый объем: диф
origin/main...HEAD (2c5ff19, ветка chore/p12-rich-dev, 1 коммит dev-волн 1–5):
`backend/app/sanitize.py` (+15 XSS/блок-кейсов словаря, depth-счетчик,
table-in-table, code-контекст), `frontend/static/js/wiki/rich/*` (model,
spoiler, codeblock, tabs, headings, tabletools, highlight), `editor.js`
(вставка блоков, serializeArea, H-toggle), `page.js` (активация view),
`backend/app/pages.py` (static_v → p12-rich-dev1), `wiki.css` (+355),
`tests/api/test_sanitize.py` (+225), `tests/api/test_wiki_rich.py` (+258),
`tests/web/test_rich_tools.py` (+792, 17 кейсов). Контракт:
openspec/changes/p12-rich-tools/{spec(×2 дельты),design,review-architecture}
(F1–F5 устранены, эталоны ОВ-1…ОВ-5).

Метод: полный diff + сверка с design §1–§10; три эскалации ТЗ проверены
с пристрастием кодом и ЖИВЫМИ playwright-пробами на изолированном стенде
(qa_stand_up.sh из worktree, STAND_DIR=/tmp/qa-stand-p12rev, nginx :18461 —
поднят из этого диффа, в конце сессии погашен). Прогоны: api
(sanitize+wiki_rich+wiki_api) — **89 passed**; web rich-сьют
test_rich_tools.py — **17 passed**; regression p15 (wiki-домен:
test_p15_wiki_{page,editor,tree,history}) — **32 passed + 2 environmental**
(empty-state тесты пали на ЗАМЕТАННОМ дереве стенда: 8 страниц-остатков
общего стенда; на чистом дереве оба перепрогнаны — **green**; к диффу
отношения не имеют, фикстура wiki_api на внешнем стенде не убирает за
собой — замечание W1). Живые пробы: ввод двух строк в код-блок (Enter),
сохранение, чтение БД/API; перехват pageerror.

---

## Вердикт: return

Вернуть dev'у на доработку. Архитектура валидна (все три эскалации ТЗ
проверены — см. «Эскалации»), XSS-поверхность прикрыта (api+web векторы
green), depth-лимит и static_v — ОК. Но найден **блокер класса «потеря
контента»** (урок rich-v1 §7 — воспроизведен живой пробой) плюс два major;
все три точечные, без переделки архитектуры.

## Находки

| # | Файл:строка | Серьезность | Суть | Рекомендация |
|---|---|---|---|---|
| F-1 | codeblock.js:216-222 + sanitize.py (unwrap br в code-контексте) | **blocker** | Enter в код-блоке редактора дает `<br>` внутри `<code>` (Chromium; проба: DOM `<code>line1<br>line2</code>`). Санитайзер в code-контексте разрешает только pre/code/текст — br unwrap'ится, и ВЕСЬ перенос строки теряется: в БД сохраняется `line1line2` (проба: view-код слит, api-контент без `\n`). Многострочный код штатным вводом набрать НЕЛЬЗЯ — тот же класс потери контента, что rich-v1 (design §7), нарушение инварианта «текст кода сохраняется» (§1/FR-119). Комментарий в newCodeblockHtml («санитайзер br вырезает — в БД текст без мусора») описывает ровно этот канал и считает его фичей | Нормализовать переносы ДО сериализации/на санитайзере: в code-контексте `br` → текстовый `\n` (санитайзер), либо normalizeCodeInput при вводе конвертирует `<br>` в `\n`-текстовый узел. Обязательно web-тест «две строки кода через Enter → в БД ровно один `\n`» (сейчас_multiline-путь не покрыт ни одним тестом) |
| F-2 | codeblock.js:49 (syncGutter → buildGutter(code)) | **major** | buildGutter(codeEl, block) вызывается с ОДНИМ аргументом; внутри `block.querySelector('.codeblock-head')` → TypeError «Cannot read properties of undefined» на КАЖДОМ input-событии в код-блоке (проба: 11 pageerror за 4 нажатия). Гуттер в редакторе не обновляется никогда (проба: две строки — нумерация осталась «1»); ОВ-2 нумерация в редакторе сломана. View не затронут (там buildGutter зовется с двумя аргументами), потому сьют green — кейса «многострочный ввод в редакторе» нет | Передать `block` вторым аргументом (или вынести подсчет строк в чистую функцию). Тест: ввод 2+ строк → гуттер «2», pageerror = 0 |
| F-3 | spoiler.js:59-66 (buildHead без учета editable) | **major** | Клик по названию спойлера открывает инлайн-rename и в СТАТЬЕ (view): buildHead вешает startRename безусловно. Нарушает ОВ-1 («кликабельна ВСЯ шапка — сворачивание/разворачивание») и сценарий FR-118 «клик в любое место шапки → сворачивается» в части названия; в статье появляется мутация data-title без пути сохранения (фиктивное «редактирование», теряется на перезагрузке). Сьют green, потому что тест кликает `.spoiler-head` в центр (мимо title-спана) — хрупко | Ветвить по `options.editable`: в view клик по названию = toggle. Тест: в статье клик по `.spoiler-title` → спойлер свернулся, input не появился |

## Эскалации ТЗ (проверены с пристрастием)

1. **FR-119 отклонение (подсветка только в view; в редакторе plain+нумерация)
   — ВАЛИДНО.** Альтернатива подсветки в contenteditable ушла бы в PUT
   (сохранение = innerHTML минус data-editor), санитайзер срезал бы спаны →
   расхождение «редактируемый DOM ≠ сохраняемый» — тот же класс бага, что
   rich-v1; design §1 («спанов подсветки в БД нет, подсветка — только при
   отображении, §5») и §5 реализацию подтверждают. Web-тест test_code_language_
   numbering_copy_highlight фиксирует инвариант «в БД нет tok-*». НО: текст
   spec FR-119 («Код MUST подсвечиваться… нумерация строк — ДА») и сценарий
   «Вставка кода… THEN код отображается с нумерацией строк и подсветкой»
   даны в редакторном контексте GIVEN — термин не разграничен edit/view.
   Рекомендация (Should, правка текстом дельты, не кодом): в spec добавить
   «подсветка — только при отображении статьи; в редакторе — plain моно с
   нумерацией» (сейчас это держится только на design §1).
2. **Гуттер соседом+absolute — решение КОРРЕКТНО.** Сериализация не режет:
   pre — прямой контентный узел, гуттер — data-editor-сиблинг, вырезается
   детерминированным обходом (model.js serializeArea); live-проба: после
   сохранения pre/code на месте. Съезжанию препятствует `.codeblock{position:
   relative}` + `pre{margin-left:40px}` (wiki.css), top выставляется по
   высоте шапки. Единственный дефект узла — F-2 (обновление), не схема.
3. **Chromium-квирки — подход разумен, но хрупкость ПОДТВЕРДИЛАСЬ один в один:**
   br-якорь каретки (newCodeblockHtml) рассчитан на то, что санитайзер br
   вырезает, а Enter-ввод дает br, который «безвреден» — ровно эта пара и
   потеряла переносы (F-1). normalizeCodeInput (перенос узлов pre→code) и
   отложенная каретка tabletools (setTimeout-хил выделения после удаления
   строки) тестами покрыты (17/17 green), table-ветка стабильна. Фикс F-1
   обязан сохранить оба механизма и добавить multiline-тест.

## Проверено и в порядке

- **XSS-векторы sanitize**: script/style с содержимым, on* (onclick/onerror),
  `javascript:`-URL (в т.ч. tab/mixed-case-обфускация), data:-img, подмененные
  значения словаря (data-block=evil, data-lang=javascript), svg-инъекция через
  класс не возможна (class вне whitelist; SVG спойлера — статический
  CARET_SVG в JS, не данные). api: 89 passed (в т.ч. test_rich_* 15 кейсов,
  словарь sanitize↔model.js сверяется тестом test_rich_dictionary_matches_js_
  model); web: test_xss_vectors_inside_blocks_not_executed — window.__xss
  не выставляется, pageerror 0.
- **Лимит глубины 5**: 5 уровней проходят, 6-й unwrap'ается, текст цел
  (test_rich_depth_five_passes / _six_unwrapped) — соответствует NFR-39.
- **table-in-table** режется на санитайзере с сохранением текста ячеек
  (`<br>`-разделитель) — F3 ревью-архитектуры закрыт в коде, тесты green.
- **static_v = p12-rich-dev1 (pages.py)** — промежуточный идемпотентный бамп
  по impact.md §Статика/IR-03 (каждый dev-PR со статикой несет бамп),
  финальный `p12-rich-1` за волной 6.3 (ПМ) — ОК, правок не требует.
- **Лексер (highlight.js)**: sticky-правила без вложенных квантификаторов,
  линейный проход, >64 КБ → plain, любой эксепшн → plain (F5 закрыт);
  экранирование эмита сверено (esc над декодированным текстом).

## Наблюдения (не блокеры)

- **W1**: фикстура wiki_api (tests/web/test_rich_tools.py) на внешнем стенде
  (EKOTOV_WIKI_BASE_URL задан) оставляет после себя 8 страниц — teardown-DELETE
  не отработал; на общем стенде это валит чужие empty-state кейсы (проверено:
  p15 tree empty-state краснеет на заметеанном дереве, green на чистом).
  Кандидат на отдельный chore-фикс фикстуры, не блокер P12.
- **W2**: syncGutter пересобирает гуттер только по input; undo (Ctrl+Z) не
  шлет input в части случаев — после undo нумерация может отстать. Закроется
  вместе с F-2, если пересчет звать и по selectionchange с дебаунсом.

## Provenance

- Дифф: origin/main...HEAD @ 2c5ff19 (chore/p12-review worktree /tmp/wt-p12rev).
- Прогоны: api 89 passed (5.4s); web rich 17 passed (36s); p15 32 passed
  (+2 environmental — перепрогон на чистом дереве 2 passed).
- Живые пробы: /tmp/wt-p12rev/probe_gutter.py (GUTTER_TEXT:'1', PAGE_ERRORS:11,
  VIEW_CODE:'line1line2'), probe_newline.py (DOM `<code>line1<br>line2</code>`).
- Стенд: STAND_DIR=/tmp/qa-stand-p12rev, порты 18091–18095/18461, погашен
  после ревью.
