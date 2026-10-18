# Code review — video-hosting, review-002: волны D (b43ef99), B (13855d5), C (f8a15f1)

Роль: code_reviewer (независимый). Ревьюируемый объем: дельта с review-001 (голова 77613d7) —
кусок D (b43ef99, tasks 2.1–2.5), кусок B (13855d5, tasks 3.1–3.2), кусок C (f8a15f1, task 4.1);
отчеты дев-агентов dev-report-D-wave2.md, dev-report-B.md, dev-report-C.md. База: main.
Фокус ТЗ: (1) атомарность реакций/403/CASCADE; (2) инъекция в subprocess, timeout-kill,
re-enqueue без дубля, удаление оригинала; (3) RO справочника категорий; (4) LIKE-escape;
(5) 7 эскалаций отчетов B/C; (6) tasks.md.

Метод: чтение дифа 77613d7..f8a15f1 (services/video/app/{social,converter,videos,db,main,storage}.py,
backend/app/migrate_video.py, фронтенд, тесты) против sdd §2/§3/§4, design §3/§7/§8; grep-пробы
(запись в image_categories, env-переменные в deploy/); прогон services/video/tests (66 passed, 15.6s,
venv backend/.venv) и сбор tests/ --collect-only (607 тестов, 0 errors). Полный регресс на стенде не
гонялся — паритет отчетам девов (стенды наборов в этой среде не поднимаются, фон сверен ими с чистым HEAD).

---

## Проверка по фокусам

**(1) Соцслой — ДА.**
- *Атомарность реакций:* put_reaction — SELECT голоса, DELETE (снятие) / UPDATE (перенос) / INSERT —
  в одной транзакции BEGIN IMMEDIATE на соединении с busy_timeout=5000 (db.py). Два одновременных
  клика одного пользователя сериализуются BEGIN IMMEDIATE: второй ждет блокировку, читает
  post-commit-состояние и честно toggle'ит — двух голосов на пару (PK video_id+user_id) не возникает
  и по построению, и по CHECK. Расчет счетчиков — после commit, отдельным чтением (нестрогий
  snapshot-ответ допустим). Коды 422 (value∉{1,-1}) / 404 на месте.
- *403 на чужой комментарий:* delete_comment — 404 (нет видео/комментария) → 403 (user_id ≠ сессия)
  → DELETE своего; тест test_comment_delete_only_own покрывает обе ветки. Раскрытие существования
  чужого комментария через 403 — паритет спеки (Scenario «Удаление только своего»).
- *CASCADE:* video_comments/video_reactions — FK video_id REFERENCES video_videos(id) ON DELETE
  CASCADE (DDL миграции); migrate_video._verify проверяет on_delete=CASCADE по PRAGMA
  foreign_key_list; каскад работает при foreign_keys=ON (db.get_connection) — runtime-тест
  test_delete_video_cascades_social (строки = 0 после DELETE).
- Замечание (не блокер, см. minor-5): настоящая конкурентность (два потока/клиента на одну пару)
  тестами не покрывается — атомарность подтверждена чтением кода + серийными тестами toggle/переноса.

**(2) Конвертер — ДА, uuid-пути из куска A держатся.**
- *Subprocess-инъекция:* cmd = [ffmpeg_bin(), «-nostdin», «-y», «-i», orig] + VIDEO_ARGS + [mp4] —
  shell=False (list-argv, shell-метасимволы не интерпретируются); orig/mp4/preview — ТОЛЬКО пути
  storage (<videos-dir>/<uuid-hex>/original.<ext>, video.mp4, preview.jpg): имя каталога — uuid4 сервиса,
  расширение нормализовано ^[a-z0-9]{1,8}$ (кусок A), пользовательское имя файла в argv не попадает
  нигде; «-nostdin» закрывает чтение stdin. Опция-инъекция через имя, начинающееся с «-», невозможна —
  имя файла всегда «original.<ext>»/«video.mp4» внутри uuid-каталога. ffmpeg_bin — только env
  (EKOTOV_WIKI_FFMPEG, конфигурация окружения, не пользовательский ввод).
- *Timeout-kill:* subprocess.run(timeout=1800) на истечение сам kill()+wait() ребенка — зомби не
  остается; stdout/stderr=DEVNULL (нет pipe-дедлока), stdin=DEVNULL; тест
  test_timeout_kills_process_and_retries. Ограничение: kill — только прямой ребенок (сам ffmpeg;
  в проде это бинарь без внуков — оберток нет); preexec_fn=os.nice — минимальный fork-хук
  (см. nit-1).
