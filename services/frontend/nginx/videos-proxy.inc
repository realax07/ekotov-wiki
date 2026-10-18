# Прокси video-семейства (задача 1.4, change video-hosting; design §1/§6).
# Подключается из ekotov-wiki.conf локациями = /api/videos и ^~ /api/videos/.
#
# Переменная $upstream_videos — по образцу search-proxy.inc/images-proxy.inc:
# без нее proxy_pass со статическим именем резолвится ОДИН раз на старте —
# при отсутствии video-контейнера в сети nginx не стартует (host not found
# in upstream), а при пересоздании video держал бы мертвый IP. resolver из
# server-блока (127.0.0.11 valid=10s) + переменная = переразрешение на
# запросах (анти-stale-DNS); старт nginx без video безопасен.
#
# URI не переписывается (proxy_pass БЕЗ URI-части): video-роутеры видят
# свои пути как есть (design §1 «маршрутизацию выполняет nginx»).

set $upstream_videos http://video:8380;

# Лимит загрузки (design §4, ОВ-1): файл ≤ 500 МБ + multipart-обвязка
# (~20 МБ) — ТОЛЬКО в локациях /api/videos (include-файл подключается
# именно ими). Прод-лимит server-уровня 2m перебивается локацией — без
# этого upload 500МБ валится 413 раньше сервиса (урок search/images-семейства).
# Согласован с pre-check сервиса (500 МБ + та же обвязка — app/videos.py).
client_max_body_size 520m;

# Отказ video (design §1/§6, «Деградация при отказе»: nginx отвечает на
# /api/videos* быстрым управляемым 503 — не таймаут, не 502-залипание) —
# паттерн @images_down/@search_down: proxy_next_upstream error timeout
# гоняет ошибку соединения в error_page сразу; proxy_intercept_errors +
# error_page 502 503 504 → именованная локация @videos_down (быстрый
# управляемый 503, JSON + Retry-After). Тот же сценарий для /videos/
# назначается в самой локации (отказ authcheck-subrequest — тоже 503,
# устранение F2, design §5).
proxy_next_upstream error timeout;
proxy_intercept_errors on;
error_page 502 503 504 = @videos_down;

# Таймауты уже заданы в server-блоке (proxy_connect_timeout 5s и пр.) —
# не переопределяем.
proxy_http_version 1.1;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_pass $upstream_videos;
