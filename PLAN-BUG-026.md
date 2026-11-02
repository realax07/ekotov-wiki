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
      run: gate:python3 -m pytest tests/api/test_images_gallery.py tests/api -q -k "reaction or like or dislike" --ignore=tests/web
    - id: review
      run: hermes:code_reviewer
```

## Журнал раннера

- 2026-11-02T06:56:26Z | stage dev_fix | pi:dev | ok
- 2026-11-02T06:56:33Z | stage tests_gallery | gate:python3 -m pytest tests/ -q -k gallery | STOP (gate exit 2)
- 2026-11-02T07:36:34Z | stage dev_fix | pi:dev | ok
- 2026-11-02T07:36:41Z | stage tests_gallery | gate:python3 -m pytest tests/ -q -k gallery | STOP (gate exit 2)
- 2026-11-02T07:48:32Z | stage dev_fix | pi:dev | ok
- 2026-11-02T07:50:29Z | stage tests_gallery | gate:python3 -m pytest tests/ --ignore=tests/web -q | STOP (gate exit 1)
- 2026-11-02T07:57:28Z | stage dev_fix | pi:dev | ok
- 2026-11-02T08:09:34Z | stage dev_fix | pi:dev | ok
- 2026-11-02T08:11:31Z | stage tests_gallery | gate:python3 -m pytest tests/ --ignore=tests/web -q | STOP (gate exit 1)
- 2026-11-02T10:50:47Z | stage dev_fix | pi:dev | ok
- 2026-11-02T10:52:44Z | stage tests_gallery | gate:python3 -m pytest tests/ --ignore=tests/web -q | STOP (gate exit 1)
