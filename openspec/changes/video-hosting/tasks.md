# tasks.md — video-hosting (P11 «Видеохостинг wiki»)

Флоу 1 (полный: СА → дизайн → dev → QA → приемка Заказчика). Куски PLAN:
**0 дизайн → A ядро → D социальный слой → B конвертация (с превью) →
C полировка**, у каждого куска — живая приемка (урок J51/rich).
r2 (дополнение пакета, решение Заказчика 2026-10-17 при утверждении
мокапов): добавлен кусок D (комментарии/лайки-дизлайки/категории) и
превью-кадр перенесен из C в B; нумерация волн сдвинута (бывшие 2.x→3.x,
3.x→4.x, 4.x→5.x, 5.x→6.x — ссылки ревью №1: «задача 2.1» = конвертер =
сегодняшняя 3.1, «5.1» деплой = 6.1). r3 (мини-дельта после приемки 6.2,
решение Заказчика): добавлено переименование видео (паритет rename
изображений FR-97) — волна 7; Requirement и сценарии — в дельте
specs/video-service, строка скоупа — в proposal.md. Архитектурное ревью пакета —
`review-architecture.md` №1 (verdict APPROVE, находки F1/F2 устранены в
design/sdd); новое (кусок D, превью в B) — эволюция существующего
техрешения (таблицы-паттерн галереи, тот же воркер) — новых
архитектурных задач не порождает. Формат: задача = наблюдаемый результат +
критерий проверки + зона файлов + трассировка; 1 задача = 1 сабагент +
независимый ревьюер. Ворота: `openspec validate --all --strict` — change
green на каждом шаге. Порядок: 0 (мокапы утверждены) → 1 → 2 → 3 → 4
(QA-контур) → 5 → 6.

## Волна 0. Пакет и дизайн-фаза (Д-паттерн Р4/Р5)

- [x] 0.1 [docs] [S] СА: change-пакет + архитектурное ревью — proposal,
  requirements (12 Requirements / 23 сценария, DRAFT r1), design r1 (с
  устранением F1/F2), sdd, дельта specs/video-service; ревью —
  `review-architecture.md` №1 (APPROVE); нарезка — настоящий tasks.md.
  Проверка: `openspec validate video-hosting --type change --strict` — green.
  Зона: `openspec/changes/video-hosting/**`. (утверждено: ревью №1)
