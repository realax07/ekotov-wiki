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

## Волна 2 (2026-10-14, deleg_bdd7a28e — завершена)

- Конвертированы все 10 оставшихся топ-файлов (settings_categories 84,
  p12_ui_polish 67, crop 64, gallery 59, tag_combobox 58, settings_profile 56,
  wiki_editor 43, navigation_search 40, r3_selects 37, r3_formv3 37).
- PO: +SettingsPage, +ProfileSettingsPage, +CropWidget, +TagCombobox,
  +GalleryPage; расширены WikiPage(+WikiEditor), Auth/Sidebar, TaskForm,
  TaskDetail, Search.
- Пофайлово: каждый файл НЕ хуже базлайна main (прогоны до/после через
  worktree). Полный набор дважды: 217 passed / 12 failed / 2 skipped /
  16 errors; 12 failed и 15 errors — пред-существующий фон; +1 error —
  ротирующий средовый flake pw 1.63 (Route.fulfill/Fetch disposed при
  browser.new_context; в разных прогонах разные тесты, автономно зеленые).
- Итог PO-рефакторинга: tests/web полностью на PO, ~800+ дублированных
  локаторов вынесены в 14 PO-файлов; test-логика и TC-трассировка не тронуты.
