# HW-AUDIT: сырые данные (разделы 1–4) — 2026-10-28

Сбор фактов, Флоу 4, роль devops. **Read-only**: ни одной записи/рестарта/prune на проде не выполнено; 3x-ui и game-portal — только inspect/stats/ps. Отчет по командам, раздел 5 (анализ) — за ПМ.
Сборка: 3 среза `docker stats --no-stream` с интервалом ~60 с (06:42:23 / 06:43:25 / 06:44:27 UTC, 2026-10-28).

---

## 1. Инвентаризация хоста

```
$ date       → Wed Oct 28 06:41:28 UTC 2026
$ uname -a   → Linux r1254098 6.8.0-142-generic #142-Ubuntu SMP PREEMPT_DYNAMIC Wed Sep  2 14:24:27 UTC 2026 x86_64
$ cat /etc/os-release → Ubuntu 24.04.4 LTS (Noble)
$ uptime     → up 20 days, 9:16, load average: 0.41, 0.17, 0.12
```

### CPU
```
$ nproc → 4
$ grep -c ^processor /proc/cpuinfo → 4
$ grep 'model name' /proc/cpuinfo | head -1
  Intel(R) Xeon(R) Gold 6148 CPU @ 2.40GHz
```

### RAM / swap
```
$ free -h
               total        used        free      shared  buff/cache   available
Mem:           7.8Gi       2.6Gi       1.3Gi       2.0Mi       4.2Gi       5.2Gi
Swap:             0B          0B          0B
$ swapon --show → (пусто; swap отключен)
```
**Факт:** swap отсутствует — при исчерпании RAM только OOM-killer.

### Диски
```
$ df -h
Filesystem      Size  Used Avail Use% Mounted on
tmpfs           795M  2.0M  793M   1% /run
/dev/sda1       193G   33G  161G  17% /
tmpfs           3.9G     0  3.9G   0% /dev/shm
tmpfs           5.0M     0  5.0M   0% /run/lock
/dev/sda16      881M  194M  626M  24% /boot
/dev/sda15      105M  6.2M  99M   6%  /boot/efi
tmpfs           795M  16K  795M   1% /run/user/0
tmpfs           795M  28K  795M   1% /run/user/1000

$ df -i (корень) → /dev/sda1: Inodes 26 083 328, IUsed 714 341, IFree 25 368 987 (3%)
```

### Версии docker/compose
```
$ docker version → Client/Server: Docker Engine - Community 29.8.2 (API 1.56, go1.26.8, git 7fc2dff)
  containerd v2.3.6 · runc 1.5.1 · docker-init 0.19.0 · Experimental: false
$ docker compose version → Docker Compose version v5.6.0
$ docker-compose (legacy) → command not found
$ docker info → Containers: 10 (running 9) · Images: 194 · StorageDriver: overlayfs · Cgroup: v2 · NCPU 4 · MemTotal 7.755 GiB
```

---

## 2. Снимки потребления: docker stats (3 среза × 60 с)

```
$ docker stats --no-stream (срез 1, 06:42:23 UTC)
NAME                        CPU %     MEM USAGE / LIMIT     MEM %     NET I/O          BLOCK I/O       PIDS
ekotov-wiki-par-nginx-1     0.00%     7.922MiB / 64MiB      12.38%    3.31MB / 4.83MB  803kB / 8.19kB  5
ekotov-wiki-par-weather-1   0.23%     36.59MiB / 128MiB     28.58%    980B / 126B      6.47MB / 0B     6
ekotov-wiki-par-backup-1    0.00%     11.84MiB / 64MiB      18.51%    1.11kB / 126B    680kB / 1.16MB  1
ekotov-wiki-par-images-1    0.21%     37.07MiB / 128MiB     28.96%    1.02kB / 126B    8.24MB / 0B     6
ekotov-wiki-par-search-1    0.22%     35.53MiB / 512MiB     6.94%     2.38kB / 1.2kB   7.6MB / 0B      6
ekotov-wiki-par-app-1       0.29%     41.03MiB / 512MiB     8.01%     2.63MB / 2.09MB  6.52MB / 49.2kB 6
game-portal                 0.00%     21.18MiB / 7.755GiB   0.27%     1.84MB / 11.2MB  709kB / 0B      11
ekotov-wiki-par-video-1     0.26%     40.69MiB / 512MiB     7.95%     84.3kB / 2MB     32.5MB / 0B     7
3x-ui                       2.31%     165.4MiB / 7.755GiB   2.08%     0B / 0B          51.2MB / 27.4GB 35

(срез 2, 06:43:25)
ekotov-wiki-par-nginx-1     0.00%  7.922MiB/64MiB   weather 0.27% 36.59MiB  backup 0.00% 11.84MiB
ekotov-wiki-par-images-1    0.26%  37.07MiB         search  0.25% 35.53MiB  app   0.22% 41.03MiB
game-portal                 0.00%  21.18MiB         video   0.31% 40.69MiB  3x-ui 4.29% 175.5MiB CPU 4.29%

(срез 3, 06:44:27)
ekotov-wiki-par-nginx-1     0.00%  7.922MiB/64MiB   weather 0.27% 36.59MiB  backup 0.00% 11.84MiB
ekotov-wiki-par-images-1    0.29%  37.07MiB         search  0.23% 35.53MiB  app   0.31% 41.03MiB
game-portal                 0.00%  21.18MiB         video   0.30% 40.69MiB  3x-ui 1.76% 176.8MiB
```

