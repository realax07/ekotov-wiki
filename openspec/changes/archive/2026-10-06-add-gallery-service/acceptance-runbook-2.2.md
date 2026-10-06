# Протокол-заготовка приемки Заказчика: задача 2.2 (прод-выкатка и приемка галереи)

Change-пакет: `add-gallery-service` | Задача: 2.2 [ops] | Флоу 1
Целевой коммит: d25a499 (r7.1-gallery: add-gallery-service + бамп static_v r7.1)
Форма: исполнение Заказчиком под root (VPS), ПМ-сопровождение, независимая верификация.
Прод: compose-проект `ekotov-wiki-par`, порт 10443, владелец схемы gallery — сервис images.

## 0. Предусловия (ПМ проверил до передачи)

- [x] Клон /home/openclaw/ekotov-wiki на d25a499 (main, PR #28+#30 смержены, CI green)
- [x] Репетиция миграции на копии прод-БД (/tmp/prod-copy-rehearsal2.db): 6 таблиц,
      идемпотентна (повтор no-op), integrity_check ok, данные ядра не тронуты (8 задач)
- [x] openspec strict 15 PASS, flow_check OK
- [x] Полный web-регресс 170p/1s/0f; юниты images 28/28
- [ ] У Заказчика: свободное место > 3 GB (df -BG /), память ≥ 1.5 GB available

## 1. Подтяжка прода и деплой (Заказчик, root)

```bash
cd /home/openclaw/ekotov-wiki && git pull        # → d25a499

# 1а. DRY_RUN (ничего не меняет — ОБЯЗАТЕЛЬНЫЙ первый прогон):
sudo -E DRY_RUN=1 PROJECT=ekotov-wiki-par SRC_DIR=/home/openclaw/ekotov-wiki \
  RELEASE_TAG=r7.1-gallery MIGRATE_MODULE=app.migrate_gallery \
  bash deploy/deploy.sh

# 1б. Боевой деплой (тот же набор БЕЗ DRY_RUN):
sudo -E PROJECT=ekotov-wiki-par SRC_DIR=/home/openclaw/ekotov-wiki \
  RELEASE_TAG=r7.1-gallery MIGRATE_MODULE=app.migrate_gallery \
  bash deploy/deploy.sh
```

Скрипт сам: бэкап БД+аватаров (`/var/backups/ekotov-wiki/wiki-pre-r7.1-gallery-*.db`)
→ build 5 образов (app/frontend/search/backup/images — матрица расширена images)
→ МИГРАЦИЯ gallery one-shot ДО подъема (composе run, владелец схемы — ядро) →
up app → healthy → up search backup → healthy → up nginx → healthy →
смоук-матрица → image prune.

ВНИМАНИЕ: deploy.sh v3 KNOWS только 4 сервиса (app/frontend/search/backup) в
проверке образов (шаг 6.8) — images поднимается, но в матричной проверке не
участвует; gallery-смоук ниже добивает проверку images отдельно.

## 2. Подъем images (если матрица deploy.sh его не подняла)

```bash
sudo -E PROJECT=ekotov-wiki-par docker compose -f /home/openclaw/ekotov-wiki/deploy/compose.yaml up -d images
sudo -E PROJECT=ekotov-wiki-par docker compose -f /home/openclaw/ekotov-wiki/deploy/compose.yaml ps
```
Ожидание: 5 сервисов Up, images healthy.

## 3. Gallery-смоук (ПМ, независимая верификация)

```bash
B=https://127.0.0.1:10443
curl -sk -o /dev/null -w '%{http_code}\n' $B/api/health          # 200
curl -sk -o /dev/null -w '%{http_code}\n' $B/api/images          # 401 (без сессии — images ответил)
curl -skI $B/api/images 2>/dev/null | grep -i x-service           # X-Service: images
curl -sk -o /dev/null -w '%{http_code}\n' $B/gallery             # 302/200 (редирект/страница)
curl -sk -o /dev/null -w '%{http_code}\n' "$B/static/js/gallery.js?v=r7.1"  # 200
curl -sk $B/login | grep -o 'v=r7.1' | head -1                   # v=r7.1 (кеш-бамп жив)
sudo docker stats --no-stream | grep images                      # RAM ≤ 128Mi (design §5)
```

## 4. Приемка Заказчика ВЖИВУЮ (критерий приемки ОВ)

Под owner на https://194.58.34.122:10443/gallery:
- загрузка изображения (drag&drop или выбор файла; JPEG/PNG/GIF/WebP ≤ 10 МБ)
- просмотр: сетка превью (не обрезаются, contain) → full-screen по клику,
  листание ←/→ (кнопки и клавиши), Esc закрывает
- лайк/дизлайк (подсветка, счетчик), комментарий (добавить/удалить свой)
- категория/теги на загрузке; фильтры в сетке
Критерий: «работает» вживую — приемка состоялась.

## 5. Откат (если что-то пошло не так)

```bash
# Пара «код+БД»: таблицы gallery ядром НЕ читаются — откат кода безопасен
sudo -E PROJECT=ekotov-wiki-par SRC_DIR=/home/openclaw/ekotov-wiki \
  RELEASE_TAG=r7-netdata bash deploy/deploy.sh   # предыдущий тег всей матрицы
# БД при необходимости: /var/backups/ekotov-wiki/wiki-pre-r7.1-gallery-*.db
# (миграция НЕ откатывается — 6 пустых таблиц остаются, совместимо)
```

## 6. Хвосты (после приемки)

- [ ] acceptance-protocol-2.2-gallery.md (факты приемки, дословная цитата)
- [ ] RUNBOOK: раздел «Галерея» (миграция, том images-data, бэкап, лимиты 128m)
- [ ] tasks.md [x] 2.2 → openspec archive add-gallery-service (После archive —
      проверить, что MODIFIED-дельты не омичили сценарии; strict green)
- [ ] RAM-замер images в отчет (кейс TC-GAL-121, SKIPPED-хвост QA)
