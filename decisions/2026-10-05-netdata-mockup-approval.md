# Решение Заказчика: утверждение мокапов 1.1 (add-netdata-monitoring)

Дизайн-приемка задачи 1.1 [design] (мокапы eac40de: sidebar/transition/icon).
Дословно Заказчика (2026-10-05, Telegram): «1. ок, можем без карточки
2. Утверждаю 3. Не нужен.»

## Что решено

1. Промпт-карточка перед дашбордом НЕ нужна: клик «Мониторинг» → `/netdata/`
   напрямую (basic auth спрашивает браузер сам).
2. Иконка-пульс утверждена (netdata-icon.svg).
3. Маркер внешней ссылки у пункта сайдбара НЕ нужен.

## Последствия

- dev 1.4 внедряет: пункт сайдбара «Мониторинг» (owner-only, direct link),
  без переходной страницы; transition-mockup в архив (не внедряется).

```decision-record
{
  "schema_version": "decision-record/1",
  "decision_id": "2026-10-05-netdata-mockup-approval",
  "date": "2026-10-05",
  "scope": {
    "project": "wiki",
    "change_id": "add-netdata-monitoring",
    "phase": 1
  },
  "action": "dev_task",
  "commit": "026cd56",
  "source": "Заказчик, Telegram DM 2026-10-05: «1. ок, можем без карточки 2. Утверждаю 3. Не нужен.»"
}
```
