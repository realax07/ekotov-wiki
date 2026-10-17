# sdd.md — Системный дизайн: change video-hosting (P11 «Видеохостинг wiki»)

Источник требований: `openspec/changes/video-hosting/requirements.md`
(DRAFT r2; решения Заказчика ОВ-1…ОВ-4 — PLAN-video-hosting.md, 2026-10-17;
r2 — кусок D «Социальный слой» + превью в B по утвержденным мокапам).
Файл дополняет корневой `sdd.md` и не заменяет его: стек, компоненты,
авторизация и контракты действуют без изменений. Техрешения — `design.md`;
здесь — декомпозиция модулей, контракты, модель данных, трассировка.
tasks.md пишет архитектор после ревью пакета (Флоу 1).

## 1. Стек и компоненты

Без изменений (корневой sdd: nginx + FastAPI + SQLite WAL + Jinja2/
ванильный JS; ОГР-8 — новых рантайм-зависимостей frontend нет). Новый
компонент — **контейнерный сервис `video`** (`services/video/`, FastAPI +
uvicorn 1 воркер :8380 + **статический ffmpeg/ffprobe бинарь в образе**,
без apt). Решение «сервис vs роутер в ядре» — по критериям
service-decomposition §1: свой том данных вне БД ядра (`videos-data`,
критерий «отдельный том»), независимая деградация (503 от nginx — ядро
живо), независимый деплой по тегам — три сильных критерия, прецедент
images. Состояние конвертации — память процесса (очередь) + статус в БД;
брокер не вводится (design §3, YAGNI при 2 пользователях).

## 2. Границы модулей монолита services/video (швы по service-decomposition §4)

Модульный монолит внутри сервиса: единица резки — зона файлов, шов —
непересекающиеся зоны записи. 1–3 разработчика — модули, не микросервисы.

| Модуль | Зона (файлы) | Ответственность | Шов (кто его вызывает) |
|---|---|---|---|
| `app/main.py` | `services/video/app/main.py`, `services/video/Dockerfile` | FastAPI-вход: роутеры, 422-обработчик, сессионный middleware, `/api/health` (копия паттерна images/search) | включает `videos_router`, `converter.start_worker()` на старте |
| `app/videos.py` | `services/video/app/videos.py` | API: upload (pre-check 500 МБ → storage, опц. category_id), list (поиск/сортировка/фильтр категории), delete, file/preview, authcheck; JSON-формы ответов | вызывает `storage.*` и `converter.enqueue()`; НЕ вызывает subprocess и SQL напрямую |
| `app/social.py` | `services/video/app/social.py` | API социального слоя (кусок D): комментарии (список/добавить/удалить — только свои), реакция (один голос: toggle/перенос), список категорий из `image_categories` | вызывает `db.*`; проверка владения комментарием — здесь; счетчики голосов — SQL-агрегаты через db |
| `app/storage.py` | `services/video/app/storage.py` | Единственный владелец путей тома: `<id>/original.*`, `<id>/video.mp4`, `<id>/preview.jpg`; сохранить/удалить каталог/путь файла; uuid | вызывают `videos.py` и `converter.py`; Никто больше не строит путей (path traversal — design §8) |
| `app/converter.py` | `services/video/app/converter.py` | Очередь `queue.Queue` + поток-воркер (серийно): subprocess ffmpeg/ffprobe (nice 10, timeout 30 мин), превью-кадр `preview.jpg` тем же проходом (в т.ч. для уже-mp4 — быстрый `-frames:v 1`; r2: кусок B, не C), статусы БД, ровно 1 ретрай, удаление оригинала при успехе, отмена при delete, крэш-восстановление на старте (re-enqueue `uploaded` И `converting` — design §3) | читает/пишет статус через `db.*`, файлы — через `storage.*`; API узнает о готовности только по БД |
| `app/db.py` | `services/video/app/db.py` | Единственный слой SQL: RW `video_videos` + `video_comments` + `video_reactions`, SELECT `users`, `image_categories` (паритет images/app/db.py: short transactions, busy_timeout) | вызывают `videos.py`, `social.py` и `converter.py` |
| `app/middleware.py` | `services/video/app/middleware.py` | Сессионный middleware (копия images: без права писать в sessions), exempt: `/api/health`, `/api/videos/authcheck`; D-эндпоинты НЕ exempt (NFR-38) | регистрирует `main.py` |

