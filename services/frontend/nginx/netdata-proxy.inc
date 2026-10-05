# Прокси netdata-семейства (задача 1.3, add-netdata-monitoring; design §1/§2).
# Подключается из ekotov-wiki.conf локациями = /netdata/ и ^~ /netdata/.
#
# Официальный паттерн Netdata за nginx в subpath (docs Netdata «Running
# Netdata behind Nginx», «As a subfolder»): URI дашборда НЕ переписывается на
# стороне netdata — префикс /netdata вырезается на прокси и netdata видит
# свой корень («/», «/v1/...», «/static/...»). Вырезание — через named
# capture в rewrite: (?<ndpath>...) сохраняет под-путь в переменную $ndpath,
# затем proxy_pass собирает полный URL из $ndpath + строка запроса
# ($is_args$args — при переменных в proxy_pass исходный URI НЕ
# подставляется, аргументы нужно передать явно — отсюда официальный хвост
# …/$ndpath$is_args$args).
#
# Переменная $netdata_upstream: паритет app/search — proxy_pass со
# статическим именем резолвится ОДИН раз на старте (stale-DNS 502 при
# пересоздании netdata). resolver 127.0.0.11 из server-блока + имя в
# переменной = переразрешение на запросах (valid=10s); старт nginx без
# поднятого netdata безопасен (ошибка резолва — только на запросе).
#
# Аутентификация (auth_basic) задается в самих локациях ДО этого include —
# access-фаза идет раньше content-фазы, поэтому без валидных кредов ни один
# запрос до netdata не доходит (ОВ-2, spec monitoring: «401 ДО любого
# обращения к netdata»).
#
# Таймауты наследуются из server-блока (proxy_connect_timeout 5s,
# proxy_read_timeout 30s) — netdata-дашборд штатно переподключает свои
# потоки данных; отдельных таймаутов не заводим (паритет app/search).
#
# proxy_intercept_errors НЕ включаем (в отличие от search): ошибки netdata
# (его собственные страницы/коды) должны проходить браузеру как есть —
# деградация «@search_down» для мониторинга не заведена (design §1/§4).

# ВАЖНО (порядок директив): set — директива rewrite-фазы, а rewrite c флагом
# break ОСТАНАВЛИВАЕТ обработку rewrite-фазы в локации. Поэтому set
# $netdata_upstream обязан стоять ДО rewrite: иначе переменная остается
# пустой и proxy_pass получает «/v1/...» без схемы («invalid URL prefix»,
# 500). Проверено прогоном песочницы nginx (задача 1.3).
set $netdata_upstream http://netdata:19999;

# Вырезание префикса: /netdata/... → $ndpath = "/..." (для точной локации
# «= /netdata/» — $ndpath = "/"). break останавливает rewrite-фазу внутри
# локации; итоговый URI для upstream собирает proxy_pass ниже.
rewrite ^/netdata(?<ndpath>/.*)$ $ndpath break;

proxy_pass $netdata_upstream$ndpath$is_args$args;

proxy_http_version 1.1;
proxy_redirect off;
proxy_pass_request_headers on;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host  $host;
# Keep-Alive к netdata (официальный паттерн subpath: netdata держит
# долгоживущие соединения потоков дашборда на HTTP/1.1).
proxy_set_header Connection "Keep-Alive";
