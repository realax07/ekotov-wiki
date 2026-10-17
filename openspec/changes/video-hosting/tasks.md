# tasks.md — video-hosting (P11 «Видеохостинг wiki»)

Флоу 1 (полный: СА → дизайн → dev → QA → приемка Заказчика). Куски PLAN:
**0 дизайн → A ядро → B конвертация → C полировка**, у каждого куска — живая
приемка (урок J51/rich). Архитектурное ревью пакета —
`review-architecture.md` №1 (verdict APPROVE, находки F1/F2 устранены в
design/sdd). Формат: задача = наблюдаемый результат + критерий проверки +
зона файлов + трассировка; 1 задача = 1 сабагент + независимый ревьюер.
Ворота: `openspec validate --all --strict` — change green на каждом шаге.
Порядок: 0 → (утверждение Заказчиком) → 1 → 2 → 3 → 4 (QA-контур) → 5.

## Волна 0. Пакет и дизайн-фаза (Д-паттерн Р4/Р5)

- [x] 0.1 [docs] [S] СА: change-пакет + архитектурное ревью — proposal,
  requirements (12 Requirements / 23 сценария, DRAFT r1), design r1 (с
  устранением F1/F2), sdd, дельта specs/video-service; ревью —
  `review-architecture.md` №1 (APPROVE); нарезка — настоящий tasks.md.
  Проверка: `openspec validate video-hosting --type change --strict` — green.
  Зона: `openspec/changes/video-hosting/**`. (утверждено: ревью №1)
