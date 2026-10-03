# RUNBOOK — прод-окружение ekotov-wiki

Факты собраны командами 2026-09-26 (devops_agent, задача E9). Перед каждым деплоем — перепроверить раздел «Быстрая проверка фактов»: окружение может измениться.

## 1. Топология

```
Заказчик (браузер)
   │  https://194.58.34.122:10443  (TLS self-signed, подтверждение исключения)
   ▼
nginx :10443 (0.0.0.0 + [::])
   ├── location /static/  → alias /opt/ekotov-wiki/frontend/static/  (expires 7d, Cache-Control: public)
   └── location /         → proxy_pass http://127.0.0.1:8377
                                ▼
                     uvicorn (systemd: ekotov-wiki, user wiki)
                     127.0.0.1:8377, cwd=/opt/ekotov-wiki/backend
                                ▼
                     SQLite /var/lib/ekotov-wiki/wiki.db (владелец wiki)
```

## 2. Компоненты и факты (проверено 2026-09-26)

| Компонент | Факт | Проверка |
|---|---|---|
| Сервис systemd | `ekotov-wiki`, active, User=wiki, `WorkingDirectory=/opt/ekotov-wiki/backend`, `EnvironmentFile=/opt/ekotov-wiki/.env`, `Restart=on-failure` | `systemctl cat ekotov-wiki` |
| ExecStart | `/opt/ekotov-wiki/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8377` | `systemctl show ekotov-wiki -p ExecStart` |
| Каталог кода | `/opt/ekotov-wiki`, владелец `wiki:wiki`, **не git** (файловая копия); обновление только rsync из клона | `ls -la /opt/ekotov-wiki` |
| Пользователь | `wiki` uid=999 gid=988 (системный, без shell-логина); файлы /opt и БД — его | `id wiki` |
| Порт приложения | `127.0.0.1:8377` (только localhost, наружу только через nginx) | `ss -tln \| grep 8377` |
| Порт nginx | `10443` (0.0.0.0 и [::]; TLS, не 443) | `ss -tln \| grep 10443` |
| nginx-конфиг | `/etc/nginx/sites-enabled/ekotov-wiki`; `server_name 194.58.34.122`; `/static/` → `alias /opt/ekotov-wiki/frontend/static/` с `expires 7d`; gzip on | `cat /etc/nginx/sites-enabled/ekotov-wiki` |
| TLS | self-signed `/etc/nginx/ssl/ekotov-wiki.crt`, CN=194.58.34.122, notAfter=2028-12-22 (**расхождение с брифом «expires 7d»: 7d — это HTTP-заголовок `expires` кеша статики, не срок сертификата**) | `openssl x509 -enddate -noout -in /etc/nginx/ssl/ekotov-wiki.crt` |
| venv | `/opt/ekotov-wiki/backend/.venv`, Python 3.12.3, pip 24.0 | `.venv/bin/python --version` |
| БД | `/var/lib/ekotov-wiki/wiki.db`, владелец `wiki:wiki`, 0644, wal-режим не наблюдается (файлов -wal/-shm в каталоге нет) | `ls -la /var/lib/ekotov-wiki/` |
| Бэкапы | `/var/backups/ekotov-wiki/wiki-pre-<цель>-<дата>-<время>.db` (пример: `wiki-pre-r2-2026-09-24-1351.db`), владелец wiki, создаются `sqlite3 ".backup"` без остановки сервиса | `ls -la /var/backups/ekotov-wiki/` |
| Локальный клон | `/home/openclaw/ekotov-wiki`, ветка main — источник истины для rsync; владелец openclaw | `git -C ~/ekotov-wiki log --oneline -1` |
| Текущий релиз в бою | хотфикс `541e844` (кеш-бастинг `?v=`, стили V3); сейчас main ушел дальше (`0cc9d6b` на момент E9), прод отстает от клона — dry-run rsync показывает реальные дельты | `git merge-base --is-ancestor 541e844 main` |
| Снапшот отката | `/home/openclaw/ekotov-wiki-R1-snapshot/` — файловая копия /opt эпохи R1 (без .git), **устарел**: перед следующим деплоем пересоздается от текущего main (см. §4.3) | `ls -ld ~/ekotov-wiki-R1-snapshot` |
| Версии | nginx 1.24.0 (Ubuntu), sqlite3 3.45.1, rsync 3.2.7, Python 3.12.3 | `nginx -v; sqlite3 --version; rsync --version` |
| Точка входа страницы | `/` → 302 → `/login` (неавторизованный), страница отдает 200 через прод-URL | `curl -k https://127.0.0.1:10443/` |
| Секреты | `/opt/ekotov-wiki/.env` (DB_PATH, SECRET_KEY), 0640 wiki:wiki; в артефакты/репозиторий не попадают (в отчетах — `[REDACTED]`) | `sudo ls -la /opt/ekotov-wiki/.env` |
| Docker CE + compose plugin | НЕ установлен (проверено 2026-10-03); установка — ЭТАП 0, вручную Заказчиком по `deploy/dependencies-to-install.md` §1–3; ожидание: docker-ce 28.x, compose v2.x | `sudo docker version --format '{{.Server.Version}}'; sudo docker compose version` |
| Переходный порт контейнеров | `10444` свободен (проверено 2026-10-03) — первый контейнерный деплой публикует контейнерный nginx через него (§7.4 фаза 1) | `ss -tln \| grep 10444` (пусто = свободен) |

