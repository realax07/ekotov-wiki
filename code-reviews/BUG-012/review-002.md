# Ревью 002 (код-ревью Флоу 2): фикс BUG-012 — фикс-цикл 2 после RETURN review-001

- **Reviewer-Delegation:** внешняя (correlation 0fb60b21915841ddaa7bde3f97d4c3c5, review-002; сессия review-001 finished)
- **Ревьюируемый фикс:** PR #79, новый HEAD `1beb036` (`fix/bug-012-combobox`, поверх da32681); дельта `git diff da32681..1beb036` = ровно 2 файла (tag-combobox.js, test_r6_tag_combobox_ui.py; conftest.py не тронут), +79/−10. origin/fix/bug-012-combobox = `1beb0361b2fc0ab502a8629a2d21784ab22cf739` (сверено fetch'ем); PR #79 открыт, не смержен
- **Provenance SHA:** `1beb0361b2fc0ab502a8629a2d21784ab22cf739`; sha256 файлов диффа (рабочее дерево review-worktree `/tmp/review-bug012-r2` @ 1beb036, побайтно чистое до и после мутаций): tag-combobox.js `b8764523d358cecc697f5e6c0ccedfb9a73bd9ce3ce85cd64c82120d651b2023`, test_r6_tag_combobox_ui.py `79159fa03dd217ec5ad8eb7d996b1b7bd198643703685db6dc75a66b846bbbdd`, conftest.py `8f39e66b4724c935718063b59a225ac5da33665031e5fb00191a10f2c3d605f8` (= da32681-значению из review-001 — файл действительно не менялся)
- **Карточка:** `test-model/bugs/BUG-012-combobox-enter-double-chip.md`; спека-арбитры: FR-92, TC-UIP-109 (диспозиция ПМ), ПМ-семантика цикла 2: потребляется ТОЛЬКО currentToken и только если он — подстрока выбранного committed-значения; rest-теги сохраняются безусловно
- **Зона ревьюера:** только этот файл; rest read-only. Основной клон — pipeline/r8-32-prep @ dae085b, не тронут; все прогоны — в изолированном worktree 1beb036
- **Дата:** 2026-10-07
- **Метод:** (1) разбор дельты da32681→1beb036 против ПМ-семантики и замечаний review-001; (2) негативная проба самостоятельно (свежие токены, отличные от TC-011); (3) полный сьют + смежные на автостенде; (4) мутационная проверка дельты (возврат da32681-семантики → TC-011 обязан покраснеть; снятие фикса → двойной чип)

---

## Проверка 1: consumed теперь привязан к currentToken, rest сохраняется безусловно — blocker-1 СНЯТ

```js
// tag-combobox.js (1beb036)
var token = currentToken(input.value).toLowerCase();
var rest = splitTags(input.value).filter(function (tag) {
  if (committedTags.indexOf(tag) !== -1) {
    return false;                 // дедуп против committed — как было
  }
  if (!token || tag.toLowerCase() !== token) {
    return true;                  // ← несвязанный rest-тег: сохраняется ВСЕГДА
  }
  return !committedTags.some(function (selected) {
    return selected.toLowerCase().indexOf(token) !== -1;
  });
});
```

Дефектная конструкция da32681 (consumed вычислялся один раз от currentToken и возвращался как фильтр для ВСЕХ тегов) устранена: early-return `return true` для любого тега, не равного (точным сравнением, case-insensitive) currentToken, стоит ДО some-проверки. Соответствие ПМ-семантике цикла 2 — полное:

- потребляется только currentToken (последний редактируемый токен);
- потребление — только если токен является подстрокой (case-insensitive) какого-либо committed-значения;
- остальные rest-теги — безусловное сохранение;
- точное сравнение `tag.toLowerCase() !== token` (не подстрочное) корректно реализует границу «токен-префикс «QAT» в середине rest сохраняется» — он до some-проверки не доходит; вопрос префикса из review-001 «Что НЕ проверено» закрыт зафиксированной в комментарии кода семантикой;
- комментарий в коде переписан и теперь описывает фактическую семантику (замечание review-001 о расхождении комментария и кода устранено).

