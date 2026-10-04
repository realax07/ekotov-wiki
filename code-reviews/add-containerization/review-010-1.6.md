# Ревью задачи 1.6 (независимое, ретро): deploy.sh v2 + фикс 95ee43a + RUNBOOK §7

- **Change:** add-containerization, диф задачи 1.6: 5ccdb89 (deploy-v2) + фикс 95ee43a (review-003)
- **Дата:** 2026-10-04
- **База ревью:** ветка add-microservices-full, HEAD 6c75aa1
- **Reviewer-Delegation: deleg_UNKNOWN**
- **Контекст:** заменяет ПМ-self-review-004 (нарушение SELF_REVIEW — не засчитано); закрывает J10-покрытие 1.6 задним числом. Все факты проверены кодом и живыми пробами, отчеты предыдущих ревью не принимались на веру.

## Проверено (факты)

**Синтаксис и каркас.** `bash -n` — OK. `set -euo pipefail` (deploy.sh:28). Границы
`git show 5ccdb89 --stat`: ровно 3 файла в `deploy/` (RUNBOOK.md, deploy-v1-systemd.sh
+185, deploy.sh). Выхода за границу задачи нет. Фикс 95ee43a: 2 файла
(deploy/deploy.sh +11/-3, review-003-1.6.md) — в границах.

**v1 сохранен дословно.** `git show 3bfb018:deploy/deploy.sh` vs
`deploy/deploy-v1-systemd.sh` → `diff -q` пуст (идентичны).

**Валидация тега (FR-72) — живые пробы** (изолированный клон /tmp, прод не тронут):
- без `RELEASE_TAG` → `[FAIL] … latest ЗАПРЕЩЕН (FR-72)`, rc=1;
- `RELEASE_TAG=latest` → rc=1 (тот же fail);
- charset-кейс: паттерн `*[!A-Za-z0-9._-]*` (стр.67–70) отвергает прочий мусор;
- в скрипте нигде не конструируется тег `latest`; `APP_IMAGE`/`FRONTEND_IMAGE`
  всегда `${BASE}:${RELEASE_TAG}` (стр.52–53).

**Порядок шагов.** 1 предусловия → 2 бэкап → 3 build → 4 миграция → 5 up →
6 смоук → 7 prune (стр.72–241). Миграция СТРОГО до up (шаг 4 < 5); пустой
`MIGRATE_MODULE` → шаг пропускается с журналом (стр.161–163); падение миграции
→ `fail` ДО up со ссылкой на бэкап (стр.158) — FR-70.

**Бэкап (FR-71).** Метод = design §6: python-модуль `sqlite3` `.backup` через
`docker exec -T` в контейнер app → `/tmp/.deploy-backup.db` → `compose cp`
наружу → `rm` временного → проверка размера `[ -s "${DB_BACKUP}" ]` (стр.125–131)
+ `du -h` в журнале. Аватары: tar `/data/avatars` тем же exec, fallback с
`mkdir -p` на пустом томе (стр.136–139). Без остановки стека; каждая ступень
с `|| fail`. Отсутствие контейнера app (первый деплой) → явный fail с
подсказкой RUNBOOK §7.3 (стр.113–115) — первый up по RUNBOOK, deploy.sh —
для обновлений; синхронно с документацией.

**DRY_RUN немутирующий — живой прогон.** В изолированном клоне:
`sg docker -c "DRY_RUN=1 RELEASE_TAG=probe-test SRC_DIR=<клон> BACKUP_DIR=<клон>/backup bash deploy/deploy.sh"`
→ exit 0, все 7 шагов напечатаны как `[DRY-RUN]`, финал «Ничего не изменено».
Проверка мутаций после прогона: BACKUP_DIR НЕ создан, контейнеров проекта
probe-test нет (`docker ps -a` — 0), образов `probe-test` нет. Кодом: все
мутации (mkdir, 2×docker build, up -d, image prune) идут через `run()` →
в dry-run только печать (стр.60, 110, 145–146, 167, 237–241); exec-шаги
(бэкап, смоук) — за `exit 0` dry-run-ветки (стр.189) либо в `else`
не-dry-run (стр.156).

