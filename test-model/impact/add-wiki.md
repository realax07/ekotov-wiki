# Impact-анализ: change add-wiki

> Дата: 2026-10-10 | Режим: QA-хвост PR (Этап C: задачи 4.1–4.4 прогнаны,
> артефакт-пробел — чеклист/кейсы/impact для PR #144). Вход: дельты
> `openspec/changes/add-wiki/specs/` (navigation MODIFIED ×1, wiki ADDED ×14),
> requirements.md пакета (FR-107…FR-116, NFR-30…NFR-34), design.md §1–§7,
> tasks.md (волны 1–4 + QA), прецедент
> `test-model/impact/add-responsive-mobile.md`.
>
> Факт реализации: ветка `pipeline/p15-stage-a` (волна 3 = 6fdc36c; HEAD
> прогонов 91658ec/a374381). Факт QA: api 62 passed (27 API + 35 sanitize)
> + полный регресс ядра 274 passed / 0 failed + NFR-30 все цели с запасом
> ×3–10 (REPORT-4.1); web-desktop 29 passed + desktop-регресс 193 passed
> (14 фейлов = не-волна-3, baseline-сверка) + DV-контроль 14/14 (REPORT-4.2);
> web-mobile 12/12 после фикса BUG-017 (REPORT-4.3); смок стенда 16/16 +
> репетиция migrate_wiki на фактическом прод-снапшоте ОК×2 +
> кроссбраузерность Chromium/Firefox 16/16 × 2 (REPORT-4.4). DV
> review-001-design.md: СООТВЕТСТВУЕТ/ОДОБРИТЬ (0 blocker; major DV-1
> исправлен — подтверждено test_search_snippet_plain_text_no_tags и
> DV-контролем).

## Затронутые зоны (по дельтам и коду волн)

| Зона | Что меняется | Риск | Проверка |
|---|---|---|---|
| backend/app/wiki.py, sanitize.py (НОВЫЕ) | REST 9 путей `/api/wiki/*`, sanitizer whitelist, сессии по паттерну board.py | средний: новый публичный API — XSS через HTML-контент, 401-гейты | 4.1: sanitize 35p + 401 на все методы; NFR-30 p95 ×3–10 запас |
| backend/app/pages.py, main.py | роуты /wiki, /wiki/{id} — заглушка → живой раздел; подключение роутера | низкий: middleware-редиректы уже покрыты | 4.4 смок п.7 (302), test_wiki_page_scaffold_no_todo_stub |
| backend/app/migrate_wiki.py (НОВЫЙ) | 2 таблицы + 3 индекса, идемпотентно, BEGIN IMMEDIATE | средний: боевая БД — необратимая накатка | 4.4 §(а): репетиция на прод-снапшоте ОК×2, 0 расхождений по 13 таблицам; откат кода безопасен |
| frontend/static/js/wiki/* (tree, search, page, editor, history), wiki.css, wiki.html | новый раздел целиком по мокапам 1.1 | средний: UX/мокапы, токены V3, ОГР-8 | 4.2: 29p + DV 14/14; DV review-001 (токены, ОГР-8); 4.3: 12/12 на 375px |
| Соседние разделы (доска, поиск, галерея, настройки, auth) | не меняются — риск регресса от миграции/статики | низкий | 4.1 регресс 274p/0f; 4.2 desktop-регресс 193p; 4.3 смоук P14 на 375px |
| contracts/openapi.json | волна 3 добавила /wiki/{page_id}/history | низкий: контракт vs живая схема | test_openapi_r11 green после перегенерации (4.1 §6; правка в worktree — на фиксацию dev-циклу) |

## Известный фон / вне скоупа

- test_search* (14 кейсов) — отрезка f0fe4ec (add-microservices-full), падают
  на любом коммите после отрезки; к волне 3 отношения не имеет (4.1 §5).
- Desktop-хвост 4.2 (14f/3e) — baseline dec22a6 воспроизводит: загрязнение
  tmp-БД галерейными картинками, стенд conftest без wiki-схемы/images-сервиса,
  flaky-пятерка; navigation wiki-stub тест семантически устарел (кандидат на
  обновление в 6.1).
- BUG-017 (тач-таргеты футера редактора) — исправлен, ре-проба 4.3: 12/12.
- compose.test-стенд требует явных migrate_gallery+migrate_wiki в seed —
  замечание RUNBOOK (4.4), не блокер прода.

## Вывод

Волны 1–4 и QA-хвост не ломают существующую функциональность; новые зоны
(эндпоинты, редактор, миграция) покрыты прогонами 4.1–4.4. Вход 4.5: боевая
накатка migrate_wiki разрешена. Блокеров для PR нет — остаются
организационные гейты pr_validate вне компетенции qa_author (delegation-реестр
Reviewer-Delegation для code-reviews add-wiki).
