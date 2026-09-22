# Review-002 — Ревью КОДА автотестов (G8) — add-r2-categories-settings

- **Ревьюер:** qa_case_reviewer_agent (G8 — оси ревью кода тестов)
- **Дата:** 2026-09-22
- **Объект:** ветки `origin/feature/r2-qa-api-tests` (71973fc) и `origin/feature/r2-qa-web-tests` (86b14a2), диффы от main
- **Отдельно от:** review-001 (кейсы) — это ревью тестового кода
- **Вердикты:**
  - `feature/r2-qa-api-tests` — **ВЕРНУТЬ** (1 major, 4 minor)
  - `feature/r2-qa-web-tests` — **ОДОБРИТЬ** (0 blocker/major, 3 minor)

Метод: чтение всех файлов диффа в изолированных worktree (/tmp/rv-g8-api, /tmp/rv-g8-web), спот-сверка ассертов против approved-кейсов (TC-cat-005/006/008, TC-fast2-004, TC-sel-001 + revalidate-тесты), обязательные прогоны на локальных стендах (копия БД в /tmp; боевой не затронут).

## Результаты прогонов (обязательные)

| Сьют | Стенд | Результат |
|---|---|---|
| tests/api @ r2-qa-api-tests | uvicorn :8080, копия БД /tmp/rv-g8-stand.db (seed owner/wife + справочник) | **115 passed / 0 failed / 1 xfailed** (9 skipped — DB-крюки вне скоупа/рестарт-НФТ) — прогоны №2 и №3 |
| tests/web @ r2-qa-web-tests | self-стенд conftest (временная БД, свободные порты) | **45 passed / 0 failed** — с первого прогона |

Цели по задаче достигнуты в обоих сьютах. Замечание по прогону №1 API-сьюта — см. minor №5 (флaky-наблюдение, не воспроизведено в двух повторах).

## Ось 1 — Ассерты дословны кейсу

Спот-сверка 6 тестов против approved-кейсов:

- **TC-cat-005** (`test_category_rename_applies_to_all_tasks`) — дословно: 200 + тело, старого нет/новое ровно одно, category обеих задач; cleanup Д-1. ОК.
- **TC-cat-006** (`test_category_delete_in_use_blocked_409`) — дословно: 409 `{"error": "category in use", "details": {"tasks": 2}}`, категория осталась, cleanup переводом на `Дом`. ОК.
- **TC-fast2-004** (`test_fast_explicit_null_priority_422`) — дословно (payload кейса, тело 422), xfail(strict) по BUG-002. ОК (см. ось 6).
- **TC-sel-001** (`test_task_form_category_select_from_directory`) — дословно: set(опций)==set(справочника), свежая категория присутствует. ОК.
- **TC-sugg-007 / TC-UI-SUGG-001/002** (revalidate) — расщепление по доменам соответствует TC-sugg-007-update; конфликт сценария 7 спеки с FR-19 корректно помечен как эскалация в docstring. ОК.
- **TC-cat-008** (`test_category_empty_name_rejected_422`) — **MAJOR, см. таблицу замечаний**: ассерт тела ослаблен (`"validation" in body["error"]` вместо дословного тела кейса).

Ослабление `assert got["category"] in (None, "")` в TC-cat-015 — задокументировано в docstring дословной формулировкой кейса («NULL или отсутствие значения») — приемлемо.

## Ось 2 — Изоляция

- Seed справочника session-scope, идемпотентный (201/409); cleanup QAT-хвостов в teardown фикстуры — ОГР-7 соблюден.
- `category_directory`: track/untrack + удаление в teardown; задачи удаляются ДО категорий (Д-1) — в API и web (хелперы form-домена: поиск задачи по title → DELETE задачи → DELETE категории). ОК.
- Revalidate-тесты suggestions: категория в справочник до создания задачи (FR-21), cleanup в finally. ОК.
- `migr_temp_db`: временная копия БД (sqlite3 backup с WAL), миграция не трогает стенд. ОК.
- `r2_fast_line` вмешивается в общие данные (чужие активные fast → done) с восстановлением — обосновано предусловием негативов; minor №3.

## Ось 3 — Детерминизм

- `time.sleep` в тестах = 0; готовность сервера — poll `/api/health` с таймаутом (конвенция README); Playwright — expect/wait_for_function. ОК.
- Исключение: `page.wait_for_timeout(100/40)` в TC-form-011 (web) — только для скриншотов промежуточных кадров анимации, ассерты от пауз не зависят — minor №1 (web).
- Привязок ко времени суток/локали/портам нет (web-стенд — свободные порты).

## Ось 4 — Селекторы

