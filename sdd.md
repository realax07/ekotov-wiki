# sdd.md — Системный дизайн: ekotov-wiki, релиз 1 (change add-kanban-core)

Источник требований: `requirements.md` (r3, утвержден). Пакет: `openspec/changes/add-kanban-core/`.

## 1. Стек и обоснование

Ограничение ОГР-1: легковесность («веб движок (можно nginx)», «lite DB» — SQLite по слову Заказчика, вне репозитория). ОГР-4: ограничений по ресурсам VPS нет. Масштаб: 2 пользователя, до 1 000+ задач (NFR-2).

| Слой | Выбор | Обоснование в рамках легковесности |
|---|---|---|
| Front-proxy | **nginx** (reverse-proxy, TLS/Let's Encrypt, раздача статики) | Прямое пожелание Заказчика (п. В-1). Проверенное решение, нулевая стоимость лицензии, конфиг ~десяток строк |
| Backend-фреймворк | **Python + FastAPI** (ASGI, uvicorn) | Микрофреймворк: маршруты + валидация схем (pydantic) + middleware сессий из коробки; нет «энтерпрайз»-обвязки. REST API (ОГР-2) выражается напрямую. Альтернатива Flask — равно легковесна, FastAPI предпочтительнее готовыми контрактами OpenAPI |
| БД | **SQLite** (WAL-режим), файл вне репозитория | Прямое пожелание Заказчика (ОГР-1, NFR-5). Для 2 пользователей и 1 000 задач серверная БД (PostgreSQL) — лишняя эксплуатационная сущность; SQLite WAL покрывает конкурентность двух пользователей с запасом. Ноль демонов, бэкап = копия файла |
| Пароли | bcrypt (passlib) или argon2 | NFR-7: не хранить в открытом виде; оба алгоритма — стандарт, доступны pip-пакетом |
| Веб-морда | Серверные шаблоны (Jinja2) + минимальный ванильный JS (fetch к API) | Без SPA-фреймворков (React и т.п.) — несоразмерно личному проекту на 2 пользователей; ОГР-2 соблюдается: UI — клиент REST API, не лезет в БД |
| Развертывание | systemd-юнит, VPS, HTTPS | NFR-6 |

Отклонение от пожеланий: нет. nginx и SQLite приняты; фреймворк — решение СА в рамках «легковесности» (ОГР-1 делегирует выбор системному анализу).

## 2. Компоненты

```
Браузер ──HTTPS──> nginx ──> FastAPI (uvicorn, systemd)
                              ├── auth middleware (сессии/куки)
                              ├── REST API (/api/*)
                              │     ├── auth (login/logout)
                              │     ├── tasks CRUD + move + comments
                              │     ├── board
                              │     └── search (builder + advanced)
                              ├── Jinja2 шаблоны (страницы: login, доска, поиск)
                              └── SQLite (WAL) ── файл вне репозитория (NFR-5)
```

- **Auth middleware** — единая точка проверки сессии для страниц и API.
- **API-слой** — вся бизнес-логика, включая инвариант fast line (серверная проверка, не UI).
- **Фильтр-конвейер поиска** — builder→text→parse→параметризованный SQL (см. design.md §6).

## 3. API-контракты (REST, JSON)

Общее: префикс `/api`; все запросы, кроме `POST /api/auth/login`, требуют валидную сессионную куку, иначе **401** `{"error": "unauthorized"}`. Ошибки валидации — **422** `{"error": "<сообщение>", "details": {...}}`. Конфликт — **409**. Не найдено — **404**.

### 3.1 Auth

| Метод/путь | Описание |
|---|---|
| `POST /api/auth/login` | Вход |
| `POST /api/auth/logout` | Выход (удаляет сессию и куку) |

**POST /api/auth/login**
- Запрос: `{"login": "string", "password": "string"}`
- Ответ 200: `{"ok": true, "user": "string"}` + `Set-Cookie: session=<token>; HttpOnly; SameSite=Lax; Secure`
- Ошибки: `401 {"error": "invalid credentials"}` — единый текст и для неверного логина, и для неверного пароля (не раскрывать существование логина, NFR-7).

### 3.2 Задачи (CRUD)

| Метод/путь | Описание |
|---|---|
| `POST /api/tasks` | Создать задачу |
| `GET /api/tasks/{id}` | Карточка задачи со всеми признаками и комментариями |
| `PATCH /api/tasks/{id}` | Редактировать признаки |
| `DELETE /api/tasks/{id}` | Удалить задачу |
| `POST /api/tasks/{id}/move` | Перевести в другой столбец (в т.ч. в «Выполнено» = архив) |
| `POST /api/tasks/{id}/comments` | Добавить комментарий |

Объект Task:
```json
{
  "id": 1,
  "title": "string (обязательно)",
  "description": "string|null",
  "priority": "low|medium|high|null",
  "category": "string|null",
  "due_date": "YYYY-MM-DD|null",
  "tags": ["string"],
  "is_fast": false,
  "status": "todo|in_progress|done",
  "archived_at": "ISO-datetime|null"
}
```

**POST /api/tasks**
- Запрос: поля Task; обязателен `title`; `is_fast` — опциональный флаг fast line (только при создании — ручное назначение, ОГР-5).
- Ответ 201: Task.
- Ошибки: `422` — нет названия; `409 {"error": "fast line occupied"}` — is_fast=true при наличии активной (todo/in_progress) fast-задачи.

**PATCH /api/tasks/{id}** — Ответ 200: Task. Ошибки: `404`, `422`.

**POST /api/tasks/{id}/move**
- Запрос: `{"status": "todo|in_progress|done"}`
- Ответ 200: Task (при `done` — `archived_at` проставлен, с доски исчезает).
- Ошибки: `404`, `422` (недопустимый статус).

### 3.3 Доска

| Метод/путь | Описание |
|---|---|
| `GET /api/board` | Задачи, сгруппированные по столбцам |

- Ответ 200: `{"columns": {"todo": [Task], "in_progress": [Task], "done_note": "…"}}` — только активные (не архивные) задачи; внутри столбцов: fast-задача выделена и отсортирована по приоритету.
- Ошибки: только 401.

### 3.4 Fast line

Отдельного endpoint нет: fast line — проекция `is_fast` + активные статусы в `GET /api/board` и ограничение при `POST /api/tasks` (409). См. design.md §4.

### 3.5 Поиск

| Метод/путь | Описание |
|---|---|
| `GET /api/search` | Поиск по признакам |
| `POST /api/search/advanced` | Поиск по SQL-подобному тексту фильтра |

**GET /api/search**
- Query-параметры (все опциональны; пустой набор = все задачи): `priority`, `category`, `tag` (повторяемый), `due_before`, `due_after`, `archived=true|false|all` (по умолчанию `all`).
- Ответ 200: `{"results": [Task]}` — каждый Task содержит признак архивности.
- Ошибки: `422` (невозможное значение параметра).

**POST /api/search/advanced**
- Запрос: `{"query": "priority = \"high\" AND tag IN (\"home\")"}`
- Ответ 200: `{"results": [Task], "normalized_query": "…"}` (normalized — сериализация распарсенного фильтра обратно, для UI).
- Ошибки: `400 {"error": "filter syntax: <позиция/причина>"}` — синтаксическая ошибка; запрос не выполняется.

### 3.6 Страницы (не API)

`GET /login`, `GET /board`, `GET /search`, `GET /wiki` (заглушка с todo). Все, кроме `/login`, — редирект на `/login` без сессии.

## 4. Модель данных (SQLite)

Файл БД — вне репозитория (NFR-5: `*.db`, `*.sqlite*` в `.gitignore`; путь — конфиг развертывания).

```sql
users (
  id            INTEGER PK,
  login         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL            -- bcrypt/argon2, не открытый пароль (NFR-7)
)

sessions (
  token       TEXT PK,                   -- криптостойкий случайный
  user_id     INTEGER NOT NULL FK -> users.id,
  created_at  TEXT NOT NULL,
  expires_at  TEXT NOT NULL              -- скользящий TTL
)

tasks (
  id          INTEGER PK,
  title       TEXT NOT NULL,             -- обязательно (FR-5)
  description TEXT,
  priority    TEXT CHECK(priority IN ('low','medium','high') OR priority IS NULL),
  category    TEXT,
  due_date    TEXT,                      -- YYYY-MM-DD
  is_fast     INTEGER NOT NULL DEFAULT 0,-- fast line (FR-3)
  status      TEXT NOT NULL DEFAULT 'todo'
              CHECK(status IN ('todo','in_progress','done')),  -- Ожидает/В работе/Выполнено (ОГР-3)
  archived_at TEXT,                      -- NOT NULL <=> в архиве (FR-4)
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
)

tags (
  id    INTEGER PK,
  name  TEXT UNIQUE NOT NULL
)

task_tags (
  task_id INTEGER NOT NULL FK -> tasks.id ON DELETE CASCADE,
  tag_id  INTEGER NOT NULL FK -> tags.id,
  PRIMARY KEY (task_id, tag_id)
)

comments (
  id         INTEGER PK,
  task_id    INTEGER NOT NULL FK -> tasks.id ON DELETE CASCADE,
  author_id  INTEGER NOT NULL FK -> users.id,
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL
)
```

Индексы: `tasks(status, is_fast)`, `tasks(archived_at)`, `tasks(priority)`, `task_tags(tag_id)`, `comments(task_id)`.

Проверка NFR-5: `git check-ignore data/app.db` — проигнорирован.

## 5. Решения по НФТ

| НФТ | Решение |
|---|---|
| NFR-1 (≤2 с) | Легковесный стек; замер на 1 000 задач (tasks 8.2); индексы выше |
| NFR-2 (1 000 задач) | SQLite с индексами; пагинация не требуется на этом объеме |
| NFR-3 (данные при рестарте) | Все данные в SQLite (WAL, fsync); единственное in-memory — кеш сессий; инвалидация сессий при рестарте допустима (зафиксировано в спеке) |
| NFR-4 (2 пользователя) | Seed двух учеток; регистрации нет |
| NFR-5 (БД вне репо) | `.gitignore`, путь в конфиге развертывания |
| NFR-6 (VPS, интернет) | nginx + TLS Let's Encrypt, systemd; см. tasks 1.4 |
| NFR-7 (базовая безопасность) | Обязательная авторизация всех страниц и API (middleware); куки HttpOnly/SameSite/Secure; хеши паролей; параметризованный SQL (фильтры — через парсер, не конкатенацию); единый текст ошибки логина; CSRF-минимум через SameSite=Lax |

## 6. Матрица трассировки: FR/NFR → Requirement (домен.спеки)

Требования спек change-пакета (все ADDED):

| Требование ТЗ | Приоритет | Requirement спеки |
|---|---|---|
| FR-1 | Must | board: «Отображение канбан-доски» |
| FR-2 | Must | board: «Три фиксированных столбца» |
| FR-3 | Must | fastline: «Выделенная линия fast line»; «Назначение… вручную при создании»; «Не более одной fast-задачи в активных статусах»; «Освобождение fast line…»; «Приоритетный порядок…»; board: «Перемещение задач…» (частично) |
| FR-4 | Must | archive: «Задача уходит в архив после "Выполнено"»; «Доступ к архивным задачам через поиск»; board: «Перемещение задач…», «Быстрый доступ к действию "Выполнено"» |
| FR-5 | Must | tasks: «Создание задачи» |
| FR-6 | Must | board: «Перемещение задач между столбцами» |
| FR-7 | Must | tasks: «Редактирование задачи»; «Удаление задачи» |
| FR-8 | Should | tasks: «Перемещение задачи через API»; search: «Поиск через API» (+ auth: «Авторизация обязательна для API») |
| FR-9 | Must | tasks: «Признаки задачи» |
| FR-10 | Must | search: «Вкладка поиска старых задач»; archive: «Доступ к архивным задачам через поиск» |
| FR-11 | Must | search: «Фильтр-конструктор по признакам задачи» |
| FR-12 | Must | search: «Режим advanced с SQL-подобным синтаксисом» |
| FR-13 | Must | navigation: «Навигация через сайдбар»; «Пустой раздел Wiki с пометкой todo» |
| FR-14 | Must | auth: «Вход по логину и паролю»; «Сохранение входа через сессии и куки» |
| NFR-3 | Must | tasks: «Данные не теряются при перезапуске сервера» |
| NFR-4 | Must | auth: «Доступ только для своих пользователей»; «Вход по логину и паролю» |
| NFR-6 | Must | — (развертывание; покрывается tasks 1.4 и design/sdd §1, наблюдаемого поведения приложения не добавляет; фраза об этом в proposal, In scope) |
| NFR-7 | Must | auth: «Авторизация обязательна для всех страниц»; «Авторизация обязательна для API»; «Пароли не хранятся в открытом виде» |
| NFR-1, NFR-2, NFR-5 | Should | — (НФТ-пороги; решения §5, проверка tasks 8.1/8.2/1.1; отдельные Requirement не заводились, т.к. это метрики развертывания, а не наблюдаемое поведение доменов) |

Покрытие Must: **все 13 Must-FR (FR-1…FR-7, FR-9…FR-14) и Must-NFR (NFR-3, NFR-4, NFR-7) имеют Requirements; NFR-6 (Must) — развертывание, покрыто задачей tasks 1.4** (дальнейшая детализация — не поведение системы; отмечено намеренно, не пропущено).

## 7. Допущения (зафиксированы в proposal.md)

- Общая доска: оба пользователя видят все задачи; разделение по владельцу не вводится (ОГР-6, «сильно не заморачиваемся»).
- Сессии при рестарте могут инвалилироваться (NFR-3 — про данные).
- Регистрации нет: 2 учетки заводятся seed'ом.
