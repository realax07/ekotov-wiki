# REPORT-coverage-audit — независимый аудит покрытия «спека → кейсы → автотесты» (add-wiki)

- **Аудит:** покрытие ОТ ТРЕБОВАНИЙ (не от тестов). QA-артефакты написаны задним числом — проверен каждый Scenario каждой Requirement дельт `openspec/changes/add-wiki/specs/{wiki,navigation}`.
- **Репо:** /home/openclaw/ekotov-wiki, ветка main @ 5f7f36a. Дата: 2026-10-10.
- **Метод:** сценарий → кейс в `test-model/approved/add-wiki/` (поле «Источник») → автотест в `tests/api/test_wiki_api.py` (27), `tests/api/test_sanitize.py` (16), `tests/web/test_p15_wiki_{tree,page,editor,history}.py` (29, TC-wiki-001…309) — **по телу/docstring, не по формальной ссылке** → при отсутствии автотеста: REPORT-4.1…4.4 / DV / смок.
- **Масштаб:** 15 Requirements (14 wiki ADDED + 1 navigation MODIFIED), 40 сценариев.

Вердикты: **covered** — кейс + автотест, проверяющий именно этот аспект; **script-only** — автотеста нет, проверено скриптом прогона/смока/DV (задокументировано); **GAP** — автотеста нет и/или фактическое подтверждение отсутствует/противоречит заявке.

## 1. Таблица покрытия

### wiki ADDED

