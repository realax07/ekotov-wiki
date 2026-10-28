# HW-cleanup: чистка диска + ротация логов 3x-ui

Исполнение раздела 3 плана `PLAN-hw-audit.md` (approved Заказчиком). Выполнено: 2026-10-28, роль devops, Флоу 4. Исполнитель: openclaw (группа docker, без sudo).

**Итог коротко:** высвобождено **~8.5 GB** (df: 33G → 27G used, 17% → 14%). Контейнер 3x-ui пересоздан с лимитом json-лога (50m×3); **ВПН работает** (порты 443/2096/3482 слушаются, xray 26.10.10 запущен, RestartCount=0, ≥60с без рестарт-лупа). Два пункта — под sudo Заказчика (см. §4).

## 1. Диагноз по 3x-ui: исправляю ошибку аудита

Аудит (hw-audit-2026-10-26.md, §4) предположил «лог контейнера ~2.3 GB/сут без ротации». Проверка фактами:

| Проверка | Факт |
|---|---|
| json-лог контейнера (`LogPath`) | **56 KB** — не растет |
| rw-слой контейнера (`docker ps -s`) | 365 KB |
| `/var/log/x-ui` внутри контейнера | 164 KB |
| volume-маунты (db, cert на хосте) | 5.6 MB суммарно |
| docker stats | **Net**IO 51MB/**27.6GB** (сеть — трафик VPN), BlockIO ~0 |

Источник «27.4 GB записи на диск» в аудите — это **сетевой** счетчик (NetIO за 12 дней), а не дисковая запись. Роста ~2.3 GB/сут на диске 3x-ui не создает; на момент аудита лог-файл локализовать не удалось (§6 аудита) — теперь локализован и он пуст. Диск не был «единственной горящей статьей» по вине 3x-ui; фактическую массу дало docker-накопительство (§2 ниже).

Тем не менее `LogConfig` был `json-file` **без лимитов** — риск класса «один ошибочный спам-лог забьет диск» оставался. Применен approved-хардинг (§3).

## 2. Часть 1 — чистка диска (approved)

До/после:

| Метрика | До | После |
|---|---|---|
| df `/` | 33G used / 193G (17%) | **27G used / 193G (14%)** |
| Images (system df) | 194 шт, 6.888GB | 17 шт, 3.425GB |
| Containers | 10 шт, 1.216GB (99% reclaimable) | 9 шт, 328KB |
| Build Cache | 392 записи, 4.78GB | 183 записи, 2.33GB (in-use текущими образами) |
| Volumes | 5 | 4 |

Состав:

1. `docker builder prune -f` — **2.452 GB** (совпало с оценкой аудита).
2. `docker image prune -a -f --filter "until=72h"` — **3.03 GB**, 179 тегов (полный список ниже). Все старые релизные теги p11–p26/r7–r8/stand/test/local; running-контейнеры не затронуты (после чистки все 9 Up, стек ekotov-wiki-par — healthy, game-portal Up 5 days).
3. `docker rm ekotov-wiki-par-netdata-1` — policy `unless-stopped` (≠ always, критерий плана выполнен), Exited(0) с 2026-10-14, rw-слой **~1.22 GB**. При необходимости возвращается `docker compose -p ekotov-wiki-par up -d netdata` (после `git pull`).
4. `docker volume rm ekotov-wiki_wiki-data` — брошенный том проекта v1-эпохи (создан 2026-10-03), 0 ссылающихся контейнеров (проверено `docker ps -a --filter volume=` перед удалением). Живой том прода — `ekotov-wiki-par_wiki-data`, не тронут.

<details><summary>Удаленные образы (179 тегов)</summary>

```
alpine:3
alpine:latest
ekotov-wiki/app:check
ekotov-wiki/app:local
ekotov-wiki/app:p11-r1
ekotov-wiki/app:p12-rc1
ekotov-wiki/app:p12-rich-1
ekotov-wiki/app:p12-rich-2
ekotov-wiki/app:p14-responsive-1
ekotov-wiki/app:p14-responsive-2
ekotov-wiki/app:p15-wiki-1
ekotov-wiki/app:p15-wiki-2
ekotov-wiki/app:p15-wiki-3
ekotov-wiki/app:p15-wiki-4
ekotov-wiki/app:p15-wiki-5
ekotov-wiki/app:p15-wiki-6
ekotov-wiki/app:p15-wiki-7
ekotov-wiki/app:p15-wiki-7-orig-20261016
ekotov-wiki/app:p15-wiki-8
ekotov-wiki/app:p15-wiki-9
ekotov-wiki/app:p15s-a
ekotov-wiki/app:p23-fastline-1
ekotov-wiki/app:p23-fastline-2
ekotov-wiki/app:p26-games-1
ekotov-wiki/app:p26-games-2
ekotov-wiki/app:r7-netdata
ekotov-wiki/app:r7.1-gallery
ekotov-wiki/app:r8-polish
ekotov-wiki/app:r8-polish-2
ekotov-wiki/app:r8-polish-3
ekotov-wiki/app:redesign-1
ekotov-wiki/app:stand-1.4
ekotov-wiki/app:v2-livecheck
ekotov-wiki/app:video-1
ekotov-wiki/app:video-1.1
ekotov-wiki/app:weather-1
ekotov-wiki/backup:local
ekotov-wiki/backup:p12-rc1
ekotov-wiki/backup:p12-rich-1
ekotov-wiki/backup:p12-rich-2
ekotov-wiki/backup:p14-responsive-1
ekotov-wiki/backup:p14-responsive-2
ekotov-wiki/backup:p15-wiki-1
ekotov-wiki/backup:p15-wiki-2
ekotov-wiki/backup:p15-wiki-3
ekotov-wiki/backup:p15-wiki-4
ekotov-wiki/backup:p15-wiki-5
ekotov-wiki/backup:p15-wiki-6
ekotov-wiki/backup:p15-wiki-7
ekotov-wiki/backup:p15-wiki-7-orig-20261016
ekotov-wiki/backup:p15-wiki-8
ekotov-wiki/backup:p15-wiki-9
ekotov-wiki/backup:p15s-a
ekotov-wiki/backup:p23-fastline-1
ekotov-wiki/backup:p23-fastline-2
ekotov-wiki/backup:p26-games-1
ekotov-wiki/backup:p26-games-2
ekotov-wiki/backup:r7-netdata
ekotov-wiki/backup:r7.1-gallery
ekotov-wiki/backup:r8-polish
ekotov-wiki/backup:r8-polish-2
ekotov-wiki/backup:r8-polish-3
ekotov-wiki/backup:redesign-1
ekotov-wiki/backup:stand-1.4
ekotov-wiki/backup:test
ekotov-wiki/backup:video-1
ekotov-wiki/backup:video-1.1
ekotov-wiki/backup:weather-1
ekotov-wiki/frontend:check
ekotov-wiki/frontend:local
ekotov-wiki/frontend:p11-r1
ekotov-wiki/frontend:p12-rc1
ekotov-wiki/frontend:p12-rich-1
ekotov-wiki/frontend:p12-rich-2
ekotov-wiki/frontend:p14-responsive-1
ekotov-wiki/frontend:p14-responsive-2
ekotov-wiki/frontend:p15-wiki-1
ekotov-wiki/frontend:p15-wiki-2
ekotov-wiki/frontend:p15-wiki-3
ekotov-wiki/frontend:p15-wiki-4
ekotov-wiki/frontend:p15-wiki-5
ekotov-wiki/frontend:p15-wiki-6
ekotov-wiki/frontend:p15-wiki-7
ekotov-wiki/frontend:p15-wiki-7-orig-20261016
ekotov-wiki/frontend:p15-wiki-8
ekotov-wiki/frontend:p15-wiki-9
ekotov-wiki/frontend:p15s-a
ekotov-wiki/frontend:p23-fastline-1
ekotov-wiki/frontend:p23-fastline-2
ekotov-wiki/frontend:p26-games-1
ekotov-wiki/frontend:p26-games-2
ekotov-wiki/frontend:r7-netdata
ekotov-wiki/frontend:r7.1-gallery
ekotov-wiki/frontend:r8-polish
ekotov-wiki/frontend:r8-polish-2
ekotov-wiki/frontend:r8-polish-3
ekotov-wiki/frontend:redesign-1
ekotov-wiki/frontend:stand-1.4
ekotov-wiki/frontend:v2-livecheck
ekotov-wiki/frontend:video-1
ekotov-wiki/frontend:video-1.1
ekotov-wiki/frontend:weather-1
ekotov-wiki/images:local
ekotov-wiki/images:p12-rich-1
ekotov-wiki/images:p12-rich-2
ekotov-wiki/images:p15-wiki-1
ekotov-wiki/images:p15-wiki-2
ekotov-wiki/images:p15-wiki-3
ekotov-wiki/images:p15-wiki-4
ekotov-wiki/images:p15-wiki-5
ekotov-wiki/images:p15-wiki-6
ekotov-wiki/images:p15-wiki-7
ekotov-wiki/images:p15-wiki-7-orig-20261016
ekotov-wiki/images:p15-wiki-8
ekotov-wiki/images:p15-wiki-9
ekotov-wiki/images:p15s-a
ekotov-wiki/images:p23-fastline-1
ekotov-wiki/images:p23-fastline-2
ekotov-wiki/images:p26-games-1
ekotov-wiki/images:p26-games-2
ekotov-wiki/images:r7.1-gallery
ekotov-wiki/images:r8-polish
ekotov-wiki/images:redesign-1
ekotov-wiki/images:test
ekotov-wiki/images:video-1
ekotov-wiki/images:video-1.1
ekotov-wiki/images:weather-1
ekotov-wiki/search:local
ekotov-wiki/search:p12-rc1
ekotov-wiki/search:p12-rich-1
ekotov-wiki/search:p12-rich-2
ekotov-wiki/search:p14-responsive-1
ekotov-wiki/search:p14-responsive-2
ekotov-wiki/search:p15-wiki-1
ekotov-wiki/search:p15-wiki-2
ekotov-wiki/search:p15-wiki-3
ekotov-wiki/search:p15-wiki-4
ekotov-wiki/search:p15-wiki-5
ekotov-wiki/search:p15-wiki-6
ekotov-wiki/search:p15-wiki-7
ekotov-wiki/search:p15-wiki-7-orig-20261016
ekotov-wiki/search:p15-wiki-8
ekotov-wiki/search:p15-wiki-9
ekotov-wiki/search:p15s-a
ekotov-wiki/search:p23-fastline-1
ekotov-wiki/search:p23-fastline-2
ekotov-wiki/search:p26-games-1
ekotov-wiki/search:p26-games-2
ekotov-wiki/search:r7-netdata
ekotov-wiki/search:r7.1-gallery
ekotov-wiki/search:r8-polish
ekotov-wiki/search:r8-polish-2
ekotov-wiki/search:r8-polish-3
ekotov-wiki/search:redesign-1
ekotov-wiki/search:stand-1.4
ekotov-wiki/search:test
ekotov-wiki/search:video-1
ekotov-wiki/search:video-1.1
ekotov-wiki/search:weather-1
ekotov-wiki/video:local
ekotov-wiki/video:regress3-verify
ekotov-wiki/video:test
ekotov-wiki/video:video-1
ekotov-wiki/video:video-1.1
ekotov-wiki/weather:p12-rich-1
ekotov-wiki/weather:p12-rich-2
ekotov-wiki/weather:p23-fastline-1
ekotov-wiki/weather:p23-fastline-2
ekotov-wiki/weather:p26-games-1
ekotov-wiki/weather:p26-games-2
ekotov-wiki/weather:redesign-1
ekotov-wiki/weather:test
ekotov-wiki/weather:weather-1
hello-world:latest
netdata-stub:local
nginx:alpine
python:3-alpine
python:3.12-slim
wt-p26-nginx-fixed:latest
```

</details>

## 3. Часть 2 — 3x-ui: минимальный recreate по logging (approved)

Дифф `/home/openclaw/3x-ui/docker-compose.yml` — единственный блок `logging`, больше ничего (образ/порты/env/байнды сверены `docker inspect` до recreate — без изменений):

```yaml
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "3"
```

`docker compose up -d` → `Recreated` → `Started`. Лимит подтвержден: `LogConfig = {"max-file":"3","max-size":"50m"}`. Лимит «спящего» лога: ≤150 MB навсегда. Прежний 56KB-лог удален демоном вместе со старым контейнером.

**Проверка ВПН после recreate:**

| Проверка | Факт |
|---|---|
| Контейнер | `Up`, образ `ghcr.io/mhsanaei/3x-ui:latest` (тот же локальный sha, pull не выполнялся) |
| RestartCount | **0** (нет рестарт-лупа), ≥60с стабильно |
| Порты (ss -tln, host-сеть) | 443, 2096, 3482 — **идентичны до/после** (diff пуст) |
| xray | `Xray 26.10.10 started`, процесс жив; REALITY-ворнинги по vk-таргетам — штатные, были и до |
| Панель | HTTP 404 на `http://127.0.0.1:3482/` (секретный webBasePath — корень отвечает 404 штатно); 2096 = sub-server |
| Остальной прод | стек ekotov-wiki-par ×7 healthy, :10443 не затронут |

Откат не потребовался.

## 4. Команды для Заказчика под sudo (не выполнено агентом)

- `sudo -n` недоступен, journalctl без sudo очистил 0B (архивные журналы системного journal недоступны):
  ```
  sudo journalctl --vacuum-size=300M
  ```
- btmp (84.5 MB на момент чистки; подбор SSH — см. аудит §5 про fail2ban):
  ```
  sudo truncate -s 0 /var/log/btmp
  ```

## 5. Остаточное

- Build Cache 2.33 GB — in-use актуальными образами; агрессивный `builder prune -a` не применялся (вне approved).
- Images reclaimable 1.33GB (38%) — промежуточные слои активных образов, не трогать.
- Рекомендации аудита вне скоупа (swapfile, healthcheck 3x-ui/game-portal, лимиты) — остаются в плане.
