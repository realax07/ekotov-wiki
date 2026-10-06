# REPORT — fix BUG-009: gallery.js — fetchImages не наполняет селект тегов (fillTagFilterOptions недостижим)

- **Change:** add-gallery-service | **Задача:** 2.1-фикс (BUG-009, major) | **Дата:** 2026-10-06
- **Роль:** dev (автор gallery.js 1.5/1.6 c652cd3/3ebeec2 и фикса BUG-008 3430e4f) | **correlation_id:** e742d5a5fd5b4a56a4bbf71b95f9a9b1
- **Баг-репорт:** `test-model/bugs/` BUG-009 (черновик `tests/REPORT-2.1-gallery-bug009-draft.md` — статический анализ и подтвержденная причина)
- **Ветка:** `add-gallery-service` (база HEAD 0882734) | **Зона:** frontend/static/** (строго)

## Причина

`fetchImages()` в success-ветке вызывал только `fillFilterOptions()`
(селект категорий). `fillTagFilterOptions()` из этого пути недостижим:
после фикса BUG-008 (3430e4f, удален дубль) единственным живым вызовом
оставался `appendKnownTag()` (точечное добавление после upload'а), а
обертка `refreshFiltersFromData()` (= `fillFilterOptions()` +
`fillTagFilterOptions()`, gallery.js:240) стала мертвым кодом — ни
одного вызова в модуле. До BUG-008 дефект маскировался SyntaxError всего
модуля. Итог: `#filter-tag` содержит только «Все теги», фильтрация по
тегу из UI невозможна (TC-GAL-115 FAIL, перегон 06ad3718).

## Фикс (1 строка, вариант QA из черновика)

`frontend/static/js/gallery.js`, success-ветка `fetchImages()` (строка 207):

```diff
       collectFacets();       // категории + теги — из фактических данных (Э-2/Э-3)
-      fillFilterOptions();   // опции категорий — из фактических данных (Э-2)
+      refreshFiltersFromData(); // ОБА селекта (категории + теги) — из фактических данных (BUG-009)
       renderGrid();
```

`appendKnownTag()` не тронут: его семантика (push в `state.tags` → sort →
`fillTagFilterOptions()`) сохранена — точечное добавление после upload'а
по-прежнему обходится без полного `fetchImages()`.

## Вызовы до / после

| Функция | До фикса (@0882734) | После фикса |
|---|---|---|
| `refreshFiltersFromData` | 0 вызовов (мертвый код; декларация :240) | 1 вызов — `fetchImages()` :207 |
| `fillTagFilterOptions` | 1 вызов — только из `appendKnownTag()` :418 | 2 вызова — `refreshFiltersFromData()` :242 + `appendKnownTag()` :418 |
| `fillFilterOptions` | 2 вызова — `fetchImages()` :207 + обертка :241 | 1 вызов — обертка :241 |
| `appendKnownTag` | 2 вызова (upload :999, лайтбокс :556) — без изменений | без изменений |

## Верификация

1. **`node --check frontend/static/js/gallery.js` → exit 0.**
2. **Скрипт-проверка живого вызова `fillTagFilterOptions`:** grep — декларация
   :395, вызовы :242 (через `refreshFiltersFromData` ← `fetchImages` :207 —
   живой путь загрузки списка) и :418 (`appendKnownTag`). Живых вызовов ≥1 ✓.
3. **(а)** `refreshFiltersFromData` — ровно одна декларация (:240), дублей нет
   (grep `^function refreshFiltersFromData` = 1).
   **(б)** Рекурсии/двойного вызова нет: тела `fillFilterOptions()` и
   `fillTagFilterOptions()` не содержат ни `refreshFiltersFromData`, ни друг
   друга (sed-вырезка тел + grep = 0 вхождений). Цепочка строго линейная:
   `fetchImages → refreshFiltersFromData → {fillFilterOptions, fillTagFilterOptions}`.
   **(в)** Все вызовы консистентны (см. таблицу «до/после»); внешних вызовов из
   шаблонов/других скриптов нет.
4. **Минимальный стенд** (процессная топология, прецедент REPORT-2.1 §1; docker
   недоступен, как и у QA): БД `/tmp/bug009/app.db` — `app.db` (схема) →
   `app.migrate_gallery` (6 таблиц, сверка ОК) → `app.migrate_r4` → seed
   owner/wife (bcrypt); app :8080 (`DB_PATH`, `SECRET_KEY`, `EKOTOV_WIKI_DB_PATH`,
   `EKOTOV_WIKI_AVATARS_DIR`), images :8379 (`EKOTOV_WIKI_IMAGES_DIR=/tmp/bug009/images`),
   статика :18480 (`python -m http.server` на frontend/static); health обоих
   сервисов `{"status":"ok"}`.
   - Изображение с тегом создано API: `POST /api/images` (PNG 640×480,
     `category=BUG009`, `tags=BUG009-лето`) → 201, в списке `tags:["BUG009-лето"]`.
   - **Единый origin:** в app статика не смонтирована (design §8 —
     `GET :8080/static/js/gallery.js` = 404, это норма стенда), а прямой fetch
     на :8379 с origin :8080 блокируется CORS. Поднят однопортовый раздающий
     `/tmp/bug009/proxy.py` :18443 (паритет nginx-пары: `/api/images*`, `/images/*`
     → images; `/api/*`, `/gallery` → app; остальное → статика) — имитация продовой
     топологии «единый origin».
   - Байты отданной статики — испраленному файлу репо идентичны
     (`GET /static/js/gallery.js?v=r7.0` = 200, `refreshFiltersFromData` в тексте).
5. **Живая DOM-проба** (chromium через браузерный инструмент; playwright как
   python-модуль на этой машине недоступен — `ModuleNotFoundError`, поэтому
   проба выполнена эквивалентным живым браузером, НЕ переносится на QA):
   - логин owner → `/gallery` → 200;
   - `#filter-tag` = `["", "BUG009-лето"]` (было `[""]` — дефект);
   - `#filter-category` = `["", "BUG009"]`;
   - сетка: 1 карточка с превью; ошибки галереи нет;
   - выбор тега `BUG009-лето` в селекте → `change` → фильтрация отработала
     (карточка с тегом осталась, запрос `/api/images?tag=BUG009-лето` — 200).

Функциональный e2e-сьют (TC-GAL-115 полный шаг «фильтр тег/комбинация») — за
QA: `tests/web/test_qa21_gallery_ui.py` на nginx-стенде.

## ⚠️ static_v — ТРЕБУЕТСЯ БАМП ПРИ ВЫКАТЕ

Изменение `frontend/static/js/gallery.js` при `static_v = "r7.0"`
(`backend/app/pages.py:36`) будет отдано браузерам из кеша по старому
`?v=r7.0` — фикс не увидят. **Бамп r7.0 → r7.1 — при выкате**, по прецеденту
цикла 1.6; `pages.py` вне зоны этого фикса и не тронут (второй фикс ветки,
BUG-008, бампал тот же файл — один бамп покрывает оба).

## Изменения

- `frontend/static/js/gallery.js` — строка 207: `fillFilterOptions()` →
  `refreshFiltersFromData()`; 1 insertion(+), 1 deletion(−). Больше ничего.