## 3. Быстрая проверка фактов (прогон перед деплоем)

```bash
systemctl is-active ekotov-wiki && systemctl show ekotov-wiki -p MainPID,User,WorkingDirectory
ss -tln | grep -E '8377|10443'
ls -ld /opt/ekotov-wiki /var/lib/ekotov-wiki/wiki.db /opt/ekotov-wiki/backend/.venv
id wiki
ls -la /var/backups/ekotov-wiki/ | tail -5
cat /etc/nginx/sites-enabled/ekotov-wiki | grep -E 'listen|server_name|alias|proxy_pass'
curl -s http://127.0.0.1:8377/api/health
curl -k -o /dev/null -w '%{http_code}\n' https://127.0.0.1:10443/login
git -C /home/openclaw/ekotov-wiki log --oneline -1
```

## 4. Процедуры

### 4.1 Деплой новой версии

Канонический скрипт ЭТОГО раздела (rsync/pip/systemd): `deploy/deploy-v1-systemd.sh` —
**устарел как основной** (P11 ЭТАП 1: основной деплой — контейнерный `deploy/deploy.sh`,
§7.6; v1 сохранен для отката на systemd-схему). Запускает **Заказчик из-под root**: `sudo bash deploy/deploy-v1-systemd.sh` (скрипт сам понижает права до `wiki` там, где нужно). Агент под openclaw прод не деплоит.

Параметры (env, с дефолтами): `APP_DIR`, `DB_PATH`, `PORT`, `PROD_URL`, `SERVICE`, `SRC_DIR`, `EXPECTED_COMMIT`, `TARGET_LABEL`, `DRY_RUN`.

Порядок подготовки и запуска:

1. В клоне `~/ekotov-wiki` на main должен лежать целевой коммит; вписать его в `EXPECTED_COMMIT` (env или правка шапки скрипта).
2. Прогнать dry-run (ничего не меняет): `DRY_RUN=1 bash deploy/deploy.sh` — проверить предусловия и дельту rsync.
3. Запустить деплой. Шаги скрипта: предусловия → бэкап БД → rsync кода (exclude `.git/.env/.venv/__pycache__` и пр.) → pip install → схема `app.db` (из cwd=backend, от wiki) → **миграция Релиза 4 — шаг «4b/6»** (`python -m app.migrate_r4` — встроен в deploy.sh, change add-r4-user-profile-ticket-view, ревью review-001 C-2: после схемы, строго до рестарта, от wiki, падение прерывает деплой; остановка uvicorn не требуется; метка «4b», не «3c» — review-002 M-1: шаг идет после схемы (4), до рестарта (5)) → рестарт → смоук. Бэкап аватаров: при релизах, трогающих аватары, каталог `/var/lib/ekotov-wiki/avatars/` копируется рядом с бэкапом БД (Релиз 4, review-001 C-3).
4. Смоук после деплоя — обязателен (урок E10), см. §4.4. Плюс один проход страницы в браузере.
5. Если релиз трогал статику — убедиться, что забамплен `static_v` в `backend/app/pages.py` (кеш-бастинг), иначе браузеры держат старый CSS 7 дней. Дисциплина (review-001 C-5): один финальный бамп на релиз, формат `r4.x`.
6. Релиз 4 (аватары): в nginx-конфиг `/etc/nginx/sites-enabled/ekotov-wiki` добавляется `location /avatars/` — alias `/var/lib/ekotov-wiki/avatars/`, `expires 7d`, `add_header Cache-Control "public"` (шаблон — `deploy/nginx-ekotov-wiki*.conf`, ревью review-001 blocker C-1: хранение вне rsync-корня); правка — `nginx -t` → reload. Пример шага:

