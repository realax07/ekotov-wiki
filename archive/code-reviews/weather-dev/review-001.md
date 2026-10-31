# Code review — weather-service, dev-волна 3 (tasks 3.1–3.4): review-001

Роль: code_reviewer (независимый, append-only). Ревьюируемый объем: диф
2c77164...6b2727f (3 коммита e85e9a9/4e6a5d4/6b2727f, ветка chore/weather-dev):
services/weather/ (FastAPI :8381, 8 модулей + 21 тест), backend/app/pages.py
(роут /weather), frontend/templates/weather.html (+394) и base.html (пункт
сайдбара), services/frontend (Dockerfile COPY + ekotov-wiki.conf +
weather-proxy.inc + weather-headers.inc), deploy/compose.yaml +
compose.test.yaml, tests/web/test_weather_ui.py (5), пиннед-обновление
tests/web/test_p12_nav_icons_favicon_r8.py. 24 файла, +2151/−13.

Контракт: openspec/changes/weather-service/ (spec-дельта 14 Requirements /
23 сценария; design r2). Ворота: `openspec validate weather-service --type
change --strict` — green (воспроизведено на диффе).

Метод: полный diff всех 24 файлов; сверка с design §1–§7 и сценариями спеки
пофайлово; line-by-line паритет middleware/db с services/video; статический
разбор nginx против канона videos-proxy.inc; воспроизведение: pytest
services/weather/tests (21 passed, venv wiki), pytest tests/web/
test_weather_ui.py (5 passed, стенд conftest), pytest
test_p12_nav_icons_favicon_r8.py (5 passed + 1 fail), проверка
pre-existing-фейла на базовом 2c77164 во временной worktree (1 failed —
подтверждено).

---

## Вердикт: APPROVE

## Проверка по фокусам ТЗ

**(1) Соответствие design — ДА.**
- Кэш (§4): атомарная запись tmp + `os.replace` + fsync (cache.py:51-61);
  TTL 60 мин от fetched_at (is_fresh, наивное время трактуется как UTC —
  старые записи не «вечны»); все 4 ветки чтения реализованы и покрыты
  тестами (TC-weather-030…034, 041); обновление при истекшем TTL под
  `asyncio.Lock` с повторной проверкой под локом — двойных вызовов
  провайдера нет (TC-weather-040, конкурентный gather); сбой записи кэша
  (OSError) логируется, ответ не меняется, прежний файл не затерт
  (TC-weather-036, ревью №1 O2); битый JSON провайдера и битый кэш-файл
  не затирают данные (TC-weather-033/041).
- Таймауты/повтор (§3): connect/read/write/pool по 5 с, ATTEMPTS=2
  (ровно один повтор, пауза 1 с) — TC-weather-035 подтверждает ровно 2
  попытки в обоих исходах; суммарный потолок ~11 с соблюден.
- wind_speed_unit=ms — в параметрах и в ассертах; конверсии: гПа →
  мм рт. ст. (×0.750062, TC-weather-011: 984→738), румбы 45° (225°→ЮЗ),
  WMO→ru с дефолтом для неизвестного кода; осадки карточки «Сегодня» —
  вероятность % из daily[0].precipitation_probability_max,
  current.precipitation НЕ запрашивается (TC-weather-013/020/021 —
  ревью №1 F2 закрыто).
- ЭСКАЛАЦИЯ E1 (6b2727f) корректна: у реального Open-Meteo daily-поля
  wind_direction_10m_max нет (задокументировано live-проверкой в
  provider.py:63-70), включено рабочее wind_direction_10m_dominant.
  ВАЖНО: сценарий спеки «Запрос к провайдеру…» daily-направление ветра
  вообще не перечисляет — против spec дифф не идет; расхождение только
  с design §3 (термин). Правку термина в design/spec — на ПМ/архитектора
  (уже помечено в коде), dev-дефектом не считается.

**(2) nginx weather-proxy.inc против канона — ДА.**
- `$upstream_weather` + resolver server-блока 127.0.0.11 valid=10s
  (resolver в ekotov-wiki.conf:79) — анти-stale-DNS, старт без weather
  безопасен; `proxy_next_upstream error timeout`; `proxy_http_version
  1.1`; заголовки Host/X-Real-IP/X-Forwarded-* — дословный паритет
  videos-proxy.inc; URI не переписывается.
