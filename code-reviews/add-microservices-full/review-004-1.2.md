# Ревью задачи 1.2 — пакет add-microservices-full (образы search/backup + compose прод/стенд)

Reviewer-Delegation: deleg-260608110985472e <!-- платформенный id в задании не передан; выведен из correlation_id задания 260608110985472e9c903a3b7b8aef28 по прецеденту review-004-1.1 (deleg-<префикс correlation_id>, role=code_reviewer); ПМ — сверить/вписать из реестра async_delegations. Отчет исполнителя: цикл deleg-95138022 -->

- Дата: 2026-10-04
- Ревьюируемый коммит: `980bbac` — «feat(services): образы search/backup + compose-сервисы (прод/стенд) — задача 1.2» (основной). Fix `41ffe87` (ro-открытие БД search) ревьюится отдельно (review-004-1.1); здесь учтено итоговое состояние дерева.
- База: HEAD ветки `add-microservices-full` = `f0fe4ec`; `git diff 980bbac..HEAD -- <зона 1.2>` пуст — финальное состояние зоны задачи с `980bbac` не менялось.
- Задача: 1.2 (tasks.md ЭТАП B): `services/search/Dockerfile` + `services/backup/{Dockerfile,backup.py}` + `deploy/compose.yaml` (прод) + `deploy/compose.test.yaml` (стенд). (design §1, §5, §7; FR-73 паритет)
- Автор: dev-делегация (не я — независимое ревью).
- Метод (собственные команды, отчет исполнителя deleg-95138022 не принимался на веру): `git show 980bbac` (полный дифф), построчное чтение 5 файлов зоны; сверка с design §1/§2/§5/§7 и дельтами specs (services/deploy) пакета; сверка пинов `services/search/Dockerfile` с `backend/requirements.txt`; сверка upstream `services/frontend/nginx/search-proxy.inc` (задача 1.3) с именем/портом сервиса; `python3 -m py_compile backup.py`; парсинг обоих compose-файлов yaml-парсером (структура, имена сервисов/томов); структурные sqlite-реплики ro-сценариев (A: wal+shm при ro-каталоге → чтение OK; B: wal/shm отсутствуют → mode=ro OK; C: `src.backup(dst)` с source mode=ro → OK; D: wal жив, -shm удален, каталог ro → OperationalError, подтверждает докстринг db.py; E: файла БД нет, mode=ro → OperationalError — старт до init_db app); grep-сверка заявлений compose-комментариев против deploy.sh (chown/10001/шаги); docker недоступен — живые build/smoke не воспроизводились (см. «Что НЕ проверено»).

---

## 1. Зона диффа

`git show 980bbac --stat`: ровно 5 файлов — `services/search/Dockerfile` (new), `services/backup/Dockerfile` (new), `services/backup/backup.py` (new), `deploy/compose.yaml` (+75), `deploy/compose.test.yaml` (+98/−14). Выхода за зону задачи нет. Чекбокс tasks.md 1.2 не снимался — корректно.

Внутри зоны есть сознательное расширение: в `compose.test.yaml` переведены app с tmpfs на именованный том проекта `wiki-test-data` и nginx-маунт avatars на тот же том (удален `avatars-test`). Обоснование в шапке файла и коммит-месседже корректно по существу: tmpfs не шарится между контейнерами — search/backup на tmpfs видели бы пустой /data (подтверждено репликами B/E: search 500 без схемы, backup не открывает источник); вариант «каждому свой tmpfs» ломает единственность данных. Изоляция от прода сохранена (проект `wiki-test` + отдельное имя тома; фактическое `wiki-test_wiki-test-data` ≠ продового `ekotov-wiki_wiki-data` — проверено по `name:` обоих файлов). Правка купирована документированно и не задевает nginx-образ задачи 1.3. Принимаю без замечания по существу; правило «одно инфраизменение в шаге» (tasks.md «Ворота») не нарушено — правки в пределах compose-файлов шага 1.2.

## 2. Search-образ и compose-сервис search (design §1/§2/§7, FR-73)

