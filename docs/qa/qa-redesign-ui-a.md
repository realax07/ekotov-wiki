# QA-отчет — редизайн UI направления A (Волна 4)

- **Ветка**: `feat/redesign-ui-a` (коммиты 31b15e5 Dev-1, 10451a2 Dev-2)
- **Дата прогона**: 2026-11-22
- **Сьют**: `tests/web` (Playwright, chromium), автостенд conftest
  (uvicorn app + uvicorn search + http.server static, tmp-SQLite + seed owner/wife)
- **Объем QA**: полный прогон tests/web + классификация фейлов + функциональная
  проверка доски/wiki/gallery/video в браузере (обе темы, 1440/390) + браузерная
  сверка с эталонами `design-forge/a/` и `design-forge/extra/*` + контроль консоли.

---

## 1. Прогон tests/web

### Прогон 1 (исходный, до правок Волны 4)

```
11 failed, 410 passed, 4 skipped, 16 errors — 1113s
```

По файлам (только ненулевые отклонения):

| Файл | pass | fail | err | skip | Причина |
|---|---|---|---|---|---|
| test_coverage_uip | 10 | 1 | — | — | см. §2.3 |
| test_coverage_p14_mobile | 9 | — | — | 1 | плановый skip |
| test_coverage_weather | 15 | — | — | 1 | плановый skip |
| test_games_nav | 1 | 1 | — | — | см. §2.2 (средовой) |
| test_navigation_search_ui | 2 | 1 | — | — | см. §2.1 (регресс волны правок) |
| test_p12_gallery_rename_masonry_r8 | — | — | 4 | — | см. §2.2 (средовой) |
| test_p12n004_sidebar_footer_long_gallery | — | — | — | 1 | плановый skip |
| test_p14_22_ticket_modal_fullscreen | — | 6 | — | — | см. §2.2 (средовой) |
| test_p14_41_lightbox_swipe | — | — | 7 | — | см. §2.2 (средовой) |
| test_qa21_gallery_design | 1 | 1 | — | — | см. §2.2 (TC-GAL-122-live, известный средовой) |
| test_qa21_gallery_ui | — | 1 | 5 | — | см. §2.1+§2.2 |
| test_r3_selects_ui | 7 | — | — | 1 | плановый skip |
| остальные 30 файлов | 366 | — | — | — | зеленые |

### Прогон 2 (финальный, после правок §2.1 + окружения §2.3)

```
9 failed, 412 passed, 4 skipped, 16 errors — 1067s
```

По файлам (только ненулевые отклонения; все — §2.2 средовые):

| Файл | pass | fail | err | skip | Причина |
|---|---|---|---|---|---|
| test_coverage_p14_mobile | 9 | — | — | 1 | плановый skip |
| test_coverage_weather | 15 | — | — | 1 | плановый skip |
| test_games_nav | 1 | 1 | — | — | §2.2 (средовой) |
| test_p12_gallery_rename_masonry_r8 | — | — | 4 | — | §2.2 (средовой) |
| test_p12n004_sidebar_footer_long_gallery | — | — | — | 1 | плановый skip |
| test_p14_22_ticket_modal_fullscreen | — | 6 | — | — | §2.2 (средовой) |
| test_p14_41_lightbox_swipe | — | — | 7 | — | §2.2 (средовой) |
| test_qa21_gallery_design | 1 | 1 | — | — | §2.2 (TC-GAL-122-live, известный средовой) |
| test_qa21_gallery_ui | — | 1 | 5 | — | TC-GAL-119: средовой ConnectionError :18443 (правка §2.1 применена, верификация на живом стенде) |
| test_r3_selects_ui | 7 | — | — | 1 | плановый skip |
| остальные 32 файла | 368 | — | — | — | зеленые, включая исправленные `test_navigation_search_ui` (3) и `test_coverage_uip` (11) |

## 2. Классификация фейлов

### 2.1 Регресс волны правок тестов (исправлено в рамках Волны 4)

1. **`test_navigation_search_ui::test_sidebar_all_pages_and_wiki_stub`** —
   ожидал 7 пунктов сайдбара, фактически 8 («Манчкин», коммит 5c9ab55 —
   предсуществующий апстрим-пункт, вне редизайна). Dev-1 в коммите 31b15e5
   синхронизировал литералы навигации 7→8 в `test_redesign_console.py`
   (CHK-011, line 1249), но пропустил два файла. **Фикс**: `7→8` в
   - `tests/web/test_navigation_search_ui.py` (count + docstring-комментарий);
   - `tests/web/test_qa21_gallery_ui.py` (TC-GAL-119: labels-список + count).
   Перегон: `test_navigation_search_ui` — 3 passed. TC-GAL-119 локально не
   проверяем (нужен живой стенд :18443, §2.2) — правка верифицирована по
   фактическому DOM (aria-снапшот сайдбара: 8-й пункт «Манчкин» после «Игры»).