| Requirement (приоритет) | Scenario | Кейс (approved) | Автотест (фактическая проверка) | Вердикт |
|---|---|---|---|---|
| Дерево страниц Wiki (Must) | Открытие /wiki со страницами | TC-wiki-411 | TC-wiki-001 `test_wiki_tree_three_levels_build_and_collapse` (3 уровня, build+collapse) + API `test_list_pages_flat_shape` | covered |
| Дерево страниц Wiki | Раскрытие и сворачивание узлов | TC-wiki-411 | TC-wiki-001 (тот же тест: aria-expanded, повторный клик) | covered |
| Дерево страниц Wiki | Пустое состояние | TC-wiki-411 | TC-wiki-004/005/006 (`.wiki-empty`, кнопка → редактор) | covered |
| Создание страницы (Must) | Создание корневой | TC-wiki-412 | TC-wiki-307 `test_save_create_posts_and_redirects` + API `test_create_page_returns_201` | covered |
| Создание страницы | Создание вложенной | TC-wiki-412 | API `test_create_page_with_valid_parent` (появление в дереве — UI через TC-wiki-001/307 косвенно) | covered |
| Создание страницы | Пустой заголовок отклоняется | TC-wiki-412 | TC-wiki-309 `test_empty_title_error_no_request` + API 422 ×2 (empty/missing title) | covered |
| Breadcrumb (Must) | Полная цепочка предков | TC-wiki-413 | TC-wiki-101 (4 уровня, ссылки, aria-current) + API `test_breadcrumb_deep_chain` | covered |
| Breadcrumb | Breadcrumb корневой страницы | TC-wiki-413 | TC-wiki-102 `test_breadcrumb_root_single_item` | covered |
| WYSIWYG-редактор (Must) | Тулбар применяет форматирование | TC-wiki-414 | TC-wiki-301/302/303 + sanitize `test_toolbar_markup_passes`, `test_full_toolbar_document_roundtrip` + кроссбраузер 4.4 | covered |
| WYSIWYG-редактор | Undo/redo | TC-wiki-414 | TC-wiki-302 `test_toolbar_lists_and_undo_redo` | covered |
| WYSIWYG-редактор | Редактор без внешних зависимостей | TC-wiki-414 (шаг 5) | НЕТ автотеста; REPORT-4.4 §(в) — но замерявшийся показатель pageerror, **сетевые запросы не перехватывались** | **GAP G3** (Must) |
| Изображения (Must) | Вставка из галереи | TC-wiki-415 | TC-wiki-305 `test_image_insert_from_gallery` (`/images/{id}` в контенте) | covered |
| Изображения | Загрузка с диска | TC-wiki-415 | TC-wiki-306 `test_image_insert_from_disk_uploads_and_inserts` (file input → POST /api/images) | covered |
| Изображения | Нарушение лимитов загрузки (422) | TC-wiki-415 (шаг 4) | НЕТ автотеста; заявка «REPORT-4.2 §4 DV-8» — фактически зафиксирован **HTTP 404** (images-API на стенде 4.2 не поднимался) — ветка 422 НИКОГДА не выполнялась вживую | **GAP G2** (Should) |
| Редактирование с версией (Must) | Сохранение правки создает версию | TC-wiki-416 | API `test_update_creates_version_and_bumps_updated_at`, `test_update_title_only_keeps_content` + TC-wiki-308 | covered |
| Редактирование с версией | История полная | TC-wiki-416 | TC-wiki-202 (правки owner+wife, авторы/время) + паритет-смок 4.1 | covered |
| История и откат (Must) | Список версий от новых к старым | TC-wiki-417 | TC-wiki-202 + API `test_versions_list_newest_first_without_content` | covered |
| История и откат | Просмотр версии read-only | TC-wiki-417 | TC-wiki-204 `test_version_view_readonly` | covered |
| История и откат | Откат создает новую версию | TC-wiki-417 | TC-wiki-205/206 + API `test_revert_creates_new_version_not_rewrite` + смок 4.4 п.13 | covered |
| Поиск по wiki (Must) | Находит по заголовку и тексту | TC-wiki-403 | TC-wiki-002 (`<mark>`, путь, счетчик) + API `test_search_finds_title_and_content` | covered |
| Поиск по wiki | Поиск не затрагивает версии (ОВ-3) | TC-wiki-403 (шаг 4) | **Автотеста НЕТ**: `test_search_finds_title_and_content` правит контент PUT'ом, но не ассертит «старая версия не ищется»; REPORT-4.1 §2 заявляет «не по версиям» без имени теста | **GAP G1** (Must) |
| Поиск по wiki | Поиск без совпадений | TC-wiki-403 | TC-wiki-003 + API empty-q 422 + `test_search_limit_20`, `test_search_escapes_like_wildcards` | covered |
| Права доступа (Must) | Паритет owner и wife | TC-wiki-401 | 401-гейт — автотест; **двухсессионный паритет — только смок-скрипты** (4.1 §2, 4.4 пп.6/9/14) | script-only |
| Права доступа | Анонимный доступ к странице (302) | TC-wiki-401 (шаг 2) | /wiki — смок 4.4 п.7 (скрипт); /wiki/{id}/history — TC-wiki-201; **анонимный GET /wiki/{id} — нигде явно**; заявка REPORT-4.1 §2 «покрыто test_wiki_page_scaffold_no_todo_stub» неверна (тест ходит под owner-сессией, assert 200) | **GAP G5** (Low) |
| Права доступа | Анонимный вызов API (401) | TC-wiki-401 | `test_all_endpoints_require_session` — все 9 методов, по телу | covered |
| Удаление страницы (Should) | Удаление листовой | TC-wiki-418 | TC-wiki-104 (диалог, редирект) + API `test_delete_leaf_removes_versions` (CASCADE); файлы галереи не тронуты — имплицитно (нет кода удаления) | covered |
| Удаление страницы | С дочерними запрещено (409) | TC-wiki-418 | TC-wiki-103/105 + API `test_delete_with_children_409`, `test_get_page_can_delete_leaf_vs_parent` | covered |
| Производительность (Must, NFR-30) | Пороги на эталонном корпусе | TC-wiki-402 | автотеста нет — прогон 4.1 §4 (скрипт-сеялка 1000 стр./10 000 верс., p95 ×20 ×2 круга, запас ×3–10) | **script-only** (NFR — по постановке) |
| Санитизация (Must, NFR-31) | Скрипт вырезается при отображении | TC-wiki-404 | sanitize-негативы ×6 (`script`/`style`/`on*`/`javascript:`/мутация/iframe) + сквозные `test_create_sanitizes_content`, `test_revert_sanitizes_stored_content` | covered |
| Санитизация | Разрешенные теги проходят | TC-wiki-404 | `test_toolbar_markup_passes`, roundtrip, data:image, plain-text escaping | covered |
| Миграция (Must, NFR-32) | Повторный запуск (no-op) | TC-wiki-405 | автотеста нет — прогон 4.4 §(а) прогон 2 (created=0, сверка ОК, exit 0); BEGIN IMMEDIATE/IF NOT EXISTS подтверждены в `backend/app/migrate_wiki.py` | **script-only** |
| Миграция | Репетиция на копии прод-БД | TC-wiki-405 | прогон 4.4 §(а) — фактический прод-снапшот, ОК×2, integrity ok, 0 расхождений | **script-only** (по природе ручная) |
| Фронтенд без зависимостей (Must, NFR-33) | Токены вместо хардкода | TC-wiki-406 (шаг 1) | автотеста нет — DV review-001 (grep `#hex` по wiki.css пуст) | **script-only** (DV) |
| Фронтенд без зависимостей | Кроссбраузерность редактора | TC-wiki-406 (шаг 3) | автотеста нет — прогон 4.4 §(в): Chromium 153 + Firefox 155, 16/16 ×2, pageerror 0 | **script-only** (NFR — по постановке) |

