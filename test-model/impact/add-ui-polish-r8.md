# Impact-анализ: change add-ui-polish-r8

> Дата: 2026-10-06 | Режим: прогнозный impact (задача 3.1 шаг 1,
> qa_impact_analyst; полный регресс 3.1 на стенде еще не прогнан — вердикты
> по существующим наборам даны априори по дельтам и прецеденту
> add-gallery-service). Вход: дельты `openspec/changes/add-ui-polish-r8/specs/`
> (board MODIFIED, tasks MODIFIED ×2, navigation MODIFIED+ADDED, gallery
> MODIFIED+ADDED), requirements.md (FR-87…FR-98, NFR-22), design.md,
> tasks.md §ЭТАП A (волны 2.1–2.7), прецедент
> `test-model/impact/add-gallery-service.md`, манифест регресса.
>
> Волны, чьи дельты анализируются: 2.1 (fastline+кнопки+настройки, FR-87/88/
> 93/96 — в main), 2.2 (#51, модалка, FR-90), 2.3 (#49, комментарии+combobox,
> FR-91/92), 2.4 (сайдбар+favicon, FR-94/95 — в main), 2.5
> (feature/p12-25-gallery-rename, FR-97), 2.6 (#52, masonry, FR-98),
> 2.7 (#53, fastline-edit, FR-89).

## Характер дельты

- **MODIFIED — board «Просмотр карточки задачи» (FR-90):** окно просмотра
  по утвержденному мокапу (дизайн-фаза); read-only семантика, кнопка
  «Редактировать», закрытие — сохраняются; DOM-id не переименовываются
  (ОГР-28, `#task-detail-attrs` и др. на месте); шапка комментария
  «автор · дата» (преемственность FR-91).
- **MODIFIED — tasks «Признаки задачи» (FR-91):** шапка комментария — имя
  автора (join users, `author_name` добавляется в ответ GET списка) и
  человекочитаемая дата/время вместо id и сырого timestamp; контракт POST
  комментария MUST NOT меняться.
- **MODIFIED — tasks «Кастомный комбобокс тегов» (FR-92):** после выбора или
  создания тега текст поля ввода ОБЯЗАТЕЛЬНО убирается (остается чип);
  множественное добавление и удаление по одному — работают; NFR-17/18
  сохраняются.
- **MODIFIED — navigation «Навигация через сайдбар» (FR-94):** inline-SVG
  иконки у всех разделов (доска, поиск, wiki, настройки), эталон — иконка
  «Мониторинг»; порядок/адреса/состояния MUST NOT меняться.
- **ADDED — navigation «Favicon» (FR-95):** inline-SVG data-URI в base.html,
  URL с cache-busting `?v=`.
- **MODIFIED — gallery «Full-screen просмотр» (FR-97):** переименование
  original_name операцией `PUT /api/images/{id}/name` (200/401/404/422),
  форма в лайтбоксе, обновление сетки/лайтбокса без перезагрузки; физические
  файлы и `/images/…` не меняются.
- **ADDED — gallery «Сетка галереи держит ритм» (FR-98):** вариант «В
  masonry» (решение Заказчика); ячейки выровнены, адаптив 2/3/4 колонки
  сохраняется.
- **FR-87/88/89/93/96 и NFR-22 — дельты спеки НЕ имеют** (fastline-инварианты
  и стиль кнопок вне спеки; design §2). Тестовые последствия — по tasks.md
  волн 2.1/2.7: (а) класс `has-fast` на СТОЛБЦЕ убирается — подсветка
  только плитки `.task-card-fast`; (б) блок `.fast-row` формы создания по
  макету V3; (в) fastline в форме редактирования — ряд с текущим is_fast
  (сейчас `.fast-row` скрыт в редактировании); (г) кнопка настроек без
  смещения текста; (д) кнопки поиска/галереи — единый класс токенов V3.
- **REMOVED — нет.**

## Известные пред-существующие проблемы (НЕ дельты пакета)

Помечены отдельно, чтобы 3.1 не смешивала их с новыми падениями:

1. **tests/web/test_r6_tag_combobox_ui.py — красные на автостенде** (стенд
   tests/web: http.server вместо nginx + полный compose): сьют гонялся на
   nginx-стенде :18443; на автостенде — пред-существующие environment-фейлы,
   к волнам 2.3 отношения не имеют (вердикты ниже — по семантике ассертов).
2. **6 фейлов test_tasks KeyError `results`** — тесты `tests/api/test_tasks.py`
   падают на `api.search(...).json()["results"]` (среда/стенд без
   search-маршрута или пустой ответ) — пред-существующее средовое, не дельта.
3. **advanced-search 404** — режим advanced на автостенде отвечает 404
   (маршрутизация search): затрагивает TC-search-r4-ui-004 и шаги advanced в
   TC-view-109 — прогонять на маршрутизированном стенде.
4. **bare-стенд без search/images** — сьюты галереи
   (test_qa21_gallery_api/design/ui, TC-GAL-115…122) на голом app-стенде
   честно SKIP с причиной либо падают connection-error'ом; нужен
   nginx-стенд с images :8379 (прецедент QA 2.1).
5. **openapi /gallery контракт** — `services/images/tests/
   test_images_service.py::test_openapi_paths` фиксирует точное множество
   маршрутов БЕЗ `/api/images/{id}/name`; после волны 2.5 ассерт устареет
   гарантированно (см. update ниже).

## Таблица вердиктов

### Волна 2.1 — fastline+кнопки+настройки (FR-87/88/93/96)

| Тест | Вердикт | Обоснование |
|---|---|---|
| tests/web/test_fastline_ui.py::test_fast_task_create_and_highlight (TC-UI-010) | **update** | **Строка 42** `assert "has-fast" in todo.get_attribute("class")` — ассертит окраску СТОЛБЦА, которую FR-87 убирает. Заменить на ОБРАТНЫЙ: `assert "has-fast" not in todo.get_attribute("class")` (столбец НЕ красится) + `assert "task-card-fast" in fast_card.get_attribute("class")` (строка 43, остается). Docstring строк 28–29 («столбец подсвечен») переписать. Остальное (бейдж, first-in-column) не меняется |
| tests/web/test_fastline_ui.py::test_second_fast_task_rejected (TC-UI-011) | **keep** | 409 «fast line занята», форма открыта, поля сохранены — поведение FR-88 сохраняет без изменений |
| tests/web/test_navigation_search_ui.py::test_final_path_autoarchive_and_fast_release (TC-UI-018) | **keep** | Ассертит `task-card-fast` на карточке (строка 233) — подсветка плитки сохраняется; столбец не проверяет |
| tests/api/test_fastline.py (11, TC-fast-001…012) | **keep** | Инварианты fast-спеки (409, high, освобождение) FR-87/88 не ослабляются; UI-пропуски (test_fast_line_visual_highlight/test_fast_task_visual_priority) остаются skip-заглушками скоупа tests/web |
| tests/api/test_fast2.py (12, TC-fast2-001…012) | **keep** | Контракт создания (priority auto-high, 422, 409) волной 2.1 не меняется; блокировка приоритета в форме сохраняется (FR-88) |
| tests/web/test_r3_formv3_ui.py::test_form_fields_v3_tokens_and_focus_ring и прочие 4 | **keep** | Токены/фокус-ринги формы создания не деградируют (NFR-22); FR-88 только приводит .fast-row к макету V3 |
| tests/web/test_search_r4_ui.py (4), test_search_suggestions_ui.py (3) | **keep** | FR-93 меняет ТОЛЬКО стиль кнопки «Найти» (класс/отступы) — поведение фильтров и подсказок не затронуто; локаторы `#search-advanced-submit` и др. не переименовываются (ОГР-28) |
| tests/web/test_settings_categories_ui.py (24) | **keep** | FR-96 (кнопка настроек, active/focus-геометрия) не входит в ассерты сьюта категорий; TC-nav-006/007/008 — позиция/переход, не затронуты волной 2.1 |
| Геометрия TC-nav-006 (test_settings_link_position_bottom_left_near_logout) | **revalidate** | Bbox-ассерты (Y к «Выйти» +32px, X-колонка, «ниже Доски») чувствительны к любым правкам сайдбара/кнопок; иконки 2.4 меняют разметку .nav-item. Перегнать на новой ветке (прецедент review-002-tests: порог +32px эвристический) |

### Волна 2.2 — модалка тикета (FR-90)

| Тест | Вердикт | Обоснование |
|---|---|---|
| tests/web/test_view_modal_r4.py::test_card_click_opens_readonly_view (TC-view-101) | **keep** | `#task-detail-attrs`, read-only (0 input/textarea/select), список комментариев — контракты ОГР-28 не переименовываются; вид по мокапу семантику не меняет |
| tests/web/test_view_modal_r4.py::test_view_has_no_edit_elements (TC-view-102) | **revalidate** | **Строки 125–133:** ассерт точного состава кнопок view `names == ["Редактировать", "Закрыть"]` + крестик. Мокап 2.2 может добавить/переименовать кнопки футера (иконка «Редактировать» и т.п.) — ассерт точного множества хрупок к редизайну. Перегнать на новой ветке; при расхождении с мокапом — update по факту |
| test_edit_button_opens_task_form (TC-view-103) | **keep** | Д-9: «Редактировать» открывает существующую форму — семантика сохранена FR-90 |
| test_escape_closes_view / test_cross_closes_view (TC-view-104/105) | **keep** | Сценарии закрытия сохраняются (Esc/крестик #task-view-close) |
| test_user_rows_when_api_provides / test_unassigned_em_when_empty (TC-view-106/107) | **keep** | assigned/creator-ряды — вне зон волн; гварды остаются |
| test_fast_task_shown_in_view (TC-view-108) | **keep** | Признак «Fast line: да» во view — 2.1 меняет подсветку доски, не view; DOM-id не меняется |
| test_search_card_click_opens_view (TC-view-109) | **keep** | BUG-001-регресс; открыть на маршрутизированном стенде (известная средовая: advanced 404 на автостенде — шаги 319–319 пропустить/стенд) |

### Волна 2.3 — комментарии + combobox (FR-91/92)

| Тест | Вердикт | Обоснование |
|---|---|---|
| tests/web/test_r6_tag_combobox_ui.py::test_combobox_opens_on_focus_and_filters (TC-r6-comb-001) | **keep** | Открытие/фильтрация не меняются (NFR-17) |
| test_combobox_highlights_match_fragment (TC-r6-comb-002) | **keep** | Подсветка <mark> — вне дельты FR-92 |
| test_combobox_excludes_entered_tags (TC-r6-comb-003) | **keep** | Исключение введенных тегов не зависит от сброса поля |
| test_combobox_add_new_tag_item (TC-r6-comb-004) | **update** | **Строка 165** `assert tags.input_value() == " QATсовершенноновый,"` — фиксирует ОСТАЮЩИЙСЯ текст в поле; FR-92 требует пустого поля после создания тега. Заменить на `assert tags.input_value() == ""` + чип с текстом тега (уже ассертится строкой 166). Аналогично пересмотреть строки 227 (`value.startswith(" QATkb")`) |
| test_combobox_keyboard_navigation (TC-r6-comb-005) | **update** | **Строки 227–228:** Enter-выбор ассертит «тег дописан в input» (`value.startswith(" QATkb")`) — после FR-92 поле пустое, чип вместо текста. Заменить на пустой input + `#task-tags-chips .chip` с текстом активного пункта; шаг Tab (строки 236–240: `assert "QATkbнов" in tags.input_value()`) — Tab-путь выбора также оставить текст в поле → заменить на чип-ассерт |
| test_combobox_escape_closes_dropdown_not_form (TC-r6-comb-006) | **update** | **Строки 261–263:** `assert "QATescтег" in tags.input_value()` после Enter-выбора — заменить на пустое поле + чип. Шаги Escape (267–271) не меняются; сохранение формы проходит как прежде |
| test_combobox_aria_attributes (TC-r6-comb-007) | **keep** | NFR-17/18 aria-контракт сохраняется (NFR-22 преемственно) |
| test_combobox_click_outside_closes (TC-r6-comb-008) | **keep** | Клик вне — вне дельты |
| test_combobox_touch_tap_and_load_failure (TC-r6-comb-009) | **update** | **Строка 377** `assert "QATtapтег" in tags.input_value()` после клика по пункту — заменить на пустое поле + чип. Сбой загрузки (383–395) не меняется |
| test_combobox_closes_with_form_no_stuck_dropdown (TC-r6-comb-010) | **keep** | Залипание дропдауна — вне дельты |
| tests/web/test_board_tasks_ui.py::test_add_comment_persists (TC-ui-…) | **keep** | Комментарий создается и виден; FR-91 меняет шапку, не создание |
| tests/web/test_r4_commentfix_ui.py (4, TC-cmt-201…203) | **keep** | Вёрстка блока комментариев в форме редактирования — геометрия блока; шапка комментария (автор·дата) геометрию не ломает, но перегнать вместе с регрессом 3.1 (безопасный дефолт: верстка той же зоны) |
| tests/api/test_comments_author_r8.py (5, НОВЫЙ файл волны 2.3) | **new** | author_name в GET списка, обратная совместимость, контракт POST — появляется на ветке 2.3 (#49); в чеклист 3.1 как обязательный набор на маршрутизированном стенде |
| tests/api/test_tasks.py::test_comment_persists (строка 149) | **keep** | POST-контракт комментария MUST NOT меняться (FR-91) — прямой сторожевой тест |

### Волна 2.4 — сайдбар + favicon (FR-94/95) + фикс сайдбара (viewport)

| Тест | Вердикт | Обоснование |
|---|---|---|
| tests/web/test_qa21_netdata_sidebar_ui.py (6, TC-ADD-201…206) | **keep** | Иконка «Мониторинг» — ЭТАЛОН для FR-94; ассерты svg.nav-icon/polyline/currentColor/16px остаются истинными; порядок «Мониторинг перед Настройками» (строки 105–108) сохраняется (порядок MUST NOT меняться) |
| tests/web/test_auth_ui.py (5, TC-UI-001…005) | **keep** | Сайдбар/редиректы не меняются; favicon и иконки не входят |
| tests/web/test_navigation_search_ui.py::test_sidebar_all_pages_and_wiki_stub (TC-UI-016) | **keep** | Разделы/бейдж todo — состояния сохранены (порядок/адреса MUST NOT) |
| tests/web/test_settings_categories_ui.py TC-nav-006/007/008 | **revalidate** (TC-nav-006) / keep (007/008) | TC-nav-006 — см. выше (геометрия при новых svg-иконках внутри .nav-item: 16px-иконка сдвигает bbox текста; порог |ΔY| < height+32 может мигать). TC-nav-007/008 (переход, наличие) — keep |
| tests/web/test_tooltip_r4.py (8, TC-tip-101…108) | **keep** | Профиль/tooltip — волна 2.4 трогает только .nav-item иконки и favicon; позиция tooltip у нижнего края (TC-tip-104) не зависит. Фикс сайдбара (viewport, #50 в main) уже учтен |
| tests/api/test_navigation.py (5) | **keep** | Маршруты разделов не меняются |
| e2e/test_stand_smoke.py (7) | **keep** | Заголовки/gzip/security/логин-смоук; favicon data-URI не влияет на сетевые контракты; new-проверка favicon — в чеклист 3.1 |

### Волна 2.5 — rename галереи (FR-97)

| Тест | Вердикт | Обоснование |
|---|---|---|
| services/images/tests/test_images_service.py — 27 из 28 (health/401/upload/list/get/reactions/comments/core-tables) | **keep** | Контракты существующих операций не меняются (FR-97 — чистое добавление); core_tables_untouched остается |
| test_openapi_paths (строка 214) | **update** | **Строки 216–223:** точное множество `paths == {...}` без `/api/images/{image_id}/name` — после волны 2.5 ассерт гарантированно устареет. Добавить `"/api/images/{image_id}/name"` в ожидаемое множество (и обновить docstring «ровно маршруты design §3») |
| tests/api/test_qa21_gallery_api.py (18, TC-GAL-107…114) | **keep** | API-контракты upload/фильтры/реакции/комментарии не тронуты rename |
| tests/web/test_qa21_gallery_ui.py::test_tc_gal_116_lightbox_nav_reactions_comment_download | **revalidate** | Лайтбокс получает НОВЫЙ элемент (иконка «переименовать» у имени) — ассерты состава панели действий/списка элементов окна могут отреагировать; перегнать на ветке 2.5 (feature/p12-25-gallery-rename) |
| tests/web/test_qa21_gallery_design.py (2, TC-GAL-122 статика+динамика) | **revalidate** | Токенная дисциплина gallery.css/gallery.js — волна 2.5 добавляет стили/JS rename: 0-литеральный ассерт перегоняется (новые стили обязаны быть на var(--token)); динамическая часть — на стенде с images |

### Волна 2.6 — masonry (FR-98)

| Тест | Вердикт | Обоснование |
|---|---|---|
| tests/web/test_qa21_gallery_ui.py::test_tc_gal_115_grid_and_filters_owner_vs_pe | **revalidate** | Сетка перестраивается на masonry (вариант «В», решение Заказчика) — ассерты карточек сетки/перерисовки фильтрами перегнать на ветке 2.6 (#52); семантика фильтров не меняется, но DOM-геометрия карточек — да |
| tests/web/test_qa21_gallery_ui.py (TC-GAL-117/118/119: лайк/загрузка/сайдбар) | **keep** | Действия окна/форма загрузки/сайдбар — вне зоны gallery.css-сетки |
| Сеточные тесты прочих сьютов | — | Отдельных grid-тестов вне test_qa21_gallery_ui не существует (проверено grep) — новых кейсов ритма сетки требует чеклист 3.1 |

### Волна 2.7 — fastline-edit (FR-89)

| Тест | Вердикт | Обоснование |
|---|---|---|
| tests/web/test_r3_formv3_ui.py::test_edit_form_matches_v3_and_hides_fast_row (TC-formv3-104) | **update** | **Строки 199–207:** `assert fast_row.get_attribute("hidden") is not None` в форме редактирования — FR-89 ПОКАЗЫВАЕТ ряд fastline в редактировании (текущее is_fast). Заменить: в редактировании .fast-row ВИДЕН и отражает состояние задачи (is_fast=false → чекбокс снят); в создании — виден как прежде (строка 207 остается). Docstring строк 8–9 («.fast-row скрыт») переписать |
| tests/api/test_fast2.py (12) | **keep** | Инварианты fast (fast⇒high, ≤1, 409, 422) не ослабляются; patch-кейсы (test_patch_cases_regular_high_ok_fast_medium_rejected) остаются истинными — 2.7 только расширяет контракт is_fast в редактировании |
| tests/api/test_fastline.py (11) | **keep** | См. волну 2.1 |

### Прочие наборы (ядерный регресс)

| Тест | Вердикт | Обоснование |
|---|---|---|
| tests/api ядро: auth/auth_me/authme_r3/avatar_r4/r5/board/categories/env/migration/migration_r4/navigation/openapi_r11/openapi_search_service/archive/gaps_r4/gaps_r5/profile_r4/users_r4/search/search_r4/suggestions*/tasks_assign_r4 (≈173) | **keep** | Дельты пакета не меняют контракты ядра (users, tasks POST/GET, категорий, миграций, search); comments join — только добавление поля (обратно совместимо) |
| tests/web ядро без затронутых: assignu/board_assign/board_tasks(кроме выше)/r3_dnd/r3_profile/r3_selects/r3_vis/r5_crop/r5_profile_card/r5_textarea/r6_gaps/r6_wave2/settings(остальное)/settings_profile (≈124) | **keep** | Зоны волн — fastline-класс, view-модалка, combobox, сайдбар-иконки, gallery; формы/DnD/селекты/профиль/кроп не затронуты (DOM-id ОГР-28 сохраняются) |

## Итог по вердиктам

**442 существующих теста: keep — 429 / revalidate — 6 / update — 7 / retire — 0**
(+1 new-файл test_comments_author_r8.py на ветке 2.3; new-кейсы — чеклист 3.1).

- **update (7):** TC-UI-010 (has-fast на столбце, test_fastline_ui.py:42);
  TC-r6-comb-004/005/006/009 (текст поля после выбора — FR-92);
  test_openapi_paths (+/api/images/{id}/name); TC-formv3-104 (fast-row
  скрыт в редактировании — FR-89).
- **revalidate (6):** TC-nav-006 (геометрия сайдбара), TC-view-102 (состав
  кнопок view vs мокап), TC-GAL-115 (сетка masonry), TC-GAL-116 (панель
  лайтбокса + rename), TC-GAL-122 ×2 (токены gallery на ветке 2.5).
- **retire (0):** удаляемого поведения дельта не содержит.

## Новые тестовые требования дельты (вход чеклиста 3.1)

1. FR-87: столбец НЕ имеет has-fast при fast-задаче; плитка — имеет
   (замещает TC-UI-010 после update).
2. FR-88: блок fastline формы создания по мокапу V3 (расположение/отступы/
   состояния галочки); блокировка приоритета сохранена.
3. FR-89: переключатель fast в редактировании: текущее is_fast; fast⇒high;
   409 «fast line занята» обрабатывается; выключение разблокирует приоритет.
4. FR-90: модалка по утвержденному мокапу — design_validator (токены V3,
   read-only, «Редактировать», закрытие).
5. FR-91: шапка комментария «автор · дата» (card и view); GET списка содержит
   author_name; POST-контракт не изменился (обратная совместимость).
6. FR-92: сброс поля после выбора/создания; 3 тега подряд; удаление по
   одному; чип с крестиком; фокус возвращается полю.
7. FR-93: кнопка «Найти» advanced + кнопки фильтров поиска/галереи — единый
   класс токенов V3, отступы 8px-сетки.
8. FR-94: иконки 4 разделов inline-SVG в едином стиле (эталон «Мониторинг»);
   внешних файлов нет.
9. FR-95: favicon data-URI в base.html, `?v=` cache-busting, стиль V3.
10. FR-96: кнопка настроек — active/focus без смещения текста (bbox до/во
    время/после).
11. FR-97: rename happy/401/404/422/пустое имя; UI лайтбокса; сетка и
    лайтбокс без перезагрузки; физические файлы/URL не меняются.
12. FR-98: сетка masonry — разнопропорциональные загрузки (квадрат/портрет/
    панорама) держат ритм; 2/3/4 колонки сохраняются; design_validator.
13. NFR-22: aria-контракт комбобокса сохранен; иконки/favicon — inline, без
    внешних запросов; токены (не хардкод); DOM-id не переименованы.

## Средовые требования прогона

1. **Маршрутизированный nginx-стенд обязателен** (app + search + images,
   :18443): advanced-search 404 и bare-стенд без search/images — известные
   пред-существующие ограничения автостенда; галерея и advanced на голом
   app-стенде невыполнимы.
2. **test_tasks KeyError `results` (6 фейлов)** — пред-существующие средовые;
   перед прогоном 3.1 убедиться в подъеме search-семейства, иначе ложный
   красный смешается с дельтами.
3. **test_r6_tag_combobox_ui на автостенде** — гонять на том же стенде, что
   и обновленные ассерты (пред-существующие красные — не считать регрессом
   FR-92).
4. **Изображения разной пропорции** для FR-98 (PNG квадрат 400×300 уже есть
   helper `_png_bytes`; добавить портрет/панораму) + том images-data чистый
   teardown по префиксу QAGAL- (готово в test_qa21_gallery_ui).
5. **Две сессии (owner и wife/PE)** — паритетные проверки галереи/комментариев
   (фикстуры client2/pe уже в юнитах и gallery-сьютах).
6. **Ветки волн**: revalidate-наборы гонять на merge-ветке со всеми волнами
   (2.2 #51, 2.3 #49, 2.5 gallery-rename, 2.6 #52, 2.7 #53) — вердикты даны
   по дельтам, факт подтверждает прогон.

## Слепые контуры (E10)

- favicon во вкладке браузера — автотест проверяет только разметку `<link
  rel="icon">`; фактическое отображение — ручной смоук приемки (внешний
  браузерный кеш не эмулируется).
- Тач-поведение комбобокса — эмуляция click-путем; реальный touch-device —
  ручной проход (унаследовано, NFR-17).