- Семантические: get_by_role/get_by_label, id (#task-category, #search-category, #category-list), aria-label крестика. Хрупких XPath/цепочек тегов нет. Цвета V3 как якоря не используются.
- TC-form-008 проверяет computed style различимость — это суть кейса CHK-119 (цвет+иконка+текст), не хрупкость. Текстовые подписи бейджей проверяются — различимость без цвета. ОК.
- TC-nav-008: assert `"active" in class` — привязка к классу состояния разметки, задокументирована — minor №2 (web).
- Геометрические пороги TC-nav-006 (+32px) и TC-form-006 (<48px) — дословно из кейсов, viewport Playwright фиксирован — приемлемо.

## Ось 5 — Трассировка и метки

- TC-ID в docstring каждого теста — проверено по всем файлам диффа. ОК.
- `# regression: keep` — расставлены на устойчивых проверках корректно (FR-15/16/17, FR-17).
- `candidate-archive` — TC-migr-001…006, TC-fast2-010 (impact §3 п.2) — заявлены в docstring/шапке модулей, корректно по G5.
- UI-остатки API-кейсов (TC-cat-001/002/003, TC-fast2-003) помечены `web_ui` + skip со ссылкой на скоуп tests/web — двойного покрытия нет, дубли закрыты web-тестами. ОК.

## Ось 6 — xfail-дисциплина

- TC-fast2-004: `xfail(strict=True)` с reason и ссылкой на test-model/bugs/BUG-002-fast-explicit-null-priority-201.md — при фиксе появится XPASS и уронит strict — сигнал снять метку. Дисциплина соблюдена.
- В ветке xfail стоит (по условию задачи — ОК, не дефект). Интегратору: main уже содержит фикс BUG-002 (da782f5) — при влитии ветки удалить xfail из этой ветки (конфликт/XPASS неизбежен).

## Таблица замечаний

| № | Ветка / файл | Тест/место | Серьезность | Дефект | Рекомендация |
|---|---|---|---|---|---|
| 1 | api / test_r2_categories.py | `test_category_empty_name_rejected_422` (TC-cat-008) | **major** | Ассерт тела ослаблен против кейса и sdd §3 (кейс/sdd: `{"error": "validation", "details": …}`; ассерт: подстрока `"validation" in body["error"]`). Ослабление маскирует реальное расхождение sdd↔реализация: каркасный обработчик RequestValidationError (app/tasks.py:510) возвращает `"validation error"`, а не `"validation"`. Прецедент BUG-002 требует обратной дисциплины: расхождение фиксируется баг-репортом + xfail(strict), тест не «проглатывает» дефект послаблением ассерта | Завести баг/эскалацию ПМ (формат 422-тела каркасной валидации vs sdd §3), тест перевести в xfail(strict) с дословными ассертами кейса — либо зафиксировать решение по спеке, легализующее каркасный формат |
| 2 | api / conftest_r2.py | `r2_seed_categories` teardown | minor | Удаление QAT-хвостов best-effort: код ответа DELETE не проверяется (409 «in use» молча пропускается — хвост останется); вложенный `api.list_all()` в цикле избыточен | Проверять/логировать статус; id брать из уже полученного списка |
| 3 | api / conftest_r2.py | `r2_fast_line` restore | minor | Восстановление чужих fast-задач переводит их в `todo` без учета исходного статуса (in_progress теряется); на общем стенде статус пользовательских задач «мигает» | Сохранять исходный статус в `_free()` и восстанавливать в него |
| 4 | api / test_r2_categories.py | `test_empty_category_is_allowed` (TC-cat-015) | minor | `assert category in (None, "")` — фиксация факта реализации (сохраняет `""`), задокументирована формулировкой кейса | При уточнении sdd (nullable vs пустая строка) свернуть до одного значения |
| 5 | api (прогон) | Полный сьют, прогон №1 | minor | 2 флaky-падения (`test_suggestions_union_of_tags_and_categories`, `test_api_search_with_filter_and_repeated_tag`): данные, созданные в setup, не видны в немедленном чтении; изолированные прогоны и повторные полные (№2, №3) — зеленые. Тестовый код синхронен (201 → чтение), привязок ко времени нет — вероятна гонка среды/хранилища, не тестов | Повторить серию прогонов при приемке; если воспроизведется — фиксировать как дефект среды/продукта (не ослаблять ассерты) |
| 6 | web / test_settings_categories_ui.py | `test_task_form_open_close_animation` (TC-form-011) | minor | `page.wait_for_timeout(100/40)` — фиксированные паузы (единственные в web-сьюте); назначение — скриншоты промежуточных кадров, ассерты независимы | Допустимо; при росте — заменить на expect-состояния |
| 7 | web / test_navigation_search_ui.py | `test_settings_link_available_from_all_pages` (TC-nav-008) | minor | Привязка к классу `active` (класс состояния разметки); задокументирована в тесте как факт | Допустимо; не расширять на классы оформления |
| 8 | web / test_settings_categories_ui.py | `test_settings_link_position_bottom_left_near_logout` (TC-nav-006) | minor | Геометрический порог +32px — эвристический (в кейсе «высота + отступ» без числа); при смене шрифтов/масштаба может мигать | Зафиксировать константу порога рядом с assert с комментарием источника |

## Дефекты тестов, блокирующие одобрение

- Только замечание №1 (api, major). Blocker нет. Web-сьют замечаний blocker/major не имеет.

## Итог

- **feature/r2-qa-web-tests — ОДОБРИТЬ** (24 новых + 7 revalidate; 45 passed; оси 1–6 без нарушений blocker/major).
- **feature/r2-qa-api-tests — ВЕРНУТЬ** автору (qa_automation): устранить замечание №1 (баг/эскалация по формату 422-тела + xfail-дисциплина как в BUG-002), по желанию — minor №2/№3. Повторный прогон с целью 115/0/1 — на rerun-итерации.
