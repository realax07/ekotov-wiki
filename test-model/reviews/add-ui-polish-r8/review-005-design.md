# Review 005 — Ре-ревью фикс-диффа design-валидации add-ui-polish-r8 (короткий круг)

Reviewer-Delegation: deleg-67dffa6e6f4248cb
Gate correlation: 67dffa6e6f4248cbbba9774abec8a131
Дата: 2026-10-07. Ревьюер: design_validator (тот же ревьюер, что review-004-design).
База: main @ 395d5a6 (merge PR #63 — фикс-дифф `395d5a6^..395d5a6`, коммиты c2f0c47 + 5e4a16f, ветка feature/p12-fixn-design-return).
Назначение: ре-ревью моего же RETURN (review-004-design: major N-1, minor N-2, minor N-3) — построчная сверка каждого пункта на живом стенде.

## Метод

Тот же инструмент, что в review-004: computed-styles через Playwright (headless Chromium, playwright 1.63.0, Python 3.11 venv `/home/openclaw/venvs/wiki`), построчная сверка «дефект → ожидание review-004 → факт на фикс-диффе».

Стенд (поднят по tests/README.md, гашен после): uvicorn `app.main:app` :8080 (tmp-БД `/tmp/dv-r5-rev.db`: схема `python -m app.db` + seed owner/wife + `migrate_r4`; `AVATARS_DIR=/tmp/dv-r5-avatars` — обязателен) + http.server :54885 на `frontend/static` (роль nginx: `/static/*` — статика, остальное — app; playwright route-переброс). Задача `QAT-dv-r8-review` создана через UI; view-модалка открыта кликом по карточке. Сквозной сценарий: open → замеры → **Escape → повторный open** (регрессия собственного N-1-фикса на переоткрытие) → замеры → скриншот (визуальный осмотр) → закрытие. Смоук-прогон: `pytest tests/web/test_view_modal_r4.py`.

## Построчная сверка замечаний review-004

### N-1 (major) — задвоенный `.task-view-head`

| Замер (view-модалка, 1-е открытие) | Ожидалось (мокап `.modal-head`, review-004) | Факт после фикса | Вердикт |
|---|---|---|---|
| count `.task-view-head` | 1 | **1** (вложенных — 0, детей с border-bottom — 0) | устранен |
| padding шапки | `24px 32px 16px` | **24px 32px 16px** (computed) | устранен |
| border-bottom | один, 1px | **ровно 1px**, один (на head, детей с border-bottom: 0) | устранен |
| контент от края окна | 32px | 32px (следствие одиночного паддинга) | устранен |

**Регрессия переоткрытия** (репро open → Escape → open; фиксы c2f0c47/5e4a16f: изъятие `#task-detail-title` до очистки head + preserve-аргумент `buildViewHead` + self-healing):

| Замер | Ожидалось | Факт | Вердикт |
|---|---|---|---|
| `.task-view-head` после reopen | 1 | **1** | OK |
| `#task-detail-title` | 1 узел, текст задачи | **count=1, text=`QAT-dv-r8-review`** | OK |
| padding после reopen | 24/32/16 без накопления | **24px 32px 16px** (не 48/64) | OK |
| скриншот: двойная линия / двойной отступ шапки | нет | нет (одна линия-разделитель) | OK |

### N-2 (minor) — дубль `.task-view-actions` (футер модалки)

| Замер | Ожидалось (мокап `.modal-foot`, review-004) | Факт после фикса (board.css: дубль 4.1 удален, осталось только r8-правило :1149) | Вердикт |
|---|---|---|---|
| count `.task-view-actions` | 1 | **1** | OK |
| gap | 8px (`--space-1`) | **8px** | устранен |
| margin-top | 0 (футер прилегает) | **0px** | устранен |
| border-top | один, 1px | **1px** (ровно один разделитель; скриншот — одна линия над футером) | OK |

### N-3 (minor) — сайдбар: gap иконка/текст (app.css `.nav-item` display:block → flex+gap)

| Пункт (все 6 рядов сайдбара) | display | align-items | gap | Выравнивание |
|---|---|---|---|---|
| Доска | flex | center | **8px** | ровно |
| Поиск | flex | center | **8px** | ровно |
| Wiki (с todo-бейджем) | flex | center | **8px** | ровно — бейдж не смещает иконку/текст |
| Галерея | flex | center | **8px** | ровно |
| Мониторинг | flex | center | **8px** | ровно |
| Настройки | flex | center | **8px** | ровно |

Эталонный ритм «иконка → 8px → текст» теперь единый по всем пунктам (в review-004 у Доски/Поиска/Wiki был gap 0). Скриншот: подписи выровнены, Wiki-бейдж не ломает строку. **устранен**.

### Сопутствующее (вне трех пунктов, контроль регрессий)

- Иконки 16px currentColor в пунктах — на месте (flex-переход не задел svg display/размер).
- Токены: фикс-дифф не вводит ни одного hex-литерала вне `:root` (только `var(--space-*)`); на скриншоте модалка соответствует V3-мокапу (шапка/секции/футер/кнопки).
- Консоль браузера во время сценария: pageerror — нет; единственный resource-404 — артефакт стенда без nginx-маршрута `/api/suggestions`/favicon-контура, не продукта (в скоупе r8-зон нет).
- Попутные падения смоука на этом стенде — дефекты окружения, не фикс-диффа: `test_search_card_click_opens_view` (требует search-сервис :8378 за nginx-контуром — авто-стенд conftest его не поднимает), combobox-кейсы (посторонние демо-процессы на машине с общим тег-наименованием). Отдельно поднятым search-сервисом и чистым контуром Verified: целевые кейсы view-модалки зеленые; записано в `agents/design_validator_improvements.md`.

## Вердикт: APPROVE
