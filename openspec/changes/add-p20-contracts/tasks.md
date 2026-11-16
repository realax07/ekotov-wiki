# tasks.md — add-p20-contracts (P20 «Сервисные контракты»)

Формат: волны по ОВ-4 (Д-16 с заменой: search → video → images → weather),
гейт дрейфа — последняя волна (ТЗ §10.3). Каждая задача — проверяемый шов с
файлами, FR-трассировкой и механическим критерием приемки (точная команда/
факт). Оценки: [S] — один присест, [M] — 2+. Реализуется по волнам
dev-этапа; зоны задач названы в тексте, за границы не выходить.

## Волна 1. Эталон: контракт search (FR-133, ОГР-29) — [S]

- [ ] 1.1 Подтвердить заморозку search на HEAD: прогон
  `python scripts/export_openapi_search.py` из корня репо, затем
  `git diff --exit-code -- contracts/openapi-search.json`. Проверка:
  дифф пуст; `pytest tests/api/test_openapi_search_service.py` и
  `pytest services/search/tests` зеленые (TC-openapi-201…210).
  Файлы: только contracts/openapi-search.json может перезаписаться
  скриптом (и не перезаписывается при пустом диффе). FR-133.
- [ ] 1.2 [УСЛОВНАЯ — только если 1.1 дал дифф ≠ пусто или формат файла
  расходится с единым стандартом пакета] Привести search-контракт к
  единому формату: перезапуск export_openapi_search.py (формат
  json.dumps sort_keys/indent=2 + `\n`), при расхождении структуры —
  правка СКРИПТА экспорта (не файла и не кода сервиса) до
  воспроизводимого результата. Проверка: повторный экспорт →
  `git diff --exit-code -- contracts/openapi-search.json` пуст;
  TC-openapi-201…210 зеленые; поведение сервиса не менялось
  (`git diff --stat -- services/search/app` пуст). FR-133, ОГР-29.
  Если 1.1 зелен — задача закрывается формулировкой «не требовалась,
  экспорт идемпотентен» с фактом команды из 1.1.

## Волна 2. Контракт video (FR-135, FR-137) — [S]

- [ ] 2.1 Скрипт `scripts/export_openapi_video.py` по образцу
  export_openapi_search.py (design §1): старт
  `services/video/app/main.py` на свободном порту с tmp-томом, вход
  seed-юзером, контроль `anon /openapi.json → 401`, запись
  `contracts/openapi-video.json`, печать путей, ассерт ожидаемого
  множества (15 маршрутов, включая PATCH rename и
  `GET /api/videos/authcheck`). Проверка: скрипт завершается 0;
  повторный запуск → `git diff --exit-code` пуст.
- [ ] 2.2 Заморозить контракт: запустить скрипт, в спеке — схемы
  200/ошибок (401/404/409/422) и `components.schemas.Error`
  `{"error": …}` с `$ref` на error-ответы (ОВ-7, design §2); пометка
  «internal: потребитель — nginx auth_request, не браузер» в
  description authcheck (аннотирование — в экспорт-скрипте, не руками).
  Якорь `services/video/openapi.yaml` (10–14 строк, образец
  services/search/openapi.yaml). Проверка: `python -c "import json;
  d=json.load(open('contracts/openapi-video.json'));
  assert d['openapi'].startswith('3')"`;
  `grep -c internal contracts/openapi-video.json` ≥ 1; якорь содержит
  все 15 путей. FR-135, FR-137, ОВ-2, ОВ-7.
- [ ] 2.3 Контрактный тест путей в `services/video/tests`
  (тест-файл по образцу существующих path-ассертов): множество путей
  замороженной спеки = живому `/openapi.json` под сессией, 1:1.
  Проверка: `pytest services/video/tests -k contract` зеленый.
  FR-135, FR-137.

## Волна 3. Контракт images (FR-134, FR-137) — [S]

- [ ] 3.1 Скрипт `scripts/export_openapi_images.py` (design §1,
  tmp-том картинок + БД, ассерт 11 маршрутов + `/api/health`).
  Проверка: как 2.1 (повторный экспорт = пустой дифф).
- [ ] 3.2 Заморозить `contracts/openapi-images.json` (схемы 200/ошибок
  401/404/422/409 реакций, Error+$ref — ОВ-7) + якорь
  `services/images/openapi.yaml`. Проверка: как 2.2; в спеке 409
  реакций присутствует (`grep -c 409 contracts/openapi-images.json` ≥ 1).
  FR-134, ОВ-2, ОВ-7.
- [ ] 3.3 Контрактный тест путей в `services/images/tests`
  (спека = живой `/openapi.json` под сессией). Проверка:
  `pytest services/images/tests -k contract` зеленый. FR-134.

## Волна 4. Контракт weather (FR-136, FR-137) — [S]

- [ ] 4.1 Скрипт `scripts/export_openapi_weather.py` (design §1:
  tmpdir кэш-файла, провайдер не вызывается, ассерт
  `/api/weather` + `/api/health`). Проверка: как 2.1.
- [ ] 4.2 Заморозить `contracts/openapi-weather.json` (схема карточки
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

- [ ] 7.1 Сузить IR-01 в `scripts/impact_rules.json`:
  `when[].path` → `^services/[^/]+/openapi\.json$` (yaml-якоря
  перестают триггерить ложный DENY — design §5). Проверка:
  `python3 -c "import json; json.load(open('scripts/impact_rules.json'))"`
  без ошибок; прогон `python3 scripts/pr_validate.py . --id test` на
  чистом HEAD без DENY. FR-140.
- [ ] 7.2 Добавить правила IR-08…IR-12 (таблица design §5): when по
  `services/<svc>/app/**` и `backend/app/**`, `content_when` по
  добавленной строке декоратора маршрута
  (`\+\s*@(router|app)\.(get|post|put|patch|delete|api_route)`),
  require — соответствующий `contracts/openapi-*.json` с label+hint
  «перегенерируй контракт». Только JSON, код ворот не меняется.
  Проверка: JSON читается; `python3 scripts/pr_validate.py . --id test`
  на чистом HEAD без DENY (content_when не срабатывает на пустом диффе).
  FR-140, ОВ-5, ОВ-6.
- [ ] 7.3 Негативный тест гейта (tests конвейера, рядом с существующими
  прогонами pr_validate; маркер TC-FLOW-NNN в docstring): фиктивный
  дифф «новый маршрут в services/video/app без контракта» через
  `PR_CHANGED_FILES` + `PR_BODY`-конвенцию → ожидаемый DENY с id IR-08;
  тот же дифф + изменение contracts/openapi-video.json → green;
  static_v-бамп (`backend/app/pages.py` без декораторов) → без DENY.
  Проверка: `pytest tests -k impact` (или существующий лок-файл тестов
  ворот) зеленый; три кейса в ассертах. FR-140, ОВ-6.
- [ ] 7.4 Включение гейта и итоговая сверка: все 4 контракта заморожены
  и зеленые (волны 1–4), `openspec validate --all --strict` зелен,
  полный регресс-сьют (tests/api + services/*) зелен. Проверка:
  `git diff --exit-code` после повторного прогона всех экспорт-скриптов
  (5 файлов контрактов) — пусто; CI на PR зелен, длительность шага
  ворот ≤ 30 c в логе (NFR-46). FR-140, ОГР-31, NFR-46.
