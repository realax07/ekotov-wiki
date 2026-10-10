# TC-wiki-418 — Удаление страницы: лист по подтверждению, родитель с дочерними запрещен (ОВ-2, FR-116)

- **Change:** add-wiki
- **Источник:** wiki (ADDED): Requirement «Удаление страницы» (Should, дефолт ОВ-2, FR-116) — Scenario «Удаление листовой страницы», «Удаление страницы с дочерними запрещено»; design §6, мокап wiki-page (04, 14); CHK-wiki-13, CHK-wiki-14
- **Тип:** ФТ, негатив + позитив | **Приоритет:** Should
- **Предусловия:** авторизованный пользователь; листовая страница без дочерних (с изображением в контенте — для проверки файлов галереи) и страница с хотя бы одной дочерней
- **Шаги:**
  1. У листа нажать «Удалить» → диалог `.confirm[role=dialog][aria-modal]` «Удалить страницу?» (текст по мокапу, фокус на «Отмена», Esc закрывает) → подтвердить → DELETE 200 → страница исчезла из дерева; файлы изображений в галерее остались (в контенте были только ссылки /images/{id}); версии листа удалены (CASCADE).
  2. У страницы с дочерними: попытка удаления → 409; баннер `.error-banner[role=alert]` «Страницу удалить нельзя: у неё есть дочерние страницы. Сначала перенесите или удалите их.»; страница и поддерево на месте.
  3. Кнопка «Удалить» показывается только при can_delete (лист); у родителя с детьми — скрыта.
- **Ожидаемый результат:** лист удаляется после подтверждения без затирания файлов галереи; удаление страницы с дочерними запрещено (409, поддерево цело). Факт прогона 4.1: green (test_delete_with_children_409, test_delete_leaf_removes_versions, test_get_page_can_delete_leaf_vs_parent — passed из 27); 4.2 desktop: green (TC-wiki-103/104/105; DV 04-delete-dialog.png, 14-409-banner.png).
- **Автотест:** tests/web/test_p15_wiki_page.py::test_actions_visible_and_delete_gated_by_can_delete (TC-wiki-103), ::test_delete_confirm_dialog_and_redirect (TC-wiki-104), ::test_delete_conflict_409_banner_page_stays (TC-wiki-105) + tests/api/test_wiki_api.py::test_delete_with_children_409, ::test_delete_leaf_removes_versions, ::test_get_page_can_delete_leaf_vs_parent
- **Статус:** **approved** (QA 4.1: 27 API passed / 0 failed; QA 4.2 прогнан: 29 passed / 0 failed + DV 14/14)
