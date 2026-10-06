# Ревью 001 — пакет add-gallery-service: задачи 1.2 + 1.3 + 1.4 (один файл на три задачи)

Reviewer-Delegation: deleg-0e211c2888f747ab

- Дата: 2026-10-05 | Ветка: `add-gallery-service` | Worktree:
  `/home/openclaw/ekotov-wiki-worktrees/dev-12-gallery`
- **Охват:** настоящий файл покрывает ТРИ задачи пакета: **1.2** (сервис
  images — коммиты `55ea2dc`, `d8a8bce`; приемка ПМ `540b8ef`), **1.3**
  (миграция + compose — `45eda39`, `1001d13`), **1.4** (nginx — `9fdb0bf`).
- Автор диффа: dev-делегации (не я — независимое ревью).
- Метод: спека как закон (requirements/design/tasks + дельты
  `specs/{gallery,services,deploy}`; design §2/§3/§4 — дословно) → best
  practices → интеграция. Отчеты девов (REPORT-1.2/1.3/1.4) не принимались
  на веру: каждое заявление проверено по диффу/коду/прогону.
- Зоны диффа: `services/images/**`, `backend/app/migrate_gallery.py`,
  `deploy/compose*.yaml`, `services/frontend/**` — выхода за зоны задач нет
  (единственное пересечение — `services/images/Dockerfile` внесен в 1.3 вне
  заявленных границ задачи, по эскалации E1 и с ведома ПМ — процессное
  наблюдение, не дефект кода).

---

## Круг 1 — спека как закон

### 1.2 сервис images (services/images/**)

Сверено с design §2/§3 и дельтой specs/gallery по каждому пункту:

| Требование (design §3 / дельта) | Реализация | ✓ |
|---|---|---|
| `POST /api/images` multipart; тип по magic-байтам (JPEG/PNG/GIF/WebP), размер ≤10 МБ, 422, файл НЕ сохраняется | `app/images.py`: `detect_mime` (JPEG/PNG/GIF87a/89a/WebP RIFF..WEBP), размер проверен ДО декодирования и ДО записи; `gallery.py:upload_image` пишет файлы только после валидации; тесты фиксируют пустой том и пустую БД при 422 | ✓ |
| Имя файла генерирует сервер, расширение по фактическому типу | `uuid4().hex + ext` по mime (`_EXT_BY_MIME`); original_name — в БД | ✓ |
| Превью Pillow, длинная сторона ≤800px, JPEG на upload | `make_thumbnail` (LANCZOS, без апскейла, первый кадр GIF/WebP), тесты проверяют JPEG и ≤800 | ✓ |
| Метаданные + связи — одна транзакция | один `commit()` на upload; при провале INSERT файлы удаляются (без сирот в основной ветке) | ✓ |
| `GET /api/images?category=&tag=` — фильтры комбинируются, пустые = все, created_at DESC, счетчики + мой голос | параметризованный SQL, EXISTS-подзапрос по тегу, `ORDER BY created_at DESC, id DESC`, коррелированные подзапросы likes/dislikes/comments/my_reaction — тест `test_list_filters_combine` покрывает комбинацию | ✓ |
| `GET /api/images/{id}` — метаданные + реакции + комментарии (автор display_name/логин, created_at) | `_LIST_SELECT` + JOIN users с COALESCE | ✓ |
| Реакции: ровно один голос; смена; снятие повтором того же знака; явное снятие DELETE | upsert по PK (image_id,user_id) + ветка удаления при совпадении значения; DELETE снимает только свой знак; тест `test_reaction_flow` — полный цикл + PK-инвариант в БД | ✓ |
| Комментарии: непустой после trim → иначе 422; удаление только своего, чужой → 403, нет → 404 | `add_comment`/`delete_comment`; тесты на «», «   », None, 403, 404 | ✓ |
| 401 без сессии на все API, включая /openapi.json; /api/health exempt, без БД-запроса | `middleware.py` (паттерн search, SELECT-only по sessions — записи в sessions нет, скользящий TTL остается ядру — соответствует спеке services «таблицы ядра не изменены») | ✓ |
| RW-профиль: только таблицы gallery + `SELECT users`; busy_timeout; WAL не трогается; foreign_keys=ON | `db.py`: busy_timeout=5000, journal_mode НЕ выполняется; в коде INSERT/UPDATE только в 6 таблиц gallery (проверено поиском по всем execute) | ✓ |
| Удаление изображений — не-цель (design §8) | эндпоинта DELETE /api/images/{id} нет; openapi-тест фиксирует ровно 7 путей | ✓ |

