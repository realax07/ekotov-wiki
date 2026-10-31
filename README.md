# ekotov-wiki — конвейер AI Factory

> Пилотный проект конвейера AI Factory. Правила процесса — в репозитории фабрики
> (`~/ai-factory/AGENTS.md`, `docs/process-context.md`, `docs/README-flow-control.md`):
> они наследуются, здесь не дублируются. Отличия и локальные факты — ниже.

## Что это

Личная wiki (задачи, заметки, аватары, полнотекстовый поиск, wiki-раздел с деревом
страниц и историей версий) + полигон конвейера разработки из агентов-сабагентов.
Монорепо микросервисов (P11): `services/{app,frontend,search,backup,images,auth}`
в docker compose, прод — проект `ekotov-wiki-par`.

## Локальные факты

- Скиллы: зеркало фабрики в `skills/` (9 групп: pm-factory/flow/roles/roles-tools/runtimes/engineering/creative/research/office), проектные — `skills/project/`, не трогаются фабричным синком. Агенты `agents/` — проектные копии роль-файлов фабрики. Активных change-пакетов нет: все релизы архивированы (2026-10-31), планы — `archive/plans/`, код-ревью — `archive/code-reviews/`.

- Прод: docker compose проект `ekotov-wiki-par` (7 контейнеров: app :8377 внутри сети,
  frontend nginx TLS :10443, search :8378, images :8379, backup, netdata);
  systemd-юнит `ekotov-wiki` эпохи монолита выведен из боевого пути.
- БД: sqlite в томе `ekotov-wiki-par_wiki-data` (`/data/wiki.db` внутри контейнеров);
  прод-данные НЕ править с хоста напрямую — только через `docker compose ... exec app`.
- Деплой: `deploy/deploy.sh` (`RELEASE_TAG=<метка> MIGRATE_MODULE=app.migrate_wiki
  PROJECT=ekotov-wiki-par SRC_DIR=<репо> bash deploy/deploy.sh`); теги релизные,
  `latest` запрещен (FR-72); pre-deploy бэкапы `/var/backups/ekotov-wiki/`
  (wiki-pre-<tag>-*.db + avatars-pre-<tag>-*.tar); статическая версия —
  `static_v` в `backend/app/pages.py`, бампится на каждый деплой с изменениями
  статики (сейчас `redesign-1a`).
- Стенды (тесты): порт 8080, env `EKOTOV_WIKI_DB_PATH` +
  `EKOTOV_WIKI_AVATARS_DIR`/`AVATARS_DIR` (оба), venv `~/venvs/wiki`, playwright 1.63.
  После seed — миграции `app.migrate_r4` (нужен SECRET_KEY) и `app.migrate_wiki`.
- RUNBOOK: `deploy/RUNBOOK.md` (деплой, откат, диагностика — источник правды по экспл.).

## Статус пакета add-wiki (P15)

Wiki-раздел в проде: дерево страниц слева 280px + контент до 1200px (десктоп),
мобила ≤480px — дерево в потоке сверху; WYSIWYG-редактор, история версий,
полнотекстовый поиск (X-Search-Service, сервис search). Приемочные прогонки:
`test-model/reports/add-wiki/REPORT-4.{1,2,3,4}*.md`; решение по раскладке —
`decisions/2026-10-11-wiki-layout-tree-left.md`. Открытые хвосты: протокол 4.5,
эскалация backup `:ro`-маунта (решение Заказчика), чистка 6.1.

## Статус-доклад (правило фабрики, AGENTS.md правило 9)

Доклад о работе в конвейере всегда содержит этапы ворот со статусами:

```
prepare: PASS/DENY/UNKNOWN | reserve: PASS/ZONE_CONFLICT | zone-check+gates: PASS/FAIL/SKIPPED | provenance: OK/DENY/UNKNOWN
```

Со статусами PASS/DENY/UNKNOWN/SKIPPED и кодами причин при отказе. Скрывать или смягчать статусы запрещено — это исполняемое правило (детерминированный Flow Control, enforcing), не договоренность.
