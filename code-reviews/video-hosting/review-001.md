# Code review — video-hosting, волна 1, кусок A (tasks 1.1–1.6)

Роль: code_reviewer (независимый). Ревьюируемый объем: коммит 6383890 (кусок A) + контроль [chore] aaa1900 и 48fa1c4. База: main. Фокус: авторизация, загрузка (лимит/traversal/отказ), удаление, изоляция отказа, SQLite-профиль, chore-коммиты. Спека: openspec/changes/video-hosting/ (12 Requirements; кусок A без D-эндпоинтов и без конвертации — enqueue-заглушка осознанная, решение оркестратора 2026-10-17).

Метод: чтение дифа main...HEAD (services/video/**, deploy/**, services/frontend/nginx/**, backend/app/migrate_video.py, фронтенд, тесты) против sdd §2/§3/§4, design §1/§4/§5/§7/§8, specs/video-service; точечный прогон services/video/tests (29 passed, 8.8s, venv backend/.venv); сбор tests/ --collect-only (600 tests, 0 collection errors — проверка восстановления conftest). Полный регресс не гонялся — доверие отчету dev (713-эквивалент, видео 32), стендовая верификация из коммит-месседжа (healthy, 401, upload→playback 200+Range 206, 302 без сессии, 503 при остановке video, 501 МБ → 422 без записи) принята.

---

## Проверка по фокусам

**(1) Авторизация — ДА.** Middleware (app/middleware.py) — исчерпывающий exempt-список {(GET /api/health), (GET /api/videos/authcheck)}, все остальные пути /api/videos* → 401 {"error": "unauthorized"} (NFR-36); тест test_endpoints_require_session покрывает POST/GET/DELETE/file/preview/openapi.json. authcheck валидирует cookie сам (200 {} / 401) — стык auth_request корректен: subrequest без сессии → 401 → nginx @login_redirect (302 /login); без cookie до БД не доходит. Обход мимо nginx исключен топологией: порты video НЕ публикуются (compose.yaml/compose.test.yaml), достучаться можно только из compose-сети; /_video_auth и @-локации internal. /openapi.json за middleware (401 без сессии) — паритет FR-68. Замечаний нет.

**(2) Загрузка — ДА, с двумя наблюдениями (minor-1, minor-2).**
- CL pre-check: тело > 500 МиБ + 20 МиБ обвязки → 422 ДО чтения (check_content_length; int()-parse защищен). Обход через chunked без Content-Length закрыт потоковым счетчиком (spool_to_temp: >MAX → UploadTooLarge → 422; тесты test_upload_precheck_rejects_huge_content_length, test_upload_too_large_422_no_volume_dir).
- Path traversal: id — uuid4().hex, генерируется сервисом, единственная форма каталога (^[0-9a-f]{32}$, is_video_id на каждом публичном id); от имени клиента берется только расширение после ^[a-z0-9]{1,8}$-нормализации (иначе "bin"); имя файла в путь не попадает нигде (в БД — метаданными, в UI — textContent, innerHTML только для статических SVG-констант — XSS чист). Тесты test_upload_avoids_path_traversal + test_storage изоляция путей (TC-vid-001…) — осмысленные.
- Отказ посреди записи: spool — tempfile ВНЕ тома; каталог в томе создается только после успешного спула; store_original-сбой → delete_video_dir, INSERT-сбой → delete_video_dir; temp чистится в finally. Каталог-мусор в томе не остается (тесты test_upload_aborted_body_leaves_nothing / _too_large_…_no_volume_dir это ассертят).
- **minor-1 (наблюдение, не блокер):** «потоковое» чтение — на самом деле копирование из spool'а Starlette: FastAPI резолвит UploadFile через request.form(), т.е. python-multipart УЖЕ спулил все тело в свой temp (в /tmp контейнера) до входа в хендлер; наш spool — второй темп. Пик диска в writable-слое контейнера ~2×500 МиБ на загрузку, вне тома и вне mem_limit. Том при этом чист (гарантия тестами), для куска A принято; замер NFR-35 на стенде — туда же смотреть диск /tmp при параллельных загрузках.
- **minor-2 (косметика):** UploadAborted маппится в тот же текст «file is larger than 500 MB» — при обрыве тела сообщение ложно (клиент его уже не увидит, но логи/422-тело вводят в заблуждение). Развести тексты в 3.1.

**(3) Удаление — ДА.** delete_video → _require_video (is_video_id) → DELETE row → delete_video_dir; video_dir кидает ValueError на любой не-uuid — rmtree физически не может выйти за <videos-dir>/<uuid>/, т.е. за пределы тома videos-data удаление невозможно по построению. 404 на чужом/маломformed id, паритет прав галереи FR-84. **minor-3 (низкий):** порядок «сначала БД, потом rmtree(ignore_errors=True)» — при сбое rmtree файлы остаются в томе без записи (тихий orphan-диск). Для консистентности API порядок разумный (запись без файлов = 404 файла), но ignore_errors глушит даже лог; в 3.1 — логировать результат rmtree (или возвращать bool).

**(4) Изоляция отказа и SQLite-профиль — ДА.** video вниз → nginx: /api/videos* → 503 JSON + Retry-After (@videos_down через proxy_intercept_errors + error_page), /videos/ → перехват 500-от-Auth_request в тот же @videos_down (нюанс auth_request→500 корректно задокументирован и обработан — F2 закрыт); ядро app не затронуто (проверено dev на стенде, конфиг прочитан — паттерн @search_down/@images_down дословно). SQLite: db.py НЕ трогает journal_mode (WAL-нейтралитет — RW-профиль ядра НЕ расширен файлово), busy_timeout=5000, foreign_keys=ON; код пишет только video_videos, читает users/sessions — test_core_tables_untouched фиксирует байт-нетронутость users/sessions. Миграция migrate_video: BEGIN IMMEDIATE одной транзакцией, идемпотентный CREATE IF NOT EXISTS, автосверка PRAGMA (колонки/DEFAULT/PK/FK) c exit 1 — паттерн migrate_gallery соблюден, двойной запуск безопасен.

**(5) Эскалации дев-агента — ЧАСТИЧНО ПРОВЕРЕНО, отчет в репозитории ОТСУТСТВУЕТ (minor-4, процесс).** В дереве репо отчета с 5 эскалациями нет (tests/REPORT*, openspec/changes/video-hosting/, docs — пусто). Единственная эскалация, трассируемая из коммит-месседжа 6383890: «форма 201 status:ready ОТКЛОНЯЕТСЯ от sdd §3 (uploaded)» — **согласен**: для куска A решение рабочее (список/плеер живут), шов enqueue_conversion() оставлен корректно, откат формы в 3.1 запланирован — отклонение задокументировано на месте. Остальные 4 эскалации оценить не могу — отчет не найден; ПМ приложить файл отчета (или вложить в tasks.md/openspec-папку), до тех пор этот пункт ревью считается не закрытым, а не согласованным.

**(6) [chore] aaa1900 / 48fa1c4 — ДА.** aaa1900: удалены ровно два файла (tests/api/test_rich_blocks.py, tests/web/test_rich_editor.py), оба импортируют app.rich_blocks — модуль откачен в 92bd2c8, collection errors реальны; наработка на полке подтверждена (коммит 901428c существует, rich-сьют 230 passed — факт прогона не повторял, ветка в месседже названа «rich», фактически pipeline/add-rich-editor — nit). Возврат pytest_plugins в корневой conftest.py корректен (pytest ≥ 8 запрещает не-корневой pytest_plugins; tests/web/conftest.py — регистрация снята, комментарий оставлен); проверено сбором: pytest tests/ --collect-only → 600 tests, 0 ошибок. 48fa1c4: ожидания сайдбара 5 пунктов + Sidebar.gallery_link/video_link — соответствует поставленному 1.5 (пункт «Видео» в base.html 5-м после «Галерея»); правка оправдана (патч волны 1 не лег).

---

## Находки

| # | Severity | Находка | Куда |
|---|---|---|---|
| minor-1 | low | Двойной temp-спул при загрузке (~2×500 МиБ в /tmp контейнера, вне mem_limit) — следить за диском в NFR-35 | волна 5 / 3.1 |
| minor-2 | cosmetic | UploadAborted → текст «file is larger than 500 MB» (ложное сообщение при обрыве) | 3.1 |
| minor-3 | low | DELETE: rmtree(ignore_errors=True) после коммита БД — тихие orphan-файлы при сбое; добавить лог результата | 3.1 |
| minor-4 | process | Отчет дев-агента с 5 эскалациями не найден в репо — согласовано 1/5 (201-ready), 4 не проверяемы | ПМ |
| nit | nit | В коммит-месседже aaa1900 полка названа «ветка rich» — фактически pipeline/add-rich-editor | — |
| note | info | /videos/ (nginx alias) проверяет только сессию, не статус видео: с куском B (статусы uploaded/converting) исходник станет скачиваемым через /videos/<id>/original.<ext> в обход API-409. В куске A не эксплойт (все сразу ready) — зафиксировать решение для 3.1/2.3: либо принять осознанно, либо authcheck с проверкой статуса | 3.1 |

## Проверено прогоном (этим ревью)

| Сьют | Результат |
|---|---|
| services/video/tests | **29 passed** (8.8s) |
| pytest tests/ --collect-only | **600 collected, 0 errors** (conftest-восстановление) |

## Вердикт: APPROVE

Кусок A соответствует sdd/design/specs по всем пяти фокусам; defense-in-depth авторизации (middleware + auth_request + unpublished ports + internal-локации) корректен, лимит и traversal закрыты тестируемо, том при отказах чист, WAL-нейтралитет соблюден. Minors не блокируют кусок A: minor-1/2/3 — в 3.1, minor-4 — на ПМ (приложить отчет эскалаций), note про /videos/-статус — принять решение к 3.1. Chore-коммиты aaa1900/48fa1c4 — корректны.

## Reviewer-Delegation

- deleg_649140ec (завершена, role=code_reviewer, кусок A, 2026-10-18)
