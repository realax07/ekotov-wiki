# PLAN-BUG-026: идемпотентный PUT реакции (TD-5)

Флоу: 2 — баг-фикс (пилот оркестратора: исполнение через package_runner)

## Задача
dev: PUT like/dislike → idempotent set (тот же голос no-op 200; противоположный — перенос);
снятие голоса — DELETE. Обновить докстринг, тесты gallery (позитив идемпотентности).

## Pipeline

```yaml
pipeline:
  package: BUG-026
  flow: 2
  stages:
    - id: dev_fix
      run: pi:dev
      zones:
        - services/images/**
      inputs: [test-model/bugs/BUG-026-reaction-put-not-idempotent.md]
      task: "PUT /api/images/{id}/like и /dislike сделать идемпотентным: тот же голос — 200 no-op (без снятия); противоположный — перенос как сейчас. Снятие — DELETE (если есть) или повторный PUT противоположного. Обновить докстринг + тесты идемпотентности в tests/."
    - id: tests_gallery
      run: gate:python3 -m pytest tests/ -q -k gallery
    - id: review
      run: hermes:code_reviewer
```
