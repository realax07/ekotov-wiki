# Решение Заказчика: действие design_task в Флоу 1 (роль ui_designer)

## Контекст

SA пакета `add-netdata-monitoring` ввел задачу `1.1 [design] ui_designer`
(мокапы UI-дельты в `design/`, паттерн Р4/Р5 — требование Заказчика «Дизайн
не забудь» / «У нас есть дизайнер»). Механика Флоу 1 остановила диспатч:
`dev_task` зарезервирован ролью `dev` (WRONG_ROLE на ui_designer).
Предложенные варианты: расширение STAGE_TABLE (dev + ui_designer) /
внеполосный артефакт / dev рисует мокап. Заказчик выбрал введение
специализированного действия: «Может внедрим design task?».

## Что решено

1. В Флоу 1 вводится действие **`design_task`** — роль **`ui_designer`**,
   зона записи `design/**` (уже в role_zone_policy). Стадия в STAGE_TABLE
   Флоу 1 — рядом с `dev_task` (после architecture_review, до/параллельно
   dev-задач; gates: flow_check, pm_bounds_check J9/J10 — те же, что dev_task).
2. Изменение ядра вносится в ОБОИХ репозиториях (`~/ekotov-wiki`,
   `~/ai-factory`) `[pipeline]`-коммитом синхронно: STAGE_TABLE Флоу 1 +
   check_design_task (проверки — как check_dev_task: requirements approved +
   arch review + task существует).
3. ТЗ ui_designer-делегаций идут через delegate_gate (start → диспатч →
   finish) как остальные роли; ревью design-артефактов — design_validator
   (существующая роль, зона test-model/reviews/*/review-*-design.md).
4. J10 не применяется к `[design]`-задачам (аналог [ops]/[docs]: мокап не
   код — review-файл не обязателен; приемка через утверждение мокапа
   Заказчиком, фиксируется в tasks.md чекбоксом после вердикта «ок»).

## Последствия

- approval_ref для design_task пакета add-netdata-monitoring:
  `2026-10-05-netdata-monitoring-requirements` (уже покрывает задачи пакета).
- Задача 1.1 [design] диспатчится после мержа ядра (обе репы) —
  `delegate_gate start --action design_task --role ui_designer`.
- Перенос в ai-factory BACKLOG не нужен — правка вносится в эталон этим же
  решением.

```decision-record
{
  "schema_version": "decision-record/1",
  "decision_id": "2026-10-05-design-task-flow1",
  "date": "2026-10-05",
  "scope": {
    "project": "wiki",
    "change_id": "add-netdata-monitoring",
    "phase": 1
  },
  "action": "design_task",
  "commit": "08025cf",
  "source": "Заказчик, Telegram DM 2026-10-05: «Может внедрим design task?» — ответ на развилку WRONG_ROLE (dev_task зарезервирован dev; варианты ОВ-1 расширение / ОВ-2 внеполосно / ОВ-3 dev рисует)"
}
```
