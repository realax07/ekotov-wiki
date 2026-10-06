# Code-review 1.3 — Devops: nginx-локации /netdata с basic auth (change add-netdata-monitoring)

- **Дата:** 2026-10-06 (ретроспективное ревью, закрытие процессного долга P13)
- **Ревьюер:** независимый code_reviewer (review-004)
- **Reviewer-Delegation:** deleg_b75e09f8
- **Correlation:** 0dd08a0b4a90448eb758fe6f326f5706
- **Диф:** `3fd7af7` (ekotov-wiki.conf +48, netdata-proxy.inc новый 57 строк, netdata-headers.inc новый, compose.yaml +7, compose.test.yaml +12, deploy/.gitignore новый, Dockerfile COPY; итого 8 файлов, +230/−4, включая REPORT-1.3-netdata-nginx.md)
- **Арбитры:** openspec/changes/add-netdata-monitoring/specs/monitoring/spec.md (FR-75/76/77; пакет еще не архивирован), design.md §1/§2/§6, tasks.md 1.3, deploy/RUNBOOK.md §2.2
- **Provenance:** ревью на SHA `3fd7af794af9ebab40ed816a00b473f51ed003de` (входит в head main `0b9a670d1da57da18a926b8fd83434ddaf28c08c`); пост-диффных правок ревьюируемых nginx/compose-файлов задетой зоны нет (дальнейшие изменения — только images-семейство задачи 1.4 add-gallery-service, вне зоны 1.3). Контекст ретро: код смержен и работает на проде (r7-netdata, приемка Заказчика пройдена), review-файл отсутствовал — ревью задним числом по прецеденту add-containerization (review-008/009).

## Вердикт: **ОДОБРИТЬ** (approve; blocker 0, major 0, minor 1)

## Таблица замечаний

| # | Серьезность | Файл:строка | Замечание | Рекомендация |
|---|---|---|---|---|
| 1 | minor | git-история: 34c32d6 (revert 85158a4) | Hash ТЕСТ-пароля стенда попал в историю main: `deploy/netdata.htpasswd.test` (содержимое `qa-monitoring:$apr1$839S8.nB$…`) закоммичен в design-коммите 34c32d6 2026-10-05 18:42:43 и отrevert-нут через 8 секунд (85158a4), но остался достижим из main. Вне диффа 1.3: сам дифф ввел deploy/.gitignore, и он работает (check-ignore подтвержден, в HEAD htpasswd-файлов нет — сценарий спеки «htpasswd вне репозитория» на срезе HEAD выполняется). Риск ограничен: креды только стенда (qa-test-only), стенд не публичный. | Историю не переписывать (main защищен ruleset, тестовые креды). Сменить тест-пароль стенда при следующем регрессе (openssl passwd -apr1) и записать урок: перед commit -A проверять git status на ignore-артефакты. |
| 2 | nit | deploy/compose.test.yaml:19-21 | Тестовые креды стенда (qa-monitoring/qa-test-only) в открытом виде в комментарии compose-файла — осознанное решение (пароль тестовый, только стенд), но текстом в репо. | Не чинить. При смене пароля (замечание 1) креды из комментария убрать, оставить только команду генерации. |

## Первый круг — спека (дельта monitoring, FR-75/76)

Верифицировано `git show 3fd7af7` + независимые прогоны ревьюера (не пересказ REPORT):

- **Локации (FR-76, design §1):** `location = /netdata → return 301 /netdata/`; `location = /netdata/` и `location ^~ /netdata/` — обе с `auth_basic "Monitoring"` + `auth_basic_user_file /etc/nginx/netdata.htpasswd` (парная проверка точной и префиксной — дословно spec). `^~` отключает regex — семейство не перебивается будущими regex-локациями, паритет search/images-семейств. `^~ /netdata/` — граница сегмента: `/netdataX` не захватывается (regex-проверка ревьюера: `/netdataX` и `/netdata` NOT MATCH, `/netdata/…` → ndpath корректен).
- **Прокси (официальный паттерн Netdata subpath):** named capture `rewrite ^/netdata(?<ndpath>/.*)$ $ndpath break` + `proxy_pass $netdata_upstream$ndpath$is_args$args` — префикс вырезан, строка запроса передана явно (при переменных в proxy_pass исходный URI не подставляется). Порядок `set` ДО `rewrite` корректен и откомментирован: break останавливает rewrite-фазу, иначе пустая переменная → «invalid URL prefix» (отловлено dev при прогоне песочницы — комментарий в файле подтверждает и объясняет). Симуляция regex: `/netdata/`→`/`, `/netdata/v1/info`→`/v1/info`, `/netdata/static/main.css`→`/static/main.css` — PASS.
- **Анти-stale-DNS (паритет search-семейства):** `resolver 127.0.0.11 valid=10s ipv6=off` из server-блока + имя в переменной `$netdata_upstream` — переразрешение на запросах; старт nginx без поднятого netdata безопасен. Схема идентична app/search (ekotov-wiki.conf:79).
- **Маунты htpasswd (FR-76, design §2):** прод compose.yaml — bind `/etc/nginx/netdata.htpasswd:/etc/nginx/netdata.htpasswd:ro` хоста; стенд compose.test.yaml — `./netdata.htpasswd.test:…:ro`; оба :ro. Комментарии фиксируют: генерация до пересоздания frontend (иначе nginx падает на старте — design §6), пароль отдельный от wiki-owner. **Секреты вне репо:** deploy/.gitignore покрывает netdata.htpasswd, netdata.htpasswd.test, *.htpasswd — `git check-ignore` подтверждает все три; в HEAD и во всей истории после фикса tracked htpasswd-файлов нет (исключение — история-инцидент, замечание 1, вне диффа).
- **Dockerfile:** netdata-proxy.inc и netdata-headers.inc добавлены в COPY /etc/nginx/conf.d/ — файлы попадают в образ; htpasswd в COPY НЕ входит (маунт с хоста) — PASS.
- **Границы диффа:** только заявленные файлы, tasks.md/спеки/фронтенд не тронуты.

