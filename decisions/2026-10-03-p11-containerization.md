# Решение: P11 контейнеризация (ЭТАП 0+1)

Человекочитаемая часть: Заказчик одобрил план P11 (ОВ-1..4 — все рекомендации
ПМ приняты), дополнения: SSL CA нет — ходим по self-signed до 2028, ошибки
игнорируем; Docker на VPS отсутствует (входит в ЭТАП 0). SA — главный
проектировщик (перепроектирование границ/виртуализация); БА — легкий проход
(внешнее поведение продукта не меняется). Нормативный план:
docs/ba/architecture-services-plan.md §8 (решения + факты VPS).

```decision-record
{
  "schema_version": "decision-record/1",
  "decision_id": "2026-10-03-p11-containerization",
  "date": "2026-10-03",
  "scope": {"project": "ekotov-wiki", "change_id": "add-containerization"},
  "action": "create_change",
  "commit": "5027073",
  "source": "Telegram 2026-10-03: «Согласен со всем» (ОВ-1..4 плана P11); дополнение: SSL CA нет, self-signed до 2028; Docker отсутствует → ЭТАП 0. SA — главный проектировщик, БА — легкий проход."
}
```