- Ключевое отличие по design §5 воспроизведено: `proxy_intercept_errors
  off` + `error_page 502 504 = @weather_down` (503 в error_page НЕ
  назначен) — честный 503 weather_unavailable живого сервиса доходит до
  клиента без подмены, отказ соединения ловится (502/504 генерирует сам
  nginx). `@weather_down` определен (503 JSON + Retry-After 5,
  ekotov-wiki.conf:329-335).
- auth_request НЕ используется нигде в пакете (ни на = /api/weather,
  ни на ^~ /api/weather/); локации /weather и /_weather_auth в nginx
  НЕТ — только API-семейство, паритет design §5. weather-headers.inc
  повторяет security-набор (add_header не наследуется — урок по канону).
- frontend Dockerfile: оба новых inc добавлены в COPY.

**(3) Страница — ДА.**
- pages.py: `/weather` — зеркальный паритет video_page, рендер ядром;
  weather.html extends base.html, `active_page='weather'` (активный
  пункт сайдбара из base.html — ревью №1 O4); собственной копии каркаса
  нет; static_v не требуется (стили/JS в шаблоне — паттерн video.html,
  app.css не тронут).
- base.html: пункт «Погода» СТРОГО шестой, после «Видео», inline-SVG
  16px .nav-icon (viewBox 24, stroke currentColor, aria-hidden) +
  словарь заголовков страницы дополнен.
- 4 состояния UI реализованы: загрузка/данные/устаревшие (баннер с
  временем МСК из fetched_at)/ошибка («Не удалось получить данные
  погоды» + «Повторить», без карточек-заглушек); деградация метрики —
  прочерк «—»; даты парсятся без `new Date(строка)`/toLocaleString —
  от таймзоны браузера не зависят; 401 → редирект /login.
- Без CDN/внешних библиотек (ОГР-8): внешних URL в шаблоне нет.

**(4) Тесты реальные — ДА.**
- services/weather/tests 21/21 passed (прогон review). Провайдер мокается
  двумя независимыми способами: роутер — async-стаб app.provider.fetch со
  счетчиком вызовов; клиент — httpx.MockTransport через аргумент
  transport. Сети нет (TC-weather-020: len(captured)==1 — «никаких других
  внешних вызовов»). Негативные ветки покрыты: 401 без обращений к
  провайдеру/кэшу, TTL-ветки, stale, битый JSON, 503 + несоздание
  кэш-файла, ровно один повтор, сбой записи кэша, конкурентный лок.
- Хелперы — пакетный импорт `from tests.helpers import …`, голых
  conftest-импортов нет (урок BUG-video-001 соблюден).
