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

Канонический скрипт: `/home/openclaw/ekotov-wiki/deploy/deploy.sh`. Запускает **Заказчик из-под root**: `sudo bash /home/openclaw/ekotov-wiki/deploy/deploy.sh` (скрипт сам понижает права до `wiki` там, где нужно). Агент под openclaw прод не деплоит.

Параметры (env, с дефолтами): `APP_DIR`, `DB_PATH`, `PORT`, `PROD_URL`, `SERVICE`, `SRC_DIR`, `EXPECTED_COMMIT`, `TARGET_LABEL`, `DRY_RUN`.

Порядок подготовки и запуска:

1. В клоне `~/ekotov-wiki` на main должен лежать целевой коммит; вписать его в `EXPECTED_COMMIT` (env или правка шапки скрипта).
2. Прогнать dry-run (ничего не меняет): `DRY_RUN=1 bash deploy/deploy.sh` — проверить предусловия и дельту rsync.
3. Запустить деплой. Шаги скрипта: предусловия → бэкап БД → rsync кода (exclude `.git/.env/.venv/__pycache__` и пр.) → pip install → схема `app.db` (из cwd=backend, от wiki) → рестарт → смоук.
4. Смоук после деплоя — обязателен (урок E10), см. §4.4. Плюс один проход страницы в браузере.
5. Если релиз трогал статику — убедиться, что забамплен `static_v` в `backend/app/pages.py` (кеш-бастинг), иначе браузеры держат старый CSS 7 дней.

### 4.2 Рестарт / останов

```bash
sudo systemctl restart ekotov-wiki && sleep 2 && systemctl is-active ekotov-wiki
curl -s http://127.0.0.1:8377/api/health        # {"status":"ok"}
sudo journalctl -u ekotov-wiki -n 50            # при отказе — логи первыми
```

### 4.3 Откат

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
