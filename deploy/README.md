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
sudo apt install -y python3-venv nginx certbot python3-certbot-nginx
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

# миграция: применяет схему (идемпотентна)
sudo -u wiki env DB_PATH=/var/lib/ekotov-wiki/wiki.db SECRET_KEY=x \
  .venv/bin/python -m app.db

# seed: заводит РОВНО 2 учетки — owner (владелец) и wife (жена); интерактивный:
# пароль для каждой вводится с терминала без эха (запускать в интерактивной сессии)
sudo -u wiki env DB_PATH=/var/lib/ekotov-wiki/wiki.db SECRET_KEY=x \
  .venv/bin/python -m app.seed_users
```

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

## Локальная эмуляция (без VPS)

`nginx -t deploy/nginx-ekotov-wiki.conf` — проверка синтаксиса (см. отчет
задачи 1.4). Полную эмуляцию с сертами можно сделать self-signed сертификатом
и `listen 443 ssl` без certbot — вне скоупа задачи 1.4.
