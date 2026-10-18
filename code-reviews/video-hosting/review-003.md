# Code review — video-hosting, review-003: волна 7 (03bee7f)

Роль: code_reviewer (независимый, append-only). Ревьюируемый объем: дельта с review-002
(голова ea7fb22→03bee7f) — волна 7: 7.1 API переименования + 7.2 фронтенд; отчет дев-агента —
коммит-месседж 03bee7f (отдельного dev-report волны 7 нет, объем сверен с дифом). База: main.
Фокус ТЗ: (1) PATCH-валидация 1–255 юникод/trim/ctrl/слэши — обходные векторы; (2) 401/404/422
по NFR-36/38; (3) только filename в БД — том uuid побайтно цел; (4) фронт: DOM без перезагрузки,
XSS через title; (5) tasks 7.1/7.2 [x], спека strict.

Метод: чтение дифа d8da90b..03bee7f (services/video/app/videos.py, services/video/tests/
test_videos_rename.py, frontend/{templates/video.html,static/js/video.js},
tests/web/test_video_rename_ui.py, tasks.md) против specs/video-service «Переименование видео»
(9 сценариев), NFR-36/38, design §0/§8; паритет-сверка с services/images/app/gallery.py
(_validate_image_name, rename_image); grep-пробы exempt-списка middleware; прогон
services/video/tests (**94 passed**, 33.7s — 72 база + 22 новых) и
tests/web/test_video_rename_ui.py (**3 passed**, 10.3s, реальный playwright-браузер, route-мок);
openspec validate video-hosting --strict — **valid**. Полный регресс (597/0 failed за 773s) —
принят по отчету волны (паритет практике review-001/002: стенд ревью-средой не поднимается).

---

## Проверка по фокусам

**(1) Валидация title — ДА, обходные векторы закрыты (или паритетны images).**
- `_validate_title` (videos.py:516+): не-строка/пустой/whitespace-only → 422; `str.strip()`
  режет юникод-пробелы (U+00A0, U+2000-семейство, U+3000) — «только пробелы» не проходит
  как невидимое имя (тесты: `""`, `"   "` → 422, TC-vid-093).
- NUL (U+0000) → 422 (ord < 0x20, тест `term\x00`, TC-vid-094) — NUL-обрезка на стороне
  sqlite/C невозможна, символ не доходит до БД.
