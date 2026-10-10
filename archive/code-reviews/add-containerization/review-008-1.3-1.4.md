# Ревью задач 1.3 + 1.4: compose-топология прода и стенда

- **Reviewer-Delegation:** deleg_23caa03a
- **Change:** add-containerization (ЭТАП 1), дифы: 1.3+1.4 в коммите d27c98b, фикс 7065a71 (nginx-маунт той же глубиной); ревью задним числом по живым артефактам (ревьюер — не автор)
- **Дата:** 2026-10-03
- **Боевой факт учтен:** переключение прода 2.4 выполнено на этом файле (прод на контейнерах с 2026-10-03), смоук green

## Проверено (факты)

**compose.yaml (1.3) — код + `docker compose config` + живой инспекция боевого стека:**
- именованный том `wiki-data`: app RW `/data` (DB_PATH=/data/wiki.db, AVATARS_DIR=/data/avatars), живой inspect: RW=true ✓
- TLS bind-mount `/etc/nginx/ssl/ekotov-wiki.{crt,key}` ro у nginx (живой inspect: оба bind, RW=false) ✓
- SECRET_KEY только из deploy/.env: `${SECRET_KEY:?...}` — живая проба без env: интерполяция падает с сообщением «создайте deploy/.env» (fail-closed); deploy/.env существует, chmod 600, `.env` в .gitignore ✓
- mem_limit: живой inspect боевых контейнеров — app 536870912 (512m), nginx 67108864 (64m) ✓
- logging json-file 10m×3 на обоих сервисах (живой inspect LogConfig) ✓
- порт публикует только nginx: `${NGINX_PORT:-10443}:10443`; app портов не имеет (живой inspect: только внутренний 8377/tcp; nginx 0.0.0.0:10443->10443) ✓
- restart: unless-stopped на обоих (живой inspect RestartPolicy) ✓
- healthcheck app — python-urllib без curl, ровно формула design §1; depends_on nginx→app `condition: service_healthy` (compose config) ✓; оба боевых контейнера (healthy) ✓
- **фикс 7065a71:** nginx-маунт изменен `wiki-data:/data/avatars:ro` → `wiki-data:/data:ro`. Корректность: alias `/data/avatars/` в nginx-конфиге образа при маунте тома на /data резолвится в `<том>/avatars` = тот же каталог, что AVATARS_DIR app — дефект 404 при непустых данных устранен (смоук после фикса в commit-message: avatars/1.png=200, 502=0). Регрессий для app нет: маунт app (`wiki-data:/data` RW) не менялся; nginx получил ro только на весь том — запись app не затрагивает. Тот же паттерн подтвержден живым inspect боевого nginx (Destination=/data, Mode=ro)

**compose.test.yaml (1.4) — код + живой подъем стенда в ходе этого ревью:**
- те же образы, что прод (`${APP_IMAGE:-ekotov-wiki/app:local}` / frontend), та же топология nginx→app→том, healthcheck/depends_on/logging идентичны прод-файлу ✓
- tmpfs `/data:size=256m,mode=1777` у app (данные исчезают при down -v) ✓
- порт 8443: `${TEST_NGINX_PORT:-8443}:10443` — не пересекается с продом 10443/10444 ✓
- TEST_SECRET_KEY с дефолтом — продовый ключ не нужен ✓
- файл автономен (name: wiki-test, свой volume avatars-test) ✓
- **живой прогон этого ревью:** up -d → app healthy, health через nginx 200, /login 200; схема+seed+миграции (см. review-009); down -v — контейнеров/томов нет, 8443 закрыт ✓
- факт приема: через стенд прошли 2.1 (репетиции), 2.2 (e2e 8 passed), CI e2e-job (run 37160534481 на HEAD 762d57c: e2e ✓ 57s) ✓

## Соответствие спеке/дизайну

Источник: tasks.md 1.3/1.4, design §1/§3/§6, specs/deploy/spec.md (FR-65/66/67/73/74, NFR-10/11). Пункты MUST покрыты (см. выше). Негативные сценарии: «app недоступен снаружи» ✓ (порт не опубликован), «latest запрещен» ✓ (дефолты `:local`, боевое тегирование p11-r1), «Временный том стенда не трогает прод-данные» ✓ (tmpfs + проект wiki-test, прод-том ekotov-wiki_wiki-data не задет).

Замечания (minor, не блокируют):
1. **minor** (compose.test.yaml:74): avatars-маунт стенда расходится с app-хранилищем — nginx читает volume `avatars-test:/data/avatars:ro`, а app пишет аватары в tmpfs `/data/avatars` (том avatars-test при этом пуст всегда). Следствие: аватар, загруженный через app на стенде, nginx по `/avatars/*` не отдаст (404). Сейчас не проявляется (e2e аватары не гоняет, том одноразовый), но это тот же класс ошибки глубины/хранилища, что 7065a71, и отступление от «топология стенда воспроизводит прод» в аватар-аспекте. Рекомендация: отдельной chore-задачей выровнять хранилище (общий named volume RW для app + ro для nginx, как в проде).
2. **minor** (compose.test.yaml:70-73): стенд требует хостовые `/etc/nginx/ssl/*` — на чистой машине файлы нужно создать; компенсируется self-signed-шагом в flow.yml/e2e/README, зафиксировано в шапке.

## Вердикт: approve
