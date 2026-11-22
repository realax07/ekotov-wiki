# Impact-анализ QA: change redesign-ui-a (H5)

> Дата: 2026-11-22 | Роль: qa_impact_analyst | Ветка: `feat/redesign-ui-a`
> (HEAD ff5a12d; dev-волны 1–3 и QA Волна 4 завершены). Вход: дельты
> `openspec/changes/redesign-ui-a/specs/` (7 capability, 11 Requirement,
> 29 Scenario — 6 MODIFIED + 1 ADDED), impact-раздел proposal.md пакета,
> `docs/sa/sdd-redesign-ui-a.md` §4 (план правки тестов: 12 файлов / 114
> тестов), требования `docs/ba/requirements-redesign-ui-a.md`.
>
> Зоны воздействия НЕ дублируются: единственный источник — дельты пакета +
> sdd §1.3 (маппинг «токены A → существующие переменные app.css») и §1.7
> (файлы и зоны правки). Этот документ — только тестовый срез: вердикты по
> каждому затронутому существующему тесту + сверка плана sdd §4 с реальным
> прогоном QA (docs/qa/qa-redesign-ui-a.md, 2026-11-22).

## Метод

1. Список-план sdd §4 — 12 файлов тестов с заменами «только литерал
   ожидаемого значения» (палитра/шрифт/радиус/тень/тайминг), железное
   правило: локаторы, семантика, пороги, методология — без изменений.
2. Сверка с дельтами: MODIFIED FR-128/129/130 (design-tokens), FR-132
   (board), FR-125 (gallery), FR-126 (video-ui), FR-123/124 (wiki),
   NFR-41/42 (accessibility); ADDED «Переключатель темы в каркасе»
   (navigation) — единственный ADDED, новых страниц/маршрутов не вводит.
3. Реальный полный прогон tests/web на HEAD ветки (QA Волна 4, прогон 2:
   412 passed / 9 failed / 16 errors / 4 skipped — все отклонения средовые
   :18443, классификация в QA-отчете §2.2) + браузерные сверки с эталонами
   `design-forge/a/` и `design-forge/extra/*` (обе темы, 1440/390).

## Факт прогона (HEAD ветки, QA прогон 2)

- **412 passed / 9 failed / 16 errors / 4 skipped** за 1067s. Все 25
  отклонений (без плановых skip) — средовые на живой nginx-стенд
  `127.0.0.1:18443` (EKOTOV_WIKI_BASE_URL, стенд не поднят):
  p14_22 ×6, p14_41 ×7, p12_gallery_rename ×4, qa21_gallery_ui ×6
  (5 error + TC-GAL-119), qa21_gallery_design-live ×1, games_nav ×1.
  Признак средовости однозначный — ConnectionError/ERR_CONNECTION_REFUSED
  на :18443 до любых ассертов редизайна; для regress-final канонический
  контур поднимается (`scripts/qa_stand_up.sh`), фейлы классифицированы
  в QA-отчете §2.2.
- **Регрессов редизайна кода (CSS/шаблоны/JS) НЕ обнаружено** (QA §2.1 п.2):
  все функциональные сьюты (fastline, dnd, форма, комментарии, wiki,
  галерея, видео-каркас) зеленые без правок логики — DOM-селекторы не
  тронуты (ОГР-28), API не менялся.
- Найдено и устранено в волне правок QA (§2.1 п.1): довнесенный регресс
  тестовых литералов — сайдбар 7→8 пунктов («Манчкин», апстрим вне
  редизайна) в `test_navigation_search_ui` (исправлен, 3 passed) и
  TC-GAL-119 `test_qa21_gallery_ui` (правка применена; локальная
  верификация по DOM-снапшоту, автопрогон — на живом стенде).
- Средовой дефицит окружения (§2.3): `jsonschema==4.26.0` установлен в
  `backend/.venv` (пакет из requirements.txt, в репо не фиксируется) —
  `test_coverage_uip::test_tc_p12n_008_core_api_regression` 1 passed.