- [ ] 0.2 [design] [M] ui_designer: мокапы страниц «Видео» в `design/` —
  standalone HTML по токенам V3 «Бумага», без внешних библиотек/CDN (ОГР-8):
  (а) страница `/video` — список карточек (превью-кадр, имя, статус, размер,
  дата; плейсхолдер несконвертированного; индикатор конвертации);
  (б) форма загрузки с индикацией прогресса и ошибки лимита 500 МБ;
  (в) встроенный плеер `<video>`; (г) подтверждение удаления;
  (д) пункт сайдбара «Видео» после «Галерея», иконка в едином стиле
  (эталон «Мониторинг»/«Галерея»). Зона: `design/**` только.
  Проверка: мокапы открываются без сети, токены V3, все 5 состояний
  присутствуют. (design §0; Requirements «Раздел „Видео"…», «Вид интерфейса…»)
- [ ] 0.3 [design] Развилка Заказчика: утверждение мокапов 0.2 — волны 1–3
  НЕ стартуют до зафиксированного утверждения (прецедент Д-5). Позиция
  пункта сайдбара и вид плейсхолдера/индикатора — финал здесь.
  Проверка: решение Заказчика зафиксировано (approval_ref оркестратора).
  (requirements «Открытые вопросы»; design §0)

## Волна 1. Кусок A — ядро сервиса (после 0.3)

- [ ] 1.1 [migration] [S] Dev: one-shot миграция ядра `backend/app/
  migrate_video.py` — таблица `video_videos` по схеме sdd §4 (id TEXT PK
  uuid4, filename, status, size_bytes, mime, uploaded_by FK users,
  created_at, convert_attempts DEFAULT 0), идемпотентно (CREATE IF NOT
  EXISTS), одна транзакция BEGIN IMMEDIATE, автосверка структуры (паттерн
  migrate_gallery/migrate_wiki); ядро больше НИЧЕГО не пишет в таблицу
  (владелец — сервис video). Включение в деплой: `MIGRATE_MODULE` в 5.1
  (строго до up). Проверка: двойной запуск без ошибок; состав колонок
  соответствует sdd §4. Зона: `backend/app/migrate_video.py`.
  (design §7; sdd §4; Requirement «Отдельный контейнерный сервис…»)
- [ ] 1.2 [infra] [M] Dev: каркас контейнерного сервиса `services/video/` —
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
- [ ] 1.3 [code] [M] Dev: API видео `app/videos.py` + `app/storage.py` —
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
- [ ] 1.4 [infra] [M] Dev: nginx-маршрутизация и деградация — (а)
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
- [ ] 1.5 [code] [M] Dev: фронтенд страницы «Видео» — (а) роут `/video` в
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
- [ ] 1.6 [tests] [M] Dev: сервисные тесты куска A в
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

## Волна 2. Кусок B — конвертация (после волны 1)

- [ ] 2.1 [code] [M] Dev: фоновая конвертация `app/converter.py` — (а)
  очередь queue.Queue + 1 поток-воркер (строго одна конвертация
  одновременно), start_worker() на старте main; (б) subprocess ffmpeg
  `nice -n 10` (preexec_fn) `-c:v libx264 -preset veryfast -movflags
  +faststart`, wall-clock timeout 30 мин (истечение = kill = неудача
  попытки), ffprobe/первый кадр → preview.jpg; (в) статусы: uploaded →
  converting → ready; пишет статус ТОЛЬКО воркер (API — читатель); (г) ровно
  один авторетрай (non-zero exit / timeout / нет выходного файла), после
  второй неудачи — `error`, оригинал сохранен; (д) успех: mp4+preview в том,
  оригинал удален, size_bytes обновлен; (е) отмена при DELETE (флаг in-memory,
  воркер проверяет перед записью результата — артефакты отбрасываются);
  (ж) крэш-восстановление на старте: re-enqueue записей в статусах
  `uploaded` И `converting` (устранение F1), частичный mp4 удалить перед
  повтором. Проверка: ручной прогон MKV→mp4 со статусами в UI; симуляция
  рестарта контейнера в статусе converting и в статусе uploaded — обе
  записи дообслуживаются; поврежденный файл → ровно 2 попытки → `error` с
  сохраненным оригиналом; удаление во время конвертации не оставляет
  артефактов. Зона: `services/video/app/converter.py` (+ строка старта в
  main.py; волна 2 после 1.2 — последовательная, не [P]).
  (design §3; Requirements «Серверная конвертация…», «Удаление оригинала…»,
  «Удаление видео» (сценарий недоконченного), NFR-37)
- [ ] 2.2 [tests] [M] Dev: тесты конвертации в `services/video/tests/` —
  статусы по жизненному циклу; ровно 1 ретрай (счетчик convert_attempts 2 =
  error); timeout → kill → ретрай; крэш-восстановление uploaded+converting;
  отмена DELETE; удаление оригинала только после успеха (в `error` —
  оригинал на месте); серийность воркера (вторая задача ждет).
  Проверка: pytest зелен; фейки ffmpeg (скрипт-заглушка) для веток
  неудачи/таймаута. Зона: `services/video/tests/**`.
  (design §3; Requirements B)
- [ ] 2.3 [ops] [M] Живая приемка куска B: загрузка MKV ~200 МБ → статусы
  «загружено»→«конвертируется»→«готово» в UI без перезагрузки; после успеха
  в томе mp4+preview, оригинала нет; поврежденный файл → «ошибка», оригинал
  на месте; playback готового. Проверка: протокол приемки.
  (PLAN B; design §3, §10)

## Волна 3. Кусок C — полировка (после волны 2; Should — исключение только по решению Заказчика)

- [ ] 3.1 [code] [S] Dev: превью-кадр, сортировка и поиск — (а) превью
  первого кадра в карточке списка (`/videos/<id>/preview.jpg` через nginx),
  плейсхолдер несконвертированного по макету; (б) GET /api/videos
  `?query=<подстрока>&order=asc|desc` — поиск по подстроке имени без учета
  регистра (lower()-нормализация обеих сторон LIKE), сортировка filename
  COLLATE NOCASE в обе стороны, пустой query — все; (в) UI-контролы
  поиска/сортировки по макету. Проверка: сценарий «Поиск и сортировка»
  спеки (≥3 видео, кириллица, регистр); плейсхолдер до конвертации.
  Зона: `services/video/app/{videos,db}.py`,
  `frontend/static/js/video.js`, `frontend/templates/video.html`
  (последовательная после 2.1 — общая зона с волной 2).
  (Requirement «Превью-кадр, сортировка и поиск…»; design §7)
- [ ] 3.2 [ops] [S] Живая приемка куска C: поиск/сортировка/превью на
  стенде. Проверка: протокол приемки. (PLAN C)

## Волна 4. QA-контур (обязателен, инцидент J39; после волн 1–3)

- [ ] 4.1 [tests] [S] qa_checklist: `test-model/checklists/video-hosting.md`
  — покрытие всех 23 сценариев дельты specs/video-service (12 Requirements).
  Проверка: каждому сценарию ≥1 чеклист-пункт с трассировкой.
  (flow-1; J23)
- [ ] 4.2 [tests] [M] qa_author: кейсы из дельт спеки (НЕ из кода) в
  `test-model/new/video-hosting/` — happy path и негатив по каждому
  сценарию чеклиста 4.1. Проверка: каждый кейс ссылается на Requirement +
  Scenario. (flow-1 п.3)
- [ ] 4.3 [tests] [S] qa_case_reviewer: независимое ревью кейсов 4.2,
  `test-model/new/` → `test-model/approved/`. Проверка: вердикт ревьюера
  зафиксирован; замечания — возвратом автору. (flow-1 п.3)
- [ ] 4.4 [tests] [M] qa_automation: автотесты по approved-кейсам, TC-ID
  `TC-video-hosting-NNN` в каждом тесте, трассировка кейс→тест;
  API-сьют против стенда (compose), включая 401/422/409/404/503-ветки и
  лимит 500 МБ. Проверка: pytest зелен; каждый approved-Must-кейс имеет
  тест или скриптовый прогон с REPORT. (flow-1 п.4; правило 6 flow_check)
- [ ] 4.5 [tests] [M] Прогоны по наборам — отдельные делегации-раннеры:
  api → web-desktop → web-mobile → **смок** (сквозной: загрузка →
  конвертация → playback через nginx → удаление; деградация 503 при
  остановленном video; доступ без сессии). Падение набора = баг-репорт
  `test-model/bugs/BUG-NNN`, набор стоит до фикса (Флоу 2) и зеленого
  перегона. Проверка: REPORT каждого набора. (service-decomposition §3 п.6;
  решение 2026-10-12)
- [ ] 4.6 [tests] [S] Замеры NFR-35/37 на стенде до прод-выкатки — REPORT:
  RSS/CPU контейнера (docker stats) при конвертации ~200–300 МБ, healthcheck,
  p95 (20 списков + 5 малых загрузок при идущей конвертации ~300 МБ) < 500
  мс; суммарные лимиты стека с резервом хосту ≥ 2 GB. Стабильное превышение
  mem_limit — стоп, эскалация Заказчику. Проверка: REPORT в
  `test-model/reports/`. (NFR-35, NFR-37; design §10)
- [ ] 4.7 [tests] [S] Независимый аудит покрытия «сценарий дельты → кейс →
  тест» до прод-выкатки (прецедент add-wiki REPORT-coverage-audit). GAP
  Must-сценария = блокер волны 5; Should — фикс или принятый риск с пометкой.
  (flow-1 «Критично»; J39)

## Волна 5. Deploy, приемка, архивация (после волны 4 без GAP-Must)

- [ ] 5.1 [ops] [M] Деплой релиза: build тегов (latest запрещен), бэкап БД
  до деплоя, `MIGRATE_MODULE=migrate_video` строго до up (шов миграций:
  владелец-таблица создается до старта потребителя video, depends_on [app]),
  подъем app → healthy → video → nginx, смоук с 502-контролем; regress-final
  по механике J51 (regress_runner). Проверка: regress-final зелен; на проде
  /api/health video отвечает, пункт «Видео» на месте.
  (design §2; map §1.3; flow-1)
- [ ] 5.2 [ops] [M] Прод-выкатка + живая приемка Заказчика (протокол
  обязателен): С1 загрузка/конвертация/playback, С2 удаление, С3 доступ без
  сессии; отдельно упомянуть: оригиналы удаляются после конвертации (ОВ-4)
  и том videos-data в бэкап-контур не входит (наблюдение O1 ревью №1).
  Откат — предыдущий релизный тег. Проверка: подписанный протокол приемки.
  (flow-1; PLAN)
- [ ] 5.3 [docs] [S] Архивация и карта: `openspec archive video-hosting`
  (слияние дельты в master-spec video-service, сквозная нумерация FR-117+,
  NFR-35+), validate strict; финальная актуализация `architecture/map.md`
  (перевод плановой дельты §7 в тело карты: 7-й контейнер, владение
  video_videos, том videos-data, швы app/nginx) + release-log.
  Проверка: `flow_check.py` green; карта синхронна проду.
  (openspec-authoring п.9; задача СА ревью №1)

## Зависимости и порядок

0.1 → 0.2 → **0.3 (развилка Заказчика)** → 1.1 → (1.2 → 1.3 → 1.6) ∥ 1.4 ∥
1.5 → 1.7 → 2.1 → 2.2 → 2.3 → 3.1 → 3.2 → 4.1 → 4.2 → 4.3 → 4.4 → 4.5 →
4.6 → 4.7 → 5.1 → 5.2 → 5.3.
Волна A: [P]-допустимо только 1.4 и 1.5 против (1.2→1.3) — зоны файлов
непересекающиеся (проверено seam_checker); 1.2 и 1.3 делят HTTP-формы
ответов — строго последовательно (sdd §2 «НЕЛЬЗЯ делить»). Кусок B — после
приемки A; C — после B. QA-контур стартует только после кода всех кусков,
«кейсы до автотестов» (4.2 раньше 4.4).

## Швы и зоны (проверка seam_checker)

```
1.1:backend/app/migrate_video.py
1.2:services/video/Dockerfile  1.2:services/video/app/main.py
1.2:services/video/app/middleware.py  1.2:services/video/app/db.py
1.2:deploy/compose.yaml
1.3:services/video/app/videos.py  1.3:services/video/app/storage.py
1.4:services/frontend/nginx/
1.5:frontend/templates/video.html  1.5:frontend/templates/base.html
1.5:frontend/static/js/video.js  1.5:backend/app/pages.py
1.6:services/video/tests/  2.1:services/video/app/converter.py
2.2:services/video/tests/  3.1:services/video/app/videos.py
```

Результат seam_checker (skills/service-decomposition): параллельный набор
зон (все, кроме двух последовательных пар ниже) — **0 пересечений**, exit 0.
Две осознанные последовательные пары (§4: общая зона = одна задача или
последовательно; НЕ [P]): **1.3 → 3.1** (videos.py: кусок C расширяет API
куска A, волна 3 строго после волны 1) и **1.6 → 2.2** (тест-контур
`services/video/tests/`: тесты конвертации после тестов ядра). Пара
1.2/1.3 — общая зона HTTP-форм ответов (sdd §2 «НЕЛЬЗЯ делить») —
последовательна и не входит в [P]-набор.

## Ворота и правила

- `openspec validate --all --strict` — change video-hosting green на каждом
  шаге; `flow_check.py` — зелен (tasks.md существует с этого ревью).
- Дизайн-фаза Р4/Р5: мокапы ui_designer → утверждение Заказчика (0.3) → dev
  по мокапам → design_validator; СА/dev мокапы не рисуют.
- Волны 1–3 не стартуют без 0.3; задача 5.2 — только с явным участием
  Заказчика.
- ffmpeg — статический бинарь с пином и SHA256; без apt/CDN/внешних
  библиотек (ОГР-8); плеер — нативный `<video>`, иконки — inline-SVG.
- Таблицы ядра, editor, доска, поиск, галерея — не трогаем; сервис не имеет
  права писать в sessions и в чужие таблицы (владение: video_videos — только
  у video).
- Баги QA-раннеров → `test-model/bugs/BUG-NNN`, фикс Флоу 2 с code_review,
  повторный прогон набора — отдельной делегацией.
