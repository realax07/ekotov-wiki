# TC-wiki-412 — Создание страницы Wiki: корневая/вложенная, пустой заголовок отклоняется (FR-108)

- **Change:** add-wiki
- **Источник:** wiki (ADDED): Requirement «Создание страницы Wiki» (FR-108) — Scenario «Создание корневой страницы», «Создание вложенной страницы», «Пустой заголовок отклоняется»; design §3, §5; CHK-wiki-9, CHK-wiki-10
- **Тип:** ФТ, позитив + негатив | **Приоритет:** Must
- **Предусловия:** авторизованный пользователь; в дереве есть страница-родитель для кейса вложенного создания
- **Шаги:**
  1. `?create=1`: заполнить заголовок + контент, выбрать «Без родителя (корень раздела)» → «Сохранить» → POST /api/wiki/pages → редирект на статью; страница — в дереве на верхнем уровне.
  2. Повторить с выбором родителя → страница дочерняя, в дереве внутри поддерева родителя.
  3. API-негативы: POST без title и с пустым title → 422; несуществующий parent_id → 422; страница не создается.
  4. UI-негатив: пустой заголовок + «Сохранить» → баннер «Заголовок не может быть пустым…» (role=alert, под h1 — DV-6) БЕЗ запроса к API.
- **Ожидаемый результат:** создание корневой и вложенной страницы работает, страница появляется в дереве на выбранном месте; пустой/отсутствующий заголовок и битый parent отклоняются (422 / ошибка формы без создания). Факт прогона 4.1: green (test_create_page_* — passed из 27); 4.2 desktop: green (TC-wiki-307/309; DV-6 OK, 05-editor-error.png); 4.4 смок п.10 — 201.
- **Автотест:** tests/web/test_p15_wiki_editor.py::test_save_create_posts_and_redirects (TC-wiki-307), ::test_empty_title_error_no_request (TC-wiki-309) + tests/api/test_wiki_api.py::test_create_page_returns_201, ::test_create_page_empty_title_422, ::test_create_page_missing_title_422, ::test_create_page_bad_parent_422, ::test_create_page_with_valid_parent
- **Статус:** **approved** (QA 4.1: 27 API passed / 0 failed; QA 4.2: 29 passed / 0 failed)