Предложенный в review-001 рецепт (`return !committedTags.some(s => s.toLowerCase().indexOf(tag.toLowerCase()) !== -1)` per-tag, подстрочный) dev реализовал строже: потребление возможено только для редактируемого токена, а не для любого rest-тега, оказавшегося подстрокой committed. Это соответствует формулировке ПМ цикла 2 («только currentToken») — принято как канон.

## Проверка 2: TC-r6-comb-011 — мутационный пробел review-001 ЗАКРЫТ

`test_combobox_multitoken_rest_unrelated_token_survives` закрывает оба дефекта ассерт-зоны, названных в blocker-1:

- мульти-токеновый rest: несвязанный токен «QATmtokчужой» стоит В НАЧАЛЕ строки, currentToken «QATmtok» — в конце (конфигурация, на которой da32681 теряла данные, а TC-005 молчала);
- ассерты в поле: выбранный «QATmtokдва» присутствует; «QATmtokчужой» СОХРАНЕН; дубля потребленного токена нет (`"QATmtok," not in value` + не заканчивается на «QATmtok»);
- чипы: ровно 2, каждый count==1 по тексту (усиленный стиль ассертов TC-005);
- **end-to-end**: сабмит формы → `GET /api/search` → в сохраненной задаче оба тега — именно уровень, на котором review-001 поймал безвозвратную потерю «QATprobelost»;
- изоляция: уникальное семейство QATmtok + seed одного тега → детерминированный единственный активный пункт (ассерт на data-value), флейк от QATkb-остатков предыдущих тестов исключен (проблема загрязнения БД, обнаруженная dev, — задокументирована в отчете, эскалация на ПМ в силе).

## Проверка 3: регрессии против FR-92/TC-UIP-109 — НЕТ

Дельта не трогает ничего вне фильтра rest и тестового файла. Двойной чип по-прежнему закрыт: мутация полного снятия фикса (см. проверку 6а) краснит `test_combobox_keyboard_navigation` (как и в review-001), а на чистом 1beb036 TC-005 green (1 чип выбранного). Committed-леджер (тег остается в input до сабмита) не изменен. `node --check` tag-combobox.js — OK.

## Проверка 4: самостоятельная негативная проба (отличные от TC-011 токены) — GREEN end-to-end

Временный тест в worktree (удален после фиксации): input `tags.fill("QATprobe2чужой, QATprobe2")` → единственная опция «QATprobe2два» (data-value ассерт) → Enter:

- в поле: «QATprobe2чужой» сохранен, «QATprobe2два» присутствует;
- сабмит → `GET /api/search` → сохраненная задача содержит ОБА тега (`QATprobe2два` и `QATprobe2чужой`).

Несвязанный токен переживает Enter-выбор и в поле, и в сохраненной задаче — blocker-1 не воспроизводится. (Проба сначала падала дважды по причинам самой пробы — лишний `status` в seed-POST (422) и неверный селектор листбокса `#task-tags-listbox` вместо `#task-tag-combobox`; после исправления пробы — green. К фиксу отношения не имеет.)

## Проверка 5: верификация на автостенде (worktree 1beb036)

```
env -u DB_PATH -u EKOTOV_WIKI_BASE_URL venvs/wiki/bin/python -m pytest tests/web/test_r6_tag_combobox_ui.py -q
→ 11 passed in 28.77s   (10 прежних + новый TC-011)
# смежные:
test_search_suggestions_ui.py + test_r8_tag_ledger_leak_ui.py + test_r6_wave2_ui.py + test_r3_formv3_ui.py
→ 13 passed in 34.69s
```

Заявления dev (11/11 green, смежные 13/13) — подтверждены независимо. `node --check` — OK.

## Проверка 6: мутационная проверка дельты (обязательна) — обе мутации ловятся

**(б) Возврат da32681-семантики** (consumed от currentToken, применяется ко всем rest — точный код da32681; node --check OK):

```
pytest tests/web/test_r6_tag_combobox_ui.py::test_combobox_multitoken_rest_unrelated_token_survives -q
→ FAILED tests/web/test_r6_tag_combobox_ui.py::test_combobox_multitoken_rest_unrelated_token_survives[chromium]
    value = tags.input_value()
    assert "QATmtokдва" in value, value
>   assert "QATmtokчужой" in value, value
E   AssertionError: QATmtokдва,
E   assert 'QATmtokчужой' in 'QATmtokдва,'
1 failed in 5.14s
```

