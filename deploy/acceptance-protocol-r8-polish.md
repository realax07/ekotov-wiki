# Протокол приемки r8-polish (задача 3.2, деплой 2026-10-08)

Деплой: RELEASE_TAG=r8-polish, PROJECT=ekotov-wiki-par, main 5b41f8d.
Прогон deploy.sh v3 — успешен (смоук матрицы green: health app/search, X-Service,
статика, аватары, 502=0, образы=теги). Бэкап до деплоя: /tmp/r8-backups/
wiki-pre-r8-polish-2026-10-08-0403.db (+avatars tar) — ВРЕМЕННО в /tmp
(см. примечание ниже), после приемки перенести в /var/backups/ekotov-wiki
(команда Заказчика, требует root):
  cp /tmp/r8-backups/wiki-pre-r8-polish-*.db /tmp/r8-backups/avatars-pre-*.tar /var/backups/ekotov-wiki/

Состав матрицы (все healthy): app/frontend(nginx)/search/images/backup = r8-polish, netdata stable.
ВНЕ матрицы deploy.sh: images-сервис — образ собран отдельно (services/images менялся:
rename API), поднят `up -d images` с IMAGES_IMAGE=r8-polish.

Пост-смоук ПМ: /login 200 (v=r8-polish в разметке), /api/health 200 {"status":"ok"},
/static/css/app.css 200, /gallery 302→login (норм без сессии), /api/search 401+X-Service: search
(контракт), smoke_static --base прод: 16/16 OK.
Маркеры фиксов на проде: app.css .content без height:100vh (BUG-011, .sidebar sticky
сохранен); tag-combobox.js sha256 = main (BUG-012, currentToken-семантика).

## Отклонения от канона (зафиксировать, уроки)
1. BACKUP_DIR=/tmp/r8-backups: у ПМ (openclaw) нет root — /var/backups/ekotov-wiki
   недоступен на запись. Бэкап сделан до деплоя (модуль backup.run_backup), но лежит
   в /tmp → перенести командой выше немедленно после приемки.
2. images-сервис вне SERVICES deploy.sh (dockerfile_for/image_for/6.8 не знают images) —
   образ собран и поднят отдельно; кандидат в chore: добавить images в матрицу deploy.sh.
3. Права /tmp/r8-backups для sidecar-бэкапа (uid 10001): chown/chmod через
   docker run alpine (запись от openclaw невозможна).

## Чек-лист приемки Заказчика (вживую, P12 пп.1–12)
Открывается https://<prod-ip>:10443 (принять self-signed). Пункты чек-листа
P12 пп.1–12 (PRODUCT_BACKLOG.md, дословно 2026-10-06) — каждый закрыть вживую.
После приемки: протокол заполнить, задачу 3.2 закрыть, пакет add-ui-polish-r8
архивировать (openspec archive), validate strict + flow_check, коммит архивации.
