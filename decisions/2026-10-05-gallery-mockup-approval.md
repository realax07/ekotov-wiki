# Решение Заказчика: утверждение мокапов 1.1 (add-gallery-service) + ack инцидента bypass

Дизайн-приемка задачи 1.1 [design] (мокапы d080883 + инкремент: превью
contain, бейджи форматов). Дословно Заказчика (2026-10-05, Telegram):
«По прошлому вопросу, макеты утверждаю» + «Признаю.» (по инциденту
bypass deleg_4e067ab4).

## Что решено

1. Мокапы галереи 1.1 УТВЕРЖДЕНЫ: gallery-grid / gallery-lightbox /
   gallery-upload (инкремент в силе: превью contain без кропа, бейджи
   jpeg/png/webp/gif, подсказки форматов в upload). Развилка закрыта —
   dev 1.5 (страница /gallery) разрешен строго по этим мокапам.
2. Ack инцидента delegate_watchdog: обход deleg_4e067ab4 (ui_designer
   1.1 инкремент) признан Заказчиком; работа легитимна (коммиты в ветке),
   диспатч — процессное нарушение. Все следующие диспатчи — только полный
   цикл delegate_gate (start/run/finish) + поздний reconcile делегации.
3. Директива Заказчика: design_validator ОБЯЗАТЕЛЕН после реализации —
   включен в 2.1(г) обоих пакетов R7 (netdata — уже в tasks; gallery —
   в tasks 2.1 присутствует).

## Последствия

- Пакет 1: закрыта бухгалтерия 1.3 (nginx/basic auth, 3fd7af7), стартует
  QA-волна 2.1 (включая design_validator).
- Пакет 2: ветка add-gallery-service выправлена (SA-коммиты 1ddba4a..
  89be53f вернулись в историю, мокапы перебазированы сверху, 189fadb);
  dev-волна 1.2–1.5 к запуску через ворота.

```decision-record
{
  "schema_version": "decision-record/1",
  "decision_id": "2026-10-05-gallery-mockup-approval",
  "date": "2026-10-05",
  "scope": {
    "project": "wiki",
    "change_id": "add-gallery-service",
    "phase": 1
  },
  "action": "design_task",
  "commit": "189fadb",
  "source": "Заказчик, Telegram DM 2026-10-05: «По прошлому вопросу, макеты утверждаю» + «Признаю.» (ack bypass deleg_4e067ab4) + директива «Не забудь валидатора дизайна запустить, после реализации»"
}
```