Правила швов (НЕЛЬЗЯ делить / нельзя нарушать):

- **Пути файлов** — только через `storage.py`: `videos.py`/`converter.py`
  не конструируют пути из пользовательских имен (design §8).
- **subprocess ffmpeg** — только в `converter.py` (одна точка таймаута,
  nice, ретрая); `videos.py` отвечает только за HTTP-слой.
- **Писатель статуса** — только поток-воркер `converter.py`; API — читатель
  (один писатель — нет гонок, design §3).
- `videos.py` + `main.py` — общая зона HTTP-форм ответов: задачи по ним —
  последовательные, не [P].
- **Социальный слой** — отдельный модуль `social.py` (r2, кусок D):
  комментарии/реакции/категории живут ТОЛЬКО в его зоне; `videos.py`
  не знает о реакциях (в list отдаст готовые агрегаты из db). Зона
  `social.py` не пересекается с зоной `videos.py` — задача D по API
  может идти после (последовательно) задач ядра.

## 3. Контракты API (метод, путь, схема, коды)

Общее: без валидной сессии — 401 `{"error": "unauthorized"}` (NFR-36);
ошибки валидации — 422 в форме ядра `{"error": "validation error",
"details": {...}}`; страницы: `/video` в ядре (редирект на `/login` без
сессии). Exempt middleware: `/api/health`, `/api/videos/authcheck`.

| Метод/путь | Описание | Ответы |
|---|---|---|
| `POST /api/videos` | Загрузка multipart-файла (любой формат); лимит 500 МБ проверяется ДО записи на диск; опц. поле `category_id` (NULL = «Без категории»; валидация: значение существует в `image_categories`); ставит в очередь конвертации | 201 `{id, filename, status: "uploaded", size, category_id}`; 401; 422 (файл больше 500 МБ / пустое тело / category_id не найден) |
| `GET /api/videos` | Список: `?query=<подстрока>&order=asc\|desc&category=<id\|none>` (по имени, регистр не учитывается; пустой query — все; category=none — «Без категории») | 200 `{"videos": [{id, filename, status, size_bytes, created_at, preview_url, file_url, category_id, category_name, likes, dislikes, my_reaction}]}`; 401 |
| `DELETE /api/videos/{id}` | Удаление: том (`<id>/` целиком) + метаданные + CASCADE комментарии/реакции; отменяет идущую конвертацию | 200 `{"ok": true}`; 401; 404 |
| `GET /api/videos/{id}/file` | mp4 (готовое видео; для `<video>` и скачивания; паритет 401-маршрут — основной поток идет через nginx `/videos/`, design §5) | 200 (видео/mp4, Range-friendly); 401; 404; 409 (статус не `ready` — плеер не запускается) |
| `GET /api/videos/{id}/preview` | Превью-кадр (готовое видео) / 409 для плейсхолдера | 200 (jpeg); 401; 404; 409 (не `ready`) |
| `GET /api/videos/{id}/comments` | Комментарии видео (автор, время, текст) — кусок D | 200 `{"comments": [{id, user_id, user, text, created_at}]}`; 401; 404 |
| `POST /api/videos/{id}/comments` | Добавить комментарий `{text}`; пустой/whitespace-текст отклоняется — кусок D | 201 `{id, text, user, created_at}`; 401; 404; 422 |
| `DELETE /api/videos/{id}/comments/{cid}` | Удалить комментарий — ТОЛЬКО свой (чужой = 403) — кусок D | 200 `{"ok": true}`; 401; 403 (чужой); 404 |
| `PUT /api/videos/{id}/reaction` | Голос `{value: 1\|-1}`: ровно один голос на пользователя — тот же value снимает голос, противоположный переносит (PK(video_id,user_id), upsert/delete) — кусок D | 200 `{my_reaction, likes, dislikes}` (my_reaction=null после снятия); 401; 404; 422 |
| `GET /api/videos/categories` | Справочник категорий — SELECT из существующей `image_categories` (новый НЕ создается; RO) — кусок D | 200 `{"categories": [{id, name}]}`; 401 |
| `GET /api/videos/authcheck` | Стык nginx auth_request (design §5): 200/401 по сессии, без чтения БД тяжелее проверки сессии | 200 `{}`; 401 |
| `GET /api/health` | Healthcheck (exempt, без БД-запроса — паритет images/search) | 200 `{"status": "ok"}` |

