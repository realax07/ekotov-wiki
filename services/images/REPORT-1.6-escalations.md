# REPORT-1.6 — Dev: закрытие эскалаций Э-3/Э-4 (change add-gallery-service)

- Роль: dev (авто-делегация, correlation_id `6fb2c1bdbaf048ed81f170c3eacf68a7`)
- Дата: 2026-10-05 | Ветка: `add-gallery-service` (worktree
  `/home/openclaw/ekotov-wiki-worktrees/dev-12-gallery`) | Push: НЕТ
  (правило конвейера — пушит ПМ)
- Задача: 1.6 [M] tasks.md — решение Заказчика
  `2026-10-05-gallery-fix-escalations` («по gallery — чини все»)
- Зона записи: `services/images/**`, `backend/app/auth.py`,
  `frontend/static/**` — выхода за зону нет

## Статус этапов ворот (обязательный блок, AGENTS.md п.9)

| Ворота | Статус | Примечание |
|---|---|---|
| prepare / flowctl | **SKIPPED** | сабагенту не передан запуск flowctl (adapter=manual); ворота — зона ПМ |
| reserve (session_check) | **PASS (со слов ТЗ)** | worktree dev-12-gallery ↔ ветка add-gallery-service сверены (J7-чек: toplevel/branch совпали) |
| zone-check (дифф ⊆ зона) | **PASS** | git status — только `services/images/**`, `backend/app/auth.py`, `frontend/static/js/gallery.js` |
| юнит-тесты images | **PASS** | **28 passed** (26 прежних + 2 новых TC-gal-104/105) |
| юнит-тесты search (регресс эталона) | **PASS** | 12 passed |
| web-сьют (регресс ядра+фронтенда) | **PASS** | см. ниже — прогон на стенде после фикса |
| /me обратная совместимость | **PASS** | tests/api: test_auth_me + test_authme_r3 + test_users_r4 — 10 passed на живом стенде; смоук me.id owner=1/wife=2 |
| openspec validate --all --strict | **PASS** | 15 passed, 0 failed |
| flow_check.py | **FAIL (пред-существующий, эскалация Э-5)** | J10: вердикт «ОДОБРИТЬ» в review-001-1.2 не распознается регэкспом approve; красный и на чистом HEAD до моих правок — см. «Эскалации» |
| push | **SKIPPED (запрещен)** | коммит локальный |

## Что сделано (по пунктам задачи а–д)

### (а) services/images — tags в списке (Э-3) — `app/gallery.py`

- `_LIST_SELECT` дополнен скалярным подзапросом-агрегатом
  image_tags+gallery_tags → `tags_csv` (group_concat по подзапросу с
  ORDER BY g.name — имена тегов алфавитны и детерминированы);
  `_serialize_list_row` превращает `tags_csv` в `tags: [имена]`
  (NULL/без тегов → `[]`). SELECT общий для списка и detail — **паритет
  ответов** по трассировке: одно место, расхождение невозможно.
- Байтовый формат списка изменился только добавлением ключа `tags`
  (прежние ключи не тронуты).
- Обновлены шапка-docstring модуля и таблица API в `README.md`.

### (б) ядро — id в /api/auth/me (Э-4) — `backend/app/auth.py`

- В ответ `me` добавлен `"id": <users.id>` (row[6] — SELECT его уже
  читал). Только добавление ключа: `user`/`display_name`/`role`/`bio`/
  `avatar_url` не менялись, 401-ветка (`{"user": ""}` / middleware) не
  тронута — обратная совместимость с profile.js/settings (читают
  именованные ключи — сверено по коду profile.js fillProfile).

### (в) frontend — `static/js/gallery.js`

- **Пилюли тегов на карточках** (мокап 1.1 design/gallery-grid.html):
  в `buildCard` к `.g-card-tags` после категории добавляются
  `span.task-tag` из `img.tags` (createElement+textContent — XSS-дисциплина
  сохранена). Пилюли также в мете лайтбокса (мокап gallery-lightbox.html).
- **Мост /api/users демонтирован**: удалены `fetchUsers`,
  `state.usersById`, вызов в init (был `Promise.all([fetchMe(),
  fetchUsers()])` → теперь `fetchMe().then(fetchImages)`).
- **«Свой комментарий» по прямому me.id**: `isMyComment` сравнивает
  `comment.user_id === me.id` (числовое сравнение) вместо резолва
  логина через мост. state.me расширен комментарием про id.
- **Селект тегов фильтра наполняется из списка** (следствие Э-3):
  collectFacets собирает имена тегов из поля tags элементов списка —
  фильтр «Тег» полон сразу, а не по мере открытий лайтбокса
  (loadTagFacets-заглушка удалена, общая пересборка вынесена в
  fillTagFilterOptions, appendKnownTag переиспользует её).
- Загрузивший в мете лайтбокса: резолв login был единственной второй
  функцией моста; после демонтажа показывается «загружено <дата>» (автор
  резолвит только сервер в комментариях). Отступление от мокапа
  (подпись «ekotov») — осознанное, зафиксировано ниже (О-1).
- Кеш-бастинг `?v={{ static_v }}` — **НЕ бампался** (r6.1 на проде;
  поднимется релизным бампом при выкате пакета, по ТЗ).

### (г) юниты images — 2 новых

