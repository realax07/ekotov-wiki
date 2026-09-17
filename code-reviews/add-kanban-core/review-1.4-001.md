# Ревью задачи 1.4 — Развертывание (systemd + nginx)

- **Change:** add-kanban-core
- **Задача:** 1.4 (systemd-юнит + конфиг nginx: reverse-proxy, TLS Let's Encrypt)
- **Диф:** коммит `24b02d3` (task 1.4: deploy configs)
- **Файлы дифа:** `deploy/ekotov-wiki.service` (новый, 45 строк), `deploy/nginx-ekotov-wiki.conf` (новый, 82 строки), `deploy/README.md` (+120: инструкция VPS + локальная эмуляция), удалены плейсхолдеры `.service.placeholder` / `.conf.placeholder`, `tasks.md` (чекбокс 1.4 → [x])
- **Арбитры:** sdd.md §1 (стек: nginx front-proxy, systemd-юнит, NFR-6), design.md §8 (развертывание), tasks.md 1.4, NFR-5 (БД/секреты вне репо), NFR-6 (VPS, интернет, HTTPS), NFR-7 (базовая безопасность)
- **Метод:** три круга скилла code-review + независимый факт-чек ревьюером (nginx 1.24.0 из deb-пакета, systemd 255, venv wiki)

## Вердикт: **return**

Blocker и нарушений спеки нет; 1 major (невоспроизводимый шаг миграции в README) + 4 minor.

## Таблица замечаний

| # | Файл | Место | Серьезность | Замечание | Рекомендация |
|---|------|-------|-------------|-----------|--------------|
| 1 | deploy/README.md | шаг 5 (блок миграции) | **major** | Команда `sudo -u wiki env DB_PATH=… SECRET_KEY=x /opt/ekotov-wiki/backend/.venv/bin/python -m app.db --workdir=/opt/ekotov-wiki/backend` невоспроизводима. (а) `--workdir` — несуществующий флаг: `app.db` не парсит argv (проверено: выполняется молча игнорируясь); (б) модуль ищется относительно cwd, а не флага: к этому шагу админ находится в `/opt/ekotov-wiki` (шаг 3 заканчивается `cd /opt/ekotov-wiki`), и `python -m app.db` падает с `ModuleNotFoundError: No module named 'app'` — воспроизведено ревьюером. Шаг заведения БД на реальном VPS не сработает. | Заменить на `cd /opt/ekotov-wiki/backend && sudo -u wiki env DB_PATH=/var/lib/ekotov-wiki/wiki.db SECRET_KEY=x .venv/bin/python -m app.db` либо `sudo -u wiki … /bin/sh -c 'cd /opt/ekotov-wiki/backend && .venv/bin/python -m app.db'`. Флаг `--workdir` убрать. |
| 2 | deploy/README.md | шаг 8 (fallback-совет) | minor | Совет «установите `libnginx-mod-http-headers-more-filter`» не относится к делу: конфиг не использует headers-more; `options-ssl-nginx.conf` и `ssl-dhparams.pem` ставятся пакетом certbot, а не этим модулем. Совет введет в заблуждение. | Убрать упоминание пакета; оставить только «уберите include/ssl_dhparam» и `openssl dhparam`. |
| 3 | deploy/README.md | шаг 5 (seed) | minor | «seed интерактивный — запустите один раз под своим пользователем» — при запуске не под `wiki` созданные `wiki.db*` требуют `chown` (он есть), но WAL-файлы (`-wal`, `-shm`) в маске `wiki.db*` появляются только после подключения; если seed прерван, владельцы могут различаться. Также `SECRET_KEY=x` в команде миграции — заглушка, допустимая (config.py требует только наличие), но рядом с «секреты только через .env» стоит пометка, что это не прод-значение. | Явно написать: миграция и seed выполняются от `wiki` (одной командой `sudo -u wiki`), заглушечный `SECRET_KEY=x` пометить комментарием «только для миграции, не прод». |
| 4 | deploy/nginx-ekotov-wiki.conf | server (443) | minor | `server_tokens` не отключен — nginx отдает свою версию в Server-заголовке (проверено: `Server: nginx/1.24.0 (Ubuntu)`). Для интернет-facing заготовки NFR-7 это не требование, но отключение — одна строка. | Добавить `server_tokens off;` в http/server-контекст (в обертку или README-примечание, т.к. конфиг — site-файл). |
| 5 | deploy/nginx-ekotov-wiki.conf | gzip | minor | `gzip_types application/json` в сочетании с TLS и секретами в ответах — теоретический вектор BREACH (сжатие отражаемых секретов). При 2 пользователях и SameSite=Lax риск пренебрежим; фиксировать как «принято осознанно». | Либо исключить `application/json` из gzip_types, либо оставить с комментарием. Не блокирует. |

## Круг 1 — спека как закон

- tasks.md 1.4: «systemd-юнит + конфиг nginx (reverse-proxy, TLS Let's Encrypt)» — оба артефакта присутствуют, плейсхолдеры удалены; «приложение доступно извне по HTTPS… (или локально эмулировано nginx'ом)» — эмуляция выполнена (см. факт-чек). ✅
- sdd.md §1 Front-proxy: nginx как reverse-proxy + TLS/Let's Encrypt + терминация перед uvicorn — соответствует; приложение за nginx на localhost. ✅
- design.md §8: nginx reverse-proxy/TLS-терминатор → uvicorn, процесс — systemd-юнит, файл БД вне репозитория по конфигу (`DB_PATH=/var/lib/ekotov-wiki/wiki.db`). ✅
- NFR-6: HTTPS + Let's Encrypt + systemd — выполнено (webroot certbot, renew --dry-run в README). ✅
- Вне спеки «улучшений», требующих трассировки, нет: gzip/таймауты/client_max_body_size — стандартная обвязка front-proxy, в рамках sdd «конфиг ~десяток строк» — с натяжкой (82 строки с комментариями), но без новой функциональности.

## Круг 2 — best practices / безопасность (интернет-facing)

- **Секреты:** в конфигах и README нет ни одного значения секрета; только пути (`EnvironmentFile=/opt/ekotov-wiki/.env`, пример пути БД). `SECRET_KEY=x` в README — заглушка для миграции (замечание 3, minor). Серты — пути `/etc/letsencrypt/...`, в репо не попадают. ✅
- **Слушающий адрес:** юнит: `--host 127.0.0.1 --port 8377` — только loopback; nginx `proxy_pass http://127.0.0.1:8377`. Ни одного `0.0.0.0` в дифе. ✅
- **Security-заголовки:** X-Content-Type-Options, X-Frame-Options DENY, Referrer-Policy, HSTS — все `always`, только в 443-блоке (80-й блок заголовков не имеет — проверено эмуляцией). HSTS `max-age=31536000; includeSubDomains` — корректен для TLS-сервера. ✅
- **acme-challenge:** `location /.well-known/acme-challenge/` стоит до `location /` и отдает webroot без редиректа (проверено: 200 с телом файла, остальные пути — 301). certbot-webroot сработает. ✅
- **Данные:** БД — `/var/lib/ekotov-wiki/`, `.gitignore` уже содержит `.env`, `*.db` (задача 1.1). В дифе нет ни артефактов, ни секретов. ✅ (NFR-5)
- **Hardening юнита:** NoNewPrivileges, PrivateTmp, ProtectSystem=full, ProtectHome=read-only, не-root User/Group (wiki, nologin). `PrivateTmp=true` SQLite не мешает (БД в /var/lib, не в /tmp). `ProtectHome` не задевает `/opt`. ✅

## Круг 3 — integration-точки

- Согласованность путей юнит ↔ README ↔ конфиг nginx: `/opt/ekotov-wiki`, `backend/.venv/bin/uvicorn`, WorkingDirectory `/opt/ekotov-wiki/backend`, порт 8377, домен-плейсхолдер в 4 местах конфига (2 server_name + 2 пути сертов) — README шаг 7 упоминает «2 server_name + 2 пути сертов». ✅
- `.env.example` ↔ юнит: переменные ровно `DB_PATH`, `SECRET_KEY`; `app/config.py` требует обе через `_require` без дефолтов — 1-в-1. ✅ (проверено фактом)
- Соседние задачи: `/api/health` (задача 1.1) проксируется и отвечает 200 через 443-эмуляцию; миграция `app.db` и модуль `seed_users` (1.2/1.3) запускаются из `backend/` — сломаны только инструкцией README (замечание 1), не кодом. Смоук `GET /api/health` через TLS-эмуляцию пройден. ✅

## Факт-чек ревьюера (проверено лично, а не по отчету dev)

| Заявление dev | Проверка ревьюера | Результат |
|---|---|---|
| `nginx -t` валиден | nginx 1.24.0 (Ubuntu) из официального deb, распакован без sudo; тестовая копия конфига: порты 80→8080, 443→8443, серты → self-signed `/tmp`, `include options-ssl`/`ssl_dhparam` → закомментированы, webroot/static → `/tmp` | `syntax is ok / test is successful`, rc=0 ✅ |
| 80→443 редирект 301 | живой nginx: `GET /` и `GET /api/health` на 80-м → `301`, `Location: https://$host/...` (с подмененным Host — сохраняет `$host`) | подтверждено ✅ |
| 4 security-заголовка | `GET https://127.0.0.1:8443/` через живой nginx: все 4 присутствуют с `always`; на 80-м (до TLS) заголовков нет, HSTS только на 443 | подтверждено ✅ |
| TLS-цепочка + health через proxy = 200 | поднят реальный uvicorn (venv wiki, `app.main:app` на 127.0.0.1:8377, DB_PATH/SECRET_KEY из тестового env) за живым nginx (self-signed): `GET /api/health` → `200 {"status":"ok"}` со всеми 4 заголовками | подтверждено ✅ |
| acme-challenge не мешает редиректу | файл в webroot → `200` с телом; соседний путь → `301` | подтверждено ✅ |
| `systemd-analyze verify` rc=0 | тестовая копия юнита (пути → /tmp, существующий исполняемый uvicorn, существующий EnvironmentFile с DB_PATH/SECRET_KEY) | `verify` rc=0, ни одного предупреждения ✅ |
| `.env.example` ↔ EnvironmentFile 1-в-1 | `.env.example`: `DB_PATH`, `SECRET_KEY`; юнит/comments: те же две; `config.py` требует ровно их | подтверждено ✅ |
| — | README шаг 5 (миграция) воспроизводим | **не воспроизводим** (замечание 1, major) ❌ |

## Что принято по отчету dev без личной проверки

- Поведение на реальном VPS: выпуск серта certbot'ом, `certbot renew --dry-run`, автопродление, таймер systemd — эмуляция без sudo и внешнего домена невозможна; принято по отчету (шаблонные пути certbot стандартны).
- Наличие/поведение `options-ssl-nginx.conf` и `ssl-dhparams.pem` на VPS (в тесте исключены) — принято по отчету + fallback в README (с поправкой замечания 2).
- Поведение `listen [::]:80/443` при отсутствии IPv6 на хосте — не проверялось (в тестовой среде IPv6-сокет поднялся).

## Итог

Вернуть dev'у на исправление замечания №1 (major, README шаг 5) и по желанию №2–5 (minor). Конфиги юнита и nginx замечаний по существу не имеют (№4–5 — опциональная полировка); после исправления README повторное ревью дифа исправления (append-only).
