# Фикс-цикл по review-004-1.1 (+ 1.2-f) — search-сервис

Корреляция flowctl: a4d1b09b8d2e42d6968acaead9cdf7c2. Ветка: `add-microservices-full`.
Зона: `services/search/**` (контракт `contracts/openapi-search.json` не тронут).

## Что сделано

### 1.1-a (major) — TC-212 не проходил через fallback immutable=1
**Файл:** `tests/test_search_service.py` (фикстура `db_path`).

Причина подтверждена эмпирически: фикстура создавала БД в delete-journal-режиме
(заголовок write/read_version = 1/1, байты 18/19). На такой БД probe `mode=ro`
на ro-каталоге **успешен** — fallback `immutable=1` не исполнялся, тест был
зеленым независимо от работоспособности fallback-ветки.

Фикс: фикстура задает `PRAGMA journal_mode=WAL` (заголовок 2/2 сохраняется
после закрытия писателя) и явно удаляет остатки `-wal`/`-shm` — состояние
«wal физически отсутствует», ровно сценарий TC-212. Probe `mode=ro` падает
(«attempt to write a readonly database») → исполняется fallback.

Попутно ужесточен TC-213: писатель теперь держит соединение **открытым** на
время запроса (раньше закрывал до запроса, `-wal/-shm` исчезали и тест мог
пройти через fallback — что противоречит его смыслу «свежесть при живом wal»).

### 1.1-b (major) — TC-214 не дискриминировал дефектный middleware
**Файл:** `tests/test_search_service.py` (`test_expired_session_select_only`).

Тест переведен на ro-каталог БД (как TC-212): `os.chmod(ro_dir, 0o500)` на
время запроса. Дефектный вариант (ядро-поведение: DELETE истекшей сессии +
sliding-TTL UPDATE) на этом условии дает 500 («attempt to write a readonly
database»), SELECT-only вариант — 401.

### 1.1-c (minor) — 422-handler без jsonable_encoder
**Файл:** `app/main.py`.

`exc.errors()` обернут в `jsonable_encoder(...)` (паритет ядра
`backend/app/tasks.py:706`), импорт добавлен. Без обертки ctx с
не-JSON-сериализуемым объектом (например, `ValueError` из custom-валидатора)
приводил к 500 вместо 422.

### 1.1-d (minor) — мертвый SESSION_TTL
**Файл:** `app/middleware.py`.

`SESSION_TTL` удален, импорт `timedelta` убран; комментарий у
`SESSION_COOKIE_NAME` переписан: TTL продлевает app, в сервисе скользящего
продления нет (ro-маунт, ревью задачи 1.2).

### 1.1-e (nit) — _open_readonly
**Файл:** `app/db.py`.

- (1) Fallback ловит `sqlite3.Error` (вместо только `OperationalError`) —
  `DatabaseError` (поврежденный wal-index и пр.) тоже уходит в immutable=1
  вместо 500.
- (2) Утверждение ревью про `quote(path, safe='/')` **не подтвердилось**
  (проверено: `quote('/tmp/a?b#c?d', safe='/')` → `'/tmp/a%3Fb%23c%3Fd'` —
  `?` и `#` экранируются). Код не менялся.

### 1.2-f (nit) — healthcheck-дубль в Dockerfile
**Файл:** `Dockerfile`.

Добавлен комментарий «каноничные значения интервалов/лимитов — в
deploy/compose.yaml; синхронизировать при изменении» — паритет
`services/app/Dockerfile`.

## Прогон тестов

| Момент | Результат |
|---|---|
| До (baseline) | 12 passed (1.30s) |
| После всех фиксов | **12 passed** (1.40s) |

## Негативные пруфы дискриминации

### Пруф 1.1-a (ветка fallback мертва на старой фикстуре)
Скрипт-реплика `_open_readonly` на двух БД, ro-каталог:

| Фикстура | Ветка исполнения |
|---|---|
| delete-journal (старая) | `mode_ro` — probe успешен, fallback НЕ исполнялся |
| WAL (новая) | `immutable` — probe упал, fallback исполнился |

⇒ До фикса TC-212 не проверял fallback-ветку вообще; после — проверяет.

### Пруф 1.1-b (дефектный middleware валится новым TC-214)
Дефектный `_is_valid` (DELETE+UPDATE+commit, реконструкция старого варианта):

| Условие | Соединение | Результат |
|---|---|---|
| writable dir (старый TC-214) | rw (ядро-стиль) | **401** — дефект проходил незамеченным (гипотеза ревью подтверждена) |
| writable dir (старый TC-214) | ro-URI слоя db.py | 500 — запись запрещена самим URI-режимом |
| **ro dir (новый TC-214)** | rw (ядро-стиль) | **500** — тест красный, дискриминирует |
| ro dir (новый TC-214) | актуальный SELECT-only код | 401 — зеленый |

⇒ Новый TC-214 валит дефектный вариант и проходит на актуальном.

### Пруф 1.1-c (500 вместо 422 без jsonable_encoder)
Мини-app с тем же handler-кодом; валидатор бросает `ValueError` в query-парамeтре
(BeforeValidator → `ctx: {'error': ValueError(...)}`):

| Handler | Статус |
|---|---|
| `details: exc.errors()` (до фикса) | **500** — дефект подтвержден |
| `details: jsonable_encoder(exc.errors())` (после) | **422** — фикс работает |

## Измененные файлы

- `services/search/tests/test_search_service.py` — фикстура WAL + очистка wal/shm; TC-213 live-writer; TC-214 ro-dir.
- `services/search/app/main.py` — jsonable_encoder (1.1-c).
- `services/search/app/middleware.py` — SESSION_TTL удален, комментарий поправлен (1.1-d).
- `services/search/app/db.py` — fallback ловит sqlite3.Error (1.1-e).
- `services/search/Dockerfile` — комментарий про каноничные значения healthcheck (1.2-f).

Контракт `contracts/openapi-search.json` и все файлы вне `services/search/**` не тронуты.