```bash
sudo mkdir -p /var/lib/ekotov-wiki/avatars && sudo chown wiki:wiki /var/lib/ekotov-wiki/avatars
# вписать location /avatars/ { alias /var/lib/ekotov-wiki/avatars/; expires 7d; add_header Cache-Control "public"; }
sudo nginx -t && sudo systemctl reload nginx
```

### 4.2 Рестарт / останов

```bash
sudo systemctl restart ekotov-wiki && sleep 2 && systemctl is-active ekotov-wiki
curl -s http://127.0.0.1:8377/api/health        # {"status":"ok"}
sudo journalctl -u ekotov-wiki -n 50            # при отказе — логи первыми
```

### 4.3 Откат (rsync/systemd-схема — v1, откат на нее см. §7.6)

Откат кода — из снапшота (копия /opt на момент прошлого релиза), откат данных — из бэкапа БД. Снапшот `~/ekotov-wiki-R1-snapshot` устарел; **перед деплоем нового релиза пересоздать его от текущего main**:

```bash
# пересоздание снапшота (до деплоя; .env в снапшот не копируется — в /opt живой)
sudo rm -rf /home/openclaw/ekotov-wiki-R1-snapshot
sudo rsync -a --exclude '.git/' --exclude '.env' --exclude 'backend/.venv/' \
  --exclude '__pycache__/' --exclude '*.pyc' --exclude '.pytest_cache/' --exclude '.ruff_cache/' \
  /home/openclaw/ekotov-wiki/ /home/openclaw/ekotov-wiki-R1-snapshot/
sudo chown -R openclaw:openclaw /home/openclaw/ekotov-wiki-R1-snapshot
```

Откат кода (после неудачного деплоя):

```bash
sudo systemctl stop ekotov-wiki
sudo rsync -a --delete --exclude '.env' --exclude 'backend/.venv/' \
  /home/openclaw/ekotov-wiki-R1-snapshot/ /opt/ekotov-wiki/
sudo chown -R wiki:wiki /opt/ekotov-wiki
[ -f /opt/ekotov-wiki/.env ] || sudo cp /opt/ekotov-wiki/.env.bak /opt/ekotov-wiki/.env   # .env не трогается rsync
sudo systemctl start ekotov-wiki
# смоук §4.4 — обязателен
```

Откат данных (БД):

```bash
sudo systemctl stop ekotov-wiki
sudo cp /var/backups/ekotov-wiki/wiki-pre-<цель>-<дата>-<время>.db /var/lib/ekotov-wiki/wiki.db
sudo chown wiki:wiki /var/lib/ekotov-wiki/wiki.db
sudo rm -f /var/lib/ekotov-wiki/wiki.db-wal /var/lib/ekotov-wiki/wiki.db-shm
sudo systemctl start ekotov-wiki
```

Совместно: деплой, упавший после миграции схемы, требует отката и кода, и БД (код без миграции может ожидать старой схемы — и наоборот).

### 4.4 Смоук после деплоя (обязателен, урок E10)

Две точки + страница через прод-URL (именно прод-URL — nginx-слой и статику скрипт проверяет напрямую):

