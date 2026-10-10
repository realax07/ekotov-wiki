# Чеклист проверок: add-microservices-full

Change-пакет: `openspec/changes/add-microservices-full/` — дельта deploy
(MODIFIED: миграция one-shot до подъема, матрица сервисов) + новая capability
services (ADDED: search-сервис, nginx-маршрутизация, 503-деградация,
backup-sidecar).
ТЗ для сверки: requirements.md пакета (факты QA-цикла: REPORT-regress-21.md
финал api 201p/9s/2xf/0f, web 165p/0f/1s; REPORT-matrix-22.md), решения —
design.md §1–§8, sdd.md пакета.

Типы: **поз.** — позитивная, **нег.** — негативная, **гран.** — граничное значение,
**НФТ** — нефункциональная, **сред.** — средовое предусловие (деплой-проверка).

## Сервисный разрез search (capability services)

| ID | Источник | Проверка | Тип | Приоритет | Покрытие |
|---|---|---|---|---|---|
| CHK-P12-1 | services Requirement: Поиск работает отдельным сервисом / Scenario: Маршруты обслуживает search | `/api/search*`, `/api/suggestions*` через nginx → 200 + `X-Service: search` | поз./сред. | Must | REPORT-regress-21 §5 (смоук) + REPORT-matrix-22 §2 |
| CHK-P12-2 | services Requirement: Поиск работает отдельным сервисом / Scenario: Ядро не содержит маршрутов | `main.py` без search/suggestions-роутеров; гейт «экспорт = файл» green | нег. | Must | **TC-openapi-201/202** (tests/api/test_openapi_search_service.py, задача 1.5) |
| CHK-P12-3 | services Requirement: Контракт поиска зафиксирован до выделения / Scenario: экспорт = файл | Схема search-сервиса = замороженный `contracts/openapi-search.json` (пути/операторы/схемы) | поз. | Must | гейт 0.1/1.5 (сверка программная) + юниты 12p |
| CHK-P12-4 | services Requirement: Search читает данные read-only | search на ro-маунте отвечает при живом app (WAL-протокол db.py) | поз./сред. | Must | юниты services/search 12p + REPORT-regress-21 (201p на маршрутизированном стенде) |
| CHK-P12-5 | services Requirement: Поиск работает отдельным сервисом (nginx 503-деградация, design §4) | stop search → управляемый 503 JSON + Retry-After за ~1мс; restart → восстановление ≤0.5с | нег./сред. | Must | REPORT-matrix-22 §2 (PASS) |
| CHK-P12-6 | services Requirement: Search читает данные read-only / Scenario: изоляция записи при упавшем search (design §8) | запись в app живет при упавшем search (201/200), задачи находимы после restart | поз./сред. | Must | REPORT-matrix-22 §2.3 (смоук записи, PASS) |
| CHK-P12-7 | services Requirement: Поиск работает отдельным сервисом / Scenario: nginx-маршрутизация семейства (design §1/§4) | `= /api/search` + `^~ /api/search/`, resolver 127.0.0.11, без соседских захватов | нег. | Must | review-001-1.3/1.4 approve + смоук 4 эндпоинтов (REPORT-matrix-22 §2) |

## Deploy MODIFIED: матрица сервисов (FR-70/71/72 паритет)

| ID | Источник | Проверка | Тип | Приоритет | Покрытие |
|---|---|---|---|---|---|
| CHK-P12-8 | deploy Requirement: Миграции БД — one-shot до подъема нового app | миграция из образа ядра строго до up app; повтор идемпотентен | поз./сред. | Must | deploy.sh v3 (1.4) + DRY_RUN EXIT=0 (REPORT-fix-12/12g), review-004/005/006 approve |
| CHK-P12-9 | deploy Requirement: Миграции БД — one-shot (порядок матрицы, design §6) | бэкап → build ×4 → миграция → up app → healthy → up search/backup → nginx → смоук | сред. | Must | deploy.sh v3, DRY_RUN-план; боевой прогон — 2.3 (Заказчик) |
| CHK-P12-10 | deploy Requirement: Деплой матрицей сервисов / Scenario: смоук-матрица | health×2, поиск через nginx + X-Service, статика, аватары, 502=0, теги образов = релизные | сред. | Must | deploy.sh шаг смоука (DRY_RUN); боевой — 2.3 |
| CHK-P12-11 | services Requirement: Бэкап тома — sidecar по расписанию (деплой-бэкап той же трассой) | run_backup на копии БД валиден, префиксы вне масок retention | поз./сред. | Must | REPORT-matrix-22 §3 (PASS), review-004-1.2/006 approve |
| CHK-P12-12 | deploy Requirement: Лимиты памяти контейнеров (FR-73 паритет) | search 512m, backup 64m в пределах; свободная память хоста ≥2GB | НФТ/сред. | Must | REPORT-matrix-22 §4 (2749MB PASS; RSS в лимитах) |
| CHK-P12-13 | deploy Requirement: Деплой матрицей сервисов (FR-72: latest запрещен) | теги образов `ekotov-wiki/<name>:<RELEASE_TAG>` | нег. | Must | review-004-1.4/1.5 approve + смоук «теги = релизные» |
| CHK-P12-14 | deploy Requirement: Деплой матрицей сервисов / Scenario: откат тегом (design §8) | пара (app+search) катится одним тегом; точечный фикс одного сервиса | сред. | Must | RUNBOOK §7.6; боевая проверка — 2.3/2.4 |

## Средовые ограничения с компенсацией

| ID | Источник | Проверка | Тип | Приоритет | Покрытие |
|---|---|---|---|---|---|
| CHK-P12-15 | deploy Requirement: Лимиты памяти контейнеров / comp: docker stats | `docker stats --no-stream` на параллели | НФТ/сред. | Must | компенсация: 2.3 прод-параллель (Заказчик) |
| CHK-P12-16 | services Requirement: Бэкап тома — sidecar по расписанию / comp: контейнерный режим | cron-цикл контейнера backup; retention-маски | сред. | Must | компенсация: 2.3 (реестр компенсаций REPORT-matrix-22 §5, review-009 approve) |
| CHK-P12-17 | deploy Requirement: Деплой матрицей сервисов / comp: TLS (NFR-9) | HTTPS паритета NFR-9 | сред. | Must | компенсация: 2.3 |

Известное ограничение среды: BUG-006 (pytest tests/ не собирается одной
командой — pytest_plugins в не-корневом conftest, pytest 8+) — обход
покаталоговым запуском, задокументирован в test-model/bugs и REPORT-regress-21.

## Дефекты спеки

Дефектов спеки в цикле не обнаружено: дельты services/deploy исполнены как написаны
(расхождений, потребовавших правки спеки, ревью 001–009 не зафиксировали;
замечания review относились к коду/стенду/тестам, не к requirements).
