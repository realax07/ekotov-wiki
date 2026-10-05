# Impact-анализ: change add-microservices-full

> Дата: 2026-10-05 | Режим: ПМ-сводка по фактам QA-цикла (полный регресс 2.1
> прогнан и принят review-007/008; стенд-матрица 2.2 принята review-009).
> Вход: дельты `openspec/changes/add-microservices-full/specs/` (2 файла:
> deploy MODIFIED, services ADDED), REPORT-regress-21.md (финал: api
> 201p/9s/2xf/0f; web 165p/0f/1s), REPORT-matrix-22.md, review-001…009.

## Характер дельты

- **MODIFIED — 1 шт.:** deploy — миграции выполняются one-shot из образа ядра
  ДО подъема app; порядок матрицы: бэкап → build всех → миграция ядра → up app
  → healthy → up search/backup → healthy → up nginx → healthy → смоук-матрица.
- **ADDED — 1 шт.:** services (новая capability) — поиск и подсказки
  обслуживаются отдельным контейнером `search`; ядро не содержит этих
  маршрутов; read-only профиль данных; nginx-маршрутизация `/api/search*`,
  `/api/suggestions*` на search, 503-деградация при недоступном search;
  backup-sidecar; релизный бэкап в деплое.
- **REMOVED — нет.**

## Резюме вердиктов

**keep — весь регресс (201 api + 166 web = 367 тестов), revalidate — нет
отдельных точек, retire — нет.** Обоснование: переезд search-маршрутов в
сервис НЕ меняет клиентское поведение (URL те же, паритет контракта
зафиксирован `contracts/openapi-search.json` и гейтом «экспорт = файл»
TC-openapi-201/202), поэтому все существующие кейсы остаются актуальными
и гоняются против маршрутизированного стенда. Подтверждено прогоном:
api 201 passed/0 failed, web 165 passed/0 failed на nginx:18443 →
app:8080 + search:8378.

## Покрытие новой capability (services)

- TC-openapi-201 «Экспорт = файл» — контракт search заморожен и валиден
  (tests/api/test_openapi_search_service.py, задача 1.5, xfail снят).
- TC-openapi-202 «Ядро без маршрутов поиска» — main.py не тянет
  search/suggestions-роутеры (задача 1.5).
- Юниты search-сервиса: 12 passed (services/search/tests).
- Смоук маршрутизации: search-пути через nginx → `X-Service: search`
  (REPORT-regress-21 §5, REPORT-matrix-22 §2).
- 503-деградация: stop search → управляемый 503 JSON + Retry-After ~1мс,
  restart → восстановление ≤0.5с; смоук записи при упавшем search (201/200)
  — изоляция сервисов (REPORT-matrix-22 §2, review-009 approve).
- Деплой-бэкап без sidecar: трасса run_backup на копии БД валидна
  (REPORT-matrix-22 §3).

## Deploy MODIFIED — влияние на деплой-кейсы

Кейсы add-containerization (CHK-R11-1…5, деплой-проверки) сохраняют силу:
матрица 1.4 (deploy.sh v3) расширяет схему app+nginx до app+frontend+search+
backup, смоук-матрица расширена (health×2, поиск через nginx, 502=0, теги).
Изменение порядка (миграция ядра строго ДО up) покрывается сценарием дельты и
DRY_RUN-прогоном (REPORT-fix-12/12g). docker-зависимые проверки (stats,
sidecar-ретеншн, TLS) — компенсация на 2.3/2.4 прод-параллель.

## Кандидаты на пересмотр — нет

Правки тестов цикла (изоляция test_search_r4_ui, скоупы локаторов board/
view-modal, review-008) — усиление ассертов без изменения семантики проверок;
traceability TC-search-r4-ui-002/004, TC-view-109, TC-UI-007 сохранена.
BUG-006 (pytest tests/ не собирается целиком из-за pytest_plugins в
не-корневом conftest, pytest 8+) — задокументирован в test-model/bugs,
обход покаталоговым запуском, на вердикты не влияет.