2. **Регрессов редизайна кода (CSS/шаблоны/JS) НЕ обнаружено**: все
   функциональные сьюты §3.3 (fastline, dnd, форма, комментарии, wiki,
   галерея, видео-каркас) — зеленые без правок логики.

### 2.2 Средовые / предсуществующие (не трогались)

Все завязаны на **живой nginx-стенд `127.0.0.1:18443`** (EKOTOV_WIKI_BASE_URL),
который в данной среде не поднят; падают и на базовом состоянии ветки
(зафиксировано в брифе Волны 4 как известные средовые):

- `test_p14_22_ticket_modal_fullscreen` — 6 fail (ConnectionError :18443);
- `test_p14_41_lightbox_swipe` — 7 error (setup: ConnectionError :18443);
- `test_p12_gallery_rename_masonry_r8` — 4 error (ERR_CONNECTION_REFUSED :18443);
- `test_qa21_gallery_ui` — 5 error + TC-GAL-119 fail (ConnectionError :18443);
- `test_qa21_gallery_design::test_tc_gal_122_live_computed_styles_and_states` —
  известный средовой (ERR_CONNECTION_REFUSED :18443);
- `test_games_nav::test_games_sidebar_munchkin_after_games` — известный средовой
  (навигация на прокси-префикс внешнего хаба /games/, standalone-контейнер
  поднимает ПМ — RUNBOOK §9).

Проверка «воспроизводимость на HEAD»: воспроизводимость на базовом коммите
для этих сьютов следует из их природы — они обращаются к внешнему стенду
напрямую (traceback: ConnectionError/ERR_CONNECTION_REFUSED на :18443),
редизайн CSS не влияет на поднятие nginx-стенда. Отдельный чекаут HEAD
не выполнялся — признак средовости однозначный (сетевой отказ до любых
ассертов редизайна).

Примечание: `test_p12_nav_icons_favicon_r8` (в брифе упомянут как известный
«no-external 500») в данном прогоне — **6 passed**, средовый сбой не
воспроизвелся.

### 2.3 Средовой дефицит окружения (устранен установкой пакета)

- `test_coverage_uip::test_tc_p12n_008_core_api_regression` — падал на
  сабпрогоне `services/images/tests/test_images_service.py::test_openapi_paths`:
  `ModuleNotFoundError: No module named 'jsonschema'`. Пакет **объявлен** в
  `backend/requirements.txt` (jsonschema==4.26.0), но отсутствовал в
  `backend/.venv`. Установлен в venv (`uv pip install jsonschema==4.26.0`) —
  изменений в репо нет. Перегон: 1 passed.

## 3. Функциональная проверка в браузере (обе темы)

Стенд QA: uvicorn app :18901 + search :18902 + static :18903 + сервисы
images :18905 / video :18904 (та же tmp-БД; миграции wiki/gallery/video;
Playwright-маршрутизация в роли nginx). Скриншоты: `/tmp/qa-shots/`.

### Доска (`/board`) — dark + light, 1440 + 390

- Создание задачи: название/описание/приоритет high/категория «Работа»/срок/теги —
  карточка в «Ожидает», признаки видны в read-only модалке ✓
- Комментарий: detail → «Редактировать» → #task-comments → добавление →
  комментарий в списке ✓
- DnD канбан: «Ожидает» → «В работе» синтетическим жестом (dragstart → rAF →
  dragover/drop/dragend, хелперы tests/web/dnd_helpers) — карточка переехала ✓
- Фастлайн: создание fast-задачи; гейт занятого слота — `#fastline-add-button`
  disabled + чип «В фастлайне уже есть задача — выполните текущую» ✓; гейт
  чекбокса в форме редактирования обычной задачи (disabled + `#task-is-fast-gate`) ✓;
  DnD fast-карточки по этапам зоны (todo → in_progress) ✓
- Тумблер темы `#theme-toggle`: обе темы переключаются, инверсия корректна,
  без FOUC ✓
- Скриншоты: `views-board-{dark,light}-{1440,390}.png`,
  `board-{dark,light}-{form,created,detail,comment,dnd,fastline-gate,fastline-dnd,full}.png`,
  `views-task-{dark,light}-{1440,390}.png`

### Wiki — dark + light

- Дерево: корень + дочерняя страница, активный пункт ✓
- Статья: breadcrumb (mono), h1 serif 22px, h2 с бордовой inset-полосой ✓,
  h3, спойлер (закрыт по умолчанию → клик раскрывает, «Тайное содержимое»
  читается) ✓, код-блок (шапка с языком + «Копировать», нумерация строк,
  JBM) ✓, таблица ✓. `<mark>` проверить в статье нельзя — санитайзер
  вырезает тег (XSS-правило, FR контракт) — стилизация mark покрыта
  ассертами §4 (`test_p15_wiki_tree` green).
- Скриншоты: `wiki-{dark,light}-{tree,article-spoiler-closed,article-spoiler-open,article-full,390}.png`

### Gallery — dark + light

