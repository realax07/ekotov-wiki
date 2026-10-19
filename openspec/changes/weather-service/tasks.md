# tasks.md — weather-service (P18 «Погода»)

Флоу 1 (компактный, новый сервис: СА → arch-ревью → dev → QA → деплой).
Дизайн-фаза выполнена: мокап **вариант A** утвержден Заказчиком
2026-10-19 (`design/p18-weather/variant-a.*`) — отдельная волны дизайна
нет (Д-паттерн: утверждение зафиксировано ДО dev). Границы PLAN: БД нет
(кэш-файл в томе, миграций нет), секретов нет (Open-Meteo без ключа,
User-Agent/таймауты в конфиге), один город (Москва). Формат: задача =
наблюдаемый результат + критерий проверки + зона файлов + трассировка;
1 задача = 1 сабагент + независимый ревьюер. Ворота:
`openspec validate weather-service --type change --strict` — change
green на каждом шаге. Порядок: 1 → 2 (ворота arch) → 3 → 4 → 5.

## Волна 1. СА-пакет (эта волна)

- [x] 1.1 [docs] [S] СА: change-пакет weather-service — proposal (ОВ-1…4,
  провайдер, границы), дельта specs/weather-service (14 Requirements /
  21 сценарий), design r1 (топология weather:8381, кэш-файл в томе,
  nginx auth_request, Open-Meteo-параметры, мокап A), tasks.md
  (настоящий). Проверка:
  `openspec validate weather-service --type change --strict` — green.
  Зона: `openspec/changes/weather-service/**`. (design §0–§8)

## Волна 2. Архитектурное ревью (ворота до dev)

- [ ] 2.1 [arch] [S] Ревью пакета по канону (VALID_GATE): топология
  сайдкара weather:8381 против паттерна video:8380, швы nginx↔weather
  (§5), кэш-файл vs БД (обоснование отклонения), контракт API (§6).
  Verdict в change-пакет (review-файл); находки — правки design/spec
  до старта dev. Проверка: verdict зафиксирован, validate green.
  Зона: `openspec/changes/weather-service/**`. (proposal Approach)

## Волна 3. Dev: сервис + фронт + тесты

- [ ] 3.1 [dev] [M] Сервис `services/weather/` — FastAPI :8381:
  `GET /api/weather` (контракт design §6: today + 7 дней + fetched_at +
  stale), `/api/health`, `/api/weather/authcheck` (200/401); сессионный
  middleware (паттерн images/video); Dockerfile по образцу
  services/images (USER 10001, healthcheck urllib, uvicorn 1 воркер) —
  без системных бинарей, без БД. Проверка: локальный прогон — свежий
  кэш отдается без вызова провайдера; аноним — 401.
  Зона: `services/weather/**`. (Req «API погоды…», «Отдельный
  контейнерный сервис…»; design §2)
- [ ] 3.2 [dev] [M] Интеграция Open-Meteo + кэш (design §3–§4): запрос с
  зафиксированными параметрами (55.7539/37.6208, Europe/Moscow,
  forecast_days=7, current/daily-поля), User-Agent из конфига, таймауты
  5 с, ровно один повтор; кэш-файл в томе (атомарная запись tmp+rename,
  TTL 60 мин); деградация: провайдер недоступен → stale-кэш / пустой
  кэш → 503 weather_unavailable; преобразования (мм рт. ст., румбы,
  WMO-коды → ru). Проверка: стабом провайдера — все 4 ветки §4;
  битый JSON не затирает кэш. Зона: `services/weather/**`.
  (Req «Провайдер…», «Кэш 60 минут», «Недоступность…», «Пустой кэш…»,
  «Таймауты…»)
- [ ] 3.3 [dev] [M] Фронт: страница `/weather` по мокапу A — карточка
  «Сегодня» (8 метрик), сетка 7 дней (день/ночь, осадки %, ветер),
  пункт сайдбара «Погода» после «Видео»; состояния загрузка/данные/
  устаревшие/ошибка (без CDN, токены V3). Проверка: design_validator
  против `design/p18-weather/variant-a.*`; все 4 состояния в DOM.
  Зона: `frontend/**`. (Req «Раздел „Погода“…», «Карточка „Сегодня“…»,
  «Прогноз на 7 дней», «Вид интерфейса…»; design §0, §7)
- [ ] 3.4 [dev] [S] Тесты api/web (TC-префикс weather): 401 анониму;
  параметры запроса к провайдеру (стаб); TTL-ветки кэша; stale-флаг;
  503 при пустом кэше + отказе; ровно один повтор; authcheck 200/401.
  Проверка: тесты green, покрыты все сценарии спеки с проверяемым
  поведением. Зона: `tests/**`, `services/weather/**`.
  (вся дельта specs/weather-service)

## Волна 4. QA

- [ ] 4.1 [qa] [M] Доменный smoke + tests/api срез weather: авторизованный
  видит карточку «Сегодня» (8 метрик) и 7 дней; аноним — редирект/401;
  провайдер отрублен → stale-баннер / честная ошибка (пустой кэш);
  TTL: второй запрос из кэша; кэш переживает down/up контейнера.
  Проверка: чек-лист по сценариям спеки, дефекты заведены.
  (дельта specs/weather-service; design §4–§6)
- [ ] 4.2 [qa] [S] NFR-замеры на стенде: mem_limit/healthcheck, RAM в
  лимите, отзывчивость при отказе провайдера (≤ ~11 с), деградация
  nginx 503 при остановленном weather. REPORT до прод-выкатки.
  (Req «Ресурсы и здоровье…», «Отзывчивость…»)

## Волна 5. Деплой (после приемки QA)

- [ ] 5.1 [pm] [S] static_v-бамп фронта (обязанность ПМ до
  диспетчеризации devops — прецедент P11). Проверка: версия поднята в
  конфиге деплоя. (design §7)
- [ ] 5.2 [devops] [M] deploy: сервис `weather` в `deploy/compose.yaml`
  (restart, mem_limit 128m, healthcheck :8381, логи 10m×3, порты не
  публикуются, том `weather-cache`); nginx-локации `/weather`,
  `/api/weather*`, `/_weather_auth`, `@weather_down` (design §5);
  deploy.sh матрица + weather; RUNBOOK-раздел (кэш-файл, том, TTL,
  отказ провайдера — штатная деградация). Проверка: деплой на стенд,
  `openspec validate` green, стек здоров. (design §1, §2, §5)
