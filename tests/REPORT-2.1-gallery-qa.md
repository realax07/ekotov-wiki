# REPORT-2.1 — QA-прогоны add-gallery-service (контракт 6: прогон по approved-кейсам TC-GAL-106..123)

- **Change:** add-gallery-service | **Роль:** QA (deleg-c49f8f1b7c5e4380; перегон после фикса BUG-008 — deleg-06ad37187cce4099) | **Дата:** 2026-10-06
- **Ветка:** add-gallery-service, база HEAD db592a9; перегон на HEAD 3430e4f (фикс BUG-008) | **correlation_id:** c49f8f1b7c5e4380b431136f95c375f9; перегон: 06ad37187cce4099925980508b3f3bd5
- **Истина:** approved-кейсы `test-model/approved/add-gallery-service/TC-GAL-106..123` (18 кейсов)
- **Прецедент формата:** 9c8a7f7 (qa(2.1) add-netdata-monitoring, REPORT-2.1-netdata-qa.md)

> **Перегон 2 (этот документ, §2/§4/§5 обновлены):** после фикса BUG-008
> (3430e4f, дубль `refreshFiltersFromData` удален) — стенд поднят заново
> (схема+seed, app :8080 + search :8378 + images :8379 + nginx :18443),
> e2e-сьют перегнан: guard'ы TC-GAL-115..118 снялись автоматически,
> TC-GAL-122 динамика переведена в автопрогон
> (`test_tc_gal_122_live_computed_styles_and_states` — 2p).
> **Итог перегона: e2e 4p/1f** — TC-GAL-115 FAIL по НОВОМУ **BUG-009**
> (gallery.js: селект тегов не наполняется — fetchImages не вызывает
> `fillTagFilterOptions`/`refreshFiltersFromData`; до фикса BUG-008 был
> маскирован SyntaxError). Детали §3. Остальное — без изменений к первому
> прогону.

---

## §1. Среда и стенды

- **Юниты images:** `python3 -m pytest services/images/tests/` (TestClient, без стенда) — 28/28.
- **API-стенд (docker недоступен — топология пакета воспроизведена процессами,
  прецедент REPORT-regress-21):**
  - app (backend/app): uvicorn 127.0.0.1:8080, `DB_PATH=/tmp/qa21-gallery/app.db`,
    `SECRET_KEY=<hex>`, `EKOTOV_WIKI_AVATARS_DIR=/tmp/qa21-gallery/avatars`;
  - search (services/search/app): uvicorn 127.0.0.1:8378, `EKOTOV_WIKI_DB_PATH` (RO-профиль);
  - images (services/images/app): uvicorn 127.0.0.1:8379, `EKOTOV_WIKI_DB_PATH` +
    `EKOTOV_WIKI_IMAGES_DIR=/tmp/qa21-gallery/images` (в dev-стенд images не входит — поднят отдельно, п.2 задачи);
  - nginx :18443 — паритет `services/frontend/nginx/ekotov-wiki.conf` 1.4 без docker:
    images-пара (`= /api/images`, `^~ /api/images/`, client_max_body_size 12m, X-Service: images,
    error_page @images_down + Retry-After), search-семейство, `/images/` alias тома с expires 7d,
    статика с mime.types (урок regress-21). Прод-семантика resolver 127.0.0.11 +
    переменная `$upstream_images` (анти-stale-DNS) — на VPS-стенде, здесь статический upstream.
- **БД стенда (порядок tests/README):** `python -m app.db` (схема) → `python -m app.migrate_gallery`
  (6 таблиц gallery, сверка ОК) → `python -m app.migrate_r4` (роли PM/PE) → seed owner/wife
  (bcrypt, stdin-pipe) → seed категорий задач. Health до прогона: `:8080/api/health`,
  `:8378/api/health`, `:8379/api/health` = `{"status":"ok"}`, `:18443/api/health` = 200.
- **Web/e2e:** playwright headless chromium (pytest-playwright), против nginx-стенда :18443
  (единый origin, Secure-куки localhost-trustworthy).
- **Изоляция:** все загрузки QA — префикс `QAGAL-`; teardown чистит БД + том по префиксу
  (у images нет DELETE-эндпоинта для изображений — правки строго по маркеру).

