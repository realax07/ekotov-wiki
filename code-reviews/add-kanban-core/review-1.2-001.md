# Code Review: задача 1.2 «Схема SQLite (миграция/seed-init)» — review-1.2-001

- **Репозиторий:** ekotov-wiki, ветка main
- **Диф:** коммит `a5614e2` «task 1.2: sqlite schema migration» (2 файла: `backend/app/db.py` +93, `tasks.md` чекбокс — диф чистый, посторонних изменений нет)
- **Арбитры:** sdd.md §4 (модель данных), §5 (NFR-3/5), tasks.md 1.2
- **Процедура:** скилл code-review, три круга (спека → практики → integration)
- **Дата:** 2026-09-17

## Вердикт: **approve**

Задача 1.2 выполнена полностью: схема SQLite дословно соответствует sdd.md §4, миграция
запускается как скрипт, идемпотентна (проверено двойным запуском), WAL и FK-контроль
включаются в `get_connection()`. Все заявления dev-отчета проверены ревьюером фактически
(собственные запуски миграции, дамп `.schema` через sqlite3-модуль, поведенческие
smoke-тесты CHECK/UNIQUE/FK/CASCADE) — подтверждены. Blocker, major, minor: отсутствуют.

## Круг 1 — соответствие спеке (sdd.md §4, построчная сверка с фактической БД)

Сверка выполнена по дампу реальной БД `/tmp/review_12.db` (`sqlite_master` +
`PRAGMA foreign_key_list`), не по исходнику db.py.

| Объект §4 | Факт в БД | Статус |
|---|---|---|
| users: id PK, login UNIQUE NOT NULL, password_hash NOT NULL | совпадает дословно | OK |
| sessions: token PK, user_id NOT NULL FK→users.id, created_at, expires_at NOT NULL | совпадает; FK подтвержден `foreign_key_list` | OK |
| tasks: 11 полей — title NOT NULL; priority CHECK(low/medium/high OR NULL); is_fast INTEGER NOT NULL DEFAULT 0; status NOT NULL DEFAULT 'todo' CHECK(todo/in_progress/done); archived_at NULLable; created_at/updated_at NOT NULL | совпадает дословно, включая DEFAULT и оба CHECK | OK |
| tags: id PK, name UNIQUE NOT NULL | совпадает | OK |
| task_tags: PK(task_id,tag_id); task_id FK→tasks.id **ON DELETE CASCADE**; tag_id FK→tags.id (без каскада — по спеке) | совпадает; CASCADE подтвержден `foreign_key_list` (on_delete=CASCADE для tasks) и smoke-тестом | OK |
| comments: task_id FK→tasks.id **ON DELETE CASCADE**; author_id FK→users.id (без каскада — по спеке); body, created_at NOT NULL | совпадает | OK |
| Индексы: ровно 5 — tasks(status,is_fast), tasks(archived_at), tasks(priority), task_tags(tag_id), comments(task_id) | ровно 5, имена и столбцы совпадают; лишних и недостающих нет | OK |
| Таблиц ровно 6 | users, sessions, tasks, tags, task_tags, comments — других (кроме служебных sqlite_*) нет | OK |

Пункт tasks.md 1.2: «скрипт создает БД с нуля» — OK (запуск с пустым путем);
«повторный запуск идемпотентен» — OK (факт-чек ниже).

## Круг 2 — практики / security (проверено исполнением)

| # | Заявление dev | Проверка ревьюера | Результат |
|---|---|---|---|
| 1 | Первый запуск создает БД | `rm -f /tmp/review_12.db*`; `DB_PATH=/tmp/review_12.db SECRET_KEY=x python3 -m app.db` → exit 0, «Схема применена» | ✅ |
| 2 | Повторный запуск идемпотентен | Второй запуск того же скрипта → exit 0, без ошибок; схема в `sqlite_master` не задублирована (по 1 определению на объект) | ✅ |
| 3 | WAL в `get_connection()` | `PRAGMA journal_mode` через соединение из `get_connection()` → `('wal',)` | ✅ |
| 4 | foreign_keys=ON в `get_connection()` | `PRAGMA foreign_keys` через то же соединение → `(1,)` (замечание: дефолт SQLite — 0; факт-тест FK ниже проходит только благодаря прагме) | ✅ |
| 5 | users=0 после создания схемы | `SELECT COUNT(*) FROM users` → 0 (seed — задача 1.3, users не создаются) | ✅ |
| 6 | CHECK-констрейнты работают | INSERT status='nope' → IntegrityError «CHECK constraint failed: status…»; INSERT priority='urgent' → IntegrityError «CHECK constraint failed: priority…» | ✅ |
| 7 | UNIQUE работает | Двойной INSERT users.login='a' → IntegrityError «UNIQUE constraint failed: users.login» | ✅ |
| 8 | FK-контроль работает | INSERT comments с author_id=999 (нет в users) → IntegrityError «FOREIGN KEY constraint failed» | ✅ |
| 9 | ON DELETE CASCADE работает | INSERT task+tag+task_tags → DELETE task → task_tags опустел (0 строк) — каскад фактически сработал | ✅ |
| 10 | Нет DB_PATH → понятная ошибка | Запуск `python -m app.db` без env → RuntimeError «Обязательная переменная окружения DB_PATH не задана…» — fail-fast на импорте config, без стек-мусора в stdout, без дефолтного пути | ✅ |
| 11 | SQL-инъекции / секреты | SCHEMA_SQL — статический DDL без конкатенации пользовательского ввода; секретов в коде нет; DB_PATH/SECRET_KEY из env | ✅ |
| 12 | БД не в git (NFR-5) | Файлы БД создавались только в /tmp; `git show a5614e2 --stat` — только db.py и tasks.md | ✅ |

## Круг 3 — integration-точки

- Соседние сценарии: задача не меняет поведение каркаса (main.py не затронут);
  `get_connection()` — новая точка, которую следующие задачи (1.3 seed, 2.x API)
  будут использовать; сигнатура с опциональным `db_path`-переопределением совместима
  с конфигом из env (задача 1.1).
- Комментарии в SCHEMA_SQL трассируются на FR-3/FR-4/FR-5/ОГР-3/NFR-7 — расхождений с
  спекой нет.
- tasks.md: отмечен ровно чекбокс 1.2, формат строки сохранен.

## Замечания

Отсутствуют (blocker: 0, major: 0, minor: 0).

## Проверено фактически (сводка)

Двойной запуск `python -m app.db` с DB_PATH=/tmp/review_12.db; дамп схемы из реальной БД
и построчная сверка с sdd.md §4 (6 таблиц, все поля/типы/DEFAULT, 2 CHECK, UNIQUE,
FK-направления и ON DELETE CASCADE, ровно 5 индексов); PRAGMA journal_mode=wal и
foreign_keys=1 через `get_connection()`; users=0; поведенческие smoke-тесты CHECK,
UNIQUE, FK, CASCADE; отказ без DB_PATH; чистота диф-а.

## Что не проверено (честно)

- Поведение под реальной конкурентной нагрузкой двух процессов (WAL-локи) — вне объема
  задачи 1.2; покрывается NFR-замерами tasks 8.x.
- Скользящий TTL сессий и формат timestamp-строк created_at/expires_at — логика еще не
  написана (задачи 1.3/2.1); схема фиксирует только TEXT NOT NULL, как в §4.
- Соответствие запуска в systemd/uvicorn (task 1.4) — задача еще не реализована.
