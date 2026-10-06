# Impact-анализ: change add-gallery-service

> Дата: 2026-10-06 | Режим: прогнозный impact (задача 2.1, qa_impact_analyst;
> полный регресс 2.1 на стенде еще не прогнан — вердикты по существующим
> наборам даны априори по дельтам и прецеденту search-семейства).
> Вход: дельты `openspec/changes/add-gallery-service/specs/` (gallery ADDED,
> navigation ADDED, services ADDED, deploy MODIFIED), design.md §1–§7,
> чеклист `test-model/checklists/add-gallery-service.md` (CHK-GAL-1…30),
> REPORT-1.6-escalations (Э-6/Э-7), review-002-1.5.
> Требование H5: impact обязателен при любой MODIFIED-дельте — пакет
> содержит MODIFIED deploy (и MODIFIED services-лимиты) ⇒ файл создан.

## Характер дельты

- **ADDED — gallery (новая capability):** сервис `images` (:8379, FastAPI,
  порты не публикуются) — upload (JPEG/PNG/GIF/WebP по magic-байтам, ≤10 МБ,
  превью Pillow ≤800px), список с комбинируемыми фильтрами категория/тег,
  реакции один-голос (upsert по PK), комментарии (чужой → 403); файлы в томе
  `images-data` (не БД, не wiki-data), отдача `/images/` nginx-alias с
  expires 7d (паритет `/avatars/`); full-screen просмотр с листанием ←/→;
  доступ паритетный owner/PE (ОВ-4), без сессии — 401/редирект.
- **ADDED — navigation:** пункт «Галерея» ЧЕТВЕРТЫМ в сайдбаре, после «Wiki»
  (порядок: Доска, Поиск, Wiki, Галерея), всем авторизованным без
  role-рендера; вид — по утвержденным мокапам 1.1, проверка design_validator
  (FR-86, CHK-GAL-27).
- **ADDED — services (сервис-писатель images):** четвертый контейнер рядом с
  search/backup; первый сервис-писатель после ядра — маунт `wiki-data` **RW**,
  пишет ТОЛЬКО таблицы gallery (users — только чтение); миграций у images
  нет — схему создает ядро (один владелец миграций, паритет search).
- **MODIFIED — deploy (триггер H5):** что именно меняется:
  1. **миграция `migrate_gallery` one-shot** (`python -m app.migrate_gallery`,
     6 таблиц + индексы, идемпотентно, автосверка exit 1 при расхождении) —
     строго ДО подъема app, порядок матрицы: бэкап → build → миграция →
     up app → healthy → up images/frontend → healthy → смоук (правило
     «миграции one-shot до подъема нового app» сохраняется, носитель
     расширяется);
  2. **новый том `images-data`** — файлы изображений вне БД; в compose:
     images — `wiki-data:/data:rw` + `images-data:/data/images` (rw),
     frontend (nginx) — второй маунт `images-data:/data/images:ro` для
     alias-отдачи; том включается в бэкап-контур (tar images-data, design §7);
  3. **nginx-пара по образцу search-семейства**: `= /api/images` +
     `^~ /api/images/` (include images-headers.inc + images-proxy.inc,
     resolver+переменная, `client_max_body_size 12m`, деградация 503 JSON +
     Retry-After по паттерну `@search_down`) + `location /images/` alias
     в том (ro, expires 7d); `/gallery` остается на ядре (app:8377);
  4. **MODIFIED requirement «Лимиты памяти контейнеров»**: + images 128m —
     суммарные лимиты 1.54 GB (было 1.41 GB), резерв хосту ≥ 2.3 GB
     (требование ≥ 2 GB сохраняется; NFR-20).
- **REMOVED — нет.** Внепакетная дельта: `/api/auth/me` + ключ `id` (1.6,
  Э-7 — MODIFIED-дельту auth готовит СА) — тестовые последствия см. ниже.

## Влияние на существующие прогоны

- **Миграция добавляет 6 таблиц gallery — ядро их НЕ читает** (design §2:
  после миграции ядро таблицы gallery не трогает; владелец — сервис images).
  Существующие данные (tasks, comments, categories, sessions, users) не
  изменяются — обратная совместимость; регресс ядра по данным не ожидается.
- **nginx-конфиг меняется — паритет с search-семейством**: та же механика
  (`=` + `^~`, resolver+переменная, include, 503-деградация), уже проверенная
  на search (REPORT-regress-21/matrix-22); существующие маршруты
  (`/api/tasks`, `/api/search*`, `/avatars/`, netdata) не трогаются.
  Риск — только ошибки конфигурации при встраивании локаций ⇒ смоук соседей
  в матрице 2.1 обязателен.
