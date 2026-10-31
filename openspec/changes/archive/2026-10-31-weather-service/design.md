# Design: weather-service

Версия: r2 (2026-10-19; правки по ревью №1 — review-architecture.md,
находки F1/F2/F3 + O1/O2). r1 (2026-10-19). Источники: PLAN-p18-weather.md (ОВ-1…ОВ-4,
границы: без БД, без секретов, один город), утвержденный мокап
`design/p18-weather/variant-a.html` (вариант A, выбор Заказчика
2026-10-19; B/C — отклонены). Прецеденты: `services/video`
(сайдкар-сервис, сессионный middleware, auth_request, деградация 503,
compose-паттерн), `services/images` (том вне БД).

## §0. Дизайн-фаза (Д-паттерн Р4/Р5; выполнена до dev)

Мокапы P18 подготовлены ui_designer (`design/p18-weather/variant-a/b/c.*`),
**вариант A утвержден Заказчиком 2026-10-19** — сетка карточек: карточка
«сегодня» сверху (крупная температура + описание, 8 метрик в meta-строке),
секция «Прогноз на неделю» — 7 карточек 4-в-ряд (день/ночь, осадки %,
ветер). Пункт «Погода» в sidebar-nav после «Видео», inline-SVG иконка 16px.
Токены V3 «Бумага», без внешних библиотек/CDN (ОГР-8). Dev-задачи идут
строго по мокапу A; после dev — design_validator против `variant-a.*`.

## §1. Целевая топология

```
Браузер (owner/PE) ── https://…:10443 ── nginx [frontend]
   ├── ^~ /api/weather/        → weather:8381 (API)
   ├── = /api/weather          → weather:8381
   └── остальное               → как сейчас (app, search, images, video, …)

Страница /weather nginx-локации НЕ требует — рендерится ядром app
(Jinja-шелл из base.html, active_page='weather'; паритет /video, §7):
маршрутизация страницы идет общим правилом ядра, аноним-редирект дает
сессионный middleware ядра, static_v работает из коробки.

weather:8381  — FastAPI (uvicorn 1 воркер): GET /api/weather (JSON:
               today + 7 дней + fetched_at + stale), /api/health;
               БД НЕТ; кэш-файл в томе
```

- Наружу открыт только nginx :10443 (FR-65-преемственность) — `weather`
  порты НЕ публикует (паритет app/search/images/video).
- При отказе `weather` nginx отвечает на `/api/weather*` быстрым
  управляемым 503 (JSON + Retry-After, паттерн `@video_down` →
  `@weather_down`); остальные маршруты работают.
- Порядок сервисов в compose: `depends_on: [app]` не требуется для схемы
  (БД нет), но сохраняется для единообразия стека/сессий.

## §2. Контейнер: services/weather (по образцу services/video, упрощенный)

`services/weather/Dockerfile` — копия схемы `services/images`/`video`
(python:3.12-slim, deps слоями с пинами fastapi/uvicorn, код в
`/srv/app`, USER 10001, EXPOSE 8381, healthcheck через urllib без curl,
CMD uvicorn 1 воркер). Отличия от video:

1. **Никаких системных бинарей** (ffmpeg не нужен) — образ тоньше.
2. **БД НЕТ**: RW-маунт только один — том `weather-cache:/cache`
   (env `EKOTOV_WEATHER_CACHE_PATH`, дефолт `/cache/weather.json`;
   маунтпоинт `/cache` — верхнеуровневый путь вне `/data`, где ro-маунт БД).
   Тома данных, томов БД, миграций у пакета нет (граница PLAN).

compose-сервис `weather` в `deploy/compose.yaml` (паритет video):
`restart: unless-stopped`, `mem_limit: 128m` (сервис stateless-легкий —
один HTTP-клиент + кэш-файл; факт — замер NFR на стенде), healthcheck
тот же шаблон (:8381), ротация логов json-file 10m×3, порты не
публикуются. Резерв хосту ≥ 2 GB — проверка в задаче деплоя.

## §3. Интеграция Open-Meteo

**Запрос (зафиксирован, город один — Москва):**

```
GET https://api.open-meteo.com/v1/forecast
  ?latitude=55.7539&longitude=37.6208
  &timezone=Europe/Moscow&forecast_days=7
  &wind_speed_unit=ms
  &current=temperature_2m,apparent_temperature,
           weather_code,relative_humidity_2m,surface_pressure,
           wind_speed_10m,wind_direction_10m
  &daily=weather_code,temperature_2m_max,temperature_2m_min,
         precipitation_probability_max,wind_speed_10m_max,wind_direction_10m_dominant
```

