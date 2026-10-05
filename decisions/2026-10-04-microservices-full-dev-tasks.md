# Решение: dev-задачи ЭТАПА B add-microservices-full — делегации через delegate_gate

- **decision_id:** 2026-10-04-microservices-full-dev-tasks
- **Дата решения Заказчика:** 2026-10-04 (дословная фиксация из диалога)
- **Статус:** принято

## Дословная фиксация

> «Давай сделаем.» — Заказчик, 2026-10-04 (Telegram DM; ответ на доклад ПМ:
> BYPASS-инцидент — 8 делегаций задач 1.1/1.2 цикла add-microservices-full
> диспатчились мимо delegate_gate; следующие задачи пакета (1.3–1.5, ревью) —
> только через delegate_gate.py с prepare/run/finish и валидным approval_ref;
> ПМ подготовит decision-record на dev-задачи пакета)

## Что решено

1. Dev-задачи ЭТАПА B пакета `add-microservices-full` (1.3, 1.4, 1.5 и
   последующие dev-задачи пакета до его архивации) делегируются ТОЛЬКО через
   `scripts/delegate_gate.py` (prepare → run → finish), роль dev, действие
   dev_task.
2. Обходы 1.1/1.2 (deleg_1dfe5828 и др., файл
   `~/.hermes/state/delegate_bypass_incidents.json`) признаются нарушением
   процесса при корректном результате; результат принят, процесс исправлен
   (этим решением).
3. Вотчдог (delegate_watchdog, крон */5) остается слоем гарантии; его
   BYPASS-репорты доставляются Заказчику как есть.

## Последствия

- approval_ref для dev_task задач 1.3–1.5 пакета: `2026-10-04-microservices-full-dev-tasks`.
- Роль у delegate_gate: `dev` (WRONG_ROLE на devops — задача 1.4 в tasks.md
  помечена «Devops», но действие dev_task в графе Флоу 1 зарезервировано
  ролью dev; исполнение задач 1.2–1.4 — dev-сабагент в зоне deploy/**,
  frontend/**, services/**).
- Зоны задач берутся из фактических файлов задачи (deploy/**, services/**,
  tests/api/** и т.п. — в пределах зон роли dev политики).

```decision-record
{
  "schema_version": "decision-record/1",
  "decision_id": "2026-10-04-microservices-full-dev-tasks",
  "date": "2026-10-04",
  "scope": {
    "project": "wiki",
    "change_id": "add-microservices-full",
    "phase": 1
  },
  "action": "dev_task",
  "commit": "41ffe87",
  "source": "Заказчик, Telegram DM 2026-10-04: «Давай сделаем.» (ответ на доклад о 8 BYPASS-обходах delegate_gate и предложении оформить решение на dev-задачи ЭТАПА B)"
}
```