nginx-маршруты (design §6): `= /api/videos`, `^~ /api/videos/`,
`/videos/` (alias тома ro + auth_request), `/_video_auth` (internal).
Плеер: нативный `<video src="/videos/<id>/video.mp4">` (ОГР-8 — без CDN);
`faststart`-mp4 поддерживает прогрессивную отдачу.

## 4. Модель данных (дельта)

```sql
video_videos (
  id               TEXT PK,            -- uuid4; же имя каталога в томе videos-data/<id>/
  filename         TEXT NOT NULL,      -- исходное имя (метаданные; путь из него НЕ строится)
  status           TEXT NOT NULL,      -- uploaded | converting | ready | error
  size_bytes       INTEGER NOT NULL,   -- актуальные файлы (после успеха — mp4+preview)
  mime             TEXT,               -- исходный mime (по факту; белый список НЕ применяется)
  uploaded_by      INTEGER NOT NULL,   -- FK users(id) — SELECT, имя загрузившего
  created_at       TEXT NOT NULL,      -- ISO-8601
  convert_attempts INTEGER NOT NULL DEFAULT 0,  -- 0..2; 2 + error = исчерпание ретрая
  category_id      INTEGER,            -- r2 (кусок D): NULL = «Без категории»;
                                       -- FK image_categories(id) — СУЩЕСТВУЮЩИЙ
                                       -- справочник галереи, только SELECT (RO);
                                       -- новый справочник НЕ создается
)
```

Таблицы социального слоя (r2, кусок D; паттерн image_comments/
image_reactions галереи, FR-81/82):

```sql
video_comments (
  id         TEXT PK,                  -- uuid4
  video_id   TEXT NOT NULL,            -- FK video_videos(id) ON DELETE CASCADE
  user_id    INTEGER NOT NULL,         -- FK users(id) — SELECT, автор
  text       TEXT NOT NULL,            -- непустой (валидация API, 422)
  created_at TEXT NOT NULL             -- ISO-8601
)

video_reactions (
  video_id   TEXT NOT NULL,            -- FK video_videos(id) ON DELETE CASCADE
  user_id    INTEGER NOT NULL,         -- FK users(id)
  value      INTEGER NOT NULL CHECK (value IN (1, -1)),  -- лайк/дизлайк
  created_at TEXT NOT NULL,
  PRIMARY KEY (video_id, user_id)      -- уникальность голоса: ровно один
                                       -- голос на пользователя; toggle=DELETE,
                                       -- перенос=UPDATE value
)
```

- Владелец схемы — сервис `video` (RW-своей-схемы): `video_videos` +
  `video_comments` + `video_reactions`; ядро НЕ пишет (первичное создание
  — one-shot миграция ядра по запросу владельца, паттерн migrate_gallery;
  design §7). `image_categories` — только SELECT (RO, справочник
  галереи; запись/изменение категорий остается у галереи).
- Тома: `videos-data` (RW у `video`, ro у frontend для alias-отдачи —
  паритет images-data). Файлов в БД нет (NFR-паттерн FR-79). Превью-кадр
  (`<id>/preview.jpg`) — в томе рядом с mp4 (r2: генерится в куске B
  воркером, в т.ч. для уже-mp4).

## 5. Сквозные процессы (service-decomposition §3)

| Процесс | Сегменты | Контракт стыка | Деградация | Смоук |
|---|---|---|---|---|
| Загрузка+конвертация | nginx → video API → том → поток-воркер → БД-статус → список | лимит 500 МБ согласован nginx (520m) и сервисом (до записи); статусы UI ← БД | nginx 503 при отказе video; статус «ошибка» с сохраненным оригиналом при неудаче ffmpeg | QA-набор «смок» пакета (стенда/прод) |
| Playback | nginx auth_request → video authcheck → alias тома → `<video>` | authcheck 200/401; 401-редирект на /login | без сессии — 401/редирект (файл не отдается, NFR-36) | тот же смок |
| Отказ сервиса | nginx → video (down) | error_page → быстрый JSON 503 | остальные разделы работают | тот же смок |
| Социальный слой (r2, кусок D) | nginx → video API (social) → БД (comments/reactions, SELECT image_categories) | 401 без сессии (NFR-38); 422 пустой комментарий; 403 чужой комментарий; один голос на пользователя (PK) | отказ video — 503 (D-операции недоступны вместе с сервисом, ядро живо) | тот же смок (комментарий → реакция → фильтр категории) |