- **Dockerfile**: `python:3.12-slim`; слой deps с пинами `fastapi==0.141.1`, `uvicorn[standard]==0.53.0` — дословно синхронны `backend/requirements.txt:1-2` (проверено diff-сравнением строк); осознанное исключение playwright/pytest/Pillow/python-multipart обосновано (импорты `services/search/app/*` — только fastapi/starlette/uvicorn). `COPY services/search/app/ /srv/app/` + `WORKDIR /srv` + `uvicorn app.main:app` — та же схема пакетов, что у app; `--workers 1` (FR-73/design §7); `USER 10001` после COPY; `EXPOSE 8378` без публикации порта (design §1); данных в образе нет — подтверждено: COPY только кода, БД/аватары не копируются. HEALTHCHECK через urllib (curl в slim нет) — параметры (30s/10s/15s/3) идентичны app-образу и compose-маунту.
- **compose.yaml search**: `mem_limit: 512m` = design §7 и specs/deploy («search 512m»); `wiki-data:/data:ro` — файловая гарантия RO (specs/services, Scenario «RO-маунт»); `EKOTOV_WIKI_DB_PATH=/data/wiki.db` согласован с `services/search/app/db.py` (env-имя и дефолт); `depends_on: - app` БЕЗ `service_healthy` — соответствует задаче (search читает БД независимо; specs/deploy требует «после healthy ядра» только для деплой-матрицы deploy.sh — там шаг 5/8 wait_healthy app реализован, проверено grep deploy.sh). Healthcheck `:8378`, logging/restart — паритет app. Именованный образ без latest (FR-72).
- **Согласованность с nginx задачи 1.3**: `search-proxy.inc`: `set $upstream_search http://search:8378` — имя сервиса и порт совпадают с compose (внутрисетевое имя `search`, EXPOSE 8378, порт не публикуется); `X-Service: search` добавляет search-headers.inc — контракт «Деградация/Маршрутизация» specs/services не задет зоной 1.2. ✓
- На пустом томе search: `/api/health` exempt БД → healthy 200; реальный поиск до init_db app → 500. Задокументировано в комментарии compose.yaml:73-77; scenario «Схема не мигрирует» соблюден (search не мигрирует). Приемлемо.

## 3. Backup: образ, backup.py, compose (design §5, specs/services «sidecar»)

- **backup.py**: только stdlib (sqlite3/tarfile) — слой deps в образе отсутствует осознанно; `sqlite3 .backup` (WAL-safe) с source `mode=ro` — реплики B/C подтверждают работоспособность на ro-маунте; назначение удаляется при ошибке + контроль пустого размера (не оставляет «пустой бэкап»); avatars-tar терпит отсутствие каталога (паритет deploy.sh шаг 2); retention 14d строго по своим префиксам `wiki-daily-*`/`avatars-daily-*` — релизные `wiki-pre-*`/`avatars-pre-*` deploy.sh не трогает (контракт deploy.sh:193-208 сходится); cron-цикл `while True` с try вокруг run_backup — цикл переживает сбой тика; в том app не пишет (пишет только в bind /backups и /tmp). Дублирования с релизным бэкапом нет — deploy.sh 2/8 вызывает `from backup import run_backup` (один код, design §5), релизный шаг сохранен (проверено в deploy.sh:149-208).
- **Циклы/пробелы**: первый бэкап сразу при старте контейнера, далее раз в INTERVAL_SEC; при деплое контейнер backup пересоздается (новый образ) → сразу еще один daily-бэкап — дублирование с релизным wiki-pre-* безвредно (разные префиксы, retention независим). Пробел циклов при затяжном сбое — см. 1.2-d.
- **compose.yaml backup**: `mem_limit: 64m` = design §7 (пик при tar — оценка корректна: tarfile пишет потоково в файл, memory flat); том данных ro; bind `/var/backups/ekotov-wiki:/backups` = design §5/specs. Healthcheck heartbeat-процесса в образе — состав verifier'а разумный (stale > 2 интервалов). Но комментарий образа обещает то, что Docker не делает — находка 1.2-b; права на bind — находка 1.2-a.
- **compose.test.yaml backup**: тот же сервис, том проекта ro, bind `./backups-test` (изоляция от /var/backups хоста — NFR-10 ✓), цикл 3600с (проверяемость), retention тот же. Топология паритетна продовой ✓.

## 4. Стенд compose.test.yaml (FR-67/NFR-10)

Порт 8443→10443 внутрь ✓; SECRET_KEY дефолт-заглушка, не продовый ✓; `down -v` задокументирован как обязательный (том теперь персистентен — честно описано в шапке, риск «данные стенда переживают пересоздание» купирован процедурой); search/backup — те же параметры, что в проде, кроме тома/bind/интервала — FR-67 паритет соблюден. Порядок сервисов и healthcheck-параметры идентичны продовым.

