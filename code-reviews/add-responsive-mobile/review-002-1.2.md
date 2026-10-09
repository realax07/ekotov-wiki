# Code Review: add-responsive-mobile — задача 1.2 [S], ПОВТОРНОЕ ревью после RETURN (fix major-1)

- **Ревьюер:** независимый code_reviewer-сабагент (не автор диффа)
- **Reviewer-Delegation:** deleg_0ac187a9 (повторное ревью после RETURN; прогон 1
  — deleg_3646c6f7 + deleg_ecf87f4f, оба прерваны ротацией сессии gateway
  (state=error платформы, delivery dropped), результаты извлечены и
  задокументированы; завершающее ревью — deleg_0ac187a9, state=completed)
- **Дата:** 2026-10-08 18:10 UTC
- **Correlation:** 076eb97c46474be6a5618f36acb22089
- **Ревьюемый коммит:** 987a896259bb512023c22d6d379ac19e135ca4a1 (ветка feature/p14-1.2-active-section, PR #110, НЕ мержен)
- **База сравнения с review-001:** 8159650511af8b3c2252d4703f7b98b2bb410507 — голова ветки на момент review-001 (дифф 8159650..987a896 = ровно фикс major-1)

## Provenance

| Поле | Значение |
|---|---|
| Ревьюемый дифф | `git show 987a896`: frontend/templates/base.html, +1/−1 — перестановка `<p class="header-title">` с позиции ПЕРЕД `<button id="burger-button">` на позицию ПОСЛЕ него (спейсер и все атрибуты без изменений) |
| Дифф вне перестановки | пусто: `git diff 987a896^ 987a896 --stat` = только base.html 2 +/−; app.css не тронут (sha256 `2b20a036…` — идентичен прокомментированному в review-001) |
| sha256 frontend/templates/base.html @987a896 | aecdb42c589f0ca9a6bc3859d7fb6824db8db06cf773468fb6e9f7e624e4e935 |
| Арбитры | мокап design/mobile-p14/01-frame-drawer-closed.html (утв. decision 2026-10-08-p14-mockups-approve), openspec/changes/add-responsive-mobile/design.md §2 |
| Стенд ревьюера | uvicorn app.main (порт 56697, DB_PATH=/tmp/p14-12-review/review002.db, init_db + seeded owner) + http.server frontend/static (порт 34289) + uvicorn services/search; playwright route-паттерн из /tmp/p14-12-review/check.py (перехват /static/** на http.server) |

## Вердикт: **APPROVE**

Замечание major-1 review-001-1.2 устранено точно и минимально: порядок детей
`.mobile-header` теперь `burger → header-title → header-spacer` — дословно по
мокапу 01. Титул отцентрован (offset 0.0px @375). Дифф не трогает ничего кроме
перестановки. Regression-smoke чист: z-фикс minor-1 жив, desktop 1280 без
изменений (сравнение с baseline main на одинаковом стенде — поведенческих
различий нет; изменение computed `display` кнопки — артефакт UA-стилей при
отсутствии CSS-скрытия, см. ниже).

## Проверено на стенде (playwright, 375×812 touch / 1280×1024)

| Ассерт | Результат |
|---|---|
| Порядок детей `.mobile-header` | ✅ `["burger", "header-title", "header-spacer"]` — == мокап 01 |
| Центровка титула @375 (|titleCenter − headerCenter| < 2px) | ✅ titleCenter 187.5, headerCenter 187.5 — **offset 0.0px** (в review-001 было 139.5 vs 187.5, offset −48px) |
| Титул на 6 путях, 17px | ✅ /board «Доска», /search «Поиск», /wiki «Wiki», /gallery «Галерея», /settings «Настройки», /settings/profile «Настройки» — текст и font-size 17px везде, видим |
| Горизонтальный скролл @375 | ✅ scrollWidth 375 == innerWidth 375 |
| Тап-закрытие drawer бургером (z-фикс minor-1, smoke) | ✅ click открывает (`sidebar-open` true), elementFromPoint в центре бургера при открытом drawer → `burger` (z шапки 320), повторный tap по центру бургера закрывает (false); первый пункт drawer не накрыт (itemTop 68 ≥ headerBottom 56, paddingTop 68px) |
| Активный пункт drawer | ✅ на /search подсвечен «Поиск» |
| Desktop 1280 — без изменений | ✅ burger/header/title/spacer/backdrop не видны, sidebar 200px, flex-direction row, transform none — **побайтово идентичные метрики на worktree main и на fix-ветке** (одинаковый стенд, одинаковый probe); скриншот 1280 — обычный десктоп без мобильной шапки |

## Дифф-гигиена

- `git show 987a896` — единственное изменение: перестановка строки
  `<p class="header-title">…</p>` ниже закрывающего `</button>` бургера.
  Комментарий, спейсер, атрибуты (role=presentation, aria) — без изменений.
- app.css в коммите отсутствует — z-фикс и стили титула не затронуты.
- Рабочее дерево ревьюера чистое (`git status` quiet), код ревьюером не правился.

## Примечание о computed display на desktop (не замечание к диффу)

Без таблицы стилей (первый прогон без route-перехвата статики) браузер
рендерит button как `display: inline-block` — это UA-стили, а не регрессия:
элемент `.mobile-header` при этом геометрически невидим (0×0) и на main, и на
фиксе. С загруженным app.css (route-паттерн) на 1280px burger/header/title
имеют нулевые боксы в обеих ветках — desktop-вид инвариантен к диффу.

## Что НЕ проверено (честно)

- Полный 59-ассертный набор прогона 1 review-001 не повторялся — объем
  повторного ревью ограничен фикс-диффом (+ regression-smoke по чек-листу ПМ).
- Смежные web-тесты (pytest) не прогонялись: дифф не трогает JS/CSS/бэкенд,
  перестановка DOM внутри шапки на strict-локаторы heading не влияет (титул
  остался role=presentation).
- design_validator pixel-consistent — вне роли code_reviewer (волна 5.1в).

## Границы

Ревьюер код не правил, push/merge не выполнял. Стенд погашен (uvicorn ×2 +
http.server, process-managed, termination подтвержден). Зона записи — только
этот файл.