- Координаты/город в конфиг и API НЕ выносятся (граница PLAN) —
  константы кода; правка = только код-изменение.
- **Таймауты:** connect 5 с / read 5 с (httpx, единый клиент); истечение
  = ошибка провайдера. **Повтор:** ровно один автоматический (пауза 1 с);
  после второй неудачи — деградация (§4). Суммарный потолок ~11 с.
- **User-Agent** — в конфиге сервиса (env `EKOTOV_WEATHER_USER_AGENT`),
  не дефолт httpx; требование вежливости публичного API.
- **Валидация ответа:** проверяется схема-минимум (current + daily
  массивы нужной длины); невалидный/неполный JSON = ошибка провайдера,
  кэш НЕ затирается (spec «Битый ответ…»).
- **Преобразования:** ветер приходит из провайдера УЖЕ в м/с — в запрос
  включен `wind_speed_unit=ms` (у Open-Meteo дефолт — км/ч; конверсия
  в коде не нужна, ревью №1 F2); давление гПа → мм рт. ст.
  (×0.750062, округление до целого); направление ветра в градусах →
  русские румбы (С/СВ/В/ЮВ/Ю/ЮЗ/З/СЗ); WMO weather_code → русские
  описания и иконки (статическая таблица в коде). Карточка «Сегодня»
  берет max/min из daily[0] — согласованность с прогнозом; **осадки
  карточки «Сегодня» — вероятность (%) из `daily[0].
  precipitation_probability_max`** (в `current` поле `precipitation`
  НЕ запрашивается — это мм осадков, карточкой не используется;
  ревью №1 F2).

## §4. Кэш: файл в томе weather-cache, TTL 60 мин

- Файл `/cache/weather.json` (том `weather-cache`, named volume —
  переживает пересоздание): полезная нагрузка ответа + `fetched_at`.
- **Атомарная запись:** tmp-файл + `os.replace` — читатели никогда не
  видят полуфайл.
- **Логика чтения:**
  1. кэш свежий (< 60 мин) → отдать из кэша, провайдер не вызывается;
  2. кэш истек → запрос провайдеру (§3); успех — обновить кэш,
     `stale: false`;
  3. провайдер недоступен/невалиден → отдать устаревший кэш с
     `stale: true` (файл не трогается);
  4. кэша нет И провайдер недоступен → 503 JSON
     `{"error": "weather_unavailable"}` (UI — честное сообщение,
     кэш-файл не создается).
- Кэш общий для всех пользователей (не персональный) — состояние только
  в файле, в памяти ничего авторитетного. Обновление кэша при истекшем
  TTL — под `asyncio.Lock`: два одновременных запроса инициируют одно
  обновление (второй дожидается и получает свежий результат) —
  двойных вызовов провайдера нет (ревью №1 O1).
- Невозможность ЗАПИСАТЬ кэш (том переполнен/ro) ответ не меняет:
  запись сбоит — фиксируется в логе, пользователю отдается полученное
  от провайдера как при успехе (кэш-файл остается прежним) —
  (ревью №1 O2).
- «Мягкое» обновление: истекший кэш НЕ блокирует ответ — при отказе
  провайдера пользователь всегда получает максимум доступного (spec
  «Недоступность провайдера…»).

## §5. nginx: только API-семейство /api/weather* (прод-паттерн видео)

Страница `/weather` рендерится ядром (§7) — nginx-локации для нее НЕТ
и auth_request не нужен вовсе (ревью №1 F1/F3). nginx обслуживает
только API-семейство; как на API-локациях video (`= /api/videos`,
`^~ /api/videos/` в проде), auth_request НЕ применяется — сессию
проверяет сессионный middleware сервиса (401 JSON), без двойной
валидации subrequest'ом:

```
location = /api/weather {
    include snippets/weather-proxy.inc;   # паттерн videos-proxy.inc
}
location ^~ /api/weather/ {
    include snippets/weather-proxy.inc;
}
```

`snippets/weather-proxy.inc` (по образцу `videos-proxy.inc`, уроки
прод-инсов видео перенесены):

```
set $upstream_weather http://weather:8381;
# Переменная + resolver server-блока (127.0.0.11 valid=10s, паритет
# video/search/images): proxy_pass статическим именем резолвится один
# раз на старте — без переменной nginx не стартует без контейнера
# weather и держит мертвый IP после пересоздания; с переменной —
# переразрешение на запросах, старт nginx без weather безопасен
# (анти-stale-DNS).
proxy_next_upstream error timeout;
# intercept_errors ВЫКЛЮЧЕН (отличие от video, ревью №1 F1-в): сервис
# СА отвечает управляемым 503 weather_unavailable (spec «Пустой кэш…»)
# — он должен дойти до клиента без подмены. nginx-ский 502 (соединение
# отвергнуто — контейнер остановлен) ошибкой error_page ловится и без
# intercept: error_page генерируется самим nginx, не upstream'ом.
proxy_intercept_errors off;
error_page 502 504 = @weather_down;       # быстрый управляемый 503 JSON+Retry-After
proxy_http_version 1.1;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_pass $upstream_weather;
```