```bash
curl -s --max-time 5 http://127.0.0.1:8377/api/health                       # {"status":"ok"}
curl -k -o /dev/null -w '%{http_code}\n' https://127.0.0.1:10443/login      # 200 (страница через nginx+uvicorn)
curl -k -o /dev/null -w '%{http_code}\n' https://127.0.0.1:10443/static/css/app.css   # 200 (статика через nginx)
```

Плюс один реальный проход в браузере (логин → доска). Функциональный смоук стили не проверяет — при сомнениях в оформлении: `grep` класса по `frontend/static/css/` и `getComputedStyle` (аудит стилей — отдельная процедура скилла ekotov-wiki-ops).

## 5. Типовые отказы

| Симптом | Причина | Действие |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` при `python -m app.*` | запуск не из cwd=`backend` (пакет `app` резолвится из CWD) | всегда `( cd /opt/ekotov-wiki/backend && sudo -u wiki env DB_PATH=… .venv/bin/python -m app.<module> )` |
| Приложение работает со старым кодом/конфигом после правок | stale env: systemd прочитал `EnvironmentFile` при старте; правки .env/кода без рестарта не подхватываются | `sudo systemctl restart ekotov-wiki`; переменные процесса: `sudo cat /proc/$(systemctl show -p MainPID --value ekotov-wiki)/environ \| tr '\0' '\n'` |
| Порт занят, uvicorn не стартует (`address already in use`) | висячий процесс прошлого запуска / чужой слушатель на 8377 | `ss -tlnp \| grep 8377`; убить висяка (`kill <pid>`), затем `systemctl start ekotov-wiki` |
| У пользователя частичный рендер, старые стили после релиза | кеш браузера: nginx отдает `/static/` с `expires 7d` | проверить, что забамплен `static_v`; пользователю — обычный F5 (новые `?v=` сами обходят кеш) |
| `curl` на 10443 — connection refused, приложение живо на 8377 | nginx не перечитал конфиг / упал | `sudo nginx -t && sudo systemctl reload nginx`; `ss -tln \| grep 10443` |
| Бэкап не создался | нет каталога/прав у `/var/backups/ekotov-wiki` | скрипт останавливает деплой до всяких изменений; создать каталог, `chown wiki:wiki`, повторить |
| rsync затирает лишнее | неправильная пара источник/назначение при `--delete` | источник — `~/ekotov-wiki/` (с хвостовым слэшем), приемник — `/opt/ekotov-wiki/`; сначала `DRY_RUN=1` и смотреть itemize |

## 6. Границы

- Агент работает под `openclaw`; владелец прода — `wiki`: любые файловые операции по `/opt` и `/var/lib` — только `sudo -u wiki` (или root-скриптом, который сам понижает права).
- `/opt/ekotov-wiki` — не git: `git pull` там невозможен и не нужен; единственный путь обновления — rsync из клона на main.
- Секреты (`SECRET_KEY`, содержимое `.env`) в артефакты, отчеты и репозиторий не попадают — маскировать как `[REDACTED]`.
- Деплой запускает Заказчик; агент — подготовка скрипта, dry-run и пост-деплойная диагностика.

## 7. Контейнерный деплой (P11 ЭТАП 0+1, change add-containerization)

Целевая схема (design.md §1): app (uvicorn, порты не публикуются) + nginx
(TLS, единственный публикует порт) в compose-сети; данные (SQLite wiki.db +
avatars/) — named volume `wiki-data`; серт `/etc/nginx/ssl/ekotov-wiki.{crt,key}`
(до 2028-12-22) монтируется томом ro. Файлы: `deploy/compose.yaml` (прод),
`deploy/compose.test.yaml` (стенд, порт 8443), `deploy/dependencies-to-install.md`
(ручная установка Docker Заказчиком — ЭТАП 0).

Пока работает контейнерная схема — разделы §4.1–4.3 (rsync/pip/systemd) НЕ
применять к контейнерному стеку; они остаются для отката (см. §7.6).

### 7.1 Предусловия (все — до любого шага переключения)

1. Docker CE 28.x + compose plugin v2.x установлен Заказчиком вручную
   (`deploy/dependencies-to-install.md` §1–3): `sudo docker compose version`.
2. `openclaw` в группе docker (после перелогина): `id openclaw | grep docker`.
3. `/opt/ekotov-wiki/deploy/.env` существует, 0600, содержит продовый
   `SECRET_KEY=<тот же, что в /opt/ekotov-wiki/.env>` (иначе слетят сессии).
4. Серт на месте: `openssl x509 -in /etc/nginx/ssl/ekotov-wiki.crt -noout -enddate`
   → `notAfter=Dec 22 10:24:00 2028 GMT`.
5. Ресурсы: `free -m` → available ≥ 1500; `df -h /` → свободно ≥ 10G.
6. Системный прод жив и НЕ затронут: `systemctl is-active ekotov-wiki nginx` →
   `active`, `ss -tln | grep -E '8377|10443'` → оба слушают, 10444 свободен.

### 7.2 Сборка образов (на VPS, из клона; последовательно — вне часов пик)

```bash
cd /opt/ekotov-wiki   # или путь клона с целевым коммитом
sudo docker build -t ekotov-wiki/app:<release>      -f services/app/Dockerfile      .
sudo docker build -t ekotov-wiki/frontend:<release> -f services/frontend/Dockerfile .
sudo docker image ls | grep ekotov-wiki    # latest ЗАПРЕЩЕН (FR-72)
```

`<release>` — метка релиза (например `p11-r1`). Сборка двух образов не должна
идти параллельно с пиком нагрузки (plan §6 ОВ-2: VPS 3.9 GB).

### 7.3 Первый `compose up` — порт 10444, прод не тронут (фаза 1, tasks 2.3)

```bash
cd /opt/ekotov-wiki/deploy
export APP_IMAGE=ekotov-wiki/app:<release> FRONTEND_IMAGE=ekotov-wiki/frontend:<release>
sudo -E NGINX_PORT=10444 docker compose up -d
docker compose ps                          # app healthy, nginx up
sudo docker volume ls | grep wiki-data     # том создан
```

Перенос данных прода в том (ОДНОКРАТНО, до смоука фазы 1; контейнеры остановить):

```bash
cd /opt/ekotov-wiki/deploy && docker compose stop
# БД: консистентная копия .backup с живого прода → в том
sudo sqlite3 /var/lib/ekotov-wiki/wiki.db ".backup '/tmp/wiki-seed.db'"
sudo docker run --rm -v ekotov-wiki_wiki-data:/data -v /tmp:/seed \
  ekotov-wiki/app:<release> cp /seed/wiki-seed.db /data/wiki.db
