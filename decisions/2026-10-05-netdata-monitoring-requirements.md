# Решение Заказчика: утверждение requirements add-netdata-monitoring + расширение zone-политики sa

## Контекст

SA-фаза пакета `add-netdata-monitoring` (R7, пакет 1) завершена
(da6e645 + c059c5d): requirements.md r1 (FR-75…FR-78, NFR-19) в статусе
«ГОТОВ К УТВЕРЖДЕНИЮ»; эскалация E1 из REPORT-0.1.md — role_zone_policy
роли `sa` не покрывает выходы роли `requirements.md` и `research.md`
((sa_agent.md — выходы роли), zone-check дал честный OUT_OF_ZONE.

## Что решено

1. **requirements.md пакета add-netdata-monitoring УТВЕРЖДЕН** Заказчиком
   (r1, FR-75…FR-78, NFR-19). Статус файла → «УТВЕРЖДЕН». Действие
   `dev_task`/`design`-фаза пакета разрешены; approval_ref для задач пакета —
   `2026-10-05-netdata-monitoring-requirements` (покрывает: ui_designer-
   мокап 1.1, devops 1.2/1.3, dev 1.4, QA 2.1, code_review; [ops] 2.2 —
   протокол приемки Заказчика).
2. **Zone-политика sa расширена** на `requirements.md` и `research.md`
   (пакета) — в ОБОИХ репозиториях: эталон фабрики `~/ai-factory`
   (scripts/role_zone_policy.py) и проект `~/ekotov-wiki` — `[pipeline]`-
   коммит синхронно с таблицей agents/README.md. Изменение аддитивное
   (новый допустимый источник артефактов SA), переносится в эталон фабрики.

## Последствия

- СА-фазы будущих пакетов перестают давать известный OUT_OF_ZONE по
  requirements/research.
- Перенос урока в ai-factory BACKLOG: закрыть после синхронизации.

```decision-record
{
  "schema_version": "decision-record/1",
  "decision_id": "2026-10-05-netdata-monitoring-requirements",
  "date": "2026-10-05",
  "scope": {
    "project": "wiki",
    "change_id": "add-netdata-monitoring",
    "phase": 1
  },
  "action": "dev_task",
  "commit": "a47b6b6",
  "source": "Заказчик, Telegram DM 2026-10-05: «1. Утверждаю 2. Расширяем (обе репы учти в этом случае)» — ответ на развилку (утверждение requirements add-netdata-monitoring + эскалация E1 zone-policy sa)"
}
```