Контракт шва nginx↔weather: authcheck-эндпоинта у сервиса НЕТ —
auth_request в пакете не используется нигде (по прод-паттерну видео
он был бы нужен только там, где nginx сам отдает контент; с рендером
страницы ядром таких мест нет). Сессионный middleware сервиса —
паритет images/video (только чтение своей сессии, без права писать в
sessions); @weather_down — по паттерну @videos_down (JSON +
Retry-After).

## §6. API-контракт (шов фронт↔weather)

`GET /api/weather` → 200 JSON:

```json
{
  "fetched_at": "2026-10-19T12:00:00+03:00",
  "stale": false,
  "today": {
    "temperature": 4, "description": "Пасмурно, дождь", "code": 63,
    "apparent": 1, "temp_max": 5, "temp_min": 1,
    "precipitation": 80, "wind": {"dir": "ЮЗ", "speed": 5},
    "humidity": 87, "pressure_mmhg": 738
  },
  "days": [
    {"date": "2026-10-26", "code": 63, "description": "Дождь",
     "temp_max": 4, "temp_min": 1, "precipitation": 80,
     "wind": {"dir": "ЮЗ", "speed": 5}}
  ]
}
```

- `days` — ровно 7 элементов, включая сегодня (days[0] ↔ today).
- `today.precipitation` — **вероятность осадков (%)**, берется из
  `daily[0].precipitation_probability_max` (поле `current.precipitation`
  провайдера — мм осадков — в запрос не входит; ревью №1 F2). `speed` —
  м/с (запрашивается `wind_speed_unit=ms`).
- Ошибки: 401 (аноним — от сессионного middleware сервиса), 503
  `weather_unavailable` (нет кэша + провайдер недоступен — ответ
  сервиса проходит через nginx без подмены, intercept off), 503 от
  nginx при down контейнера (@weather_down).
- `/api/health` — 200 без бизнес-логики (шаблон healthcheck video).

## §7. Фронт: страница /weather — Jinja-рендер ядра (паритет /video)

- Страница рендерится **ядром app** (ревью №1 F3, принят вариант
  архитектора): Jinja-шаблон в `frontend/templates`, расширяющий
  `base.html` (каркас сайдбара наследуется — второй копии шаблона нет,
  синхронизация не нужна), `active_page='weather'` (активное состояние
  пункта сайдбара работает из base.html — ревью №1 O4), статика — через
  `static_v` (Jinja-глобал ядра — кеш-бастинг из коробки, релизный
  бамп 5.1 инвалидирует страницу как и весь стек). Вид — по мокапу A
  (`variant-a.html`; токены V3 «Бумага», inline SVG-иконки, без CDN);
  пункт «Погода» в sidebar-nav после «Видео» (правка base.html в ядре).
- Роут + middleware: аноним получает редирект на `/login` штатным
  сессионным middleware ядра (паритет /video — бесплатно, без
  auth_request/nginx).
- Загрузка данных: fetch `/api/weather` (cookie сессии — same-origin);
  состояния: **загрузка** (индикатор), **данные** (карточки),
  **устаревшие** (баннер «данные устарели, обновлено …» + карточки),
  **ошибка** (сообщение «не удалось получить данные погоды» + кнопка
  «Повторить» — честная ошибка, без заглушек). Никакого JS-фреймворка.

## §8. Альтернативы (отклоненные)

| Альтернатива | Почему нет |
|---|---|
| Кэш в БД ядра / таблица weather_cache | граница PLAN — без БД; миграции и RW-профиль не нужны; файл-атомарной записи достаточно для одного ключа с TTL |
| Кэш только в памяти процесса | теряется при пересоздании контейнера — первый запрос после рестарта бьет в провайдера; том дешевле |
| Выбор города параметром API/конфига | граница PLAN — один город; параметризация — продуктовое решение на будущее |
| Проксирование Open-Meteo напрямую из фронтенда | ломает ОВ-1 (аноним получил бы данные), CORS, таймауты/кэш не контролируются — данные только через weather:8381 |
| Другой провайдер (Яндекс/OpenWeather) | требует ключ/секрет — граница PLAN (Open-Meteo без ключа, решение 2026-10-19) |