Схема в фикстуре тестов дословно = design §2 (6 таблиц, PK, CHECK, UNIQUE,
4 индекса, FK-цели и CASCADE) — независимо сверена с `GALLERY_DDL`
миграции: **паритет**.

### 1.3 миграция + compose (backend/app/migrate_gallery.py, deploy/compose*.yaml, services/images/Dockerfile)

- 6 таблиц + 4 индекса дословно design §2; идемпотентность IF NOT EXISTS;
  все DDL в одной транзакции BEGIN IMMEDIATE; guard на отсутствие users.
- Автосверка (design §7 «exit 1 при расхождении»): таблицы/колонки/составные
  PK/FK-цели+ON DELETE/CHECK/UNIQUE/индексы — реализована и
  **независимо проверена мной негативом** (см. ниже).
- Compose прод и стенд (проверено yaml.safe_load обоих файлов): images —
  mem_limit 128m (design §5 / MODIFIED deploy «Лимиты памяти»), healthcheck
  urllib :8379, logging json-file 10m×3, restart unless-stopped, depends_on
  app, **порты не публикуются** (design §1, спека gallery MUST NOT
  публиковать), тома `wiki-data:/data:rw` + `images-data:/data/images`
  (спека services «RW-маунт общей БД» + «Данные изображений в отдельном
  томе»); стенд — зеркально с томами проекта (`wiki-test-data`,
  `images-test-data`, изоляция NFR-10).
- Dockerfile images: пины deps синхронны backend/requirements.txt
  (fastapi 0.141.1, uvicorn[standard] 0.53.0, Pillow 12.3.0,
  python-multipart 0.0.32 — сверено), USER 10001, HEALTHCHECK = compose,
  данных в образе нет, EXPOSE 8379 — паритет app/search.
- Замер RAM 35.68 MiB/128m (idle) зафиксирован в REPORT-1.3 (п. (в)
  задачи 1.3); контроль под нагрузкой — по плану в 2.1.

### 1.4 nginx (services/frontend/**, маунты в compose)

Сверено с design §1/§4 и спекой gallery («Маршрутизация nginx»,
«Деградация при отказе images», «Отдача файла nginx из тома»):

- Пара `= /api/images` + `^~ /api/images/` — по образцу search-семейства;
  в обоих локациях включены ОБА include (headers + proxy); `^~` отключает
  regex — семейство не перебивается будущими локациями.
- `images-proxy.inc`: `$upstream_images http://images:8379` + resolver
  server-блока 127.0.0.11 valid=10s (анти-stale-DNS; имя сервиса совпадает
  с именем сервиса в ОБОИХ compose — сверено); URI не переписывается;
  `client_max_body_size 12m` — согласован с NFR-21 (10 МБ + multipart),
  перекрывает server-лимит 2m именно на локациях images (остальной стек
  не ослаблен — проверено: директива только в images-proxy.inc);
  `proxy_next_upstream error timeout` + `proxy_intercept_errors` +
  `error_page 502 503 504 = @images_down` — быстрый управляемый 503
  (паттерн @search_down, живой прецедент прода).
- `images-headers.inc`: X-Service: images + повтор security-заголовков
  (NFR-7; add_header в location наследуется с перекрытием — набор
  идентичен search-headers.inc).
- `location /images/` — `alias /data/images/` + expires 7d — паритет
  `/avatars/`; alias указывает точно на маунт-точку тома (файлы сервис
  кладет в корень images-data — сверено с `app/gallery.py`), глубина
  маунта = глубине alias (учет тома avatars) в ОБОИХ compose.
