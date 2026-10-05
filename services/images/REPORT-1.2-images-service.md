# REPORT-1.2 — Dev: сервис images (change add-gallery-service)

- Роль: dev (deleg-8f48213c7fe6413b, correlation `7649f32288cc400f9662c1b782e6240f`)
- Дата: 2026-10-05 | Ветка: `add-gallery-service` (worktree
  `/home/openclaw/ekotov-wiki-worktrees/dev-12-gallery`) | Push: НЕТ (по
  правилу конвейера)
- Задача: 1.2 [L] tasks.md — сервис `services/images` (FastAPI по образцу
  `services/search`, порт 8379)
- Зона записи: `services/images/**` — выхода за зону нет

## Статус этапов ворот (обязательный блок, AGENTS.md п.9)

| Ворота | Статус | Примечание |
|---|---|---|
| prepare / flowctl | **UNKNOWN** | сабагенту не передан запуск flowctl (adapter=manual, примечание оркестратора в goal); ворота — зона ПМ |
| reserve (session_check) | **PASS (со слов ТЗ)** | зона делегации — services/**; worktree dev-12-gallery, ветка add-gallery-service сверены (J7-чек: toplevel/branch совпали, SESSION.md подтверждает) |
| zone-check (дифф ⊆ зона) | **PASS** | изменены только `services/images/**` (git status — см. ниже) |
| юнит-тесты images | **PASS** | 26 passed (python 3.14, fastapi 0.141.1, Pillow 12.3.0) |
| юнит-тесты search (регресс эталона) | **PASS** | 12 passed — эталон не задет |
| smoke-запуск uvicorn :8379 | **PASS** | `/api/health` → 200 без сессии; `/api/images` → 401 `{"error":"unauthorized"}` |
| openspec validate --all --strict | **PASS** | 15 passed, 0 failed (прогон в worktree после коммита 55ea2dc; спеки не менялись) |
| push | **SKIPPED (запрещен)** | коммиты локальные, пушит ПМ |

## Что реализовано

Структура `services/images/` (паритет search: `app/` + `tests/` + `README.md`;
Dockerfile и compose — НЕ моя зона, см. «Зависимости/эскалации»):

1. **`app/main.py`** — FastAPI-приложение: роутер изображений, healthcheck
   `/api/health` (без БД-запроса), 422 в форме ядра
   (`{"error":"validation error","details":...}` — exception_handler,
   паритет search), docs/redoc выключены, `/openapi.json` включен, но
   защищен middleware (401 без сессии — design §3).
2. **`app/middleware.py`** — сессионный middleware (копия паттерна
   services/search): exempt — только `GET /api/health` (+ мертвый
   `POST /api/auth/login` для паритета); валидация сессии SELECT-only,
   `request.state.user_id` для эндпоинтов; 401 единым текстом.
3. **`app/db.py`** — RW-профиль БД (design §2): env
   `EKOTOV_WIKI_DB_PATH` (дефолт `/data/wiki.db`), `foreign_keys=ON`,
   `busy_timeout=5000`, короткие транзакции; **journal_mode НЕ
   переключается** (WAL принадлежит ядру-писателю).
4. **`app/images.py`** — валидация/обработка: тип по **magic-байтам**
   (JPEG `\xff\xd8\xff`, PNG, GIF87a/89a, WebP `RIFF…WEBP`), лимит
   **≤10 МБ проверен ДО декодирования и ДО записи** (NFR-21); битый файл
   (сигнатура есть, Pillow не декодирует) → 422; превью Pillow — длинная
   сторона ≤800px, JPEG q85, без апскейла, первый кадр для GIF/WebP.
5. **`app/gallery.py`** — эндпоинты (пути/коды — design §3 дословно):
   - `POST /api/images` (multipart: file, category?, tags?): 422 до записи
     файлов; имя файла генерирует сервер (uuid4hex + расширение по
     фактическому mime — паттерн аватаров); category — существующий id ИЛИ
     новое имя (создается в справочнике галереи); теги — «a,b» /
     переиспользование + создание (`gallery_tags`); оригинал (исходные
     байты, не перекодируются) + превью → том; метаданные + связи — одна
     транзакция; при сбое БД файлы-сироты удаляются; 201.
   - `GET /api/images?category=&tag=` — фильтры комбинируются (AND),
     пустые = все, `created_at DESC`; элемент: метаданные + url/thumb_url +
     likes/dislikes/comments + my_reaction (для бейджа, design §3).
   - `GET /api/images/{id}` — метаданные + реакции + комментарии
     (author = display_name/login, created_at).
   - `PUT /api/images/{id}/like|dislike` — upsert одного голоса
     (PK image_id+user_id): противоположный — перенос, тот же знак —
     снятие (spec FR-81 «повторное действие того же знака снимает»);
     ответ — обновленные счетчики + мой голос.
   - `DELETE /api/images/{id}/like|dislike` — явное снятие (чужой знак не
     трогает).
   - `POST /api/images/{id}/comments` — `{body}`, пустой после trim → 422;
   - `DELETE /api/images/{id}/comments/{cid}` — только автор: чужой → 403,
     нет → 404.
   - `DELETE /api/images/{id}` — **НЕТ** (удаление изображений —
     осознанная не-цель пакета, design §8; расхождение с текстом делегации
     решено по design.md как источнику правды).
6. **`tests/test_images_service.py`** — 26 юнитов на временной БД (схема
   design §2 дословно, env `EKOTOV_WIKI_DB_PATH` в tmp) + временный том
   (env `EKOTOV_WIKI_IMAGES_DIR`): upload happy/4 негатива, типы всех 4
   mime, переиспользование категории/тегов, фильтры (по отдельности,
   комбинация, пустые, несуществующие), сортировка, реакции (полный поток
   FR-81 + 401), комментарии (add/пустой/свой/чужой 403/404), границы
   RW-профиля (users/sessions байт-в-байт не изменены).
7. **`README.md`** — запуск, env, таблица API, границы.

Теги: механизм переиспользован как решили СА — **собственные таблицы
галереи** `gallery_tags`/`image_tags` (design §2, research №3), отдельно от
тегов задач.

## Трассировка проверенных сценариев (включая негативные)

- gallery «Файлы… вне БД»: upload → файлы в tmp-томе, в БД только
  метаданные (test_upload_png_happy_path)
- «Категории и теги»: загрузка с созданием/переиспользованием; без
  категории/тегов (test_upload_reuses…, test_upload_without_category_tags)
- Фильтры: категория, тег, комбинация AND, пустой = все
  (test_list_filters_combine)
- «Лайк/дизлайк — один голос»: постановка, смена (ровно один голос),
  снятие повтором, явное DELETE, PK-инвариант в БД (test_reaction_flow)
- «Комментарии»: add/виден обоим, пустой → 422, удаление своего,
  чужой → 403 и остался (test_comment_*)
- «Лимиты загрузки»: PNG happy; 12 МБ → 422 без файла ни в томе ни в БД;
  PDF→.jpg → 422 по содержимому (test_upload_too_large_422,
  test_upload_bad_type_422, test_upload_corrupted_image_422)
- «Доступ… общий»: 401 без сессии на всех маршрутах + openapi
  (test_endpoints_require_session); паритет owner/PE — оба клиента в
  тестах (Ограничение: полный паритет ОВ-4 — на стенде, задача 2.1)
- services «Границы записи»: users/sessions не изменены
  (test_core_tables_untouched)

## Самопроверка (чеклист dev-промпта)

- [x] Все Scenario задачи, включая негативные, покрыты юнитами (26 passed)
- [x] Нет файлов БД/секретов в репозитории (том и БД — tmp-фикстуры; .gitignore покрывает *.db)
- [x] API-пути и коды ошибок — design §3 дословно (401/404/403/422)
- [x] Файлы НЕ в БД (том images-data; БД — метаданные)
- [x] Миграция таблиц gallery НЕ запускалась и не создавалась (задача 1.3); схема в тестах — копия design §2 для юнитов на временной БД
- [x] Коммит в ветку add-gallery-service локально; push нет

## Зависимости / не моя зона (для ПМ)

- **compose-сервис images, том images-data, mem_limit 128m — задача 1.3**
  (deploy/compose*.yaml не трогал). Юнитам compose НЕ нужен (TestClient
  in-process) — блокировки нет.
- **nginx-локации — задача 1.4** (не трогал).
- **Dockerfile для images** — по аналогии со search потребует
  `Pillow` + `python-multipart` в слое deps (пометка для 1.3; сам не
  создавал — файл образа в зоне задачи 1.3/部署). Если Dockerfile
  относится к 1.2 — нужен явный арбитраж ПМ, сейчас его нет ни у кого.
- Для стенда (2.1): оба env уже поддержаны — `EKOTOV_WIKI_DB_PATH`,
  `EKOTOV_WIKI_IMAGES_DIR` (compose задаст `/data/wiki.db`,
  `/data/images`).

## Эскалации / вопросы

1. **E1 (расхождение делегация vs спека):** текст делегации упоминает
   `POST /api/images/{id}/like` и `DELETE /api/images/{id}` (удаление
   изображения). design.md §3 и дельта спеки определяют
   `PUT/DELETE …/like` + `PUT/DELETE …/dislike` (дизлайк — отдельный
   маршрут), а удаление изображения — **осознанная не-цель** (design §8,
   предложение Заказчику). Исполнено по design.md (источник правды по ТЗ).
   Если Заказчик утвердит удаление — отдельная дельта.
2. **E2 (интерпретация):** поведение «повторный клик снимает, переносит»
   реализовано так: повтор того же знака — снятие; противоположный —
   перенос (spec FR-81: «голос MUST сниматься повторным действием того же
   знака либо явным снятием»). Делегатская формула «повторный клик
   снимает, противоположный переносит» — та же семантика.
3. **E3 (заметка):** в тестовой среде нет compose/uvicorn-стенда —
   интеграционные проверки (маунт тома, healthcheck-контейнера, RAM ≤128m)
   переходят к 1.3/2.1 по плану.

## Проблема → решение (E16-политика, повторов не было)

- `PermissionError: /data` в тестах: IMAGES_DIR читался env на импорт
  модуля (до monkeypatch фикстуры) → перенес чтение env в
  `get_images_dir()` на каждый запрос (заодно соответствует правилу
  «конфигурация через окружение»). Повторов не было.
- Два красных юнита на первом прогоне — ошибки ожиданий в самих тестах
  (множество mime; состояние счетчиков в шаге 4 потока реакций) — правлены
  тесты, не код.

## Коммиты

- **55ea2dc** — [1.2] dev: сервис images (10 файлов, +1610; push НЕТ).
- Правка отчета (статус ворот openspec) — следующим коммитом.
