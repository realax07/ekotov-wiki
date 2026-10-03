# Решение: P11 контейнеризация (ЭТАП 0+1)

```decision-record
schema_version: decision-record/1
decision_id: 2026-10-03-p11-containerization
date: 2026-10-03
scope:
  project: ekotov-wiki
  change_id: add-containerization
action: create_change
commit: 5027073
source: |
  Заказчик (Telegram, 2026-10-03): «Согласен со всем» (по ОВ-1..4 плана
  P11), дополнение: SSL-сертификата нет, ходим по битому серту, ошибки
  игнорируем; Docker на VPS отсутствует. После factory-init доработки:
  «наведи порядок в ekotov-wiki... подготовь структуру папок под каждый
  сервис, это часть будущего перехода на микросервисы». SA назначен
  главным проектировщиком (перепроектирование границ/виртуализация);
  БА — легкий проход (внешнее поведение продукта не меняется).
expiration: null
```

## Содержание

Запускается change `add-containerization` (ЭТАП 0+1 плана P11):
контейнеризация монолита как есть (app + nginx + том данных, compose),
открытие /openapi.json как машинного контракта, e2e против compose-стенда.
ЭТАП 2 (выделение search) — отдельно после паузы эксплуатации.

Нормативный план: docs/ba/architecture-services-plan.md (сверен с кодом,
решения ОВ-1..4 зафиксированы в §8).