— дословное воспроизведение blocker-1 (несвязанный ранний токен исчез из input, исчез бы и end-to-end). Мутационный пробел review-001 закрыт: мутация, которую старый сьют пропускал, теперь красная.

**(а) Полное снятие фикса** (rest без фильтра потребления, `return committedTags.indexOf(tag) === -1;`; node --check OK):

```
pytest ...::test_combobox_keyboard_navigation ...::test_combobox_multitoken_rest_unrelated_token_survives -q
→ 2 failed in 12.12s (keyboard_navigation — двойной чип, как в review-001; TC-011 — потеря несвязанного)
```

**Восстановление:** из бэкапа → sha256 tag-combobox.js `b8764523…` совпал с до-мутационным → node --check OK → полный сьют **11 passed in 28.20s**, `git status` worktree чист.

## Находки

| # | Серьезность | Место | Замечание | Рекомендация |
|---|---|---|---|---|
| 1 | minor (не блокирует) | tests/web/conftest.py:320–327 | В силе с review-001: префиксы `_to_search` без левого анкера — хрупко при смене схемы base_url | Анкеровать слева; вне дельты цикла 2 |
| 2 | obs (для ПМ) | test-model, системная тема | Межтестовое загрязнение tmp-БД автостенда (QAT-теги живут до конца сессии, cleanup задач теги не удаляет) — dev задефензировал TC-011 уникальным семейством QATmtok, но тема системная | Решение ПМ вне этого PR |
| 3 | obs (для ПМ) | frontend/static/js/board/task-form.js | В силе с review-001: чипы рендерятся из строки input (ОГР-27) — при рефакторинге на рендер из committedTags фильтр потребления переносить туда же | — |

Блокирующих находок: 0.

---

## Проверенные Scenario

- Дельта da32681→1beb036 построчно (2 файла); PR-граница против merge-base e3f33b3 (3 файла, все в зоне dev); origin-ветка сверена fetch'ем.
- TC-r6-comb-001…011 (полный сьют 11/11 на автостенде 1beb036); TC-UIP-109 семантика (committed-леджер, двойной чип — мутация (а) red, чистый код green); негативная проба мульти-токенового rest с end-to-end сабмитом (самостоятельно, иные токены); смежные: test_search_suggestions_ui (3), test_r8_tag_ledger_leak_ui (1), test_r6_wave2_ui + test_r3_formv3_ui (9); мутации (а) и (б) с дословной фиксацией и восстановлением по sha256.

## Что НЕ проверено (честно)

- CI PR #79 на 1beb036 (flow/e2e green) — принято по отчету dev и статусам PR, самостоятельно не воспроизводилось.
- Внешний QA-стенд :18443 — не в делегации; все прогоны на автостенде worktree.
- tests/api/test_suggestions_* (8 red на HEAD) — вне зоны PR, эскалация в силе.
- Тач-устройства и реальные скринридеры — только DOM/ARIA.
- Поведение при выборе «+ Добавить тег» (Tab-путь) с мульти-токеновым rest — покрыто косвенно (семантика фильтра едина для Enter/Tab, TC-005 green), отдельного e2e нет; риск низкий, так как chooseValue/путь фильтра общий.

---

## Вердикт: APPROVE

Blocker-1 review-001 устранен по ПМ-семантике цикла 2 (consumed только для currentToken и только как подстрока committed-значения; rest-теги сохраняются безусловно) и подтвержден независимо: самостоятельная end-to-end негативная проба green, мутационный пробел закрыт с обеих сторон (TC-011 краснеет дословно на da32681-семантике; снятие фикса краснит двойной-чип фиксатор). Регрессий против FR-92/TC-UIP-109 нет; conftest циклом 2 не тронут; дифф в границах зоны. Карточка BUG-012 — основание для перевода в APPROVED (запись за ПМ).

Provenance: вердикт привязан к SHA `1beb0361b2fc0ab502a8629a2d21784ab22cf739` и sha256 файлов из шапки. PR #79 НЕ смержен, НЕ запушен — решение за ПМ.
