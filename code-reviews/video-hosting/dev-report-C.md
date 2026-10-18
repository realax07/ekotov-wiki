# Отчет dev по куску C (волна 4: полировка) — задача 4.1

Ветка `pipeline/video-hosting`, head 13855d5 → коммит волны 4. Зоны:
`services/video/app/videos.py` (список: ?query=/?order=),
`services/video/app/db.py` (unicode-lower), `frontend/templates/video.html`
(тулбар мокапа + CSS + пустой state), `frontend/static/js/video.js`
(поиск/сортировка/сброс, polling с фильтрами), `services/video/tests/
test_list_search_order.py` (новый), `tests/web/test_video_ui.py` (TC-vid-110),
tasks.md 4.1 [x].

## Реализовано

- **API `GET /api/videos`** (4.1(б), sdd §3): `?query=<подстрока>&order=asc|desc`
  — поиск по подстроке имени без учета регистра (lower()-нормализация ОБЕИХ
  сторон LIKE) и сортировка по имени в обе стороны; комбинируется с фильтром
  категории куска D (`?category=<id|none>`, AND-условия); пустой/whitespace
  query — все видео; неверный order — 422 в форме ядра (паритет category);
  без order порядок прежний (created_at DESC — паритет
  test_list_order_newest_first куска A). `%`/`_`/`\` в query — литералы
  (ESCAPE '\'), не wildcard'ы.
- **Кириллица без учета регистра — отклонение от буквы 4.1 осознанное**:
  встроенные lower() и COLLATE NOCASE SQLite — ASCII-only («ПРИВЕТ» не
  складывается, проверено), а сценарий «Поиск и сортировка» спеки прямо
  требует кириллицу. Решение: в db.get_connection lower перекрыт
  application-defined функцией (str.lower, deterministic=True) — SQL
  остался ровно «lower()-нормализация обеих сторон LIKE» + ORDER BY
  lower(filename) из задачи; поведение на ASCII идентично встроенному.
- **Фронт** (4.1(в), дословно мокап video-list.html): поле «Поиск по имени»
  (#video-search, type=search, placeholder «подстрока имени…», debounce
  300 мс + trim), select «Сортировка» (#video-sort: «Имя А→Я» — дефолт/
  «Имя Я→А»), кнопка «Сбросить» (#video-filter-reset — поиск+категория к
  дефолту, сортировка к asc); порядок контролов тулбара — поиск →
  категория → сортировка → сброс → счетчик → «Загрузить видео»;
  CSS input'а и .filter-reset — из мокапа (нижняя линия 2px, hover/focus).
  Пустой результат фильтра — тихий state мокапа «Ничего не найдено…»
  (#video-search-empty), отличен от «Видео пока нет» пустой библиотеки.
- **Polling-шов с куском B**: параметры списка собраны в buildListParams() —
  refreshTick (автообновление 3 с) ходит с теми же query/order/category,
  что и loadList (попутно устранен прежний дефект: polling терял фильтр
  категории); отрисовка списка — общий renderList().
- **Превью в карточках** (п.1 ТЗ волны) — уже закрыто куском B (r2: превью
  перенесено из C в B): buildCard для ready ставит img preview_url с
  фолбэком на .ph-frame при 409, для uploaded/converting/error — плейсхолдер
  «превью появится после конвертации»; в C не трогалось, только проверено.
- static_v НЕ бампится — единый финальный бамп релиза (C-5 ревью-001,
  паритет волны B).

## Тесты

- `services/video/tests`: **66 passed** (59 до волны + 7 новых:
  test_list_search_order.py, TC-vid-080…086 — поиск подстрокой
  регистронезависимо латиница/КИРИЛЛИЦА; сортировка asc/desc по имени;
  комбинирование query×category и query×none; литеральность %/_; пустой/
  whitespace query — все; неверный order 422; пустой результат 200; дефолтный
  порядок не изменился).
- `tests/web`: **+1** TC-vid-110 (test_video_ui.py): тулбар по мокапу —
  атрибуты/подписи поиска, опции и дефолт сортировки, «Сбросить», порядок
  контролов. Видео-сьют tests/web: **10 passed**.
- Сериальный полный регресс в этой среде (паритет волн B/D: стенды наборов
  не поднимаются): (а) `services/video/tests` — 66 passed; (б) видео-сьют
  tests/web — 10 passed; (в) сбор `pytest tests/` — 607 тестов / 0 errors
  (606 до волны + 1 новый); (г) полный серийный прогон `pytest tests/` —
  api-набор требует внешний стенд :8080 (массовые ERROR «не готов за 60s»,
  E6 stale-предупреждение conftest — среда, не код); tests/web — 229
  passed / 11 failed / 15 errors, все падения вне видео-домена (board/
  gallery/profile/nav), выборочная проверка 2 failed на чистом HEAD
  (git stash) воспроизвела их — претестовые, к волне C не относятся.
- `openspec validate video-hosting --type change --strict` — green;
  `node --check video.js` — ok.

## Эскалации/решения (2)

1. **Unicode-lower вместо буквального COLLATE NOCASE** (см. выше):
   acceptance-сценарий (кириллица, регистр) несовместим со встроенным
   NOCASE/lower SQLite. Сделано перекрытием lower на соединении сервиса;
   альтернатива — фильтрация в Python — отклонена (список должен
   фильтроваться одним SQL-запросом, зона db.py это позволяет).
2. **Polling терял фильтр категории** (дефект волны B, вне буквы 4.1):
   refreshTick ходил на /api/videos без параметров. Исправлен в рамках
   куска C (поиск обязан переживать автообновление), зона та же — video.js.
   Считаю minor-фиксом шва B×C, ревью волны — валидатор.