# Аватары: tar прода → в том
sudo tar -C /var/lib/ekotov-wiki -cf /tmp/avatars-seed.tar avatars
sudo docker run --rm -v ekotov-wiki_wiki-data:/data -v /tmp:/seed \
  ekotov-wiki/app:<release> tar -C /data -xf /seed/avatars-seed.tar
rm -f /tmp/wiki-seed.db /tmp/avatars-seed.tar
cd /opt/ekotov-wiki/deploy && sudo -E NGINX_PORT=10444 docker compose up -d
```

(На этой VPS avatars/ пока пуст — каталог появился в Релизе 4 без аватаров;
шаг 3.2 тогда можно пропустить, но выполнить проверку тома после `up`.)

### 7.4 ЧЕКЛИСТ ПЕРЕКЛЮЧЕНИЯ ПРОДА (tasks 2.4; выполняет Заказчик под sudo)

Каждый шаг — с чекпоинтом отката. Откат на ЛЮБОМ шаге = возврат systemd-прода
за минуты: `sudo systemctl start ekotov-wiki` (+ возврат сайта nginx, шаг §7.6).

- [ ] **Шаг 0. Бэкап.** `sudo sqlite3 /var/lib/ekotov-wiki/wiki.db ".backup '/var/backups/ekotov-wiki/wiki-pre-p11-$(date +%Y-%m-%d-%H%M).db'"` — файл создан, размер совпадает с исходником.
- [ ] **Шаг 1. Параллельная проверка на 10444** (если не сделана в §7.3):
      `curl -sk https://127.0.0.1:10444/api/health` → `{"status":"ok"}`;
      `curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:10444/login` → 200;
      `curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:10444/static/css/app.css` → 200;
      логин seeded-юзера (или продового из перенесенной БД) браузером по `https://194.58.34.122:10444` — доска открывается. Прод на 10443 работает всё это время.
