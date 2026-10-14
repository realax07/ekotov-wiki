# Решение: PO-рефакторинг web-тестов (Флоу 5, экспресс — ретроспективный артефакт)

- **Дата:** 2026-10-13
- **Флоу:** 5 (экспресс; данный документ — ретроспективный артефакт express_close)
- **Ветка:** pipeline/po-refactor
- **Скиллы:** test-automation §Page Objects + playwright-pro (фабрика, J45)

## Что сделано

- `tests/web/pages/` — package Page Objects: Board, TaskForm, TaskDetail,
  Search, Auth, Sidebar (6 PO).
- Конвертированы: `test_board_tasks_ui.py` (8/8), `test_view_modal_r4.py`
  (9/9; заодно починен error `test_card_click_opens_readonly_view`, падавший
  на main).
- Верификация: полный прогон tests/web ветка vs main —
  main: 215 passed / 12 failed / 18 errors; ветка: **218 / 12 / 15** —
  нулевой регресс, +3 passed (все 12 failed — пред-существующий фон
  gallery/crop-фикстур, идентичен на main).

## Правила конвертации (для следующих волн)

1. PO на страницу/компонент в `tests/web/pages/`; локаторы по приоритету
   playwright-pro (get_by_role → … → CSS крайний случай).
2. Ассерты — в тестах; PO — действия/возврат локаторов (wait-обертки —
   исключение).
3. Чистый рефакторинг: логика/ассерты/TC-docstring не меняются.
4. PO — не догма: экраны с 1–2 использованиями можно оставлять прямыми
   локаторами.
5. Конвертация файла = коммит = прогон файла (атомарно).

## Остаток (волна 2, после восстановления пула провайдера)

settings_categories (84), p12_ui_polish (67), r5_crop (64), qa21_gallery (59),
r6_tag_combobox (58), settings_profile (56), p15_wiki_editor (43),
navigation_search (40), r3_selects (37), r3_formv3 (37) локаторов.
