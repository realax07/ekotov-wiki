# Ревью 002 — задачи 4.2/4.3: повторное ревью дифа фиксов (change add-rich-editor)

- **Диф:** `git diff f439a26..ae1a136` (единственный фикс-коммит ae1a136; review-001-4.1 не тронут).
- **Объем:** 10 файлов, +410/−37: rich_blocks.py, sanitize_rich.py, wiki.py, block-parser.js, renderer.js + тесты (api: rich_blocks/sanitize_rich/wiki_api; web: test_rich_editor; REPORT-perf — новая строка прогона 0.24 с PASS).
- **Вердикт: APPROVE** — все 5 пунктов review-001-4.1 закрыты корректно и подтверждены прогоном. Одно новое наблюдение (minor, вне дифа, не блокирует — см. «Хвост»).

## Проверка пунктов review-001-4.1

| # | Исходно | Статус | Чем закрыт |
|---|---|---|---|
| 1 | **major**: нет лимита глубины → RecursionError/500 в шве | **Закрыт** | `MAX_DEPTH=100` в rich_blocks.py (depth-параметр протянут через ВСЕ рекурсивные пути: callout/aside/spoiler children + segments columns) и зеркально в block-parser.js (локальная `depth` в parseColumns переименована в `openDepth` — тень параметра устранена). strict → RichSyntaxError (ValueError), толерантно → текст+warning; страховка `except (ValueError, RecursionError)` в шве wiki.py (патологический контент мимо лимита — та же политика A-2). Тесты: TC-RICH-201/202 (n=500: strict — ошибка, tolerant — без исключения, roundtrip стабилен), 203/204 (границы: ровно MAX_DEPTH валидно, +1 — ошибка), 209/210 (POST/PUT/revert с 500 callout → 201/200/200, plain text, НЕ 500 — через живой стенд), 211 (реальный браузер: JS MAX_DEPTH == Python MAX_DEPTH, parseStrict бросает, parse — нет). |
| 2 | minor: кандидат блока-изображения с URL в скобках — инвариант зеркала не зафиксирован | **Закрыт** (выбранный вариант — «задокументированный инвариант + дифтест») | SECURITY-ИНВАРИАНТ задокументирован в ОБОИХ парсерах (sanitize_rich.py у _URL_GROUP; block-parser.js у IMAGE_LINE_RE); проверено: `_IMAGE_LINE_RE` (rich_blocks.py:74) и `IMAGE_LINE_RE` (block-parser.js:46) — дословно идентичны. PAREN_URL-фикстуры `![a](javascript:alert(1))` / `[ссылка](http://x/a(b)c(d))` заведены синхронно в api-тестах (FIX_*) и web GRAMMAR_FIXTURES (дословное зеркало). Тесты: TC-RICH-205 (passthrough == sanitize_html, M-4), 206 (внутри блока javascript: нейтрализуется rich-путем), 208 (lossless roundtrip фикстур). |
| 3 | minor: рассинхрон URL-групп инлайна бэк/фронт | **Закрыт** | `INLINE_TOKEN_RE` URL-группа теперь `((?:[^()\s]|\([^()]*\))*)` — дословное зеркало `_URL_GROUP`; комментарий-инвариант синхронизации на месте. Тесты: TC-RICH-207 (бэк сохраняет ссылку с ≥2 группами скобок целиком), 212 (реальный браузер: фронт рендерит ССЫЛКОЙ с полным href, не литералом). |
| 4 | minor: `&amp;` мутирует при правке | **Закрыт** (в скоупе замечания) | Все 4 пути renderer.js (escTextToNode, renderTextContent, appendTextParagraphs, unfolded) больше не декодируют `&amp;`; `folded`/`textToDialect` (таблицы) эскейпят только `<`/`>` — согласовано с бэкендом (& не экранируется). TC-RICH-213: реальный roundtrip в браузере — `AT&amp;T` показывается/сохраняется без мутации, `&lt;` разворачивается. |
| 5 | minor: стиль wiki.py, лог create_page | **Закрыт** | Лишние пустые строки убраны; `create_page` передает `page_id="new page"` — лог fallback не теряет контекст. |

## Верификация (реальный прогон, не чтение диффа)

- Стенд поднят по tests/README.md (uvicorn :8092, tmp-БД + seed owner/wife + migrate_r4).
- `pytest tests/api/test_rich_blocks.py tests/api/test_sanitize_rich.py tests/api/test_wiki_api.py` → **102 passed** (включая все новые TC-RICH-201…210; тесты шва идут через живой HTTP, не мок).
- `pytest tests/web/test_rich_editor.py` → **15 passed** (~28 с, автостенд + chromium): TC-RICH-211/212/213 выполняются в реальном DOM.
- Диф-дисциплина: вне перечисленных файлов изменений нет; REPORT-perf дополнен фактом повторного прогона (0.24 с, PASS) — append-only соблюден.

## Хвост (новое наблюдение, вне среза ревью — НЕ блокирует)

Тот же класс roundtrip-мутации `&amp;`, что в пункте 4, остался в блочных модулях, которые в review-001 не назывались: `blocks/code.js` (`unfoldEntities`), `blocks/spoiler.js` (`unfolded` заголовка), `blocks/tables.js` (`fillCell`) — декодируют `&amp;`→`&` на показ/правку, а write-back эскейпит только `<`/`>`. Литеральный `&amp;` в код-блоке/заголовке спойлера/ячейке таблицы мутирует в `&` при открытии-правке-сохранении. TC-RICH-213 покрывает только текстовый путь renderer.js. Рекомендация: синхронное снятие декода `&amp;` в этих трех модулях + расширение TC-RICH-213 (или отдельный кейс) — в очередной итерационный хвост, не ре-ревью этого диффа.

## Итог

Major устранен точечно и проверен на живом шве и в реальном браузере; minors 2–5 закрыты в выбранных формулировках. Диф фиксов чист, тесты честные и проходят на стенде. **APPROVE** — ветка готова к дальнейшим задачам конвейера; хвост из трех блочных модулей — в backlog.
