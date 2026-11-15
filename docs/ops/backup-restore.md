# RUNBOOK «Бэкап/Restore» — ekotov-wiki (TD-A, PLAN-TD-CLOSEOUT)

> Дополнение к `deploy/RUNBOOK.md` (прод-факты, сервисы, деплой). Этот раздел —
> что лежит в бэкапах, как проверить целостность и как восстановиться на чистом
> volume. Код: `services/backup/backup.py` (цикл), `services/backup/restore.py`
> (восстановление). Тест: `tests/test_backup_restore.py`.

## 1. Что в бэкапе

Каталог `/var/backups/ekotov-wiki` (bind в backup-контейнер, `/backups`):

| Файл | Что это | Откуда |
|---|---|---|
| `wiki-daily-<UTC>.db` | консистентная копия SQLite (`sqlite3.Connection.backup` — WAL-safe, НЕ файл-копия живой БД) | volume `wiki-data` (ro) |
| `avatars-daily-<UTC>.tar` | аватары + hash-манифест `_manifest.json` | volume `wiki-data` → `/data/avatars` |
| `images-daily-<UTC>.tar` | файлы галереи (оригинал+превью) + манифест | volume `images-data` → `/data/images` |
| `videos-daily-<UTC>.tar` | файлы видео (оригинал+mp4+превью) + манифест | volume `videos-data` → `/data/videos` |

- **Retention 14 дней** — на файлы `*-daily-*` (mtime). Релизные копии
  деплоя (`wiki-pre-*`, `avatars-pre-*`) sidecar НЕ трогает (их жизненный
  цикл — `deploy/deploy.sh`).
- **Манифест** (`ekotov-wiki-media-manifest/1`): JSON внутри tar — путь,
  размер, sha256 каждого файла + суммарные счетчики. По нему restore
  сверяет восстановленное байт-в-байт.
- **Пропуск отсутствующего каталога**: если том не смонтирован в
  backup-контейнер (см. §4), цикл пишет «пропущено» и НЕ падает — запуск
  бэкапа не блокирует работу сервисов. avatars при этом всегда дают tar
  (пустой при отсутствии каталога) — паритет ожиданий `deploy.sh` (шаг 2/8).

## 2. Гарантии и известные ограничения

- **WAL-safe**: копия снимается через `sqlite3.Connection.backup` (sqlite
  backup API), не копированием файла живой БД — коммиты, живущие в
  `-wal` на момент бэкапа, в копию входят (проверено
  `tests/test_backup_restore.py::test_backup_db_includes_wal_tail`).
- **immutable-fallback** (ro-том без создания `-wal`/`-shm`, прод p15):
  бэкап читает ТОЛЬКО main-файл БД; незалитетый WAL-хвост в копию НЕ
  входит. Модуль печатает WARNING с размером `-wal` — по нему видно масштаб.
  Фундаментальное решение (rw-маунт `/data` для backup) — за Заказчиком,
  см. комментарий в `backup.py::backup_database`.
- **Целостность копий**: `wiki-daily-*.db` — `PRAGMA integrity_check` на
  restore; медиа-tar — sha256 по манифесту. Битый tar/файл restore не
  пропускает (тест `test_restore_detects_corrupted_media`).
- Тары до TD-A (аватары без манифеста, абсолютные пути в членах) restore.py
  по манифесту не восстанавливает — честно падает с «tar без манифеста».

## 3. Restore-процедура (чистый volume)

Restore выполняется при ОСТАНОВЛЕННЫХ писателях (app/images/video) —
скрипт отказывается писать в существующий файл/каталог (защита от затирания
живых данных по опечатке). restore.py — stdlib-only, можно запустить в
контейнере backup (в образе, `/srv`) или любым python 3.11+.

