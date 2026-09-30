# Impact-анализ: change add-r4-user-profile-ticket-view

> Роль: QA impact-аналитик + чеклист (ОБЪЕДИНЕННАЯ СЕССИЯ, задача 6.1 шаги 1–2; прецедент сокращения этапов — решение Заказчика, J23). Разделение усилий — в конце файла.
> Дата: 2026-09-30 | Режим: auto-edit | Пушка: НЕ было (impact по коду/графу, по указанию ПМ).
> Вход: дельты `openspec/changes/add-r4-user-profile-ticket-view/specs/` (6 доменов: auth 1 MODIFIED + 4 ADDED, navigation MODIFIED, settings 2 ADDED, board 1+1, tasks 3 MODIFIED + forms-V3 MODIFIED, search 4 MODIFIED), proposal/design, sdd §3/§9, код main (991029a: миграция R4, профиль/пароль/аватар API, настройки+tooltip, view-модалка, DEF-005, assigned/creator, поиск+suggestions/users), регресс tests/api 176p + tests/web 112p.
> Код и openspec НЕ менялись; прогоны не запускались (задачи 1.1–5.2 слиты, релизный прогон — вне этой сессии).

## 1. Затронутые области по дельтам

| Область | Файлы реализации | Дельта |
|---|---|---|
| backend: me/profile/password | `backend/app/auth.py`, `profile.py`, `main.py` | auth MODIFIED (состав me), ADDED профиль/пароль |
| backend: avatar | `backend/app/avatar.py`, `config.py` (EKOTOV_WIKI_AVATARS_DIR), Pillow/python-multipart | auth ADDED загрузка аватара |
| backend: users (read-only) | `backend/app/users.py` | новый `GET /api/users` (select исполнителя, B-1) |
| backend: tasks | `backend/app/tasks.py` | tasks MODIFIED: assigned_to_id/creator_id в контрактах, creator server-side immutable |
| backend: board | `backend/app/board.py`, `frontend/static/js/board/*` | board MODIFIED: users-line, tooltip карточки |
| backend: search + suggestions | `backend/app/search.py`, `suggestions.py` (`/api/suggestions/users`) | search MODIFIED ×4: фильтры assigned/creator, IS NULL, поля в выдаче |
| backend: middleware | `backend/app/middleware.py` | exempt-список авторизации НЕ расширяется (NFR-7) — все новые эндпоинты под 401 |
| frontend: профиль/tooltip | `profile.js`, `tooltip.js`, шаблоны `base.html`, `profile-settings.html` | navigation MODIFIED, settings ADDED, auth FR-43 |
| frontend: доска/формы/view | `board/cards.js`, `card-tooltip.js`, `task-detail.js` (read-only), `task-form.js` | board ADDED view-модалка; tasks DEF-005 V3; assigned/creator |
| frontend: поиск | `search.js` (конструктор, advanced, users-подсказки) | search MODIFIED |
| схема БД | `backend/app/db.py` (SCHEMA_SQL), `migrate_r4.py` | users: display_name, role, bio, avatar_path, avatar_updated_at; tasks: creator_id, assigned_to_id + индексы FR-46 |
| deploy | `deploy/deploy.sh` (бэкап → схема → migrate_r4 → рестарт), `deploy/nginx-*.conf` (location /avatars/) | ОГР-16/ОГР-19 |

## 2. Существующие/новые тесты пакета — вердикты (все уже в наборе)