## Второй круг — security

- **Basic auth ДО прокси:** auth_basic — access-фаза, раньше content-фазы proxy — без валидных кредов ни один запрос до netdata не доходит. Проверено на живом проде: `/netdata/` без кредов → **401** с `WWW-Authenticate: Basic realm="Monitoring"`; `/netdata/static/main.css` без кредов → **401** (префиксная локация прикрыта той же парой).
- **Обходных путей нет:** порт 19999 netdata не публикуется — `ss -tln` на хосте слушает только :10443 (из docker-семейства), `docker ps`: netdata `19999/tcp` без маппинга (внутри compose-сети), frontend публикует только 10443. Спека «Netdata не публикуется наружу напрямую» — PASS на живом проде.
- **Заголовки (NFR-7):** netdata-headers.inc повторяет security-набор server-уровня (nosniff, X-Frame-Options DENY, Referrer-Policy, HSTS) — корректно: add_header в location перекрывает server-уровень (урок Р6). Без X-Service — обоснованно (ответ от netdata, не от сервиса-маркера). 301-локация без auth — только слэш-редирект, контента не отдает (спека прямо этого требует).
- **Осознанные отличия от search-proxy.inc:** proxy_intercept_errors выключен (ошибки netdata проходят браузеру как есть, деградация @search_down для мониторинга не заведена — design §1/§4), Connection "Keep-Alive" — официальный паттерн долгоживущих потоков дашборда. Отличия откомментированы и трассируются на design.

## Третий круг — интеграция и живой факт (прод r7-netdata)

- **Регресс соседних семейств:** search/images-локации в конфиге не задеты (дифф — вставка блока между search-семейством и `location /`); images-семейство появилось позже (1.4), конфликта локаций нет (`^~ /netdata/` vs `^~ /api/images/` — непересекающиеся префиксы).
- **RUNBOOK §2.2** соответствует факту: «/netdata — basic auth (htpasswd bind :ro, chmod 644) → netdata:19999» (chmod 644 — после инцидента 640→644 на выкатке, зафиксирован в 5f553a0; сам дифф chmod не задает — чинится операционно на хосте, замечание к инструкции ПМ, не к коду).
- **Живой прод (https://127.0.0.1:10443, self-signed):** `/netdata` → 301 → `/netdata/`; `/netdata/` → 401 realm Monitoring; `/netdata/static/main.css` → 401; порт 19999 наружу закрыт. Успешный вход с кредами не проверялся ревьюером (креды owner известны только Заказчику; успешный путь принят по факту приемки r7-netdata 2026-10-05 и 10/10 сценариев песочницы REPORT-1.3).

## Что НЕ проверено (честно)

- **Успешная аутентификация с кредами owner** на проде (200 + сборка дашборда) — креды у Заказчика; покрыто приемкой r7-netdata и песочницей dev (10/10), но не воспроизведено ревьюером.
- **nginx -t валидация локально** — системный python 3.14 без nginx; валидация визуальная + grep + живой прод (конфиг реально работает под nginx образа).
- **Стенд compose.test** с bind тест-htpasswd — живой прогон стенда не поднимался ревьюером; паритет прод/стенд структурно проверен по файлам.
- Ретроспективность: ревью выполняется на head main (0b9a670) с provenance на SHA диффа — пост-диффные изменения зоны проверены на отсутствие (их нет, кроме последующего независимого images-семейства).

## Прочие наблюдения (не замечания к 1.3)

- Чекбокс 1.3 в tasks.md задним числом НЕ проставляется (урок 7b12097, febd267) — закрытие процессного долга фиксируется этим review-файлом, отметка задач — решение ПМ.
- Пакет add-netdata-monitoring на момент ревью не архивирован — арбитры читались из openspec/changes/add-netdata-monitoring/ (specs/monitoring, design.md).