### navigation MODIFIED

| Requirement | Scenario | Кейс | Автотест / фактическая проверка | Вердикт |
|---|---|---|---|---|
| Пустой раздел Wiki → полноценный (Must) | Раздел Wiki отображается как заглушка (инверт.) | TC-wiki-408 | `test_wiki_page_scaffold_no_todo_stub` — проверяет страницу /wiki, НЕ сайдбар; **в `frontend/templates/base.html:99` бейдж `todo` ФИЗИЧЕСКИ ПРИСУТСТВУЕТ** («Wiki <span class="todo-badge">todo</span>»), а легаси-тест `test_nav_order_addresses_states_unchanged` его even assert'ит. Текст сценария («пометки todo нет») сегодня НЕ выполнен; TC-408 признаёт «хвост 6.x», review-001 — вне шва волны 3 | **GAP G4** (Must; принятый риск — задокументированный перенос) |
| — | Раздел Wiki не дает wiki-функций (инверт.) | TC-wiki-408 | весь wiki-сьют 56 проверок + смок 4.4 | covered |
| — | Переход в Wiki через сайдбар | TC-wiki-408 | `test_nav_order_addresses_states_unchanged` (кликабельность, href, active) + скрин 4.2 01-tree.png | covered |
| — | Пункт Wiki в существующем порядке | TC-wiki-408 | тот же тест: labels == [Доска, Поиск, Wiki, Галерея] | covered |
| — | Неавторизованный доступ к Wiki (302 /login) | TC-wiki-408 (шаг 5) | смок 4.4 п.7 (скрипт, /wiki → 302); автотеста на /wiki нет (см. G5) | script-only |
| — | Wiki-функции доступны из раздела | TC-wiki-408 (шаг 3) | suite + смок 4.4 (создание/правка/поиск/откат) | covered |

## 2. Сводка

- **Requirements: 15/15** проверены; **Scenario'ев: 40** → covered **31**, script-only **6** (NFR-30/32/33 по постановке + паритет + аноним-/wiki + токены-DV), **GAP 5**.
- Честность реестра: автотестов по телам подтверждено 27 (API) + 35 sanitize-проверок + 29 (web) — совпадает с заявленным.

## 3. GAP'ы