- `@images_down` — internal, JSON + Retry-After: 5 — паритет @search_down.
- Маунт `images-data(–test-data):/data/images:ro` в frontend — в ОБОИХ
  compose-файлах (yaml-парс подтверждает); согласованность томов с
  images-сервисом (ro у nginx / rw у images) — полная.
- Dockerfile frontend: COPY обоих include — файлы реально попадают в образ.

Отклонений от MUST/SHOULD спеки не найдено. Замечания по тексту
документации и два дефекта спеки (эскалации Э-1/Э-2) — ниже.

## Круг 2 — best practices

- SQL: все запросы параметризованы (`?`), конкатенации пользовательских
  значений нет (WHERE собирается из фиксированных строк) — инъекций нет.
- Секреты: в коде/тестах нет паролей/ключей; конфиг только через env
  (EKOTOV_WIKI_DB_PATH/EKOTOV_WIKI_IMAGES_DIR; SECRET_KEY миграция не
  использует по существу — требование config.py ядра, задокументировано).
- Пути: имена файлов генерирует сервер (uuid4hex), имя клиента в БД
  только как original_name — path traversal через upload невозможен;
  nginx alias с фиксированным префиксом, `/images/../` нормализуется.
- Ошибки: пользователь видит коды 401/403/404/422/500 в форме ядра
  ({"error": ...}), стек-трейсов нет; sqlite3.Error → 500 + rollback.
- Транзакции sqlite: короткие (commit на операцию), busy_timeout, WAL не
  переключается — инварианты design §2 соблюдены.
- Pillow: декодирование полного образа до записи — DecompressionBomb
  защита Pillow активна по умолчанию (превышение → 422 not_image); битые
  файлы отклоняются до диска (тест есть).
- Данные в git: БД/тома в репозиторий не попадают; __pycache__ в индекс
  не попал (git ls-files — чисто).

## Круг 3 — интеграция

- Цепочка 1.2 → 1.3 → 1.4 соблюдена (порядок коммитов и зоны); 1.3 создает
  схему, images схему не мигрирует (спека services «Схему создает ядро») —
  в коде сервиса миграций нет.
- Паритет прод/стенд compose — построчно (yaml): идентично, кроме
  имен томов и тега образа — NFR-10 выполнен.
- Согласованность томов images-data: images rw `/data/images`, nginx ro
  `/data/images` — имена томов совпадают внутри каждого файла, стенд
  изолирован; nginx не может писать (ro) — файловая гарантия отдачи.
- Upstream `images:8379` = имя сервиса + EXPOSE/CMD порта — совпадают.
- Соседние сценарии: регресс search-сьюита 12/12 (эталонный сервис не
  задет); `openspec validate --all --strict` — 15 passed, 0 failed
  (прогон мной в worktree); существующие локации nginx (static, avatars,
  search-семейство, location /) не тронуты — дифф только добавляет блок
  images-семейства и @images_down.
- Бэкап images-data: в контур включается задачей 2.2 (tasks.md; backup
  sidecar пока DB+avatars — по плану пакета, дефекта нет).

## Независимая верификация (мой прогон, не из отчетов)

| Проверка | Результат |
|---|---|
| Юниты images: `EKOTOV_WIKI_DB_PATH/EKOTOV_WIKI_IMAGES_DIR=tmp`, venv /home/openclaw/venvs/wiki | **26 passed** |
| Регресс search (эталон не задет) | **12 passed** |
| Миграция: свежая БД (после `python -m app.db`) | 6 таблиц + сверка ОК, **exit 0** |
| Миграция: повторный прогон | no-op «Создано таблиц: 0», сверка ОК, **exit 0** |
| Миграция: негатив (сломан PK image_reactions + убран CHECK, users на месте) | «FAIL: PK=…», «FAIL: CHECK … не найден», **exit 1** |
| Миграция: чистая БД без users | guard FAIL, exit 1 |
| `yaml.safe_load` deploy/compose.yaml + compose.test.yaml | mem_limit 128m / no ports / healthcheck :8379 / depends_on app / logging 10m×3 / тома rw+ro / стенд-паритет — **все инварианты** |
| nginx-конфиг (чтение + структурная сверка с search-паттерном) | локации/include/alias/expires/12m/@images_down/resolver — соответствие |
| `openspec validate --all --strict` | **15 passed, 0 failed** |

