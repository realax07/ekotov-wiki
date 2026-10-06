# Design: add-gallery-service

Версия: r1 (2026-10-05). Источники: вводные Заказчика (PLAN-R7.md пакет 2,
решение `decisions/2026-10-05-r7-launch-gallery`), прод-топология p12-rc1
(`deploy/RUNBOOK.md` §1, `deploy/compose.yaml`), прецедент companion-сервиса
`services/search` (nginx-паттерн `=`+`^~`, resolver+переменная, include'ы,
healthcheck), профиль аватаров ядра (Pillow, том, `/avatars/` alias).

## §0. Дизайн-фаза (дополнение Заказчика: «Дизайн не забудь», «У нас есть дизайнер» — преемственность пакета 1)

Галерея — **крупная видимая UI-дельта**: пакет проходит дизайн-фазу по
конвейерному паттерну Р4/Р5, исполняют её штатные роли (СА дизайн НЕ рисует):

1. **[design] ui_designer** (`agents/ui_designer_agent.md`, зона `design/**`,
   продукт-код не пишет): мокапы в `design/` — standalone HTML (открывается
   без сборки), токены V3 «Бумага» (`frontend/static/css/app.css` `:root`:
   paper-050/100/200, ink-900/600, clay-600 акцент, Georgia display, радиусы
   6/10px, focus-ring, 8px-сетка), **без внешних библиотек/шрифтов/CDN**
   (ОГР-8), контраст AA. Состав мокапов:
   - **сетка галереи** (`/gallery`): карточки превью (masonry/равная сетка —
     решает дизайнер), карточка: превью, название, категория/теги, счетчики
     лайков/комментариев; фильтры категория/тег над сеткой; кнопка/форма
     загрузки;
   - **full-screen просмотр**: модальное окно на весь экран — изображение,
     листание ←/→ (кнопки + клавиши), панель: лайк/дизлайк (счетчики,
     состояние «мой голос»), скачать, комментарии (список + поле ввода +
     удаление своего), закрытие (Esc/крестик);
   - **карточка с лайками/комментариями** — состояния hover/focus-visible;
   - **форма загрузки**: выбор файла, категория (из справочника + создание
     нового значения), теги (подсказки заведенных + ввод нового),
     индикация загрузки и ошибок (лимит 10 МБ / тип файла).
