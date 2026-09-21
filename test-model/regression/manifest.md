# Манифест регресса: домен suggestions (change add-suggestions)

> Ведет: qa_regression_analyst (с первого релиза; роль по H5 — боевой запуск
> на первом change с MODIFIED/REMOVED-дельтами). Заготовка создана
> qa_automation в рамках автоматизации дыры FR-17 (QA-цикл 1.5, Р1.3).
> Источник вердиктов: `test-model/impact/add-suggestions.md` (все keep, 0
> candidate-archive) + review-001 (одобрить, 5 minor — учтены в тестах).
>
> **Порядок меток:** `# regression: keep` — тест гоняется всегда; метка
> `candidate-archive` — только для разовых тестов (миграции, воспроизведение
> конкретного прод-бага, разовое событие). Проставляется комментарий в код
> теста + строка в эту таблицу. Изменение метки — только через impact-анализ.

## Таблица: тест → метка → обоснование

| Тест | Файл | Кейс / CHK | Метка | Обоснование |
|---|---|---|---|---|
| `test_suggestions_200_and_format` | tests/api/test_suggestions.py | TC-API-SUGG-001 | keep | Постоянное спек-поведение FR-15/СЦ-1: 200 + формат `{"suggestions": [...]}` + членство значений; эндпоинт постоянный (impact-001 п.1) |
| `test_suggestions_unauthorized` | tests/api/test_suggestions.py | TC-API-SUGG-002 | keep | Негатив 401 (FR-18, следствие NFR-7); безопасность не подлежит архивированию никогда (impact-001 п.1) |
| `test_suggestions_unique` | tests/api/test_suggestions.py | TC-API-SUGG-003 | keep | Set-семантика (FR-16/СЦ-3) — контрактное поведение; QAT-изоляция, `count == 1` не зависит от чужих данных (impact-001 п.1) |
| `test_suggestions_sorted` | tests/api/test_suggestions.py | TC-API-SUGG-004 | keep | Сортировка (FR-16/СЦ-4): инвариант `s == sorted(s)`, устойчив к составу данных (impact-001 п.1) |
| `test_suggestions_union_of_tags_and_categories` | tests/api/test_suggestions.py | TC-API-SUGG-005 | keep | Объединение источников (FR-16/17/СЦ-5): membership-ассерты по уникальным значениям, не хрупко (impact-001 п.1) |
| `test_suggestions_exclude_orphan_tag_and_null_category` | tests/api/test_suggestions_gap.py | TC-sugg-006 / CHK-S-6 | keep | FR-17, Scenario 6 спеки: «только заведенные» (осиротевший тег, NULL-категория) — постоянное контрактное требование |
| `test_free_input_does_not_change_suggestions_source` | tests/web/test_search_suggestions_ui.py | TC-sugg-007 / CHK-S-7 | keep | FR-17, Scenario 7 спеки: свободный ввод легитимен (FR-11), источник подсказок не меняется — устойчивое поведение |
| `test_suggestions_all_categories_empty_only_tags` | tests/api/test_suggestions_gap.py | TC-sugg-008 / CHK-S-8 | keep | FR-17, граница: фильтр `category IS NOT NULL AND != ''` — постоянный инвариант UNION |
| `test_suggestions_task_delete_updates_without_restart` | tests/api/test_suggestions_gap.py | TC-sugg-009 / CHK-S-9 | keep | FR-17, состояние: пересчет подсказок на каждый GET без кеша/рестарта — постоянное свойство |
| `test_tag_hints_datalist_bound_and_filled` | tests/web/test_search_suggestions_ui.py | TC-UI-SUGG-001 | keep | FR-15/СЦ-8: привязка datalist к обоим полям + заполнение из живого ответа API; захардкоженных ожиданий нет (impact-001 п.1) |
| `test_tag_hints_set_semantics_and_order` | tests/web/test_search_suggestions_ui.py | TC-UI-SUGG-002 | keep | FR-16 в UI: дубль пересечения + порядок option; источник истины — живой API, QAT-изолировано (impact-001 п.1) |

## Итог

- **11/11 keep, 0 candidate-archive** (7 из impact-анализа + 4 новых из дыры FR-17).
- Метки `# regression: keep` + однострочное обоснование проставлены в коде
  каждого теста (и fixture keep-тестов: `sugg_fixtures`, `sugg_gap_tasks`).
- Разовых тестов (кандидатов на архив) в домене нет: scenarios 6–9 —
  граничные/негативные/состояние, все — постоянное поведение ADDED-Requirement.

## Правило для будущих записей

1. Новый тест → impact-вердикт → метка в код (`# regression: keep|candidate-archive`
   + одна строка обоснования) → строка в таблицу выше.
2. `candidate-archive` — только разовые тесты; обоснование должно называть
   разовое событие (миграция, прод-баг, дата).
3. Изменение метки существующего теста — только через revalidate/retire
   impact-анализа (MODIFIED/REMOVED-дельта), история append-only.
