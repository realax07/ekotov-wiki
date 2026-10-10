# Review 4.5 — повторное ревью (итерация 002)

- **Коммит:** 7ca9284 (`task 4.5: fixes from review-4.5-001`)
- **Первичное ревью:** [review-4.5-001.md](review-4.5-001.md) (верdict **return**: 1 major + 2 minor)
- **Ревьюер:** code_reviewer (изолированная сессия)
- **Дата:** 2026-09-17

## Вердикт: **approve**

Все три замечания 001 устранены, каждое проверено на фактически исполненном коде
(смок: реальный TestClient 422 + исполнение board.js в node с эмуляцией DOM).
Остался один косметический пункт (№4 ниже) — неисполним при схеме сервера,
не блокирует. Одиночный коммит исправлений — только `board.js` (+33/−9),
плюс файл этого ревью (001) — регрессий нет.

## Проверка замечаний 001

### №1 (major) handleApiError — details-массив pydantic: **исправлено**

- Ветка `Array.isArray(details)` (board.js:94-102) добавлена **до** ветки объекта;
  формат объекта оставлен как fallback (board.js:103-109) — рекомендация выполнена дословно.
- **Смоук с реальным 422:** TestClient (venv wiki), `POST /api/tasks {"title": "   "}` → 422,
  тело `{"error": "validation error", "details": [{type, loc: ["body","title"], msg, ...}]}` —
  массив, как и зафиксировано в 001. Текст пользователя после handleApiError:
  **«validation error. body.title: Value error, title must not be empty»** — без
  `[object Object]`. Второй случай (`due_date: "17.09.2026"`) → «…body.due_date:
  Input should be a valid date or datetime…», тоже чисто.
- Регресс формата details-объекта: `{title: ["не может быть пустым", "too short"]}` →
  «validation error. title: не может быть пустым; too short» — прежнее поведение сохранено.
- Краевые: пустой `details: []` → «validation error»; элемент без `loc` →
  «validation error. bad»; без `details` вовсе → «validation error» (не падает).

### №2 (minor) parseBody — не-JSON тело: **исправлено**

- `response.json().catch(() => null)` (board.js:64-70) — async-reject ловится;
  комментарий в коде объясняет, почему try/catch не годится.
- В `handleApiError` ветка `!body` → **«Ошибка запроса (HTTP N).»** (board.js:79-84).
  Смок: тело HTML-страница 502 → «Ошибка запроса (HTTP 502).» — не «Сетевая ошибка».
  Обычный JSON-ответ с 404 по-прежнему дает «Ошибка запроса (HTTP 404).»; 401 →
  redirect /login без сообщения — не задето. Пустой JSON-тело (`null`/пустой
  объект) на 2xx уходит в onOk как раньше (ветка `!body` только в error-пути).

### №3 (minor) renderComments — фолбэк отсутствующих полей: **исправлено** (с оговоркой №4)

- Метка собирается из отфильтрованных непустых частей (board.js:343-351); пустая
  метка → элемент не рендерится. Смок: без `created_at` → «id 7» (не «id 7 · undefined»);
  пустая строка `created_at` отфильтрована; `id`+`created_at` на месте → «id 5 · <date>».
- body рендерится через `textContent` — как и прежде (XSS не задет).

### Диф и регрессии

- `git diff 177269a..7ca9284 --name-only`: **только `frontend/static/js/board.js`**
  (42 строки: +33/−9) плюс файл review-4.5-001.md. `backend/` не тронут, tasks.md не тронут.
- `node --check board.js` — OK. `app.js`/`login.js` не изменялись (свои fetch-точки
  не используют parseBody/handleApiError — общей регрессии в остальном JS нет).
- Функциональный объем 4.5 не сокращен: изменены только три целевые функции,
  вызовы api()/401/204-пути сохранены (проверено исполнением 401- и 404-веток).

## Замечания

| # | Серьезность | Файл/строка | Замечание | Рекомендация |
|---|---|---|---|---|
| 4 | minor (косметика, неисполнимо при текущей схеме) | frontend/static/js/board.js:344 | `"id " + comment.id` вычисляется **до** фильтра: при отсутствующем `comment.id` строка «id undefined» проходит фильтр как непустая. Смоук: `renderComments([{body:"no id"}])` → children `["id undefined","no id"]`. Достижимо только если API вернет комментарий без `id`, чего схема (NOT NULL PK, sdd §4) не допускает — поэтому не блокирует. | В后续 итерациях: добавлять в массив готовые части (`comment.id !== undefined ? "id " + comment.id : null`) или фильтровать до склейки. |

## Проверено лично

- Реальный серверный 422 (TestClient, venv wiki, свой смок в /tmp, вне репозитория):
  пустой title и кривая due_date → тела с details-массивом; тексты после
  handleApiError — без `[object Object]`.
- Исполнение **реального** board.js в node (эмуляция DOM, извлечение функций без
  правки файла): все ветки handleApiError (422 массив/объект/пусто/без details,
  !body/HTML-502, 404, 401→redirect), parseBody (async-reject → null),
  renderComments (4 варианта полей).
- node --check; диф-границы коммита; отсутствие изменений в backend/, tasks.md,
  остальных JS.

## Не проверено

- Реальный браузер (DOM-события, оверлеи) — вне инструментария; изменение
  затрагивает только тексты ошибок, behavior не менялся.
- nginx-502 вживую (эмуляция телом HTML при статусе 502 в node-смоке).
