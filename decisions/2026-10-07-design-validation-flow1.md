# Решение: design_validation в графе Флоу 1 (этап QA)

- **decision_id:** 2026-10-07-design-validation-flow1
- **дата:** 2026-10-07
- **статус:** принято (дословная фиксация решения Заказчика в Telegram DM, 2026-10-07)

## Scope

- repo: ekotov-wiki + ai-factory (эталон), файл `scripts/flow_transition.py`
- тип: `[pipeline]` — расширение ядра конвейера

## Контекст (факт)

Пакет add-ui-polish-r8, задача 3.1(г): design_validator (сверка реализованного
UI с утвержденными мокапами) не проходит через delegate_gate — в графе Флоу 1
(STAGE_TABLE) нет пары действие+роль для design_validator. Зона роли в
role_zone_policy есть (`test-model/reviews/*/review-*-design.md`), действия нет.
Машина (enforcing) последовательно DENY: `code_review`→только code_reviewer,
`qa_automation`→только qa_automation, `qa_review`→INVALID_GATE (нет кейсов в
new/). DENY-факты: deleg-bce54776addf43ca (WRONG_ROLE code_review),
deleg-561cec6aeb5e4bc1 (WRONG_ROLE qa_automation), deleg-cdea5a2a0f92435c
(INVALID_GATE qa_review).

Прецедент R7 (add-netdata-monitoring 2.1): design-проход шел в составе
qa-задачи под ролью dev, без отдельного gate — обход, не решение.

## Решение Заказчика (дословно)

Выбор из развилки: «Расширить ядро: действие design_validation
(design_validator) в граф Флоу 1 — [pipeline]-коммит в обоих репо».

## Action

1. `Stage("design_validation", ("design_validator",), False,
   ("flow_check (контракт 5: review-файл вердикта)",), check_design_validation)`
   в STAGE_TABLE Флоу 1, после qa_automation.
2. `check_design_validation`: требует задачу (как code_review flow=1) +
   наличие утвержденных мокапов дизайн-фазы (факт design-approve решения
   необязателен на уровне ядра — проверка зоны и задачи достаточны;
   содержательная сверка — работа агента).
3. Синхронно: таблица ролей в agents/README.md обоих репо (строка
   design_validator уже есть, дополнить колонку действия).
4. Тест: test_flowctl (ekotov-wiki) — ALLOW на design_validation/design_validator
   с зоной review-*-design.md; DENY WRONG_ROLE для чужой роли на действии.
5. diff кода ядра = идентичный в обоих репо (эталон ai-factory → проект).

## Gates

flow_check + pm_bounds_check не требуются (ядро); проверка — юнит-тесты
test_flowctl.py + живой prepare в ekotov-wiki.

```decision-record
decision_id: 2026-10-07-design-validation-flow1
date: 2026-10-07
customer_quote: "Расширить ядро: действие design_validation (design_validator) в граф Флоу 1 — [pipeline]-коммит в обоих репо"
scope:
  repos: [ai-factory, ekotov-wiki]
  files: [scripts/flow_transition.py, agents/README.md]
  pipeline: true
```