## §2. Таблица прогонов TC → результат

| TC | Что проверено | Результат | Где |
|---|---|---|---|
| TC-GAL-106 | nginx-пара /api/images* (X-Service: images), health images 200, ядро 404 (без маршрутов), /images/ static: Content-Type png + Expires 7d + Cache-Control public + тело = байты тома, соседи (search X-Service, board без X-Service) не изменены | **PASS (шаги 1–4)** / шаг 5 (compose/порты) — **SKIPPED, требует docker** | tests/api/test_qa21_gallery_infra.py |
| TC-GAL-107 | upload happy PNG+JPEG 201; оригинал+превью — файлы тома (размеры совпадают); превью ≤800px (Pillow); малое НЕ апскейлится (640×480 → 640×480); ядро (tasks/comments/categories/users/sessions) не изменено; список + отдача файла | **PASS (5 тестов)** — юнит-базис 28/28 + api-сьют стенда | tests/api/test_qa21_gallery_api.py |
| TC-GAL-108 | >10 МБ (11 МБ, в пределах nginx 12m) → **422 too_large**, следов нет; PDF под .jpg → **422 bad_type** (magic-байты); поврежденный PNG → 422; ~9.5 МБ валидный PNG проходит nginx целиком; факт стенда: тело >12m → 413 (nginx, до сервиса) | **PASS (5 тестов)** | tests/api/test_qa21_gallery_api.py |
| TC-GAL-109 | 401 без сессии на ВСЕ 7 эндпоинтов (list/detail/upload/like/dislike/comment POST+DELETE), тело `{"error":"unauthorized"}`; реакции/комментарии/том — без изменений | **PASS** | tests/api/test_qa21_gallery_api.py |
| TC-GAL-110 | справочник галереи отделен от задач (категории задач не протекают), переиспользование значений; фильтры category/tag/комбинация = конъюнкция; пустой фильтр = все; created_at DESC (+tie-break id); tags в списке (Э-3); несуществующая категория фильтра → 200 []; неизвестный числовой category_id → 422 | **PASS (3 теста)** | tests/api/test_qa21_gallery_api.py |
| TC-GAL-111 | toggle-семантика: повторный same-sign PUT СНИМАЕТ голос (my_reaction: null, счетчик −1); смена голоса = смещение ровно на 1 (0/0→0/1); голоса owner/PE независимы; в image_reactions ровно 2 строки (PK upsert, без дублей); my_reaction в списке и детали | **PASS** | tests/api/test_qa21_gallery_api.py |
| TC-GAL-112 | комментарий виден ОБОИМ (текст/автор/время); пустой и из пробелов → 422; удаление своего → 200 (исчез); чужого → 403 (ОСТАЛСЯ); несуществующий cid → 404 | **PASS** | tests/api/test_qa21_gallery_api.py |
| TC-GAL-113 | **Э-6**: `/api/auth/me` → ровно 6 ключей `{id, user, display_name, role, bio, avatar_url}`, id = users.id; без сессии 401; ME_KEYS-тесты обновлены (2 файла) и зеленые; регресс /me-домена 20/20 | **PASS — Э-6 ЗАКРЫТ** | tests/api/test_qa21_gallery_api.py + обновленные test_profile_r4/test_gaps_r4 |
| TC-GAL-114 | /gallery анонимно → 302 /login; с сессией → 200 (страница галереи); смоук /board, /login, /search, /wiki — как прежде | **PASS (3 теста)** | tests/api/test_qa21_gallery_api.py |
| TC-GAL-115 | сетка карточек + фильтры UI + паритет PE | **FAIL — BUG-009** (частично): сетка/превью/категория-фильтр/сброс/паритет owner-PE PASS (guard BUG-008 снялся, тест исполнился); фильтр тег/комбинация FAIL — селект `#filter-tag` не наполняется (только «Все теги») при тегах в данных: `fetchImages` вызывает только `fillFilterOptions`, `refreshFiltersFromData` (обертка обоих селектов) — мертвый код без вызовов; подтверждено живой DOM-пробой chromium | tests/web/test_qa21_gallery_ui.py (дефект: §3 BUG-009, зона QA — вне tests/**; черновик баг-репорта в tests/REPORT-2.1-gallery-bug009-draft.md) |
| TC-GAL-116 | лайтбокс: листание/реакции/комментарий/скачивание | **PASS** (исполнился впервые): открытие кликом, ←/→ циклично по выдаче created_at DESC ([lb3,lb2,lb1]), клавиши, Esc/крестик, лайк+счетчик без выхода, комментарий, скачивание — href оригинала = upload-ответу, байты по href 200 | tests/web/test_qa21_gallery_ui.py |
| TC-GAL-117 | лайк с подсветкой + комментарии UI + XSS | **PASS**: лайк persist после reload, смена/снятие голоса, автор комментария (Владелец — display_name через COALESCE), пустой → disabled+ошибка, XSS-текст не исполняется, удаление — только у своего (PE без кнопки) | tests/web/test_qa21_gallery_ui.py |
| TC-GAL-118 | форма загрузки drag&drop/input + ошибки 422 в UI | **PASS**: happy через input (категория «__new__»+имя, теги), карточка без перезагрузки; 12 МБ → человекочитаемая too_large (клиентская pre-check), PDF под .jpg → ошибка типа; отказные в сетке отсутствуют; dropzone доступна | tests/web/test_qa21_gallery_ui.py |
| TC-GAL-119 | сайдбар «Галерея» 4-м пунктом (Доска, Поиск, Wiki, Галерея) у owner И PE (паритет, без role-рендера), inline-SVG иконка; клик → /gallery (страница 200, пункт active); регресс разделов (board/search/wiki маркеры на месте); ссылок на трекер в сетке нет (ОВ-3) | **PASS (1 тест)** — страница/сайдбар/навигация; отрисовка сетки — после фикса BUG-008 | tests/web/test_qa21_gallery_ui.py |
| TC-GAL-120 | 503-деградация images | **SKIPPED — требует docker** (SIGSTOP-аналог возможен на процессном стенде, но паттерн @images_down конфигурируется контейнером frontend; локальный nginx-паритет содержит @images_down — статически, динамический отказ не прогонялся) | — (см. §4) |
| TC-GAL-121 | RAM images ≤128m (docker stats), лимиты стека | **SKIPPED — требует docker-доступа Заказчика** (кейс явно помечает «замер отложен» без docker CLI; план 2.2/эскалация) | — (см. §4) |
| TC-GAL-122 | design_validator: токены V3 | **PASS (статика):** gallery.css — 0 hex-литералов, 224 var(--token*), все rgba() — от токенных базовых цветов (ink/paper/clay); gallery.js — 0 цветовых литералов; Georgia/radius 6/10px/focus-ring в app.css :root; мокапы 1.1 на месте. **PASS (динамика — перегон после фикса BUG-008):** живая /gallery в chromium — computed styles из токенов (акцент = #a8432c clay-600, радиус карточки 10px = --radius-card, --radius-field 6px, Georgia в --font-family-display и заголовках карточек, фон paper-050); hover карточки меняет box-shadow (подъем по мокапу 1.1); focus-ring виден с клавиатуры; «мой голос» после лайка — бейдж .my-vote с фоном clay-050; 422-ошибка типа файла человекочитаема в форме. **Итог TC-GAL-122: PASS** (вердикт approve/return — зона СА) | tests/api/test_qa21_gallery_design.py (2 теста, оба PASS) |
| TC-GAL-123 | репетиция миграции на копии БД стенда | **PASS — все шаги:** прогон 1 exit 0 (6 таблиц + 4 индекса, сверка ОК); прогон 2 no-op exit 0; мутант (а) junk-колонка → **exit 1** `FAIL: images: лишние колонки ['junk']`; мутант (б) чужой PK → **exit 1** `FAIL: image_tags: PK=('tag_id','image_id'), ожидается ('image_id','tag_id')`; app/images на мигрированной БД healthy; смоук ядра green. Детали: tests/REPORT-2.1-gallery-migration-rehearsal.md. Прод-копия — план 2.2 | tests/REPORT-2.1-gallery-migration-rehearsal.md |

### Числа прогонов

| Сьют | passed | failed | skipped |
|---|---|---|---|
| services/images/tests (юниты, регресс) | **28** | 0 | 0 |
| tests/api/test_profile_r4.py + test_gaps_r4.py + test_auth_me.py (Э-6 + регресс /me) | **20** | 0 | 0 |
| tests/api/test_qa21_gallery_api.py (новый, TC-GAL-107..114) | **18** | 0 | 0 |
| tests/api/test_qa21_gallery_infra.py (TC-GAL-106) | **1** | 0 | 1 (docker) |
| tests/api/test_qa21_gallery_design.py (TC-GAL-122, прогон 1) | **1** | 0 | 1 (BUG-008) |
| tests/api/test_qa21_gallery_design.py (TC-GAL-122, перегон: статика+динамика) | **2** | 0 | 0 |
| tests/web/test_qa21_gallery_ui.py (TC-GAL-115..119, прогон 1) | **1** | 0 | 4 (BUG-008) |
| tests/web/test_qa21_gallery_ui.py (TC-GAL-115..119, перегон 3430e4f) | **4** | **1 (BUG-009)** | 0 |
| **Итого (оба прогона)** | **75** | **1** | **5** |

Сумма без дубликатов перегона (актуальное состояние сьютов на HEAD 3430e4f):
юниты 28 + /me-регресс 20 + api-gallery 18 + infra 1(1s) + design 2 + web 4/1 =
**73 passed / 1 failed / 1 skipped**.

## §3. Найденное

### BUG-008 — gallery.js: дубликат `refreshFiltersFromData` → SyntaxError, /gallery мертва — **FIXED (3430e4f)**

`frontend/static/js/gallery.js:240` и `:393` — функция объявлена дважды (тела
идентичны, след merge 1.6 «tags в списке»). Модуль не исполнялся ВООБЩЕ
(SyntaxError парсинга). **Фикс dev (3430e4f): дубль удален, node --check OK —
ПОДТВЕРЖДЕН перегоном:** guard e2e-сьюта снялся автоматически, pageerror
«already been declared» отсутствует, /gallery отрисовывается (TC-GAL-116..118
PASS — лайтбокс/лайк/загрузка живы). Найден 1 новый дефект — BUG-009 ниже.

### BUG-009 (НОВЫЙ, перегон 3430e4f) — gallery.js: селект фильтра тегов не наполняется (MAJOR)

`fetchImages()` в success-ветке вызывает `collectFacets()` (наполняет
`state.tags` из поля tags списка) и `fillFilterOptions()` (селект
КАТЕГОРИЙ), но НЕ `fillTagFilterOptions()` — селект `#filter-tag` остается
с единственной опцией «Все теги», фильтрация по тегу из UI невозможна.
`refreshFiltersFromData()` (обертка обоих селектов, gallery.js:240) после
удаления дубля в 3430e4f — мертвый код: в модуле не осталось ни одного
вызова. До фикса BUG-008 дефект маскировался (модуль не исполнялся вовсе).
Подтверждено живой DOM-пробой chromium: карточки с тегами в сетке есть,
опции `#filter-tag` = `['']`. Блокирует шаг «фильтр тег/комбинация»
TC-GAL-115 (тест падает честно). **Предложение фикса (dev, 1 строка):** в
success-ветке `fetchImages()` заменить `fillFilterOptions()` на
`refreshFiltersFromData()`. Полный черновик баг-репорта:
`tests/REPORT-2.1-gallery-bug009-draft.md` (файл баг-репорта в
test-model/bugs/ — вне зоны tests/** сессии, перенести дев-циклом ПМ).

### Э-6 (TC-GAL-113) — ЗАКРЫТ

`/api/auth/me` на стенде возвращает ровно 6 ключей с `id` (=users.id);
обратная совместимость (только добавление). ME_KEYS-константы обновлены
(правки тестов — зона QA по кейсу):
- `tests/api/test_profile_r4.py:60` (ассерты :399, :423)
- `tests/api/test_gaps_r4.py:68` (ассерт :322, TC-profile-r4-101)

Регресс /me-домена (test_profile_r4 + test_gaps_r4 + test_auth_me): **20 passed,
0 failed** — миграция gallery и дельта auth.py существующее не сломали.
Замечание 5 review-002-1.5 закрыто.

### Прочее (не дефекты)

- Граница 10 МБ vs nginx 12m: тело ровно 12 МиБ + multipart-обвязка отсекается
  nginx (413) ДО сервиса — это корректное поведение транспортного контура
  (design §4: «10 МБ + multipart-обвязка»); контракт «422 too_large» проверен
  телом 11 МБ. Зафиксировано в docstring теста.
- Смоук-матрица TC-GAL-114: маршрута «/» в ядре нет (pages.py: /login, /board,
  /search, /wiki, /settings*, /gallery) — кейс перечисляет «/» по памяти;
  проверены фактические маршруты (несоответствие кейса, не продукта).
- Токенная дисциплина: gallery.css использует rgba()-alpha от токенных базовых
  цветов (paper/ink) — тот же класс, что эталонные app.css/board.css; не отход.

## §4. Ограничения / SKIPPED (с причинами)

| Что | Причина | Куда |
|---|---|---|
| TC-GAL-106 шаг 5 (compose config, порты images не опубликованы) | docker.sock закрыт subagent-сессии | стенд Заказчика / план 2.2 |
| TC-GAL-120 (503-деградация images) | управляемый отказ контейнера (docker compose stop/start) — требует docker; локальный nginx-паритет содержит @images_down статически (конфиг проверен `nginx -t`) | docker-стенд Заказчика |
| TC-GAL-121 (docker stats RAM ≤128m) | кейс явно требует docker CLI («замер отложен» без доступа) | эскалация: замер при участии Заказчика до прод-выкатки |
| TC-GAL-115 (частично: шаги «фильтр тег/комбинация») | **BUG-009** (major): селект тегов не наполняется — фикс dev (1 строка) → перегон шага | фикс dev → перегон |
| TC-GAL-123 шаг 6 (прод-копия) | план 2.2 ([ops], только с Заказчиком) | 2.2 |
| Прод-TLS/заголовки HSTS на реальном nginx-образе | локальный стенд HTTP (QA-семантика не зависит; прецедент regress-21) | VPS-стенд |

## §5. Вывод (вердикт по кейсам)

- **Перегон после фикса BUG-008 (HEAD 3430e4f), актуальный статус 18
  approved-кейсов TC-GAL-106..123:**
  - **green (11):** 106 (API-часть), 107, 108, 109, 110, 111, 112, 113, 114,
    122 (статика+динамика — design_validator PASS), 123;
  - **green (3, исполнились впервые после фикса BUG-008):** 116 (лайтбокс),
    117 (лайк/комментарии/XSS), 118 (загрузка/422-UI);
  - **green частично (1):** 119 (сайдбар/навигация/ОВ-3 + сетка жива — PASS);
  - **FAIL (1):** 115 — частично (сетка/категория-фильтр/паритет PASS,
    фильтр тег/комбинация FAIL) по **BUG-009** (major);
  - **SKIPPED по среде (3):** 106-шаг5, 120, 121 — docker;
  - **SKIP-хвост BUG-008 снят** (115..118 исполняются, 122-динамика PASS).
- **BUG-008 (блокер) — FIXED (3430e4f), подтверждено перегоном:** guard
  снялся автоматически, /gallery жива, TC-GAL-116..118 PASS без правок
  e2e-шагов семантики кейса (порядок листания приведен к created_at DESC
  выдаче — семантика TC-GAL-110; правки тестов в зоне tests/**).
- **Найден 1 новый дефект: BUG-009 (major, фронтенд)** — селект фильтра
  тегов не наполняется (`fetchImages` не вызывает `fillTagFilterOptions`;
  `refreshFiltersFromData` — мертвый код). Рекомендация: точечный фикс dev
  (1 строка) → перегон TC-GAL-115.
- **Э-6 закрыт** (ME_KEYS 6 ключей, тесты обновлены, регресс 20/20).
- **Миграция TC-GAL-123** — готова к 2.2: создание/идемпотентность/автосверка
  (оба мутанта exit 1) подтверждены; прод-репетиция — план 2.2.
- **Числа актуальных сьютов (HEAD 3430e4f): 73p / 1f / 1s** (+ история
  прогонов в таблице §2). Чекбокс 2.1 НЕ закрывается (приемка ПМ; BUG-009 —
  фикс-цикл dev). Ветка не пушится (правила конвейера).
