# TC-GAL-106 — nginx-маршрутизация изображений: пара /api/images*, health, отдача /images/ с expires 7d

- **Change:** add-gallery-service
- **Источник:** gallery (ADDED): «Изображения обслуживаются отдельным сервисом images» (FR-79) — Scenario «Маршрутизация nginx + Ядро без маршрутов», «Деградация — healthcheck/порты», «Отдача файла nginx из тома»; services (ADDED): порты images не публикуются; deploy (MODIFIED): nginx-пара по образцу search-семейства + `location /images/` alias в том images-data (ro) с expires 7d; CHK-GAL-1, CHK-GAL-5, CHK-GAL-8
- **Тип:** ФТ, инфраструктура/среда | **Приоритет:** Must
- **Маркер:** ручной/стендовый — REPORT-2.1 (инфра-чеки nginx; юнит-базис маршрутов ядра — `services/images/tests/test_images_service.py::test_openapi_paths`, OpenAPI ядра без images-путей)
- **Предусловия:** стенд поднят по матрице пакета (миграция gallery до подъема app, images + frontend healthy); nginx-конфиг 1.4 в образе frontend (`= /api/images` + `^~ /api/images/`, include images-headers.inc/images-proxy.inc); том images-data примонтирован (images rw, frontend ro); в томе есть ≥1 загруженное изображение (см. TC-GAL-107)
- **Шаги:**
  1. Через nginx: `GET /api/images` (с сессией) и `GET /api/images/<id>` — фиксировать код ответа и заголовки.
  2. Через nginx: `GET /api/health` images; параллельно проверить соседей `/api/tasks`, `/api/search` — поведение как прежде.
  3. Напрямую к контейнеру app: `GET /api/images` (минуя nginx) — ожидать 404/405 (маршрутов изображений в ядре нет).
  4. `GET /images/<файл-оригинала>` и `GET /images/<файл-превью>` — проверить код, `Content-Type`, заголовки кеша (`Expires`/`Cache-Control`, срок 7d) и что тело — байты файла из тома images-data.
  5. Проверить конфигурацию compose: порты images не опубликованы наружу (`docker compose config` / `docker port images` пусто); в nginx-локациях зафиксировать наличие X-Service-заголовков по образцу search-семейства (если предусмотрены include'ами — зафиксировать фактические имена/значения в REPORT-2.1).
- **Ожидаемый результат:** шаг 1 — `/api/images*` обслуживается сервисом images (:8379) через nginx, ответы 200; шаг 2 — `/api/health` → 200 `{"status":"ok"}`, соседи `/api/tasks`, `/api/search` не изменены; шаг 3 — ядро отвечает 404/405 (маршрутов изображений нет — гейт «ядро без маршрутов»); шаг 4 — `/images/<файл>` отдается nginx'ом (alias в том images-data) с кеш-заголовками expires 7d, паритет `/avatars/`; обращения к сервису images при отдаче статики не требуются; шаг 5 — порты images наружу не публикуются, X-Service-заголовки зафиксированы (или задокументировано их отсутствие).
