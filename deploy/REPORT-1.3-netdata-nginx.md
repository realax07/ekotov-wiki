# REPORT 1.3 — nginx-локации /netdata с basic auth (add-netdata-monitoring)

Задача: tasks.md 1.3 [M] (Devops: nginx-локации `/netdata` в образе frontend).
Correlation_id: 0dd08a0b4a90448eb758fe6f326f5706.
Design: §1 (топология, resolver + переменная, официальный паттерн Netdata
subpath), §2 (basic auth, htpasswd вне репозитория, ro-маунт).

## Что сделано

1. `services/frontend/nginx/ekotov-wiki.conf` — netdata-семейство по образцу
   search-семейства (пара «точная + префиксная», `^~` отключает regex):
   - `location = /netdata` → `return 301 /netdata/` (дашборду Netdata нужен
     trailing slash; 301 не аутентифицируется — редирект на корректный URL);
   - `location = /netdata/` и `location ^~ /netdata/` → `auth_basic
     "Monitoring"` + `auth_basic_user_file /etc/nginx/netdata.htpasswd` →
     include `netdata-headers.inc` + `netdata-proxy.inc`.
2. `services/frontend/nginx/netdata-proxy.inc` — официальный паттерн Netdata
   subpath: named capture `rewrite ^/netdata(?<ndpath>/.*)$ $ndpath break;` +
   `proxy_pass $netdata_upstream$ndpath$is_args$args` (переменные в
   proxy_pass исходный URI НЕ подставляют — строку запроса передаем явно);
   префикс вырезается на прокси, netdata видит свой корень. Переменная
   `$netdata_upstream` + resolver 127.0.0.11 valid=10s из server-блока —
   анти-stale-DNS (паритет app/search). proxy_intercept_errors НЕ включен:
   собственные коды/страницы netdata проходят как есть (деградация
   «@search_down» для мониторинга не заведена, design §1/§4).
3. `services/frontend/nginx/netdata-headers.inc` — security-набор NFR-7
   повторен в локациях (add_header в location наследуется с перекрытием —
   server-уровень к ним не применяется; урок Р6).
4. `services/frontend/Dockerfile` — COPY двух новых include в
   /etc/nginx/conf.d/. htpasswd в образ НЕ копируется (design §2).
5. `deploy/compose.yaml` — bind-mount
   `/etc/nginx/netdata.htpasswd:/etc/nginx/netdata.htpasswd:ro` (+ команда
   генерации в комментарии, design §6: файл создается на VPS до пересоздания
   frontend, иначе nginx упадет на старте).
6. `deploy/compose.test.yaml` — bind-mount
   `./netdata.htpasswd.test:/etc/nginx/netdata.htpasswd:ro` + креды стенда и
   команда генерации в шапке.
7. `deploy/.gitignore` — `netdata.htpasswd`, `netdata.htpasswd.test`,
   `*.htpasswd` (spec monitoring: «htpasswd вне репозитория»).
8. Тест-htpasswd для стенда сгенерирован:
   `deploy/netdata.htpasswd.test` — `qa-monitoring` / `qa-test-only`
   (apr1-хеш, openssl passwd -apr1). Креды ТОЛЬКО стенда (изоляция NFR-10),
   продовый пароль задает Заказчик в 2.2 (вне репозитория).

## Урок реализации (не в скиллах ранее)

**`rewrite … break` останавливает rewrite-фазу, включая стоящие ПОСЛЕ него
`set`.** Первый вариант netdata-proxy.inc имел `set $netdata_upstream` после
rewrite — переменная оставалась пустой, `proxy_pass` получал «/v1/...» без
схемы: «invalid URL prefix», 500. Поймано живым прогоном песочницы (не
`nginx -t` — тот синтаксически пропускает). `set` перенесен ДО rewrite.

## Верификация (локальная песочница nginx 1.24.0, конфиг образа с
подстановками: порты 10443→18443, upstream-имена → 127.0.0.1-стабы,
контейнерные пути include/ssl/htpasswd → пути песочницы; стабы python на
8377/8378/19999 отвечают JSON с фактическими path)

`nginx -t` песочницы: syntax ok / test successful.

| # | Сценарий (spec monitoring) | Результат |
|---|---|---|
| 1 | `/netdata` без кредов | **301** Location=…/netdata/ ✓ |
| 2 | `/netdata/` без кредов | **401** `Basic realm="Monitoring"` ✓ (до прокси) |
| 3 | `/netdata/` с тест-кредами | **200**, стаб 19999 получил `path=/` ✓ |
| 4 | `/netdata/v1/info?after=5` | 200, upstream-путь `/v1/info?after=5` — префикс вырезан, args сохранены ✓ |
| 5 | `/netdata/static/img/logo.svg` | 200, `/static/img/logo.svg` ✓ |
| 6 | неверный пароль | **401** ✓ |
| 7 | регресс `/api/health` | 200 через app-стаб, без basic ✓ |
| 8 | регресс `/api/search` | 200, `X-Service: search` ✓ |
| 9 | `/netdataX` (посторонний) | ушел в app, НЕ в netdata-локации ✓ |
| 10 | security-заголовки netdata-ответа | nosniff/DENY/same-origin/HSTS присутствуют ✓ |

YAML: `yaml.safe_load` обоих compose + проверка htpasswd-маунтов `:ro` в
nginx-сервисе обоих файлов — PASS.
`.gitignore`: `git check-ignore` подтверждает покрытие обоих артефактов;
`git status` их не показывает.

## Ограничения

- Живой смоук на стенде с реальным контейнером netdata (301 → 401 → 200 +
  сборка дашборда, наличие метрик) — у Заказчика в задачах 2.1/2.2 (docker
  агенту недоступен; здесь стаб вместо netdata — паттерн прокси проверен,
  поведение самого Netdata за прокси — нет).
- Файл htpasswd отсутствует на данной машине в контейнерном пути — nginx
  контейнера при старте без него упадет (ожидаемо, design §6: генерация до
  пересоздания frontend).
- Чекбокс 1.3 в tasks.md НЕ отмечал: прецедент 1.2/1.4 — чекбокс отмечает
  ПМ при приемке (review-002-1.2, «[x] 1.2» — коммит ПМ).
