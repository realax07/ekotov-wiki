# Чеклист проверок: add-netdata-monitoring

Change-пакет: `openspec/changes/add-netdata-monitoring/` — дельта deploy
(MODIFIED: сервис netdata в матрице + nginx-локации /netdata в frontend),
новые capabilities monitoring + navigation.
ТЗ для сверки: requirements.md пакета (факты QA-цикла: REPORT-2.1-netdata-qa.md
web 171p/1s, api 201p/9s/2xf, смоук /netdata 10/10), design.md §1–§6,
решение Заказчика 2026-10-05-netdata-mockup-approval.

Типы: **поз.** — позитивная, **нег.** — негативная, **НФТ** — нефункциональная,
**сред.** — средовое предусловие (деплой-проверка).

## Monitoring (capability monitoring, FR-75/76, NFR-19)

| ID | Источник | Проверка | Тип | Приоритет | Покрытие |
|---|---|---|---|---|---|
| CHK-ADD-1 | monitoring Requirement: Метрики собираются без агентов на хосте / FR-75 | сервис netdata в compose прод/стенд, паритет топологии | поз./сред. | Must | review-002-1.2 approve (yaml-сверка) + REPORT-2.1 §3 |
| CHK-ADD-2 | monitoring Requirement: Netdata не публикуется / FR-75 | порты netdata не публикуются; доступ только через nginx /netdata/ | нег. | Must | review-002-1.2 + смоук REPORT-2.1 §3 (прямого порта нет в compose) |
| CHK-ADD-3 | monitoring Requirement: Доступ к дашборду защищен / FR-76 | `/netdata` → 301; `/netdata/` без кредов → 401 (realm до прокси); с кредами → 200 + маркер дашборда; неверный пароль → 401 | поз./нег. | Must | REPORT-2.1 §3 (смоук 10/10, live-nginx + стаб) |
| CHK-ADD-4 | monitoring Requirement: NFR-19 ресурсы ограничены | mem_limit 256m, logging 10m×3, restart unless-stopped, healthcheck | НФТ | Must | review-002-1.2 (yaml-сверка) |
| CHK-ADD-5 | monitoring Scenario: метрики хоста и контейнеров в дашборде (FR-75) | `/api/v1/…` через прокси отдают метрики host+containers; RAM netdata ≤ 256m | поз./сред. | Must | **частично**: смоук дашборд-маркера (стаб); живые метрики + docker-коллектор + RAM-замер — 2.2 (E-2.1a) |

## Navigation (capability navigation, FR-78)

| ID | Источник | Проверка | Тип | Приоритет | Покрытие |
|---|---|---|---|---|---|
| CHK-ADD-6 | navigation Requirement: Ссылка «Мониторинг»… / FR-78 | owner (Product manager) видит пункт в sidebar-footer; PE/wife и аноним — не видят | поз./нег. | Must | TC-ADD-201…206 (tests/web/test_qa21_netdata_sidebar_ui.py, 6 проверок, REPORT-2.1 §2) |
| CHK-ADD-7 | navigation Requirement: Вид пункта по утвержденному мокапу | иконка-пульс, hover/focus-visible/active, токены V3 (не хардкод), позиция sidebar-footer | поз. | Must | design_validator review-001-design APPROVE + TC-ADD-205/206 (токены/регресс) |
| CHK-ADD-8 | navigation Scenario: переход открывает /netdata/ в новой вкладке (FR-78) | href=/netdata/ target=_blank rel=noopener; без промпт-карточки (решение Заказчика) | поз. | Must | TC-ADD-202 + design_validator APPROVE |

## Deploy MODIFIED: смоук-матрица выката

| ID | Источник | Проверка | Тип | Приоритет | Покрытие |
|---|---|---|---|---|---|
| CHK-ADD-9 | deploy Requirement: NFR-10 паритет топологии | compose прод/стенд идентичны по сервисам/лимитам/маунтам | поз./сред. | Must | review-002-1.2 + статическая yaml-сверка (REPORT-2.1 §3.3) |
| CHK-ADD-10 | deploy Requirement: деградация | остановленный netdata → управляемая ошибка /netdata/, остальные маршруты работают | нег./сред. | Must | смоук REPORT-2.1 §3 (app/search не затронуты); полный live-чек — 2.2 |
| CHK-ADD-11 | deploy Scenario: регресс ядра при выкате (FR-75, NFR-10) | полный api+web регресс зеленый после включения netdata в матрицу | сред. | Must | REPORT-2.1 §2 (201p/171p, 0 продуктовых фейлов) |

## Дефекты спеки

- Э-1 (review 001-1.2/REVIEW-2.1): чек «/api/health images через nginx 200» в задачах gallery-пакета неинформативен (маршрут уходит в app, false positive) — учтено в пакете add-gallery-service, к netdata не относится.
- Дефектов спеки add-netdata-monitoring не обнаружено; расхождение «проверка ссылки требует стенда с netdata» (tasks.md §Зависимости) учтено разнесением: ролевая видимость — 2.1a (TC-ADD), живой дашборд — 2.2.
