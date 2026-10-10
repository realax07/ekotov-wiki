# Code-review 1.2 — Devops: сервис netdata в compose (change add-netdata-monitoring)

- **Дата:** 2026-10-05
- **Ревьюер:** независимый code_reviewer (auto-edit, итерация review-002)
- **Reviewer-Delegation:** deleg_56063e79
- **Correlation:** 54e97c3b731c4e55b9d65af3470244a7
- **Диф:** `aeaa447` (deploy/compose.yaml +42, deploy/compose.test.yaml +34; итого +76)
- **Арбитры:** tasks.md 1.2 (FR-75, NFR-19; NFR-10 паритет), design.md §1/§4/§5, requirements.md дельта monitoring
- **Provenance:** ревью на SHA `aeaa44758a9425ace2efa19539daa718f086efa2` (diff sha256 `5a62cb62…b80bd`); head на момент ревью `8f96d4b`; дифф входит в head, пост-диффных правок файлов нет; flow_check: OK

## Вердикт: **ОДОБРИТЬ** (approve; blocker 0, major 0, minor 1)

## Таблица замечаний

| # | Серьезность | Файл:строка | Замечание | Рекомендация |
|---|---|---|---|---|
| 1 | minor | deploy/compose.yaml:136 (compose.test.yaml:165) | `image: ${NETDATA_IMAGE:-netdata/netdata:stable}` — канал `stable` — подвижный тег: обновляется апстримом без изменения compose-файла (в отличие от digest-пина). Паттерн соответствует остальной части стека (все образы через env-дефолт, `latest` действительно запрещен FR-72 и не используется), риск минимален и покрывается healthcheck/порядком отката 2.2. | Не блокер. При желании — digest-пин `stable@sha256:…` в будущей полировке; в рамках 1.2 правку не требовать. |

## Первый круг — спека (tasks.md 1.2, design §1/§4/§5)

Дифф верифицирован `git show aeaa447`: оба compose-файла, +76 строк, вне зон ничего. Далее — независимая структурная валидация ревьюера: `yaml.safe_load` обоих файлов + 33 параметризованные проверки (не пересказ отчета dev):

- **Образ:** дефолт `netdata/netdata:stable` в обоих файлах, `latest` отсутствует (FR-72) — PASS.
- **mem_limit 256m** (NFR-19, design §5) — PASS в обоих файлах; сумма лимитов стека 1.41 GB / резерв хосту ≥ 2.4 GB сходится с design §5.
- **Порты НЕ публикуются:** ключа `ports` нет (паритет app/search, design §1, FR-75) — PASS.
- **Маунты — ровно 3, все ro:** `/proc:/host/proc:ro`, `/sys:/host/sys:ro`, `/var/run/docker.sock:/var/run/docker.sock:ro` (design §4) — PASS.
- **ENV:** `DOCKER_HOST=unix:///var/run/docker.sock`, `DISABLE_TELEMETRY=1` — PASS. Прокидывание DOCKER_HOST избыточно-безопасно: entrypoint образа (`packaging/docker/run.sh`) детектирует docker.sock и экспортирует DOCKER_HOST сам; явное значение делает конфиг самодокументированным.
- **Healthcheck:** `CMD curl -fsS http://127.0.0.1:19999/api/v1/info`, interval 30s / timeout 10s / retries 3 / start_period 30s — PASS. Паритет «самодостаточных» healthcheck app/search соблюден.
- **Logging json-file 10m×3, restart unless-stopped** — PASS, дословный паритет с search/backup.
- **Сеть:** сервис в дефолтной compose-сети без публикаций; nginx (1.3) сможет адресовать `http://netdata:19999` — соответствует design §1.
- **Паритет prod↔test (NFR-10):** структуры `services.netdata` ПОБАЙТОВО идентичны (`prod == test` на.safe_load) — PASS. Паритет ключей против search/backup: netdata ⊆ {их ключи} + healthcheck (у backup его нет по его роли — обоснованно, не дефект).
- Итого независимых проверок ревьюера: **33/33 PASS** (сверх 26 проверок dev).

## Обоснование curl-vs-wget — верифицировано по апстриму

ТЗ 1.2 писало «healthcheck (wget внутри образа)», design §5 — то же, с оговоркой «или curl…». Dev заменил wget→curl с обоснованием «Debian-based образ, встроенный health.sh использует curl». Проверка по первоисточникам (не по доверию):

1. `packaging/docker/health.sh` апстрима (master, прочитан ревьюером напрямую): `curl -sSL http://localhost:${PORT}/api/v1/info` — **curl подтвержден дословно**; endpoint и порт совпадают с healthcheck dev'а (тот же `/api/v1/info`).
2. Образ `netdata/netdata:stable` действительно Debian-based (манифест hub.docker.com), у образа есть собственный `HEALTHCHECK CMD /usr/sbin/health.sh` — т.е. curl в образе гарантирован как зависимость штатного механизма здоровья.
3. Встроенный HEALTHCHECK образа (interval 1m, без start_period) явным healthcheck'ом переопределяется — параметры dev'а (30s/10s/3/30s) разумны и консервативнее дефолта.

Вывод: замена — «разрешенная по ТЗ» ветка («иначе curl»), фактическая семантика совпадает с апстримной. Замечаний нет.

## Риск-чек: docker.sock:ro

- ro-флаг ограничивает контейнер от **записи в файл сокета**, но подключившийся к сокету процесс получает API docker daemon с корневыми полномочиями на хосте — это фундаментальное свойство docker.sock, не снимаемое ro. Компромисс **осознан в design**: §4 прямо фиксирует «docker.sock дает видимость всех контейнеров хоста — на этом VPS других контейнеров нет (факт RUNBOOK §1), риск принят и смягчен basic auth + непубликуемым портом»; урок R6/PLAN-R7 («строго ro, netdata НЕ управляет контейнерами») воспроизведен в комментарии диффа. Оценка: решение спеки легитимно, реализация ему соответствует. Замечаний к 1.2 нет; для будущей полировки (вне скоупа пакета) возможны docker-socket-proxy или netdata-коллектор без сокета — кандидат в BACKLOG, не в ревью.

## Что не проверено (вне зоны 1.2, по плану пакета)

- Живой подъем стенда, healthcheck в статусе healthy, фактический RAM-замер (`docker stats`) — docker ревьюеру недоступен; заявлено в 2.1/2.2 (RAM-замер — критерий задачи 1.2/2.2, эскалация до 1.5 при превышении).
- nginx-локации `/netdata` (401/301/200) — зона задачи 1.3.
- Проверка «ссылка сайдбара открывает дашборд» — 2.1.

## Соответствие границ

Зона записи соблюдалась: ревьюер менял только этот файл. tasks.md, спеки, код — не тронуты. Push запрещен, не выполнялся.
