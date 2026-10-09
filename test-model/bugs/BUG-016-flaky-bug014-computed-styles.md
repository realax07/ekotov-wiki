# BUG-016: flaky test_search_task_view_computed_styles_match_board (bug014-сьют)

- **Дата:** 2026-10-09 00:30 UTC
- **Источник:** QA 5.1 add-responsive-mobile (deleg_5ae3be12, подтверждено ПМ)
- **Серьезность:** minor (тестовая инфраструктура, не продукт)

## Кейс

`tests/web/test_bug014_search_task_view.py::test_search_task_view_computed_styles_match_board`

## Ожидание

Тест стабильно зеленый: computed styles панели просмотра задачи совпадают с доской.

## Факт

Падает ~25% (2/8 прогонов в QA 5.1), нестабильно между сессиями.

## Root cause (диагноз QA)

Гонка тест-механики: `evaluate` вычисляет стили без предварительного ожидания
появления `.task-view-head`; при медленной перерисовке элементы отсутствуют в
момент снятия значений.

## Рекомендация

Добавить `expect(page.locator(".task-view-head")).to_be_visible()` перед
evaluate-блоком (паттерн автожиданий Playwright, ОГР спеки qa-pipeline:
никаких sleep).

## Окружение

nginx-стенд :18443 (app+search+images), chromium, fresh tmp-БД; воспроизводится
и на main 64dedaf, и до волн 1–4 (не P14-регресс).
