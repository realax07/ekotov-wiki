# TC-ui-a-007: Сетка галереи и лайтбокс в стиле A (FR-125)

- **Change:** redesign-ui-a
- **Источник:** gallery MODIFIED — «Сетка галереи и лайтбокс в стиле «Пульт» (FR-125)» / Scenario: «Сетка галереи на темной теме», «Лайтбокс в визуале «Пульта»», «Тесты галереи без цветовых правок проходят»
- **Тип:** визуальный | **Приоритет:** Must
- **Среда/предусловия:** галерея с изображениями (fixture gallery_mock); для live-части — канонический контур :18443
- **Шаги:**
  1. Сетка/плитки: hover — подъем -2px + бордо-кромка accent-2, лайтбокс на bg/color-mix, счетчики mono tabular-nums (автотест `test_tc_redesign_016_gallery_grid_lightbox_pult`).
  2. Реакция «мой голос» — #4e3124 подсветка, 0-literal гейт (нет rgba/hex вне токенов; rgba «Пульта» удалены) (автотест `test_tc_redesign_017_gallery_my_vote_amber_no_v3`).
  3. TC-GAL-122 (`tests/api/test_qa21_gallery_design.py`): whitelist `--color-accent/#d6a85c`, `--color-warning-soft/#4e3124`; live-часть (`test_tc_gal_122_live_computed_styles_and_states`) — на каноническом контуре regress-final.
- **Ожидаемый результат:** сетка/лайтбокс соответствуют эталону `design-forge/extra/gallery` (сверка QA §4 ✓); функциональные gallery-сьюты зеленые без правок логики (Scenario 3 — прогон 2: green).
- **Тестовые данные:** изображения в tmp-томе images; категория для фильтра.
