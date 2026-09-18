# deploy/

Развертывание ekotov-wiki на VPS (задача 1.4, NFR-6): systemd-юнит приложения
и конфиг nginx (reverse-proxy, TLS Let's Encrypt).

- `ekotov-wiki.service` — systemd-юнит uvicorn (слушает только 127.0.0.1:8377)
- `nginx-ekotov-wiki.conf` — конфиг nginx (80 → редирект, 443 TLS, proxy на 8377)

Инструкция развертывания — ниже (пути соответствуют юниту и nginx-конфигу).

## Развертывание на VPS (Ubuntu/Debian)

Домен: замените `ekotov-wiki.example.com` на свой (A-запись → IP VPS) — в
nginx-конфиге и в командах certbot ниже.

### 1. Системные пакеты

```bash
sudo apt update
sudo apt install -y python3-venv nginx certbot python3-certbot-nginx sqlite3
```

### 2. Код

```bash
sudo mkdir -p /opt/ekotov-wiki && sudo chown $USER /opt/ekotov-wiki
git clone <repo-url> /opt/ekotov-wiki
cd /opt/ekotov-wiki
```

### 3. Окружение и секреты

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`.env` — в корне репозитория, вне git (в `.gitignore`). Переменные — см.
`.env.example` (`DB_PATH`, `SECRET_KEY` — обе обязательны, без дефолтов в коде):

```bash
cd /opt/ekotov-wiki
cp .env.example .env
# DB_PATH=/var/lib/ekotov-wiki/wiki.db   # вне репозитория (NFR-5)
# SECRET_KEY=<python3 -c "import secrets; print(secrets.token_hex(32))">
nano .env   # заполнить значения
```

### 4. Пользователь сервиса и каталог БД

```bash
sudo useradd --system --home-dir /opt/ekotov-wiki --no-create-home --shell /usr/sbin/nologin wiki
sudo mkdir -p /var/lib/ekotov-wiki
sudo chown wiki:wiki /var/lib/ekotov-wiki
# чтение .env процессом сервиса:
sudo chgrp wiki /opt/ekotov-wiki/.env && chmod 640 /opt/ekotov-wiki/.env
```

### 5. Миграция (схема БД) и seed пользователей

Обе команды выполняются от пользователя `wiki` (через `sudo -u wiki`), чтобы БД
и WAL-файлы (`wiki.db-wal`, `wiki.db-shm`) создались сразу с его владельцем —
без последующего `chown`. `SECRET_KEY=x` здесь — заглушка только для разового
запуска миграции/seed (config.py требует лишь наличие переменной); прод-значение
живет в `.env` (шаг 3) и в команды ниже не подставляется.

```bash
cd /opt/ekotov-wiki/backend

# миграция: применяет схему (идемпотентна); для БД, созданных до sdd r5,
# добавляет колонку done_at (ALTER TABLE tasks ADD COLUMN done_at — задача 6.1,
# FR-4 в редакции «архивация через день»); для свежих БД колонку создает схема.
sudo -u wiki env DB_PATH=/var/lib/ekotov-wiki/wiki.db SECRET_KEY=x \
  .venv/bin/python -m app.db
```

Миграция после обновления кода (git pull): безопасно запустить повторно —
`ALTER` выполняется только если колонки `done_at` в таблице tasks еще нет
(проверка `PRAGMA table_info` в `app/db.init_db`); повторный запуск идемпотентен.
Данные при миграции не трогаются. После миграции перезапустите сервис:
`sudo systemctl restart ekotov-wiki`.

```bash
# seed: заводит РОВНО 2 учетки — owner (владелец) и wife (жена); интерактивный:
# пароль для каждой вводится с терминала без эха (запускать в интерактивной сессии)
sudo -u wiki env DB_PATH=/var/lib/ekotov-wiki/wiki.db SECRET_KEY=x \
  .venv/bin/python -m app.seed_users
```

Логины фиксированы: `owner` и `wife` (плейсхолдеры; при необходимости других
логинов — поправьте `USERS` в `backend/app/seed_users.py` до запуска). Пароли
вводятся интерактивно с терминала без эха, с повтором; в открытом виде нигде
не сохраняются (только bcrypt-хеши, NFR-7). Регистрации в приложении нет —
ровно эти 2 учетки (NFR-4). Повторный запуск seed идемпотентен: существующий
логин пропускается (пароль не перезаписывается).

### 6. systemd

```bash
sudo cp deploy/ekotov-wiki.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ekotov-wiki
systemctl status ekotov-wiki
curl -s http://127.0.0.1:8377/api/health   # {"status":"ok"}
```

### 7. nginx (до TLS — только 80-й блок)

```bash
sudo cp deploy/nginx-ekotov-wiki.conf /etc/nginx/sites-available/ekotov-wiki
sudo ln -s /etc/nginx/sites-available/ekotov-wiki /etc/nginx/sites-enabled/
sudo nano /etc/nginx/sites-available/ekotov-wiki   # заменить домен (2 server_name + 2 пути сертов)
sudo nginx -t
```

Пока сертификата нет, 443-й блок не стартует (`nginx -t` ругается на отсутствие
файлов сертов) — временно закомментируйте его, выпустите сертификат (шаг 8),
раскомментируйте обратно.

### 8. TLS Let's Encrypt

```bash
sudo mkdir -p /var/www/html
sudo certbot certonly --webroot -w /var/www/html -d ekotov-wiki.example.com
sudo certbot renew --dry-run   # автопродление по таймеру
sudo nginx -t && sudo systemctl reload nginx
```

Если `options-ssl-nginx.conf`/`ssl-dhparams.pem` отсутствуют (обычно их ставит
пакет python3-certbot-nginx) — уберите `include`/`ssl_dhparam` из конфига либо
сгенерируйте dhparam самостоятельно:
`sudo openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 2048`.

### 9. Проверка

```bash
curl -s https://ekotov-wiki.example.com/api/health   # {"status":"ok"}
curl -sI http://ekotov-wiki.example.com/             # 301 → https
```

## Бэкап

Данные живут в одном файле SQLite (путь — `DB_PATH` в `.env`, по умолчанию
`/var/lib/ekotov-wiki/wiki.db`, вне репозитория — NFR-5). Бэкап = копия этого
файла. Приложение работает в WAL-режиме: копировать файл БД «в лоб» (cp) во
время работы нельзя — копия может уйти рассинхронизированной с `wiki.db-wal`.
Два допустимых способа:

**Способ 1 (рекомендуется): онлайн-копия через `sqlite3 .backup`** — сервис
не останавливается:

```bash
sudo -u wiki sqlite3 /var/lib/ekotov-wiki/wiki.db \
  ".backup /var/backups/ekotov-wiki/wiki-$(date +%F).db"
```

**Способ 2: stop → copy → start** — если `sqlite3`-клиента нет:

```bash
sudo systemctl stop ekotov-wiki
sudo cp -a /var/lib/ekotov-wiki/wiki.db* /var/backups/ekotov-wiki/   # вкл. -wal/-shm
sudo systemctl start ekotov-wiki
```

(кратковременный простой ~1–2 с; для личной wiki на 2 пользователей приемлемо).

Каталог бэкапов (вне репозитория и вне каталога БД):

```bash
sudo mkdir -p /var/backups/ekotov-wiki
sudo chown wiki:wiki /var/backups/ekotov-wiki
```

**Периодичность:** ежедневно (cron). Данные на 2 пользователей меняются
умеренно, ежедневный бэкап + хранение 7–14 дневных копий покрывает потерю
с запасом. Пример cron (`sudo crontab -e`):

```cron
30 3 * * * sudo -u wiki sqlite3 /var/lib/ekotov-wiki/wiki.db ".backup /var/backups/ekotov-wiki/wiki-$(date +\%F).db" && find /var/backups/ekotov-wiki -name 'wiki-*.db' -mtime +14 -delete
```

**Восстановление** (файл бэкапа кладется на место `DB_PATH`; владельцем
должен быть `wiki`):

```bash
sudo systemctl stop ekotov-wiki
sudo cp /var/backups/ekotov-wiki/wiki-YYYY-MM-DD.db /var/lib/ekotov-wiki/wiki.db
sudo chown wiki:wiki /var/lib/ekotov-wiki/wiki.db
sudo rm -f /var/lib/ekotov-wiki/wiki.db-wal /var/lib/ekotov-wiki/wiki.db-shm
sudo systemctl start ekotov-wiki
# проверка живости и данных:
curl -s http://127.0.0.1:8377/api/health
```

(WAL-файлы восстанавливаемой БД удаляются: свежий бэкап из `.backup` — целостный
снимок; оставшийся старый `-wal` к чужому файлу прикладывать нельзя.)

**Проверка бэкапа:** периодически (например, раз в месяц) восстанавливайте
копию во временный файл и просматривайте количество задач:

```bash
sqlite3 /var/backups/ekotov-wiki/wiki-YYYY-MM-DD.db "SELECT COUNT(*) FROM tasks;"
```

## Локальная эмуляция (без VPS)

`nginx -t deploy/nginx-ekotov-wiki.conf` — проверка синтаксиса (см. отчет
задачи 1.4). Полную эмуляцию с сертами можно сделать self-signed сертификатом
и `listen 443 ssl` без certbot — вне скоупа задачи 1.4.
