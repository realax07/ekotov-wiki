# ekotov-wiki — конвейер AI Factory

> Пилотный проект конвейера AI Factory. Правила процесса — в репозитории фабрики
> (`~/ai-factory/AGENTS.md`, `docs/process-context.md`, `docs/README-flow-control.md`):
> они наследуются, здесь не дублируются. Отличия и локальные факты — ниже.

## Локальные факты

- Прод: systemd `ekotov-wiki`, uvicorn 127.0.0.1:8377, nginx TLS :10443, БД `/var/lib/ekotov-wiki/wiki.db`.
- Деплой: `deploy/deploy.sh` (EXPECTED_COMMIT), бэкапы `/var/backups/ekotov-wiki/`.
- Стенды: порт 8080, env `EKOTOV_WIKI_DB_PATH` + `EKOTOV_WIKI_AVATARS_DIR`/`AVATARS_DIR` (оба), после seed — `app.migrate_r4`.

## Статус-доклад (правило фабрики, AGENTS.md правило 9)

Доклад о работе в конвейере всегда содержит этапы ворот со статусами:

```
prepare: PASS/DENY/UNKNOWN | reserve: PASS/ZONE_CONFLICT | zone-check+gates: PASS/FAIL/SKIPPED | provenance: OK/DENY/UNKNOWN
```

Со статусами PASS/DENY/UNKNOWN/SKIPPED и кодами причин при отказе. Скрывать или смягчать статусы запрещено — это исполняемое правило (детерминированный Flow Control, enforcing), не договоренность.

## negative probe
