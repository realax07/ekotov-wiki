# Proposal: add-netdata-monitoring

## Change ID

`add-netdata-monitoring`

## Why

Пакет 1 цикла R7 (PLAN-R7.md; решение Заказчика `decisions/2026-10-05-r7-launch`,
Telegram 2026-10-05: «Давай графану добавим…» с уточнением ОВ-1…ОВ-2):
**мониторинг железа, контейнеров и сервисов wiki**. Вводные Заказчика:

- **ОВ-1** = вариант (в) **Netdata** — легкий стек (один контейнер, без
  Prometheus/Grafana-обвязки): «сделай доступ туда только для Учетки owner»;
- **ОВ-2** = доступ к мониторингу **только учетка owner**;
- дословно: «В UI в нижнем левом углу сделай просто ссылку на нее. В графану
  выведи показатели контейнеров, сервисов и железа (cpu, RAM, HDD)»;
- критерий приемки Заказчика: дашборд с CPU/RAM/HDD/контейнерами вживую
  (задача [ops] 2.2).

Прод — матричный контейнерный стек p12-rc1 (compose-проект `ekotov-wiki-par`,
2026-10-05): app + frontend(nginx, TLS :10443, единственная наружная точка) +
search + backup; том `wiki-data`. Существующая capability `deploy` —
`openspec/specs/deploy/spec.md`. Ссылка на мониторинг — в существующем
сайдбаре (capability `navigation`).

## What Changes

Дельты: **новая capability `monitoring`** (стек Netdata и доступ к нему) +
**ADDED Requirement в capability `navigation`** (ссылка в сайдбаре) +
**MODIFIED Requirement в capability `deploy`** (лимиты памяти: +netdata).

| Группа | Requirement | Тип | Capability | Источник |
|---|---|---|---|---|
| Сбор метрик | «Метрики собираются сервисом Netdata без агентов на хосте» | ADDED | monitoring | ОВ-1, FR-75 |
| Изоляция | «Netdata не публикуется наружу напрямую» | ADDED | monitoring | FR-75 |
| Авторизация | «Доступ к дашборду — только учетка owner через nginx» | ADDED | monitoring | ОВ-2, FR-76 |
| Показатели | «Дашборд покрывает показатели Заказчика (CPU/RAM/HDD, контейнеры)» | ADDED | monitoring | FR-77 |
| Ресурсы | «Ресурсы мониторинга ограничены» | ADDED | monitoring | NFR-19 |
| Ссылка в UI | «Ссылка «Мониторинг» в сайдбаре для owner» | ADDED | navigation | FR-78, ОВ-2 |
| Ресурсы (деплой) | «Лимиты памяти контейнеров» (+netdata 256m) | MODIFIED | deploy | NFR-19 |

Нумерация требований продолжает сквозную: FR-75…FR-78, NFR-19 (последние
использованные — FR-74, NFR-18). Полное ТЗ — `requirements.md` этого пакета
(статус ставит Заказчик).

## Scope

### In scope

- Контейнер `netdata` (образ `netdata/netdata`) в `deploy/compose.yaml` и
  `deploy/compose.test.yaml` (стенд — паритет топологии, NFR-10): RAM-лимит
  256m, healthcheck, ротация логов, маунты `/proc`, `/sys` **ro** и
  `/var/run/docker.sock` **ro** (контейнеры через cgroups/docker-сокет),
  порты наружу не публикуются.
- nginx-локация `/netdata/` в образе frontend (пара `=` + `^~` по паттерну
  search-семейства; resolver+переменная против stale-DNS): proxy на
  `netdata:19999`, перед прокси — HTTP Basic-аутентификация (htpasswd с
  кредами owner; файл — вне репозитория, bind-mount ro, генерация — шаг
  RUNBOOK/задачи [ops]).
- Ссылка «Мониторинг» в `sidebar-footer` base.html (внизу слева, рядом с
  «Настройки»/«Выйти»): `target="_blank"` на `/netdata/`, рендер по роли из
  `GET /api/auth/me` — только owner.
- MODIFIED deploy: суммарные лимиты 1.41 GB, резерв хосту ≥ 2.4 GB (VPS
  3.9 GB; до пакета — 1.15 GB / ≥ 2.7 GB).
- QA-смоук (стенд) и прод-выкатка с приемкой Заказчика ([ops]).

### Out of scope

- Grafana, Prometheus, cAdvisor, exporters, long-term storage метрик,
  алертинг, Netdata Cloud — ОВ-1 фиксирует Netdata как легкий стек; docker
  cgroups-коллектор Netdata покрывает «показатели контейнеров и сервисов»
  без дополнительной инфры (design §4).
- Метрики приложения (бизнес-метрики задач/поиска) — не запрашивалось.
- Изменение поведения существующих маршрутов wiki — только добавление
  `/netdata`-семейства на nginx и одного пункта сайдбара.
- Разделение метрик между пользователями (ОВ-4 Галереи к мониторингу не
  относится): мониторинг — только owner (ОВ-2).

## Impact

- **Код/инфра:** `deploy/compose.yaml`, `deploy/compose.test.yaml` (сервис
  netdata), `services/frontend/nginx/ekotov-wiki.conf` (+2 локации,
  htpasswd-маунт), `services/frontend/Dockerfile` (копия конфига — уже
  generic), `deploy/deploy.sh` (смоук-чек netdata), `deploy/RUNBOOK.md`
  (генерация htpasswd, раздел мониторинга), `frontend/templates/base.html` +
  `frontend/static/js/profile.js` (или точечный модуль — design §3),
  `.gitignore` (htpasswd).
- **Спеки:** новая `openspec/specs/monitoring/` (после архивации), дельта
  navigation (+1 Requirement), дельта deploy (MODIFIED «Лимиты памяти»).
- **Данные:** БД не меняется — миграций нет; новый маунт хоста — только ro
  (`/proc`, `/sys`, `docker.sock`).
- **Ресурсы:** +256m лимит; суммарно 1.41 GB при 3.9 GB хоста (design §5).
- **Пользователи:** для PE/анона — ничего не меняется (пункт скрыт, /netdata/
  без кредов — 401); для owner — новый пункт сайдбара.

## Risks

- **docker.sock в контейнер** — расширяемая поверхность: смягчение — маунт
  строго `:ro` (только чтение метрик, урок R6/PLAN-R7), порт не публикуется,
  доступ за basic auth owner. Альтернатива без docker.sock (cgroup-маунты)
  дает неполные метрики контейнеров — принято осознанно (design §4).
- **Неполные метрики дисков (HDD) в контейнере** — проверяется смоуком
  стенда (1.2) и приемкой Заказчика на проде (2.2); при пробеле — докрутка
  маунтов тем же пакетом до приемки (эскалация в REPORT).
- **Рассинхрон htpasswd с паролем wiki-owner** — креды basic auth задаются
  Заказчиком отдельно (не читаются из БД wiki); смена пароля в wiki не
  меняет доступ к /netdata/ — осознанное ограничение, зафиксировано в
  design §2 и RUNBOOK.
- **RAM Netdata** — стоковый образ ~150–300 MB; лимит 256m по вводным;
  факт-замер после подъема (задача 1.1, урок PLAN-R7 «вес меряем по факту»);
  при стабильном превышении — эскалация Заказчику до прод-выкатки.