---

## Находки

### 1.2-a (major) — запись sidecar в прод-bind не обеспечена механизмом; комментарий compose ссылается на несуществующий шаг deploy.sh

`deploy/compose.yaml:113-117`:

> Владелец на хосте — wiki:wiki (uid 10001; создан deploy.sh — тот же uid, что USER образа) → non-root пишет напрямую. Свежий хост: mkdir + chown 10001 из RUNBOOK (deploy.sh уже делает это в шаге 2/7).

Проверено по коду: **deploy.sh не делает никакого chown** — grep по `chown|10001` по `deploy/deploy.sh` пуст; шаг 2/8 (не «2/7» — шага с таким номером в v3 нет) делает только `run mkdir -p "${BACKUP_DIR}"` (deploy.sh:160), т.е. root-owned каталог. Штатная документация прав предписывает `chown wiki:wiki` **по имени** (deploy/README.md:172, RUNBOOK:150), а числовое равенство uid(wiki)==10001 нигде не создается и не проверяется — на этой машине, например, `wiki` = uid 999. Итог: единственная функция нового сервиса (межрелизная страховка) на свежем/перезаведенном хосте молча не работает: uid 10001 не может создать файл в bind → каждый тик падает (loop это переживает), heartbeat не пишется → контейнер постоянно unhealthy, рестартов нет (см. 1.2-b) — **межрелизных бэкапов нет**, при этом релизный бэкап deploy.sh работает и дефект не виден до попытки восстановления. На текущем проде bind уже существует с какими-то правами (экспертом не проверяемо — docker/доступ к VPS недоступны), но «какие-то права» ≠ «пишет uid 10001», и это нигде не зафиксировано как предусловие.

Лечение (малое, в основном документально-скриптовое): (1) idempotent-проверка/`chown 10001:10001 ${BACKUP_DIR}` в deploy.sh (шаг предусловий 1/8, только для прод-файла) — зона 1.4, координировать с ПМ; (2) поправить комментарий compose.yaml:113-117 (убрать ложную ссылку на deploy.sh, зафиксировать числовое требование 10001:10001); (3) RUNBOOK/README: `chown wiki:wiki` → `chown 10001:10001` (или явно проверить uid wiki на VPS = 10001 и зафиксировать). До правки — известный риск для 2.3/2.4 (свежий том проекта = свежие права).

Обоснование major: сервис создается ровно ради этой записи; гарантия не обеспечена ни кодом, ни документацией, а комментарий активно дезинформирует («deploy.sh уже делает»).

### 1.2-b (minor) — «stale-heartbeat → рестарт контейнера» — Docker так не работает

`services/backup/Dockerfile:33-37`: «stale-heartbeat (> 2 интервала) = деградация — рестарт контейнера». Docker restart policy реагирует только на exit процесса, на статус health — нет (autoheal-плагина в стеке нет). Фактический эффект stale-heartbeat: флаг unhealthy + fail гейта `wait_healthy` при деплое (deploy.sh:266) — это и достаточно, но комментарий обещает несуществующую автоматику самовосстановления и маскирует последствие находки 1.2-a («подвисший» backup останется unhealthy-надгробием между релизами, а не перезапустится). Лечение: переформулировать комментарий («деградация = unhealthy; рестарт — только при падении процесса (restart: unless-stopped); гейт деплоя — wait_healthy»).

### 1.2-c (minor) — устаревший комментарий тома в compose.yaml противоречит новому backup-сервису

`deploy/compose.yaml:160-163`:

> volumes: wiki-data: # wiki.db + avatars/. Бэкап — docker exec python sqlite3 .backup (design §6, метод зафиксирован до реализации).

Метод заменен этим же коммитом: бэкап — sidecar-сервис `backup` (строки 92-126 того же файла, sqlite3 .backup из контейнера backup, не docker exec). Комментарий дезориентирует при следующей правке. Лечение: переписать на «wiki.db + avatars/; бэкап — сервис backup (design §5)».

### 1.2-d (minor) — на свежем хосте первый суточный цикл backup может пройти до создания схемы app → окно до 24 ч без sidecar-бэкапа

