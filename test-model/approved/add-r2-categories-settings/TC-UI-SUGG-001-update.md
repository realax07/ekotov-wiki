# REVALIDATE UPDATE — TC-UI-SUGG-001 (CHK-141)

> **REVALIDATE UPDATE.** Не новый кейс: файл-обновление существующего кейса `TC-UI-SUGG-001` (`tests/web/test_search_suggestions_ui.py::test_tag_hints_datalist_bound_and_filled`). Источник: impact `test-model/impact/add-r2-categories-settings.md` §2.1 (вердикт revalidate, pending_update); пункт чеклиста CHK-141. Кейс вне релизного прогона до обновления; обновление теста — qa_automation через qa_case_reviewer (G8).

- **CHK:** CHK-141
- **Change:** add-r2-categories-settings
- **Затрагиваемый кейс:** TC-UI-SUGG-001 (утвержден: `test-model/approved/add-suggestions/sugg-01.md` §TC-UI-SUGG-001, тест `test_tag_hints_datalist_bound_and_filled`)
- **Причина обновления:** дельта categories/search превращает поле категории в select из справочника (FR-19/FR-30, sdd §4) — существующий ассерт `#search-category[list="tag-hints"]` становится невыполнимым: у select не будет атрибута `list`.
- **Суть изменения (impact §2.1):** ассерт `#search-category[list="tag-hints"]` удалить — поле категории становится select из справочника (без атрибута list); проверку разделить по полям: категория — select, привязан к `GET /api/categories`; теги — datalist `#tag-hints` остается.

## Таблица «было → станет»

| # | Шаг/ассерт кейса (было) | Станет (после обновления) |
|---|---|---|
| 1 | GIVEN: открыта `/search`, datalist `#tag-hints` загружен | Без изменений |
| 2 | Проверка привязки поля «Категория»: локатор `#search-category`, ассерт `get_attribute("list") == "tag-hints"` | **УДАЛИТЬ.** Заменить: поле `#search-category` — тег `SELECT`; опции select сверены с `GET /api/categories` (set-равенство, без пустой опции-плейсхолдера); атрибута `list` нет |
| 3 | Проверка привязки поля «Теги»: локатор `#search-tags`, ассерт `list == "tag-hints"` | Без изменений (теги остаются datalist `#tag-hints`) |
| 4 | Проверка наполнения datalist подсказками из `GET /api/suggestions` | Без изменений (для поля тегов) |

## Критерий приемки обновления

- Тест падает на текущей реализации ПОСЛЕ внедрения дельты только на удаленном ассерте (шаг 2); после правки — проходит на обеих реализациях поля (input+datalist до внедрения недопустим как финальный ассерт — правка синхронна с задачей dev).
- Разделение по полям сохранено: один тест проверяет и select категории (от справочника), и datalist тегов — ИЛИ расщеплен на два теста тем же файлом (решение qa_automation, трассировка TC-UI-SUGG-001 сохраняется в docstring).

## Ожидаемый результат обновленного кейса (GIVEN/WHEN/THEN)

- **GIVEN** пользователь авторизован, в справочнике есть категории (seed)
- **WHEN** открыта страница поиска (режим конструктора)
- **THEN** поле «Категория» — select, опции == фактическому справочнику (источник `GET /api/categories`); поле «Теги» — input с `list="tag-hints"`; datalist `#tag-hints` наполнен из `GET /api/suggestions`