- *Крэш-восстановление без дубля:* recover_pending() — только в start_worker(), который идемпотентен
  (guard _worker.is_alive) и зовется один раз из lifespan; uvicorn --workers 1 (Dockerfile CMD) —
  одного процесса/очереди на сервис. convert_attempts персистится в БД → крэш посреди попыток НЕ
  сбрасывает бюджет ретраев (после крэша на попытке 1 Recovered-проход сделает ровно еще одну).
  Тест test_crash_recovery_reenqueues_uploaded_and_converting.
- *Удаление оригинала только после успеха:* _remove(orig) — единственная точка, после break по
  успешной _attempt; на error-пути оригинал сохранен (тест test_convert_error_keeps_original);
  для уже-mp4 оригинал остается playable (без перекодирования, escalation B-4 — согласен, design §3 r2).
  Нюанс порядка «статус ready → remove orig» — minor-1.
- *Гонка DELETE↔воркер:* cancel ДО удаления строки/каталога; воркер проверяет флаг на входе, перед
  каждой попыткой и перед записью результата; UPDATE по удаленной строке = 0 строк; _remove/
  _discard_artifacts глотают FileNotFoundError; ffmpeg в удаленный каталог не пишет (open падает) —
  сирот в томе гонка не оставляет. Тесты test_delete_cancel_discards_artifacts /
  test_delete_removed_row_is_noop_for_worker / test_cancel_before_start_discards_without_status.

**(3) Категории — только SELECT чужого справочника — ДА.** Все касания image_categories в коде
сервиса: SELECT списка (social.py), SELECT валидации category_id (videos.py), LEFT JOIN в списке.
INSERT/UPDATE/DELETE на image_categories в services/video/app — ноль (grep; INSERT'ы — только в
фикстурах тестов, вне прод-кода). Создание категорий — POST /api/categories ядра с фронта.
Миграция справочник не создает (fail fast при отсутствии), RW-профиль в db.py задокументирован.

