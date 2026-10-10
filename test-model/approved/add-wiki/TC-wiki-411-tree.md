# TC-wiki-411 — Дерево страниц Wiki: корни, поддеревья без ограничения глубины, пустое состояние (FR-107)

- **Change:** add-wiki
- **Источник:** wiki (ADDED): Requirement «Дерево страниц Wiki» (ОВ-4, FR-107) — Scenario «Открытие /wiki со страницами», «Раскрытие и сворачивание узлов», «Пустое состояние»; design §6, мокап wiki-tree.html; CHK-wiki-3, CHK-wiki-4, CHK-wiki-5
- **Тип:** ФТ, UI | **Приоритет:** Must
- **Предусловия:** авторизованный пользователь; корпус: корневые страницы + вложенность 3+ уровней; отдельный прогон — пустая wiki (0 страниц)
- **Шаги:**
  1. Открыть /wiki без параметров → список корневых (`parent_id = NULL`) с поддеревьями; дерево построено из плоского списка одним GET /api/wiki/pages.
  2. Клик по узлу с детьми → поддерево раскрыто (aria-expanded=true, шеврон 90°); повторный клик → свернуто; вложенность любой глубины без ограничения.
  3. Мета узлов: «N страниц» / «N страниц · обновлено …» (DV-3 на месте).
  4. Desktop: раскладка `.wiki-layout` 280px + контент; ≤480px — одна колонка, дерево сверху.
  5. Прогон на пустой wiki → dashed-плашка `.wiki-empty` «В Wiki пока нет страниц» + кнопка «Создать первую страницу» → ?create=1 (редактор); отдельной «главной страницы» нет (ОВ-4).
- **Ожидаемый результат:** дерево корректно отображает иерархию, узлы раскрываются/сворачиваются, пустое состояние с рабочей кнопкой создания. Факт прогона 4.2: green (TC-wiki-001/004/005/006/007 в составе 29 passed; DV: 01-tree.png, 01b-tree-expanded.png, 13-empty-state.png); 4.3 mobile п.1 — PASS.
- **Автотест:** tests/web/test_p15_wiki_tree.py::test_wiki_tree_three_levels_build_and_collapse (TC-wiki-001), ::test_wiki_empty_state_create_first_page (TC-wiki-004), ::test_wiki_empty_state_button_opens_editor (TC-wiki-005), ::test_wiki_toolbar_create_button_opens_editor (TC-wiki-006), ::test_wiki_layout_desktop_280_and_mobile_one_column (TC-wiki-007) + tests/api/test_wiki_api.py::test_list_pages_flat_shape
- **Статус:** **approved** (QA 4.2 прогнан: wiki-сьют 29 passed / 0 failed + DV-контроль 14/14; REPORT-4.2-web-desktop.md §2, §4)