| Тесты | Файл | Вердикт | Основание |
|---|---|---|---|
| TC-me4-001/002 + TC-profile-001…007, TC-passwd-001…004 | tests/api/test_profile_r4.py (13) | **keep** | Постоянное контрактное поведение: состав me (ключ `user` сохранен — backward-compat), GET/PUT профиля, 422 справочник ролей, 401 вне exempt, Д-10/Д-11.Fixture `_restore_profile_defaults` возвращает role=«Product manager» — иначе повторный migrate_r4 даст exit 1 (сам тест документирует связность с миграцией) |
| TC-ava-001…007 (+4b/4c) | tests/api/test_avatar_r4.py (9) | **keep** | FR-42/NFR-10/Д-8: png/jpg, 422 тип/размер/битый, 256px-квадрат, 401, перезапись + инверсия `?v=` (кеш-бастинг) |
| TC-assign-api (post/patch assigned, creator immutable) | tests/api/test_tasks_assign_r4.py (11) | **keep** | ОВ-26/FR-37: assigned опционален, 422 несуществующий пользователь, creator = сессия и не входит в контракт PATCH, users в GET task/board |
| TC-search-r4-001…008 | tests/api/test_search_r4.py (8) | **keep** | FR-46: фильтры assigned/creator/IS NULL, 422 неизвестный логин, 400 синтаксис, поля в выдаче |
| TC-users-001…004 | tests/api/test_users_r4.py (4) | **keep** | Контракт GET /api/users: состав, сортировка, read-only, 401 |
| TC-migr-r4-001…010 | tests/api/test_migration_r4.py (10) | **keep** (частично candidate-archive-стиль по природе, но метки не менялись — тесты на копиях БД, быстрые) | NFR-9: снапшот «ноль потерь», бэкфилл creator/assigned=owner 100%, роли ОВ-21, идемпотентность (rerun noop), негативы (owner отсутствует, расхождение сверки → exit 1), foreign_key_check |
| TC-auth-me (R1/R3) | tests/api/test_auth_me.py, test_authme_r3.py | **keep** | Backward-compat me: логин/сессии/401/истекшая — расширенный состав не ломает прежних потребителей |
| TC-search-001…011 (R1) | tests/api/test_search.py | **revalidate → подтвержден keep** | Расширяющий MODIFIED: прежние фильтры/пустой фильтр/400-негативы семантически не изменились (пути не менялись, только состав ответа+); дефект волны 5 (row[10] tags=[]) уже пойман и починен прогонами |
| TC-sugg-* | tests/api/test_suggestions*.py | **keep** | Старый эндпоинт `/api/suggestions` не изменен; новый `/users` — отдельный роут |
| TC-board-*, TC-UI-006…015 | tests/api/test_board.py, tests/web/test_board_tasks_ui.py | **keep** | Клик по карточке теперь открывает view-модалку — тесты 4.1 переписаны под новую механику (hidden обеих оберток, «Закрыть»); TC-UI-009 признаки —(attrs в view) подтверждены |
| TC-assignu-101…107 | tests/web/test_board_assign_ui.py (7) | **keep** | ОВ-24/25/26 UI: Unassigned курсив, строка во всех столбцах+fast, tooltip карточки, reduced-motion, select форм, creator в форме отсутствует |
| TC-search-r4-ui-001…004 | tests/web/test_search_r4_ui.py (4) | **keep** | Конструктор assigned/creator + подсказки из /api/suggestions/users, «без исполнителя», advanced UI, Unassigned в выдаче |
| TC-view-101…109 | tests/web/test_view_modal_r4.py (9) | **keep** | FR-47/Д-9/ОГР-18: read-only, отличие от форм, «Редактировать», закрытие, users-ряды (route-перехват), fast, поиск→view |
| TC-tip-101…108 | tests/web/test_tooltip_r4.py (8) | **keep** | FR-43: hover/focus, пустой bio, аватар в tooltip, позиционирование, переиспользование модуля, reduced-motion, клик сквозь tooltip |
| настройки пользователя UI | tests/web/test_settings_profile_r4.py (10) | **keep** | FR-39…42 UI + ОГР-20 (нет категорий), 401-редирект, роль ровно 2 опции, Д-10 очистка, аватар-превью+сайдбар |
| TC-r3nav-*, TC-r3form-* | tests/web/test_r3_profile_ui.py, test_r3_formv3_ui.py | **keep** | FR-33 блок (в т.ч. нет лишних контролов — ОГР-15), формы V3 (DEF-005 зоны: теги-чипы, поля+фокус-кольцо, приоритет, edit-форма целиком, все интерактивные стилизованы — DEF-004) |

**Итог: revalidate-эскалаций нет, retire нет.** Все затронутые существующие тесты уже обновлены в задачах 1.1–5.2 и слиты в 991029a; MODIFIED-дельты покрыты расширяющими тестами, а не переделкой старых.

## 3. Архитектурные допущения (обязательный вопрос E10 — внешние компоненты)

