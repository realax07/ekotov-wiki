# Сервис images (ekotov-wiki)

FastAPI-сервис изображений галереи (change `add-gallery-service`, задача
1.2; design §2/§3). По образцу `services/search`: uvicorn 1 воркер, порт
**8379**, сессионный middleware ядра (без сессии — 401), healthcheck
`/api/health` без БД-запроса.

## Запуск

```
cd services/images
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8379 --workers 1
```

env:

| Переменная | Дефолт | Смысл |
|---|---|---|
| `EKOTOV_WIKI_DB_PATH` | `/data/wiki.db` | общая БД (RW-профиль: свои таблицы gallery, users — только чтение; design §2) |
| `EKOTOV_WIKI_IMAGES_DIR` | `/data/images` | том изображений (compose задачи 1.3 смонтирует `images-data:/data/images`) |
| `PORT` | `8379` | порт `python -m app.main` |

## API

| Метод/путь | Что делает |
|---|---|
| `GET /api/health` | 200 `{"status":"ok"}` (exempt, без БД) |
| `POST /api/images` | multipart (file, category?, tags?) → 201; валидация JPEG/PNG/GIF/WebP по magic-байтам и ≤10 МБ **до записи**; оригинал+превью (JPEG ≤800px) в том, метаданные в БД; 422 — тип/размер/битый файл |
| `GET /api/images?category=&tag=` | список, created_at DESC, фильтры комбинируются; элемент: метаданные + теги `tags: [имена]` (1.6/Э-3, паритет с detail) + URL + счетчики + мой голос |
| `GET /api/images/{id}` | метаданные + теги + реакции + комментарии (автор, время) |
| `PUT/DELETE /api/images/{id}/like` | голос +1 (upsert; повторный — снятие) / явное снятие |
| `PUT/DELETE /api/images/{id}/dislike` | голос −1 (перенос противоположного) / снятие |
| `POST /api/images/{id}/comments` | `{body}` → 201; пустой после trim → 422 |
| `DELETE /api/images/{id}/comments/{cid}` | только автор; чужой → 403 |

Коды ошибок: 401 без сессии (включая `/openapi.json`), 404 нет
изображения/комментария, 403 чужой комментарий, 422 валидация (форма ядра
`{"error": "validation error", ...}`). Удаления изображения нет — осознанная
не-цель пакета (design §8).

## Схема БД

6 таблиц gallery (`image_categories`, `images`, `gallery_tags`,
`image_tags`, `image_reactions`, `image_comments` + индексы) создает
one-shot-миграция ядра `backend/app/migrate_gallery.py` — **задача 1.3**;
сервис сам миграций не выполняет (спека services: «Схему создает ядро»).
Файлы — в томе `images-data`, НЕ в БД (FR-79).

## Тесты

```
cd services/images
python3 -m pytest tests/ -v
```

TestClient in-process; временная БД (схема design §2 дословно) и временный
том — фикстуры. 26 тестов: upload happy/негативы (размер/тип/битый/без
файла), фильтры и комбинации, реакции (постановка/смена/снятие/DELETE +
401), комментарии (добавление/пустой 422/удаление своего/чужой 403/404),
границы RW-профиля (users/sessions не изменены).