## Эскалации (дефекты спеки — оркестратору; по регламенту НЕ являются основанием return задачи)

- **Э-1.** Проверка ТЗ 1.4 «`/api/health` images через nginx 200» в такой
  формулировке неинформативна: `/api/health` не матчится `^~ /api/images/`
  и уходит в `location /` → **app:8377**; «200» будет ответом ЯДРА даже при
  остановленном images (false positive для QA 2.1). Доступного через nginx
  маршрута именно к health images нет (compose-healthcheck ходит на
  127.0.0.1:8379 внутри контейнера — это корректный health-гейт).
  Предложение: в чек-листе 2.1 заменить проверку на «GET /api/images без
  сессии → 401» (доказывает живость images через nginx) + 503-чек при
  остановленном images; health images — только compose-healthcheck.
- **Э-2.** design §3 декларирует `GET /api/images?category=<id>&tag=<name>`,
  реализация фильтрует по ИМЕНИ категории (`c.name = ?`), сценарий дельты
  specs/gallery тоже формулирует фильтр по имени («категории „семья"»).
  Спека внутренне неоднозначна (id vs имя). До старта 1.5 (фронтенд
  выбирает, что слать) оркестратору зафиксировать контракт; коду
  рекомендация — принимать id и имя (как `_resolve_category` на upload).

## Таблица замечаний

| # | Серьезность | Файл:строка | Замечание | Рекомендация |
|---|---|---|---|---|
| 1 | minor | services/frontend/nginx/ekotov-wiki.conf:125–132 | Неверный комментарий: утверждает, что healthcheck frontend (`wget /api/health`) «попадает в ^~-локацию и обслуживается images» — фактически `/api/health` матчится `location /` → app. Введение в заблуждение при диагностике и приемке (связано с Э-1) | Исправить комментарий при следующем касании конфига; никаких изменений маршрутизации не требуется |
| 2 | minor | services/images/app/gallery.py:264–266 | Фильтр `category` сверяется только с именем; design §3 декларирует `category=<id>` (неоднозначность спеки — Э-2); при выборе фронтом id фильтр вернет пусто | Принимать id и имя (по образцу `_resolve_category`) или дождаться решения Э-2 до 1.5 |
| 3 | minor | services/images/app/gallery.py:133–135 | Если запись/сохранение превью падает после записи оригинала (OSError/PIL), cleanup-блок (охватывает только провал INSERT) не сработает — файл-сирота в томе | Расширить try/очистку на запись обоих файлов (unlink в общем except) |
| 4 | minor | services/images/app/gallery.py:105 | `await file.read()` читает тело целиком в память; в целевой топологии ограничено nginx 12m и закрытыми портами, но сам сервис размер потока не ограничивает | Принять осознанно (зафиксировать в README); при изменении топологии — потоковое чтение с лимитом |
| 5 | minor | backend/app/migrate_gallery.py:262–270 | Проверка CHECK — substring («CHECK» + «1» + «-1»): неверный CHECK (напр. `value > -1`) пройдет; FK сверяется без колонки `to` (row[4]) | Ужесточить регэкспом `CHECK\(value IN \(1,\s*-1\)\)` (нормализация кавычек уже есть) и сверять `to` |
| 6 | minor | services/images/Dockerfile:36–38 + deploy/deploy.sh | Комментарий Dockerfile обещает «владелец томов приводится deploy-скриптом/при первом старте» — шага для images-data в deploy.sh нет; прецедент wiki-data/app (тот же uid 10001) работает, но upload на стенде еще не выполнялся (замер RAM был idle) | В 2.1 смок upload обязателен первым (сразу вскроет EACCES); при необходимости — chown 10001 тома по образцу 2.4-switch.sh |
| 7 | minor | services/images/app/gallery.py:428–433 | Длина тела комментария и имен тегов/категорий не ограничена (многомегабайтный body ляжет в БД; лимит запроса 12m) | Мягкий лимит (напр. 2000 символов → 422) при следующем касании; срочно — нет (2 пользователя, trusted) |
| 8 | minor | services/images/tests/test_images_service.py:205–206, 250 | Мертвый код в тесте (for…pass), лишний walrus — гигиена | Убрать при следующем касании тестов |
| 9 | minor | services/frontend/nginx/ekotov-wiki.conf:149–154 | В `location /images/` security-заголовки server-уровня не наследуются (add_header в location перекрывает) — HSTS/X-Frame на файлах отсутствуют; плюс expires+add_header дают двойной Cache-Control. Паритет существующим /static/ и /avatars/ — устоявшийся паттерн стека | Опционально: собрать заголовки images-файлов в include по образцу images-headers.inc; поведение не хуже принятого в стеке |

**Blocker: 0 | Major: 0 | Minor: 9.** Ни одно замечание не блокирует
слияние задач 1.2/1.3/1.4; замечания 1, 2 и эскалации Э-1/Э-2 желательно
закрыть до старта QA 2.1 и задачи 1.5 соответственно.

## Проверенные Scenario (выборка по трем задачам)

- gallery: «Валидная загрузка», «Негативный: превышение размера»,
  «Негативный: недопустимый тип» (+битое содержимое), «Загрузка с категорией
  и тегами»/«без», «Фильтр по категории/тегу», «Комбинация», «Пустой фильтр»,
  «Постановка лайка», «Смена голоса», «Снятие голоса повторным действием»,
  «Негативный: без сессии реакция недоступна», «Добавление и просмотр
  комментария», «Негативный: пустой комментарий», «Удаление своего»,
  «Негативный: чужой → 403», «Негативный: без сессии API → 401»,
  «Отдача файла nginx из тома» (статически: alias/маунт/expires),
  «Деградация при отказе images» (статически: паттерн @images_down),
  «Лимит images применен» (compose 128m + факт-замер idle в REPORT-1.3)
- services: «RW-маунт общей БД», «Границы записи» (тест core_tables_untouched
  + инспекция всех execute), «Схему создает ядро, сервис не мигрирует»,
  «Данные изображений в отдельном томе»
- deploy (MODIFIED): «Лимиты применены» — mem_limit images 128m в обоих
  compose, сумма 1.54 GB сходится
- 401-матрица всех 9 эндпоинтов + /openapi.json (тест), роутер openapi
  ровно = design §3

## Что НЕ проверено (честно)

- Живой стенд: `nginx -t`, 200/401/503/кеш-заголовки через nginx, поведение
  `/gallery` — docker в сессии недоступен; согласованное ограничение среды
  (SKIPPED в отчетах девов честно), проверка переносится на QA 2.1 —
  **не дефект кода**.
- docker build образов (images/frontend), фактический запуск контейнеров,
  запись uid 10001 в свежий том images-data (замечание 6).
- RAM images под нагрузкой (upload-пачка) — план 2.1; репетиция миграции на
  копии прод-БД — обязательный шаг 2.2.
- Фронтенд 1.5, design_validator, прод-приемка 2.2 — вне объема этого ревью.

## Вердикт: **ОДОБРИТЬ**

Задачи 1.2, 1.3, 1.4 соответствуют спеке (requirements, design §1–§5/§7,
дельты specs) и проверены независимо: юниты 26/26, регресс search 12/12,
миграция fresh/no-op/негатив exit-коды подтверждены, compose-паритет
прод/стенд и nginx-структура сверены, openspec validate 15/15. Blocker/major
нет; 9 minor-замечаний с рекомендациями (таблица выше) в код не блокируют;
два дефекта спеки (Э-1, Э-2) эскалируются оркестратору вне вердикта задачи.
