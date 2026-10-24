# Code review: redesign-console — dev-волны 1.1–2.7

- flow: flow=1 role=code_reviewer repo=/home/openclaw/ekotov-wiki scope=redesign-console
- Reviewer: code_reviewer (Флоу 1)
- Дифф: `origin/main...HEAD` (281bfbb..07c8f13, коммиты 1.1–2.7), worktree /tmp/wt-red-rev, ветка art/rev-001
- Вердикт: **APPROVE** (3 minor-находки, блокеров нет)

## Проверки (все программные, на дереве HEAD)

### 1. DOM-хуки §D2/ОГР-28 — PASS
Полный grep `querySelector/getElementById/closest/classList` по `frontend/static/js/**`
(включая `data-col-count`, `#readout-act/done/date` из cards.js 2.2 и
`.wiki-layout[data-page-id]` из tree.js 2.3) — все селекторы резолвятся в
шаблонах/pages.py/CSS. Ни один хук из списка design §D2 (`.nav-item*`, `#sidebar`,
`#burger-button`, `sidebar-open`, `.task-card*`, `.fastline-column`, `.chip`,
`.spoiler-*`, `lb-*` и т.д.) не переименован. Подсчет вхождений по каждому хуку
HEAD vs 281bfbb — расхождение только в комментарии app.css (упоминание
`.g-card:hover` в пояснении BUG-017), не селектор. JS-правки (cards.js, tree.js)
аддитивные декоративные, `aria-hidden` на decor, поведение не трогают.

### 2. static_v — PASS
`grep -rn static_v backend/` → только `backend/app/pages.py:60`
`templates.env.globals["static_v"] = "redesign-1"` (единственная функциональная
строка pages.py в диффе, impact.md «ОДНА строка» соблюден). Favicon-маркер
`<!--cache:v=2-->` внутри data-URI (base.html) — бамп по design §D4.

### 3. Правки тестов по impact.md — PASS
8 файлов, все правки — замена значений/пар токенов, ни один тест/ассерт не удален:
- п.1 `test_qa21_netdata_sidebar_ui.py`: t600/bg2-hover/focus-ring-cyan/active-bg3 ✓
- п.2 `test_r6_tag_combobox_ui.py`: accent `#f0b45c`, soft `#3a2c12` ✓
- п.3 `test_board_fastline.py`: bg `rgb(58,44,18)` (--p-amber-900), border solid ✓
- п.4 `test_p12_ui_polish_r8.py`: пары amber-900/amber-400, комментарий обновлен ✓
- п.5 `test_p15_wiki_tree.py`: mark bg `rgb(58,44,18)` ✓
- п.6 `test_r5_profile_card_ui.py`: bg2 `#1d2b40`, accent `#f0b45c` ✓
- п.7 `test_r3_vis_ui.py`: t900-заголовок, hover-рамка border2 — семантика сохранена ✓
- п.8 `test_p12_nav_icons_favicon_r8.py`: `%23f0b45c`, cache v=2 ✓
Доп. `page.wait_for_timeout(250)` в 3 местах — ожидание transition 140ms,
легитимная стабилизация, не ослабление ассерта.
Примечание (F-2): значения п.1 взяты из утвержденной дельты спеки navigation
(`--p-text-600`), а не из устаревшего прогноза impact.md (t900) — см. находки.

### 4. ОГР-8 (внешние ресурсы) — PASS
grep `https?://|@import|cdn.` по templates+CSS: единственное вхождение — текст
комментария в login.html (описание Secure-куки). CDN, внешних шрифтов, @import
нет; favicon — inline SVG data-URI.

### 5. Мертвые V3-стили — PASS
Эвристический скан «селектор CSS без вхождения в templates+pages.py+JS»:
baseline 34 / HEAD 31 «мертвых», **новых — 0**, 3 предсуществующие
ложноположительные исчезли. Deprecated V3-алиасы из :root удалены в 2.7
(«--p-paper/--p-clay/--p-blue-050/200/--p-amber-700/--ink» — grep 0 вхождений).

### 6. Доступность — PASS
skip-link первый фокусируемый → `#main-content` (base.html:34); focus-visible
(99 вхождений), `prefers-reduced-motion` (22), aria-current/aria-expanded/
aria-controls сохранены; декор (LED, трек фастлайна) — `aria-hidden`. kbd-футер
не рендерится (реальных глобальных хоткеев нет — design §D2 «ложный аффорданс
запрещен»); kbd в лайтбоксе галереи соответствует реальным обработчикам
gallery.js:1275–1290 (ArrowLeft/Right/Escape) — предсуществующее, вне диффа.

### 7. Токены — PASS
`app.css :root` = `design/redesign-pro/tokens-console.html` дословно (сверка всех
65 переменных — 0 расхождений). Голые hex вне токен-блоков/снимков: 0
(все вхождения — внутри :root, локальных снимков login/video/weather и
комментариев). Все `var()`-ссылки (CSS + inline `<style>` шаблонов) резолвятся
в :root либо локальный скоуп — «ни один селектор не ссылается на отсутствующий
токен» выполнен.

### 8. Мобильные брейкпоинты (p23) — PASS
board.css 480px-ветки не тронуты (той же структуры, что baseline); контракт
«481–768px — десктопный ряд» держится отсутствием media-ветки (как в baseline),
`test_p23_fastline_mobile_ui.py` в диффе отсутствует. Новая раскладка каркаса —
одна ветка ≤860px в app.css, в зоны доски не протекает; `body.modal-shell-open
{overflow:hidden}` (BUG-013) и 44px тач-таргеты перенесены в новую ветку.

## FINDINGS

### F-1 (minor, doc-drift): устаревший комментарий drawer в base.html
`frontend/templates/base.html:35–40` — комментарий волны add-responsive-mobile
описывает старое поведение: «мобильная шапка с бургером. Видима ТОЛЬКО ≤768px».
После 2.7 burger/drawer скрыты безусловно (`.burger {display:none}`), мобильная
раскладка ≤860px — сайдбар наверх (мокап FR-131). На функциональность не влияет
(хуки сохранены сознательно, ОГР-28), но комментарий вводит в заблуждение
следующего ревьюера. Рекомендация: обновить комментарий в обслуживающем
изменении (или в хвосте редизайна).

### F-2 (minor, doc-drift): impact.md п.1 не соответствует финальной спеке
`openspec/changes/redesign-console/impact.md:41` предсказывал «текст пункта
`#e7edf4` (t900)»; утвержденная дельта specs/navigation и реализация
(app.css `.nav-item {color:var(--p-text-600)}`) — `--p-text-600` (#a7b7c8),
и тест ассертит t600. Dev поступил правильно (спека старше прогноза),
но расхождение impact↔spec стоит пометить, чтобы qa_checklist (3.2),
собиравшийся из impact, не нес устаревшее значение t900.

### F-3 (info, риск дрейфа): локальные снимки токенов login/video/weather
`login.css:8–24`, `video.html:26–42`, `weather.html:29–55` дублируют палитру
литеральными hex (документированное решение волн 2.4/2.5 — «снимок
tokens-console», скоупы сохранены). Значения сейчас идентичны снапшоту
(проверено, 0 drift), но при будущей правке палитры три копии надо бампить
руками. Рекомендация: при следующем изменении токенов — централизовать
(общий файл/переменные сборки) или добавить lint-проверку равенства снимков.

## Верdict

APPROVE. Все гейты чек-листа (хуки, static_v, тесты-значения, ОГР-8, мертвые
стили, a11y, токены, брейкпоинты) — PASS; находки F-1..F-3 не блокируют
(документация/информационные), могут уйти в обслуживающий хвост.
