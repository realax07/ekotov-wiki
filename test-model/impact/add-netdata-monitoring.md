# Impact-анализ: change add-netdata-monitoring

> Дата: 2026-10-05 | Режим: ПМ-сводка по фактам QA-цикла (REPORT-2.1-netdata-qa.md:
> web 171p/1s/0f, api 201p/9s/2xf/0f — оба xf/фейла стендовые 413 nginx, не
> продукт; смоук /netdata 10/10 на live-nginx с netdata-стабом).
> Вход: дельты `openspec/changes/add-netdata-monitoring/specs/` (1 файл:
> deploy MODIFIED; monitoring/navigation — ADDED capabilities без MODIFIED),
> REPORT-2.1, review-001-1.4, review-002-1.2, review-001-design.

## Характер дельты

- **MODIFIED — 1 шт.:** deploy — в матрицу сервисов добавлен `netdata`
  (образ netdata/netdata, mem_limit 256m, порты не публикуются, маунты
  /proc, /sys, docker.sock — ro), frontend получает nginx-локации
  `/netdata` с basic auth (htpasswd-маунт ro) и маунт маунт htpasswd;
  порядок выката: build frontend → up netdata → up frontend → смоук.
- **ADDED — 2 шт.:** monitoring (метрики железа/контейнеров Netdata,
  не публикуется, ресурсы ограничены), navigation (ссылка «Мониторинг»
  в sidebar-footer только для Product manager, вид по утвержденному
  мокапу). Ядро app не затронуто — маршруты и UI-ссылка живут в
  frontend-образе и profile.js.
- **REMOVED — нет.**

## Резюме вердиктов

**keep — весь регресс (201 api + 171 web = 372 теста), revalidate — нет
отдельных точек, retire — нет.** Обоснование: добавление netdata-сервиса
и ссылки в сайдбаре не меняет существующее клиентское поведение
(проверено полным регрессом 2.1: 0 продуктовых фейлов; сайдбар-регресс —
6 новых проверок + 165 прежних web зеленые). Стендовые 413 на
avatar-boundary — прод-лимит nginx `client_max_body_size 2m`, известная
средовая особенность, не дельта пакета (REPORT-2.1 §4).

## Вердикты по сьютам

| Сьют | Вердикт | Обоснование |
|---|---|---|
| tests/api (201) | keep | паритет ядра подтвержден (0f) |
| tests/web (171) | keep + 6 новых netdata-проверок | сайдбар/разделы не сломаны |
| services/search/tests (12) | keep | сервис не затронут |
| e2e netdata (дашборд живого контейнера) | revalidate на 2.2 | docker-недоступность в QA; стаб за живым nginx — 10/10 |

## Риски для прода (2.2)

- Реальный контейнер netdata не гонялся (QA — стаб): RAM-замер, сборка
  дашборда и docker-коллектор проверяются на live-выкате (E-2.1a).
- htpasswd генерируется на VPS Заказчиком, вне репозитория; `nginx -t`
  до reload обязателен.
- Откат: предыдущий тег frontend + `docker compose stop netdata`.
