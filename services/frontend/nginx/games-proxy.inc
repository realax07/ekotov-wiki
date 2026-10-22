# Прокси game-portal (P26; PRODUCT_BACKLOG.md «P26. Интеграция game-portal»).
# Подключается из ekotov-wiki.conf локациями = /games и ^~ /games/.
#
# game-portal — standalone-контейнер ВНЕ compose (хаб external, поднимает ПМ
# отдельно: docker run … --network ekotov-wiki-par_default, порт 8080 внутри;
# см. RUNBOOK §9). Префикс /games вырезается на прокси — хаб видит свой
# корень: named capture по образцу netdata-proxy.inc — (?<gpath>...) сохраняет
# под-путь, proxy_pass собирает URL из $gpath + строка запроса ($is_args$args
# — при переменных в proxy_pass исходный URI НЕ подставляется, аргументы
# передаются явно).
#
# Переменная $upstream_games — паритет weather/videos: без нее proxy_pass со
# статическим именем резолвится ОДИН раз на старте — при отсутствии
# game-portal в сети nginx не стартует (host not found in upstream), а при
# пересоздании контейнера держал бы мертвый IP. resolver из server-блока
# (127.0.0.11 valid=10s) + переменная = переразрешение на запросах;
# старт nginx без game-portal безопасен (ошибка резолва — только на запросе).
#
# sub_filter (P26): хаб раздает АБСОЛЮТНЫЕ пути (href="/…", src="/…",
# fetch('/api/…)) и ничего не знает о префиксе /games — на прокси пути
# переписываются под внешний префикс. sub_filter работает только по
# proxy-ответам перечисленных типов: дефолтный text/html (sub_filter_types)
# + application/javascript явно. proxy_set_header Accept-Encoding "" —
# сжатый ответ upstream'а субфильтр не обрабатывает. sub_filter_once off —
# заменяются ВСЕ вхождения на странице/в бандле.
# proxy_intercept_errors не включаем — собственные ответы/коды хаба (его
# 404 и т.п.) проходят браузеру как есть; деградация @*_down для хаба не
# заведена (внешний контейнер вне матрицы деплоя, RUNBOOK §9).
# Таймауты наследуются из server-блока (proxy_connect_timeout 5s и пр.).

# ВАЖНО (порядок директив): set ДО rewrite — директива rewrite-фазы, а
# rewrite c break ОСТАНАВЛИВАЕТ rewrite-фазу в локации (урок
# netdata-proxy.inc: иначе переменная пуста и proxy_pass получает
# «invalid URL prefix», 500).
set $upstream_games http://game-portal:8080;

# Вырезание префикса: /games/... → $gpath = "/..." (для точной локации
# «= /games/» — $gpath = "/"). break останавливает rewrite-фазу внутри
# локации; итоговый URI для upstream собирает proxy_pass ниже.
rewrite ^/games(?<gpath>/.*)$ $gpath break;

# Хаб не сжимает для нас: sub_filter по сжатому телу не работает.
proxy_set_header Accept-Encoding "";

proxy_pass $upstream_games$gpath$is_args$args;

sub_filter_types application/javascript;
sub_filter_once off;
sub_filter 'href="/' 'href="/games/';
sub_filter 'src="/' 'src="/games/';
sub_filter 'fetch(\'/api/' 'fetch(\'/games/api/';

proxy_http_version 1.1;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