- [ ] **Шаг 2. Остановка systemd-прода.** `sudo systemctl stop ekotov-wiki && systemctl is-active ekotov-wiki` → `inactive` (юнит НЕ удаляется, `disable` НЕ делать).
- [ ] **Шаг 3. Освобождение 10443:** `sudo rm /etc/nginx/sites-enabled/ekotov-wiki && sudo nginx -t && sudo systemctl reload nginx` (или `sudo systemctl stop nginx` целиком). Шаги 2–3 — «два действия одного шага», разрыв — секунды.
- [ ] **Шаг 4. Публикация 10443 контейнером:** в том же каталоге deploy:
      `sudo -E NGINX_PORT=10443 docker compose up -d` — compose пересоздает ТОЛЬКО nginx-контейнер (app не трогает, том общий). `ss -tln | grep 10443` → слушает docker.
- [ ] **Шаг 5. Смоук через 10443** (§7.5): health / login / статика / avatars → все 200.
- [ ] **Шаг 6. Финальный смоук + браузер:** §4.4 (страница через прод-URL) +
      один реальный проход (логин → доска → создание задачи). Пользователь
      переживает только подтверждение self-signed исключения (серт тот же).
- [ ] **Шаг 7. Закрепление:** `docker compose ps` → обе службы Up (политика
      `restart: unless-stopped` поднимет стек после ребута VPS); юнит systemd
      оставить остановленным (`inactive`, enabled — НЕ disable) до конца паузы
      эксплуатации (ОВ-1=а, 1–2 недели).

**Откат на любом шаге (в порядке возврата, минуты):**

```bash
cd /opt/ekotov-wiki/deploy && sudo NGINX_PORT=10444 docker compose up -d   # или: docker compose stop
sudo ln -s /etc/nginx/sites-available/ekotov-wiki /etc/nginx/sites-enabled/ekotov-wiki   # если удаляли (шаг 3)
sudo nginx -t && sudo systemctl reload nginx      # или: systemctl start nginx
sudo systemctl start ekotov-wiki
systemctl is-active ekotov-wiki nginx; ss -tln | grep -E '8377|10443'
curl -k -o /dev/null -w '%{http_code}\n' https://127.0.0.1:10443/login   # 200
# БД тома НЕ трогаем; прод продолжает работать на своей БД /var/lib/ekotov-wiki/wiki.db
# Данные, созданные УЖЕ В КОНТЕЙНЕРЕ после переключения, при откате в прод-БД
# не попадают — зафиксировать вручную (или повторить переключение с новым бэкапом).
```

### 7.5 Смоук контейнерного прода (дополняет §4.4)

```bash
docker compose ps                                                  # app: healthy; nginx: up
curl -sk --max-time 5 https://127.0.0.1:<NGINX_PORT>/api/health   # {"status":"ok"}
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:<NGINX_PORT>/login          # 200
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:<NGINX_PORT>/static/css/app.css  # 200
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:<NGINX_PORT>/avatars/        # 200/403/404 — НЕ 502
sudo docker logs ekotov-wiki-nginx-1 2>&1 | grep -c 502           # 0 (stale-DNS контроль)
```

Отдельная проверка stale-DNS (design §1, смоук задачи 1.6): после выката НОВОГО
образа app (`docker compose up -d` с новым тегом) nginx-контейнер не пересоздается —
`curl` `/api/health` через nginx должен остаться 200 (не 502); если 502 —
`docker compose restart nginx` и завести дефект на resolver-конфиг.

### 7.6 Стенд и обновления