## Вердикты по затронутым существующим тестам

Шкала: **keep** — тест не затронут дельтой; **revalidate** — требует
правки/перепроверки; **retire** — удалить.

### revalidate — правка цветовых литералов по sdd §4, подтверждена прогоном 2 (green)

| # | Файл (тестов) | Что менялось (дельта) | Факт прогона 2 | Вердикт |
|---|---|---|---|---|
| 1 | `tests/web/test_redesign_console.py` (36) | FR-128/129/130 + NFR-41/42: палитра-снапшот на токены A (BG0 rgb(30,15,20), золото #d6a85c, бордо #c4505c, success #5ad88e, danger #e9817f), HUD-градиенты «0» (инверсия по FR-130-THEN), focus-visible золото, hex-gate whitelist A; сайдбар-литералы 7→8 (CHK-011, апстрим) | 36/36 green | revalidate — CLOSED |
| 2 | `tests/web/test_board_fastline.py` (9) | FR-132: фон зоны → computed `--fastline-tint` (color-mix золота 8% на surface) | green | revalidate — CLOSED |
| 3 | `tests/web/test_coverage_fastline.py` (13) | FR-132: outline drop-target → бордо `--color-accent-2` rgb(196,80,92); цвета dnd-направлений accent-2/accent | green | revalidate — CLOSED |
| 4 | `tests/api/test_qa21_gallery_design.py` (2) | FR-128: whitelist `--color-accent/#d6a85c`, `--color-warning-soft/#4e3124`; гейт «нет rgba/hex вне токенов» сохранен; парсинг `:root` — первый блок (вынужденно, light-блок) | 1 passed + 1 средовой (TC-GAL-122-live :18443, §2.2) | revalidate — CLOSED (live-часть на стенде regress-final) |
| 5 | `tests/web/test_qa21_netdata_sidebar_ui.py` (6) | NFR-41/42: подпись #c6ad9f, hover #2a161d, active #371f28, focus #d6a85c | green | revalidate — CLOSED |
| 6 | `tests/web/test_r3_formv3_ui.py` (5) | FR-129/132: focus-ring золото, чипы radius 10px, пилюля bg бордо/warning/border | green | revalidate — CLOSED |
| 7 | `tests/web/test_r3_vis_ui.py` (5) | FR-132: hover accent #d6a85c; empty-state `--color-border`; тайминг 160ms; TC-vis-101 — инверсия ассерта hover-фона (ступень фона удалена THEN-ом FR-132, зафиксировано sdd §4) | green | revalidate — CLOSED |
| 8 | `tests/web/test_r5_profile_card_ui.py` (7) | FR-128: bg rgb(42,22,29), radius 18px, shadow `--shadow-1`, кнопка rgb(214,168,92) | green | revalidate — CLOSED |
| 9 | `tests/web/test_p12_ui_polish_r8.py` (7) | FR-128: `.btn-action` радиус 10px | green | revalidate — CLOSED |
| 10 | `tests/web/test_p15_wiki_tree.py` (10) | FR-123: `<mark>` bg rgb(78,49,36) `--color-warning-soft` + dark-фикстура `_redesign_a_theme` (темозависимый ассерт) | green | revalidate — CLOSED |
| 11 | `tests/web/test_r6_tag_combobox_ui.py` (11) | FR-129: подсветка rgb(214,168,92), bg rgb(78,49,36) | green | revalidate — CLOSED |
| 12 | `tests/web/test_bug004_board_empty_state.py` (3) | FR-132: dashed-border → `--color-border` | green | revalidate — CLOSED |

### revalidate — точечные правки в смешанных сьютах (sdd §4, последний абзац)

| # | Файл | Что менялось | Факт | Вердикт |
|---|---|---|---|---|
| 13 | `tests/web/test_qa21_gallery_ui.py` | TC-GAL-119: hex-точки + литералы сайдбара 7→8 (labels + count) | правка применена, DOM-верификация OK; автопрогон — средовой :18443 (ConnectionError) | revalidate — OPEN → закрывается regress-final на каноническом контуре (стенд поднимает живые :18443-кейсы) |
| 14 | `tests/web/test_p12_nav_icons_favicon_r8.py` | favicon %23f0b45c→%23d6a85c (FR-129) | 6 passed (средовый сбой «no-external 500» не воспроизвелся, QA §2.2 прим.) | revalidate — CLOSED |
| 15 | `tests/web/test_r6_wave2_ui.py` | token-цвета | green | revalidate — CLOSED |
| 16 | `tests/web/test_navigation_search_ui.py` | литерал сайдбара 7→8 (count + docstring) — довнесенный регресс волны правок, исправлен QA Волной 4 | 3 passed | revalidate — CLOSED |

### ADDED «Переключатель темы в каркасе» (navigation) — новый функционал

Покрытие: ассерты `#theme-toggle` в `test_redesign_console.py` (TC-redesign-023
— hit-target 44px на мобильном каркасе; TC-010 — light-блок
`:root[data-theme="light"]` в снапшоте токенов; TC-001 — контраст обеих
тем через `_theme_pairs`), плюс ручная браузерная проверка QA §3
(переключение без перезагрузки, инверсия, без FOUC, обе темы, 1440/390).
Вердикт: **покрыто** (авто + ручное); сценарий «localStorage недоступен» —
try/catch-инициализатор в base.html, проверен вручную (QA §3, тумблер без
FOUC) — не отдельный автотест, принято как ограничение покрытия (minor,
см. Д2).

### keep — не затронуты

- Функциональные сьюты §3.3 БА (fastline-логика, dnd, форма, комментарии,
  wiki-функционал, галерея API/UI, видео-каркас, auth/settings/weather-сьюты)
  — открывались QA только для контроля: зеленые без правок логики.
  Вердикт: **keep** (полная проверка — regress-final).
- Смоуки страниц вне объема (login/settings/weather TC-031/032) —
  переведены на семантические/неизменность-декора ассерты (ОВ-4), зеленые.

### retire

- 0 тестов. Удалений нет; переименование 3 тест-функций
  `test_redesign_console.py` (cyan→gold: TC-redesign-002/012/019) — правка
  имен, зашивавших цвет «Пульта», правомерно по смыслу (QA §2.1 п.3;
  старые ссылки в QA-отчетах относятся к прежним именам).

## Дополнения (REPORT-impact)

- **Д1 (средовые, вне дельты)**: 25 отклонений прогона 2 — живой стенд
  :18443 (классификация QA §2.2). Для regress-final: канонический контур
  `scripts/qa_stand_up.sh` (nginx :18443 → app/search/images/video/weather,
  свежая БД + seed + миграции) + полный env прогона; ожидаемый исход —
  green по всем :18443-кейсам (прецедент regress-final redesign-console:
  полный сериал на контуре).
- **Д2 (minor, покрытие)**: сценарий «localStorage недоступен» (ADDED
  navigation) без отдельного автотеста — покрыт ручной проверкой QA §3 и
  try/catch-инициализатором. Не блокер; кандидат на попутный автотест вне
  волны.
- **Д3 (принятое ограничение)**: спойлер-статья wiki — `<mark>` санитайзер
  вырезает в UI-прогоне (XSS-правило); стилизация mark покрыта ассертами
  `test_p15_wiki_tree` (CSS-срез), QA §3 примечание. Не дефект.

## Вывод

План sdd §4 (12 файлов / 114 тестов) подтвержден прогоном: все правки —
«только литерал значения» (кроме задокументированных исключений: парсинг
`:root` на первый блок, инверсия hover-ассерта TC-vis-101 по THEN FR-132),
регрессов продукта дельта не дала (412 passed, 0 дельтовых фейлов).
Счет: **keep — функциональные сьюты; revalidate — 16 позиций (15 CLOSED +
1 OPEN на живом стенде); retire — 0**. Средовые отклонения :18443
классифицированы и закрываются подъемом канонического контура для
regress-final.