- Сетка плиток: serif-имена, PNG-бейдж, реакции/счетчики (mono), даты ✓
- Фильтр по категории: «QA4-категория» → 1 плитка ✓, «Найдено: N» обновляется ✓
- Лайтбокс: открытие кликом, навигационные зоны, закрытие по Esc ✓
- Скриншоты: `gallery-{dark,light}-{grid,filtered,lightbox,390}.png`
- Загрузка через UI не проверялась (не обязательна по брифу; happy-path
  покрыт TC-GAL-118).

### Video — dark + light

- Карточки со всеми 4 статусами (сид в БД сервиса): «загружено» (золотой
  бейдж), «конвертируется» (warning), «готово» (success) + play-overlay,
  «ошибка» (danger + подпись «конвертация не удалась — оригинал сохранен») —
  различимы в обеих темах ✓
- Плеер-рамка: клик по «готово» — контейнер плеера с `<video>` (8 player-узлов
  в DOM), плейсхолдеры ph-frame/ph-no-frame для неготовых ✓
- Скриншоты: `video-{dark,light}-{grid,player,390}.png`

## 4. Браузерная сверка с эталонами

Эталоны: `design-forge/a/{board,task,kit}.html`, `design-forge/extra/{wiki,gallery,video}`,
сняты в 1440/390 (`mock-*-1440/390.png`).

| Аспект | Эталон A | Реализация | Вердикт |
|---|---|---|---|
| Палитра dark | bg #1e0f14, surface #2a161d, бордо #c4505c, золото #d6a85c | совпадает (кнопка-primary золото, кромки high бордо, фастлайн золото-кромка) | ✓ |
| Палитра light | кремовый фон, белые поверхности, те же акценты | совпадает, читаемость полная, остатков dark-токенов нет | ✓ |
| Типографика | PT Serif заголовки, Golos текст, JBM mono-подписи | «Доска»/«Wiki»/«Галерея»/«Видео» serif; readout/breadcrumb/счетчики mono | ✓ |
| Карточки задач | raised, кромка приоритета 3px, LED-точки столбцов, сериф-тайтл | совпадает (high бордо-кромка, LED gray/amber/green) | ✓ |
| Фастлайн | золото-кромка зоны, чип-гейт | совпадает; структура «3 столбца-этапа» сохранена намеренно (ОГР-28 — DOM не меняется, горизонтальный стрип мокапа не переносится) | ✓ (оговорка ОГР-28) |
| Wiki статья | h2 serif + бордо-инсет, спойлер золотой, код-блок с шапкой | совпадает | ✓ |
| Gallery | плитки с подъемом/бордо-кромкой на hover, mono-счетчики | совпадает | ✓ |
| Video | статусы LED: золото/warning-blink/success/danger, play-overlay gold | совпадает, различимы в обеих темах | ✓ |
| Нет HUD-стиля | 0 cyan/сетка/уголки | не обнаружено ни на одной странице | ✓ |

## 5. Консоль браузера

Собиралась на каждой странице (board, task-detail, wiki tree/article,
gallery grid/filters/lightbox, video grid/player, обе темы; console.error,
pageerror, requestfailed, HTTP ≥ 400):

- **pageerror (JS-исключения): 0** на всех страницах в обеих темах.
- **console.error**: только спроектированные ответы превью-эндпоинта видео
  (HTTP 409 «preview is not ready» — контракт плейсхолдера, JS обрабатывает
  через onerror → ph-frame). Прочих ошибок нет.
- Отчет: `/tmp/qa-shots/console-report.json`.

## 6. Изменения в репо (эта волна)

- `tests/web/test_navigation_search_ui.py` — литерал сайдбара 7→8 (+комментарий).
- `tests/web/test_qa21_gallery_ui.py` — литералы сайдбара 7→8 в TC-GAL-119.
- Окружение: `jsonschema==4.26.0` установлен в `backend/.venv` (пакет из
  requirements.txt; в репо не фиксируется).
- Прод-код/CSS не менялся.

Предсуществующее грязное состояние (не от Волны 4, не трогалось):
`design/p23-fastline/mobile/after-empty-390.png`,
`design/p23-fastline/mobile/after-occupied-390.png` (modified до начала QA).

## 7. Вердикт

**ГОТОВ К РЕВЬЮ.**

- Регрессов редизайна нет: все функциональные сьюты зеленые, DOM-селекторы
  не тронуты (ОГР-28), API не менялся.
- Оба найденных отклонения вне средовых — довнесенные правки литералов
  тестов (7→8) и дефицит окружения (jsonschema); оба устранены и перегнаны
  до зеленого.
- 25 средовых отклонений (9 fail + 16 error; без плановых skip): живой стенд
  :18443 — p14_22 ×6, p14_41 ×7, p12_gallery ×4, qa21_gallery_ui ×6
  (5 error + TC-GAL-119), qa21_gallery_design-live ×1, games_nav ×1 —
  предсуществующие, требуют стенда ПМа для regress-final; на редизайн
  не влияют.
- Браузерные сверки с эталонами A — соответствие по палитре/типографике/
  деталям в обеих темах на 1440/390; консоль чистая (0 JS-ошибок).