**Сводка по 3 срезам (все срезы стабильны, пиков не видно — см. сноску):**

| Контейнер | CPU % (мин–макс) | MEM (стабильно) | MEM % лимита | BLOCK I/O write (накопл.) |
|---|---|---|---|---|
| ekotov-wiki-par-nginx-1 | 0.00 | 7.92 MiB | 12.4% от 64 MiB | 8 kB |
| ekotov-wiki-par-weather-1 | 0.23–0.27 | 36.59 MiB | 28.6% от 128 MiB | 0 B |
| ekotov-wiki-par-backup-1 | 0.00 | 11.84 MiB | 18.5% от 64 MiB | 1.16 MB |
| ekotov-wiki-par-images-1 | 0.21–0.29 | 37.07 MiB | 29.0% от 128 MiB | 0 B |
| ekotov-wiki-par-search-1 | 0.22–0.25 | 35.53 MiB | 6.9% от 512 MiB | 0 B |
| ekotov-wiki-par-app-1 | 0.22–0.31 | 41.03 MiB | 8.0% от 512 MiB | 49 kB |
| ekotov-wiki-par-video-1 | 0.26–0.31 | 40.69 MiB | 8.0% от 512 MiB | 0 B |
| **итого стек ekotov-wiki-par (running)** | ~1.3% (≈0.05 ядер) | **≈210.7 MiB** | 11% от суммы лимитов 1.92 GiB | — |
| game-portal | 0.00 | 21.18 MiB | 0.27% (лимита нет) | ~0 |
| 3x-ui | 1.76–4.29 (0.05–0.17 ядра) | 165.4–176.8 MiB | 2.1–2.2% (лимита нет) | **27.4 GB write** |

Сноска: срезы сделаны в 06:42–06:44 UTC (ночная низкая нагрузка). Пики (бэкап-джоб, ffmpeg в video, xray-трафик 3x-ui) этой выборкой не покрыты — для вердиктов о пиках нужны длительные метрики (netdata контейнер остановлен, см. §4).

---

## 3. Диск: docker system df, логи, volumes, journald

### docker system df
```
$ docker system df
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          194       77        6.888GB   1.31GB (19%)
Containers      10        9         1.216GB   1.216GB (99%)
Local Volumes   5         4         30.56MB   190.9kB (0%)
Build Cache     392       10        4.78GB    2.452GB
```

**Ключевое (перекрестная проверка по `docker system df -v`):**
- 194 образа при 77 активных: 36 тегов frontend, 36 app, 34 search, 34 backup, 27 images, 11 weather, 6 video — накопление артефактов релизных волн (p15-*, r8-*, p12-*, p23-*, p26-*, redesign-* и т.д.). Base-слои общие, но уникальная часть по ~1–2 MB/тег × сотни тегов + уникальные слои video/weather.
- Containers 1.216 GB — практически весь в **остановленном netdata** (rw-слой 1.22 GB, Exited(0) 2026-10-14; пересоздавался 2026-10-07). Активные контейнеры по 4–70 kB rw.
- Build Cache 4.78 GB (392 записей, от 3 недель до 33 часов; крупные записи 98–484 MB).
- Суммарно потенциально высвобождаемое docker'ом (только оценка, НЕ выполнялось): ~1.31 (dangling-часть образов) + ~1.22 (netdata rw) + ~2.45 (build cache) ≈ **5 GB**.

### Логи контейнеров
```
$ docker inspect --format '{{.HostConfig.LogConfig}}' <каждый контейнер>
```
| Контейнер | Драйвер | Ротация |
|---|---|---|
| все 8 ekotov-wiki-par-* | json-file | max-size 10m × max-file 3 (= ≤30 MB/контейнер) |
| 3x-ui | json-file | **{} — ротации НЕТ (безлимит)** |
| game-portal | json-file | **{} — ротации НЕТ (безлимит)** |