- Стенд (e2e/репетиции, tasks 1.4/2.1): `docker compose -f deploy/compose.test.yaml -p wiki-test up -d --build`
  → порт 8443, tmpfs-том (данные исчезают при down), seed:
  `docker compose -p wiki-test exec app python -m app.seed_users` (пароли интерактивно).
- Обновление контейнерного прода — канонический скрипт `deploy/deploy.sh` (v2,
  контейнерный, задача 1.6; v1 systemd/rsync сохранен как `deploy/deploy-v1-systemd.sh`
  — только для отката на systemd-схему, RUNBOOK §4.1–4.3). Запуск (Заказчик,
  из-под root, из клона с целевым коммитом):
  `sudo RELEASE_TAG=<метка> bash deploy/deploy.sh`
  (миграционные релизы — с `MIGRATE_MODULE=app.migrate_rN`; `latest` запрещен —
  FR-72, скрипт падает без валидного тега).

  Шаги скрипта (design §6): предусловия → **бэкап до КАЖДОГО деплоя, БЕЗ
  остановки** (метод/путь: БД — python-модуль `sqlite3` `.backup` через
  `docker exec` в контейнер `app` — sqlite3 CLI в slim отсутствует — во
  временный файл контейнера + `docker compose cp` наружу;
  аватары — `tar` каталога `/data/avatars` тем же exec; файлы:
  `/var/backups/ekotov-wiki/wiki-pre-<release>-<дата>-<время>.db` и
  `avatars-pre-<release>-<дата>-<время>.tar`) → build образов
  `ekotov-wiki/{app,frontend}:<release>` → one-shot миграция
  `docker compose run --rm app python -m app.migrate_rN` (СТРОГО до `up`,
  только после репетиции — tasks 2.1) → `up -d` → смоук (health/login/статика/
  avatars + «после up нового образа app nginx не отдает 502» — stale-DNS,
  design §1; fallback — `docker compose restart nginx` внутри скрипта;
  полный смоук статики `scripts/smoke_static.py` — применим против
  контейнерного nginx, статика в образе) → `docker image prune -f`.
  **Первый деплой нового метода — только после `DRY_RUN=1` прогона**
  (обязателен; показывает все шаги, ничего не меняет).
- Откат кода контейнерного прода: предыдущий `RELEASE_TAG` (образы тегированы,
  `latest` не используется — FR-72); несовместимая схема — восстановление БД
  из пред-деплойного бэкапа парой «код+БД».
- Возврат на systemd-схему целиком (аварийный, после недели+ эксплуатации):
  откат = §7.4 откат + восстановление БД из пред-деплойного бэкапа (§4.3),
  контейнерный стек `docker compose down` (том wiki-data сохранить до сверки данных).

### 7.7 Типовые отказы контейнерной схемы

| Симптом | Причина | Действие |
|---|---|---|
| `compose up` — `port is already allocated` | 8377/10443 заняты системным продом (это НОРМАЛЬНО до переключения) / висячий контейнер на 10444 | фаза 1 всегда `NGINX_PORT=10444`; `docker ps -a` → убрать висяка |
| nginx 502 на `/` после пересоздания app | stale-DNS (design §1) | должен лечиться resolver 127.0.0.11 + переменная proxy_pass; если нет — `docker compose restart nginx`, дефект |
| app не стартует, в логах «обязательная переменная SECRET_KEY» | нет `/opt/ekotov-wiki/deploy/.env` или compose запущен вне каталога deploy | создать .env (§7.1 п.3), запускать из `deploy/` |
| `permission denied` на /var/run/docker.sock | openclaw вне группы docker / старый сеанс | `sudo usermod -aG docker openclaw` + перелогин |
| после переключения «не открывается извне» | ufw закрыл 10443 | `sudo ufw status`; `sudo ufw allow 10443/tcp` |
| диск растет после каждого деплоя | dangling-образы | `docker image prune -f` (после каждого деплоя — шаг 7/7 в deploy.sh) |
| контейнеры не поднялись после ребута VPS | docker.service не в автозапуске | `sudo systemctl enable docker`; стек поднимется сам (`restart: unless-stopped`) |