**(4) Поиск LIKE-escape — ДА, обходных векторов не нашел.**
- Экранирование в правильном порядке: `\` → `\\`, затем `%`/`_` → `\%`/`\_`; ESCAPE '\' в SQL;
  needle — параметр (конкатенация '%' || lower(?) || '%' в SQL — инъекции нет). Тест
  test_like_wildcards_are_literals (a_b vs axb, 100%).
- Векторы проверены чтением: backslash-хвост («a\» → «a\\» — литерал, порядок замен корректен),
  wildcard через ESCAPE-символ, кириллица (lower перекрыт unicode-функцией на соединении —
  «ПРИВЕТ» находится по «привет», тест TC-vid-081), пробелы/whitespace (trim, пустой — все).
  NUL-байт в query деградирует только точность фильтрации (обрезка на границе C-строки SQLite),
  не инъекция — на практике недостижим из HTML-формы.
- Отклонение от буквы 4.1 (unicode-lower вместо ASCII COLLATE NOCASE) — согласен (эскалация C-1):
  acceptance-сценарий спеки требует кириллицу, встроенный lower/NOCASE SQLite — ASCII-only;
  create_function deterministic — lower остается валидным в выражениях; перекрытие локально
  соединению сервиса.

**(5) Эскалации отчетов — все 7 СОГЛАСЕН.**

| # | Эскалация | Вердикт |
|---|---|---|
| B-1 | storage.find_original — точечное расширение зоны 1.3 | Согласен: шов sdd §2 «пути только через storage», иначе конвертер строил бы пути сам |
| B-2 | start_worker в lifespan, не на импорте | Согласен: импортный старт читал БД до env — дефект реальный, lifespan корректное место |
| B-3 | env-гейты EKOTOV_WIKI_CONVERTER/EKOTOV_WIKI_FFMPEG | Согласен: дефолты прод-безопасны (on / PATH; ffmpeg в образе). Но задокументировать — minor-3 |
| B-4 | mp4-исходник без rename в video.mp4 | Согласен: design §3 r2 «без перекодирования»; playable_path отдает original.mp4 |
| B-5 | flow_check J10: 13 закрытых задач без approve на момент волны | Согласен: ожидаемый фон до ревью; порядок «чекбокс после вердикта» отныне соблюдается |
| C-1 | unicode-lower вместо буквального COLLATE NOCASE | Согласен: acceptance требует кириллицу; см. фокус (4) |
| C-2 | фикс polling-потери фильтров (шов B×C) | Согласен: поиск/категория обязаны переживать автообновление; buildListParams() общий для loadList/refreshTick — проверено в video.js |

**(6) tasks.md — ДА.** Все dev-задачи [x]: 1.1–1.6, 2.1–2.5, 3.1–3.2, 4.1 (порядок маркеров
корректный: `[x] N.N [code] [M]` — маркер сразу после ID); QA-волна 5.1–5.7 — все [ ],
деплой-волна 6.1–6.3 — все [ ]. Сбор tests/ — 607 тестов, 0 collection errors.

---

## Находки

| # | Severity | Находка | Куда |
|---|---|---|---|
| minor-1 | low | Конвертер, успех: status=«ready» коммитится ДО _remove(orig); сбой remove (не-FileNotFoundError OSError) или крэш между коммитом и remove оставляет original.<ext> навсегда (recover трогает только uploaded/converting) — тихий orphan на диске тома. Рекомендация: удалять оригинал до set-ready (падение → recover → «original missing» → error с готовым mp4 хуже) ЛИБО one-shot свип orphan-original'ов у ready-записей в recover_pending | 6.x / backlog |
| minor-2 | low | converter.cancel() зовется при КАЖДОМ DELETE (videos.py), но _unmark_cancelled — только в finally обработанного элемента очереди; id удаленных ready-видео навсегда остаются в _cancelled set — неограниченный (медленный) рост памяти за жизнь процесса. Рекомендация: чистить в delete_video после удаления (discard) или discard в _process по row is None | 6.x / backlog |
| minor-3 | low/process | Новые env EKOTOV_WIKI_CONVERTER/EKOTOV_WIKI_FFMPEG не отражены в deploy/RUNBOOK.md (в compose их нет — дефолты прод-корректны). По blast-radius (rev-002 §4a) новые env-переменные документируются | 6.1 |
| minor-4 | low | Реальная конкурентность (два одновременных клиента на toggle одного голоса; DELETE↔конвертация в интерливинге) тестами не покрыта — атомарность подтверждена кодом (BEGIN IMMEDIATE) и серийными тестами. При контеншене > busy_timeout клиент получает 500 (OperationalError), не 409/200 — приемлемо, но знать | волна 5.5 (набор api) |
| minor-5 | cosmetic | list_videos order=asc: tie-break v.created_at DESC внутри одного имени — «свежие выше» на равных именах; поведение не специфицировано, отметить в 5.2 при написании кейсов | волна 5.2 |
| nit-1 | nit | preexec_fn=os.nice в многопоточном процессе формально не рекомендован (fork+preexec_fn); os.nice — async-signal-safe и хук минимальный, риска практически нет — не трогать без причины | — |
| note | info | review-001 note (обход статуса через /videos/-alias) — принято девом осознанно (равноправие FR-84, authcheck O(мс)); согласен с принятием, зафиксировано в dev-report-B | закрыто |

## Проверено прогоном (этим ревью)

| Сьют | Результат |
|---|---|
| services/video/tests | **66 passed** (15.6s) — 44 D + 15 B + 7 C на месте |
| pytest tests/ --collect-only | **607 collected, 0 errors** |

## Что НЕ проверено (честно)

- Полный регресс на живом стенде (api/web-наборы) — среда ревью не поднимает стенд :8080; фон
  претестовых падений сверен девами с чистым HEAD, принят по отчетам (паритет всем трем волнам).
- Реальная многопоточная гонка реакций — только аргументация по BEGIN IMMEDIATE (см. minor-4).
- Браузерный прогон фронтенда (video.js/video.html) — проверено чтение (XSS: textContent/user-данные,
  innerHTML только статические SVG; buildListParams общий; debounce/trim), не playwright.
- Сквозной смоук с реальным ffmpeg повторен не был — принят отчет B (TestClient + реальный ffmpeg).

## Вердикт: APPROVE

Волны D/B/C соответствуют sdd/design/specs по всем шести фокусам ТЗ. Атомарность реакций
(BEGIN IMMEDIATE + PK), 403/CASCADE, RO справочника, LIKE-escape с обходом кириллицы, изоляция
subprocess (shell=False, uuid-пути куска A держатся, -nostdin), timeout-kill без зомби, re-enqueue
без дубля и потерянных ретраев, удаление оригинала только после успеха — подтверждены кодом и
тестами. Все 7 эскалаций отчетов B/C согласованы. Minors не блокируют: minor-1/2 — backlog/6.x,
minor-3 — документирование env к 6.1, minor-4/5 — учесть в QA-волне 5. Следующий рубеж —
QA-контур 5.1–5.7 (чекбоксы корректно остаются [ ]).