| Допущение | Источник | Покрытие тестами | Статус |
|---|---|---|---|
| nginx `location /avatars/` → alias `/var/lib/ekotov-wiki/avatars/`, `expires 7d`, `Cache-Control: public` | ОГР-16, review-001 C-1; шаблоны deploy/nginx-*.conf | НЕТ: web-тесты видят только `src=/avatars/…?v=` (test_avatar_png_upload_preview), заголовки и alias не проверяются | **слепой контур** — смоук на проде после деплоя (curl -I) |
| Отдача аватаров вне rsync-корня прода | review-001 blocker C-1 | НЕТ (средовое) | ручная сверка по runbook |
| Бэкап прода до накатки миграции (БД + каталог аватаров) | ОГР-19, NFR-9 | deploy.sh: `.backup` + fail на пустой файл; логика миграции покрыта test_migration_r4 на КОПИЯХ | запуск на проде — вне автотестов; чеклист-пункт |
| `static_v` бамп на релиз (сейчас `r3.2` в pages.py; аватар-CSS/JS и view-модалка меняли статику) | ОГР-16, урок DEF-002/003, review-001 C-5: один финальный бамп `r4.x` | НЕТ — прогонами не ловится (браузерный кеш) | **слепой контур** — релизная дисциплина; отметка в deploy.sh есть |
| Pillow + python-multipart с пинами | research §1/2 | косвенно: test_avatar_r4 декодирует и проверяет размеры | покрыто поведенчески |
| Миграция идемпотентна на проде (повторный deploy) | spec «Идемпотентность», NFR-8-образец | ДА: test_r4_rerun_is_noop | покрыто |
| Общая модель «без прав»: любой авторизованный правит assigned | ОВ-26/ОГР-6/NFR-4 | ДА: test_patch_assign_and_clear (owner), wife-сессии в creator-тестах | покрыто |

## 4. Риски регресса (приоритет)

1. **Миграция существующих данных (NFR-9)** — высший. Потеря логинов/хешей/полей задач недопустима. Митигировано снапшот-тестом «ноль потерь», бэкфиллом 100%, негативом «расхождение → exit 1». Остаточный риск — только прод-исполнение (см. ОГР-19) и связность: тестовые фикстуры обязаны возвращать role в справочник, иначе повторный migrate_r4 падает (задокументировано в test_profile_r4).
2. **Backward-compat `GET /api/auth/me`** — ключ `user` обязан остаться (старые потребители: сайдбар R3, тесты R1/R3). Покрыто TC-me4-001 + старыми keep-тестами. Аналогично задачи/поиск: расширение состава без смены путей — покрыто прогоном старых TC-search/TC-UI.
3. **Кеш-бастинг аватара** — `?v=avatar_updated_at` инвертируется при перезаписи (TC-ava-007), но nginx-заголовки не тестируются (п.3): при ошибке конфига пользователь не увидит новый аватар 7 дней.
4. **Хрупкость row-индексов search.py** (волна 5: row[10] tags=[], pair[2] 500) — расширяли SELECT дважды за волну, оба дефекта пойманы прогонами. Урок: API-сьют не проверял содержимое tags — уходит в чеклист (CHK-R4-99).

## 5. Средовые требования прогона

- `EKOTOV_WIKI_AVATARS_DIR` на tmp-каталог стенда (web-фикстуры профиля/tooltip).
- Seed: owner/wife (NFR-4), роль owner после миграции = «Product manager» — обязательное предусловие миграционных тестов.
- Изоляция: cleanup созданных задач обязателен (урок TC-assignu-106: без cleanup ломаются count-ожидания соседних search-тестов).

## 6. Разделение усилий impact vs checklist (объединенная сессия, J23)

- Impact-шаг (п.1–5, вердикты по ~40 тестам/файлам, сверка MODIFIED-семантики со спекой): ~35% времени сессии.
- Чеклист-шаг (CHK по 88 сценариям 6 дельт + дополнения, трассировка FR-NN, статусы покрытия): ~65%.
- Синергия: impact-вердикты «keep» подставлялись в колонку покрытия чеклиста без повторного чтения тестов; E10-вопрос дал 2 слепых контура (nginx /avatars/, static_v) сразу в оба артефакта.