- **`/api/auth/me` добавил ключ `id` (1.6) — Э-6: ME_KEYS-тесты tests/api
  красные на HEAD** (подтверждено review-002-1.5: 2 failed):
  `test_profile_r4.py` (`test_me_extended_composition`, `test_me_defaults_
  when_profile_empty`, строки 399/423) и `test_gaps_r4.py:322` фиксируют
  точный состав `ME_KEYS = {user, display_name, role, bio, avatar_url}` без
  `id`, а `backend/app/auth.py:126` теперь возвращает `id`. Это не регресс
  продукта (добавление ключа обратно совместимо для клиента), а устаревший
  ассерт точного множества — тесты подлежат обновлению силами QA в 2.1
  (вердикт **revalidate**, CHK-GAL-30); до обновления api-сьют дает 2 failed
  по известной причине.
- **Юниты services** (images 28/28, search 12/12 — подтверждено на HEAD,
  коммиты 3ebeec2/45eda39) — без изменений, keep.
- **web-регресс**: известные пред-существующие фейлы прочих доменов
  воспроизведены на чистом HEAD (3ebeec2) — к галерее не относятся.

## Таблица вердиктов

| Существующий набор | Вердикт | Обоснование |
|---|---|---|
| Регресс ядра tests/api (кроме ME_KEYS) | **keep** | Ядро не читает таблицы gallery, маршруты ядра не изменены; клиенты существующих API не затронуты |
| Регресс ядра tests/web | **keep** | Сайдбар дополняется 4-м пунктом (ADR-независимо, без role-рендера); существующие страницы/локаторы не переименовываются; навигационные тесты гоняются на новом стеке |
| Search-сьют (test_openapi_search_service, test_search*, test_suggestions*) | **keep** | nginx-паттерн images — копия search-семейства; маршруты search не тронуты; контракт search заморожен (TC-openapi-201/202) |
| Юниты services/search (12) | **keep** | Сервис не изменяется данным пакетом |
| Юниты services/images (28, TC-gal-101…105) | **keep** | Уже прогнаны green на HEAD (1.2/1.6); продолжают действовать как контракт сервиса |
| ME_KEYS-тесты (test_profile_r4 ×2, test_gaps_r4 TC-profile-r4-101) | **revalidate** | Э-6: точные ассерты множества ключей /me устарели (добавлен `id`); обновление ассертов — QA 2.1, CHK-GAL-30; известны красными на HEAD (2 failed, review-002-1.5) |
| Deploy-кейсы add-containerization (CHK-R11, деплой-проверки матрицы) | **keep** | Схема матрицы сохраняется (бэкап→build→миграция→up→healthy→смоук), расширяется носителей: +images, +миграция gallery, +том images-data, +смоук /api/health images и /gallery 200/401 |
| docker-stats/лимиты (NFR-20) | **revalidate** | MODIFIED requirement deploy: суммарные лимиты изменились (1.41→1.54 GB) — проверка резерва перегоняется с новым числом (CHK-GAL-28) |
| Новые gallery-проверки CHK-GAL-1…30 | **new** | Полный чеклист add-gallery-service (services/images-маршрутизация, том, лимиты NFR-21, категории/теги FR-80, реакции FR-81, комментарии FR-82, full-screen FR-83, доступ FR-84, navigation FR-85/86, design_validator, миграция, ME_KEYS) |
| Retire | — **нет** — | Ни один существующий кейс не теряет актуальности: удаляемых маршрутов/поведений дельта не содержит |

Итого по вердиктам: **keep — 7 наборов, revalidate — 2 (ME_KEYS, лимиты
NFR-20), new — CHK-GAL-1…30, retire — 0.**

## Риски для 2.2 (прод)

- **Репетиция миграции на копии прод-БД ОБЯЗАТЕЛЬНА** (deploy-спека, урок
  Р4; design §7, CHK-GAL-29): 6 таблиц + индексы, повтор no-op, автосверка
  exit 1 при расхождении — до выкатки.
- **Бэкап перед выкаткой расширяется**: БД (python-sqlite3 .backup) +
  аватары (tar) + **tar images-data** — том новый, пустой, но включается в
  контур бэкапов с первого релиза; пропуск images-data делает последующие
  бэкапы неполными.
- **Откат = предыдущим тегом всей матрицы** (единый RELEASE_TAG): код
  откатывается целиком (app+frontend+images); таблицы gallery обратной
  совместимости не мешают — ядро их не читает, при откате БД можно не
  возвращать (решение по факту инцидента, пара «код+БД» — по общему правилу).
- **Память хоста**: резерв падает с ≥2.4 до ≥2.3 GB — при фактическом
  потреблении images сверх 128m (замер 1.3/2.1) эскалация до Заказчика до
  прод-выкатки (NFR-20).
- **Эскалации, живущие вне пакета**: Э-7 (MODIFIED-дельта auth у СА) и О-1
  (мокап лайтбокса vs факт) — не блокеры тестирования 2.1, но должны быть
  закрыты до приемки 2.2.