`services/backup/backup.py:147-155` + `deploy/compose.yaml:118-121`: комментарий «depends_on нужен только чтобы БД существовала к первому циклу» — depends_on упорядочивает только старт контейнеров, не init_db внутри app. Реплика E: `file:...?mode=ro` на отсутствующем файле → OperationalError («unable to open database file») — первый тик на пустом томе падает, следующий через BACKUP_INTERVAL_SEC=86400. Так как процесс жив (unhealthy рестарт не триггерит), retry реально случится через сутки; к этому времени release-бэкап deploy.sh уже есть, поэтому риск ограничен, но заявленный интервал страховки на новом хосте нарушается. Лечение (одно из): N быстрых retry первого тика (например, 5 попыток с шагом 30s до первого успеха), либо честный комментарий об окне. На существующем проде не актуально.

### 1.2-e (nit) — предусловие `./backups-test` (chown 10001) не задокументировано в шапке стенда

`deploy/compose.test.yaml:146`: bind `./backups-test:/backups` — каталог, созданный docker от root, не записываем uid 10001 (отчет исполнителя, REPORT-1.4 п.2, это подтверждает — чинился chown'ом). Шапка compose.test.yaml описывает запуск, seed, останов, но не это предусловие. Лечение: 3 строки в шапку (`mkdir -p deploy/backups-test && chown 10001:10001` перед первым up, иначе backup unhealthy).

### 1.2-f (nit) — healthcheck search продублирован в образе и compose с одинаковыми параметрами

`services/search/Dockerfile:44-45` и `deploy/compose.yaml:80-85` (то же в test:116-121): compose-значение перекрывает образ. Дублирование — паритет паттерну app (осознанно), но при расхождении правок легко разъехаться. Лечение: комментарий в Dockerfile «каноничные значения — в compose» (у app сделано: «Интервал/лимиты — compose»); сейчас в search-образе такой отсылки нет.

---

## Позитивные проверки (сводка)

- Пины deps search-образа дословно синхронны `backend/requirements.txt`; состав deps обоснован импортами.
- FR-73/design §7: mem_limits (search 512m, backup 64m) и 1 воркер — точное соответствие specs/services и specs/deploy; суммарный бюджет стека 1.22 GB < лимита, резерв хосту соблюдается.
- Design §1: search/backup порты не публикуются; топология maунтов (app RW, search/backup RO, nginx RO avatars) соответствует; согласованность с nginx-конфом 1.3 (upstream `search:8378`) подтверждена.
- Design §5: релизный бэкап остался в deploy.sh (2/8), sidecar вызывает тот же `run_backup` — дубля кода нет; префиксный контракт retention двух механизмов сходится (daily vs pre).
- Реплики sqlite (A–E) подтвердили: чтение search и бэкап с source mode=ro работоспособны на ro-маунте в режимах «живой writer» и «простой без wal/shm»; случай D (wal без shm) корректно покрыт fallback'ом db.py (зона 1.1, учтено итоговое состояние 41ffe87).
- `py_compile backup.py` OK; оба compose-файла парсятся, имена сервисов/томов согласованы (search/backup в обоих, `wiki-data` / `wiki-test-data`).
- FR-72: дефолтные теги `:local`/`:test`, latest отсутствует в обоих файлах и образах.
- Зона записи ревьюера соблюдается: этот файл — единственная запись в рабочее дерево, коммит не делается.

## Что НЕ проверено (docker/стенд недоступны ревьюеру — прецедент review-001…004)

- Живой `docker build` обоих образов и smoke на стенде (заявления коммит-месседжа: размеры образов, health 200, RO-маунт фактически, integrity_check, retention-тест — не воспроизводились; частично компенсировано репликами sqlite и структурным анализом).
- Фактические права `/var/backups/ekotov-wiki` на прод-VPS и uid пользователя `wiki` там (существенно для 1.2-a — проверить при 2.3).

## Итог

**request_changes** — 1 major (1.2-a: запись sidecar в прод-bind не обеспечена; ложная ссылка на deploy.sh), 3 minor (1.2-b, 1.2-c, 1.2-d), 2 nit (1.2-e, 1.2-f). Архитектура, паритет FR-73/design и код backup.py по существу корректны; правки малые и преимущественно документально-скриптовые (deploy.sh-строка координируется с зоной 1.4). После устранения 1.2-a…d готов принять повторно коротким кругом по фикс-диффу.