- [x] 0.2 [design] [M] ui_designer: мокапы страниц «Видео» в `design/` —
  standalone HTML по токенам V3 «Бумага», без внешних библиотек/CDN (ОГР-8):
  (а) страница `/video` — список карточек (превью-кадр, имя, статус, размер,
  дата; плейсхолдер несконвертированного; индикатор конвертации);
  (б) форма загрузки с индикацией прогресса и ошибки лимита 500 МБ;
  (в) встроенный плеер `<video>`; (г) подтверждение удаления;
  (д) пункт сайдбара «Видео» после «Галерея», иконка в едином стиле
  (эталон «Мониторинг»/«Галерея»). Зона: `design/**` только.
  Проверка: мокапы открываются без сети, токены V3, все 5 состояний
  присутствуют. (design §0; Requirements «Раздел „Видео"…», «Вид интерфейса…»)
  (утверждено: `design/video-hosting/`, ревью №1)
- [x] 0.3 [design] Развилка Заказчика: утверждение мокапов 0.2 — волны 1–3
  НЕ стартуют до зафиксированного утверждения (прецедент Д-5). Позиция
  пункта сайдбара и вид плейсхолдера/индикатора — финал здесь.
  Проверка: решение Заказчика зафиксировано (approval_ref оркестратора).
  (requirements «Открытые вопросы»; design §0)
  (утверждено Заказчиком 2026-10-17, включая блоки куска D — комментарии/
  лайки-дизлайки/категории; r2 волны 1–4 стартуют без дополнительной
  развилки: блоки D в утвержденных мокапах)

## Волна 1. Кусок A — ядро сервиса (после 0.3)

- [x] 1.1 [migration] [S] Dev: one-shot миграция ядра `backend/app/
  migrate_video.py` — таблица `video_videos` по схеме sdd §4 (id TEXT PK
  uuid4, filename, status, size_bytes, mime, uploaded_by FK users,
  created_at, convert_attempts DEFAULT 0), идемпотентно (CREATE IF NOT
  EXISTS), одна транзакция BEGIN IMMEDIATE, автосверка структуры (паттерн
  migrate_gallery/migrate_wiki); ядро больше НИЧЕГО не пишет в таблицу
  (владелец — сервис video). Включение в деплой: `MIGRATE_MODULE` в 6.1
  (строго до up). Проверка: двойной запуск без ошибок; состав колонок
  соответствует sdd §4. Зона: `backend/app/migrate_video.py`.
  (design §7; sdd §4; Requirement «Отдельный контейнерный сервис…»)
- [x] 1.2 [infra] [M] Dev: каркас контейнерного сервиса `services/video/` —
  (а) Dockerfile по образцу images (python:3.12-slim, deps слоями с пинами
  fastapi/uvicorn/python-multipart, код /srv/app, USER 10001, EXPOSE 8380,
  healthcheck urllib, CMD uvicorn --workers 1) + статический ffmpeg/ffprobe:
  pinned-релиз johnvansickle, версия+SHA256 в Dockerfile, checksum в RUN,
  /usr/local/bin, при недоступности источника — fail fast сборки (НЕ apt);
  (б) app/main.py (роутеры, 422-обработчик, подключение middleware,
  /api/health exempt), app/middleware.py (копия images: без сессии — 401
  `{"error":"unauthorized"}`, exempt /api/health и /api/videos/authcheck,
  без права писать в sessions), app/db.py (RW video_videos + SELECT users,
  WAL, short transactions, busy_timeout); (в) compose-сервис `video` в
  deploy/compose.yaml: restart unless-stopped, mem_limit 512m, healthcheck
  :8380, depends_on [app], ротация логов json-file 10m×3, БЕЗ публикуемых
  портов, тома wiki-data:/data:rw + videos-data:/data/videos.
  Проверка: контейнер healthy, /api/health 200 без сессии, запрос к
  /api/videos без сессии — 401; ffmpeg -version в контейнере отвечает;
  порты не опубликованы. Зона: `services/video/Dockerfile`,
  `services/video/app/{main,middleware,db}.py`, `deploy/compose.yaml`.
  (design §2; NFR-35; Requirement «Отдельный контейнерный сервис…»)
- [x] 1.3 [code] [M] Dev: API видео `app/videos.py` + `app/storage.py` —
  (а) storage: единственный владелец путей тома `<id>/original.<ext>`,
  `<id>/video.mp4`, `<id>/preview.jpg` (uuid; пути из имен пользователя НЕ
  строятся — path traversal, design §8); (б) POST /api/videos — multipart,
  любой формат, лимит 500 МБ ДО записи на диск (Content-Length pre-check +
  потоковый счетчик-страховка; превышение/обрыв — 422, диск не расходуется),
  ставит в очередь конвертации (converter.enqueue — заглушка-интерфейс до
  волны 2), 201 {id, filename, status:"uploaded", size}; (в) GET /api/videos
  — список; (г) DELETE /api/videos/{id} — том `<id>/` целиком + метаданные,
  404/401; (д) GET /api/videos/{id}/file и /preview — 200/401/404/409 (не
  ready); (е) GET /api/videos/authcheck — 200/401 по cookie, без тяжелых
  БД-чтений (контракт стыка auth_request). Загрузка НЕ блокируется фоновой
  конвертацией (основной поток uvicorn).
  Проверка: ручной прогон контракта sdd §3 — все коды ответов; файл 501 МБ
  отклонен 422 без появления каталога в томе.
  Зона: `services/video/app/{videos,storage}.py`.
  (design §4, §5, §8; sdd §2, §3; Requirements «Загрузка…», «Список и
  playback», «Удаление видео», NFR-36)
- [x] 1.4 [infra] [M] Dev: nginx-маршрутизация и деградация — (а)
  `services/frontend/nginx/videos-proxy.inc`: set $upstream_videos
  (resolver 127.0.0.11 valid=10s), proxy-заголовки, X-Service: video,
  client_max_body_size 520m (только upload-локации), error_page 502 503 504
  = @videos_down (быстрый JSON 503 + Retry-After, паритет @images_down);
  (б) локации в ekotov-wiki.conf: `= /api/videos` + `^~ /api/videos/` (пара
  точный+префикс, URI не переписывается), `/videos/` — alias /data/videos/
  (ro) + auth_request /_video_auth + error_page 401 = @login_redirect +
  error_page 502 503 504 = @videos_down (устранение F2: отказ authcheck —
  управляемая 503, не голый 500), `/_video_auth` internal → video:8380
  /api/videos/authcheck (proxy_pass_request_body off, Content-Length "");
  (в) ro-маунт videos-data у frontend в compose.yaml.
  Проверка на стенде: /api/videos* проксируется; остановка контейнера video
  → быстрый 503 (не таймаут) на /api/videos* И на /videos/; доска/поиск/
  wiki/галерея работают; /videos/<uuid>/video.mp4 без сессии — редирект на
  /login, с сессией — 200; загрузка 501 МБ — 422 (не 413 от nginx).
  Зона: `services/frontend/nginx/**`, точечно `deploy/compose.yaml`
  (frontend-маунт; коммит после 1.2).
  (design §1, §5, §6; Requirements «Отдельный контейнерный сервис…»
  (сценарий деградации), NFR-36)
- [x] 1.5 [code] [M] Dev: фронтенд страницы «Видео» — (а) роут `/video` в
  backend/app/pages.py (Jinja2, без сессии — 302 /login по middleware);
  (б) frontend/templates/video.html + frontend/static/js/video.js: список
  (имя, статус, размер, дата), форма загрузки с прогрессом и ошибкой лимита,
  плеер `<video src="/videos/<id>/video.mp4">` только для «готово», статус
  «загружено»/«конвертируется» — плейсхолдер без запуска плеера, удаление с
  подтверждением по макету; (в) пункт «Видео» в base.html после «Галерея»,
  иконка inline-SVG в едином стиле. Вид — строго по утвержденным мокапам
  0.2. Никаких изменений редактора/статей (ОВ-3).
  Проверка: сценарии спеки «Пункт сайдбара…», «Неавторизованный — редирект…»,
  «Видео не встраивается…» вручную на стенде; design_validator после dev.
  Зона: `frontend/templates/{video.html,base.html}`,
  `frontend/static/js/video.js`, `backend/app/pages.py`.
  (Requirements «Раздел „Видео"…», «Список видео и playback», «Вид
  интерфейса…»; design §0)
- [x] 1.6 [tests] [M] Dev: сервисные тесты куска A в
  `services/video/tests/` (паритет services/images/tests): 401 без сессии на
  все эндпоинты; upload happy-path + 422 (501 МБ, обрыв тела, пустое тело);
  список/удаление (200/404); file/preview 409 не-ready; authcheck 200/401;
  storage — изоляция путей (uuid, отказ построения пути из имени).
  Проверка: pytest зелен; каждый тест без сети/внешних сервисов.
  Зона: `services/video/tests/**`. (sdd §3; Requirements куска A)
- [ ] 1.7 [ops] [M] Живая приемка куска A на стенде Заказчиком — загрузка
  (499 МБ MKV) → список → playback `<video>` → удаление; 501 МБ — отказ без
  записи; без сессии — 401/редирект; остановка video → 503, ядро живо.
  Проверка: протокол приемки (по образцу галереи); замечания — баг-репортами
  `test-model/bugs/`. (PLAN: «каждому куску — приемка»)

## Волна 2. Кусок D — социальный слой (после волны 1; Must, решение Заказчика 2026-10-17)

- [x] 2.1 [migration] [S] Dev: расширение миграции `backend/app/
  migrate_video.py` (кусок D; последовательно после 1.1 — общая зона) —
  (а) `video_comments` (id TEXT PK, video_id FK CASCADE, user_id FK users,
  text NOT NULL, created_at) и `video_reactions` (video_id, user_id,
  value CHECK IN (1,-1), created_at, PRIMARY KEY(video_id, user_id) —
  уникальность голоса) по схеме sdd §4, паттерн image_comments/
  image_reactions; (б) `ALTER TABLE video_videos ADD COLUMN category_id
  INTEGER` (NULL = «Без категории»; FK image_categories — СУЩЕСТВУЮЩИЙ
  справочник галереи, новый НЕ создается) — идемпотентно (проверка
  наличия колонки перед ALTER). Включение в деплой — тот же
  `MIGRATE_MODULE` (6.1). Проверка: двойной запуск без ошибок; состав
  колонок/таблиц соответствует sdd §4. Зона:
  `backend/app/migrate_video.py`.
  (sdd §4; design §7; Requirements «Комментарии…», «Лайки…», «Категории…»)
- [x] 2.2 [code] [M] Dev: API социального слоя `services/video/app/
  social.py` + расширение `db.py` — (а) GET/POST/DELETE
  /api/videos/{id}/comments: непустой текст (422), удаление ТОЛЬКО своего
  (чужой = 403), автор/время в списке; (б) PUT /api/videos/{id}/reaction
  {value:1|-1}: один голос на пользователя (PK video_id+user_id) — тот же
  value снимает (DELETE строки), противоположный переносит (UPDATE), ответ
  {my_reaction, likes, dislikes}; (в) GET /api/videos/categories — SELECT
  из image_categories (RO, без записи в чужой справочник); (г) db.py: RW
  video_comments/video_reactions + SELECT image_categories; (д) все
  эндпоинты за сессионным middleware, БЕЗ новых exempt (NFR-38). Проверка:
  контракт sdd §3 — 200/201/401/403/404/422; счетчики меняются ровно на
  единицу при постановке/переносе/снятии. Зона:
  `services/video/app/social.py`, `services/video/app/db.py`
  (последовательно после 1.2/1.3 — общая зона db.py).
  (sdd §2, §3; design §7, §8; Requirements куска D, NFR-38)
- [x] 2.3 [code] [S] Dev: категории в upload/list `services/video/app/
  videos.py` — (а) POST /api/videos: опц. category_id (валидация
  существования в image_categories, иначе 422; NULL = «Без категории»);
  (б) GET /api/videos: `?category=<id|none>` фильтр (none = category_id IS
  NULL) + category_id/category_name/likes/dislikes/my_reaction в элементах
  списка; (в) DELETE /api/videos/{id} — CASCADE комментариев/реакций.
  Проверка: сценарии «Выбор при загрузке…», «Фильтр по категории…» спеки;
  категория, созданная в галерее, видна в /api/videos/categories. Зона:
  `services/video/app/videos.py` (последовательно после 1.3 и 2.2 —
  общая зона списка).
  (sdd §3; Requirements «Категории видео…», «Комментарии…» (CASCADE))
- [x] 2.4 [code] [M] Dev: фронтенд социального слоя — frontend/templates/
  video.html + frontend/static/js/video.js по утвержденным мокапам
  (блоки D): (а) блок комментариев под плеером — список (автор, время,
  текст), форма добавления, удаление своего; (б) лайк/дизлайк с
  счетчиками и собственным голосом (клики: поставить/перенести/снять);
  (в) выбор категории в форме загрузки (опции из /api/videos/categories,
  «Без категории» по умолчанию) и фильтр по категории в списке. Иконки —
  inline-SVG (ОГР-8). Проверка: сценарии куска D вручную на стенде
  (два пользователя: чужой комментарий не удаляется, голос переносится);
  design_validator после dev. Зона: `frontend/templates/video.html`,
  `frontend/static/js/video.js` (последовательно после 1.5 — общая зона).
  (Requirements «Комментарии…», «Лайки…», «Категории…»; design §0)
- [x] 2.5 [tests] [M] Dev: тесты социального слоя в `services/video/tests/`
  — 401 без сессии на все D-эндпоинты (NFR-38); пустой/whitespace
  комментарий 422; чужой комментарий 403; реакция: постановка/снятие
  (повтор клика)/перенос — счетчики ровно на единицу, одна строка на
  пару видео+пользователь; категории: валидный category_id, 422 на
  несуществующий, фильтр none; CASCADE при удалении видео. Проверка:
  pytest зелен; без сети/внешних сервисов. Зона: `services/video/tests/**`
  (последовательно после 1.6 — общая зона тест-контура).
  (sdd §3; Requirements куска D, NFR-38)
- [ ] 2.6 [ops] [M] Живая приемка куска D на стенде Заказчиком: два
  пользователя — комментарий (добавление/видимость/удаление только
  своего), лайк/дизлайк (постановка, перенос, снятие), категории (выбор
  при загрузке, фильтр в списке, «Без категории»); без сессии — 401.
  Проверка: протокол приемки (по образцу галереи); замечания —
  баг-репортами `test-model/bugs/`. (PLAN D; решение 2026-10-17)

## Волна 3. Кусок B — конвертация (после волны 2; порядок кусков A → D → B)

- [x] 3.1 [code] [M] Dev: фоновая конвертация `app/converter.py` — (а)
  очередь queue.Queue + 1 поток-воркер (строго одна конвертация
  одновременно), start_worker() на старте main; (б) subprocess ffmpeg
  `nice -n 10` (preexec_fn) `-c:v libx264 -preset veryfast -movflags
  +faststart`, wall-clock timeout 30 мин (истечение = kill = неудача
  попытки), превью-кадр тем же проходом воркера: `ffmpeg -frames:v 1`
  → `<id>/preview.jpg` в томе рядом с mp4 — В ТОМ ЧИСЛЕ для загруженного
  файла, уже являющегося mp4 (быстрый проход без перекодирования; r2:
  превью — кусок B, не C); (в) статусы: uploaded →
  converting → ready; пишет статус ТОЛЬКО воркер (API — читатель); (г) ровно
  один авторетрай (non-zero exit / timeout / нет выходного файла / не
  снялся кадр), после
  второй неудачи — `error`, оригинал сохранен; (д) успех: mp4+preview в том,
  оригинал удален, size_bytes обновлен; (е) отмена при DELETE (флаг in-memory,
  воркер проверяет перед записью результата — артефакты отбрасываются);
  (ж) крэш-восстановление на старте: re-enqueue записей в статусах
  `uploaded` И `converting` (устранение F1), частичный mp4 удалить перед
  повтором. Проверка: ручной прогон MKV→mp4 со статусами в UI; симуляция
  рестарта контейнера в статусе converting и в статусе uploaded — обе
  записи дообслуживаются; поврежденный файл → ровно 2 попытки → `error` с
  сохраненным оригиналом; удаление во время конвертации не оставляет
  артефактов; загрузка готового mp4 → в томе mp4+preview.jpg. Зона:
  `services/video/app/converter.py` (+ строка старта в
  main.py; волна 3 после 1.2 — последовательная, не [P]).
  (design §3; Requirements «Серверная конвертация…», «Превью-кадр
  генерируется при конвертации», «Удаление оригинала…»,
  «Удаление видео» (сценарий недоконченного), NFR-37)
- [x] 3.2 [tests] [M] Dev: тесты конвертации в `services/video/tests/` —
  статусы по жизненному циклу; ровно 1 ретрай (счетчик convert_attempts 2 =
  error); timeout → kill → ретрай; крэш-восстановление uploaded+converting;
  отмена DELETE; удаление оригинала только после успеха (в `error` —
  оригинал на месте); превью: preview.jpg появился при успехе и для
  уже-mp4-исходника тоже, при неудаче — нет; серийность воркера (вторая
  задача ждет).
  Проверка: pytest зелен; фейки ffmpeg (скрипт-заглушка) для веток
  неудачи/таймаута. Зона: `services/video/tests/**`.
  (design §3; Requirements B, «Превью-кадр…»)
- [ ] 3.3 [ops] [M] Живая приемка куска B: загрузка MKV ~200 МБ → статусы
  «загружено»→«конвертируется»→«готово» в UI без перезагрузки; после успеха
  в томе mp4+preview, оригинала нет; загрузка файла-mp4 → превью-кадр
  тоже появился; поврежденный файл → «ошибка», оригинал
  на месте; playback готового. Проверка: протокол приемки.
  (PLAN B; design §3, §10)

## Волна 4. Кусок C — полировка (после волны 3; Should — исключение только по решению Заказчика)

- [x] 4.1 [code] [S] Dev: сортировка и поиск — (б) GET /api/videos
  `?query=<подстрока>&order=asc|desc` — поиск по подстроке имени без учета
  регистра (lower()-нормализация обеих сторон LIKE), сортировка filename
  COLLATE NOCASE в обе стороны, пустой query — все; (в) UI-контролы
  поиска/сортировки по макету. Проверка: сценарий «Поиск и сортировка»
  спеки (≥3 видео, кириллица, регистр). (Превью-кадр — задача 3.1 куска B,
  r2; в C не входит.) Выполнено: поиск/сортировка комбинируются с фильтром
  категории куска D; кириллица без учета регистра — unicode-lower
  (перекрытие ASCII-only lower/COLLATE NOCASE SQLite на соединении сервиса,
  см. dev-report-C.md эскалацию 1); тулбар по мокапу video-list.html
  (поиск debounce, сортировка «Имя А→Я»/«Имя Я→А», «Сбросить», пустой
  state «Ничего не найдено»); polling куска B ходит с теми же фильтрами
  (попутный фикс: терял category). Тесты: services/video/tests 66 passed
  (+7 TC-vid-080…086), tests/web +1 TC-vid-110 (видео-сьют 10 passed).
  Зона: `services/video/app/{videos,db}.py`,
  `frontend/static/js/video.js`, `frontend/templates/video.html`
  (последовательная после 2.3 — общая зона с волной 2).
  (Requirement «Сортировка и поиск по имени…»; design §7)
- [ ] 4.2 [ops] [S] Живая приемка куска C: поиск/сортировка на
  стенде. Проверка: протокол приемки. (PLAN C)

## Волна 5. QA-контур (обязателен, инцидент J39; после волн 1–4)

- [ ] 5.1 [tests] [S] qa_checklist: `test-model/checklists/video-hosting.md`
  — покрытие всех 46 сценариев дельты specs/video-service (18 Requirements,
  включая кусок D, NFR-38 и переименование видео r3).
  Проверка: каждому сценарию ≥1 чеклист-пункт с трассировкой.
  (flow-1; J23)
- [ ] 5.2 [tests] [M] qa_author: кейсы из дельт спеки (НЕ из кода) в
  `test-model/new/video-hosting/` — happy path и негатив по каждому
  сценарию чеклиста 5.1. Проверка: каждый кейс ссылается на Requirement +
  Scenario. (flow-1 п.3)
- [ ] 5.3 [tests] [S] qa_case_reviewer: независимое ревью кейсов 5.2,
  `test-model/new/` → `test-model/approved/`. Проверка: вердикт ревьюера
  зафиксирован; замечания — возвратом автору. (flow-1 п.3)
- [ ] 5.4 [tests] [M] qa_automation: автотесты по approved-кейсам, TC-ID
  `TC-video-hosting-NNN` в каждом тесте, трассировка кейс→тест;
  API-сьют против стенда (compose), включая 401/422/409/404/503-ветки и
  лимит 500 МБ. Проверка: pytest зелен; каждый approved-Must-кейс имеет
  тест или скриптовый прогон с REPORT. (flow-1 п.4; правило 6 flow_check)
- [ ] 5.5 [tests] [M] Прогоны по наборам — отдельные делегации-раннеры:
  api → web-desktop → web-mobile → **смок** (сквозной: загрузка →
  конвертация → playback через nginx → удаление; деградация 503 при
  остановленном video; доступ без сессии). Падение набора = баг-репорт
  `test-model/bugs/BUG-NNN`, набор стоит до фикса (Флоу 2) и зеленого
  перегона. Проверка: REPORT каждого набора. (service-decomposition §3 п.6;
  решение 2026-10-12)
- [ ] 5.6 [tests] [S] Замеры NFR-35/37 на стенде до прод-выкатки — REPORT:
  RSS/CPU контейнера (docker stats) при конвертации ~200–300 МБ, healthcheck,
  p95 (20 списков + 5 малых загрузок при идущей конвертации ~300 МБ) < 500
  мс; суммарные лимиты стека с резервом хосту ≥ 2 GB. Стабильное превышение
  mem_limit — стоп, эскалация Заказчику. Проверка: REPORT в
  `test-model/reports/`. (NFR-35, NFR-37; design §10)
- [ ] 5.7 [tests] [S] Независимый аудит покрытия «сценарий дельты → кейс →
  тест» до прод-выкатки (прецедент add-wiki REPORT-coverage-audit). GAP
  Must-сценария = блокер волны 6; Should — фикс или принятый риск с пометкой.
  (flow-1 «Критично»; J39)

## Волна 6. Deploy, приемка, архивация (после волны 5 без GAP-Must)

- [ ] 6.1 [ops] [M] Деплой релиза: build тегов (latest запрещен), бэкап БД
  до деплоя, `MIGRATE_MODULE=migrate_video` строго до up (шов миграций:
  владелец-таблица создается до старта потребителя video, depends_on [app]),
  подъем app → healthy → video → nginx, смоук с 502-контролем; regress-final
  по механике J51 (regress_runner). Проверка: regress-final зелен; на проде
  /api/health video отвечает, пункт «Видео» на месте.
  (design §2; map §1.3; flow-1)
- [ ] 6.2 [ops] [M] Прод-выкатка + живая приемка Заказчика (протокол
  обязателен): С1 загрузка/конвертация/playback, С2 удаление, С3 доступ без
  сессии; отдельно упомянуть: оригиналы удаляются после конвертации (ОВ-4)
  и том videos-data в бэкап-контур не входит (наблюдение O1 ревью №1).
  Откат — предыдущий релизный тег. Проверка: подписанный протокол приемки.
  (flow-1; PLAN)
- [ ] 6.3 [docs] [S] Архивация и карта: `openspec archive video-hosting`
  (слияние дельты в master-spec video-service, сквозная нумерация FR-117+,
  NFR-35+), validate strict; финальная актуализация `architecture/map.md`
  (перевод плановой дельты §7 в тело карты: 7-й контейнер, владение
  video_videos, том videos-data, швы app/nginx) + release-log.
  Проверка: `flow_check.py` green; карта синхронна проду.
  (openspec-authoring п.9; задача СА ревью №1)

## Волна 7. Дополнение r3 — переименование видео (решение Заказчика; после 6.2)

- [x] 7.1 [code] [S] Dev: API переименования `services/video/app/videos.py` —
  `PATCH /api/videos/{id}` с телом `{"title"}` (паритет rename изображений
  `PUT /api/images/{id}/name`, FR-97): валидация title — непустая строка
  1–255 символов юникода после обрезки пробелов, без `/`, `\` и управляющих
  символов (422 — паритет валидации images); несуществующее видео — 404
  (`_require_video`); без сессии — 401 (middleware, NFR-36/38; новых exempt
  НЕ добавлять). Меняется ТОЛЬКО колонка `filename` в `video_videos` —
  том `videos-data` и маршруты `/videos/…` не трогаются (имена файлов uuid).
  Ответ 200 `{id, title}`. Тесты в `services/video/tests/`: happy-path +
  границы (1 и 255 символов — 200; 256, пустой, пробелы, без поля, `/` —
  422; кириллица), 404, 401, том не изменился, поиск/сортировка по новому
  имени. Проверка: pytest зелен; сценарии «Переименование видео» спеки.
  Зона: `services/video/app/videos.py`, `services/video/tests/`
  (последовательно после 4.1 — общая зона videos.py).
  (Requirement «Переименование видео»; NFR-36/38; design §8)
- [x] 7.2 [code] [S] Dev: фронтенд переименования — frontend/templates/
  video.html + frontend/static/js/video.js по образцу rename изображений
  (edit-иконка у имени на странице просмотра, инлайн-правка): PATCH
  `{title}`, обновление имени в DOM без перезагрузки, новое имя переживает
  перезагрузку страницы; ошибки 422/404 показываются пользователю. Иконки —
  inline-SVG (ОГР-8). Проверка: сценарий «Успешное переименование» и
  негативы вручную на стенде; design_validator после dev.
  Зона: `frontend/templates/video.html`, `frontend/static/js/video.js`
  (последовательно после 7.1 — общая зона контракта API).
  (Requirement «Переименование видео»; design §0)
- [ ] 7.3 [ops] [S] Живая приемка Заказчиком (дополнение к протоколу 6.2):
  переименование в UI (кириллица), новое имя после перезагрузки, playback/
  скачивание по прежним ссылкам, том не изменился; негативы (пустое имя,
  256 символов — отказ без изменения). Проверка: протокол приемки
  (дополнение); замечания — баг-репортами `test-model/bugs/`.
  (r3; решение Заказчика)

## Зависимости и порядок

0.1 → 0.2 → 0.3 (мокапы утверждены) → 1.1 → (1.2 → 1.3 → 1.6) ∥ 1.4 ∥
1.5 → 1.7 → **кусок D**: 2.1 → (2.2 → 2.3) → 2.4 ∥ 2.5 → 2.6 →
**кусок B**: 3.1 → 3.2 → 3.3 → **кусок C**: 4.1 → 4.2 → QA-контур: 5.1 →
5.2 → 5.3 → 5.4 → 5.5 → 5.6 → 5.7 → 6.1 → 6.2 → 6.3 (порядок кусков
A → D → B → C — r2).
Волна A: [P]-допустимо только 1.4 и 1.5 против (1.2→1.3) — зоны файлов
непересекающиеся (проверено seam_checker); 1.2 и 1.3 делят HTTP-формы
ответов — строго последовательно (sdd §2 «НЕЛЬЗЯ делить»). Кусок D — после
приемки A (2.1 общая зона с 1.1; 2.2 с 1.2 db.py; 2.4 с 1.5 фронтенд — все
последовательно, не [P]; 2.4 ∥ 2.5 зоны непересекающиеся — [P]-допустимо).
Кусок B — после приемки D (превью-кадр 3.1); C — после B. QA-контур
стартует только после кода всех кусков, «кейсы до автотестов» (5.2 раньше
5.4).
Дополнение r3 (после приемки 6.2): 7.1 → 7.2 → 7.3 — строго последовательно
(7.1/7.2 — общая зона контракта API; приемка только после кода).

## Швы и зоны (проверка seam_checker)

```
1.1:backend/app/migrate_video.py  2.1:backend/app/migrate_video.py (после 1.1)
1.2:services/video/Dockerfile  1.2:services/video/app/main.py
1.2:services/video/app/middleware.py  1.2:services/video/app/db.py
1.2:deploy/compose.yaml
1.3:services/video/app/videos.py  1.3:services/video/app/storage.py
1.4:services/frontend/nginx/
1.5:frontend/templates/video.html  1.5:frontend/templates/base.html
1.5:frontend/static/js/video.js  1.5:backend/app/pages.py
1.6:services/video/tests/
2.2:services/video/app/social.py  2.2:services/video/app/db.py (после 1.2)
2.3:services/video/app/videos.py (после 1.3, 2.2)
2.4:frontend/templates/video.html  2.4:frontend/static/js/video.js (после 1.5)
2.5:services/video/tests/ (после 1.6)
3.1:services/video/app/converter.py
3.2:services/video/tests/ (после 1.6, 2.5)
4.1:services/video/app/{videos,db}.py  4.1:frontend/{js,templates} (после 2.3, 2.4)
7.1:services/video/app/videos.py  7.1:services/video/tests/ (после 4.1)
7.2:frontend/templates/video.html  7.2:frontend/static/js/video.js (после 7.1)
```

Результат seam_checker (skills/service-decomposition): параллельный набор
зон (все, кроме последовательных пар ниже) — **0 пересечений**, exit 0.
Осознанные последовательные пары (§4: общая зона = одна задача или
последовательно; НЕ [P]): **1.3 → 2.3 → 4.1** (videos.py: куски D и C
расширяют API куска A), **1.1 → 2.1** (migrate_video.py), **1.2 → 2.2**
(db.py), **1.5 → 2.4 → 4.1** (фронтенд видео), **1.6 → 2.5 → 3.2**
(тест-контур `services/video/tests/`), **1.2/1.3** — общая зона HTTP-форм
ответов (sdd §2 «НЕЛЬЗЯ делить»). Зона `services/video/app/social.py`
(2.2) уникальна за куском D — новых пересечений r2 не добавляет. В [P]-
набор волны 2 допустима только пара 2.4 ∥ 2.5; все задачи кусков
последовательны между волнами (порядок A → D → B → C).

## Ворота и правила

- `openspec validate --all --strict` — change video-hosting green на каждом
  шаге; `flow_check.py` — зелен (tasks.md существует с этого ревью).
- Дизайн-фаза Р4/Р5: мокапы ui_designer → утверждение Заказчика (0.3) → dev
  по мокапам → design_validator; СА/dev мокапы не рисуют.
- Волны 1–4 не стартуют без 0.3 (мокапы утверждены 2026-10-17, включая
  блоки D); задача 6.2 — только с явным участием
  Заказчика.
- ffmpeg — статический бинарь с пином и SHA256; без apt/CDN/внешних
  библиотек (ОГР-8); плеер — нативный `<video>`, иконки — inline-SVG.
- Таблицы ядра, editor, доска, поиск, галерея — не трогаем; сервис не имеет
  права писать в sessions и в чужие таблицы (владение: video_videos — только
  у video).
- Баги QA-раннеров → `test-model/bugs/BUG-NNN`, фикс Флоу 2 с code_review,
  повторный прогон набора — отдельной делегацией.
