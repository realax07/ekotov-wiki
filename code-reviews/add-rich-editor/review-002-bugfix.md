# Ревью 002 — багфикс rich-редактора BUG-018/019/020 (Флоу 2, живая приемка p15-wiki-8)

- **Reviewer-Delegation:** deleg_UNKNOWN (проставить ПМ из реестра — J10)
- **Ветка:** pipeline/bugfix-rich-acceptance vs main; 5 коммитов (3 `[bugs]` + `[chore]` перф-строка + `[bugs]` статус-раздел).
- **Диф:** frontend/static/js/wiki/editor.js, rich/renderer.js, rich/blocks/code.js, wiki.css; тесты tests/web/test_rich_editor.py (+3), tests/api/test_rich_blocks.py (+2); REPORT-perf строка; BUG-018-отчет + PLAN.
## Вердикт: одобрить

Blockers нет; 2 minor (не блокируют, см. ниже).

## Проверено (фокус ТЗ)

**BUG-018 — тулбар вне редактируемого контента.**
- renderer.renderCanvas: в editing обертка блока получает `contentEditable=false` ДО appendChild контента и панели; панель (editControls) добавляется внутрь этой же обертки — по построению не входит в модель канвы. Сериализация — из `canvas.nodes` (модель), DOM-обхода нет: панель сериализоваться не может.
- Вложенные editing hosts переопределяют `contenteditable=true`: ячейки таблицы (tables.js:77), код-pre (code.js:88), legacy-сегменты и textline — редактируемость контента сохранена (TC-RICH-214 ассертит isContentEditable обоих слоев).
- XSS через новые editing hosts не вскрылось: writeback ячеек — только `textContent` (tables.js textToDialect), кода — `codeToText` (текстовые узлы + BR→\n, рекурсия по span — атрибуты/теги вставки отбрасываются); highlight-рендер — createElement/textContent. Paste-HTML в host коллапсирует в текст модели. Legacy-innerHTML путь (renderer.js:264) не тронут — серверная санитизация как до пакета.
- Опечатка «− столбtw»→«− столбец» в дифе подтверждена (tables.js editControls, текст кнопки «− столбец»).

**BUG-019 — {width=N} переживает roundtrip.**
- Парс/сериализация зеркальны: backend `_parse_image_line` (regex опциональная группа width, вне 10..100 — атрибут отбрасывается, без ошибки) ↔ `_serialize_image` (пишет width только если не None); sanitize перепроверяет whitelist на inline- И node-путях (sanitize_rich.py:93-97, :146-148); фронтовое зеркало block-parser.js:184 + renderer.js:125. Idempotentность re-save — тестом.
- Новый фронтовый узел: `insertRichImage` → `onInsertBlock({type:'image', src, alt, width: richWidthPercent(px)})`; `richWidthPercent` клампит Math.max(10, Math.min(100, …)) — NFR-34 соблюден; при отсутствии px («оригинал») → null, без {width=N}.
- `applyRichImageWidth` пишет в узел канвы через `__richCanvas`/`__richIndex` и перерендеривает — px-атрибут в DOM больше не единственный носитель. Legacy-img (вне .rich-block / не-rich режим): ранний return false → прежний px-атрибут, FR-125 не тронут (диф ветки legacy-кода отсутствует).
- Модалка при переоткрытии считает пресет из процента (style.width → px по clientWidth) — обратная конверсия симметрична.

**BUG-020 — режим «править код» удален, контент 1:1.**
- Кнопка/переключение plain подсвеченного удалены полностью (диф вычищает и bar, и CSS-класс rich-code-plain); editing host — блочный pre.
- Roundtrip 1:1: `codeToText` (текстовые узлы как есть, BR→\n, пустые div/p→\n — Chromium-состояния Enter) + `foldCode` (<→&lt;, >→&gt;) = каноническая форма диалекта; sanitize бэкенда & не экранирует — `foldCode` & тоже не создает (комментарий в коде, verified по sanitize_rich). Запись — на каждой мутации (MutationObserver) + страховочный focusout; потеря набранного (исходный баг) исключена — TC-RICH-216 прогоняет набор → blur → save → reload → re-save.
- Переподсветка на blur: перед highlightInto DOM сворачивается в единственный `code` (иначе задвоение), затем токенайзер; `highlightInto` — только textContent/createTextNode — XSS-поверхности не создает. Вектор `<b>text</b>` хранится/рендерится литерально (тест, API+web).

**Тесты — не моки.** TC-RICH-214/215/216 — реальный Playwright против автоподнимаемого стенда (uvicorn+search+static, tmp-БД), ассерты через сохраненный контент API-сессией (не DOM-заглушки); API TC-RICH-218 — реальный `sanitize`. Негативные проверки: ввод при фокусе на кнопке не меняет контент; width=101/9 отбрасывается; re-save идемпотентен.

**Перф-строка:** REPORT-perf append 0.32s (PASS, порог 2.0) — честная append-запись, деградации не скрывает (0.18→0.32 в пределах шума).

**Верификация ревью (мой прогон, ветка в актуальном состоянии):**
- `pytest tests/web/test_rich_editor.py` — **22 passed** (вкл. 3 новых);
- `pytest tests/api/test_rich_blocks.py` — **50 passed** (вкл. 2 новых);
- `node --check` всех трех тронутых JS — OK.

## Замечания

| # | Серьезность | Файл:место | Замечание | Рекомендация |
|---|---|---|---|---|
| 1 | minor | rich/blocks/code.js `unfoldEntities` | `unfoldEntities` разворачивает `&amp;`, `foldCode` его не восстанавливает: литеральный «&amp;» в коде мутирует в «&» при первой правке-сохранении; патология вида «&amp;lt;» дрейфует при повторных правках. Идемпотентно после прохода, семантически без потерь — но это ровно тот класс мутации, который review-001-4.1 №4 предписал убрать в renderer.unfolded (там исправлено, код-блок — нет; tables.fillCell — тот же паттерн, вне дифа). | Зеркально renderer.unfolded: код-специфичный unfold без декодирования `&amp;` (бэкенд & не экранирует). Можно отдельным мелким коммитом этого же пакета. |
| 2 | minor | rich/blocks/code.js focusout | Repair-циклы `while (pre.firstChild !== code …)` рассчитаны на `code` внутри pre. Select-all+delete в Chromium может удалить сам элемент `code`: циклы вычищают pre целиком, `highlightInto` наполняет ОТОРВАННЫЙ `code` — блок выглядит пустым до перерендера канвы. Модель корректна (writeBack выполняется до repair) — дефект косметический, самовосстанавливается при refresh. | Гвард перед highlightInto: `if (code.parentNode !== pre) pre.appendChild(code);` |
| 3 | info | тесты TC-RICH-214..218 | TC-RICH-217 в репо отсутствует (ни кейса, ни теста); TC-RICH-218 навешан на ОБА новых api-теста (bug019 и bug020). Если 217 — осознанный пропуск номера, зафиксировать в PLAN; если кейс существует в approved-наборе — теста под него нет. | Сверить с approved-кейсами пакета; 1 TC = 1 тест или review-mapping. |

## Итог

Все три бага закрыты по критериям отчета BUG-018-rich-editor-acceptance.md, решение Заказчика («только подсветка и графический фон») реализовано дословно. Оба minor — качество, не безопасность и не потеря контента; вливание не блокируют. Рекомендую замечания 1–2 добить точечными коммитами до живой приемки p15-wiki-9.
