# REPORT — задача 1.4 (add-gallery-service): nginx-локации images + отдача /images/

correlation_id flowctl-сессии: `6bf6bdae0d1a4afda941c72d53c8cd67`
Worktree: `/home/openclaw/ekotov-wiki-worktrees/dev-12-gallery`, ветка `add-gallery-service`
Зона записи (flowctl reserve): `services/frontend/**`, `deploy/compose.yaml`, `deploy/compose.test.yaml` — выход за зону: нет.

## Что сделано

Один инфра-коммит: только frontend-образ + compose-маунты (по ТЗ).

1. **`services/frontend/nginx/images-headers.inc`** (новый) — `X-Service: images`
   + повтор security-заголовков (NFR-7; add_header в location наследуется с
   перекрытием — по уроку search-headers.inc).
2. **`services/frontend/nginx/images-proxy.inc`** (новый) — по образцу
   search-proxy.inc:
   - `set $upstream_images http://images:8379;` + resolver server-блока
     `127.0.0.11 valid=10s` (анти-stale-DNS; старт nginx без images безопасен);
   - `client_max_body_size 12m` — локации загрузки (лимит NFR-21 10 МБ +
     multipart-обвязка; прод-лимит 2m перебивается локацией — иначе 413);
   - `proxy_next_upstream error timeout` + `proxy_intercept_errors on` +
     `error_page 502 503 504 = @images_down` — быстрая управляемая деградация;
   - X-Forwarded-For/Proto, X-Real-IP, Host, `proxy_http_version 1.1`,
     `proxy_pass $upstream_images` (URI не переписывается).
3. **`services/frontend/nginx/ekotov-wiki.conf`** — добавлены локации:
   - `location = /api/images` и `location ^~ /api/images/` — include обоих
     images-*.inc (пара «точный + префикс-слэш», `^~` отключает regex —
     паритет search-семейства; в ^~ попадают /{id}, лайки, комментарии и
     `/api/health` сервиса images — требование ТЗ «health images через nginx»);
   - `location /images/` — `alias /data/images/` + `expires 7d` +
     `Cache-Control public` — паритет `/avatars/` (alias указывает точно на
     маунт-точку тома: сервис кладет файлы в корень images-data —
     `app/gallery.py`: `orig_path = images_dir/<filename>`, превью рядом);
   - `location @images_down` — internal, JSON-тело
     `{"error": "images service unavailable"}` + `Retry-After: 5` — паттерн
     @search_down.
4. **`services/frontend/Dockerfile`** — в COPY добавлены оба images-*.inc.
5. **`deploy/compose.yaml`** (прод) — frontend(nginx): маунт
   `images-data:/data/images:ro` (глубина = маунту images, урок тома avatars).
6. **`deploy/compose.test.yaml`** (стенд) — то же: `images-test-data:/data/images:ro`.

Имена томов/сервисов сверены с фактическими в обоих compose-файлах перед
правкой: прод — том `images-data`; стенд — том `images-test-data` (проект
wiki-test); сервис images (задача 1.3) монтирует их на `/data/images` —
frontend-маунт той же глубины. Другие ключи frontend (mem_limit 64m, порты,
depends_on, logging, TLS-маунты) не менялись; сервис images не тронут.

## Чем верифицировано (статическая — docker недоступен)

Скрипт-проверка (python): `yaml.safe_load` обоих compose-файлов + структурная
сверка nginx-конфига с search-паттерном — **41/41 PASS**, в том числе:

- compose (прод и стенд, зеркально): маунт images-data(:test)-data
  ro на `/data/images` у frontend; паритет глубины с images-маунтом;
  том объявлен в `volumes:`; volumes images не изменены (1.3); mem_limit
  images 128m и healthcheck :8379 на месте; frontend ровно 4 маунта
  (2 TLS + wiki-data ro + images-data ro); mem_limit frontend 64m не тронут;
- nginx-конфиг: все 4 локации присутствуют; оба images-include подключены в
  `=` и `^~`; alias `/data/images/`; `expires 7d` — паритет с `/avatars/`;
  `@images_down` — 503 + Retry-After; resolver `127.0.0.11 valid=10s`;
  баланс скобок; Dockerfile копирует оба include;
- images-proxy.inc: набор директив = search-proxy.inc, кроме единственного
  осознанного добавления `client_max_body_size 12m` (требование ТЗ/design §4);
  error_page → @images_down; $upstream_images:8379; X-Forwarded-*;
- images-headers.inc: набор add_header идентичен search-headers.inc,
  `X-Service: images`.

Примечание к методике: первый прогон проверки дал 3 ложных FAIL — дефекты
самой проверки (healthcheck-список склеивался не по тому индексу; осознанное
отличие client_max_body_size считалось расхождением), а не артефактов; после
исправления проверки — ALL PASS на неизмененных артефактах.

## SKIPPED (живые стендовые проверки)

`docker` в сессии недоступен (известное ограничение, как в 1.3) — `nginx -t`,
подъем стенда и HTTP-проверки выполнить нечем. Следующие проверки ТЗ
зафиксированы как **SKIPPED, причина: нет docker-доступа; проверка переносится
на 2.1/QA + live-стенд**:

- `/api/health` images через nginx → 200;
- `/api/images` без сессии → 401;
- `/images/<файл>` отдается nginx'ом с кеш-заголовками (`expires 7d`);
- остановленный images → быстрый 503 на `/api/images*`, остальные маршруты
  (доска, поиск, страницы) работают как прежде.

Компенсирующая статическая верификация — раздел выше: конфиг структурно
сверен с проверенным на стенде search-паттерном (те же директивы, имена
переменных, include-файлы существуют и копируются в образ, compose-маунты
паритетны и согласованы по именам томов и глубине).

## Эскалации

Нет (E-N не заводились). Блокеров нет.

## Чекбокс

`[x] 1.4` отмечен в `openspec/changes/add-gallery-service/tasks.md`? — НЕТ:
`openspec/**` вне зоны записи этой задачи (уронит finish); отметка чекбокса —
оркестратору/ПМ при приемке.
