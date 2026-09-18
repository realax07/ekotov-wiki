# Автотесты add-kanban-core (tests/)

pytest + requests набор по 80 approved-кейсам `test-model/approved/add-kanban-core/`
(7 файлов кейсов: auth 17, board 10, fastline 12, tasks 16, archive 9, search 11,
navigation 5). Правила: 1 кейс = 1 тест минимум, ID кейса (TC-…) — в docstring,
маркеры приоритета MoSCoW из кейса, изоляция и детерминизм (скилл test-automation).

## Запуск

```bash
# 1. Приложение запущено (локально: из backend/, см. deploy/README.md):
DB_PATH=/tmp/app.db SECRET_KEY=<hex> uvicorn app.main:app --host 127.0.0.1 --port 8080
# 2. Схема + seed-пользователи (идемпотентно):
DB_PATH=... SECRET_KEY=... python -m app.db && python -m app.seed_users

# 3. Прогон (из корня репозитория):
EKOTOV_WIKI_BASE_URL=http://127.0.0.1:8080 \
EKOTOV_WIKI_DB_PATH=/tmp/app.db \
python -m pytest tests/ -q
```

Вход теста:
- `EKOTOV_WIKI_BASE_URL` — корень приложения (дефолт `http://127.0.0.1:8080`;
  либо флаг `--base-url`). VPS: домен из deploy/README.md (там же запросы идут
  по https — Secure-кука отправляется штатно).
- `EKOTOV_WIKI_DB_PATH` — путь SQLite-БД приложения. Нужен ТОЛЬКО кейсам с
  прямой правкой/чтением БД (смещение done_at, истечение сессии, bcrypt-осмотр):
  без переменной эти тесты `skip`, остальные проходят.
- `EKOTOV_WIKI_OWNER_PASSWORD` / `EKOTOV_WIKI_WIFE_PASSWORD` — пароли seed-пользователей
  (дефолты — тестовые значения локального прогона; на VPS задать явно).

Стек: `pytest`, `requests` (добавлены в `backend/requirements.txt`).

## Маркеры

| Маркер | Смысл |
|---|---|
| `api` | API-тест (requests) — весь набор |
| `must` / `should` / `could` | приоритет MoSCoW из одобренного кейса |
| `manual` | НФТ-процедура: автоматизация нецелесообразна, шаги в docstring |
| `web_ui` | UI-часть кейса: скоуп tests/web (браузер), здесь skip |

Выбор: `pytest tests/ -m must`, `-m "not manual"` и т.п. (`pytest.ini` регистрирует маркеры).

## Особенности окружения

- **Secure-кука по http.** Продукт ставит куку `session` с `Secure` (sdd §3.1).
  requests не отправляет Secure-куку по http, браузеры же для localhost
  (trustworthy origin) — отправляют. `LocalhostSession` (conftest) повторяет
  браузерное поведение для http://localhost / 127.0.0.1; на https-развертывании
  работает штатная механика.
- **Прямые операции с БД** (TC-board-005, TC-arch-002/003/007, TC-tasks-009,
  TC-auth-002/017) — через `EKOTOV_WIKI_DB_PATH`; эмуляция прошедшего МСК-дня —
  вариант Б кейсов (допустимая замена, отмечена в docstring каждого теста).
- **Изоляция:** все тестовые задачи имеют префикс `QAT-` и удаляются в teardown
  (фикстуры `api`/`cleanup_task`); сессии авторизации — function-scope.
- **Детерминизм:** sleep нет; готовность сервера — poll `/api/health` с таймаутом.

## НФТ-кейсы: решение по автоматизации

- **CHK-17 (TC-auth-017), осмотр БД** — `@pytest.mark.manual` + автоматизируемая
  часть `test_owner_password_hash_is_bcrypt` ($2b$, длина ≥60) при заданном
  DB_PATH. `grep` по бинарному файлу БД и `git check-ignore` зависят от
  окружения развертывания — ручная процедура (docstring теста).
