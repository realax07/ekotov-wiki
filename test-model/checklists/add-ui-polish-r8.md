# Чеклист проверок: add-ui-polish-r8

Change-пакет: `openspec/changes/add-ui-polish-r8/` — UI-полировка P12:
fastline-UI (FR-87/88/89), модалка просмотра тикета (FR-90), шапка комментария
«автор · дата» (FR-91), сброс поля tag-combobox (FR-92), единый стиль кнопок
поиска/фильтрации (FR-93), иконки сайдбара (FR-94), favicon (FR-95), фикс
кнопки настроек (FR-96), rename файла галереи (FR-97), ритм сетки галереи —
masonry (FR-98), NFR-22 (доступность/токены/DOM-контракты).
ТЗ для сверки: requirements.md пакета, design.md §2–§3, утвержденные мокапы
волны 2.2 (модалка) и 2.6 (masonry), формулировки задач в tasks.md §ЭТАП A.
Вход 3.1: `test-model/impact/add-ui-polish-r8.md` — 442 существующих теста
(keep 429 / revalidate 6 / update 7 / retire 0) + new-файл
`tests/api/test_comments_author_r8.py` (волна 2.3, #49).
Типы: **поз.** — позитивная, **нег.** — негативная, **гран.** — граничное
значение, **НФТ** — нефункциональная, **сред.** — средовое предусловие.
Покрытие: «update/revalidate/keep» — существующий сьют с вердиктом impact-анализа
(3.1 перегоняет update/revalidate после правок); «new» — требуемый новый кейс
(qa_case_author); «REPORT-3.1» — прогон/осмотр на стенде.

## Волна 2.1 — fastline подсветка и формы (FR-87, FR-88, FR-93, FR-96)

|| ID | Источник | Проверка | Тип | Приоритет | Покрытие ||
|---|---|---|---|---|---|
|| CHK-P12-1 | board Requirement: подсветка fast line только на плитке (FR-87) / Scenario: создание fast-задачи | при активной fast-задаче КЛАСС `has-fast` ОТСУТСТВУЕТ у элемента столбца (обратный ассерт к прежнему) и присутствует у плитки `.task-card-fast`; позиция/порядок/бейдж fast-плитки не меняются | поз./НФТ | Must | update: test_fastline_ui.py::test_fast_task_create_and_highlight (TC-UI-010, строка 42) — прогон 3.1 после правки |
|| CHK-P12-2 | board Requirement: подсветка fast line (FR-87) — вторая fast-задача | вторая fast-задача → 409 «fast line занята», форма открыта, введенные поля сохранены; подсветка первой плитки не задета | нег./гран. | Must | keep: test_fastline_ui.py::test_second_fast_task_rejected (TC-UI-011); API: test_fastline.py (TC-fast-001…012), test_fast2.py (TC-fast2-001…012) — прогон 3.1 |
|| CHK-P12-3 | tasks Requirement: блок fastline формы создания по макету V3 (FR-88) | расположение/отступы/состояния галочки `.fast-row` формы создания соответствуют мокапу V3; чекбокс блокирует выбор приоритета не-high при включенном fast (behavior-инвариант сохранен) | поз./сред. | Must | new: кейс UI-снит-шот/геометрия `.fast-row` vs мокап V3 (design_validator + web-кейс); блокировка приоритета — keep: test_r3_formv3_ui.py (TC-formv3-10x) |
|| CHK-P12-4 | tasks Requirement: единый стиль кнопок действия (FR-93) — advanced | кнопка `#search-advanced-submit` «Найти» — класс токенов V3 (не хардкод-цвет), отступы на 8px-сети; DOM-id не переименован (ОГР-28) | поз./НФТ | Must | new: кейс test_search_r4_ui / design_validator-пункт на класс+токены кнопки; поведение фильтров — keep: test_search_r4_ui.py (4), test_search_suggestions_ui.py (3) |
|| CHK-P12-5 | tasks Requirement: единый стиль кнопок (FR-93) — поиск и галерея | кнопки поиска (раздел «Поиск») и фильтров/действий галереи используют тот же паттерн-класс токенов V3; hover/focus-состояния едины; функциональное поведение кнопок не изменилось | поз./НФТ | Must | new: дизайн-проход design_validator (единый паттерн по всем разделам) + keep-прогон web-сьютов поиска/галереи 3.1 |
|| CHK-P12-6 | navigation Requirement: нажатие кнопки настроек не смещает текст (FR-96) | bbox текста кнопки «Настройки»: до / во время active-нажатия / при focus-visible — смещения нет; визуальные состояния на токенах V3 | поз./НФТ | Must | new: кейс с замером bbox в трех состояниях (прецедент TC-nav-006-геометрии); revalidate: TC-nav-006 (test_settings_link_position_bottom_left_near_logout) — порог +32px может мигать при новых svg-иконках 2.4 |

## Волна 2.2 — модалка просмотра тикета (FR-90)

|| ID | Источник | Проверка | Тип | Приоритет | Покрытие ||
|---|---|---|---|---|---|
|| CHK-P12-7 | board Requirement: вид просмотра по утвержденному мокапу (FR-90) | design_validator: фактический вид модалки соответствует утвержденному мокапу волны 2.2 (макет B) — токены V3, композиция блоков; вердикт approve/return → review-отчет | сред. | Must | new: design_validator-проход против мокапа 2.2 после dev |
|| CHK-P12-8 | board Requirement: read-only семантика сохраняется (FR-90, FR-47, Д-9) | внутри view `#task-detail-attrs`: 0 элементов input/textarea/select; назначение/исполнитель-ряды отображаются (гварды TC-view-106/107); DOM-id не переименованы (ОГР-28) | поз./НФТ | Must | keep: test_view_modal_r4.py (TC-view-101, TC-view-106/107) — прогон 3.1 |
|| CHK-P12-9 | board Requirement: кнопка «Редактировать» и закрытие (FR-90) | «Редактировать» открывает существующую форму редактирования; Esc и крестик `#task-view-close` закрывают view без побочных эффектов; состав кнопок футера — сверить с мокапом 2.2 (ассерт точного множества может разойтись) | поз./гран. | Must | keep: TC-view-103/104/105; revalidate: TC-view-102 (test_view_has_no_edit_elements, строки 125–133) — прогон 3.1, при расхождении с мокапом — update по факту |
|| CHK-P12-10 | board Requirement: view — fast-признак и открытие из поиска (FR-90 преемственность) | во view «Fast line: да» для fast-задачи; клик по карточке из выдачи поиска открывает view (BUG-001-регресс); шапка комментария во view видна (преемственность FR-91) | поз. | Must | keep: TC-view-108, TC-view-109 — прогон 3.1 (TC-view-109 — на маршрутизированном стенде, см. средовые) |

## Волна 2.3 — комментарии и tag-combobox (FR-91, FR-92)

|| ID | Источник | Проверка | Тип | Приоритет | Покрытие ||
|---|---|---|---|---|---|
|| CHK-P12-11 | tasks Requirement: шапка комментария «автор · дата» (FR-91) — UI | в шапке комментария (карточка на доске И view): имя автора (не id) и человекочитаемая дата/время (не сырой timestamp); для обоих пользователей owner и PE | поз./сред. | Must | new: web-кейс шапки комментария (автор·дата) в test_board_tasks_ui-зоне; keep: test_board_tasks_ui.py::test_add_comment_persists, test_r4_commentfix_ui.py (TC-cmt-201…203) — прогон 3.1 |
|| CHK-P12-12 | tasks Requirement: API списка комментариев доставляет автора (FR-91) | GET списка комментариев содержит `author_name` (join users) для каждого комментария; значение совпадает с именем автора; поле отсутствует/пусто — поведение UI-фоллбэка определено | поз./гран. | Must | new-файл: tests/api/test_comments_author_r8.py (5 кейсов, волна 2.3 #49) — обязательный набор на маршрутизированном стенде 3.1 |
|| CHK-P12-13 | tasks Requirement: контракт POST комментария не меняется (FR-91, Won't) | POST комментария: контрак запроса/ответа идентичен дельте (сторожевой тест); комментарий создается и виден обоим | поз./НФТ | Must | keep: tests/api/test_tasks.py::test_comment_persists (строка 149) — прогон 3.1 |
|| CHK-P12-14 | tasks Requirement: сброс поля ввода после выбора тега (FR-92) | выбор существующего тега (клик/Enter/Tab/тач-путь): текст в input стал ПУСТЫМ, чип с крестиком присутствует под полем; `#task-tags-chips` содержит текст тега | поз./гран. | Must | update: test_r6_tag_combobox_ui.py TC-r6-comb-004 (строка 165), -005 (строки 227–240), -006 (строки 261–263), -009 (строка 377) — прогон 3.1 после правок |
|| CHK-P12-15 | tasks Requirement: множественное добавление и удаление по одному (FR-92) | три тега подряд (клик+создание нового): три чипа, поле пустое после каждого; удаление чипа крестиком — чип исчез, поле не блокируется, можно вводить снова; возвращенный тег снова доступен в дропдауне | поз. | Must | new: кейс «3 тега подряд + удаление по одному» (impact п.6); частично покрывается обновленными TC-r6-comb-004/005 — прогон 3.1 |
|| CHK-P12-16 | tasks Requirement: спека комбобокса сохранена (FR-92 + NFR-17/18) | открытие по фокусу, фильтрация, подсветка <mark>, исключение введенных, aria-атрибуты, закрытие по Escape/клику вне, поведение при сбое загрузки — без деградации | НФТ | Must | keep: TC-r6-comb-001/002/003/007/008/010 — прогон 3.1 (сьют гонять на nginx-стенде, см. средовые) |

## Волна 2.4 — сайдбар и favicon (FR-94, FR-95)

|| ID | Источник | Проверка | Тип | Приоритет | Покрытие ||
|---|---|---|---|---|---|
|| CHK-P12-17 | navigation Requirement: inline-SVG иконки разделов (FR-94) | у всех разделов сайдбара (доска, поиск, wiki, настройки + галерея) — inline-SVG внутри `.nav-item`; стиль/токенная окраска (currentColor, 16px) как у эталона «Мониторинг»; внешних `<img>`/файлов нет (ОГР-8) | поз./НФТ | Must | new: кейс-обход всех разделов на inline-svg+currentColor+16px (эталонные ассерты из test_qa21_netdata_sidebar_ui.py TC-ADD-201…206, строки svg.nav-icon/polyline/currentColor); порядок/адреса MUST NOT — keep: TC-ADD-201…206, TC-UI-016, test_navigation.py |
|| CHK-P12-18 | navigation Requirement: состояния разделов не меняются (FR-94, Won't) | порядок разделов прежний, бейдж todo на «Доске», wiki-stub, редиректы без сессии — как прежде; 16px-иконка внутри .nav-item не ломает переходы и тултипы | поз. | Must | keep: test_auth_ui.py (TC-UI-001…005), test_tooltip_r4.py (TC-tip-101…108); revalidate: TC-nav-006 (см. CHK-P12-6), keep: TC-nav-007/008 — прогон 3.1 |
|| CHK-P12-19 | navigation Requirement: favicon data-URI (FR-95) | в `base.html` — `<link rel="icon">` c inline-SVG data-URI (не внешний файл, ОГР-8); URL содержит cache-busting `?v=`; мотив — терракотовый акцент стиля V3 (сверка с эскизом ui_designer) | поз./НФТ | Must | new: кейс разметки favicon в e2e/test_stand_smoke-зоне (impact п.9); фактическое отображение во вкладке — ручной смоук приемки (слепой контур E10) |

## Волна 2.5 — rename файла галереи (FR-97)

|| ID | Источник | Проверка | Тип | Приоритет | Покрытие ||
|---|---|---|---|---|---|
|| CHK-P12-20 | gallery Requirement: переименование original_name (FR-97) — happy path | `PUT /api/images/{id}/name` с непустым именем → 200; новое имя в ответе списка и GET изображения; физическое имя файла в томе images-data и URL `/images/…` НЕ изменились | поз./сред. | Must | new: API-кейсы PUT /name (happy, в test_qa21_gallery_api-зоне или new-файл ветки 2.5); nginx-стенд с images обязателен |
|| CHK-P12-21 | gallery Requirement: rename — негативные коды (FR-97) | без сессии → 401; несуществующий id → 404; пустое имя/только пробелы → 422; чужое изображение — паритет ОВ-4 (оба пользователя могут переименовать общую галерею) | нег./гран. | Must | new: API-кейсы 401/404/422 + паритет owner/PE (фикстуры client2/pe) |
|| CHK-P12-22 | gallery Requirement: форма переименования в лайтбоксе (FR-97) | в full-screen лайтбоксе у имени — иконка «переименовать»; форма принимает имя, submit обновляет имя в шапке лайтбокса И карточке сетки БЕЗ перезагрузки страницы; закрытие без сохранения — имя прежнее | поз./сред. | Must | new: web-кейс rename-формы лайтбокса (ветка 2.5, feature/p12-25-gallery-rename); revalidate: TC-GAL-116 (состав панели действий лайтбокса), TC-GAL-122 ×2 (токены gallery.css/gallery.js — 0-литеральный ассерт + новые стили на var(--token)) — прогон 3.1 |
|| CHK-P12-23 | gallery Requirement: OpenAPI-множество маршрутов (FR-97 преемственность) | `test_openapi_paths` включает `/api/images/{image_id}/name` в ожидаемое множество; остальные маршруты неизменны | поз./НФТ | Must | update: services/images/tests/test_images_service.py::test_openapi_paths (строки 216–223) + юниты 27/28 keep — прогон 3.1 |
|| CHK-P12-24 | gallery Requirement: существующие операции галереи не задеты (FR-97, Won't) | upload/фильтры/реакции/комментарии/скачивание работают как прежде; core_tables_untouched истинен | регр. | Must | keep: test_images_service.py (27), test_qa21_gallery_api.py (18, TC-GAL-107…114) — прогон 3.1 на nginx-стенде |

## Волна 2.6 — masonry сетка галереи (FR-98)

|| ID | Источник | Проверка | Тип | Приоритет | Покрытие ||
|---|---|---|---|---|---|
|| CHK-P12-25 | gallery Requirement: сетка держит ритм при разнопропорциональных изображениях (FR-98) | на стенде с seed из квадрат/портрет/панорама (напр. 400×300, 300×600, 1200×300): вариант «В masonry» — ячейки выровнены по колонкам, нет наложений/дыр; превью не искажены | поз./сред. | Must | new: web-кейс masonry-ритма (ветка 2.6 #52) — фикстуры разнопропорциональных PNG обязательны (квадрат есть `_png_bytes`, добавить портрет/панораму); revalidate: TC-GAL-115 (сетка+фильтры) — прогон 3.1 |
|| CHK-P12-26 | gallery Requirement: адаптив masonry (FR-98) | переключение колонок 2/3/4 (ширина вьюпорта) сохраняется при masonry; сетка перестраивается без наложений; вид строго по утвержденному мокапу волны 2.6 (design_validator) | поз./сред. | Must | new: web-кейсы адаптива 2/3/4 + design_validator против мокапа J; teardown тома по префиксу QAGAL- (готово в test_qa21_gallery_ui) |
|| CHK-P12-27 | gallery Requirement: семантика фильтров при masonry (FR-98 преемственность) | фильтры/сортировка (created_at DESC) перерисовывают masonry-сетку корректно; действия окна (лайк/комментарий/скачивание/загрузка) не задеты сеткой | регр. | Must | revalidate: TC-GAL-115 (перерисовка фильтрами); keep: TC-GAL-117/118/119 — прогон 3.1 |

## Волна 2.7 — fastline в редактировании (FR-89)

|| ID | Источник | Проверка | Тип | Приоритет | Покрытие ||
|---|---|---|---|---|---|
|| CHK-P12-28 | tasks Requirement: переключатель fast в форме редактирования (FR-89) | форма редактирования содержит видимый ряд `.fast-row`; чекбокс отражает текущее is_fast задачи (fast → отмечен; regular → снят); docstring/семантика «скрыт в редактировании» устарела | поз. | Must | update: test_r3_formv3_ui.py::test_edit_form_matches_v3_and_hides_fast_row (TC-formv3-104, строки 199–207) — прогон 3.1 после правки |
|| CHK-P12-29 | tasks Requirement: переключение fast при редактировании — инварианты (FR-89) | включение fast в редактировании обычной задачи ⇒ priority принудительно high; вторая активная fast → 409 «fast line занята» (обработка в форме: сообщение, данные сохранены); выключение fast разблокирует выбор приоритета | нег./гран. | Must | new: web-кейс переключения fast в редактировании (ветка 2.7 #53) + API-кейсы PATCH/PUT is_fast (test_fast2.py-зона); keep: test_fast2.py (12), test_fastline.py (11) — прогон 3.1 |
|| CHK-P12-30 | tasks Requirement: серверные инварианты fast-спеки не ослаблены (FR-89, ограничения) | fast⇒high, ≤1 fast в активных статусах, 422 на fast+medium — истинны после расширения контракта редактирования; patch-кейс regular_high_ok_fast_medium_rejected остается зеленым | регр. | Must | keep: test_fast2.py::test_patch_cases_regular_high_ok_fast_medium_rejected и весь сьют — прогон 3.1 |

## Ядерный регресс и сквозная NFR-22

|| ID | Источник | Проверка | Тип | Приоритет | Покрытие ||
|---|---|---|---|---|---|
|| CHK-P12-31 | NFR-22: aria-контракт комбобокса сохранен (NFR-17/18 преемственно) | aria-атрибуты combobox (role, aria-expanded, aria-activedescendant и пр.) идентичны до/после FR-92-правок | НФТ | Must | keep: TC-r6-comb-007 (test_combobox_aria_attributes) — прогон 3.1 |
|| CHK-P12-32 | NFR-22: иконки и favicon — inline, без внешних запросов (ОГР-8) | сетевой лог страницы: нет запросов к внешним хостам/файлам иконок и favicon (только inline-SVG/data-URI) | НФТ | Must | new: кейс мониторинга network-запросов страницы (waves 2.4); частично CHK-P12-17/19 |
|| CHK-P12-33 | NFR-22: токены V3, не хардкод цветов (весь пакет) | новые стили всех волн (fast-row V3, кнопки FR-93, иконки, favicon-акцент, rename-форма, masonry) — на var(--token) из app.css :root; литеральных hex в новых правилах нет | НФТ | Must | new: design_validator-проход по всем волнам + keep: test_qa21_gallery_design.py (TC-GAL-122 ×2, revalidate на ветке 2.5), test_r3_formv3_ui.py (токены формы) |
|| CHK-P12-34 | NFR-22: DOM-контракты форм не переименованы (ОГР-28) | `#task-detail-attrs`, `#task-view-close`, `#search-advanced-submit`, `#task-tags-chips`, `.fast-row`, поля форм создания/редактирования — id на месте после всех волн | НФТ | Must | keep: весь web-регресс ядра (локаторы не переименовывались) — прогон 3.1; комбинированная проверка e2e/test_stand_smoke.py (7) |
|| CHK-P12-35 | Ядро: контракты API не меняются дельтами (Won't пакета) | users, tasks POST/GET, категории, миграции, search, suggestions — контракт-сьюты зелены; join comments — только добавление поля (обратно совместимо) | регр. | Must | keep: tests/api ядро ≈173 (auth/avatar/board/categories/migration/navigation/openapi*/search/tasks_assign_r4) — прогон 3.1 |
|| CHK-P12-36 | Ядро: незатронутые web-сьюты не деградировали (ОГР-28 преемственность) | формы/DnD/селекты/профиль/кроп/настройки-прочее работают как прежде (≈124 теста) | регр. | Must | keep: tests/web ядро без затронутых сьютов (assignu/board_assign/r3_dnd/r3_selects/r5_crop/r5_profile_card/r5_textarea/r6_gaps/r6_wave2/settings*) — прогон 3.1 |

## Пред-существующие проблемы (НЕ дельты пакета — не смешивать с новыми падениями)

1. **test_r6_tag_combobox_ui.py красные на автостенде** — сьют рассчитан на
   nginx-стенд :18443; на автостенде (http.server) — пред-существующие
   environment-фейлы, к FR-92 отношения не имеют. Прогон 3.1 — только на
   nginx-стенде.
2. **6 фейлов test_tasks KeyError `results`** — `api.search(...).json()["results"]`
   падает без search-маршрута/пустого ответа; средовое, не дельта. Перед
   прогоном убедиться, что search-семейство поднято.
3. **advanced-search 404 на автостенде** — затрагивает TC-search-r4-ui-004 и
   advanced-шаги TC-view-109; только маршрутизированный стенд.
4. **bare-стенд без search/images** — gallery-сьюты (test_qa21_gallery_*, 
   TC-GAL-115…122) на голом app-стенде SKIP/connection-error; нужен nginx-стенд
   с images :8379 (прецедент QA 2.1).
5. **test_openapi_paths устареет гарантированно** после волны 2.5 (множество
   путей без `/api/images/{id}/name`) — это ОЖИДАЕМЫЙ update (CHK-P12-23),
   красный до правки — не регресс.

## Средовые требования прогона 3.1

- **Маршрутизированный nginx-стенд обязателен**: app + search + images на
  :18443 (прецедент QA 2.1). На автостенде невыполнимы: advanced (404),
  все gallery-сьюты, combobox-сьют — см. пред-существующие проблемы.
- **Фикстуры masonry (FR-98)**: PNG трех пропорций — квадрат (есть `_png_bytes`,
  400×300), портрет и панорама (добавить в helper); том images-data чистый
  teardown по префиксу QAGAL- (готово в test_qa21_gallery_ui).
- **Seed-данные**: пользователь owner + PE (паритет ОВ-4, фикстуры client2/pe),
  задача с is_fast и без, комментарий с известным author_id, изображения всех
  пропорций, теги для combobox-сценариев (QAT-префикс по прецеденту сьютов).
- **Ветки волн**: revalidate/update-наборы гонять на merge-ветке со ВСЕМИ
  волнами (2.2 #51, 2.3 #49, 2.5 feature/p12-25-gallery-rename, 2.6 #52,
  2.7 #53) — вердикты impact даны априори по дельтам.

## Рекомендации по разбиению прогонов

1. **Прогон R1 — API-контракты (быстрый, без стенда UI)**: services/images/tests
   (28), test_comments_author_r8.py (5), test_fastline/test_fast2 (23),
   tests/api ядро ≈173. Критерий входа: ядро зеленое, images 28/28 после
   update test_openapi_paths.
2. **Прогон R2 — fastline и combobox на nginx-стенде (волны 2.1/2.3/2.7)**:
   test_fastline_ui (после update TC-UI-010), test_r3_formv3_ui (после update
   TC-formv3-104), test_r6_tag_combobox_ui (обновленные ассерты FR-92),
   new-кейсы CHK-P12-3/15/29. Комбобокс — только здесь, не на автостенде.
3. **Прогон R3 — сайдбар/favicon/кнопки (волны 2.4/2.2)**: test_qa21_netdata_
   sidebar_ui, test_auth_ui, test_tooltip_r4, TC-nav-006 (геометрия — при
   флаппе зафиксировать bbox в отчете, порог эвристический), test_view_modal_r4
   (revalidate TC-view-102 против мокапа 2.2), e2e/test_stand_smoke + new
   favicon-кейс.
4. **Прогон R4 — галерея (волны 2.5/2.6, nginx-стенд с images)**: test_qa21_
   gallery_api, test_qa21_gallery_ui (revalidate TC-GAL-115/116), test_qa21_
   gallery_design (revalidate TC-GAL-122 ×2), new-кейсы rename (CHK-P12-20…22)
   и masonry (CHK-P12-25…26) с пропорциональными фикстурами. Запускать
   последним — зависит от веток 2.5/2.6 в merge-ветке.
5. **Дизайн-проход (после R2–R4)**: design_validator по мокапам 2.2 (модалка)
   и 2.6 (masonry) + токенный аудит NFR-22 (CHK-P12-33) — один отчет,
   вердикты approve/return.
6. **Ручной смоук приемки (вне автотестов, слепые контуры E10)**: favicon во
   вкладке браузера (внешний кеш не эмулируется), реальный touch-device для
   комбобокса (NFR-17).