```
$ du -h <LogPath> каждого контейнера  → недоступно без sudo:
  "Permission denied" на /var/lib/docker/containers/<id>/*-json.log (файлы root:root)
  (sudo в окружении нет — фактические размеры лог-файлов не сняты)
```
Косвенный факт: rw-слой 3x-ui = 365 kB, но **BLOCK I/O write = 27.4 GB за 12 дней аптайма** (см. §2) — heavy writer; куда именно пишутся 27 GB (xray access/error логи в bind-маунте `/home/openclaw/3x-ui/db` или в json-лог) — без sudo не проверить, требует ручной проверки `/home/openclaw/3x-ui/db` (там `du` выполнить можно, см. ниже).

### Проверка bind-маунта 3x-ui (readable, без sudo)
```
$ du -sh /home/openclaw/3x-ui/db  (к выполнению отдельной командой; см. дополнение в конце, если снято)
```

### Volumes
```
$ du -sh /var/lib/docker/volumes/* → Permission denied (недоступно без sudo)
$ docker system df -v (Local Volumes space usage):
VOLUME NAME                     LINKS     SIZE
ekotov-wiki-par_weather-cache   1         1.466kB
ekotov-wiki-par_videos-data     2         12.42MB
ekotov-wiki-par_images-data     2         17.36MB
ekotov-wiki-par_wiki-data       7         594.8kB
ekotov-wiki_wiki-data           0         190.9kB   (старый том от некрас-деплоя, 0 контейнеров — кандидат на удаление)
```
Данные томов суммарно ~30.6 MB — диск не потребляют.

### Бэкапы (bind /var/backups/ekotov-wiki)
```
$ du -sh /var/backups/ekotov-wiki → 188M
$ ls -lh (tail) → wiki-pre-r7.1-gallery-*.db по 88–152K, от 2026-10-05 …
```

### journald / var/log
```
$ journalctl --disk-usage → "Archived and active journals take up 174.2M"
  (замечание: без membership в adm/systemd-journal видны не все журналы; полный размер может быть больше)
$ du -sh /var/log → 1.4G (частично; /var/log/private — Permission denied)
$ du -sh /var/log/* | sort -rh | head:
  1.2G  /var/log/journal
   81M  /var/log/btmp      (неудачные SSH-логины)
   72M  /var/log/btmp.1
   40M  /var/log/syslog.1
   20M  /var/log/auth.log.1
  9.7M  /var/log/sysstat
  7.3M  /var/log/auth.log
```

---

## 4. Периметр: все контейнеры хоста (10: 9 running + 1 exited)

```
$ docker ps -a --format '{{.Names}}' | sort
3x-ui / ekotov-wiki-par-{app,backup,images,nginx,search,video,weather}-1 / ekotov-wiki-par-netdata-1 / game-portal
```

### Полная таблица (docker inspect, срез 2026-10-28)

| Контейнер | Image | Статус (аптайм) | RestartPolicy | MemLimit | CPU limit | Healthcheck | Лог-ротация |
|---|---|---|---|---|---|---|---|
| ekotov-wiki-par-app-1 | ekotov-wiki/app:redesign-1b | running, up 33h, healthy | unless-stopped | **512 MiB** | нет (unlimited) | CMD urllib :8377/api/health, 30s | 10m×3 |
| ekotov-wiki-par-search-1 | ekotov-wiki/search:redesign-1b | running, up 33h, healthy | unless-stopped | **512 MiB** | нет | urllib :8378, 30s | 10m×3 |
| ekotov-wiki-par-video-1 | ekotov-wiki/video:p12-rich-1 | running, up 7d, healthy | unless-stopped | **512 MiB** | нет | urllib :8380, 30s | 10m×3 |
| ekotov-wiki-par-images-1 | ekotov-wiki/images:redesign-1b | running, up 33h, healthy | unless-stopped | 128 MiB | нет | urllib :8379, 30s | 10m×3 |
| ekotov-wiki-par-weather-1 | ekotov-wiki/weather:redesign-1b | running, up 33h, healthy | unless-stopped | 128 MiB | нет | urllib :8381, 30s | 10m×3 |
| ekotov-wiki-par-backup-1 | ekotov-wiki/backup:redesign-1b | running, up 33h, healthy | unless-stopped | 64 MiB | нет | heartbeat-файл, 60s | 10m×3 |
| ekotov-wiki-par-nginx-1 | ekotov-wiki/frontend:redesign-1b | running, up 33h, healthy | unless-stopped | 64 MiB | нет | wget https://127.0.0.1:10443/api/health, 30s | 10m×3 |
| ekotov-wiki-par-netdata-1 | netdata/netdata:stable | **exited (0) 2026-10-14**, up не с 2026-10-07 | unless-stopped | 256 MiB | нет | curl :19999, 30s | 10m×3 |
| game-portal | node:26-alpine | running, up 5d ( healthcheck: **нет**) | unless-stopped | **0 = нет лимита** | нет | **нет** | **нет ротации** |
| 3x-ui | ghcr.io/mhsanaei/3x-ui:latest | running, up 12d | unless-stopped | **0 = нет лимита** | нет | **нет** | **нет ротации** |

