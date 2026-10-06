# Решение Заказчика: QA-волна 2.1 add-netdata-monitoring + dev-волна add-gallery-service

Дословно Заказчика (2026-10-05, Telegram): «Погнали дальше» — в контексте
доклада ПМ о готовности: пакет 1 (netdata) — все dev-задачи 1.1–1.4 закрыты
(1.3 = 3fd7af7), остается QA 2.1; пакет 2 (gallery) — мокапы 1.1 утверждены
(2026-10-05-gallery-mockup-approval), SA-артефакты готовы, dev-волна 1.2–1.5
к запуску. Директива «Не забудь валидатора дизайна запустить, после
реализации» (2026-10-05) — design_validator обязателен в QA-фазе.

## Что решено

1. QA-задача 2.1 add-netdata-monitoring (включая 2.1(г) design_validator
   против утвержденного мокапа 1.1) — к запуску.
2. Dev-волна add-gallery-service (задачи 1.2 services/images, 1.3 миграция
   ядра + compose, 1.4 nginx, 1.5 страница /gallery по утвержденным мокапам)
   — к запуску на ветке add-gallery-service.
3. approval_ref диспатчей: `2026-10-05-r7-execution` (настоящее решение).
4. Зоны не пересекаются (QA: tests/e2e/test-model; dev gallery: backend,
   services, frontend, deploy — ветка отдельная), параллельный запуск
   разрешен в рамках одного сервиса (wiki).

## Последствия

- Все диспатчи — только полный цикл delegate_gate (start → run → finish).
- 1.3 netdata: процессный хвост (возврат flowctl по чужим путям в diff-окне)
  не блокирует QA; приемка 1.3 фиксируется ПМ отдельно.

```decision-record
{
  "schema_version": "decision-record/1",
  "decision_id": "2026-10-05-r7-execution",
  "date": "2026-10-05",
  "scope": {
    "project": "wiki",
    "change_id": "add-netdata-monitoring",
    "phase": 1
  },
  "action": "dev_task",
  "commit": "118caf6",
  "source": "Заказчик, Telegram DM 2026-10-05: «Погнали дальше» — запуск QA 2.1 add-netdata-monitoring + dev-волны add-gallery-service (мокапы утверждены 2026-10-05-gallery-mockup-approval); design_validator обязателен (директива 2026-10-05)"
}
```