- tests/web/test_weather_ui.py 5/5 passed (прогон review, стенд
  conftest'а): /api/weather стабится playwright-маршрутом — сервис и сеть
  не нужны; ассерты содержательные (тексты метрик, порядок сайдбара,
  баннер с временем, retry-цикл).
- Пиннед P12 обновлен по прецеденту 1.5 (5→6 пунктов): 5 passed;
  test_no_external_icon_or_favicon_requests — 1 failed, ПОДТВЕРЖДЕНО
  pre-existing прогоном на базовом 2c77164 (1 failed там же) — вне дельты,
  утверждение dev в коммите 4e6a5d4 честное.

**(5) Compose согласован — ДА.**
- Оба файла: weather :8381, mem_limit 128m, restart unless-stopped,
  healthcheck urllib :8381 (числа синхронны Dockerfile), логи json-file
  10m×3, порты не публикуются, depends_on app. Прод: ro wiki-data +
  ЕДИНСТВЕННЫЙ RW weather-cache (named volume, вне бэкап-контура —
  комментировано). Тест: weather-cache-test + wiki-test-data (изоляция
  NFR-10, down -v). EKOTOV_WEATHER_CACHE_PATH задают оба.
- Dockerfile: python:3.12-slim, пины fastapi/uvicorn синхронны
  backend/requirements.txt, USER 10001, без системных бинарей, EXPOSE 8381
  (не публикуется), healthcheck без curl, uvicorn 1 воркер — design §2.

**(6) Зоны — ЧИСТО.**
- deploy/deploy.sh не тронут; static_v-версия не бампалась (волна 5 — ПМ).
- Измененные файлы вне weather-зоны: только разрешенные (pages.py,
  шаблоны, frontend nginx/Dockerfile, compose, tests/web).

## Adversarial-персоны

- **Саботажник — CLEAN.** Конкурентное обновление под локом с повторной
  проверкой; fsync до replace; сбой записи не меняет ответ; clock-skew
  (fetched_at из будущего) → is_fresh=false → безобидный повторный fetch;
  1 воркер — in-process Lock достаточен; nginx intercept off не
  пропускает 502-залипание (error_page 502 504).
- **Новичок — CLEAN.** Магические числа именованы (HPA_TO_MMHG,
  CACHE_TTL_SECONDS, TIMEOUT_SECONDS); E1-отклонение от design
  задокументировано в коде с датой/фактом; каждый модуль объясняет,
  какой пункт design/спеки реализует.
- **Security-аудитор — CLEAN.** Exempt только GET /api/health;
  /openapi.json под middleware; SELECT-only в БД (ro-маунт в compose —
  двойная гарантия); секретов нет (UA из env); XSS: все данные через
  textContent, innerHTML — только статические ICONS-константы; SSRF нет
  (URL — константа); middleware line-by-line паритет video (та же
  семантика expires_at).

Персоны: BLOCK/CONCERNS/CLEAN → CLEAN, CLEAN, CLEAN.

## Таблица замечаний

| # | Файл:строка | Серьезность | Замечание | Рекомендация |
|---|---|---|---|---|
| 1 | services/weather/app/provider.py:213-219 | minor | design §3 формулирует «httpx, единый клиент», код создает новый AsyncClient на каждую попытку внутри цикла | Семантики не меняет (1 запрос/60 мин); поправить формулировку design при правке термина E1 либо вынести клиент из цикла — на усмотрение ПМ |
| 2 | services/weather/app/provider.py:178-189 | minor | days строится по len(daily.time) без среза — при возврате провайдером >7 дней контракт «ровно 7» был бы нарушен (сейчас недостижимо: forecast_days=7) | Срезать [:FORECAST_DAYS] в defensive-целях |
| 3 | services/weather/app/provider.py:147 | minor | `int(code)` на нечисловой строке weather_code даст ValueError → 500 вместо деградации (validate тип кода не проверяет; describe() толерантен, поле code — нет) | Обернуть в try как _num/describe |
| 4 | services/frontend/nginx/ekotov-wiki.conf:250 | nit | Комментарий «^~ /api/weather/ — вложенные: /api/health сервиса weather» фактически неверен: /api/health НЕ под /api/weather/ и через nginx к weather не маршрутизируется (healthcheck ходит в контейнер напрямую); комментарий скопирован с images, где та же неточность | Поправить формулировку при удобном случае |
| 5 | services/weather/tests/helpers.py:108-110 | nit | payload_extra не используется ни одним тестом | Удалить или задействовать |

Ни одного blocker/major.

## Проверенные сценарии

Все 23 сценария дельты specs/weather-service с проверяемым поведением
покрыты кодом и тестами; из них воспроизведены прогоном: 401-негатив,
health-exempt, контракт §6 (7 дней, today↔days[0], 8 метрик), конверсии,
деградация null-метрики, зафиксированные параметры запроса (включая
отсутствие current.precipitation и dominant-поле), User-Agent из конфига,
все 4 ветки кэша §4, битый JSON/кэш, ровно один повтор, конкурентный лок,
503 weather_unavailable; UI: сайдбар после «Видео», аноним-редирект,
4 состояния страницы, retry. Пиннед P12: 5 passed + pre-existing fail
подтвержден на базе.

## Что НЕ проверено (честно)

- Живую НЕТ-интеграцию с реальным Open-Meteo не повторял (E1-факт
  live-проверки принят по фиксации dev; поле dominant — документированное
  API провайдера).
- nginx-конфиг проверен статически против канона (docker/nginx -t в этой
  среде недоступен) — синтаксис-прогон останется за деплой-волной 5.2.
- NFR-замеры (RAM в лимите 128m, отзывчивость ≤ ~11 с, деградация nginx
  при остановленном weather) — волна 4 (QA), вне этого ревью.
- Соответствие пиксель-в-пиксель мокапу A (design_validator) — по tasks.md
  это отдельная проверка после dev; структурно страница мокапу следует
  (сетка 4-в-ряд, 8 метрик, today-mark).

## Итог

**APPROVE.** Волна 3 соответствует design r2 и спеке; эскалация E1
обработана корректно и прозрачно; зоны волны 5 не тронуты. Действия
наружу: (1) ПМ/архитектор — правка термина wind_direction_10m_max →
wind_direction_10m_dominant в design §3/spec (помечено в коде); (2)
замечания minor-1…3 и nit-1…2 — в бэклог, не блокируют волну 4.
