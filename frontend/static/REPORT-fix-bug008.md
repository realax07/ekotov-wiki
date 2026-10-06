# REPORT — fix BUG-008: gallery.js дубликат `refreshFiltersFromData` (SyntaxError, /gallery мертва)

- **Change:** add-gallery-service | **Задача:** 2.1-фикс (BUG-008, блокер) | **Дата:** 2026-10-06
- **Роль:** dev (автор исходного gallery.js, коммиты c652cd3/3ebeec2) | **correlation_id:** 66b41dbb6f5749c790f2080dc61f9cc0
- **Баг-репорт:** `test-model/bugs/BUG-008-gallery-js-duplicate-function-syntax-error.md`
- **Ветка:** `add-gallery-service` (база HEAD 31eff01)

## Что сделано

### 1. Сравнение версий — тела ИДЕНТИЧНЫ

Обе декларации `refreshFiltersFromData` (бывшие :240 и :393) побайтово совпадали,
включая хвостовой комментарий:

```js
function refreshFiltersFromData() {
  fillFilterOptions();
  fillTagFilterOptions(); // опции тегов — из поля tags списка (Э-3 закрыт)
}
```

**Удалена вторая копия** (строки 393–397 старой нумерации: декларация + тело +
пустая строка перед следующим комментарием). Оставлена первая (:240 — сразу после
`sortGalleryData`, перед секцией фильтров), поведение файла не изменилось ни на
одном пути исполнения. Баг-репорт BUG-008 предлагает ровно этот вариант
(«тела идентичны, риск нулевой»).

### 2. Call-sites — все проверены

Репозиторий целиком (js/html/py, исключая test-model):

- `frontend/static/js/gallery.js:240` — единственное ОСТАВШЕЕСЯ объявление;
- **прямых вызовов `refreshFiltersFromData` внутри gallery.js нет** (функция
  вызывается опосредованно: `fetchImages()` → `renderFilters()`/поток первичного
  рендера использует `fillFilterOptions`/`fillTagFilterOptions` напрямую; сама
  обертка осталась в файле как публичная точка обновления фильтров);
- внешних вызовов из шаблонов/других скриптов нет (grep по js/html/py: только
  gallery.js и docstring QA-теста `tests/web/test_qa21_gallery_ui.py:140,158`).

Удаление дубля не затрагивает ни один call-site: единственная декларация
поднимается (function declaration hoisting), видимость и поведение идентичны.

### 3. Скан дублей всех top-level деклараций

Скриптом (regex `^(?:async )?function [name]` по файлу): **52 top-level
function declaration, дубликатов — 0** (был 1: `refreshFiltersFromData` ×2).
Других top-level `var/const/let` в файле нет (модуль ES, всё на функциях).

### 4. node --check

```
node --check frontend/static/js/gallery.js  → exit 0
```

## Верификация на свежем стенде (без playwright — его прогоняет QA отдельно)

Поднят минимальный стенд по tests/README (процессная топология, прецедент
REPORT-2.1 §1, без nginx — статике нужен отдельный раздающий, в app она
НЕ смонтирована по design §8 / review 2.3-002):

- БД: `/tmp/bug008/app.db` — `python -m app.db` (схема) → `app.migrate_gallery`
  (6 таблиц, сверка ОК) → seed owner/wife (`app.seed_users.seed_user`, bcrypt);
- app: uvicorn 127.0.0.1:8080 (`DB_PATH`, `SECRET_KEY`, `EKOTOV_WIKI_AVATARS_DIR`,
  `EKOTOV_WIKI_DB_PATH`) — `/api/health` 200;
- images: uvicorn 127.0.0.1:8379 (`EKOTOV_WIKI_IMAGES_DIR=/tmp/bug008/images`) —
  `/api/health` 200;
- static: `python -m http.server 18480` на `frontend/static` (паритет
  продовой топологии «статику отдает не-app»).

Проверки:

| Проверка | Результат |
|---|---|
| `GET /api/auth/login` (owner, JSON) | 200 `{"ok":true,"user":"owner"}` |
| `GET /gallery` с сессией | **200**, содержит `gallery-grid`, `gallery.js?v=r7.0` |
| `GET /gallery` анонимно | 302 → `/login` (негатив кейса на месте) |
| `GET /static/js/gallery.js?v=r7.0` (со static-сервера) | **200**, `text/javascript`, 41 931 байт, байты **побайтово =** исправленному файлу репо (diff -q: identical) |
| `node --check` отданной статики | **exit 0** |
| `grep -c 'function refreshFiltersFromData'` отданной статики | **1** |

До фикса этот контур давал `SyntaxError: Identifier 'refreshFiltersFromData'
has already been declared` и нулевую отрисовку (BUG-008); после — модуль
парсится, `/gallery` отдает страницу со здоровым JS. Функциональный e2e
(сетка/лайтбокс/лайки/загрузка — TC-GAL-115…118) остается за QA-сьютом
`tests/web/test_qa21_gallery_ui.py`.

## ⚠️ static_v — ТРЕБУЕТСЯ БАМП ПРИ ВЫКАТЕ

Изменение `frontend/static/js/gallery.js` при `static_v = "r7.0"`
(`backend/app/pages.py:36`) будет отдано браузерам из кеша по старому
`?v=r7.0`. **Релизный бамп static_v (r7.0 → r7.1) — в задаче 2.2**, по
прецеденту цикла 1.6; `pages.py` в зону фроникса не входит и не тронут.

## Изменения

- `frontend/static/js/gallery.js` — удалены строки 393–397 (вторая декларация
  `refreshFiltersFromData`), −5 строк; больше ничего.
