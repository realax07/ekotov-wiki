# REPORT-1.3: миграция ядра + compose (add-gallery-service, Флоу 1)

Делегация: de136393f6134edea37ef7168ff2ec1a, роль dev, worktree
`/home/openclaw/ekotov-wiki-worktrees/dev-12-gallery`, ветка `add-gallery-service`.
Задача: tasks.md 1.3 [M] (design §2, §4, §5, §7). Границы соблюдены: изменения
только `backend/app/migrate_gallery.py`, `deploy/compose*.yaml`,
`services/images/Dockerfile` + этот отчет. Push не выполнялся.

## Что сделано

| Артефакт | Что |
|---|---|
| `backend/app/migrate_gallery.py` | One-shot миграция: 6 таблиц gallery (image_categories, images, gallery_tags, image_tags, image_reactions, image_comments) + 4 индекса — DDL дословно design §2; идемпотентно (IF NOT EXISTS); все DDL в одной транзакции BEGIN IMMEDIATE (паттерн migrate_categories, ревью 001 з.3); автосверка: 6 таблиц / наборы колонок / составные PK (FR-79/FR-81) / FK-цели + ON DELETE CASCADE / CHECK value IN (1,-1) / UNIQUE name справочников / 4 индекса (таблица+колонки); расхождение → stdout + exit 1; guard: без users — exit 1 (FK images.uploaded_by) |
| `services/images/Dockerfile` | Паритет services/search/Dockerfile: python:3.12-slim, USER 10001, WORKDIR /srv, EXPOSE 8379, HEALTHCHECK urllib на :8379/api/health (числа = compose), CMD uvicorn 1 воркер. Deps слоя: fastapi==0.141.1, uvicorn[standard]==0.53.0, **Pillow==12.3.0, python-multipart==0.0.32** (эскалация E1 из REPORT-1.2 закрыта — пины синхронны backend/requirements.txt; jinja2/bcrypt/pytest-набор НЕ ставятся) |
| `deploy/compose.yaml` | Сервис `images` (после search): image `ekotov-wiki/images:local` (env IMAGES_IMAGE), build из корня, restart unless-stopped, **mem_limit 128m** (design §5), env EKOTOV_WIKI_DB_PATH=/data/wiki.db + EKOTOV_WIKI_IMAGES_DIR=/data/images, тома `wiki-data:/data:rw` + `images-data:/data/images`, depends_on app (без condition — паритет search), healthcheck urllib :8379 (30s/10s/3/15s), logging json-file 10m×3, **порты НЕ публикуются** (nginx — 1.4). Новый том `images-data` |
| `deploy/compose.test.yaml` | Паритет NFR-10: сервис `images` идентичен продовскому, тома проекта стенда `wiki-test-data:/data:rw` + `images-test-data:/data/images`, image `:test` (env IMAGES_IMAGE). Новый том `images-test-data` |

## Проверки (все локально, tmp-БД `/tmp/gallery-mig/`)

1. **Прогон 1 (свежая БД после `python -m app.db`)**: created 6 таблиц, сверка
   ОК, **exit 0**.
2. **Прогон 2 (повтор — идемпотентность)**: `Создано таблиц: 0 (no-op — все
   существовали)`, сверка ОК, **exit 0**.
3. **Негативная матрица (6 сценариев, все → exit 1)**: лишняя колонка images;
   убран CHECK value; убран UNIQUE gallery_tags.name; сломан составной PK
   image_tags (PK только image_id); FK image_comments.image_id без CASCADE;
   индекс idx_images_created_at на другой колонке. Скрипт
   `~/.hermes/cache/scratch/neg_migrate_1_3.py`.
4. **Поведение схемы (позитив данных)**: двойной голос → IntegrityError
   (UNIQUE image_id,user_id); value=0 → CHECK failed; DELETE images →
   CASCADE очистил image_tags/image_comments/image_reactions (0/0/0).
5. **Паритет схемы с фикстурой тестов 1.2** (services/images/tests):
   колонки + PK + 4 индекса всех 6 таблиц — **PASS** (скрипт
   `check_schema_parity.py`).
6. **Compose-валидация**: `docker compose config` успешен на обоих файлах
   (5 сервисов, включая images; прод + стенд); структурная матрица
   14 инвариантов × 2 файла (mem_limit, restart, no ports, logging 10m×3,
   healthcheck :8379, depends_on app, тома, build, env) — **PASS** (скрипт
   `check_compose_1_3.py`).

## Не проверено / эскалации

- **E1 (закрыта)**: Pillow + python-multipart в deps образа — внесены в
  Dockerfile (REPORT-1.2, эскалация E1).
- **E2: docker build образа images не выполнен** — у сабагента нет доступа к
  docker API (permission denied на /var/run/docker.sock; sudo требует пароль,
  недоступен сабагенту). Нужен build+up стенда силами оркестратора/хоста:
  `docker build -f services/images/Dockerfile -t ekotov-wiki/images:local .`
  или `docker compose -f deploy/compose.test.yaml -p wiki-test up -d --build`.
  До замера RAM (пункт (в) задачи 1.3) поднять стенд нечем.
- **E3: замер фактического RAM images не выполнен** — прямой сигнал E2:
  замер требует поднятого контейнера. Перенести замер на этап подъема стенда
  (смыкается с 2.1 «docker stats») или выполнить оркестратору после build.
  Стабильное превышение 128m — эскалация до прод (design §5).
- nginx-маунт `images-data` (ro) в frontend — задача 1.4, не моя зона; в
  compose для nginx ничего не менял (осознанно: «Одно инфраизменение» — 1.3
  добавляет только сервис images).

## Статус ворот

- openspec validate / flow_check — зона ПМ (запуск оркестратором при приемке);
  спеки не трогал.
- Чекбокс 1.3 в tasks.md НЕ отмечаю: пункт (в) замер RAM не выполнен (E3) —
  решение об отметке за ревьюером/ПМ. Код (а) и (б) готовы и проверены.
