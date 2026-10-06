# Прокси images-семейства (задача 1.4, add-gallery-service; design §1/§4).
# Подключается из ekotov-wiki.conf локациями = /api/images и ^~ /api/images/.
#
# Переменная $upstream_images — по образцу search-proxy.inc: без нее
# proxy_pass со статическим именем резолвится ОДИН раз на старте — при
# отсутствии images-контейнера в сети nginx не стартует (host not found in
# upstream), а при пересоздании images держал бы мертвый IP. resolver из
# server-блока (127.0.0.11 valid=10s) + переменная = переразрешение на
# запросах (анти-stale-DNS); старт nginx без images безопасен.
#
# URI не переписывается (proxy_pass БЕЗ URI-части): images-роутеры видят
# свои пути как есть (design §1 «маршрутизацию выполняет nginx»).

set $upstream_images http://images:8379;

# Лимит загрузки (design §4, NFR-21): файл ≤ 10 МБ + multipart-обвязка.
# Прод-лимит server-уровня 2m перебивается локацией — без этого upload
# 10МБ валится 413 раньше сервиса (урок search-семейства).
client_max_body_size 12m;

# Отказ images (design §4, «Деградация при отказе images»: nginx отвечает
# 503 быстро, не таймаут, не 502-залипание) — паттерн @search_down:
# proxy_next_upstream error timeout гоняет ошибку соединения в error_page
# сразу; proxy_intercept_errors + error_page 502 503 504 → именованная
# локация @images_down (быстрый управляемый 503, JSON + Retry-After).
proxy_next_upstream error timeout;
proxy_intercept_errors on;
error_page 502 503 504 = @images_down;

# Таймауты уже заданы в server-блоке (proxy_connect_timeout 5s и пр.) —
# не переопределяем.
proxy_http_version 1.1;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_pass $upstream_images;