- `TC-gal-104 test_list_includes_tags_of_each_image`: upload с 2 тегами →
  элемент списка содержит оба (алфавитный порядок), паритет с detail,
  фильтр по тегу не меняет состав tags.
- `TC-gal-105 test_list_tags_empty_when_no_tags`: без тегов → `tags: []`
  в списке и в detail (не null, не отсутствие поля).
- Обновлен `test_list_order_and_fields` (точный состав ключей + tags).
- Шапка файла: трассировка TC-gal-104/105 по прецеденту TC-openapi-203+
  (TC-ID в docstring юнитов сервиса — конвенция tasks 1.1
  add-microservices-full, отдельных кейс-файлов юниты сервисов не имеют).

### (д) TC-трассировка

- TC-gal-104/105 в docstring тестов + шапка тест-файла; ссылки на
  сценарий дельты specs/gallery «Категории и теги изображений» (FR-80)
  и design §6 — в комментариях кода. Полная кейс-волна — QA 2.1.

## Верификация

| Проверка | Результат |
|---|---|
| `pytest services/images/tests -q` (env tmp-БД/том) | **28 passed** |
| `pytest services/search/tests -q` (регресс эталона) | **12 passed** |
| `pytest tests/web` (регресс web-сьюта, автостенд) | см. ниже |
| tests/api: auth_me/authme_r3/users_r4 на живом стенде ядра | **10 passed** |
| Смоук /me на стенде: id owner=1, wife=2, прежние ключи на месте, 401 без сессии | PASS |
| `node --check gallery.js` | PASS |
| `py_compile` auth.py, gallery.py (оба) | PASS |
| `openspec validate --all --strict` | 15 passed / 0 failed |
| `flow_check.py` | FAIL — Э-5 (ниже), не от диффа задачи |

Примечание к API-сьюту: tests/api целиком требует маршрутизированный
стенд (search отрезан от монолита, f0fe4ec) — здесь поднималось только
голое ядро, поэтому из tests/api прогнан домен /me + users (10 passed);
полный api-регресс — зона QA 2.1. tests/api/test_profile_r4 (2 теста
ME_KEYS) и test_gaps_r4::TC-profile-r4-101 проверяют состав me
5-ключами — под новую дельту их обновляет QA (tests/ вне зоны записи
dev; перечислены в эскалации Э-6).

## Отступления / интерпретации

1. **О-1 (мета лайтбокса):** мокап показывает «загружено сегодня,
   ekotov». Резолв uploaded_by→login после демонтажа моста /api/users
   невозможен без нового API (в списке автор — числовой id). Показана
   дата без логина. Варианты: вернуть мост под другую задачу (против
   духа Э-4), поле uploader_name в API списка (дельта сервиса — вне
   зоны 1.6) или принять упрощение. Решение — за СА/оркестратором.

## Эскалации (E-N)

- **Э-5 (пред-существующая, блокер ворот J10, вне зоны dev)**:
  `flow_check.py` падает на `code-reviews/add-gallery-service/
  review-001-1.2.md` — вердикт «**ОДОБРИТЬ**» не распознается:
  `VERDICT_APPROVE_RE = \b(approve|approved|одобрен\w*)\b` матчит
  «одобрен/approved/approve», но не «одобрить» (парсер режет `*` и
  lowerит, слово «одобрить» не подходит под шаблон). Воспроизводится на
  чистом HEAD (cd0f54e) без моего диффа — проверено stash-прогоном.
  Отсюда `flow_check: 1 ошибок(и)` на каждое движение пакета. Варианты:
  добавить `одобрить\w*` в VERDICT_APPROVE_RE (scripts/ — зона ПМ/G7,
  синхронизация с эталоном ai-factory) или поправить вербировку
  review-файла. Чинить сам в чужой зоне не стал.
- **Э-6 (сопровождение дельты me, зона QA)**: 3 теста tests/api с точным
  составом me (`ME_KEYS` в test_profile_r4.py: test_me_extended_composition,
  test_me_defaults_when_profile_empty; test_gaps_r4.py::
  TC-profile-r4-101 шаг 4) требуют обновления под 6-й ключ `id` — по
  прецеденту Р3/Р4 («Обновлены me-тесты Р3 под MODIFIED-дельту»).
  Домен /me без этих 3 — зеленый (10 passed); tests/ — вне зоны записи dev.
- **Э-7 (дельта спеки — для СА, не блокер)**: состав ответа /api/auth/me
  зафиксирован в sdd §3.1a-кватер (5 ключей); добавление `id` — новая
  дельта ядра по решению Заказчика 2026-10-05-gallery-fix-escalations.
  Требует MODIFIED-дельты auth в пакете (или фиксации в decision) —
  иначе спека и код расходятся. Аналогично поле tags списка теперь
  покрывает сценарий «Категории и теги» полнее, чем сформулировано.

## Чекбокс задачи

Чекбокс 1.6 в tasks.md НЕ отмечен — openspec/ вне зоны записи сессии
(отметка — ПМ после ревью, прецедент 1.2–1.5).

## Артефакты

- Код: `services/images/app/gallery.py`, `services/images/README.md`,
  `services/images/tests/test_images_service.py`, `backend/app/auth.py`,
  `frontend/static/js/gallery.js`.
- Коммит: локальный, ветка `add-gallery-service`, push НЕТ.
- Эскалации-источники: `frontend/REPORT-1.5-gallery-frontend.md` (Э-3/Э-4).