Монтирования/сеть:
```
3x-ui:        network=host (порт наружу напрямую); binds: /home/openclaw/3x-ui/db → /etc/x-ui (rw),
              /home/openclaw/3x-ui/cert → /root/cert (rw); cmd ./x-ui
game-portal:  network=ekotov-wiki-par_default; bind /home/openclaw/game-portal → /srv (ro);
              cmd node game-hub/server.mjs; published ports: {} (за nginx стека ekotov-wiki-par)
ekotov-wiki-par-nginx-1: ports ${NGINX_PORT:-10443}:10443; binds ssl crt/key, htpasswd, тома ro
```

### Лимиты из deploy/compose.yaml (источник конфигурации стека)
```
app 512m (FR-73) · search 512m (FR-73) · video 512m · images 128m · weather 128m ·
backup 64m · nginx 64m · netdata 256m (NFR-19)   — сумма 2.16 GiB
CPU-лимитов (cpus/nanocpus) и pids_limit НЕТ нигде; memswap не задан явно.
```

---

## Дополнения (выполнено тем же read-only проходом)

```
$ du -sh /home/openclaw/3x-ui/db → 5.6M
  (внутри: x-ui.db 272K + x-ui.db-wal 4.0M (растет, час записи) + system_metrics.gob 1.3M)
$ du -sh /home/openclaw/game-portal → 4.8M; /home/openclaw/3x-ui/cert → 4K
```
Bind-маунт 3x-ui мал (5.6M) — значит 27.4 GB write (§2) идут в json-лог контейнера или другое место образа/контейнера; точно локализовать без sudo нельзя (см. «Ограничения» п.5). Обратим внимание: json-лог 3x-ui без ротации — ввиду 27.4 GB write это главный подозреваемый на скрытый потребитель диска.

## Ограничения (недоступно без sudo — sudo в окружении нет)

1. Фактические размеры json-логов контейнеров (`/var/lib/docker/containers/*/-json.log`) — Permission denied; есть только конфиг ротации (см. §3).
2. `du` по `/var/lib/docker/volumes/*` — Permission denied; размеры томов взяты из `docker system df -v`.
3. Полный размер journald (системные юниты) — нужен adm/systemd-journal; оценка 174.2M может быть занижена.
4. `/var/log/private` — не читается.
5. Локализация 27.4 GB write у 3x-ui (json-лог vs xray-логи) — требует root.

## Короткая выжимка (для ПМ, раздел 5 не заменяет)

**Топ-потребители:**
- Диск: build cache 4.78 GB + неиспользуемые образы (~1.3–3+ GB: 117 неактивных тегов из 194) + rw-слой остановленного netdata 1.22 GB + `/var/log` 1.4G (journal 1.2G, btmp 153M) — суммарно порядок **7–8 GB** потенциально высвобождаемого на диске из занятых 33 GB.
- RAM: фактическое потребление всех контейнеров ~410 MiB из 7.8 GiB (стек ~210 MiB; 3x-ui ~170 MiB; game-portal 21 MiB) — RAM не дефицит. Зато **swap 0**.
- CPU: суммарно <1 ядра даже с 3x-ui (4 ядра доступно) — не дефицит.
- Аномалии: (а) 3x-ui пишет на диск ~2.3 GB/сут (27.4 GB за 12 дней) без ротации json-лога; (б) у 3x-ui и game-portal нет mem-лимитов, healthcheck'ов и ротации логов; (в) netdata контейнер остановлен 14 дней с 1.22 GB rw-слоя (мониторинг не работает, а планы требуют метрик пиков); (г) btmp 153 MB — интенсивный брутфорс SSH; (д) старый том `ekotov-wiki_wiki-data` (0 контейнеров).

**Что НЕ трогали:** все контейнеры, образы, тома, логи. Команды — только read: `inspect`, `stats --no-stream`, `system df`, `ps -a`, `du/df/free` на чтение.
