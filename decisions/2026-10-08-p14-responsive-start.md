# Решение Заказчика 2026-10-08-p14-responsive-start

**Дата:** 2026-10-08
**Источник:** Заказчик, Telegram DM, 2026-10-08: «С 1 по 5 да; 6 — iPhone 11 у жены,
у меня Z Fold 7» — в ответ на ОВ-1..ОВ-6 БА-проработки P14 (дражфт
openspec-drafts/p14-responsive-requirements-draft.md, влит PR #94/#95).

**Смысл:** старт пакета Флоу 1 add-responsive-mobile (P14 «Адаптивная верстка
mobile-first»). Все развилки закрыты рекомендациями БА: бургер/drawer, свайп-колонки
со scroll-snap (санкция на дельту FR-62), fullscreen-модалка тикета (просмотр →
«Редактировать»), свайпы лайтбокса; планшет 768px вторичен («не разваливается»).
Целевые устройства: iPhone 11 (375px минимум) и Z Fold 7 (foldable; раскрытое
состояние = узкий планшет, отдельного макета нет).

```decision-record
{
  "schema_version": "decision-record/1",
  "decision_id": "2026-10-08-p14-responsive-start",
  "date": "2026-10-08",
  "scope": {
    "project": "wiki",
    "change_id": "add-responsive-mobile",
    "phase": 1
  },
  "action": "start_flow1",
  "commit": "3ba596d",
  "source": "Заказчик, Telegram DM 2026-10-08: «С 1 по 5 да; 6 — iphone 11 у жены, у меня z fold 7» — старт P14 по БА-проработке"
}
```
