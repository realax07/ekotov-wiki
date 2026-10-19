# Design: weather-service

Версия: r1 (2026-10-19). Источники: PLAN-p18-weather.md (ОВ-1…ОВ-4,
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
   ├── = /weather              → статика фронта (страница по мокапу A,
   │                             auth_request §5; паритет /video-страниц)
   ├── ^~ /api/weather/        → weather:8381 (API: weather/health/authcheck)
   ├── = /api/weather          → weather:8381
   └── остальное               → как сейчас (app, search, images, video, …)

weather:8381  — FastAPI (uvicorn 1 воркер): GET /api/weather (JSON:
               today + 7 дней + fetched_at + stale), /api/health,
               /api/weather/authcheck; БД НЕТ; кэш-файл в томе
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
2. **БД НЕТ**: RW-маунт только один — том `weather-cache:/data/cache`
   (env `EKOTOV_WEATHER_CACHE_PATH`, дефолт `/data/cache/weather.json`).
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
  &current=temperature_2m,apparent_temperature,precipitation,
           weather_code,relative_humidity_2m,surface_pressure,
           wind_speed_10m,wind_direction_10m
  &daily=weather_code,temperature_2m_max,temperature_2m_min,
         precipitation_probability_max,wind_speed_10m_max,wind_direction_10m_max
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
- **Преобразования:** давление гПа → мм рт. ст. (×0.750062, округление
  до целого); направление ветра в градусах → русские румбы
  (С/СВ/В/ЮВ/Ю/ЮЗ/З/СЗ); WMO weather_code → русские описания и иконки
  (статическая таблица в коде; осадки — probability_max, %; карточка
  «Сегодня» берет max/min из daily[0] — согласованность с прогнозом).

## §4. Кэш: файл в томе weather-cache, TTL 60 мин

- Файл `/data/cache/weather.json` (том `weather-cache`, named volume —
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
  в файле, в памяти ничего авторитетного.
- «Мягкое» обновление: истекший кэш НЕ блокирует ответ — при отказе
  провайдера пользователь всегда получает максимум доступного (spec
  «Недоступность провайдера…»).

## §5. nginx: auth_request по образцу video (§5 дизайна video)

Обе локации за valid сессией; проверка — subrequest к самому `weather`
(прецедент: video проверяет свою отдачу своим authcheck):

```
location = /weather {
    auth_request /_weather_auth;          # subrequest → weather:8381
    error_page 401 = @login_redirect;     # страницы: редирект на /login
    error_page 502 503 504 = @weather_down;
    # статика страницы по мокапу A (поставка static_v-бампом)
}
location ^~ /api/weather/ {
    auth_request /_weather_auth;
    error_page 401 = @weather_api_401;    # JSON 401, не редирект
    error_page 502 503 504 = @weather_down;
    resolver 127.0.0.11 valid=10s;        # анти-stale-DNS (паритет video)
    proxy_pass http://weather:8381;
}
location = /_weather_auth {
    internal;
    proxy_pass http://weather:8381/api/weather/authcheck;  # 200/401 по cookie
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
}
```

Контракт шва nginx↔weather: `/api/weather/authcheck` — exempt от JSON
401-обвязки, 200 при валидной сессии, 401 иначе (O(мс), без внешних
вызовов). Отказ subrequest (weather down) → `@weather_down` 503
(JSON + Retry-After), не голый 500. Сессионный middleware сервиса —
паритет images/video (только чтение своей сессии, без права писать в
sessions).

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
- Ошибки: 401 (аноним), 503 `weather_unavailable` (нет кэша + провайдер
  недоступен), 503 от nginx при down контейнера.
- `/api/health` — 200 без бизнес-логики (шаблон healthcheck video).

## §7. Фронт: страница /weather по мокапу A, static_v

- Статическая страница по `variant-a.html` (токены V3 «Бумага», inline
  SVG-иконки, без CDN): каркас сайдбара — дословно из
  `frontend/templates/base.html`; пункт «Погода» после «Видео».
- Загрузка данных: fetch `/api/weather` (cookie сессии — same-origin);
  состояния: **загрузка** (индикатор), **данные** (карточки),
  **устаревшие** (баннер «данные устарели, обновлено …» + карточки),
  **ошибка** (сообщение «не удалось получить данные погоды» + кнопка
  «Повторить» — честная ошибка, без заглушек).
- Поставка статикой фронта через static_v-бамп (обязанность ПМ — волна
  деплоя; паритет процесса видео/галереи). Никакого JS-фреймворка.

## §8. Альтернативы (отклоненные)

| Альтернатива | Почему нет |
|---|---|
| Кэш в БД ядра / таблица weather_cache | граница PLAN — без БД; миграции и RW-профиль не нужны; файл-атомарной записи достаточно для одного ключа с TTL |
| Кэш только в памяти процесса | теряется при пересоздании контейнера — первый запрос после рестарта бьет в провайдера; том дешевле |
| Выбор города параметром API/конфига | граница PLAN — один город; параметризация — продуктовое решение на будущее |
| Проксирование Open-Meteo напрямую из фронтенда | ломает ОВ-1 (аноним получил бы данные), CORS, таймауты/кэш не контролируются — данные только через weather:8381 |
| Другой провайдер (Яндекс/OpenWeather) | требует ключ/секрет — граница PLAN (Open-Meteo без ключа, решение 2026-10-19) |
| Отдача страницы /weather из ядра app:8377 | страница полностью статична — статика фронта дешевле и не грузит ядро (отличие от /video, где ядро уже рендерит shell) |