| ID | Сценарий (приоритет) | Суть | Severity | Рекомендация |
|---|---|---|---|---|
| **G1** | Поиск не затрагивает версии (Must, ОВ-3) | Кейс есть (TC-403 шаг 4), автотеста нет; заявка REPORT-4.1 «не по версиям» не подкреплена именованным тестом — воспроизвести/перепроверить нельзя. Риск низкий (поиск читает только `pages`), но это негатив безопасности-класса трассируемости | **Medium-High** | Автотест на 10 минут: создать страницу, PUT новый контент, search по строке из v1 → пусто. Закрыть до 4.5 |
| **G2** | Нарушение лимитов загрузки → 422 (Should, NFR-34) | Ветка 422 в контуре wiki НИКОГДА не выполнялась: на стенде 4.2 images-API отсутствовал, DV-8 зафиксировал 404, а чеклист/TC-415 подают это как проверку 422 | **Medium** (Should → фикс или принятый риск) | Один негатив на поднятом images-стенде (>10 МБ / плохой MIME → 422, контент не меняется); либо письменно принять риск |
| **G3** | Редактор без внешних зависимостей (Must, ОГР-8) | Сценарий требует контроля СЕТЕВЫХ запросов; REPORT-4.4 §(в) меряет только pageerror. CDN-запрос не порождает pageerror — контроль фактически не выполнен | **Low-Medium** (конструктивно статика локальная, grep CDN пуст) | ЗАКРЫТ пробой с перехватом сети 2026-10-10 — см. «G3 — закрытие» ниже |
| **G4** | «Пометки todo нет» в сайдбаре (Must, navigation) | `base.html:99` содержит `todo-badge`; сценарий спеки буквально не выполнен; легаси-тест закрепляет бейдж. Чеклист CHK-wiki-1 при этом заявляет «пометки „todo" нет» как проверенную — неточность чеклиста | **Medium** — задокументированный перенос («хвост 6.x», review-001, TC-408) → принятый риск | Убрать бейдж в волне 6.1 ИЛИ поправить сценарий спеки (пометить перенос явно); чеклист CHK-wiki-1 скорректировать |
| **G5** | Анонимный GET /wiki/{id} → 302 | Автотест есть только для /wiki/{id}/history (TC-201); смок проверял только /wiki; заявка REPORT-4.1 §2 о покрытии navigation-тестом ошибочна (тест ходит авторизованно) | **Low** (middleware един для всех страниц) | Добавить 2 строки в anon-тест: GET /wiki и /wiki/{id} → 302 |

### G3 — закрытие пробой с перехватом сети (2026-10-10)

- **Метод:** playwright-проба `scripts/g3_probe_wiki_network.py` против автостенда
  tests/web/conftest (tmp-БД + migrate_wiki + seed, топология «nginx» через
  playwright-роутинг); `page.on('request')` перехватывает ВСЕ запросы страниц
  `/wiki`, `/wiki?create=1` (редактор: ввод в contenteditable + клики тулбара),
  `/wiki/{id}`, `/wiki/{id}/history` + MIME-контроль ES-модулей по
  `responsefinished`. Полный отчет: `REPORT-G3-network-probe.md` (рядом).
- **Факт:** перехвачено 120 запросов; внешних (host ≠ 127.0.0.1/localhost) — **0**;
  **список внешних доменов — пуст**; MIME-ошибок ES-модулей — 0; requestfailed — 0;
  все 4 страницы отрисованы (sanity-ассерты). Статический grep шаблонов/js/css —
  внешних URL нет (только комментарий Jinja и placeholder строки, не запросы).
- **Вердикт:** **закрыт.** ОГР-8/NFR-34 подтверждены фактически: ни одна страница
  раздела Wiki не обращается за пределы localhost. Рекомендация: переложить пробу
  в автотест tests/web (6.1).

Попутные дефекты документации (не GAP'ы, исправить в 6.1): CHK-wiki-27/TC-401 приписывают `test_all_endpoints_require_session` покрытие редиректов страниц (тот проверяет только 401 API); CHK-wiki-7 отображает «Поиск не затрагивает версии» на тесты, которые этот аспект не проверяют; CHK-wiki-20 подает DV-8 (404) как подтверждение 422-ветки.

## 4. Итоговый вердикт

**Прод-выкатка 4.5 — РАЗРЕШЕНА, с двумя обязательными действиями перед накаткой** (не блокирующие по существу, закрываемые за <1 часа):

1. **G1**: добавить автотест «поиск не находит подстроку из старой версии» и прогнать — единственный Must-сценарий без воспроизводимого подтверждения.
2. **G4**: зафиксировать бейдж «todo» как формальное отклонение спеки с решением Заказчика (принять до волны 6.1) — сейчас сценарий спеки и прод-фронтенд противоречат друг другу буквально.

Сценариев «НИГДЕ не проверено» — **ноль**: каждый из 40 имеет либо автотест (31), либо задокументированный скриптовый прогон (6), либо кейс+частичное подтверждение (GAP-тройка G1/G2/G3). NFR-30/32/33 и паритет прав — «скрипт, не автотест», что по постановке допустимо; факты прогонов (4.1 §4, 4.4 §(а)/(в)) полны и воспроизводимы. G2 (Should) и G5 (Low) — принять как риск с пометкой или закрыть в 6.1.

*Аудит выполнен без изменений репо; коммит/пуш не производились.*