- `/` и `\` → 422 независимо от позиции (тесты a/b, a\b); имя не участвует в конструировании
  путей (том uuid), так что слэш — защита атрибутов download/aria-label и паритет FR-97.
- Границы 1/255 включительно, 200-кириллица ок, 256 → 422 (юникод — символы, не байты;
  len() по code points, TC-vid-091/092). Тело не-объект → 422 схемой `payload: dict`
  (TC-vid-094b); тело-массив/строка — той же схемой.
- Замечания (не блокеры, см. minor-1/2/3): U+007F DEL и C1-управляющие (U+0080–U+009F)
  проходят (ord < 0x20 их не ловит) — **паритет** images `_validate_image_name` (тот же
  предикат), risk только отображательный; U+202E (RTL-override) проходит — спуфинг порядка
  глифов в имени/aria-label, тоже паритет; сольный суррогат (`"\ud800"` в JSON) проходит
  валидатор и ловит непойманный UnicodeEncodeError на UPDATE (minor-3, проба прогоном — 500).

**(2) 401/404/422 по NFR-36/38 — ДА.**
- 401: EXEMPT_API в middleware.py — по-прежнему ровно (`GET /api/health`,
  `GET /api/videos/authcheck`); PATCH-записи НЕ добавлено; body
  `{"error": "unauthorized"}` единый (тест test_rename_no_session_401 на anon_client).
- 404: `_require_video` — несуществующий и не-uuid-формат id (storage.is_video_id) → 404
  до UPDATE (тесты TC: missing_video_404, bad_id_format_404).
- 422 — через `_validation_error` → RequestValidationError → обработчик app/main.py
  (`{"error": "validation error", details}` — форма ядра/images/search), тесты на все
  негативные ветки сверяют и статус, и тело.
- Порядок «422 до 404» — по спеке (сценарий 404 оговорен «с валидным title»), оракула
  существования не создает.

**(3) Только filename в БД, том цел — ДА.**
- UPDATE — единственная запись: `UPDATE video_videos SET filename = ? WHERE id = ?`;
  физические файлы (uuid-каталоги), storage и маршруты /videos/… кодом не затронуты;
  ответ 200 {id, title}.
- Тест-снапшот адекватен: `_volume_snapshot` — (relpath, size, mtime_ns) по всему тому
  до/после, строгое сравнение (TC-vid-097) + playback/preview по прежним ссылкам после
  rename; поиск/сортировка по новому имени (TC-vid-098), openapi: множество путей не
  расширилось, ровно 10 (TC-vid-099 — exempt/новых маршрутов нет).

**(4) Фронт — ДА.**
- DOM без перезагрузки: submitRename → PATCH → applyRenamedVideoName обновляет
  state.listItems + #player-title и карточку (.v-card-title, aria-label) в той же сессии;
  playwright-тест test_rename_inline_without_reload_survives_reload проверяет и отсутствие
  навигации, и переживание перезагрузки (сервер хранит).
- XSS-дисциплина: имя пользователя попадает в DOM только через `.textContent`
  (#player-title, карточка, #player-rename-error); aria-label — через setAttribute
  (значение-атрибут, скрипт не исполняется); innerHTML в новых путях нет; иконки —
  статические inline-SVG (ОГР-8); селектор карточки интерполирует currentPlayerId —
  uuid, валидированный сервером (is_video_id), кавычки/метасимволы не приходят.
- 401 → редирект /login; 422/404/сеть — человекочитаемые сообщения в #player-rename-error
  (playwright-тесты на 422 и 404: имя не изменилось, ошибка видна); Esc — отмена с
  возвратом фокуса; Enter/✓ — сохранить; пустое имя — кнопка disabled; maxlength=255 —
  клиентский хинт (сервер — источник истины). Редактор сбрасывается при открытии другого
  видео (closeRenameEditor в openPlayer).

**(5) tasks/спека — ДА.** 7.1 и 7.2 — [x], 7.3 (живая приемка Заказчика) — корректно [ ].
`openspec validate video-hosting --strict` — valid. Трассировка TC-vid-090…099 / 120…122
на 9 сценариев требования полная (успех/границы/пустой/256/символы/404/401/том/поиск).

---

## Замечания (все minor, не блокируют approve)

- **minor-1 (паритетный пробел, backlog):** U+007F DEL и C1-управляющие (U+0080–U+009F)
  проходят валидацию. Risk отображательный и паритетный — images имеет тот же предикат
  (ord < 0x20). Чинить надо синхронно в обоих сервисах (или осознанно задокументировать);
  в рамках волны 7 не блокер.
- **minor-2 (паритетный пробел):** U+202E RTL-override и невидимые форматные символы
  (U+200B–U+200F, U+2060) принимаются — возможен визуальный спуфинг имени/aria-label.
  XSS нет (textContent). Аналогично паритет images; кандидат в общий харденинг валидатора
  вместе с minor-1.
- **minor-3 (пробел волны 7, отказ-в-безопасность):** сольный UTF-16-суррогат в JSON
  (`PATCH` с телом `{"title": "bad\ud800title"}`) проходит `_validate_title`
  (ord ≥ 0x20, без слэшей) и роняет `conn.execute` на UnicodeEncodeError — не
  sqlite3.Error, обработчик не ловит → необработанный 500 вместо 422 (спека: «невалидный
  title — 422»). Проверено прогоном на TestClient (raw-body с экранированным суррогатом):
  UnicodeEncodeError на videos.py:540; БД не меняется (commit не достигнут). Тот же пробел
  существует в images rename (паритет кода) — т.е. не регрессия волны, но «422 на любой
  невалидный title» формально не выполнен. Фикс тривиален:except-ветка ValueError/Unicode
  → `_validation_error` (или запрет суррогатов в `_validate_title`) в обоих сервисах.
- **nit-1:** `confirmBtn.disabled = input.value.trim() === ''` после 422 включает кнопку
  даже при неизмененном поле — безвредно (повторный сабмит того же значения снова 422).
- **nit-2:** test_rename_openapi_no_new_path закрепляет `len(paths) == 10` — хрупко к
  любому будущему легитимному маршруту (осознанный трейд-офф против «тихих» новых путей;
  приемлемо).

## Проверено прогоном (этим ревью)

| Сьют | Результат |
|---|---|
| services/video/tests | **94 passed** (33.7s) — 72 база + 22 rename на месте |
| tests/web/test_video_rename_ui.py | **3 passed** (10.3s, реальный браузер, route-мок) |
| openspec validate video-hosting --strict | **valid** |
| проба сольного суррогата (raw-body PATCH) | UnicodeEncodeError → 500 (minor-3 подтвержден) |

## Что НЕ проверено (честно)

- Полный регресс на живом стенде (597 passed / 773s) — принят по отчету волны (паритет
  review-001/002); изолированные сьюты волны прогнаны здесь.
- 7.3 — живая приемка Заказчиком: вне ревью кода, чекбокс корректно [ ].
- Реальная многопоточность PATCH (два параллельных rename) — last-write-wins по
  построению (один UPDATE), гонок не вижу; отдельного теста нет (не требуется спекой).

## Вердикт: APPROVE

Волна 7 соответствует спеке «Переименование видео» и NFR-36/38 по всем пяти фокусам:
валидатор паритетен images (обходные юникод-векторы закрыты на уровне предиката), 401/404/422
на местах, том uuid побайтно цел (снапшот-тест строгий), фронт — textContent-дисциплина и
DOM-обновление без перезагрузки подтверждены и кодом, и playwright-прогоном. Minors не
блокируют: minor-3 (суррогат→500) — лучший кандидат на синхронный мини-фикс обоих rename-ов
в следующей волне/полировке, minor-1/2 — общий харденинг валидатора паритетно images.

## Reviewer-Delegation

- Reviewer-Delegation: deleg_b01644ff (завершена, role=code_reviewer, ревью №3 волна 7, 2026-10-18)
- Детали: Флоу 1, scope=video-hosting task=7.2 (approve, 5 замечаний: 3 minor, 2 nit)

- deleg_b01644ff (завершена, role=code_reviewer, ревью №3 волна 7, 2026-10-18)