**Матричный фикс 95ee43a (M-1, FR-70) — код и живая проба.**
- Код: строка 155–156 — `env APP_IMAGE="${APP_IMAGE}" FRONTEND_IMAGE="${FRONTEND_IMAGE}" ${COMPOSE} run --rm --no-deps …` — env на строке run миграции присутствует; до фикса (git show) env отсутствовал.
- Живая проба: `docker compose -f deploy/compose.yaml config` без env →
  `image: ekotov-wiki/app:local` / `frontend:local` (дефолт, подтверждена
  маскировка дефекта); с `APP_IMAGE=…:p11-r1 FRONTEND_IMAGE=…:p11-r1` →
  `image: ekotov-wiki/app:p11-r1` / `frontend:p11-r1`. Фикс резолвит дефолт.
- m-3: `docker image prune -f || echo WARN` (стр.240) — отказ prune не роняет
  exit 0 успешного деплоя; в dry-run печатается dry-run-строка (стр.238).

**RUNBOOK §7 — синхронность со скриптом.** §7.6: канонический скрипт
deploy.sh (v2), v1 сохранен для отката; запуск
`sudo RELEASE_TAG=<метка> bash deploy/deploy.sh`; перечень шагов §7.6
(предусловия → бэкап без остановки: БД sqlite3-.backup через exec + compose
cp, аватары tar /data/avatars, пути `/var/backups/ekotov-wiki/wiki-pre-<release>-….db` /
`avatars-pre-…-<время>.tar` → build → one-shot run СТРОГО до up → up -d →
смоук health/login/статика/avatars + stale-DNS c fallback restart nginx +
smoke_static.py → prune) — 1:1 со скриптом. Имена переменных
RELEASE_TAG/MIGRATE_MODULE, запрет latest (FR-72), обязательный DRY_RUN=1
перед первым боевым — синхронно. Расхождений скрипт↔RUNBOOK не найдено.

**Спека/дизайн.** tasks.md 1.6 ([x]) — все пункты покрыты (метод бэкапа §6,
dry-run обязателен, смоук со stale-DNS + fallback, теги по релизу, latest
запрещен, RUNBOOK синхронно). FR-70 (one-shot до up, падение прерывает),
FR-71 (бэкап метод/путь зафиксированы в RUNBOOK), FR-72 (теги, откат по
предыдущему тегу — финальный блок скрипта стр.251–253 + RUNBOOK §7.6) —
выполнены. NFR-9 (переходная схема портов) — вне диффа 1.6, механика в
compose/RUNBOOK §7.3–7.4; NFR-11 (ротация json-file 10m×3) — в compose.yaml
(стр.47–51, 79–83) присутствует.

**Живой факт прода (только чтение).** Прод работает на этом стеке:
`docker ps` → `ekotov-wiki-app-1` (ekotov-wiki/app:p11-r1, Up 9h, healthy),
`ekotov-wiki-nginx-1` (ekotov-wiki/frontend:p11-r1, Up 9h, healthy).
Смоук прода: /api/health 200, /login 200, /avatars/ 403 (не 502).
Скрипт буква-в-букву отвечает схеме, на которой прод поднят.

## Замечания (minor, не блокируют)

- **m-a:** комментарий `run()` (стр.58–59) упоминает хелпер `runq`, которого
  в скрипте нет (фактически не-dry-run exec-шаги — за `exit 0` dry-run-ветки).
  Документационный дрейф; на поведение не влияет.
- **m-b:** строка 226 `ok "Логи nginx: 502 не обнаружено"` печатается и после
  WARN о найденных 502 (стр.222–225) — косметика журнала.
- (Унаследовано, принято в 003/004) dry-run-эхо миграции (стр.118, 153) не
  дословно повторяет боевые команды — состав шагов показан, точные команды
  проверены реальным прогоном на стенде/проде (2.1–2.4).

## Соответствие спеке/дизайну

- tasks.md 1.6 — все требования выполнены, включая синхронный RUNBOOK §7.6.
- design §1 (stale-DNS контроль, fallback restart nginx — стр.208–220) и §6
  (метод бэкапа exec, one-shot миграция, откат по тегам) — реализованы.
- FR-70/71/72 — выполнены (см. выше, живые пробы).
- NFR-9/11 — вне диффа 1.6; в целевой конфигурации присутствуют.

## Вердикт: approve

Задача 1.6 (5ccdb89 + фикс 95ee43a) соответствует спеке и дизайну; замечания
review-003 (M-1, m-3) подтверждены закрытыми кодом и живой пробой compose
config; RUNBOOK §7 синхронен скрипту; прод работает на выпущенном из этого
скрипта стеке p11-r1. Minor-замечания (m-a, m-b) — в backlog, не блокируют.
