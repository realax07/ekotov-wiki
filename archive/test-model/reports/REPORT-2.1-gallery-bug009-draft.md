# BUG-009 — gallery.js: селект фильтра тегов не наполняется (fetchImages не вызывает fillTagFilterOptions/refreshFiltersFromData)

- **Change:** add-gallery-service | **Задача-источник:** 2.1 QA-перегон (correlation_id 06ad37187cce4099925980508b3f3bd5)
- **Найден:** перегон e2e после фикса BUG-008 (HEAD 3430e4f), TC-GAL-115, tests/web/test_qa21_gallery_ui.py
- **Серьезность:** major (фильтр по тегу недоступен из UI — шаг кейса TC-GAL-115 «фильтр тег/комбинация» невыполним; category-фильтр работает)
- **Зона проявления:** frontend/static/js/gallery.js (вне зоны QA — фикс dev)

## Симптом

На /gallery при наличии в выдаче изображений с тегами селект `#filter-tag`
содержит единственную опцию «Все теги» (`value=""`) — фильтрация по тегу
из UI невозможна. Селект категорий наполняется корректно.

Воспроизведено живой пробой chromium (probe: карточки с тегами в сетке — 2,
опции `#filter-tag` = `['']`, при `img.tags = ["QAGAL-лето"]` в данных списка).

## Причина (статический анализ gallery.js @3430e4f)

- `fetchImages()` в success-ветке вызывает `collectFacets()` (наполняет
  `state.tags` из поля `tags` списка — Э-3 закрыт на уровне данных) и
  `fillFilterOptions()` (селект КАТЕГОРИЙ), но НЕ `fillTagFilterOptions()`.
- Единственный оставшийся вызов `fillTagFilterOptions()` — из
  `appendKnownTag()` (точечное добавление после upload'а с тегами через UI).
- `refreshFiltersFromData()` (gallery.js:240), обертка
  `fillFilterOptions()+fillTagFilterOptions()`, — мертвый код: после
  BUG-008 (дубль удален в 3430e4f) в модуле не осталось НИ ОДНОГО вызова.
- До фикса BUG-008 дефект был маскирован: модуль не исполнялся вовсе
  (SyntaxError парсинга), поэтому «живой» прогон ветки 1.5/1.6 его не видел.

## История вопроса

- 1.6 (3ebeec2): «селект тегов из списка» — собирается `state.tags` сразу;
  в success-ветке fetchImages вызов `refreshFiltersFromData()` потерян
  (оставлен только `fillFilterOptions()`).
- BUG-008 (3430e4f): удален дубль `refreshFiltersFromData` из :393 —
  SyntaxError ушел, но вызываемость функции не восстановлена.

## Предложение фикса (dev, зона frontend/**)

В success-ветке `fetchImages()` заменить `fillFilterOptions()` на
`refreshFiltersFromData()` (обертка уже существует и делает ровно нужное:
оба селекта пересобираются с сохранением выбора) — 1 строка:

```js
collectFacets();            // категории + теги — из фактических данных
refreshFiltersFromData();   // ОБА селекта (сейчас только категории)
renderGrid();
```

Либо (эквивалент) добавить `fillTagFilterOptions();` рядом с
`fillFilterOptions();` и удалить мертвую `refreshFiltersFromData()`.

Риск нулевой (локальная правка ветки рендера списка); регресс —
TC-GAL-115 (перегон e2e готов, шаг упадет до фикса честным фейлом).

## Как пропущено верификацией

- Юниты images (сервис) JS не выполняют.
- web/e2e галереи до 2.1 не существовало (дельта 1.5 без e2e — гэп,
  закрыт сьютом 2.1); на прогоне 31eff01 TC-GAL-115 был SKIPPED
  по BUG-008-_guard'у — тест впервые исполнился только на этом перегоне.
