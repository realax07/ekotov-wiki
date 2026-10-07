# REPORT-3.2-prep: препарация релиза r8-polish (добивка релизного хвоста)

Change: `add-ui-polish-r8` | Задача: 3.2 [ops] (препарация) | Дата: 2026-10-07
Решение: `2026-10-07-r8-release-tail` (добивка сабагентами через ворота; боевая выкатка 2.3/2.4 — явная развилка Заказчика).

## 1. Исходное состояние хвоста (квалификация ПМ, 2026-10-07 утро)

- Релизный бамп static_v r8-polish — влит (PR #76, b0282fa).
- Web-регресс на чистом стенде: 185p/10f. Квалификация: 8 = хвосты QAT-фикстур
  БД стенда, 2 стабильных → BUG-011, BUG-012.
- Смоук-матрица и REPORT-3.2-prep — не готовы. → настоящее решение + этот отчет.

## 2. BUG-011 — ЗАКРЫТ (в main)

- Карточка: test-model/bugs/BUG-011-body-100vh-page-scroll-regression.md, статус APPROVED.
- Фикс: PR #78 (6daf970) — body.app-shell height→min-height, .content без
  height/overflow: документный скролл восстановлен; footer сайдбара держит sticky .sidebar.
- Ревью: code-reviews/BUG-011/review-001.md APPROVE (PR #80, 991f160).
- Уточнение ревью (важно для истории): глушилка скролла 9b1e4f1 — не сам
  height:100vh на body, а связка .content{height:100vh; overflow-y:auto}.
- Мутационная проверка: откат связки → фиксатор red; возврат → green. Зафиксирована в review-001.

## 3. BUG-012 — ФИКС ГОТОВ (PR #79, ожидает code_review)

- Карточка: test-model/bugs/BUG-012-combobox-enter-double-chip.md, статус НА РЕВЬЮ.
- PR #79 (da32681): два корня закрыты одним фикс-циклом:
  1) consumed-token фильтр в syncInputAndDom (двойной чип при Enter-выборе);
  2) автостенд conftest не поднимал search-семейство (10/10 red из-за 404
  /api/suggestions — СЦ-5 «сбой загрузки» легитимен на стенде без search).
- Верификация dev: 10/10 test_r6_tag_combobox_ui green; смежные green; двойная
  мутация. Претензии подтверждены ПМ по фактам (чеки flow+e2e green, отчет на диске).
- Блокер мержа: независимый code_review (запущен 23:13 UTC 2026-10-07).

## 4. Смоук-матрица r8 (чистый стенд, 2026-10-07 вечер, main c3dc1d8)

Стенд: nginx :18443 (HTTP) → app :8080 (main c3dc1d8) + images-сервис :8389;
БД /tmp/qa-r8/verify/app.db (схема ядра + миграция gallery идемпотентно).

| Сьют | Результат |
|---|---|
| smoke_static (16 статик-ресурсов, сверка ссылок) | OK, 0 проблем |
| test_fastline_ui.py + test_p12_nav_icons_favicon_r8.py + test_r4_commentfix_ui.py | 12 passed |
| test_p12_gallery_rename_masonry_r8.py (внешний стенд) | 4 passed |
| test_r6_tag_combobox_ui.py (автостенд, из цикла BUG-012) | 10 passed |
| test_r5_crop_ui.py::scroll + test_p12n004_sidebar_footer (фиксаторы BUG-011) | green (в review-001) |

Примечание: страницы без JS-модулей в nginx-конфиге стенда давали MIME-ошибку —
вылечено include mime.types (дефект стенда, не продукта; в проде nginx полный).

## 5. Известные хвосты (НЕ блокеры 3.2, в бэклог)

- tests/api/test_suggestions* — 8 red на HEAD: tests/api/conftest.py не
  маршрутизирует search-семейство (эскалация dev-сабагента BUG-012). Отдельная задача.
- Прод-контур (docker, uid 10001, порты 8377–8379) после ребута хоста не поднялся
  в полном составе — к боевой выкатке проверить compose ps (см. RUNBOOK §1.3).
- QA-стенд-инфраструктура (:8080/18443) собирается вручную; конфиг стенда не в
  репозитории (терялся в /tmp) — кандидат в chore: scripts/qa_stand_up.sh.

## 6. Готовность к 3.2 (боевая выкатка)

- Код: main c3dc1d8 = релизный бамп r8-polish + BUG-011. BUG-012 добавится мержем PR #79 после approve.
- Протокол: deploy/deploy.sh (без миграций), бамп static_v выполнен ранее (r8-polish);
  откат — предыдущий тег frontend + images парой RELEASE_TAG (tasks.md 3.2).
- Приемка: Заказчик вживую, чек-лист P12 пп.1–12, протокол обязателен.
- Развилка 2.3/2.4 остается за Заказчиком (решение 2026-10-07-r8-release-tail).

ПМ: pm-main | Статус: PREP ГОТОВ (пункт 3 закрывается мержем PR #79 после code_review).