Сегментные юниты — у dev; сквозная верификация — QA (этап прогонов пакета,
решение 2026-10-12).

## 6. Матрица трассировки: требования ТЗ → Requirement (video-service)

| Требование ТЗ (requirements.md) | Кусок | Приоритет | Requirement | Сценарии |
|---|---|---|---|---|
| «Раздел „Видео“ в сайдбаре и страница сервиса» | A | Must | Раздел «Видео» в сайдбаре и страница сервиса | 3 |
| «Отдельный контейнерный сервис video, файлы вне БД» | A | Must | Отдельный контейнерный сервис video, файлы вне БД | 3 |
| «Загрузка видео — любой формат, ≤ 500 МБ» | A | Must | Загрузка видео — любой формат, до 500 МБ | 2 |
| «Список видео и playback» | A | Must | Список видео и playback | 2 |
| «Удаление видео» | A | Must | Удаление видео | 2 |
| «Серверная конвертация в mp4 со статусами» | B | Must | Серверная конвертация в mp4 со статусами | 3 |
| «Удаление оригинала после успешной конвертации» | B | Must | Удаление оригинала после успешной конвертации | 2 |
| «Превью-кадр генерируется при конвертации» (r2: перенос из C в B) | B | Must | Превью-кадр генерируется при конвертации | 3 |
| «Сортировка и поиск по имени» | C | Should | Сортировка и поиск по имени | 1 |
| «Комментарии к видео» (r2) | D | Must | Комментарии к видео | 4 |
| «Лайки и дизлайки — один голос на пользователя» (r2) | D | Must | Лайки и дизлайки — один голос на пользователя | 3 |
| «Категории видео — общий справочник с галереей» (r2) | D | Must | Категории видео — общий справочник с галереей | 3 |
| «Вид интерфейса по утвержденному макету» (Д-паттерн) | 0 | Must | Вид интерфейса по утвержденному макету | 1 |
| NFR-35 «Ресурсы и здоровье сервиса video» | A+B | Must | Ресурсы и здоровье сервиса video (NFR-35) | 1 |
| NFR-36 «Доступ только авторизованный» | A | Must | Доступ только авторизованный, без публичных ссылок (NFR-36) | 1 |
| NFR-37 «Отзывчивость при фоновой конвертации» | B | Must | Отзывчивость при фоновой конвертации (NFR-37) | 1 |
| NFR-38 «Операции социального слоя — только авторизованные» (r2) | D | Must | Операции социального слоя — только авторизованные (NFR-38) | 2 |

Покрытие 17/17: каждая Requirements-глава requirements.md имеет ровно один
Requirement дельты (без дублей), 37 сценариев сохранены 1:1 (r1: 12/23;
r2 добавил кусок D + NFR-38 + превью в B, превью-сценарий убран из C).
Обрывов трассировки нет. Сквозная нумерация FR-117+…/NFR-35+ присваивается
при архивации в master-spec (последние использованные FR-116, NFR-34).

## 7. Ограничения и допущения

- Очередь конвертации — в памяти процесса: рестарт контейнера теряет
  очередь; компенсация — крэш-восстановление статуса `converting` на
  старте (design §3). Рост до брокера — осознанная точка расширения
  Уровня 2+ (шов: только `converter.py` знает об очереди).
- Ровно одна конвертация одновременно — достаточность при 2 пользователях;
  p95 NFR-37 замеряется именно в этом режиме.
- ffmpeg — оченьfast-пресет как баланс скорость/размер; параметры
  кодирования могут уточняться по замерам стенда (не меняют контракты).
- Имена пользователей в путях не участвуют; сортировка — по filename
  COLLATE NOCASE (без отдельного столбца-ключа).
- Справочник категорий куска D — только SELECT из `image_categories`
  (существующий, общий с галереей): создание/переименование категорий —
  зона галереи; video хранит FK, «Без категории» = NULL.
- Уникальность голоса — составной PK `video_reactions` (одна запись на
  пару видео+пользователь): toggle и перенос — атомарные upsert/delete
  в short-транзакции db.py.
- Дизайн-макет — утвержден Заказчиком 2026-10-17 (включая блоки куска D);
  обязательный предшественник dev-задач (позиция пункта сайдбара и
  плейсхолдер — финал на макете).
