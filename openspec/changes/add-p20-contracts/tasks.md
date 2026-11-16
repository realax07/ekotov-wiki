# tasks.md — add-p20-contracts (P20 «Сервисные контракты»)

Формат: волна 0 — подготовка гейта (сужения IR-01/IR-07, arch-review-001
Д-Б1/Д-Б2), затем волны по ОВ-4 (Д-16 с заменой: search → video → images
→ weather), гейт дрейфа — последняя волна (ТЗ §10.3). Каждая задача —
проверяемый шов с файлами, FR-трассировкой и механическим критерием
приемки (точная команда/факт). Оценки: [S] — один присест, [M] — 2+.
Реализуется по волнам dev-этапа; зоны задач названы в тексте, за границы
не выходить.

## Волна 0. Подготовка: сужение IR-01 и IR-07 (FR-140, ОВ-5/ОВ-6) — [S]

- [x] 0.1 Сузить IR-01 в `scripts/impact_rules.json`:
  `when[].path` → `^services/[^/]+/openapi\.json$` (yaml-якоря
  `services/<svc>/openapi.yaml` перестают триггерить ложный DENY —
  design §5). Проверка:
  `python3 -c "import json; json.load(open('scripts/impact_rules.json'))"`
  без ошибок; симуляция на синтетическом диффе «новый
  services/video/openapi.yaml» через `python3 scripts/pr_validate.py .`
  (PR_CHANGED_FILES-конвенция) — DENY нет; прогон на чистом HEAD без
  DENY. FR-140.
- [x] 0.2 Сузить IR-07 там же: `when[].path` →
  `^contracts/openapi\.json$` (новые сервисные контракты
  `contracts/openapi-<svc>.json` и будущие ОГР-31-PR сервисов правило
  не триггерит — design §5). Проверка: JSON читается; симуляция
  «новый contracts/openapi-video.json» — DENY нет; симуляция
  «services/video/app/videos.py + contracts/openapi-video.json» (ОГР-31)
  — DENY нет; прогон на чистом HEAD без DENY. FR-140.

Сами сужения гейт НЕ включают: новые правила IR-08…IR-12 — волна 7
(ОВ-4/ТЗ §10.3). До волны 0 ни один якорь/контракт не замораживается.

## Волна 1. Эталон: контракт search с полным охватом (FR-133, FR-137, ОГР-29) — [M]

- [x] 1.1 Привести search-контракт к живой схеме сервиса 1:1: правка
  `scripts/export_openapi_search.py` — упразднение фильтрации по
  префиксам (полный экспорт живого `/openapi.json`: 5 path-items,
  включая `/api/health`; замороженный контракт сейчас содержит 4 пути),
  переэкспорт `contracts/openapi-search.json`, обновление якоря
  `services/search/openapi.yaml` (точный список путей контракта).
  Проверка: множество путей контракта = живому `/openapi.json` 1:1
  (5 path-items, `/api/health` присутствует); повторный экспорт →
  `git diff --exit-code -- contracts/openapi-search.json` пуст;
  `git diff --stat -- services/search/app` пуст (код сервиса не
  меняется — ОГР-29). FR-133, FR-137.
- [x] 1.2 Синхронные правки path-ассертов TC-openapi-201…210
  (tests/api/test_openapi_search_service.py, services/search/tests):
  только множества путей («ровно 4 пути» → 5 путей с `/api/health` —
  включая TC-openapi-201/205); ассерты поведения не трогаются
  (оговорка к NFR-45 — правка ассертов множеств путей синхронно с
  переэкспортом, behavior-neutral). Проверка:
  `pytest tests/api/test_openapi_search_service.py` и
  `pytest services/search/tests` зеленые (TC-openapi-201…210). FR-133,
  FR-137, NFR-45.

## Волна 2. Контракт video (FR-135, FR-137) — [S]

- [x] 2.1 Скрипт `scripts/export_openapi_video.py` по образцу
  export_openapi_search.py (design §1): старт
  `services/video/app/main.py` на свободном порту с tmp-томом, вход
  seed-юзером, контроль `anon /openapi.json → 401`, запись
  `contracts/openapi-video.json`, печать путей, ассерт ожидаемого
  множества path-items живого `/openapi.json` (14 операций:
  `videos.py` 7 + `social.py` 6 + `/api/health`; включая PATCH rename
  и `GET /api/videos/authcheck`) — design §1, Д-З1. Проверка: скрипт
  завершается 0; повторный запуск → `git diff --exit-code` пуст.
