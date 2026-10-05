# Прокси search-семейства (задача 1.3, add-microservices-full; design §1/§4).
# Подключается из ekotov-wiki.conf локациями /api/search*, /api/suggestions*.
#
# Переменная $upstream_search: без нее proxy_pass со статическим именем
# резолвится ОДИН раз на старте — при отсутствии search-контейнера в сети
# nginx не стартует (упадет на host not found in upstream), а при
# пересоздании search держал бы мертвый IP. resolver из server-блока +
# переменная = переразрешение на запросах (анти-stale-DNS, как у app).
#
# URI не переписывается (proxy_pass БЕЗ URI-части): search-роутеры видят
# свои пути как в монолите — контракт /api/search*, /api/suggestions
# прозрачен для nginx (design §3 п.2 «маршрут прозрачен»).

set $upstream_search http://search:8378;

# Таймауты уже заданы в server-блоке (proxy_connect_timeout 5s и пр.) —
# не переопределяем.

# Отказ search (design §4, «Деградация при отказе search»: nginx отвечает
# 503 быстро, не таймаут, не 502-залипание):
#   proxy_next_upstream для single-upstream proxy_pass обрабатывает случаи
#   «соединение не установлено/обрыв во время запроса» — повторной попытки
#   на другой апстрим нет, но флаг error-timeout гоняет запрос в error_page
#   сразу, без залипания на дефолтной политике «только на неидемпотентных»;
#   proxy_intercept_errors + error_page 502 503 504 → именованная локация
#   @search_down (быстрый управляемый 503 c JSON-телом и Retry-After).
proxy_next_upstream error timeout;
proxy_intercept_errors on;
error_page 502 503 504 = @search_down;

proxy_http_version 1.1;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_pass $upstream_search;
