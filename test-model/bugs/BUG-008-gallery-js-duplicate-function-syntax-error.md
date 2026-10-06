# BUG-008 — gallery.js: дубликат декларации `refreshFiltersFromData` — SyntaxError, вся галерея мертва

- **Change:** add-gallery-service | **Задача:** 2.1 (QA-прогон, TC-GAL-115…119)
- **Серьезность:** **блокер** (страница /gallery неработоспособна полностью — сетка, фильтры, лайтбокс, загрузка)
- **Статус:** новый (найден e2e-прогоном 2.1; юниты images и API-контракт не затронуты — дефект ТОЛЬКО фронтенда)

## Где

`frontend/static/js/gallery.js` — функция `refreshFiltersFromData` объявлена **дважды**:
строка 240 и строка 393 (тела идентичны: `fillFilterOptions()` + `fillTagFilterOptions()`).

```js
// :240
function refreshFiltersFromData() {
  fillFilterOptions();
  fillTagFilterOptions(); // опции тегов — из поля tags списка (Э-3 закрыт)
}
// :393 — то же самое, вторая копия (вероятно, след merge 1.6 «tags в списке»)
function refreshFiltersFromData() {
  fillFilterOptions();
  fillTagFilterOptions();
}
```

## Воспроизведение

1. Стенд: app :8080 + images :8379 + nginx :18443 (маршрутизация по 1.4).
2. Вход owner → `GET /gallery` — страница (Jinja2) отдается 200, `gallery.js?v=r7.0` — 200.
3. Консоль браузера: `SyntaxError: Identifier 'refreshFiltersFromData' has already been declared`
   (воспроизведено playwright chromium, headless, страницa /gallery).
4. `#gallery-grid` пуст: `.g-card` = 0 при наличии ≥1 изображения в `GET /api/images`.

## Ожидание (кейсы)

TC-GAL-115 (FR-84/FR-80): сетка карточек отрисовывается из `GET /api/images`
(превью/название/категория/теги/счетчики), фильтры работают. Также блокирует
TC-GAL-116 (лайтбокс), TC-GAL-117 (лайк/комментарии UI), TC-GAL-118 (форма
загрузки), TC-GAL-119 шаг 3 (переход открывает `/gallery` — «сетка, фильтры,
форма загрузки»).

## Факт

Модуль gallery.js не исполняется ВООБЩЕ (SyntaxError при парсинге до
запуска любого кода): ни одна функция не привязана, `fetchImages()` не
вызывается, `#gallery-grid` остается пустым, `#gallery-error` не показывается
(ошибка не ловится — она на этапе парсинга). API при этом здоров:
`GET /api/images` через nginx → 200 `{...}` (проверено тем же прогоном).

## Класс дефекта

Продуктовый (фронтенд, задача 1.5/1.6 — дельта gallery.js). Пропущен юнитами
images (сервис JS не выполняет) и web-сьютом 1.5? — нет: web-сьют 1.5
(REPORT-regress-21, `tests/web`) галерею не покрывал (дельта 1.5 фронтенда
без e2e-сьюта — гэп покрытия, закрыт QA-сьютом 2.1 `tests/web/test_qa21_gallery_ui.py`).

## Предложение фикса (зона dev, НЕ зона QA)

Удалить вторую копию `refreshFiltersFromData` (строка 393, вместе с
комментарием-разделителем при необходимости) — тела идентичны, риск нулевой.
После фикса: перезагрузить `/gallery` — сетка отрисовывается; прогон
`tests/web/test_qa21_gallery_ui.py` — green (сьют готов и трассирован).

## Окружение

- ветка `add-gallery-service`, HEAD db592a9 (+ QA-коммиты 2.1)
- chromium headless (playwright), nginx-стенд :18443 (паритет 1.4, images → :8379)
- static_v=r7.0 (`?v=r7.0` — не кеш)
- correlation_id: c49f8f1b7c5e4380b431136f95c375f9