- [x] 2.2 Заморозить контракт: запустить скрипт, в спеке — схемы
  200/ошибок (401/404/409/422) и `components.schemas.Error`
  `{"error": …}` с `$ref` на error-ответы (ОВ-7, design §2); пометка
  «internal: потребитель — nginx auth_request, не браузер» в
  description authcheck (аннотирование — в экспорт-скрипте, не руками).
  Якорь `services/video/openapi.yaml` (10–14 строк, образец
  services/search/openapi.yaml). Проверка: `python -c "import json;
  d=json.load(open('contracts/openapi-video.json'));
  assert d['openapi'].startswith('3')"`;
  `grep -c internal contracts/openapi-video.json` ≥ 1; якорь содержит
  все path-items контракта (сверка с живым `/openapi.json` — design §1).
  FR-135, FR-137, ОВ-2, ОВ-7.
- [ ] 2.3 Контрактный тест путей в `services/video/tests`
  (тест-файл по образцу существующих path-ассертов): множество путей
  замороженной спеки = живому `/openapi.json` под сессией, 1:1.
  Проверка: `pytest services/video/tests -k contract` зеленый.
  FR-135, FR-137.

## Волна 3. Контракт images (FR-134, FR-137) — [S]

- [x] 3.1 Скрипт `scripts/export_openapi_images.py` (design §1,
  tmp-том картинок + БД, ассерт множества path-items живого
  `/openapi.json` — 11 операций: `gallery.py` 10 + `/api/health`).
  Проверка: как 2.1 (повторный экспорт = пустой дифф).
