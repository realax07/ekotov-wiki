# Решение Заказчика 2026-10-08-arch-review-policy

**Дата:** 2026-10-08
**Источник:** Заказчик, Telegram DM, 2026-10-08: вопрос «архитектор у нас участвует
в процессах?» → обсуждение валидации change на существующей архитектуре → санкция
«давай» на правило ниже.

## Правило: architecture review — двухуровневый триггер

1. **Обязательный arch-review** (этап architecture_review, роль архитектор):
   change затрагивает `services/**`, контрактные границы `backend/**` (API/схемы),
   `deploy/**`, ИЛИ несет MODIFIED/REMOVED-дельты контрактообразующих спек
   (auth, deploy, границы сервисов). Ревью — против `architecture/map.md` +
   спек контрактов, вердикт в `test-model/reviews/<change>/review-NNN-architecture.md`.
2. **Явный skip** (UI-only и прочие изменения вне п.1): ПМ фиксирует решение
   decision-файлом с обоснованием «arch не требуется, зона <обоснование>» —
   не молча. Прецедент: add-responsive-mobile (UI-поведенческие дельты,
   контракты/границы не тронуты).
3. **Машинный фикс (отдельный chore-пакет, после P14):** отсутствие sdd.md при
   обязательном arch-этапе должно давать явный INVALID_GATE (сейчас проверка
   молча пропускается при sdd.md=MISSING — flow_transition.py:315, условие
   `sdd_status == "ready"`). Не включать до завершения P14 — иначе заблокирует
   текущую волну.

## Применение

- К текущему add-responsive-mobile — п.2 (skip): зона frontend/UI, MODIFIED-дельты
  board/gallery/tasks — поведение, не контракты.
- К следующим пакетам — триггер п.1 проверяет ПМ на prepare (approval_ref
  решение/ skip-решение).

```decision-record
{
  "schema_version": "decision-record/1",
  "decision_id": "2026-10-08-arch-review-policy",
  "date": "2026-10-08",
  "scope": {
    "project": "wiki",
    "change_id": "process",
    "phase": 1
  },
  "action": "rules_change",
  "commit": "a7208e9",
  "source": "Заказчик, Telegram DM 2026-10-08: «давай» — санкция правила arch-review"
}
```
