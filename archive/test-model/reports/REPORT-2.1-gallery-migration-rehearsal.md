# QA 2.1 add-gallery-service — протокол репетиции TC-GAL-123 (миграция migrate_gallery)

Дата: 2026-10-06 | Ветка: add-gallery-service, HEAD db592a9
correlation_id: c49f8f1b7c5e4380b431136f95c375f9

Среда: копия БД стенда 2.1 (`/tmp/qa21-gallery/migration/app-copy.db`, схема ядра +
seed owner/wife + migrate_r4 + данные стенда), python 3.14, `backend/` worktree.
Прод-копия — план 2.2 ([ops], с Заказчиком) — вне стенда 2.1 по кейсу.

## Шаг 1 — прогон 1 (создание, свежая копия БД ядра БЕЗ gallery-объектов)

База репетиции: копия БД стенда с удаленными gallery-таблицами/индексами
(имитация «до внедрения»; осталось: users, sessions, tasks, categories, tags,
task_tags, comments).

```
DB_PATH=/tmp/qa21-gallery/migration/app-copy.db SECRET_KEY=… python3 -m app.migrate_gallery
```

- exit-код: **0**
- создано: 6 таблиц gallery (image_categories, images, gallery_tags, image_tags,
  image_reactions, image_comments) + 4 индекса (idx_images_category,
  idx_images_created_at, idx_image_tags_tag, idx_image_comments)
- stdout: `Создано таблиц: 6: [...]`, `=== Сверка: ОК ===` + «Проверено: 6 таблиц;
  колонки = design §2; PK image_tags(image_id, tag_id) и
  image_reactions(image_id, user_id); FK-цели + ON DELETE CASCADE;
  CHECK value IN (1, -1); UNIQUE name справочников; 4 индекса…»

## Шаг 2 — прогон 2 (идемпотентность)

- Повторный запуск на той же БД: exit **0**, no-op — «Создано таблиц: 0 (no-op —
  все существовали)», сверка снова ОК.

## Шаг 3 — мутанты автосверки (_verify)

| Мутант | Ожидание | Факт |
|---|---|---|
| (а) `ALTER TABLE images ADD COLUMN junk TEXT` (лишняя колонка, проверка «б») | exit 1 + FAIL-строка | **exit 1**, stdout: `FAIL: images: лишние колонки ['junk']` |
| (б) image_tags с чужим PK `(tag_id, image_id)` (порядок PK нарушен, проверка «в») | exit 1 + FAIL-строка | **exit 1**, stdout: `FAIL: image_tags: PK=('tag_id', 'image_id'), ожидается ('image_id', 'tag_id')` |

Оба мутанта воспроизведены на свежих копиях (каждый — отдельная копия БД после
шага 2): DDL молча пропускается (IF NOT EXISTS), `_verify` детектирует → exit 1.
«nginx -t-аналог для БД» подтвержден. Мутант «удалить индекс/таблицу» не
использовался (ложный exit 0 по кейсу — молча воссоздается до сверки).

## Шаги 4–5 — подъем app/images на мигрированной БД + смоук

- Выполнено на основном стенде 2.1 (та же БД мигрирована до подъема): app
  стартует и healthy (`:8080/api/health` = `{"status":"ok"}`); images стартует
  БЕЗ миграционных шагов (в `services/images/` нет миграционного кода —
  grep по каталогу: только db.py/gallery.py/images.py/middleware.py; схему
  создает ядро).
- Смоук после миграции: `GET /api/images` → 200 (стартовал с пустым списком),
  домены ядра (auth/me, tasks, search) работают — данные ядра не изменены
  (регресс /me-домена 20 passed, TC-GAL-114 смоук-матрица green).

## Шаг 6 — прод-копия

План 2.2 ([ops], только с Заказчиком) — вне стенда 2.1.
