# BUG-012: таг-combobox Enter при открытом дропдауне дает 2 чипа (committed + ручной токен)

- **ID:** BUG-012
- **Статус:** APPROVED (закрыт). 2026-10-07 23:58: review-002 APPROVE (SHA 1beb036); PR #79 влит 23b7ab5 (2026-10-07 23:32: review-001 RETURN, blocker-1 — consumed-фильтр вычислен от последнего токена и применяется ко ВСЕМ rest: несвязанные ручные токены теряются end-to-end; сьют потерю не ловит. Рецепт: per-tag фильтр `!committedTags.some(s => s.toLowerCase().indexOf(tag.toLowerCase()) !== -1)`, убрать currentToken-проверку; мульти-токеновый e2e-тест; семантику токена-префикса решить ПМ. После доработки — review-002 (provenance SHA da32681 станет STALE)
- **Дата:** 2026-10-07
- **Окружение:** main `b0282fa`; QA-стенд nginx :18443 (app :8080, worktree /tmp/qa-r8/wt); Chromium (Playwright); venv /home/openclaw/venvs/wiki.
- **Severity:** minor→major (нарушение FR-92 committed-леджера при клавиатурном выборе; TC-r6-comb-005 красный стабильно)
- **Автотест:** `tests/web/test_r6_tag_combobox_ui.py::test_combobox_keyboard_navigation` (фейл стабильный: 4+ прогона, в т.ч. изолированный на чистой БД)

## Репро

```bash
env -u DB_PATH EKOTOV_WIKI_BASE_URL=http://127.0.0.1:18443 \
  EKOTOV_WIKI_DB_PATH=/tmp/qa-r8/verify/app.db EKOTOV_WIKI_IMAGES_DIR=/tmp/qa-r8/verify/images \
  EKOTOV_WIKI_AVATARS_DIR=/tmp/qa-r8/verify/avatars \
  /home/openclaw/venvs/wiki/bin/python -m pytest \
  "tests/web/test_r6_tag_combobox_ui.py::test_combobox_keyboard_navigation" -q --tb=short
# after Enter: input.value = 'QATkbдва, QATkb,' → чипов 2 (ожидание 1)
```

## Что известно (факты ПМ — проверять, не переоткрывать)

- Воспроизводится изолированно на чистой БД: `tags.fill("QATkb")` → дропдаун
  показывает 3 option + option-add «+ Добавить тег «QATkb»» (exact-совпадения
  нет — все три подсказки содержат QATkb как подстроку); активный — первый
  option «QATkbдва». Enter → `chooseActive()` → `chooseValue("QATkbдва")` →
  committedTags=['QATkbдва'], `syncInputAndDom` строит line = committed + rest,
  где **rest включает ручной токен «QATkb»** (не был выбран, лежит в input) →
  'QATkbдва, QATkb,' → renderTagsChips рисует 2 чипа.
- Живая DOM-интроспекция: box.children — 1 ul (3 li внутри) + 1 голый li.option-add
  вне ul (append после ul); querySelectorAll('.option') = 3, activeOption() = QATkbдва
  — механика выбора работает, проблема в семантике line: «QATkb» после выбора
  остается в rest как отдельный валидный тег.
- Открытый вопрос (решать сабагенту): что делать с частичным токеном после
  committed-выбора — затирать токен ввода целиком (после Enter токен «QATkb» уже
  «потреблен» выбором), оставлять (тогда 2 чипа — легитимно, но тест/ФР-92
  говорят иное), или дедуплицировать rest против префикса committed. Ожидание
  теста: 1 чип «QATkbодин» НЕ требуется — тест ожидает 1 чип выбранного тега;
  семантику сверить с FR-92/design §2 и review #49 (committed-леджер).
- Замечание: выбор происходит по Enter при ЛЮБОМ положении — тест выбирает
  первый (aria-selected=true) пункт, т.е. «QATkbдва», а не совпадение по токену.

## Критерий закрытия

Тест зеленый на чистом стенде; смежные combobox-тесты (TC-r6-comb-001…011,
tag-ledger-leak) не деградировали; мутационная проверка (снять фикс — красный);
`node --check` + юниты committed-леджера зелёные.