- [x] 3.2 Заморозить `contracts/openapi-images.json` (схемы 200/ошибок
  401/404/422/409 реакций, Error+$ref — ОВ-7) + якорь
  `services/images/openapi.yaml`. Проверка: как 2.2; пути = живому
  /openapi.json 1:1. Критерий «grep -c 409 ≥ 1» снят решением ПМ
  (2026-11-16): 409 у реакций images НЕ существует — PUT идемпотентны
  (BUG-026, PR #266), эскалация исполнителя подтверждена; в спеке
  ассертится ОТСУТСТВИЕ 409-ответов, 409 упоминается только в
  поясняющих description. [критерий скорректирован; закрытие — после code_review волн 0-4]
  FR-134, ОВ-2, ОВ-7.
- [ ] 3.3 Контрактный тест путей в `services/images/tests`
  (спека = живой `/openapi.json` под сессией). Проверка:
  `pytest services/images/tests -k contract` зеленый. FR-134.

## Волна 4. Контракт weather (FR-136, FR-137) — [S]

- [x] 4.1 Скрипт `scripts/export_openapi_weather.py` (design §1:
  tmpdir кэш-файла, провайдер не вызывается, ассерт
  `/api/weather` + `/api/health`). Проверка: как 2.1.
- [x] 4.2 Заморозить `contracts/openapi-weather.json` (схема карточки
  «Сегодня» + 7 дней, null-метрики «—», Error+$ref) + якорь
  `services/weather/openapi.yaml`. Проверка: как 2.2; в paths спеки
  нет упоминаний Open-Meteo. FR-136, Д-17, ОВ-7.
- [ ] 4.3 Контрактный тест путей в `services/weather/tests`
  (существующий TC-weather-003 401-паттерн сохраняется). Проверка:
  `pytest services/weather/tests -k contract` зеленый. FR-136.

## Волна 5. Схемная валидация сервисных тестов (FR-138, ОВ-1б, NFR-46) — [M]

- [ ] 5.1 Зависимость `jsonschema` (draft-07+) в test-deps всех 4
  сервисов (requirements тестов; рантайм образов не меняется).
  Проверка: `python -c "import jsonschema; print(jsonschema.Draft7Validator)"`
  в окружении сервисных тестов; `pip freeze | grep -i jsonschema`
  зафиксирован там, где фиксируются deps. FR-138.
- [ ] 5.2 Helper `services/<svc>/tests/contract_helpers.py` × 4 (или
  копия одного файла — дизайн §3): загрузка
  `contracts/openapi-<svc>.json`, Draft7Validator + резолвер `$ref` на
  корень файла (строится один раз на модуль), функция
  `validate_response(path, method, status, payload)`; отсутствие
  маршрута/статуса в спеке = AssertionError. Проверка: юнит-тест
  helper'а на позитивном и негативном payload. FR-138.
- [ ] 5.3 Схемные проверки happy-path 200 каждого маршрута + типовая
  ошибка (401 без сессии и/или 422) в существующие тест-файлы 4
  сервисов — ДОБАВЛЕНИЕ проверок, существующие ассерты не правятся
  (NFR-45). Проверка: `pytest services/search/tests services/video/tests
  services/images/tests services/weather/tests` зеленый;
  `grep -rc validate_response services/*/tests` ≥ 1 на сервис.
  FR-138, NFR-45.
- [ ] 5.4 Drift-ловушка: в тесте одного сервиса (например images)
  негативный кейс — payload с чужим полем против спеки падает с
  сообщением «маршрут + несовпавшее поле». Проверка: инвертированный
  тест (pytest.raises) зеленый. FR-138.
- [ ] 5.5 Замер замедления: время `pytest services/*/tests` до волны и
  после — прирост ≤ 20%. Проверка: два замера (`time pytest ...`)
  записаны в описании задачи PR, прирост ≤ 20%. NFR-46.

## Волна 6. Карта и nginx-тест (FR-139, ОГР-30, Д-17, ОВ-9; FR-141, ОВ-8) — [S]

- [ ] 6.1 Раздел «Контракты и зависимости» в `architecture/map.md`
  (структура — design §4): nginx-маршруты (пары «= точный + ^~ префикс»,
  порты 8377–8381), потребители (браузерные JS; nginx authcheck → video
  как единственный сервер-сервер-стык), деградации `@*_down` → 503 +
  `Retry-After: 5`, файлы контрактов + якоря + экспорт-скрипты,
  внешние зависимости (Open-Meteo: таймауты 5с×2, кэш 60м — Д-17; games
  — standalone, вне скоупа — ОВ-9), правило «сервер-сервер вызовов нет»
  (ОГР-30). Проверка: карта содержит имена всех 4 контрактов и
  `Retry-After`; перечисленные в карте файлы существуют:
  `for f in contracts/openapi-{search,video,images,weather}.json
  services/{search,video,images,weather}/openapi.yaml; do test -f $f;
  done` — exit 0. FR-139, ОГР-30, Д-17, ОВ-9.
- [ ] 6.2 nginx-тест `tests/api/test_nginx_routes_contract.py` (design
  §6): парсинг location-строк `services/frontend/nginx/ekotov-wiki.conf`,
  ассерт ровно ожидаемых семейств per service + named-локации
  деградаций + `/_video_auth`; маркер TC-API-NNN внутри docstring
  литерала функции (правило 6 flow_check). Проверка:
  `pytest tests/api/test_nginx_routes_contract.py` зеленый на HEAD;
  ручной негатив — временное переименование `^~ /api/weather/` в рабочей
  копии → тест красный (возврат файла). FR-141, ОВ-8.

## Волна 7. Гейт дрейфа, последняя волна (FR-140, ОВ-5/ОВ-6, ОГР-31, NFR-46) — [M]

- [ ] 7.1 Добавить правила IR-08…IR-12 (таблица design §5): when по
  `services/<svc>/app/**` и `backend/app/**`, `content_when` — список
  пар `{path, regex}` (форма — по образцам IR-06/IR-07, Н-1):
  path — `services/<svc>/app/**` / `backend/app/**`, regex —
  добавленная строка декоратора маршрута
  (`\+\s*@(router|app)\.(get|post|put|patch|delete|api_route)`),
  require — соответствующий `contracts/openapi-*.json` с label+hint
  «перегенерируй контракт». Только JSON, код ворот не меняется.
  Проверка: JSON читается; `python3 scripts/pr_validate.py . --id test`
  на чистом HEAD без DENY (content_when не срабатывает на пустом диффе).
  FR-140, ОВ-5, ОВ-6.
- [ ] 7.2 Негативный тест гейта (tests конвейера, рядом с существующими
  прогонами pr_validate; маркер TC-FLOW-NNN в docstring): фиктивный
  дифф «новый маршрут в services/video/app без контракта» через
  `PR_CHANGED_FILES` + `PR_BODY`-конвенцию → ожидаемый DENY с id IR-08;
  тот же дифф + изменение contracts/openapi-video.json → green
  (после сужения IR-07, Д-Б1 — кейс валиден); static_v-бамп
  (`backend/app/pages.py` без декораторов) → без DENY; дифф
  «новый contracts/openapi-video.json» без ядерного контракта → без
  DENY (IR-07 сужен, регресс-проверка Д-Б1). Проверка:
  `pytest tests -k impact` (или существующий лок-файл тестов
  ворот) зеленый; четыре кейса в ассертах. FR-140, ОВ-6.
- [ ] 7.3 Включение гейта и итоговая сверка: все 4 контракта заморожены
  и зеленые (волны 1–4), `openspec validate --all --strict` зелен,
  полный регресс-сьют (tests/api + services/*) зелен. Проверка:
  `git diff --exit-code` после повторного прогона всех экспорт-скриптов
  (5 файлов контрактов) — пусто; CI на PR зелен, длительность шага
  ворот ≤ 30 c в логе (NFR-46). FR-140, ОГР-31, NFR-46.