- **CHK-55 (TC-tasks-015), CHK-56 (TC-tasks-016), рестарт** —
  `@pytest.mark.manual`: тест не может безопасно перезапускать процесс сервиса
  (systemctl/uvicorn) из pytest-сессии; процедуры в docstring (снимки до/после,
  poll health ≤60 с, diff пуст).
- **CHK-59 (TC-arch-003), граница полуночи МСК** — реализован вариант Б
  (эмуляция смещением done_at — допустимая замена по кейсу): `test_msk_midnight_boundary_done_2358_archives_next_day`.
  Вариант А (живое ожидание 23:58 МСК + 10 мин) — ручная процедура: ожидание
  полуночи в автотесте нарушило бы детерминизм и скорость прогона.
- **CHK-56/55 производительность** — NFR-2/NFR-1 (1000+ задач, ≤2 с) — кейсов в
  approved-наборе нет (вне скоупа; tasks.md 8.2 закрывается отдельной проверкой).

## UI-части кейсов (скоуп tests/web, вне API-набора)

Кейсы с браузерными шагами (переходы по сайдбару, форма, drag-n-drop, DOM/CSS
fast line) покрыты API-частью здесь; UI-проверки отмечены `@pytest.mark.web_ui`
со skip или упомянуты в docstring. Полный список UI-остатка: TC-auth-009/010/011
(частично), TC-board-001/003/007 (браузерная часть), TC-fast-001/005/012,
TC-tasks-005/011 (диалог подтверждения), TC-search-001/005/006/007 (UI-половина),
TC-arch-004/008/009 (бейджи), TC-nav-001…005 (клики по сайдбару) — tests/web,
отдельный playwright-набор.

## Матрица трассировки: 80 кейсов → тесты

| Домен | Кейсы | Тестов (модуль) | Примечание |
|---|---|---|---|
| auth | TC-auth-001…016 (16) | 16 + 1 параметризация×3 (TC-auth-009) | test_auth.py |
| auth | TC-auth-017 (1, НФТ) | manual-процедура + 1 автотест ($2b$) | test_auth.py |
| board | TC-board-001…010 (10) | 10 | test_board.py |
| fastline | TC-fast-002/003/004/006/007/008/009/010/011 (9) | 9 | test_fastline.py |
| fastline | TC-fast-001/012 (2, UI) | 2 × web_ui-skip (скоуп tests/web) | test_fastline.py |
| fastline | TC-fast-005 (1, UI-негатив) | web_ui (скоуп tests/web): создание второй fast через UI-форму | test_fastline.py |
| tasks | TC-tasks-001…014 (14) | 14 | test_tasks.py |
| tasks | TC-tasks-015/016 (2, НФТ-рестарт) | 2 × manual | test_tasks.py |
| archive | TC-arch-001…009 (9) | 9 (003 — вариант Б) | test_archive.py |
| search | TC-search-001…011 (11) | 11 | test_search.py |
| navigation | TC-nav-001…005 (5) | 5 (API-часть; UI — tests/web) | test_navigation.py |
| **Итого** | **80 кейсов** | **82 теста** (77 проходят, 5 skip: 2 рестарт-НФТ, 1 bcrypt-БД, 2 UI-fastline) | |

Чексумма кейсов: auth 17 + board 10 + fastline 12 + tasks 16 + archive 9 + search 11 + navigation 5 = 80.
Кейс CHK-35 (fastline) отсутствует в approved (отложен: DS-1) — теста нет и не требуется.

## Прогон (эталон, локально)

```
EKOTOV_WIKI_BASE_URL=http://127.0.0.1:8080 EKOTOV_WIKI_DB_PATH=/tmp/app.db \
python -m pytest tests/ -q
→ 77 passed, 5 skipped, 0 failed   (~31 c)
Без EKOTOV_WIKI_DB_PATH → 60 passed, 22 skipped (БД-кейсы пропущены).
```

Падение теста при верном коде теста = кандидат в дефекты продукта →
баг-репорт в `test-model/bugs/` (формат: BUG-N: кейс, ожидание, факт, окружение).
