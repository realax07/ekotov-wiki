# План: наполнение эшелонов регресса в ekotov-wiki (J54 → проект)

**Заявлено:** 2026-10-19. **Флоу:** 4 (обслуживание). **Роли:** dev → code_reviewer. **Ворота:** pr_validate + regress-артефакт по контуру (regress-final не требуется — прод-код не меняется).

## Фактура (инвентаризация 2026-10-19)
Каркас есть, контента нет: tests/smoke_cross/ = только README; test-model/regress-domains.json = rules:[]; test-model/regress/baseline.json = []; test-model/smoke-cross/manifest.json = suites:[].

## Состав работ
1. **Доменная карта** (`test-model/regress-domains.json`): домены по наборам кейсов (решение Заказчика, J54): wiki, gallery, video, auth-search, tasks-board (+ r4-комментарии в своих доменах). Правило: домен → паттерны тестов/TC-префиксы. Заполнить из фактической структуры tests/ и TC-ID.
2. **Cross-domain smoke** (`tests/smoke_cross/`): по 1–2 теста на домен — health (все сервисы), авторизация, страница wiki, картинка, видео. Целевой прогон 2–3 мин на каноническом контуре. Использовать существующие фикстуры/помощники (tests/conftest, api-клиенты), без дублирования.
3. **Manifest** (`test-model/smoke-cross/manifest.json`): suites = список smoke-файлов.
4. **Baseline** (`test-model/regress/baseline.json`): начать пустым (зафиксированных флейков нет); записать правило ведения в README smoke_cross.
5. **Верификация**: `flowctl regress --tier smoke` реально гоняет smoke; доменный прогон (по одному домену из карты) срезает набор корректно (числа в отчет). Полный regress-final НЕ обязателен (прод-код не трогается), но smoke-прогон и выборочный доменный — обязательны.

## Границы
- Прод-код (backend/services/frontend) не меняется — только тесты, manifest, карты, docs.
- xdist: smoke и доменные прогоны — api-часть может -n 4; web-часть сериально (гайд xdist-regression-echelons).
- Зеркало фабрики не трогается (всё байт-в-байт актуально).