```bash
# 1. Остановить писателей (ПМ/админ прод-хоста):
docker compose -p ekotov-wiki-par stop app images video search

# 2. Проверить бэкапы БЕЗ записи (--verify-only; код 0 = OK):
python restore.py --verify-only \
  --db-backup /var/backups/ekotov-wiki/wiki-daily-<UTC>.db \
  --media-backup /var/backups/ekotov-wiki/avatars-daily-<UTC>.tar \
  --media-backup /var/backups/ekotov-wiki/images-daily-<UTC>.tar \
  --media-backup /var/backups/ekotov-wiki/videos-daily-<UTC>.tar

# 3. Restore на ЧИСТЫЙ volume (каталоги назначения не должны существовать).
#    Точки монтирования чистого volume — см. §4; пример на хосте:
python restore.py \
  --db-backup  /var/backups/ekotov-wiki/wiki-daily-<UTC>.db   --db-dest  /restore/wiki-data/wiki.db \
  --media-backup /var/backups/ekotov-wiki/avatars-daily-<UTC>.tar --media-dest /restore/wiki-data/avatars \
  --media-backup /var/backups/ekotov-wiki/images-daily-<UTC>.tar  --media-dest /restore/images-data \
  --media-backup /var/backups/ekotov-wiki/videos-daily-<UTC>.tar  --media-dest /restore/videos-data

# 4. Права: сервисы работают под uid 10001 (deploy/RUNBOOK §2.1)
chown -R 10001:10001 /restore/wiki-data /restore/images-data /restore/videos-data

# 5. Подмена томов / старт (compose-проект, ПМ по deploy/RUNBOOK):
#    остановленный стек → восстановленные тома (docker volume / bind) → up → healthy.

# 6. Smoke (прод-порт):
curl -sk https://127.0.0.1:10443/api/health   # {"status":"ok"}
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:10443/login  # 200
```

restore.py сам делает `PRAGMA integrity_check` + smoke-запрос к
восстановленной БД (`--smoke`, дефолт `SELECT count(*) FROM sqlite_master`)
и печатает сводку sha256-сверки по каждому медиа-tar. Код возврата: 0 OK,
1 ошибка проверки, 2 usage.

## 4. Медиа-тома в backup-контейнере (deploy-хвост — ЗАКРЫТ TD-D, 2026-11-15)

Код backup.py читает каталоги из env `EKOTOV_WIKI_IMAGES_DIR` /
`EKOTOV_WIKI_VIDEOS_DIR` (дефолты кода — `/data/images`, `/data/videos` —
те же имена, что у сервисов images/video). В backup-контейнере пути
ДРУГИЕ — `/media/images`, `/media/videos`: `/data` у sidecar занят
ro-маунтом БД (`wiki-data:/data:ro`), а вложенный маунтпойнт внутрь
ro-маунта docker создать не может («read-only file system», класс
weather PR #207 — поймано CI e2e TD-D). У владельцев томов (images/video)
`/data` rw — там вложение легально. `deploy/compose.yaml` (сервис backup)
с TD-D маунтит медиа так:

```yaml
# сервис backup, volumes (ПРИМЕНЕНО, PR pipeline/td-d-deploy):
      - images-data:/media/images:ro
      - videos-data:/media/videos:ro
# environment:
      EKOTOV_WIKI_IMAGES_DIR: /media/images
      EKOTOV_WIKI_VIDEOS_DIR: /media/videos
```

Паритет в `deploy/compose.test.yaml` (тома стенда `images-test-data`/
`videos-test-data`). До TD-D ежедневный контур покрывал только БД+аватаров
(цикл писал «пропущено» для галереи/видео) — хвост закрыт; поведение
«пропуск отсутствующего каталога» сохранено в коде как защита (первый
прогон до создания томов не падает).

## 5. Проверка контура (тест)

```bash
/home/openclaw/venvs/wiki/bin/python -m pytest tests/test_backup_restore.py -v
```

13 кейсов: WAL-хвост в копии БД, манифесты (инвентарь+sha256, вложенность),
пропуск отсутствующего тома, полный цикл run_backup, restore-раундтрип на
чистый volume (integrity + smoke + sha256), отказ писать в существующий
каталог, детект битого tar, retention по всем daily-префиксам (релизные не
трогаются), CLI restore.py (раундтрип + verify-only + коды ошибок).
