# Code Review: add-responsive-mobile — задача 4.1 [S] (свайпы лайтбокса)

- **Ревьюер:** независимый code_reviewer-сабагент (не автор диффа)
- **Reviewer-Delegation:** deleg_921737f3
- **Дата:** 2026-10-08 19:19 UTC
- **Correlation:** 312ca50aeac14a73bebfc6838a9066c5
- **Reviewer-Delegation:** не назначался (ревью выполнено сабагентом напрямую)

## Provenance

| Поле | Значение |
|---|---|
| Ревьюемый код | a0ab898b70a604c7c27c3776e27b251a9f30a2aa (ветка pipeline/p14-41-review, PR #121, НЕ мержен) |
| База диффа | a0ab898^ (origin/main) |
| Файлы диффа | ровно 3: `frontend/static/js/gallery.js` (+57), `frontend/static/css/gallery.css` (+6), `tests/web/test_p14_41_lightbox_swipe.py` (+398) — 461 insertions, 0 deletions (чисто аддитивный, минус-строк нет) |
| sha256 gallery.js | 54f9d6923d2a173599f13d394ca40eb011c36b411c01a476261c4f80d6aaad92 |
| sha256 gallery.css | d6885fbea9a35ee4d8203defc17adc7027b37aea945af0760d982b7462410ea2 |
| sha256 test_p14_41 | 68536c2a07df4153923e706ac7f47506b7fb708d4bd1b192923147d8811a6f02 |
| sha256 диффа (git diff a0ab898^ a0ab898) | 2bb5694b052b5fdcd8edf78f6e605820b276c219fc32cef30d305eb2664b424d |
| Арбитры | openspec/changes/add-responsive-mobile/design.md §5, specs/gallery/spec.md (MODIFIED «Full-screen просмотр с листанием» — свайп-сценарии), tasks.md 4.1, мокап 07-lightbox.html (утв.) |
| Стенд ревьюера | worktree /tmp/rev41b/repo (a0ab898, общий checkout НЕ тронут — тот оставался на pipeline/p14-41-review с рабочими правками параллельной задачи); uvicorn app + search + images на свободных портах, nginx :18443 по топологии REPORT-2.1 §1 (images-пара, /images/ alias, статика с mime.types) |

## Вердикт: **APPROVE**

Blocker/major не найдено. Все свайп-сценарии specs/gallery/spec.md (в рамках задачи 4.1)
реализованы и независимо воспроизведены ревьюером на собственном стенде; anti-scope
(без зум-жестов) и зонирование (панель комментариев вне жеста) соблюдены.

## Первый круг — спека как закон

| Scenario / требование (specs/gallery, design §5, tasks.md 4.1) | Реализация | Проверка ревьюера |
|---|---|---|
| Зоны жеста: touch-обработчики ТОЛЬКО на изображении | `bindLightboxSwipe()` вешает touchstart/move/end на `elems.image` (#lb-image); bindLightboxSwipe() вызывается из bindLightbox() | ✅ код + живой прогон: жест по `#lb-comments-list` counter не меняет, overflowY панели = auto |
| Порог ≥50px и \|dx\|>\|dy\| ⇒ листание | `Math.abs(dx) >= SWIPE_THRESHOLD_PX && Math.abs(dx) > Math.abs(dy)`, SWIPE_THRESHOLD_PX=50 | ✅ свайп ровно 50px листает, ровно 49px — нет (граница порога воспроизведена, см. «Независимые пробы») |
| Цикличность по выдаче, паритет стрелкам | `navigateLightbox(dx<0?1:-1)` — тот же путь, что клавиатура/кнопки | ✅ 9 последовательных шагов свайп↔стрелка вперемешку (3 полных цикла по 3 изображениям) — 0 расхождений; тест паритета теста дева зеленый |
| Короткое/диагональное = тап, поведение не меняется | else-ветка пуста (действий на тап по картинке нет) | ✅ 49px и диагональ (\|dy\|>\|dx\|) counter не меняют |
| Зум-жесты НЕ реализуются (anti-scope, NFR-28) | pinch (touches!==1) → tracked=false; нативный zoom не отключается | ✅ viewport meta без user-scalable/maximum-scale (`width=device-width, initial-scale=1, viewport-fit=cover`); pinch-путь в коде уходит в no-op |
| Панель комментариев скроллится независимо | жест не навешан на панель; touch-action: none только на .lb-image | ✅ вертикальный жест по панели: counter 1→1, overflowY=auto |
| Стрелки-зоны/клавиатура без изменений (FR-83/FR-97) | дифф не трогает существующие обработчики (чисто аддитивный) | ✅ desktop 1280: #lb-next, #lb-prev, ArrowLeft/Right листают как прежде |
| touch-action: none ТОЛЬКО ≤480px (desktop не затронут, NFR-29) | правило внутри `@media (max-width: 480px)` в существующей ветке | ✅ computed touchAction: `none` при 375px / `auto` при 1280px |

Anti-scope соблюден: зум-жесты не реализованы, никаких библиотек (ОГР-8, ванильный JS,
node --check OK), backend/БД/compose не тронуты (3 файла в зоне tasks.md 4.1 —
`gallery.js`, `gallery.css`, тест).

## Второй круг — гигиена и best practices

- **Ровно 3 файла**, дифф чисто аддитивный (461+, 0−) — desktop-правила не переписывались,
  touch-action добавлен только в существующую 480px-ветку — ✅.
- **prefers-reduced-motion (ОГР-17):** оба существующих блока в gallery.css (:319, :1098)
  в диффе не тронуты (0 вхождений в diff) — ✅ код-ревью; живой эмуляции reduce не делал
  (см. «Не проверено»).
- **touchmove preventDefault** только при tracked && touches===1, passive:false только там,
  где нужен; touchstart passive:true — корректная дисциплина пассивных слушателей — ✅.
- **Комментарии** объясняют «почему» (touch-action против прерывания жеста браузером) — ✅.
- **XSS/инъекции:** новых вводов/выводов нет; свайп только читает clientX/Y — ✅.
- Тест-файл: изоляция QAGAL41-префикс + teardown БД/тома по маркеру (паттерн
  test_p12_gallery_rename_masonry_r8), трассировка сценариев в докстринге — ✅.

## Третий круг — regression на собственном стенде ревьюера

Стенд: worktree a0ab898 в /tmp (общий checkout не переключался), app+search+images uvicorn
+ nginx :18443 (топология REPORT-2.1 §1). Прогрев: известная особенность — Secure-куки
localhost-контура и буферизация тела nginx (крупные PNG фикстур masonry-теста) — обе
решены конфигурацией СТЕНДА (cookie secure=False в тестах уже есть; client_body_temp_path
на tmp), не продукта.

| Набор | Результат |
|---|---|
| tests/web/test_p14_41_lightbox_swipe.py | ✅ **7 passed за 44.2 c** (первый прогон на чистой БД; лимит ≤60 c соблюден) |
| test_qa21_gallery_ui.py + test_p12_gallery_rename_masonry_r8.py (одной командой) | ✅ **9 passed за 63.9 c** (~61 c чистого pytest; первый общий прогон 8p/1f — 500 была дефектом КОНФИГА NGINX СТЕНДА ревьюера, воспроизведена и устранена на стенде, к диффу отношения не имеет; после починки стенда 9/9 стабильно) |
| Независимые пробы ревьюера (свой скрипт, не ассерты дева) | ✅ touch-action none@375/auto@1280; порог: 50px листает, 49px нет; паритет+цикличность 9 шагов 0 расхождений; жест панели не листает; viewport meta без запрета зума; desktop next/prev/стрелки + нет X-скролла |
| Мутационная 1: вызов `bindLightboxSwipe()` удален | ✅ **3 failed** (оба свайп-кейса + паритет) — ассерты красные; восстановление git checkout → **byte-identical** (sha256 54f9d692… совпал с a0ab898), `git diff` quiet |
| Мутационная 2: порог 50→500 | ✅ **2 failed** (оба свайп-кейса); восстановление → byte-identical (тот же sha256) |
| Финальный прогон после мутаций | ✅ 7/7 passed за 44.2 c — тесты детерминированы, мутации не оставили следов |

## Соответствие мокапу 07-lightbox.html (утв.)

Мокап описывает desktop-композицию лайтбокса (изображение + панель, зоны ←/→); 4.1 не
меняет композицию — добавляет только жест поверх существующего DOM. Сверка ревью: DOM
элементов (#lb-image, #lb-comments-list, #lb-counter-pos, #lb-next/#lb-prev) соответствует
мокапу/верстке, новых визуальных элементов дифф не вводит — противоречий мокапу нет.

## Что НЕ проверено (честно)

- **Реальное железо:** свайпы — синтетический touch (TouchEvent + has_touch/is_mobile
  device-эмуляция 375×812); приемка «вживую» — задача 5.2 (Заказчик, С3).
- **prefers-reduced-motion в живом браузере** — только код-ревью неизменности блоков
  (swipe-логика от анимаций не зависит, риск минимален).
- **Нативный pinch-zoom браузера** не эмулировался (anti-scope подтвержден кодом:
  tracked=false + отсутствие user-scalable в meta).
- **design_validator-сверка** «pixel-consistent» — вне роли code_reviewer (5.1в).
- Мутационная — на bindLightboxSwipe-вызове и пороге (ключевые пути задачи); touchmove-
  preventDefault-ветку мутационно не проверял (прикрыта X-скролл-ассертами).

## Границы

Запись только в этот файл (новый, untracked, НЕ коммитился). Код не правился (мутации —
временные в /tmp-worktree, восстановлены byte-identical по sha256). Общий checkout
/home/openclaw/ekotov-wiki не переключался (остался на pipeline/p14-41-review с чужими
рабочими правками — не тронуты). Стенд ревьюера погашен (uvicorn ×3, nginx :18443),
/tmp-worktree удален (git worktree prune). Push/merge не выполнялись. Provenance-запись
(gate_runner record-review) — за ПМ.
