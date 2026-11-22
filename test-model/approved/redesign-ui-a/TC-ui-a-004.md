# TC-ui-a-004: Единый источник дизайн-токенов A (FR-128)

- **Change:** redesign-ui-a
- **Источник:** design-tokens MODIFIED — «Единый источник дизайн-токенов «Пульт» (FR-128)» / Scenario: «Перенос токенов без изменения значений», «Служебные токены техноязыка определены», «Нет ссылок на удаленные V3-токены», «Кеш статики инвалидирован»
- **Тип:** поз. | **Приоритет:** Must
- **Среда/предусловия:** доступ к `frontend/static/css/app.css` и `pages.py`; редизайн применен
- **Шаги:**
  1. Снапшот `:root` (первый блок — dark-канон; парсинг по первому `:root`-блоку — вынужденное отклонение, light-блок `:root[data-theme="light"]`, sdd §4) — контрольные значения: bg rgb(30,15,20) #1e0f14, surface #2a161d, raised #371f28, border #3d2229, text #f7ece4, muted #c6ad9f, accent #d6a85c, accent-2 #c4505c, warning #f0aa42, warning-soft #4e3124, success #5ad88e, danger #e9817f (автотест `test_tc_redesign_010_tokens_single_source_snapshot`).
  2. V3-токены удалены, кеш инвалидирован: `static_v`-маркер «redesign-a», ссылок `--p-*` нет (автотест `test_tc_redesign_011_v3_tokens_removed_cache_invalidated`).
  3. Hex-gate: whitelist rgba/hex-баз = A-набор (`tests/api/test_qa21_gallery_design.py`, TC-GAL-122 tokens-часть).
  4. Шрифты: @font-face Golos Text (wght 400–900) / JetBrains Mono (400–800) — variable, диапазоны в font-weight дескрипторах (ревью-002 major-2).
- **Ожидаемый результат:** снапшот совпадает с канон-справочником sdd §4; legacy `#f0b45c`-ассерт сохранен; V3-ссылок нет; кеш-маркер обновлен. Прогон 2: 010/011 green.
- **Тестовые данные:** канон-таблица sdd §1.3/§4.
