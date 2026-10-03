# Что установить/настроить на VPS вручную ДО старта контейнеризации (P11 ЭТАП 0)

**Для: Заказчик (запуск под root/sudo на VPS 194.58.34.122, Ubuntu 24.04.4 LTS).**
Файл self-contained: не требует чтения других документов. Агент установку НЕ
выполняет (зона ответственности Заказчика, задачи 0.1/2.3/2.4 — совместные).

Состояние VPS, проверено 2026-10-03 (агент, без установки):

| Что | Факт | Как перепроверить |
|---|---|---|
| Docker CE / compose plugin | **НЕ установлен** | `docker --version` → command not found |
| ОС / ядро | Ubuntu 24.04.4 LTS, ядро 6.8.0-138-generic — официальные пакеты Docker подходят | `lsb_release -ds; uname -r` |
| RAM | 3.9 GB total, ~2.7 GB available — лимиты контейнеров (nginx 64m + app 512m ≈ 0.6 GB) проходят с запасом | `free -m` |
| Диск | 49G, занято 37% (≈31G свободно) — образы и тома помещаются | `df -h /` |
| Занятые порты | 8377 (systemd-прод, live), 10443 (хостовый nginx, live), 22 (ssh). **10444 свободен** — переходный порт | `ss -tlnp \| grep -E '8377\|10443\|10444'` |
| TLS-сертификат | `/etc/nginx/ssl/ekotov-wiki.{crt,key}` self-signed, CN=194.58.34.122, действует до **2028-12-22** — перевыпуск НЕ нужен, монтируется томом ro | `openssl x509 -in /etc/nginx/ssl/ekotov-wiki.crt -noout -subject -dates` |
| sudo | под openclaw sudo требует пароль — все команды ниже выполнять в своей sudo-сессии | — |

## 1. Установка Docker CE + compose plugin (официальный репозиторий, без snap)

Ubuntu-пакет `docker.io` и snap-вариант НЕ используем (устаревший docker /
snap-песочница ломают systemd-юниты docker). Источник — официальный репозиторий
download.docker.com. Текущая стабильная мажор-версия — 28.x (фиксируем мажор,
патч-версию берете последнюю из репозитория).

```bash
# 1.1. Пререквизиты и ключ/репозиторий (gpg хранится в /etc/apt/keyrings)
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 1.2. Установка (docker-ce-cli, containerd и compose plugin — зависимости пакета)
sudo apt-get update
apt-cache madison docker-ce | head -5     # посмотреть доступные версии
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

# 1.3. Проверка версий (ожидание: Docker 28.x, compose v2.x)
sudo docker version --format '{{.Server.Version}}'
sudo docker compose version
```

## 2. Группы и права

```bash
# 2.1. Пользователь openclaw в группу docker (docker-сокет без sudo).
# ВНИМАНИЕ: членство в docker-группе = root-эквивалент (маунты/сокет);
# на данной VPS это приемлемо — машина уже полностью в управлении Заказчика.
sudo usermod -aG docker openclaw
# вступит в силу после НОВОГО login-сеанса; проверка:
#   id openclaw | grep docker && docker ps
```

Рут-обвязку Docker (`docker.socket`/`docker.service`) НЕ трогаем: автозапуск
демона нужен. Контейнеры перезапускаются сами (`restart: unless-stopped`).

## 3. Подготовка каталогов/томов (однократно, до первого `compose up`)

```bash
# 3.1. Каталог проекта для compose + deploy/.env
sudo mkdir -p /opt/ekotov-wiki/deploy
# 3.2. deploy/.env — создать ВРУЧНУЮ (в git НЕ попадает, .gitignore):
#   SECRET_KEY=<тот же, что в /opt/ekotov-wiki/.env — иначе слетят сессии>
sudo chmod 600 /opt/ekotov-wiki/deploy/.env && sudo chown root:root /opt/ekotov-wiki/deploy/.env
# 3.3. Данные — именованный том wiki-data создаст compose сам при первом up.
#      Ручное создание НЕ требуется; проверка после первого up:
sudo docker volume ls | grep wiki-data
# 3.4. TLS: сертификат уже на месте (/etc/nginx/ssl/ekotov-wiki.{crt,key}),
#      маунтится в контейнер ro. Проверить права чтения ключа демоном:
sudo ls -l /etc/nginx/ssl/
```

## 4. Опционально: sanity-проверка окружения

```bash
df -h / | awk 'NR==2 {print $4" свободно"}'      # >= 10G — норм
free -m | awk '/Mem:/ {print $7" MB available"}' # >= 1500 — норм
uname -r                                          # 6.8+ — ок для overlay2
sudo docker info | grep -E 'Storage Driver|Cgroup'  # overlay2/systemd
```

## 5. Что МОЖЕТ сломаться и что делать

| Симптом | Причина | Действие |
|---|---|---|
| `apt-get install docker-ce` — «no installation candidate» | не подключился репозиторий download.docker.com (шаг 1.1) | проверить `/etc/apt/sources.list.d/docker.list`; `apt-get update` не дал ошибок по docker |
| `port is already allocated` / `bind: address already in use` при `compose up` | порт занят: 8377 — systemd-прод, 10443 — хостовый nginx (оба ДОЛЖНЫ жить до переключения), занят 10444 — висячий контейнер прошлой попытки | `sudo ss -tlnp \| grep <порт>`; для 10444: `sudo docker ps -a` → убрать старый контейнер; 8377/10443 не занимать — первый деплой идет через 10444 |
| контейнеры недоступны снаружи по 10444/10443 | ufw/фаервол режет порт | `sudo ufw status`; если active: `sudo ufw allow 10444/tcp` (и 10443/tcp на переключении); на этой VPS ufw, скорее всего, inactive |
| после установки docker «висит» systemd-прод | docker.service потянул зависимости/рестарт сети (reload ifupdown) — на 24.04 редкость, но возможно | `systemctl is-active ekotov-wiki nginx`; при отказе — `sudo systemctl restart ekotov-wiki nginx` (прод вернется за секунды) |
| `docker: permission denied … /var/run/docker.sock` | openclaw не в группе docker или сеанс старый | перелогиниться; проверить `id openclaw \| grep docker` |
| диск заполнился образами | сборки оставляют dangling-слои | `sudo docker image prune -f` после каждого деплоя (RUNBOOK §7.7) |
| snap-версия docker уже стоит | кто-то поставил snap-вариант | `snap remove docker`, затем установка из п.1 — смешивать нельзя |

## 6. Чего НЕ делать до переключения (чекпоинты отката)

- НЕ останавливать и не отключать `systemd-юнит ekotov-wiki` и хостовый nginx —
  они держат прод (8377/10443) до фазы переключения (tasks 2.4).
- НЕ удалять `/etc/nginx/sites-enabled/ekotov-wiki` — точка отката переключения.
- НЕ заливать прод-SECRET_KEY в файлы вне `/opt/ekotov-wiki/deploy/.env`
  (0640, root) и не коммитить его.
- Удаление Docker (полный откат ЭТАПА 0): `sudo apt-get purge docker-ce
  docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin &&
  sudo rm -rf /var/lib/docker` — systemd-прод при этом не затрагивается.

## 7. Дальнейший порядок (для сведения; пошагово — RUNBOOK §7)

1. Установить Docker по п.1–3 этого файла (ЕДИНСТВЕННОЕ, что нужно вручную).
2. `deploy/compose.yaml` — prod-топология; первый подъем — `NGINX_PORT=10444`
   (параллельно с живым продом, tasks 2.3).
3. Смоук через 10444 → переключение порта на 10443 (tasks 2.4) — по RUNBOOK §7.4.
