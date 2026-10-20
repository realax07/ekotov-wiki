# Code review — p12-rich-tools фикс-раунд: review-002 (только дифф 2c5ff19..8ae9c90)

flow: flow=1 role=code_reviewer repo=/home/openclaw/ekotov-wiki scope=p12-rich task=review-2

Роль: code_reviewer (независимый, append-only). Предмет: фикс-дифф
2c5ff19..8ae9c90 (1 коммит 8ae9c90 на chore/p12-rich-dev) — реакция dev'а
на review-001 (F-1 blocker, F-2/F-3 major) + находки design_validator
(design-check #1/#5/#6). Объем: sanitize.py (+40), pages.py (static_v →
p12-rich-dev2), editor.js (+57), rich/{codeblock,spoiler,tabletools}.js,
wiki.css (+26), тесты: api sanitize +6, web rich +4 (итого 21).

Метод: полный diff-ревью каждого фикса по логике + **эмпирическая
валидация дискриминаторов**: каждый фикс ПООЧЕРЕДНО откатывался в
изолированном worktree /tmp/wt-p12rev2 (detached 8ae9c90) и прогонялся
прицельный тест — проверено, что тест ПАДАЕТ на пред-фикс коде; после
каждого прогона откат восстанавливался (git checkout, дерево чистое).

---

## Вердикт: approve

Все находки review-001 устранены корректно, дискриминаторы доказаны
эмпирически (падают на пред-фиксе), регрессий в объеме диффа не найдено.

## Проверка находок review-001

| # | Фикс | Проверка | Дискриминатор |
|---|---|---|---|
| F-1 | Два слоя: sanitize.py br→`\n` в code-контексте (sanitize.py:200-209) + normalizeNewlines в normalizeCodeInput ДО сериализации (codeblock.js:182-203) | Подтвержден. Санитайзер: br в code-контексте эмитит текстовый `\n`, прочая разметка по-прежнему unwrap; _trim_empty_code_newlines отсекает `\n` пустого блока — три пути закрытия тега (handle_endtag, handle_startendtag, result-дозакрытие) все вызывают trim, стек кортежей консистентен на всех pop-сайтах. Редакторский слой: data-caret-якорь удаляется (не заменяется), пустой код не трогается | `test_rich_code_br_becomes_newline_not_merged` + `test_rich_code_trailing_br_keeps_trailing_newline` пали на пред-фиксе (проверено откатом). Якорь в БД не остается: пустой блок `<code><br></code>` → trim → пустой `<code>` (`test_rich_code_empty_block_br_anchor_stays_empty`, green). Изоляция: br вне кода не тронут (`test_rich_br_outside_code_context_untouched`) |
| F-2 | buildGutter(code, block) в syncGutter (codeblock.js:49) | Подтвержден: пред-фикс вызов с одним аргументом давал TypeError на `block.querySelector` на каждом input | `test_code_enter_multiline_saved_with_newline_gutter` пал на пред-фиксе (гуттер «1», pageerror). На фиксе: гуттер «1\n2», в БД ровно `line1\nline2`, слития нет, pageerror = 0 (живая проба БД) |
| F-3 | Гейт rename по editable (spoiler.js:63) + гонка Escape/blur через restore() с guard `titleSpan.parentNode !== head` | Подтвержден. В статье клик по названию = toggle; restore() — единственная точка возврата, commit после restore не делает replaceChild | `test_spoiler_title_click_in_view_toggles_not_renames` пал на пред-фиксе (input появлялся). На фиксе: toggle closed→open, input.count()==0, pageerror = 0 |

## Проверка находок design_validator

| # | Фикс | Проверка | Дискриминатор |
|---|---|---|---|
| #1 | Enter в ячейке → execCommand('insertLineBreak') (tabletools.js:278) | Подтвержден | Усиленный `test_table_tab_navigation_enter_br` пал на пред-фиксе (insertHTML давал хвостовой br, текст слит). На фиксе: «вторая<br>третья строка» в innerHTML И в БД, «втораятретья» отсутствует |
| #5 | Панель таблицы по мокапу tool-5: прозрачный оверлей (pointer-events:none, кнопки auto), кластеры col/row/foot, позиционирование от целевой ячейки | Подтвержден. Геометрия проверена тестом по getBoundingClientRect: col-кластер у границы столбца над таблицей, row-кластер за правым краем на уровне строки, foot под таблицей; клики по ячейкам не перехватываются (все прочие rich-тесты green) | `test_table_panel_layout_follows_target` — прежняя однострочная панель не прошла бы метрики colAbove/rowRight/footBelow |
| #6 | Гейт блоковых вставок в код-блок: insertBlockGuarded/caretInCodeBlock (editor.js) для спойлера/табов/таблицы/картинки/кода | Подтвержден. Тихий отказ без вставки — соответствует матрице §6 («в код-блоке — НЕТ»); якорь вне area/без выделения → вставка разрешена (поведение вне кода не изменено) | `test_insert_blocks_gated_inside_codeblock`: каретка в code → 0 спойлеров/табов/таблиц в DOM и в БД, `x = 1` сохранен, pageerror = 0 |

## Попутный фикс

repr кортежа стека в result()-дозакрытии (`</('p', None)>`) устранен —
все pop-сайты распаковывают кортеж. `test_sanitize_unclosed_tag_closed_cleanly`
пал на пред-фиксе (проверено откатом), на фиксе `<p>hello</p>`/`<b>x</b>`.

## Прогоны (этот ревью, worktree /tmp/wt-p12rev2, 8ae9c90)

- api `test_sanitize.py` — **60 passed**
- web rich `test_rich_tools.py` — **21 passed** (в т.ч. 4 новых)
- Дискриминаторы: 5 целевых откатов → каждый прицельный тест падал на
  пред-фиксе; дерево восстановлено в 8ae9c90 без изменений.

## Замечания (не блокируют, W-класс)

| # | Место | Суть |
|---|---|---|
| W1 | codeblock.js:185 `if (!code.textContent) return false` | Пустой код с data-caret-якорем не нормализуется до первого ввода; при сохранении НЕпустого блока с уцелевшим якорем (вне путей normalizeCodeInput) санитайзер дал бы хвостовой `\n`. Практически недостижимо (обе ветки normalizeCodeInput зовут normalizeNewlines), но хвостовой `\n` в БД возможен при экзотических путях вставки HTML. Не фиксить в рамках волны |
| W2 | syncGutter (codeblock.js:45-52) | Копирует только textContent замены, style.top пересчитанного гуттера не переносит. Неактуально при жизни head (top стабилен между enhance), отметить при рефакторинге |
| W3 | editor.js caretInCodeBlock | Гейт молчалив: пользователь не узнает, почему вставка не сработала. Матрицей §6 допускается; UX-полировку — в бэклог |
| W4 | sanitize.py:323 has_text | Чанк `\n` от br-якоря и литеральный текстовый `\n` из источника неразличимы: whitespace-only код-блок («код» из одних переводов строк без символов) обрезается до пустого. Семантически корректно (пустой блок), поведение совпадает с пред-фиксом |

## Итог

**approve.** Дифф 8ae9c90 закрывает review-001 (F-1/F-2/F-3) и
design-check #1/#5/#6; все дискриминирующие тесты доказаны откатами;
api 60 + web rich 21 green. Ветка готова к волне 6.3 (финальный бамп
`p12-rich-1` — вне этого диффа). Не пушить (по регламенту flow).