2. **Утверждение мокапов Заказчиком** — явная развилка; dev-фронтенд НЕ
   стартует до зафиксированного утверждения (прецедент Д-5; решение
   фиксируется оркестратором approval_ref'ом).
3. **[dev] фронтенд-задача** — внедрение строго по утвержденным мокапам.
4. **[qa] design_validator** (`agents/design_validator_agent.md`, запись
   `test-model/reviews/add-gallery-service/review-NNN-design.md`): после
   dev ревьюит фактический вид против мокапов — токены (не хардкод),
   состояния, соответствие эталону; вердикт approve/return.

Состав задач — tasks.md 1.1 (design, развилка Заказчика), 1.4
(фронтенд, «по утвержденным мокапам»), validator-ревью в QA-фазе (2.1).

## §1. Целевая топология

```
Браузер (owner/PE) ── https://…:10443 ── nginx [frontend]
   ├── /gallery            → app:8377 (страница, сессия; существующая цепочка)
   ├── = /api/images       → images:8379 (пара = + ^~, include images-proxy.inc)
   ├── ^~ /api/images/     → images:8379 (API: upload/list/get/like/comments)
   ├── /images/            → alias том images-data (файлы+превью, кеш 7d — паритет /avatars/)
   └── остальное           → как сейчас (app:8377, search:8378, netdata)

app:8377      — ядро: страница /gallery + миграция таблиц gallery (one-shot)
images:8379   — FastAPI (uvicorn 1 воркер): API изображений, RW-профиль БД
                (свои таблицы gallery), том images-data RW (файлы+превью)
```

- Наружу открыт только nginx :10443 (преемственность FR-65) — images порты
  НЕ публикует (паритет app/search).
- Пара `= /api/images` + `^~ /api/images/` — по образцу search-семейства;
  resolver 127.0.0.11 + переменная в proxy_pass (анти-stale-DNS);
  деградация недоступного images — управляемый 503 (JSON + Retry-After,
  паттерн `@search_down` / `images-proxy.inc` по образцу search).
- Страница `/gallery` обслуживается **ядром** (Jinja2 + статика) — шаблоны
  и ассеты в существующих цепочках; API — отдельный сервис. Так страница
  получает стандартную сессионную защиту ядра, а сервис — только API-трафик.

## §2. Данные: таблицы gallery + RW-профиль

Новые таблицы (создает миграция ядра `backend/app/migrate_gallery.py`;
владелец схемы — сервис images; ядро после миграции таблицы gallery не
трогает):

```sql
image_categories (   -- справочник категорий ГАЛЕРЕИ (отдельный от задач, research №4)
  id   INTEGER PK,
  name TEXT UNIQUE NOT NULL
)

images (
  id            INTEGER PK,
  filename      TEXT NOT NULL,      -- имя файла в томе images-data (генерирует сервер, как аватары)
  thumb_name    TEXT NOT NULL,      -- имя превью в томе (Pillow на upload, design §3)
  original_name TEXT NOT NULL,      -- имя файла у загрузившего (для скачивания)
  mime          TEXT NOT NULL,      -- image/jpeg|png|gif|webp (NFR-21)
  size          INTEGER NOT NULL,   -- байты (≤ 10 МБ, NFR-21)
  category_id   INTEGER FK -> image_categories.id,  -- nullable (категория опциональна)
  uploaded_by   INTEGER NOT NULL FK -> users.id,
  created_at    TEXT NOT NULL
)

gallery_tags (      -- словарь тегов галереи (механизм tags, свои таблицы — research №3)
  id    INTEGER PK,
  name  TEXT UNIQUE NOT NULL
)

image_tags (
  image_id INTEGER NOT NULL FK -> images.id ON DELETE CASCADE,
  tag_id   INTEGER NOT NULL FK -> gallery_tags.id,
  PRIMARY KEY (image_id, tag_id)
)

image_reactions (
  image_id INTEGER NOT NULL FK -> images.id ON DELETE CASCADE,
  user_id  INTEGER NOT NULL FK -> users.id,
  value    INTEGER NOT NULL CHECK (value IN (1, -1)),
  PRIMARY KEY (image_id, user_id)   -- ровно один голос пользователя на изображение (FR-81)
)

image_comments (
  id         INTEGER PK,
  image_id   INTEGER NOT NULL FK -> images.id ON DELETE CASCADE,
  user_id    INTEGER NOT NULL FK -> users.id,
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL
)
```

Индексы: `images(category_id)`, `images(created_at)` (сортировка сетки),
`image_tags(tag_id)` (фильтр по тегу), `image_reactions` — PK покрывает,
`image_comments(image_id)`.

**RW-профиль images (research №2):** маунт `wiki-data:/data` **RW** (первый
сервис-писатель после ядра) — пишет/читает ТОЛЬКО таблицы gallery +
`SELECT id, login, display_name FROM users` (автор комментария/загрузчик).
Инварианты: короткие транзакции, busy_timeout, WAL не переключается;
схему существующих таблиц не трогает; миграций у images нет (схему gallery
создает ядро — один владелец миграций, правило deploy). Файлы — в отдельном
томе `images-data` (RW), НЕ в БД (FR-79). Тест-инвариант QA: images не
пишет в таблицы ядра (инспекция + код-ревью).

## §3. Сервис images (по образцу services/search)

- Порт **8379**, uvicorn 1 воркер; структура каталога паритет search:
  `services/images/{app/,tests/,README.md}`.
- Healthcheck `/api/health` (200 `{"status": "ok"}`, без БД-запроса —
  паритет search); OpenAPI включен, без сессии — 401 (паттерн ядра).
- **Загрузка (FR-79):** `POST /api/images` multipart (file, category?,
  tags?): валидация типа (JPEG/PNG/GIF/WebP по magic-байтам, не только
  Content-Type) и размера (≤10 МБ, NFR-21); имя файла генерирует сервер
  (uuid-подобное, расширение по типу — паттерн аватаров, не доверяем
  имени клиента); оригинал + превью (Pillow, длинная сторона ≤ 800px,
  JPEG — на upload, research №5) → том images-data; метаданные → БД
  (одна транзакция). Категория: существующий id ИЛИ новое имя (создается
  в справочнике галереи); теги: существующие + новые имена.
- **Список (FR-80):** `GET /api/images?category=<id>&tag=<name>` —
  фильтры комбинируются, пустые — все; сортировка по created_at DESC;
  в элементе: метаданные + URL превью + счетчики (лайки, дизлайки,
  комментарии) + собственный голос запрашивающего (для бейджа в сетке).
- **Получение:** `GET /api/images/{id}` — полные метаданные + реакции
  (счетчики + мой голос) + комментарии (автор: display_name/логин,
  created_at).
- **Реакции (FR-81):** `PUT /api/images/{id}/like` /
  `PUT /api/images/{id}/dislike` — ставит/меняет голос пользователя
  (upsert по PK); `DELETE /api/images/{id}/like` — снимает голос;
  ответ — обновленные счетчики + мой голос.
- **Комментарии (FR-82):** `POST /api/images/{id}/comments`
  `{body}` (непустой после trim → 422 иначе); `DELETE
  /api/images/{id}/comments/{cid}` — только автор (чужой → 403);
  список — в `GET /api/images/{id}`.
- Ошибки: 401 без сессии (NFR-7-паттерн ядра), 404 нет изображения,
  422 валидация (тип/размер/пустой комментарий), 403 чужой комментарий.
- RAM: FastAPI+Pillow, лимит 128m (NFR-20); факт-замер на стенде.

## §4. nginx и compose

- `images-proxy.inc` (по образцу search-proxy.inc): переменная
  `$upstream_images http://images:8379`, заголовки X-Forwarded-*,
  `client_max_body_size 12m` на локациях загрузки (лимит NFR-21 10 МБ +
  multipart-обвязка), деградация 503 по error_page (паттерн `@search_down`).
- Локации в `ekotov-wiki.conf`: `= /api/images`, `^~ /api/images/`
  (include images-headers.inc + images-proxy.inc); `location /images/`
  alias `/data/images/` из маунта тома images-data (ro) + expires 7d —
  паритет `/avatars/`.
- Compose (прод + стенд, NFR-10-паритет): сервис `images` — образ
  `ekotov-wiki/images`, `mem_limit: 128m`, healthcheck (urllib на
  `/api/health` — паритет search), logging json-file 10m×3,
  `restart: unless-stopped`, depends_on app (паритет search), тома:
  `wiki-data:/data:rw` (метаданные+users) и `images-data:/data/images`
  (файлы). nginx (frontend) получает второй маунт `images-data:/data/images:ro`
  для alias-отдачи. Стенд — те же тома с временными именами (паритет
  wiki-data_test).

## §5. Ресурсы (VPS 3.9 GB)

| Сервис | mem_limit | Было (после netdata) |
|---|---|---|
| app | 512m | 512m |
| frontend | 64m | 64m |
| search | 512m | 512m |
| backup | 64m | 64m |
| netdata | 256m | 256m |
| **images** | **128m** (вводные пакета; FastAPI+Pillow) | — |
| **сумма** | **1.54 GB** | 1.41 GB |
| **резерв хосту** | **≥ 2.3 GB** (требование deploy-спеки ≥ 2 GB выполняется) | ≥ 2.4 GB |

- Замер фактического RAM images после подъема стенда — задача 1.3 (урок
  «вес меряем по факту»); стабильное превышение 128m → эскалация до прод.
- Диск: лимит 10 МБ/файл; превью ≤ ~200 КБ; масштаб 2 пользователей —
  контроль занятости тома в смоук-матрице (2.1) и приемке (2.2).

## §6. Фронтенд: страница /gallery (по мокапам 1.1)

- Маршрут `/gallery` в ядре (страница Jinja2, сессия; редирект без сессии
  — общий механизм §3.6 sdd). JS-модуль галереи (ванильный, паттерн
  board/profile): сетка из `GET /api/images`, фильтры, загрузка, модалка.
- **Модалка** (FR-83): overlay на весь экран, ←/→ кнопки + клавиатура
  (ArrowLeft/ArrowRight, Esc), изображение — оригинал, панель реакций/
  скачивания/комментариев; листание циклично по текущей отфильтрованной
  выдаче. Скачивание — `<a download>` на `/images/<filename>` с
  original_name (атрибут download + серверный Content-Disposition —
  решает dev по мокапу).
- **Связь с трекером отсутствует** (ОВ-3): ни ссылок на задачи, ни
  фильтров по задачам; общий элемент — только сайдбар.
- **Сайдбар (FR-85):** 4-й пункт «Галерея» после «Wiki» в `base.html`
  (серверный шаблон — в отличие от «Мониторинга» пункт виден всем
  авторизованным, ОВ-4; страницы функционала и так рендерятся только под
  сессией). XSS-дисциплина в JS: createElement+textContent, href по
  данным API.
- Кеш-бастинг статики `?v=` бамп при релизе со статикой (урок DEF-002/3).

## §7. Деплой и миграция

- Новые образы: images (build), frontend (nginx-конфиг), ядро app — с
  миграционным скриптом. Один RELEASE_TAG на весь релиз (правило матрицы).
- Порядок (паритет deploy-спеке): бэкап (БД python-sqlite3 .backup + tar
  аватаров **+ tar images-data** — том новый, пустой, включается в контур
  бэкапов) → build всех → **миграция ядра one-shot: `python -m
  app.migrate_gallery`** (создание 6 таблиц gallery; идемпотентно —
  повторный запуск no-op; автосверка: таблицы существуют, инварианты
  схемы; exit 1 при расхождении) строго до up app → up app → healthy →
  up images/frontend → healthy → смоук-матрица (существующая + /api/health
  images через nginx, /gallery 200 под сессией, 401/редирект без).
- **Репетиция миграции на копии прод-БД обязательна** до выкатки (правило
  deploy-спеки, урок Р4) — шаг задачи 2.2.
- Откат: предыдущим тегом всей матрицы; новые таблицы gallery обратной
  совместимости не мешают (ядро их не читает) — при откате кода БД можно
  не возвращать, решение по факту инцидента (пара «код+БД» — по общему
  правилу).
- RUNBOOK пополняется разделом «Галерея» (миграция, том images-data,
  бэкап, лимиты).

## §8. Осознанные не-цели

- Удаление изображений / переименование категорий галереи — предложение
  Заказчику (proposal Out of scope), не реализуется без решения.
- Альбомы, привязка к задачам, приватность — ОВ-3/ОВ-4.
- Полноценная пагинация — масштаб 2 пользователей не требует (NFR-2-
  паритет); при росте — отдельное изменение.
- Внешние JS/CSS-библиотеки (светофоры галерей из CDN) — ОГР-8;
  модалка/листание — ванильный JS.
