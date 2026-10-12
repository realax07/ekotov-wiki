# Чеклист проверок: add-wiki

Change-пакет: `openspec/changes/add-wiki/` — P15 «Wiki-функционал»
(монолит: дерево страниц по parent_id, breadcrumb, WYSIWYG-редактор на
contenteditable (vanilla, ОГР-8), изображения через images-сервис, LIKE-поиск,
полная история версий с откатом, общие права owner/wife): FR-107…FR-116;
NFR-30 (перф p95 < 300/500 мс), NFR-31 (санитизация по whitelist),
NFR-32 (миграция идемпотентно + репетиция на копии прод-БД), NFR-33
(vanilla + токены V3 «Бумага», Chrome+Firefox), NFR-34 (лимиты images
переиспользованы); дельта navigation MODIFIED — раздел «Wiki» перестает быть
заглушкой (снятие Won't FR-13). ТЗ для сверки: requirements.md пакета,
design.md §1–§7, дельты `specs/{wiki,navigation}`, утвержденные мокапы
`design/wiki-{tree,page,editor,history}.html` (утверждены Заказчиком до
dev-волн, 1.1).
Статус реализации: волны 1–4 влиты в ветку `pipeline/p15-stage-a` (волна 3 =
6fdc36c, HEAD прогонов 91658ec/a374381); QA 4.1–4.4 прогнаны — api 62p +
регресс 274p/0f + NFR-30 все цели с запасом ×3–10
(REPORT-4.1-api.md), web-desktop 29p + DV-контроль 14/14
(REPORT-4.2-web-desktop.md), web-mobile 12/12 после фикса BUG-017
(REPORT-4.3-web-mobile.md), смок 16/16 + репетиция миграции на прод-снапшоте
ОК×2 + кроссбраузерность 16/16 × 2 браузера (REPORT-4.4-smoke.md);
DV review-001-design.md — СООТВЕТСТВУЕТ (0 blocker; major DV-1 исправлен и
подтвержден в 4.1/4.2; minor DV-2…DV-6 — правки на месте по DV-контролю 4.2).
Вход 4.5: боевая накатка migrate_wiki разрешена (REPORT-4.4 §(а)).

Типы: **поз.** — позитивная, **нег.** — негативная, **гран.** — граничное
значение, **НФТ** — нефункциональная, **сред.** — средовое предусловие
(стенд/корпус/браузер).
Покрытие: колонка «Автотест» — конкретная привязка к автотесту
(`tests/web/test_p15_wiki_*.py::test_*` — TC-wiki-001…309; `tests/api/
test_wiki_api.py::test_*`, `tests/api/test_sanitize.py::test_*` — TC-wiki-4xx;
реестр в шапках web-файлов). Для перф/миграции/кроссбраузерности/смока
автотеста в сьютах нет — замеры выполнялись разовыми скриптами прогонов;
честная пометка: «автотеста нет — прогон 4.x REPORT-<N> (скрипт)». Факт
прогона: «4.1 api» — REPORT-4.1 (wiki-сьют 27p + sanitize 35p; регресс ядра
274p/0f; перф-корпус 1000 страниц / 10 000 версий, p95 20 повторов); «4.2
desktop» — REPORT-4.2 (wiki-сьют 29p ≥1024px; DV-контроль 14/14, скриншоты
screenshots-42); «4.3 mobile» — REPORT-4.3 (375×812 touch, 12/12 после фикса
BUG-017, скриншоты screenshots-43); «4.4 смок» — REPORT-4.4 (compose.test
:8443, 16/16; репетиция на прод-снапшоте; Chromium 153 + Firefox 155); «DV» —
design_validator review-001-design.md (мокапы wiki-tree/page/editor/history);
«4.5» — живая приемка Заказчика на проде (план, только с Заказчиком,
протокол обязателен).

## Навигация: раздел «Wiki» перестает быть заглушкой (navigation MODIFIED, FR-13 → FR-107)

| ID | Источник | Проверка | Тип | Приоритет | Автотест | Покрытие |
|---|---|---|---|---|---|---|
| CHK-wiki-1 | navigation Requirement: Пустой раздел Wiki с пометкой todo (MODIFIED, FR-13/FR-107) / Сценарии: «Раздел Wiki отображается как заглушка» (инвертирован), «Переход в Wiki через сайдбар», «Пункт Wiki в существующем порядке сайдбара», «Неавторизованный доступ к Wiki» | пункт «Wiki» присутствует в сайдбаре без пометки «todo», третий по порядку (Доска, Поиск, Wiki, Галерея — FR-85), ведет на рабочую `/wiki` (список корневых страниц); анонимно `/wiki` → 302 /login; существующие разделы и блок профиля работают без изменений | поз. | Must | tests/api/test_navigation.py::test_wiki_page_scaffold_no_todo_stub | 4.2 desktop (§3.3: test_nav_order_addresses_states_unchanged passed, скрин 01-tree.png) + 4.4 смок (п.7: 302 → /login) |
| CHK-wiki-2 | navigation Requirement: Пустой раздел Wiki с пометкой todo (MODIFIED, FR-13/FR-107) / Сценарий: «Раздел Wiki не дает wiki-функций» (инвертирован, FR-108…FR-114) | из раздела доступны создание/редактирование страниц, история версий и поиск — прежний Won't («функции отсутствуют») снят | поз. | Must | tests/api/test_wiki_api.py (смок-маршрут CRUD на живом API) | 4.4 смок (пп. 8–14: /wiki 200 у owner и wife, создание 201, правка 200+версия, поиск 200, откат = новая запись) |

## Дерево страниц Wiki (wiki ADDED, FR-107)

| ID | Источник | Проверка | Тип | Приоритет | Автотест | Покрытие |
|---|---|---|---|---|---|---|
| CHK-wiki-3 | wiki Requirement: Дерево страниц Wiki / Сценарии: «Открытие /wiki со страницами», «Раскрытие и сворачивание узлов» | `/wiki` без параметров показывает список корневых (`parent_id = NULL`) с поддеревьями; вложенность 3+ уровней строится за один GET /api/wiki/pages, узлы раскрываются/сворачиваются (aria-expanded, шеврон) без ограничения глубины | поз. | Must | tests/web/test_p15_wiki_tree.py::test_wiki_tree_three_levels_build_and_collapse (TC-wiki-001) | 4.2 desktop (29p, DV-контроль «дерево 3 уровней») + 4.3 mobile (п.1: шеврон visible→hidden→visible) + DV (01-tree.png, 01b) |
| CHK-wiki-4 | wiki Requirement: Дерево страниц Wiki / Сценарий: «Пустое состояние» | при отсутствии страниц — пустое состояние `.wiki-empty` («В Wiki пока нет страниц») с кнопкой создания первой страницы; отдельная «главная страница» wiki не введена (ОВ-4) | поз./гран. | Must | tests/web/test_p15_wiki_tree.py::test_wiki_empty_state_create_first_page, ::test_wiki_empty_state_button_opens_editor, ::test_wiki_toolbar_create_button_opens_editor (TC-wiki-004/005/006) | 4.2 desktop + DV (13-empty-state.png) |
| CHK-wiki-5 | wiki Requirement: Дерево страниц Wiki / design §7 (NFR-33) | раскладка: `.wiki-layout` 280px + контент на desktop; ≤480px — одна колонка, дерево сверху | поз./НФТ | Must | tests/web/test_p15_wiki_tree.py::test_wiki_layout_desktop_280_and_mobile_one_column (TC-wiki-007) | 4.2 desktop + 4.3 mobile (п.1: treeTop=72, одна колонка 343px) + DV (11-tree-470.png) |

## Поиск по wiki (wiki ADDED, FR-114)

| ID | Источник | Проверка | Тип | Приоритет | Автотест | Покрытие |
|---|---|---|---|---|---|---|
| CHK-wiki-6 | wiki Requirement: Поиск по wiki / Сценарий: «Поиск находит по заголовку и тексту» | LIKE-поиск по заголовку И тексту; результат — заголовок, путь в иерархии, фрагмент с подсветкой `<mark>` (инверсная amber); счетчик «Найдено: N» | поз. | Must | tests/web/test_p15_wiki_tree.py::test_wiki_search_title_and_snippet_mark (TC-wiki-002) + tests/api/test_wiki_api.py::test_search_finds_title_and_content | 4.2 desktop + 4.3 mobile (п.4a: mark='версия три', «Найдено: 1») + DV (02-search.png) |
| CHK-wiki-7 | wiki Requirement: Поиск по wiki / Сценарии: «Поиск не затрагивает версии», «Поиск без совпадений» | поиск только по текущему контенту (ОВ-3) — подстрока из старой версии не находится; пустой запрос — пустой результат без ошибок; LIMIT 20; экранирование `%`/`_`/`\` (ESCAPE-паттерн) | нег./гран. | Must | tests/web/test_p15_wiki_tree.py::test_wiki_search_no_results (TC-wiki-003) + tests/api/test_wiki_api.py::test_search_escapes_like_wildcards, ::test_search_limit_20 | 4.1 api (27p: не по версиям, ESCAPE-паттерн) |
| CHK-wiki-8 | wiki Requirement: Поиск по wiki / DV-1 review-001 (major, исправлен) | сниппет — plain-текст без HTML-тегов (фикс DV-1: сервер режет теги до сниппета, оффсет в plain-координатах) | нег. | Must | tests/api/test_wiki_api.py::test_search_snippet_plain_text_no_tags | 4.1 api (passed) + 4.2 desktop (DV-контроль DV-1 OK, 03-search.png) |

## Статья: создание, breadcrumb, удаление (wiki ADDED, FR-108, FR-109, FR-116)

| ID | Источник | Проверка | Тип | Приоритет | Автотест | Покрытие |
|---|---|---|---|---|---|---|
| CHK-wiki-9 | wiki Requirement: Создание страницы Wiki / Сценарии: «Создание корневой страницы», «Создание вложенной страницы» | страница с непустым заголовком и контентом создается корневой или дочерней к выбранному родителю и появляется в дереве на выбранном месте; `?create=1` → POST /api/wiki/pages → редирект на статью | поз. | Must | tests/web/test_p15_wiki_editor.py::test_save_create_posts_and_redirects (TC-wiki-307) + tests/api/test_wiki_api.py::test_create_page_with_valid_parent, ::test_create_page_bad_parent_422 | 4.2 desktop (29p) + 4.4 смок (п.10: 201) |
| CHK-wiki-10 | wiki Requirement: Создание страницы Wiki / Сценарий: «Пустой заголовок отклоняется» | пустой заголовок отклоняется с ошибкой формы без запроса к API (баннер «Заголовок не может быть пустым…» по мокапу); страница не создается | нег. | Must | tests/web/test_p15_wiki_editor.py::test_empty_title_error_no_request (TC-wiki-309) + tests/api/test_wiki_api.py::test_create_page_empty_title_422 | 4.2 desktop (DV-6) + DV (06-editor-error.png); 4.1 api (422) |
| CHK-wiki-11 | wiki Requirement: Breadcrumb на странице статьи / Сценарий: «Полная цепочка предков» | на странице статьи цепочка предков от корня до текущей: все элементы кликабельны, текущая — `aria-current="page"` без ссылки; на 375px цепочка 5 уровней переносится flex-wrap без развала и без X-прокрутки | поз./гран. | Must | tests/web/test_p15_wiki_page.py::test_breadcrumb_four_levels_links_and_current (TC-wiki-101) + tests/api/test_wiki_api.py::test_breadcrumb_deep_chain | 4.2 desktop + 4.3 mobile (п.2: 5 элементов, flex-wrap=wrap) + DV (03-article.png, 03-wiki-article-long-breadcrumb-375.png) |
| CHK-wiki-12 | wiki Requirement: Breadcrumb / Сценарий: «Breadcrumb корневой страницы» | breadcrumb корневой страницы — один элемент (текущая, без ссылки на себя) | гран. | Must | tests/web/test_p15_wiki_page.py::test_breadcrumb_root_single_item (TC-wiki-102) | 4.2 desktop |
| CHK-wiki-13 | wiki Requirement: Удаление страницы / Сценарий: «Удаление листовой страницы» | удаление листа после подтверждения (диалог «Удалить страницу?» по мокапу, фокус на «Отмена»): страница исчезает из дерева; файлы изображений в галерее остаются (в контенте только ссылки /images/{id}) | поз. | Should | tests/web/test_p15_wiki_page.py::test_delete_confirm_dialog_and_redirect (TC-wiki-104) + tests/api/test_wiki_api.py::test_delete_leaf_removes_versions | 4.2 desktop (DELETE → редирект, версии CASCADE) + 4.1 api |
| CHK-wiki-14 | wiki Requirement: Удаление страницы / Сценарий: «Удаление страницы с дочерними запрещено» (дефолт ОВ-2) | попытка удалить страницу с дочерними → 409, баннер role=alert «Страницу удалить нельзя: у неё есть дочерние страницы…», страница и поддерево остаются; кнопка «Удалить» скрыта при can_delete=false | нег. | Should | tests/web/test_p15_wiki_page.py::test_delete_conflict_409_banner_page_stays (TC-wiki-105), ::test_actions_visible_and_delete_gated_by_can_delete (TC-wiki-103) + tests/api/test_wiki_api.py::test_delete_with_children_409, ::test_get_page_can_delete_leaf_vs_parent | 4.2 desktop + DV (04-delete-dialog.png, 14-409-banner.png); 4.1 api (409) |

## WYSIWYG-редактор и изображения (wiki ADDED, FR-110, FR-111, NFR-34)

| ID | Источник | Проверка | Тип | Приоритет | Автотест | Покрытие |
|---|---|---|---|---|---|---|
| CHK-wiki-15 | wiki Requirement: WYSIWYG-редактор страниц / Сценарий: «Тулбар применяет форматирование» | тулбар H1–H3, B/I/U, ul/ol, цитата, код-блок, ссылка, таблица — форматирование применяется к выделению; сохраненная страница отображает тот же вид (WYSIWYG); сохранение POST/PUT → редирект на статью | поз. | Must | tests/web/test_p15_wiki_editor.py::test_toolbar_formats_change_tags, ::test_toolbar_inserts_table_3x3 (TC-wiki-301/303) + tests/api/test_sanitize.py::test_toolbar_markup_passes, ::test_full_toolbar_document_roundtrip | 4.4 кроссбраузер (B/I/U/ul/table в DOM после save — оба браузера) + DV (05-editor.png) |
| CHK-wiki-16 | wiki Requirement: WYSIWYG-редактор / Сценарий: «Undo/redo» | undo/redo тулбара отменяют/повторяют правку (нативный contenteditable + кнопки) | поз. | Must | tests/web/test_p15_wiki_editor.py::test_toolbar_lists_and_undo_redo (TC-wiki-302) | 4.2 desktop + DV (04-editor.png, DV-4 title с хоткеями) |
| CHK-wiki-17 | wiki Requirement: WYSIWYG-редактор / Сценарий: «Редактор без внешних зависимостей» | сетевых запросов к внешним CDN/доменам нет — редактор целиком на локальной статике (vanilla JS, ОГР-8) | нег./НФТ | Must | автотеста нет — прогон 4.4 REPORT-4.4 §(в) (скрипт /tmp/t44/crossbrowser.py, pageerror-счет) | 4.4 кроссбраузер (0 JS-ошибок) + DV (токены: grep `#hex` в wiki.css пуст) |
| CHK-wiki-18 | wiki Requirement: WYSIWYG-редактор / Сценарий «Тулбар…» (безопасность, design §4) | `javascript:`-URL в диалоге ссылки отклоняется (URL-фильтр sanitizer) | нег. | Must | tests/web/test_p15_wiki_editor.py::test_link_javascript_scheme_rejected (TC-wiki-304) + tests/api/test_sanitize.py::test_javascript_href_removed_with_attribute, ::test_mixed_case_and_obfuscated_scheme | 4.2 desktop + 4.1 api |
| CHK-wiki-19 | wiki Requirement: Изображения в контенте / Сценарии: «Вставка изображения из галереи», «Загрузка изображения с диска» | диалог «Вставить изображение» с радио «Из галереи»/«Загрузить с диска»: галерея через GET /api/images, диск через существующий POST /api/images; в контенте ссылка `/images/{id}`, файлы в БД wiki не дублируются | поз. | Must | tests/web/test_p15_wiki_editor.py::test_image_insert_from_gallery, ::test_image_insert_from_disk_uploads_and_inserts (TC-wiki-305/306) | 4.2 desktop + DV (05c, 06-image-dialog.png); 4.4 смок (п.3: images-сервис жив) |
| CHK-wiki-20 | wiki Requirement: Изображения в контенте / Сценарий: «Нарушение лимитов загрузки» (NFR-34) | лимиты переиспользованы от images-сервиса (≤10 МБ, JPEG/PNG/GIF/WebP): нарушение → 422, в контент ничего не вставляется, человекочитаемая ошибка (DV-8) | нег./гран. | Should | tests/web/test_p15_wiki_editor.py::test_image_insert_from_disk_uploads_and_inserts (TC-wiki-306, happy-path диска); 422-ветка NFR-34: автотеста нет — прогон 4.2 REPORT-4.2 §4 DV-8 (скрин) | 4.2 desktop (DV-8: «Не удалось загрузить данные (HTTP 404).») + 4.1 api (лимиты NFR-21 через NFR-34, images-сервис) |

## Редактирование с записью версии, история и откат (wiki ADDED, FR-112, FR-113)

| ID | Источник | Проверка | Тип | Приоритет | Автотест | Покрытие |
|---|---|---|---|---|---|---|
| CHK-wiki-21 | wiki Requirement: Редактирование страницы с записью версии / Сценарий: «Сохранение правки создает версию» | каждое сохранение (заголовок и/или контент) создает запись в page_versions: контент, автор сессии, время; PUT → бамп updated_at | поз. | Must | tests/web/test_p15_wiki_editor.py::test_save_edit_puts_new_version_and_redirects (TC-wiki-308) + tests/api/test_wiki_api.py::test_update_creates_version_and_bumps_updated_at, ::test_update_title_only_keeps_content | 4.2 desktop + 4.1 api + 4.4 смок (п.11: versions 1→2) |
| CHK-wiki-22 | wiki Requirement: Редактирование с записью версии / Сценарий: «История полная» | страницу правили разные пользователи — в истории все правки с авторами и временем, ни одна не потеряна | поз. | Must | tests/web/test_p15_wiki_history.py::test_history_list_newest_first_with_author_and_datetime (TC-wiki-202) | 4.2 desktop + 4.1 api (паритет-смок: история 3 записи) |
| CHK-wiki-23 | wiki Requirement: История версий и откат / Сценарии: «Список версий от новых к старым», «Просмотр версии read-only» | история: автор, дата-время, от новых к старым; «Смотреть» → read-only с плашкой «только чтение»; у текущей версии пилюля «текущая» и нет кнопки «Откатить» | поз. | Must | tests/web/test_p15_wiki_history.py::test_history_list_newest_first_with_author_and_datetime, ::test_version_view_readonly, ::test_current_pill_on_latest_no_revert_button (TC-wiki-202/204/203) + tests/api/test_wiki_api.py::test_versions_list_newest_first_without_content, ::test_get_version_content_and_foreign_version_404 | 4.2 desktop + DV (07-history.png) |
| CHK-wiki-24 | wiki Requirement: История версий и откат / Сценарий: «Откат создает новую версию» (решение 6) | откат к V1 при V1–V3: контент = V1, создается НОВАЯ запись V4; V1–V3 не переписаны и не удалены; диалог подтверждения + success-баннер по мокапу | поз./гран. | Must | tests/web/test_p15_wiki_history.py::test_revert_confirm_dialog_cancel, ::test_revert_creates_new_version_updates_list (TC-wiki-205/206) + tests/api/test_wiki_api.py::test_revert_creates_new_version_not_rewrite, ::test_revert_sanitizes_stored_content | 4.2 desktop + 4.1 api + 4.4 смок (п.13: new_version_id=3, история растущая) + DV (08, 15) |
| CHK-wiki-25 | wiki Requirement: История версий и откат / мокап wiki-history (NFR-33) | раскладка истории: две колонки (minmax(300px,360px) + 1fr) на desktop; ≤880px складывается в одну без X-прокрутки | поз./НФТ | Must | tests/web/test_p15_wiki_history.py::test_history_layout_collapses_narrow (TC-wiki-207) | 4.2 desktop + 4.3 mobile (п.4b: columns='343px') + DV (09/10) |

## Права доступа (wiki ADDED, FR-115)

| ID | Источник | Проверка | Тип | Приоритет | Автотест | Покрытие |
|---|---|---|---|---|---|---|
| CHK-wiki-26 | wiki Requirement: Права доступа к wiki / Сценарий: «Паритет owner и wife» (решение 7) | owner и wife одинаково читают, создают, редактируют страницы и работают с версиями — разделения прав нет; wife правит страницу владельца → версия с её author_id | поз. | Must | tests/api/test_wiki_api.py::test_all_endpoints_require_session (401-гейт); двухсессионный паритет в сьютах не автоматизирован — смок-скрипт прогона | 4.1 api (паритет-смок: жена правит страницу владельца, author_id=2) + 4.4 смок (пп. 6, 9, 14: /wiki 200 и PUT 200 у wife) |
| CHK-wiki-27 | wiki Requirement: Права доступа / Сценарии: «Анонимный доступ к странице», «Анонимный вызов API» | анонимно: GET /wiki и /wiki/{id} → 302 /login (middleware); любой из 9 wiki-API-методов → 401 | нег. | Must | tests/api/test_wiki_api.py::test_all_endpoints_require_session + tests/web/test_p15_wiki_history.py::test_history_page_requires_session (TC-wiki-201) | 4.1 api + 4.4 смок (пп. 7, 15) |

## Производительность, санитизация, миграция (wiki ADDED, NFR-30, NFR-31, NFR-32)

| ID | Источник | Проверка | Тип | Приоритет | Автотест | Покрытие |
|---|---|---|---|---|---|---|
| CHK-wiki-28 | wiki Requirement: Производительность wiki-API / Сценарий: «Пороги на эталонном корпусе» (NFR-30) | на корпусе 1000 страниц / 10 000 версий p95: открытие/дерево/версии < 300 мс, поиск < 500 мс. Факт: открытие 26–38 мс, дерево 42–70 мс, версии 20–87 мс, поиск 32–110 мс (worst-case «нет совпадений») — запас ×3–10 | поз./НФТ | Must | автотеста нет — прогон 4.1 REPORT-4.1 §4 (скрипт-сеялка /tmp/qa41_perf_seed.py + замер p95, 20 повторов × 2 круга) | 4.1 api §4 (значения стабильны) |
| CHK-wiki-29 | wiki Requirement: Санитизация HTML контента / Сценарий: «Скрипт вырезается при отображении» (NFR-31) | серверная санитизация по whitelist: script/style с содержимым, on*-атрибуты, javascript:-URL, iframe, вложенная мутация `<scr<script>ipt>` — вырезаны до рендера; санитизация на записи (create) и при откате (revert) | нег. | Must | tests/api/test_sanitize.py::test_script_tag_removed_with_content, ::test_style_tag_removed_with_content, ::test_onclick_attribute_stripped, ::test_event_handler_img_onerror, ::test_nested_mutation_scr_script_ipt, ::test_iframe_unwrapped_content_kept + tests/api/test_wiki_api.py::test_create_sanitizes_content, ::test_revert_sanitizes_stored_content | 4.1 api (sanitize 35p) |
| CHK-wiki-30 | wiki Requirement: Санитизация HTML / Сценарий: «Разрешенные теги проходят» | вся whitelist-разметка тулбара (H1–H3, B/I/U, ul/ol, цитата, код-блок, ссылка, таблица, изображение; URL-фильтр http/https/относительные) проходит без искажений | поз. | Must | tests/api/test_sanitize.py::test_toolbar_markup_passes, ::test_full_toolbar_document_roundtrip, ::test_data_image_src_allowed_for_img, ::test_plain_text_passthrough_and_escaping | 4.1 api (sanitize 35p) |
| CHK-wiki-31 | wiki Requirement: Миграция таблиц pages и page_versions / Сценарии: «Повторный запуск миграции», «Репетиция на копии прод-БД» (NFR-32) | migrate_wiki по паттерну migrate_gallery: накатка на копию прод-БД — ОК (2 таблицы + 3 индекса, сверка ОК, integrity ok, 0 расхождений по 13 старым таблицам); повторный запуск — no-op (created=0), сверка зеленая, exit 0; все DDL в одной транзакции BEGIN IMMEDIATE | поз./НФТ | Must | автотеста нет — прогон 4.4 REPORT-4.4 §(а) (скрипт `python -m app.migrate_wiki` на прод-снапшоте, 2 прогона) | 4.4 смок §(а) (репетиция на ФАКТИЧЕСКОМ прод-снапшоте, ОК×2; боевая накатка разрешена) |

## Кроссбраузерность, mobile и регресс (wiki ADDED, NFR-33; преемственность NFR-23/26)

| ID | Источник | Проверка | Тип | Приоритет | Автотест | Покрытие |
|---|---|---|---|---|---|---|
| CHK-wiki-32 | wiki Requirement: Фронтенд wiki без внешних зависимостей / Сценарий: «Токены вместо хардкода» (NFR-33) | цвета/отступы wiki-страниц — из переменных `app.css :root` (V3 «Бумага»), хардкода цветов нет; допустимые исключения зафиксированы дизайнером (color-mix бэкдропы, инверсная mark) | поз./НФТ | Must | автотеста нет — DV-инспекция review-001-design (grep `#hex` по wiki.css) | DV review-001 (grep `#hex` пуст) |
| CHK-wiki-33 | wiki Requirement: Фронтенд wiki без внешних зависимостей / Сценарий: «Кроссбраузерность редактора» (NFR-33) | базовые операции редактора (ввод, тулбар B/I/U/список/таблица, диалог изображения, сохранение, повторная правка) работают в актуальных Chrome (Chromium 153) и Firefox 155; 0 JS-ошибок — 16/16 операций на браузер | поз./сред. | Must | автотеста нет — прогон 4.4 REPORT-4.4 §(в) (скрипт /tmp/t44/crossbrowser.py) | 4.4 смок §(в) |
| CHK-wiki-34 | tasks 4.3 (преемственность NFR-23) / design §7 | редактор на 375×812: тулбар в вьюпорте, все кнопки тулбара и футера ≥44×44 (BUG-017 «Сохранить»/«Отмена» 33px — исправлен: 86×44 / 111×44; регресса от фикса нет) | поз./НФТ | Must | автотеста нет — прогон 4.3 REPORT-4.3 (скриптовый boundingBox-замер 375×812 + ре-проба фикса) | 4.3 mobile (12/12 после фикса; до фикса 11/12) |
| CHK-wiki-35 | tasks 4.3 (преемственность NFR-26) / design §7 | на 375px нет горизонтальной прокрутки страницы на всех 4 wiki-экранах (дерево/статья/редактор/история: scrollWidth=clientWidth=375) | поз./НФТ | Must | автотеста нет — прогон 4.3 REPORT-4.3 (скриптовый scrollWidth-замер, п.5 чек-листа) | 4.3 mobile (п.5) |
| CHK-wiki-36 | wiki Requirement: Производительность wiki-API / Санитизация HTML / Права доступа (NFR-30/31, FR-107–FR-115) + tasks 4.2(б)/4.3 (регресс, NFR-преемственность NFR-23/26) | wiki не сломал существующее: полный API-регресс ядра 274p/0f; desktop-регресс 193p (14 фейлов квалифицированы как не-волна-3: baseline dec22a6 + точечные перегоны); смоук доски/поиска/галереи/drawer на 375px — PASS; сайдбар-инварианты (порядок, активный раздел) — прежние | поз. | Must | tests/api/ (полный регресс-сьют, без wiki-файлов) + tests/web/ (desktop-регресс, 38 файлов); 375px-смок — автотеста нет — прогон 4.3 REPORT-4.3 (пп. 6a–6d, скрипт) | 4.1 api §3 + 4.2 desktop §3 + 4.3 mobile (пп. 6a–6d) |

## Живая приемка Заказчика (4.5) — план

| ID | Источник | Проверка | Тип | Приоритет | Автотест | Покрытие |
|---|---|---|---|---|---|---|
| CHK-wiki-37 | tasks 4.5 / wiki Requirements FR-107–FR-116 + NFR-30…NFR-33 (критерий приемки requirements §1) | живая приемка Заказчика на проде после боевой накатки migrate_wiki (вход: зеленая репетиция 4.4) и деплоя (кеш-бастинг `?v=` бамп): создать страницу, отредактировать в WYSIWYG с изображением из галереи, найти поиском, откатить версию; смоук прода (/wiki под сессией, 401/редирект без). Только с явным участием Заказчика; протокол приемки обязателен. Откат: предыдущий тег (новые таблицы старый код не читает) | поз./сред. | Must | автотеста нет — ручная приемка; смоук-часть на проде — скриптовый прогон по образцу 4.4 | **план 4.5** (не прогонялось; все автоматизируемые предпосылки зеленые — 4.1–4.4) |

## Дефекты спеки

- Не найдены. Дельты спек соответствуют реализации; DV review-001: СООТВЕТСТВУЕТ,
  0 blocker. Найденные в QA отклонения — не дефекты спеки, а правки реализации:
  DV-1 (сниппет с HTML-тегами, major) — исправлен, подтвержден в 4.1
  (test_search_snippet_plain_text_no_tags) и 4.2 (DV-контроль 14/14);
  BUG-017 (тач-таргеты футера редактора 33px < 44px, NFR-23) — исправлен
  (min-height:44px в media ≤480px), ре-проба 4.3 подтвердила 12/12.
- Вне-спековые хвосты (не дефекты пакета): navigation wiki-stub тест
  семантически устарел (ожидает заглушку Этапа A — обновить в 6.1); flaky-хвост
  desktop-регресса (bug014, settings_link, comment_gap, combobox,
  gallery/lightbox-загрязнение tmp-БД) — воспроизводится на baseline dec22a6;
  compose.test-стенд требует явных migrate_gallery+migrate_wiki в seed
  (замечание RUNBOOK, не блокер прода).
