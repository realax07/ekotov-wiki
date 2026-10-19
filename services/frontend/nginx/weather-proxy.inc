# Прокси weather-семейства (change weather-service, задача 5.2-паттерн
# ревью №1 F1-в — design §5). Подключается из ekotov-wiki.conf локациями
# = /api/weather и ^~ /api/weather/.
#
# Переменная $upstream_weather — по образцу videos-proxy.inc:
# без нее proxy_pass со статическим именем резолвится ОДИН раз на старте —
# при отсутствии weather-контейнера в сети nginx не стартует (host not
# found in upstream), а при пересоздании weather держал бы мертвый IP.
# resolver из server-блока (127.0.0.11 valid=10s) + переменная =
# переразрешение на запросах (анти-stale-DNS); старт nginx без weather
# безопасен.
#
# URI не переписывается (proxy_pass БЕЗ URI-части): weather-роутер видит
# свой путь как есть (design §1 «маршрутизацию выполняет nginx»).
#
# ОТЛИЧИЕ от видео (ревью №1 F1-в, design §5): proxy_intercept_errors
# ВЫКЛЮЧЕН — живой сервис СА отвечает управляемым 503
# weather_unavailable (spec «Пустой кэш…»), и он должен дойти до клиента
# БЕЗ подмены. Отказ соединения (контейнер остановлен) — ошибку
# генерирует сам nginx (502/504, не upstream-ответ), error_page ловит ее
# и без intercept. Поэтому error_page 502 504 = @weather_down (503 из
# error_page НЕ назначается — честный 503 сервиса не перехватывается).
#
# auth_request НЕ используется (design §5): сессию проверяет сессионный
# middleware сервиса (401 JSON); authcheck-эндпоинта у weather НЕТ.
# client_max_body_size НЕ переопределяется (GET без тела — server-лимит 2m
# достаточен; upload-семейства у weather нет).
#
# Таймауты уже заданы в server-блоке (proxy_connect_timeout 5s и пр.) —
# не переопределяем (урок видео: server-лимиты перебиваются локацией —
# здесь ничего локация не поднимает).

set $upstream_weather http://weather:8381;

proxy_next_upstream error timeout;
proxy_intercept_errors off;
error_page 502 504 = @weather_down;

proxy_http_version 1.1;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_pass $upstream_weather;
